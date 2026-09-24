"""eval/cost_report.py — the usage ruler: tokens by model, re-derived from real run manifests.

    python3 eval/cost_report.py [runs/ | one run]            # DEFAULT: tokens by model, per stage + total
    python3 eval/cost_report.py [path] --tokens              # per-stage token categories + turns (C0 view)
    python3 eval/cost_report.py [path] --usd                 # dollar footnote (CLI-reported cost_usd)
    python3 eval/cost_report.py [path] --risk-replay         # replay verify-extract risk routing on stored extracts
    python3 eval/cost_report.py [path] --verifier            # verify-extract findings: forwarded/dropped/applied/...
    add --json to any of the above for machine-readable output

Symlinked run directories (`runs/latest`, `runs/r2-live/latest`) are skipped: they point at a
run that is already listed.

Unit. The client runs on a subscription, so the stakeholder unit is TOKENS BY MODEL (fresh
input, output, cache read, cache write), not dollars. Dollars are available behind `--usd`
and are always labelled as the CLI-reported list-price figure of the demo substrate.

What is counted. Every subagent attempt the runner recorded: first attempts, repair rounds,
failed attempts, and the per-source `verify-extract` second check (recorded inside the
extraction step at `extracts[].verification.attempts`, reported here as its own stage,
`verification`). Resumed runs copy earlier legs into their manifest; when several runs are
aggregated, an attempt whose `session_id` was already counted is counted once and the number
of skipped duplicates is printed.

Per-brief figures never silently select only clean runs: the report lists every complete
Stage-1 run with its status (clean, repaired, resumed) and prints the mean over all complete
runs next to the mean over clean runs only.

Not a gate and not frozen; it reads run records only. Costs and tokens are the demo substrate
(each stage is a multi-turn Claude Code subagent). See docs/COST_MODEL.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

VERIFICATION_STAGE = "verification"

STAGE1 = ("classification", "fidelity_check", "extraction", VERIFICATION_STAGE, "conflict_pass",
          "synthesis", "render")

#: The five model stages a complete Stage-1 brief must have (verification is optional: runs
#: made before the 2026-07-30 routing have none).
REQUIRED_STAGE1 = ("classification", "fidelity_check", "extraction", "synthesis", "render")

#: Anthropic list prices, $/MTok — (input, output, cache_read, cache_write_5m).
#: Snapshot 2026-07-25 for ATTRIBUTION ONLY: the authoritative per-call dollar figure is
#: always the CLI-reported `cost_usd`; these rates just apportion it across token categories.
#: (Known gap: the CLI appears to use 1h-TTL cache writes at 2×, so the cache-write share
#: here is a floor. The tool prints computed vs reported side by side so drift is visible.)
PRICES = {
    "haiku":  (1.00, 5.00, 0.10, 1.25),
    "sonnet": (3.00, 15.00, 0.30, 3.75),
    "opus":   (5.00, 25.00, 0.50, 6.25),
}

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

#: Token categories in report order: (report label, usage key in the manifest).
TOKEN_CATEGORIES = (
    ("fresh_input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
)

#: Routing eras. The 2026-07-30 routing (commit 6d77ae7, 2026-07-29 21:51 +0300) moved
#: extraction to sonnet and added the verify-extract stage. Its risk classes routed every
#: stored extract to sonnet, and owner decision 2026-09-23 #5 declared the verifier
#: sonnet-only, so the model routing is the same from 2026-07-30 on. Round 2 is a separate
#: era because the prompts (decontaminated) and the model seam (CLI >= 2.1.280 with
#: --restricted, --no-session-persistence, per-stage deny rules) changed; a round-2 manifest
#: is recognised by the `cli.min_version` record the round-2 runner writes.
CURRENT_ROUTING_SINCE = "2026-07-29T21:51"
CURRENT_ROUTING_LABEL = "sonnet extraction + sonnet verify-extract (owner decision 2026-09-23 #5)"
ERA_LABELS = {
    "haiku-era": "Haiku-era routing (haiku extraction, no verifier) — the graded evidence",
    "current": "Sonnet routing before round 2 (sonnet extraction + verify-extract that routed every "
               "extract to sonnet; round-1 prompts, 2026-07-30 to 2026-09-22)",
    "r2": f"Current routing: {CURRENT_ROUTING_LABEL} — round-2 prompts and model seam",
    "unknown": "Routing unknown (no extraction record and no usable date)",
}


# --------------------------------------------------------------------------------------
# Reading attempts out of a manifest step
# --------------------------------------------------------------------------------------


def _stage_attempts(step: dict) -> list:
    """(stage label, attempt) for every subagent attempt inside a step.

    The runner records the verify-extract attempts inside the extraction step
    (`extracts[].verification.attempts`); they are labelled `verification` so the second
    model stage is visible as its own row instead of vanishing (or hiding inside extraction).
    """
    name = step.get("name") or "?"
    out = []
    for e in step.get("extracts") or []:
        out += [(name, a) for a in e.get("attempts") or []]
        out += [(VERIFICATION_STAGE, a) for a in (e.get("verification") or {}).get("attempts") or []]
    for c in step.get("creative") or []:
        out += [(name, a) for a in c.get("attempts") or []]
    for f in step.get("fidelity") or []:
        out += [(name, a) for a in f.get("attempts") or []]
    for key in ("classification", "synthesis", "render"):
        if key in step:
            out += [(name, a) for a in step[key].get("attempts") or []]
    return out


def _attempts(step: dict) -> list:
    """Every subagent attempt inside a step, across the shapes the runner writes (verifier included)."""
    return [a for _stage, a in _stage_attempts(step)]


def _short_model(model_id: str) -> str:
    for alias in ("haiku", "sonnet", "opus", "fable"):
        if alias in model_id:
            return alias
    return model_id


def _model_label(sub: dict) -> str:
    """One label per call. A call reports its model IDs; usage is per call, so a call that ever
    reported two models is labelled with both rather than split by guesswork."""
    ids = sub.get("model_ids") or []
    return "+".join(sorted({_short_model(m) for m in ids})) if ids else "unknown"


def _empty_tokens() -> dict:
    return {"calls": 0, **{label: 0 for label, _ in TOKEN_CATEGORIES}, "total": 0}


def _add_tokens(row: dict, sub: dict) -> None:
    usage = sub.get("usage") or {}
    row["calls"] += 1
    for label, key in TOKEN_CATEGORIES:
        value = usage.get(key) or 0
        row[label] += value
        row["total"] += value


def load_runs(path: Path) -> list[tuple[str, dict[str, Any]]]:
    """(run id, manifest) for one run directory or every run under a runs/ directory.

    Unreadable manifests are skipped, and so is every symlinked run directory under a runs/
    directory (`runs/latest`, `runs/r2-live/latest`): it points at a run that is already listed,
    and counting it would list the same brief twice.
    """
    path = Path(path)
    if (path / "run_manifest.json").is_file():
        files = [path / "run_manifest.json"]
    else:
        files = sorted(f for f in path.glob("*/run_manifest.json") if not f.parent.is_symlink())
    runs = []
    for f in files:
        try:
            runs.append((f.parent.name, json.loads(f.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def routing_era(manifest: dict) -> tuple:
    """(era, basis) for one run: read from the models the extraction step actually used,
    falling back to the run date only when the manifest holds no extraction record."""
    ext_models: set[str] = set()
    verified = False
    for step in manifest.get("steps") or []:
        if step.get("name") != "extraction":
            continue
        for e in step.get("extracts") or []:
            if e.get("verification"):
                verified = True
            for a in e.get("attempts") or []:
                ext_models.update(_short_model(m) for m in (a.get("subagent") or {}).get("model_ids") or [])
    round2 = bool((manifest.get("cli") or {}).get("min_version"))
    if verified or "sonnet" in ext_models:
        return ("r2", "extraction models + round-2 seam") if round2 else ("current", "extraction models")
    if "haiku" in ext_models:
        return "haiku-era", "extraction models"
    started = manifest.get("started_ts") or ""
    if started:
        if started < CURRENT_ROUTING_SINCE:
            return "haiku-era", "run date"
        return ("r2" if round2 else "current"), "run date"
    return "unknown", "no extraction record"


# --------------------------------------------------------------------------------------
# Verifier effectiveness: what happened to each verify-extract finding
# --------------------------------------------------------------------------------------


def verifier_effectiveness(runs: list) -> dict:
    """Per run and in total: verify-extract checks, findings raised, forwarded to the extractor,
    dropped by the deterministic filter, and — for forwarded findings — applied or rejected in
    the extractor's adjudication. Read from the `verification` block of each extract.

    A forwarded finding with no adjudication record is counted as `unadjudicated`, never
    guessed. Runs are listed as recorded; a resumed run that copied an earlier leg repeats
    that leg's verification (the same caveat as the token ledger's session dedupe).
    """
    keys = ("checks", "issues", "forwarded", "dropped", "applied", "rejected", "unadjudicated")
    per_run = []
    total = {k: 0 for k in keys}
    for run_id, m in runs:
        row = {"run": run_id, "project": _project_label(m), "era": routing_era(m)[0],
               **{k: 0 for k in keys}, "rejections": []}
        for step in m.get("steps") or []:
            if step.get("name") != "extraction":
                continue
            for e in step.get("extracts") or []:
                v = e.get("verification")
                if not v:
                    continue
                row["checks"] += 1
                row["issues"] += int(v.get("issue_count") or 0)
                forwarded = int(v.get("forwarded_count") or 0)
                row["forwarded"] += forwarded
                row["dropped"] += len(v.get("dropped") or [])
                adj = v.get("adjudication") or {}
                applied = int(adj.get("applied") or 0)
                rejected = adj.get("rejected") or []
                row["applied"] += applied
                row["rejected"] += len(rejected)
                row["unadjudicated"] += max(0, forwarded - applied - len(rejected))
                for r in rejected:
                    row["rejections"].append({"source_id": e.get("source_id"), "finding": r.get("finding"),
                                              "where": r.get("where"), "problem": r.get("problem")})
        if row["checks"]:
            per_run.append(row)
            for k in keys:
                total[k] += row[k]
    return {"runs": per_run, "total": total}


def report_verifier(result: dict, as_json: bool) -> None:
    """Print the verifier-effectiveness view (or JSON)."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    cols = ("checks", "issues", "forwarded", "dropped", "applied", "rejected", "unadjudicated")
    print("\nverify-extract effectiveness — what happened to each finding (read from run manifests)\n")
    print(f"  {'run':<20}{'project':<25}{'era':<6}" + "".join(f"{c:>14}" for c in cols))
    for r in result["runs"]:
        print(f"  {r['run']:<20}{r['project']:<25}{r['era']:<6}" + "".join(f"{r[c]:>14}" for c in cols))
    t = result["total"]
    print(f"  {'TOTAL':<51}" + "".join(f"{t[c]:>14}" for c in cols))
    rejections = [(r["run"], x) for r in result["runs"] for x in r["rejections"]]
    if rejections:
        print("\n  Rejected findings (the extractor kept its extract):")
        for run_id, x in rejections:
            print(f"    {run_id} · {x['source_id']} · {x['finding']} at {x['where']}: {str(x['problem'])[:140]}")
    print()


# --------------------------------------------------------------------------------------
# Default view: tokens by model
# --------------------------------------------------------------------------------------


def token_ledger(runs: list, dedupe: bool = True) -> dict:
    """Tokens by (stage, model) across every attempt, plus by-model and grand totals.

    Resumed runs copy an earlier run's attempts into their own manifest; with `dedupe`, an
    attempt whose session_id was already counted is skipped (and counted in `duplicates`).
    """
    rows: dict = {}
    by_model: dict = {}
    total = _empty_tokens()
    seen: set = set()
    duplicates = 0
    for _run_id, m in runs:
        for step in m.get("steps") or []:
            if step.get("kind") != "model":
                continue
            for stage, a in _stage_attempts(step):
                sub = a.get("subagent") or {}
                sid = sub.get("session_id")
                if dedupe and sid:
                    if sid in seen:
                        duplicates += 1
                        continue
                    seen.add(sid)
                model = _model_label(sub)
                _add_tokens(rows.setdefault((stage, model), _empty_tokens()), sub)
                _add_tokens(by_model.setdefault(model, _empty_tokens()), sub)
                _add_tokens(total, sub)
    return {"rows": rows, "by_model": by_model, "total": total, "duplicates": duplicates,
            "runs": len(runs)}


def _brief_tokens(manifest: dict) -> dict:
    """Tokens by model for one brief: every attempt of every model step in the run
    (Stage 1 and, separately, Stage 2), inherited legs included — this is what the brief used."""
    stage1: dict[str, dict[str, int]] = {}
    stage2: dict[str, dict[str, int]] = {}
    for step in manifest.get("steps") or []:
        if step.get("kind") != "model":
            continue
        for stage, a in _stage_attempts(step):
            sub = a.get("subagent") or {}
            bucket = stage2 if stage.startswith("creative") else stage1
            _add_tokens(bucket.setdefault(_model_label(sub), _empty_tokens()), sub)
    return {"stage1": stage1, "stage2": stage2}


def _run_status(manifest: dict, clean: bool) -> str:
    parts = ["clean" if clean else "repaired"]
    inherited = [s["name"] for s in manifest.get("steps") or []
                 if s.get("from_earlier_run") and s.get("kind") == "model"]
    if inherited:
        parts.append(f"resumed ({len(inherited)} model leg(s) inherited)")
    return ", ".join(parts)


def _fmt(n: int) -> str:
    return f"{n:,}"


def report_ledger(ledger: dict, briefs: list, as_json: bool, path: str = "") -> None:
    """Print the default view: tokens by stage and model, totals, and per-brief means (or JSON)."""
    if as_json:
        print(json.dumps({
            "unit": "tokens",
            "rows": [{"stage": s, "model": mo, **v} for (s, mo), v in sorted(ledger["rows"].items())],
            "by_model": ledger["by_model"], "total": ledger["total"],
            "duplicate_sessions_skipped": ledger["duplicates"], "runs": ledger["runs"],
            "briefs": briefs,
            "brief_means": [{"project": pr, "era": er, **brief_means(g)}
                            for (pr, er), g in sorted(_groups(briefs).items())],
        }, indent=2))
        return

    cols = ("calls", "fresh_input", "output", "cache_read", "cache_write", "total")
    print("\nBrief Builder — usage ruler: TOKENS BY MODEL (demo substrate: multi-turn Claude Code subagents)")
    print(f"Source: {ledger['runs']} run manifest(s){' under ' + path if path else ''}; every attempt "
          f"counted (repairs, failures, verify-extract).")
    if ledger["duplicates"]:
        print(f"{ledger['duplicates']} attempt(s) copied into resumed runs were counted once (same session_id).")
    print(f"\n  {'stage':<16}{'model':<14}" + "".join(f"{c:>13}" for c in cols))
    order = {s: i for i, s in enumerate(STAGE1 + ("creative_shadow",))}
    for (stage, model), row in sorted(ledger["rows"].items(), key=lambda kv: (order.get(kv[0][0], 99), kv[0])):
        print(f"  {stage:<16}{model:<14}" + "".join(f"{_fmt(row[c]):>13}" for c in cols))
    print(f"  {'-' * 16}{'-' * 14}" + "".join(f"{'-' * 12:>13}" for _ in cols))
    for model, row in sorted(ledger["by_model"].items()):
        print(f"  {'ALL STAGES':<16}{model:<14}" + "".join(f"{_fmt(row[c]):>13}" for c in cols))
    print(f"  {'ALL STAGES':<16}{'all models':<14}" + "".join(f"{_fmt(ledger['total'][c]):>13}" for c in cols))

    print("\n  Per brief — complete Stage-1 runs (tokens across every attempt in that run, "
          "inherited legs included):\n")
    if not briefs:
        print("    No complete Stage-1 runs in this path (all five model stages passed).\n")
    for b in briefs:
        models = ", ".join(f"{mo} {_fmt(v['total'])}" for mo, v in sorted(b["tokens"]["stage1"].items()))
        print(f"    {b['run']:<22}{b['project']:<15}{b['era']:<11}{b['status']:<42}"
              f"{_fmt(b['stage1_total']):>12}  ({models})")
    for (project, era), group in sorted(_groups(briefs).items()):
        means = brief_means(group)
        print(f"\n    {project} · {ERA_LABELS.get(era, era)}")
        for key, label in (("all", "all complete runs (clean + repaired + resumed)"),
                           ("clean", "clean runs only (every stage one attempt)")):
            mean = means[key]
            if mean["n"]:
                by = ", ".join(f"{mo} {_fmt(round(v))}" for mo, v in sorted(mean["by_model"].items()))
                print(f"      mean, {label}: n={mean['n']}  {_fmt(round(mean['stage1_total']))} tokens  ({by})")
            else:
                print(f"      mean, {label}: n=0")
    print("\n  Dollars are not the stakeholder unit here; `--usd` prints the CLI-reported cost_usd "
          "as a labelled footnote.\n")


def complete_briefs(runs: list) -> list:
    """Every complete Stage-1 run, with era, clean/repaired/resumed status and tokens by model."""
    out = []
    analysed = {r["run"]: r for r in analyse(runs)["stage1"]}
    for run_id, m in runs:
        if run_id not in analysed:
            continue
        tokens = _brief_tokens(m)
        era, basis = routing_era(m)
        out.append({
            "run": run_id, "project": _project_label(m),
            "era": era, "era_basis": basis,
            "clean": analysed[run_id]["clean"],
            "status": _run_status(m, analysed[run_id]["clean"]),
            "tokens": tokens,
            "stage1_total": sum(v["total"] for v in tokens["stage1"].values()),
        })
    return out


def _project_label(manifest: dict) -> str:
    parts = Path(manifest.get("project_dir") or "?").parts
    return "/".join(parts[-2:]) if len(parts) >= 2 and parts[-2] != "fixtures" else parts[-1]


def _groups(briefs: list) -> dict:
    """Briefs grouped by (project, routing era): a mean across fixtures or eras is not a figure."""
    groups: dict = {}
    for b in briefs:
        groups.setdefault((b.get("project", "?"), b["era"]), []).append(b)
    return groups


def brief_means(briefs: list) -> dict:
    """Mean Stage-1 tokens per brief, over all complete briefs and over clean briefs only."""
    def mean(sel: list) -> dict:
        """Mean Stage-1 total and per-model tokens over the selected briefs."""
        if not sel:
            return {"n": 0, "stage1_total": 0, "by_model": {}}
        by: dict = {}
        for b in sel:
            for mo, v in b["tokens"]["stage1"].items():
                by[mo] = by.get(mo, 0) + v["total"]
        return {"n": len(sel), "stage1_total": sum(b["stage1_total"] for b in sel) / len(sel),
                "by_model": {mo: v / len(sel) for mo, v in by.items()}}
    return {"all": mean(briefs), "clean": mean([b for b in briefs if b["clean"]])}


# --------------------------------------------------------------------------------------
# --tokens view: per-stage categories, turns, $ attribution (cost-audit C0)
# --------------------------------------------------------------------------------------


def token_breakdown(runs: list) -> dict:
    """Aggregate token categories, turns and cost per stage, across every gated attempt.

    Includes failed and repaired attempts on purpose — spend is spend; a telemetry tool that
    only counts the happy path understates exactly the runs worth investigating. The
    verify-extract attempts form their own `verification` row.
    """
    stages: dict = {}
    for _run_id, m in runs:
        for step in m.get("steps") or []:
            if step.get("kind") != "model":
                continue
            for stage, a in _stage_attempts(step):
                sub = a.get("subagent") or {}
                usage = sub.get("usage") or {}
                row = stages.setdefault(stage, {
                    "attempts": 0, "cost": 0.0, "turns": 0, "models": set(),
                    **{k: 0 for k in USAGE_KEYS},
                })
                row["attempts"] += 1
                row["cost"] += sub.get("cost_usd") or 0.0
                row["turns"] += sub.get("num_turns") or 0
                for k in USAGE_KEYS:
                    row[k] += usage.get(k) or 0
                for mid in sub.get("model_ids") or []:
                    row["models"].add(_short_model(mid))
    return stages


def attribute_dollars(row: dict) -> dict:
    """Apportion one stage's tokens to dollars at list rates (see PRICES caveat)."""
    tiers = row["models"] & set(PRICES)
    # A stage normally runs one tier; the creative A/B mixes two — price at the costlier
    # tier so the attribution stays a floor-vs-reported comparison, never an overclaim.
    tier = max(tiers, key=lambda t: PRICES[t][1]) if tiers else "haiku"
    p_in, p_out, p_cr, p_cw = PRICES[tier]
    return {
        "tier": tier,
        "input": row["input_tokens"] * p_in / 1e6,
        "output": row["output_tokens"] * p_out / 1e6,
        "cache_read": row["cache_read_input_tokens"] * p_cr / 1e6,
        "cache_write": row["cache_creation_input_tokens"] * p_cw / 1e6,
    }


def report_tokens(stages: dict, as_json: bool) -> None:
    """Print the --tokens view: per-stage token categories, turns and attributed dollars (or JSON)."""
    ordered = sorted(stages.items(), key=lambda kv: -kv[1]["cost"])
    if as_json:
        payload = {
            name: {**{k: row[k] for k in ("attempts", "cost", "turns", *USAGE_KEYS)},
                   "models": sorted(row["models"]),
                   "attributed_usd": {k: round(v, 4) for k, v in attribute_dollars(row).items()
                                      if k != "tier"}}
            for name, row in ordered
        }
        print(json.dumps(payload, indent=2))
        return

    print("\nBrief Builder — where the tokens go (all gated attempts, demo substrate)\n")
    print(f"  {'stage':<16}{'n':>3}{'turns/n':>8}{'out_tok':>11}{'cache_wr':>11}"
          f"{'cache_rd':>11}{'in_tok':>9}")
    print(f"  {'-'*16}{'-'*3:>3}{'-'*7:>8}{'-'*10:>11}{'-'*10:>11}{'-'*10:>11}{'-'*8:>9}")
    for name, row in ordered:
        print(f"  {name:<16}{row['attempts']:>3}"
              f"{row['turns'] / max(row['attempts'], 1):>8.1f}"
              f"{row['output_tokens']:>11,}{row['cache_creation_input_tokens']:>11,}"
              f"{row['cache_read_input_tokens']:>11,}{row['input_tokens']:>9,}")

    totals = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    print("\n  USD footnote — list-rate attribution vs CLI-reported cost_usd (demo substrate; "
          "not the stakeholder unit):")
    print(f"  {'stage':<16}{'model':<8}{'$out':>8}{'$cache_wr':>10}{'$cache_rd':>10}"
          f"{'$in':>7}{'$computed':>10}{'$reported':>10}")
    for name, row in ordered:
        att = attribute_dollars(row)
        computed = sum(v for k, v in att.items() if k != "tier")
        for k in totals:
            totals[k] += att[k]
        print(f"  {name:<16}{att['tier']:<8}{att['output']:>8.3f}{att['cache_write']:>10.3f}"
              f"{att['cache_read']:>10.3f}{att['input']:>7.3f}{computed:>10.3f}{row['cost']:>10.3f}")

    grand = sum(totals.values())
    if grand:
        print(f"\n  Share of attributed spend: "
              f"output {totals['output'] / grand:.0%} · cache_write {totals['cache_write'] / grand:.0%}"
              f" · cache_read {totals['cache_read'] / grand:.0%} · input {totals['input'] / grand:.0%}")
        print("  (computed = list-rate floor; reported = CLI cost_usd, the authoritative figure)\n")


# --------------------------------------------------------------------------------------
# --usd view: per-brief dollars (a labelled footnote)
# --------------------------------------------------------------------------------------


def analyse(runs: list) -> dict:
    """Per-run CLI-reported dollars by stage for complete Stage-1 runs and creative runs (the --usd view)."""
    stage1_runs, creative_runs = [], []
    for run_id, m in runs:
        by_stage: dict = {}
        for s in m.get("steps") or []:
            if s.get("kind") != "model" or s.get("status") != "pass":
                continue
            for stage, a in _stage_attempts(s):
                sub = a.get("subagent") or {}
                row = by_stage.setdefault(stage, {"cost": 0.0, "attempts": 0, "models": set()})
                row["cost"] += sub.get("cost_usd") or 0.0
                row["attempts"] += 1
                row["models"].update(_short_model(mid) for mid in sub.get("model_ids") or [])
        for row in by_stage.values():
            row["models"] = sorted(row["models"])
        # "Clean" = every stage ran once: one attempt PER SOURCE for extraction and for its
        # verifier — derived from the step itself, never a hardcoded source count.
        per_source_clean = all(
            len(e.get("attempts") or []) == 1
            and len((e.get("verification") or {}).get("attempts") or []) <= 1
            for s in (m.get("steps") or []) if s.get("name") == "extraction"
            for e in s.get("extracts") or []
        )
        if all(k in by_stage for k in REQUIRED_STAGE1):
            clean = per_source_clean and all(
                by_stage[k]["attempts"] == 1
                for k in ("classification", "fidelity_check", "synthesis", "render"))
            stage1_runs.append({"run": run_id, "project": _project_label(m), "era": routing_era(m)[0],
                                "by_stage": by_stage,
                                "total": sum(v["cost"] for k, v in by_stage.items() if k in STAGE1),
                                "clean": clean})
        if "creative_shadow" in by_stage:
            creative_runs.append({"run": run_id, **by_stage["creative_shadow"]})
    return {"stage1": stage1_runs, "creative": creative_runs}


def report(result: dict, labour_eur: float, as_json: bool) -> None:
    """Print the --usd view: dollars per brief next to the assumed account-lead labour cost (or JSON)."""
    all_runs = result["stage1"]
    if as_json:
        print(json.dumps({"unit": "usd_cli_reported", "stage1": all_runs, "creative": result["creative"],
                          "labour_eur": labour_eur}, indent=2))
        return

    print("\nUSD FOOTNOTE — CLI-reported cost_usd at list price (demo substrate: multi-turn Claude Code")
    print("subagents). Not the stakeholder unit: the client runs on a subscription; see the default")
    print("tokens-by-model view.\n")
    if not all_runs:
        print("  No complete Stage-1 runs found.\n")
        return

    for r in all_runs:
        print(f"    {r['run']:<22} {r.get('project', '?'):<15} {r.get('era', '?'):<10} "
              f"{'clean' if r['clean'] else 'repaired':<9} ${r['total']:.4f}")
    stages = ("classification", "fidelity_check", "extraction", VERIFICATION_STAGE, "synthesis", "render")
    groups: dict = {}
    for r in all_runs:
        groups.setdefault((r.get("project", "?"), r.get("era", "?")), []).append(r)
    for (project, era), group in sorted(groups.items()):
        clean_runs = [r for r in group if r["clean"]]
        for label, sel in (("all complete runs (clean + repaired)", group),
                           ("clean runs only (every stage one attempt)", clean_runs)):
            print(f"\n  {project} · {era} · Stage-1 per brief — {label}, n={len(sel)}:")
            if not sel:
                continue
            print(f"    {'stage':<16} {'model':<9} {'mean $':>8}   range")
            for st in stages:
                costs = [r["by_stage"][st]["cost"] for r in sel if st in r["by_stage"]]
                if not costs:
                    continue
                model = next((r["by_stage"][st]["models"] for r in sel if st in r["by_stage"]), [""])
                mean = sum(costs) / len(costs)
                print(f"    {st:<16} {('+'.join(model) if model else ''):<9} {mean:>8.4f}   "
                      f"{min(costs):.4f}–{max(costs):.4f}  (n={len(costs)})")
            totals = [r["total"] for r in sel]
            mean_total = sum(totals) / len(totals)
            print(f"    {'STAGE 1 / brief':<16} {'':<9} {mean_total:>8.4f}   {min(totals):.4f}–{max(totals):.4f}")

    if result["creative"]:
        for c in result["creative"]:
            print(f"\n  Stage-2 creative A/B, {c['run']} ({'+'.join(c['models'])}): ${c['cost']:.4f} "
                  f"for both drafts (~${c['cost']/2:.2f} per creative brief)")

    # The labour ratio uses the largest project/era group (clean mean when it has clean runs).
    (project, era), group = max(groups.items(), key=lambda kv: len(kv[1]))
    sel = [r for r in group if r["clean"]] or group
    which = "clean" if sel is not group else "all"
    mean_total = sum(r["total"] for r in sel) / len(sel)
    ratio = labour_eur / mean_total  # treat $ ≈ € for a floor estimate; understates the ratio slightly
    print(f"\n  Against ~€{labour_eur:.0f} of account-lead labour per brief (PRD A1×A4, an assumption):")
    print(f"    {project} · {era}: ${mean_total:.2f}/brief ({which} mean)  →  ~{ratio:.0f}:1\n")


# --------------------------------------------------------------------------------------
# --risk-replay: how often would the verifier take its base (haiku) branch?
# --------------------------------------------------------------------------------------


def _extract_files(roots: Iterable[Path]) -> list:
    files = []
    for root in roots:
        root = Path(root)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
            if Path(dirpath).name == "extracts":
                files += [Path(dirpath) / f for f in sorted(filenames) if f.endswith(".json")]
    return files


def risk_replay(roots: Iterable[Path]) -> dict:
    """Replay pipeline.extraction.risk_classes over every stored extract (byte-identical copies
    counted once). Measures the routing; changes nothing."""
    sys.path.insert(0, str(REPO_ROOT))
    from pipeline import extraction  # noqa: E402 — deferred: the other views need no pipeline import

    policy = extraction._verify_policy()
    classes_all = list(policy.get("risk_classes") or [])
    seen: dict = {}
    duplicates, unreadable = 0, 0
    rows = []
    for path in _extract_files(roots):
        try:
            data = path.read_bytes()
            extract = json.loads(data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            unreadable += 1
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            duplicates += 1
            continue
        seen[digest] = str(path)
        classes = extraction.risk_classes(extract)
        rows.append({"path": str(path), "source_id": path.stem, "classes": classes})

    n = len(rows)
    per_class = {c: sum(1 for r in rows if c in r["classes"]) for c in classes_all}
    sole = {c: sum(1 for r in rows if r["classes"] == [c]) for c in classes_all}
    base_branch = sum(1 for r in rows if not r["classes"])
    return {
        "policy": {"strong_model": policy.get("strong_model"), "base_model": policy.get("base_model"),
                   "risk_classes": classes_all},
        "unique_extracts": n, "duplicate_copies_skipped": duplicates, "unreadable": unreadable,
        "base_branch": base_branch, "strong_branch": n - base_branch,
        "per_class": per_class, "sole_trigger": sole, "rows": rows,
    }


def report_risk_replay(result: dict, as_json: bool) -> None:
    """Print the verify-extract risk-routing replay: branch shares and per-class triggers (or JSON)."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    n = result["unique_extracts"]
    pol = result["policy"]
    print("\nverify-extract risk routing — replay over stored extracts (measurement only; routing unchanged)")
    print(f"  policy: strong_model={pol['strong_model']}, base_model={pol['base_model']} "
          f"(null = verify-extract frontmatter model), risk_classes={pol['risk_classes']}")
    print(f"  unique extracts: {n} (byte-identical copies skipped: {result['duplicate_copies_skipped']}; "
          f"unreadable: {result['unreadable']})")
    if not n:
        return
    print(f"  base branch ({pol['base_model']}): {result['base_branch']}/{n} = {result['base_branch'] / n:.0%}")
    print(f"  strong branch:       {result['strong_branch']}/{n} = {result['strong_branch'] / n:.0%}\n")
    print(f"  {'risk class':<16}{'present':>9}{'sole trigger':>14}")
    for c in pol["risk_classes"]:
        print(f"  {c:<16}{result['per_class'][c]:>9}{result['sole_trigger'][c]:>14}")
    print()


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry: pick the view from the flags; exit 2 when no run manifest is found."""
    p = argparse.ArgumentParser(description="Usage ruler: tokens by model from run manifests.")
    p.add_argument("path", nargs="?", default=str(REPO_ROOT / "runs"), help="runs/ dir or one run")
    p.add_argument("--tokens", action="store_true", help="per-stage token categories + turns (C0 view)")
    p.add_argument("--usd", action="store_true", help="dollar footnote: CLI-reported cost_usd per brief")
    p.add_argument("--risk-replay", action="store_true",
                   help="replay verify-extract risk routing over every stored extract under path")
    p.add_argument("--verifier", action="store_true",
                   help="verify-extract effectiveness: findings forwarded / dropped / applied / rejected per run")
    p.add_argument("--labour-eur", type=float, default=38.0,
                   help="with --usd: account-lead labour €/brief (PRD A1×A4 ≈ 38–40, an assumption)")
    p.add_argument("--no-dedupe", action="store_true",
                   help="count attempts copied into resumed runs every time they appear")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.risk_replay:
        report_risk_replay(risk_replay([Path(args.path)]), args.json)
        return 0

    runs = load_runs(Path(args.path))
    if not runs:
        print(f"[cost] no run manifests under {args.path}", file=sys.stderr)
        return 2
    if args.verifier:
        report_verifier(verifier_effectiveness(runs), args.json)
    elif args.tokens:
        report_tokens(token_breakdown(runs), args.json)
    elif args.usd:
        report(analyse(runs), args.labour_eur, args.json)
    else:
        report_ledger(token_ledger(runs, dedupe=not args.no_dedupe), complete_briefs(runs),
                      args.json, path=str(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

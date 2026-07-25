"""eval/cost_report.py — re-derive per-brief cost from real run manifests.

    python eval/cost_report.py [runs/] [--labour-eur 38] [--json]
    python eval/cost_report.py [runs/] --tokens          # where the tokens go, per stage

PRD §10 estimated "<€0.50/brief" up front. This reads what the pipeline actually spent —
`total_cost_usd` per subagent call, recorded in every `run_manifest.json` — and reports the
per-stage and per-brief cost, so the deck quotes a measured number, not a guess. It also prints
the number that actually carries the business case: cost against account-lead labour per brief.

`--tokens` is the optimisation ruler (cost-audit C0): per stage, it aggregates the token
categories the CLI reports (input, output, cache read, cache write) plus turns, and attributes
dollars to each category at list rates — so "output tokens are two-thirds of spend" is a
number this tool reproduces, not a one-off analysis.

Not a gate and not frozen; it reads run records only. Costs are the demo substrate (each stage
is a multi-turn Claude Code subagent). Production (PRD DR-1: enterprise API, prompt caching on
the static skeleton) is cheaper — see docs/COST_MODEL.md for the substrate explanation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STAGE1 = ("classification", "fidelity_check", "extraction", "conflict_pass", "synthesis", "render")

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


def _attempts(step: dict) -> list:
    """Every subagent attempt inside a step, across the shapes the runner writes."""
    out = []
    for e in step.get("extracts") or []:
        out += e.get("attempts") or []
    for c in step.get("creative") or []:
        out += c.get("attempts") or []
    for f in step.get("fidelity") or []:
        out += f.get("attempts") or []
    for key in ("classification", "synthesis", "render"):
        if key in step:
            out += step[key].get("attempts") or []
    return out


def _short_model(model_id: str) -> str:
    for alias in ("haiku", "sonnet", "opus", "fable"):
        if alias in model_id:
            return alias
    return model_id


def _step_cost(step: dict) -> tuple:
    attempts = _attempts(step)
    cost = sum(a["subagent"].get("cost_usd") or 0.0 for a in attempts)
    models = sorted({_short_model(m) for a in attempts for m in a["subagent"].get("model_ids") or []})
    return cost, len(attempts), models


def load_runs(path: Path) -> list:
    path = Path(path)
    files = [path / "run_manifest.json"] if (path / "run_manifest.json").is_file() \
        else sorted(path.glob("*/run_manifest.json"))
    runs = []
    for f in files:
        try:
            runs.append((f.parent.name, json.loads(f.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def token_breakdown(runs: list) -> dict:
    """Aggregate token categories, turns and cost per stage, across every gated attempt.

    Includes failed and repaired attempts on purpose — spend is spend; a telemetry tool that
    only counts the happy path understates exactly the runs worth investigating.
    """
    stages: dict = {}
    for _run_id, m in runs:
        for step in m.get("steps") or []:
            if step.get("kind") != "model":
                continue
            for a in _attempts(step):
                sub = a.get("subagent") or {}
                usage = sub.get("usage") or {}
                row = stages.setdefault(step["name"], {
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
    ordered = sorted(stages.items(), key=lambda kv: -kv[1]["cost"])
    if as_json:
        payload = {
            name: {**{k: row[k] for k in ("attempts", "cost", "turns", *USAGE_KEYS)},
                   "models": sorted(row["models"]),
                   "attributed": {k: round(v, 4) for k, v in attribute_dollars(row).items()
                                  if k != "tier"}}
            for name, row in ordered
        }
        print(json.dumps(payload, indent=2))
        return

    print("\nBrief Builder — where the tokens go (all gated attempts, demo substrate)\n")
    print(f"  {'stage':<16}{'n':>3}{'$rep':>8}{'turns/n':>8}{'out_tok':>9}{'cache_wr':>10}"
          f"{'cache_rd':>10}{'in_tok':>8}")
    print(f"  {'-'*16}{'-'*3:>3}{'-'*7:>8}{'-'*7:>8}{'-'*8:>9}{'-'*9:>10}{'-'*9:>10}{'-'*7:>8}")
    for name, row in ordered:
        print(f"  {name:<16}{row['attempts']:>3}{row['cost']:>8.3f}"
              f"{row['turns'] / max(row['attempts'], 1):>8.1f}"
              f"{row['output_tokens']:>9,}{row['cache_creation_input_tokens']:>10,}"
              f"{row['cache_read_input_tokens']:>10,}{row['input_tokens']:>8,}")

    totals = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    print(f"\n  {'stage':<16}{'model':<8}{'$out':>8}{'$cache_wr':>10}{'$cache_rd':>10}"
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


def analyse(runs: list) -> dict:
    stage1_runs, creative_runs = [], []
    for run_id, m in runs:
        by_stage = {}
        for s in m.get("steps") or []:
            if s.get("kind") != "model" or s.get("status") != "pass":
                continue
            cost, n, models = _step_cost(s)
            if n:
                by_stage[s["name"]] = {"cost": cost, "attempts": n, "models": models}
        # A complete Stage-1 brief: all five model stages present and each ran once (no repair).
        # "Clean" for extraction means one attempt PER SOURCE — derived from the step itself,
        # never a hardcoded source count (the runner works on any folder; so does this).
        extraction_clean = all(
            len(e.get("attempts") or []) == 1
            for s in (m.get("steps") or []) if s.get("name") == "extraction"
            for e in s.get("extracts") or []
        )
        if all(k in by_stage for k in ("classification", "fidelity_check", "extraction", "synthesis", "render")):
            clean = extraction_clean and all(
                by_stage[k]["attempts"] == 1
                for k in ("classification", "fidelity_check", "synthesis", "render"))
            stage1_runs.append({"run": run_id, "by_stage": by_stage,
                                "total": sum(v["cost"] for k, v in by_stage.items() if k in STAGE1),
                                "clean": clean})
        if "creative_shadow" in by_stage:
            creative_runs.append({"run": run_id, **by_stage["creative_shadow"]})
    return {"stage1": stage1_runs, "creative": creative_runs}


def report(result: dict, labour_eur: float, as_json: bool) -> None:
    stage1 = [r for r in result["stage1"] if r["clean"]] or result["stage1"]
    if as_json:
        print(json.dumps({"stage1": result["stage1"], "creative": result["creative"],
                          "labour_eur": labour_eur}, indent=2))
        return

    print("\nBrief Builder — measured cost (demo substrate: multi-turn Claude Code subagents)\n")
    if not stage1:
        print("  No complete Stage-1 runs found.\n")
        return

    stages = ("classification", "fidelity_check", "extraction", "synthesis", "render")
    print(f"  Stage-1 per-brief, across {len(stage1)} clean full run(s):\n")
    print(f"    {'stage':<16} {'model':<9} {'mean $':>8}   range")
    print(f"    {'-'*16} {'-'*9} {'-'*8}   {'-'*16}")
    for st in stages:
        costs = [r["by_stage"][st]["cost"] for r in stage1 if st in r["by_stage"]]
        model = next((r["by_stage"][st]["models"] for r in stage1 if st in r["by_stage"]), [""])
        mean = sum(costs) / len(costs)
        print(f"    {st:<16} {(model[0] if model else ''):<9} {mean:>8.4f}   "
              f"{min(costs):.4f}–{max(costs):.4f}")
    totals = [r["total"] for r in stage1]
    mean_total = sum(totals) / len(totals)
    print(f"    {'-'*16} {'-'*9} {'-'*8}")
    print(f"    {'STAGE 1 / brief':<16} {'':<9} {mean_total:>8.4f}   {min(totals):.4f}–{max(totals):.4f}\n")

    if result["creative"]:
        c = result["creative"][0]
        print(f"  Stage-2 creative A/B (sonnet + opus, shadow): ${c['cost']:.4f} for both drafts "
              f"(~${c['cost']/2:.2f} per creative brief)\n")

    # The line that carries the case: model cost vs account-lead labour.
    ratio = labour_eur / mean_total  # treat $ ≈ € for a floor estimate; understates the ratio slightly
    print(f"  Against ~€{labour_eur:.0f} of account-lead labour per brief (PRD A1×A4):")
    print(f"    demo substrate      ${mean_total:.2f}/brief  →  ~{ratio:.0f}:1")
    print(f"    production (PRD §10) <€0.50/brief →  ~{labour_eur/0.5:.0f}:1  (enterprise API + prompt caching)\n")
    print("  The model-call line stays the smallest line either way (PRD §10). The real drivers")
    print("  are review time, adoption, and glossary/template upkeep.\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re-derive per-brief cost from run manifests.")
    p.add_argument("path", nargs="?", default=str(REPO_ROOT / "runs"), help="runs/ dir or one run")
    p.add_argument("--labour-eur", type=float, default=38.0, help="account-lead labour €/brief (PRD A1×A4 ≈ 38–40)")
    p.add_argument("--tokens", action="store_true", help="per-stage token categories + $ attribution")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    runs = load_runs(Path(args.path))
    if not runs:
        print(f"[cost] no run manifests under {args.path}", file=sys.stderr)
        return 2
    if args.tokens:
        report_tokens(token_breakdown(runs), args.json)
    else:
        report(analyse(runs), args.labour_eur, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

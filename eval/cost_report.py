"""eval/cost_report.py — re-derive per-brief cost from real run manifests.

    python eval/cost_report.py [runs/] [--labour-eur 38] [--json]

PRD §10 estimated "<€0.50/brief" up front. This reads what the pipeline actually spent —
`total_cost_usd` per subagent call, recorded in every `run_manifest.json` — and reports the
per-stage and per-brief cost, so the deck quotes a measured number, not a guess. It also prints
the number that actually carries the business case: cost against account-lead labour per brief.

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
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    runs = load_runs(Path(args.path))
    if not runs:
        print(f"[cost] no run manifests under {args.path}", file=sys.stderr)
        return 2
    report(analyse(runs), args.labour_eur, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

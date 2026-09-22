"""eval/pass_rates.py — per-check pass rates across every stored harness report.

    python3 eval/pass_rates.py [runs/ ...]            # table per fixture × routing era
    python3 eval/pass_rates.py [runs/ ...] --json
    python3 eval/pass_rates.py [runs/ ...] --markdown # the table docs/EVAL_RECORD.md quotes

A single 17/17 is one roll. This reads every `harness_report.json` under the given roots
(symlinks are not followed, so `runs/latest` is not counted twice), pairs it with the sibling
`run_manifest.json`, and reports, per fixture and routing era, how often each frozen check
passed — with n.

Independence. Resumed runs reuse earlier legs: several reports can grade the SAME extracts or
the SAME brief. Each check is therefore also counted over distinct legs — the session IDs of
the stage(s) whose artifact the check grades (extraction for T1.x; synthesis for T2.1, T2.2,
T2.6, T3.1, T3.2, T3.4, X1, X2; synthesis + render for T2.3–T2.5, T3.3, X3). A leg graded
twice counts once, and its Wilson 95% interval is computed over distinct legs. A report with
no manifest, or a manifest without session IDs for that stage, counts as its own leg and is
flagged `leg unknown`.

What this cannot see. A re-rolled leg that was graded into the same run directory overwrote
the earlier harness_report.json; those earlier outcomes are gone and are not counted here.

Never reads an answer key: it reads the harness's own verdicts. Not frozen; not a gate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cost_report import ERA_LABELS, _stage_attempts, routing_era  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

SYNTHESIS_CHECKS = {"T2.1", "T2.2", "T2.6", "T3.1", "T3.2", "T3.4", "X1", "X2"}
RENDER_CHECKS = {"T2.3", "T2.4", "T2.5", "T3.3", "X3"}


def graded_stages(check_id: str) -> tuple:
    """The stage(s) whose output a frozen check grades — defines what counts as one leg."""
    if check_id.startswith("T1."):
        return ("extraction",)
    if check_id in RENDER_CHECKS:
        return ("synthesis", "render")
    if check_id in SYNTHESIS_CHECKS:
        return ("synthesis",)
    return ("extraction", "synthesis", "render")


def wilson(passed: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval for a binomial proportion; (0, 0) for n == 0."""
    if n == 0:
        return (0.0, 0.0)
    p = passed / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def find_reports(roots: Iterable[Path]) -> list:
    seen, out = set(), []
    for root in roots:
        root = Path(root)
        if (root / "harness_report.json").is_file():
            candidates = [root / "harness_report.json"]
        else:
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
                if "harness_report.json" in filenames:
                    candidates.append(Path(dirpath) / "harness_report.json")
        for path in candidates:
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                out.append(path)
    return sorted(out)


def _stage_sessions(manifest: dict) -> dict:
    sessions: dict = {}
    for step in manifest.get("steps") or []:
        if step.get("kind") != "model":
            continue
        for stage, attempt in _stage_attempts(step):
            sid = (attempt.get("subagent") or {}).get("session_id")
            if sid:
                sessions.setdefault(stage, set()).add(sid)
    return sessions


def load_record(report_path: Path) -> Optional[dict]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    manifest_path = report_path.parent / "run_manifest.json"
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
    era, basis = routing_era(manifest) if manifest else ("unknown", "no manifest")
    return {
        "run": report_path.parent.name,
        "path": str(report_path),
        "fixture": report.get("fixture") or "?",
        "era": era, "era_basis": basis,
        "summary": report.get("summary") or {},
        "checks": {c["check_id"]: c["status"] for c in report.get("checks") or []},
        "sessions": {k: sorted(v) for k, v in _stage_sessions(manifest or {}).items()},
    }


def _leg_key(record: dict, check_id: str) -> tuple:
    parts = []
    for stage in graded_stages(check_id):
        sids = record["sessions"].get(stage)
        if not sids:
            return ("unknown", record["path"])
        parts.append((stage, tuple(sids)))
    return tuple(parts)


def aggregate(records: list) -> dict:
    """{(fixture, era): {"reports": n, "runs": [...], "checks": {id: stats}}}."""
    groups: dict = {}
    for rec in records:
        g = groups.setdefault((rec["fixture"], rec["era"]), {"reports": 0, "runs": [], "full_passes": 0,
                                                             "checks": {}})
        g["reports"] += 1
        g["runs"].append(rec["run"])
        s = rec["summary"]
        if len(rec["checks"]) >= 17 and not s.get("failed") and not s.get("skipped"):
            g["full_passes"] += 1
        for cid, status in rec["checks"].items():
            c = g["checks"].setdefault(cid, {"pass": 0, "n": 0, "legs": {}, "unknown_legs": 0})
            if status == "skip":
                continue
            c["n"] += 1
            c["pass"] += status == "pass"
            key = _leg_key(rec, cid)
            if key[0] == "unknown":
                c["unknown_legs"] += 1
            # A leg graded more than once keeps its first outcome; the harness is deterministic
            # on identical artifacts, so a disagreement would mean the artifact changed — flag it.
            prior = c["legs"].get(key)
            if prior is None:
                c["legs"][key] = status
            elif prior != status:
                c["legs"][key] = "inconsistent"
    for g in groups.values():
        for c in g["checks"].values():
            legs = list(c["legs"].values())
            c["legs_n"] = len(legs)
            c["legs_pass"] = sum(1 for v in legs if v == "pass")
            c["legs_inconsistent"] = sum(1 for v in legs if v == "inconsistent")
            c["wilson95"] = wilson(c["legs_pass"], c["legs_n"])
            del c["legs"]
    return groups


def _check_order(cid: str) -> tuple:
    head = cid[0]
    num = cid[1:].replace(".", " ").split()
    return (0 if head == "T" else 1, [int(x) for x in num if x.isdigit()])


def render_markdown(groups: dict) -> str:
    lines = []
    for (fixture, era), g in sorted(groups.items()):
        lines.append(f"### {fixture} · {ERA_LABELS.get(era, era)}")
        lines.append("")
        lines.append(f"{g['reports']} harness report(s); {g['full_passes']} full 17/17 pass(es). "
                     f"Runs: {', '.join(sorted(g['runs']))}.")
        lines.append("")
        lines.append("| check | pass / reports | pass / distinct legs | Wilson 95% (legs) | note |")
        lines.append("|---|---|---|---|---|")
        for cid, c in sorted(g["checks"].items(), key=lambda kv: _check_order(kv[0])):
            lo, hi = c["wilson95"]
            notes = []
            if c["unknown_legs"]:
                notes.append(f"{c['unknown_legs']} leg(s) unknown")
            if c["legs_inconsistent"]:
                notes.append(f"{c['legs_inconsistent']} leg(s) graded inconsistently")
            lines.append(f"| {cid} | {c['pass']}/{c['n']} | {c['legs_pass']}/{c['legs_n']} | "
                         f"{lo:.2f}–{hi:.2f} | {'; '.join(notes)} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Per-check pass rates across stored harness reports.")
    p.add_argument("roots", nargs="*", default=[str(REPO_ROOT / "runs")])
    p.add_argument("--json", action="store_true")
    p.add_argument("--markdown", action="store_true")
    args = p.parse_args(argv)

    records = [r for r in (load_record(path) for path in find_reports(Path(x) for x in args.roots)) if r]
    if not records:
        print(f"[pass_rates] no harness_report.json under {args.roots}", file=sys.stderr)
        return 2
    groups = aggregate(records)
    if args.json:
        print(json.dumps({"records": records,
                          "groups": [{"fixture": f, "era": e, **g} for (f, e), g in sorted(groups.items())]},
                         indent=2, ensure_ascii=False))
    elif args.markdown:
        print(render_markdown(groups))
    else:
        print(f"\nPer-check pass rates — {len(records)} harness report(s) under {', '.join(args.roots)}\n")
        print(render_markdown(groups))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

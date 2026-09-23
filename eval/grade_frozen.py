"""Grade committed evidence with the frozen harness — read-only, for CI and humans alike.

`python3 eval/harness.py <run>` grades a run AND writes `harness_report.json` into it, which is
right for a fresh run and wrong for committed evidence: `runs/tier3` must stay byte-identical.
This wrapper calls the same `harness.load_run` + `harness.grade` (the harness stays the only
code that reads an answer key; nothing here re-implements a check) and never writes a file:
bytecode writing is switched off before the harness is imported, and the run directory is
fingerprinted before and after grading, so a write would fail the command instead of passing
unnoticed.

Usage:
    python3 eval/grade_frozen.py                  # runs/tier3, all 17 checks must pass
    python3 eval/grade_frozen.py runs/tier3 --expect 17
    python3 -m eval.grade_frozen

Exit codes: 0 = every check passed; 1 = a check failed or skipped, or the count differs from
--expect; 2 = the run could not be graded or grading modified the evidence.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # before any project import: grading must not write __pycache__

import argparse  # noqa: E402
import hashlib  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Optional  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval import harness  # noqa: E402

DEFAULT_RUN = REPO_ROOT / "runs" / "tier3"
DEFAULT_EXPECTED_CHECKS = 17


def tree_fingerprint(root: Path) -> str:
    """SHA-256 over every file's relative path and bytes under `root` (sorted, stable)."""
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def grade_read_only(run_dir: Path) -> list[harness.CheckResult]:
    """harness.grade on `run_dir`; raises RuntimeError if grading changed any file in it."""
    run_dir = Path(run_dir).resolve()
    before = tree_fingerprint(run_dir)
    results = harness.grade(harness.load_run(run_dir))
    if tree_fingerprint(run_dir) != before:
        raise RuntimeError(f"grading modified {run_dir}; committed evidence must stay byte-identical")
    return results


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry: grade the run read-only; exit 0 all pass, 1 a check failed or count differs, 2 ungradable."""
    parser = argparse.ArgumentParser(description="Read-only grade of committed evidence with the frozen harness.")
    parser.add_argument("run", nargs="?", default=str(DEFAULT_RUN), help="Run directory (default: runs/tier3)")
    parser.add_argument("--expect", type=int, default=DEFAULT_EXPECTED_CHECKS,
                        help="Number of checks that must run and pass (default: 17)")
    args = parser.parse_args(argv)

    try:
        results = grade_read_only(Path(args.run))
    except (harness.HarnessError, RuntimeError) as exc:
        print(f"[grade_frozen] {exc}", file=sys.stderr)
        return 2

    passed = [r for r in results if r.status == "pass"]
    for result in results:
        if result.status != "pass":
            print(f"  {result.status.upper():5} {result.check_id} {result.title}: {result.detail}")
    label = Path(args.run).name
    print(f"Frozen evidence {label}: {len(passed)}/{len(results)} pass (expected {args.expect}/{args.expect})")
    return 0 if len(results) == args.expect and len(passed) == args.expect else 1


if __name__ == "__main__":
    raise SystemExit(main())

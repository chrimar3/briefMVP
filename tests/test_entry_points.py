"""Entry points run the same way whether invoked as a script or with -m, from the repo root.

`python3 eval/rework_report.py --help` used to crash with ModuleNotFoundError while only
`-m eval.rework_report` worked. The read-only grader must also leave evidence byte-identical.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

ENTRY_POINTS = [
    ("eval", "rework_report"),
    ("eval", "grade_frozen"),
    ("eval", "agency_benchmark"),
    ("pipeline", "operations"),
    ("pipeline", "runner"),
    ("pipeline", "replay"),
]


def _run(*args):
    return subprocess.run([sys.executable, *args], cwd=REPO, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("package,module", ENTRY_POINTS)
def test_entry_point_help_works_as_script_and_module(package, module):
    as_script = _run(f"{package}/{module}.py", "--help")
    as_module = _run("-m", f"{package}.{module}", "--help")
    assert as_script.returncode == 0, as_script.stderr
    assert as_module.returncode == 0, as_module.stderr


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_frozen_grade_passes_and_never_writes():
    evidence = REPO / "runs" / "tier3"
    before = _tree(evidence)
    result = _run("eval/grade_frozen.py", "runs/tier3", "--expect", "17")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "17/17 pass" in result.stdout
    assert _tree(evidence) == before


def test_frozen_grade_fails_on_a_check_count_mismatch():
    result = _run("eval/grade_frozen.py", "runs/tier3", "--expect", "18")
    assert result.returncode == 1

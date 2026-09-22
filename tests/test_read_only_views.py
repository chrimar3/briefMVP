"""Read-only views never write into a run directory — not even a lock file.

`python3 -m pipeline.operations runs/tier3` used to open `.run.lock` for append, creating an
untracked file inside the committed evidence pack. Status and portfolio now use
`revisions.read_lock`: a shared lock when the lock file exists, nothing at all when it does not.
"""

import hashlib
import shutil
from pathlib import Path

import pytest

from pipeline import effort, operations, revisions

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "runs" / "tier3"


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_status_and_portfolio_on_committed_evidence_write_nothing():
    before = _tree(EVIDENCE)
    result = operations.status(EVIDENCE)
    operations.portfolio([EVIDENCE, EVIDENCE / "."])
    assert _tree(EVIDENCE) == before
    assert not (EVIDENCE / revisions.RUN_LOCK_FILE).exists()
    assert result["run"] == str(EVIDENCE.resolve())


def test_operations_cli_on_committed_evidence_writes_nothing():
    before = _tree(EVIDENCE)
    operations.main([str(EVIDENCE)])
    assert _tree(EVIDENCE) == before


def test_status_still_excludes_a_concurrent_writer(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(EVIDENCE, run)
    with revisions.run_lock(run):  # a writer holds the run
        result = operations.status(run)
    assert result["stage"] == "error"
    assert any("busy" in b for b in result["blockers"])
    # Once the writer is gone the shared lock is granted and status reads the run normally
    # (the evidence copy has no agency baseline, so it reports its real blockers).
    assert operations.status(run)["stage"] == "blocked"


def test_read_lock_is_shared_between_readers(tmp_path):
    with revisions.run_lock(tmp_path):
        pass  # creates the lock file, as any real write does
    with revisions.read_lock(tmp_path):
        with revisions.read_lock(tmp_path):
            pass
    with revisions.read_lock(tmp_path):
        with pytest.raises(revisions.RunBusyError):
            with revisions.run_lock(tmp_path):
                pass


def test_read_lock_refuses_a_view_if_a_writer_started_during_it(tmp_path):
    with pytest.raises(revisions.RunBusyError, match="changed during a read-only check"):
        with revisions.read_lock(tmp_path):
            with revisions.run_lock(tmp_path):
                pass  # a writer appears mid-read: the lock file did not exist before


def test_read_lock_never_creates_a_missing_directory(tmp_path):
    missing = tmp_path / "missing"
    with revisions.read_lock(missing):
        pass
    assert not missing.exists()


def test_effort_ledger_read_creates_no_lock_file(tmp_path):
    assert effort.read_events(tmp_path) is None
    assert list(tmp_path.iterdir()) == []

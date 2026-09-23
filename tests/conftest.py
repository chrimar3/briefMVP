import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: One definition of "frontmatter is the FIRST `---` block only" (agent bodies legitimately
#: contain `---` lines). The *parse* below stays independent on purpose: yaml.safe_load
#: verifies the frontmatter is real YAML, which the runtime's deliberately naive key:value
#: parser never checks.
from pipeline.agents import _FRONTMATTER_RE  # noqa: E402


@pytest.fixture(autouse=True)
def _never_call_a_real_model(monkeypatch):
    """Hard stop on model calls from the test suite.

    Registering a stage handler made a previously-safe runner test start shelling out to
    `claude -p`, which hung the suite and would have spent real money. Tests exercise the gates
    around the models, never the models — so the binary is pointed at a name that cannot exist
    and any accidental invocation fails instantly and loudly.
    """
    from pipeline import agents

    monkeypatch.setattr(agents, "CLAUDE_BIN", "brief-builder-tests-must-not-call-a-model")
    # The `--version` probe is cached per binary; every test starts without a cached answer,
    # and never inherits the operator's live opt-in.
    monkeypatch.setattr(agents, "_CLI_VERSIONS", {})
    monkeypatch.delenv(agents.LIVE_ENV, raising=False)


#: Committed run evidence the suite reads but must never write into (not even a lock file).
COMMITTED_EVIDENCE = ("runs/tier3", "runs/voreas-prep-02", "runs/voreas-prep-03")
_LOCK_NAMES = (".run.lock", ".effort.lock")


def _evidence_lock_files() -> set:
    return {str(p.relative_to(REPO_ROOT)) for d in COMMITTED_EVIDENCE for name in _LOCK_NAMES
            for p in (REPO_ROOT / d).rglob(name)}


@pytest.fixture(scope="session", autouse=True)
def _committed_evidence_stays_untouched():
    """Fail the session if any test leaves a lock file in committed evidence.

    A read-only status check once created runs/tier3/.run.lock as an untracked file; read-only
    views now use revisions.read_lock, and this guard keeps it that way for every test.
    """
    before = _evidence_lock_files()
    yield
    created = sorted(_evidence_lock_files() - before)
    if created:
        pytest.fail(f"the test session created lock files in committed evidence: {created}")


#: The fake `claude` CLI (offline replay + subprocess-seam fault injection).
FAKE_CLAUDE = REPO_ROOT / "tools" / "replay" / "claude"


@pytest.fixture
def fake_claude(monkeypatch) -> Path:
    """Point the model seam at the fake CLI (absolute path: invoke runs from a neutral cwd).

    Overrides the autouse poison above for this test only; the fake makes no model call.
    """
    from pipeline import agents

    monkeypatch.setattr(agents, "CLAUDE_BIN", str(FAKE_CLAUDE))
    for name in ("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "BRIEF_BUILDER_FAKE_CLAUDE_ARGV", "BRIEF_BUILDER_REPLAY_RUN",
                 "BRIEF_BUILDER_FAKE_CLAUDE_VERSION"):
        monkeypatch.delenv(name, raising=False)
    return FAKE_CLAUDE


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_project(repo_root: Path) -> Path:
    return repo_root / "fixtures" / "northlight_01"


def split_frontmatter(path: Path):
    """Return (frontmatter_dict, body_str) for a Claude Code agent file."""
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.name}: no YAML frontmatter block at the top of the file"
    return yaml.safe_load(match.group(1)), match.group(2)

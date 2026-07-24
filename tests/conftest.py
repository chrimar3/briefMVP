import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: Frontmatter is the FIRST `---` block only. Agent bodies legitimately contain `---`
#: lines (the injected skills use them as rules), so anchor the match at the start.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


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

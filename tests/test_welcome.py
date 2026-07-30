"""START_HERE.html is the operator's front door: a fresh cloner double-clicks it and sees
the product before running anything. Its promises are links into the committed repo — a
rotten link on the front door is a broken first impression, so link integrity is tested.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "START_HERE.html"


def _hrefs() -> list[str]:
    return re.findall(r'href="([^"]+)"', PAGE.read_text(encoding="utf-8"))


def test_front_door_exists_and_links_the_committed_example_pages():
    hrefs = _hrefs()
    assert "runs/tier3/brief_review.html" in hrefs
    assert "runs/tier3/run_review.html" in hrefs


def test_every_front_door_link_resolves_inside_the_repo():
    """The page ships in git and must work offline from a fresh clone — every relative
    link points at a committed file."""
    for href in _hrefs():
        assert not href.startswith(("http:", "https:")), (
            f"front door links out to the network: {href}"
        )
        assert (REPO / href).is_file(), f"START_HERE.html links to missing file: {href}"


def test_front_door_mentions_the_commands_that_matter():
    text = PAGE.read_text(encoding="utf-8")
    for command in ("pytest", "demo.sh", "run_full.sh", "pipeline/runner.py", "eval/harness.py"):
        assert command in text, f"front door lost the {command} pointer"

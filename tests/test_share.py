"""SHARE_ME.html travels alone — one attachment, no repo behind it — so everything it
promises must be inside the file, current, and intact. The committed copy is generated
by pipeline/share.py; these tests fail the suite the moment it drifts from the real
example pages, so a stale front door can never ship silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline import share

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "SHARE_ME.html"


def _embedded(key: str) -> str:
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(
        rf'<script type="application/json" id="doc-{key}">(.*?)</script>', text, re.S
    )
    assert match, f"SHARE_ME.html lost its embedded {key!r} page"
    return json.loads(match.group(1))


def test_committed_share_file_matches_the_real_example_pages():
    """The embedded copies must be byte-identical to the committed tier3 pages —
    regenerate with `python3 pipeline/share.py` after any renderer change."""
    for key, name in (("brief", "brief_review.html"), ("run", "run_review.html")):
        real = (REPO / "runs" / "tier3" / name).read_text(encoding="utf-8")
        assert _embedded(key) == real


def test_share_file_is_self_sufficient():
    """No relative links: the recipient has only this file. The single allowed external
    reference is the repo URL in the footer."""
    text = PAGE.read_text(encoding="utf-8")
    hrefs = re.findall(r'href="([^"]+)"', text)
    assert hrefs == [share.REPO_URL]
    assert 'src="' not in text  # no external scripts, images, or frames


def test_builder_is_deterministic(tmp_path):
    a = share.build_share(out_path=tmp_path / "a.html").read_text(encoding="utf-8")
    b = share.build_share(out_path=tmp_path / "b.html").read_text(encoding="utf-8")
    assert a == b
    assert a == PAGE.read_text(encoding="utf-8")


def test_no_script_close_can_break_the_carrier():
    """The embedded pages contain their own </script>; inside the carrier JSON every
    `</` must be escaped so the payload cannot terminate the carrier element early."""
    text = PAGE.read_text(encoding="utf-8")
    for match in re.finditer(
        r'<script type="application/json" id="doc-[a-z]+">(.*?)</script>', text, re.S
    ):
        assert "</" not in match.group(1)

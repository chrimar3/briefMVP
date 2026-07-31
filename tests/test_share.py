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
    """The embedded copies must track the committed tier3 pages — regenerate with
    `python3 pipeline/share.py` after any renderer change. The brief page rides
    byte-identical; the walkthrough gets exactly one adaptation (see below)."""
    brief = (REPO / "runs" / "tier3" / "brief_review.html").read_text(encoding="utf-8")
    assert _embedded("brief") == brief
    run = (REPO / "runs" / "tier3" / "run_review.html").read_text(encoding="utf-8")
    assert _embedded("run") == share.adapt_run_page(run)


def test_embedded_walkthrough_has_no_dead_relative_buttons():
    """A blob page has no folder around it — relative hrefs to sibling files can never
    resolve, so the bottom button row must be adapted out, not shipped broken."""
    run = _embedded("run")
    assert '<div class="cta-row">' not in run  # the class survives only as a CSS rule
    assert 'href="brief_review.html"' not in run
    assert 'href="brief_el.md"' not in run
    assert "εξώφυλλο" in run  # the replacement note pointing back to the cover


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

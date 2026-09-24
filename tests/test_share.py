"""SHARE_ME.html travels alone — one attachment, no repo behind it — so everything it
promises must be inside the file, current, and intact. The committed copy is generated
by pipeline/share.py; these tests fail the suite the moment it drifts from the real
example pages, so a stale front door can never ship silently.
"""

from __future__ import annotations

import html
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


def _tier3(name: str) -> str:
    return (REPO / "runs" / "tier3" / name).read_text(encoding="utf-8")


def test_committed_share_file_matches_the_real_example_pages():
    """The embedded copies must track the committed tier3 pages — regenerate with
    `python3 pipeline/share.py` after any renderer change. The brief page rides
    byte-identical; the walkthrough gets exactly one adaptation (see below)."""
    assert _embedded("brief") == _tier3("brief_review.html")
    assert _embedded("run") == share.adapt_run_page(
        _tier3("run_review.html"),
        _tier3("brief_review.html"),
        _tier3("brief_el.html"),
        _tier3("brief_en.html"),
    )


def test_embedded_walkthrough_buttons_carry_their_own_targets():
    """A blob page has no folder around it — relative hrefs can never resolve. The
    bottom buttons must therefore carry their targets: the brief page and both
    rendered documents ride inside the walkthrough as payloads, and every button is
    a blob-opener. No dead relative href may survive."""
    run = _embedded("run")
    assert 'href="brief_review.html"' not in run
    assert 'href="brief_el.md"' not in run
    assert 'href="brief_en.md"' not in run
    for key in ("brief", "el", "en"):
        assert f'data-open="{key}"' in run
        payload = re.search(
            rf'<script type="application/json" id="doc-{key}">(.*?)</script>', run, re.S
        )
        assert payload, f"walkthrough lost its embedded {key!r} payload"
        assert "</" not in payload.group(1)  # inner carrier escaped like the outer ones
    assert json.loads(
        re.search(
            r'<script type="application/json" id="doc-brief">(.*?)</script>', run, re.S
        ).group(1)
    ) == _tier3("brief_review.html")
    assert json.loads(
        re.search(
            r'<script type="application/json" id="doc-el">(.*?)</script>', run, re.S
        ).group(1)
    ) == _tier3("brief_el.html")


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


def _pitch_text() -> str:
    """SHARE_ME's own visible text (the pitch before the embedded carriers), entities decoded."""
    text = PAGE.read_text(encoding="utf-8")
    body = text.split('<script type="application/json"', 1)[0]
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


def _plain(path: Path) -> str:
    """A repo page's text with tags removed and entities decoded, whitespace collapsed."""
    raw = html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8")))
    return " ".join(raw.split())


def test_share_file_carries_the_three_decisions_with_owners_and_deadlines():
    """A forwarded sponsor must see the decision itself, not a pointer to it: the answer
    first, the three decisions, each owner and needed-by date, and the go-live mapping."""
    pitch = " ".join(_pitch_text().split())
    assert share.ANSWER in pitch
    assert len(share.DECISIONS) == 3
    for decision in share.DECISIONS:
        assert decision["ask"].rstrip(".") in pitch
        assert f"Owner: {decision['owner']} · needed {decision['needed_by']}" in pitch
        assert decision["items"] in pitch
    assert "What you are signing" in pitch
    assert share.SIGNING_RULE in pitch
    for gid in ("D-01", "D-16", "D-13", "D-14", "D-17", "T-02", "T-03", "D-27"):
        assert gid in pitch, gid


def test_share_file_carries_the_proven_and_not_proven_lists_and_the_risks():
    pitch = " ".join(_pitch_text().split())
    assert "Not proven" in pitch and "Proven" in pitch and "Risks" in pitch
    for item in (*share.PROVEN, *share.NOT_PROVEN, *share.RISKS):
        assert " ".join(item.split()) in pitch, item[:60]
    assert "0.44–1.00" in pitch  # the small-n caveat travels with the numbers
    assert "Synthetic fixtures only" in pitch


def test_share_headline_tiles_are_era_labelled():
    """Every headline tile says which routing era its number belongs to."""
    pitch = " ".join(_pitch_text().split())
    for big, _unit, text in share.TILES:
        assert big in pitch
        assert "September" in text or "July" in text, big
    usage = next(text for big, _unit, text in share.TILES if big == "926,524")
    assert "estimate" in usage and "Haiku-era (July, historical)" in usage
    assert "client-ready" not in pitch and "review-ready draft" in pitch


def test_step_count_sentence_is_the_same_on_all_three_front_doors():
    """WALKTHROUGH sheet 02, START_HERE and SHARE_ME describe the flow in one sentence."""
    assert share.STEP_SENTENCE in " ".join(_pitch_text().split())
    for name in ("START_HERE.html", "WALKTHROUGH.html"):
        assert share.STEP_SENTENCE in _plain(REPO / name), name
    assert "Nine steps" not in _plain(REPO / "WALKTHROUGH.html")


def test_decision_texts_and_owners_match_the_decision_paper():
    """SHARE_ME's decisions are the decision paper's, word for word, with the same owners."""
    paper = _plain(REPO / "WALKTHROUGH.html")
    for decision in share.DECISIONS:
        assert decision["ask"].rstrip(".") in paper, decision["ask"][:60]
        assert f"owner: {decision['owner']}" in paper, decision["owner"]
    assert "What you are signing" in paper


def test_no_script_close_can_break_the_carrier():
    """The embedded pages contain their own </script>; inside the carrier JSON every
    `</` must be escaped so the payload cannot terminate the carrier element early."""
    text = PAGE.read_text(encoding="utf-8")
    for match in re.finditer(
        r'<script type="application/json" id="doc-[a-z]+">(.*?)</script>', text, re.S
    ):
        assert "</" not in match.group(1)

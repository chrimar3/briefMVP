"""The Brief Review Page is a VIEW: it must show everything brief.json says and be
unable to say anything brief.json does not say. These tests keep both directions of
that property machine-checked — completeness (every entry/conflict/question/evidence
ref reaches the page) and containment (no cost/model/run information, ever; owner
decision §6.1 in docs/FABLE_MISSION_visualisation.md). Deterministic, zero model calls.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from pipeline import review

REPO = Path(__file__).resolve().parents[1]
STORED_RUNS = ("runs/tier3", "runs/live", "runs/evidence-20260729")

FORBIDDEN = re.compile(r"cost|model|claude|sonnet|haiku|opus", re.IGNORECASE)


def _brief(run: str) -> dict:
    return json.loads((REPO / run / "brief.json").read_text(encoding="utf-8"))


def _mini_brief(**overrides) -> dict:
    """Smallest schema-shaped brief; overrides let a test poison one corner of it."""
    base = {
        "meta": {
            "project_id": "p_01",
            "client_id": "acme_soda",
            "project_type": "advertising_creative",
            "classification_confidence": "high",
            "sensitivity_tier": "S0",
            "sources": [
                {"source_id": "src_a", "source_type": "rfp", "source_date": "2026-07-01"}
            ],
            "created_ts": "2026-07-30T10:00:00",
            "pipeline_version": "1.0.0",
        },
        "objectives": [
            {
                "content": "Grow awareness in the launch window.",
                "evidence": [
                    {
                        "source_id": "src_a",
                        "location": "§2",
                        "anchor": "grow awareness fast",
                        "speaker_or_author": "Acme CMO",
                    }
                ],
                "confidence": "high",
                "qualifier": "stated",
            }
        ],
        "audiences": [],
        "key_messages": [],
        "deliverables": [],
        "timeline": [],
        "budget": [],
        "mandatories": [],
        "open_questions": [
            {
                "field": "budget",
                "gap": "No figure was given.",
                "why_it_matters": "Scopes every deliverable.",
                "suggested_question_for_client": "Ποιο είναι το τελικό ποσό;",
            }
        ],
        "conflicts": [],
        "readiness": {
            "fields_with_evidence": 1,
            "low_confidence_share": 0.0,
            "open_question_count": 1,
            "verdict": "thin_input_return_to_client",
        },
        "signoff": {"status": "draft"},
    }
    base.update(overrides)
    return base


def _entries(brief: dict):
    for field in review.BRIEF_FIELDS:
        for entry in brief.get(field) or []:
            yield field, entry


# ---------------------------------------------------------------- completeness


@pytest.mark.parametrize("run", STORED_RUNS)
def test_every_entry_conflict_and_question_appears_on_the_page(run):
    """An account lead reviewing the page must be reviewing the whole brief — a
    dropped entry would be an invisible editorial decision by the view."""
    brief = _brief(run)
    page = review.render_review(brief)
    for _field, entry in _entries(brief):
        assert html.escape(entry["content"]) in page
    for conflict in brief.get("conflicts") or []:
        for position in conflict["positions"]:
            assert html.escape(position["statement"]) in page
    for question in brief.get("open_questions") or []:
        assert html.escape(question["suggested_question_for_client"]) in page


@pytest.mark.parametrize("run", STORED_RUNS)
def test_evidence_quotes_ride_with_their_entries(run):
    """The trust story is 'every value carries its evidence' — anchor, source,
    location and speaker must all survive into the page for every reference."""
    brief = _brief(run)
    page = review.render_review(brief)
    refs = []
    for _field, entry in _entries(brief):
        refs.extend(entry.get("evidence") or [])
    for conflict in brief.get("conflicts") or []:
        refs.extend(p["evidence"] for p in conflict["positions"])
    for question in brief.get("open_questions") or []:
        refs.extend(question.get("linked_evidence") or [])
    assert refs, f"{run} has no evidence refs — fixture no longer exercises the test"
    for ref in refs:
        assert html.escape(ref["anchor"]) in page
        assert html.escape(ref["source_id"]) in page
        assert html.escape(ref["location"]) in page
        assert html.escape(ref["speaker_or_author"]) in page


def test_conditional_and_low_are_always_badged():
    """Shaky things must LOOK shaky: `conditional` and `low` get attention styling
    unconditionally — there is no page state that hides them."""
    brief = _mini_brief(
        objectives=[
            {
                "content": "A conditional idea.",
                "evidence": [
                    {
                        "source_id": "src_a",
                        "location": "§9",
                        "anchor": "if budget allows",
                        "speaker_or_author": "Acme CMO",
                    }
                ],
                "confidence": "low",
                "qualifier": "conditional",
            }
        ]
    )
    page = review.render_review(brief)
    assert 'pill conf-low' in page
    assert 'badge qual-conditional' in page
    assert 'entry attention' in page


@pytest.mark.parametrize("run", STORED_RUNS)
def test_stored_briefs_badge_every_conditional_and_low_entry(run):
    """One badge per shaky entry — the class token count must match the object."""
    brief = _brief(run)
    page = review.render_review(brief)
    lows = sum(1 for _f, e in _entries(brief) if e["confidence"] == "low")
    conditionals = sum(1 for _f, e in _entries(brief) if e["qualifier"] == "conditional")
    assert page.count("pill conf-low") == lows
    assert page.count("badge qual-conditional") == conditionals


# ----------------------------------------------------------------- containment


def test_page_chrome_never_adds_cost_or_model_strings():
    """Owner decision §6.1: no cost or model information on the page. A brief that
    contains none of those strings must produce a page that contains none — proving
    the chrome contributes zero on its own."""
    page = review.render_review(_mini_brief())
    assert "$" not in page
    assert not FORBIDDEN.search(page), FORBIDDEN.search(page).group(0)


@pytest.mark.parametrize("run", STORED_RUNS)
def test_stored_pages_add_nothing_the_brief_does_not_say(run):
    """The view property, directly: any forbidden-family string on the page must
    already exist verbatim-insensitive in brief.json (client budget language like
    'costs' is brief content; run cost/model info lives only in the manifest and
    must never appear)."""
    raw = (REPO / run / "brief.json").read_text(encoding="utf-8")
    page = review.render_review(json.loads(raw))
    assert "$" not in page
    for match in {m.group(0).lower() for m in FORBIDDEN.finditer(page)}:
        assert re.search(match, raw, re.IGNORECASE), (
            f"page says {match!r} but brief.json never does"
        )
    assert not re.search(r"claude|sonnet|haiku|opus", page, re.IGNORECASE)


def test_content_script_tags_arrive_escaped():
    """Brief content is model-authored and untrusted — a script tag in any content
    position must render inert. The page's only live script is its own."""
    payload = '<script>alert(1)</script>'
    brief = _mini_brief(
        objectives=[
            {
                "content": payload,
                "evidence": [
                    {
                        "source_id": payload,
                        "location": payload,
                        "anchor": payload,
                        "speaker_or_author": payload,
                    }
                ],
                "confidence": "high",
                "qualifier": "stated",
            }
        ],
        open_questions=[
            {
                "field": "budget",
                "gap": payload,
                "why_it_matters": payload,
                "suggested_question_for_client": payload,
            }
        ],
    )
    page = review.render_review(brief)
    assert payload not in page
    assert page.count("<script>") == 1  # the page's own inline script, nothing else
    assert html.escape(payload) in page


# ----------------------------------------------------------- chrome & behavior


def test_greek_first_chrome_with_a_data_lang_toggle():
    """Owner decision §6.4: Greek-first chrome, EN one toggle away — the default is
    set at parse time on the root element, not by script."""
    page = review.render_review(_mini_brief())
    assert '<html lang="el" data-lang="el">' in page
    assert 'data-set-lang="en"' in page
    assert 'data-set-lang="el"' in page
    assert "data-lang" in page.split("<script>")[1]  # the toggle drives the attribute
    # Greek labels are the visible default; EN labels exist for the toggle.
    assert '[data-lang="el"] .i-en { display: none; }' in page
    assert "Ανοιχτές ερωτήσεις" in page


def test_health_strip_shows_the_readiness_block_verbatim():
    """The strip mirrors brief['readiness'] — no recomputation, so the page can
    never disagree with the gates."""
    brief = _brief("runs/evidence-20260729")
    page = review.render_review(brief)
    readiness = brief["readiness"]
    assert f"{readiness['fields_with_evidence']}/7" in page
    assert "ΕΤΟΙΜΟ ΓΙΑ ΕΛΕΓΧΟ" in page  # verdict == ready_for_review
    open_conflicts = sum(
        1 for c in brief["conflicts"] if c["status"] != "resolved_by_human"
    )
    assert f"<strong>{open_conflicts}</strong>" in page
    assert f"<strong>{len(brief['open_questions'])}</strong>" in page


def test_empty_field_arrays_and_zero_conflicts_render_quiet_placeholders():
    """tier3 ships empty audiences/budget and runs/live ships zero conflicts — the
    page must show an explicit absence, never a broken or missing section."""
    tier3_page = review.render_review(_brief("runs/tier3"))
    assert 'id="field-audiences"' in tier3_page
    assert 'id="field-budget"' in tier3_page
    assert "Καμία τεκμηριωμένη εγγραφή" in tier3_page
    live_page = review.render_review(_brief("runs/live"))
    assert "Καμία σύγκρουση μεταξύ των πηγών" in live_page


def test_render_review_is_deterministic():
    """Same object, same bytes — the page carries no timestamps or randomness of
    its own, so reruns and git diffs stay honest."""
    brief = _brief("runs/tier3")
    assert review.render_review(brief) == review.render_review(brief)


# ------------------------------------------------------------------ write/CLI


def test_write_review_emits_the_page_beside_the_brief(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief.json").write_text(
        json.dumps(_mini_brief(), ensure_ascii=False), encoding="utf-8"
    )
    out = review.write_review(run_dir)
    assert out == run_dir / "brief_review.html"
    assert out.read_text(encoding="utf-8") == review.render_review(_mini_brief())


def test_write_review_raises_a_legible_error_without_a_brief(tmp_path):
    """A run that never reached synthesis has no brief.json — the failure must name
    the directory and the missing file, not stack-trace into pathlib."""
    empty = tmp_path / "no-brief-here"
    empty.mkdir()
    with pytest.raises(review.ReviewInputError) as excinfo:
        review.write_review(empty)
    message = str(excinfo.value)
    assert "brief.json" in message
    assert str(empty) in message


def test_write_review_raises_on_unparseable_brief(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(review.ReviewInputError, match="not valid JSON"):
        review.write_review(run_dir)


def test_cli_prints_the_emitted_path_and_fails_legibly(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief.json").write_text(
        json.dumps(_mini_brief(), ensure_ascii=False), encoding="utf-8"
    )
    assert review.main([str(run_dir)]) == 0
    assert str(run_dir / "brief_review.html") in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert review.main([str(empty)]) == 1
    assert "brief.json" in capsys.readouterr().err

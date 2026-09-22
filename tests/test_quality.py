"""pipeline/quality.py render_coverage: question blocks must carry their own linked evidence.

Go-live precondition T-01 (docs/pilot/GO_LIVE_DECISIONS.md): a question whose evidence location is
a bracketed transcript timestamp (`[00:03:41]`) could never pass, because a location containing
`]` cannot sit inside one `[...]` tag. These tests pin the correction in both directions: the
correctly evidenced question passes, a genuinely uncovered one still fails.
"""

from pipeline import quality


def _brief(location, source_id="transcript_kickoff"):
    return {"open_questions": [{"field": "audiences", "linked_evidence": [
        {"source_id": source_id, "location": location, "anchor": "a"}]}]}


def _render(block):
    return f"## 1. Objectives\n- Something [other_source L1]\n\n## ⚠ Open questions\n\n1. **audiences**\n   {block}\n"


def test_a_timestamp_located_question_cited_with_its_timestamp_passes():
    """The render order's own tag form is `[<source_id> <location>]`, e.g. `[kickoff_call 00:12:05]`:
    the transcript's bracketed timestamp is written without its own brackets inside the tag."""
    text = _render("Gap: who buys it? [transcript_kickoff 00:03:41]")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en") == []


def test_a_timestamp_written_with_its_brackets_inside_the_tag_passes():
    text = _render("Gap: who buys it? [transcript_kickoff [00:03:41]]")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en") == []


def test_a_timestamp_question_without_its_citation_still_fails():
    text = _render("Gap: who buys it? (no citation)")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en") == [
        "en: question 0 lacks its linked evidence citation"]


def test_a_timestamp_question_citing_another_moment_still_fails():
    text = _render("Gap: who buys it? [transcript_kickoff 00:14:32]")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en")


def test_a_timestamp_question_citing_the_moment_under_another_source_still_fails():
    text = _render("Gap: who buys it? [emails_thread 00:03:41]")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en")


def test_the_bare_timestamp_outside_any_tag_does_not_count():
    text = _render("Gap: said at 00:03:41 by transcript_kickoff, see [other_source L1]")
    assert quality.render_coverage(_brief("[00:03:41]"), text, "en")


def test_unbracketed_locations_are_matched_exactly_as_before():
    assert quality.render_coverage(_brief("§3", "client_rfp"), _render("Gap [client_rfp §3]"), "en") == []
    assert quality.render_coverage(_brief("§3", "client_rfp"), _render("Gap [client_rfp §4]"), "en")

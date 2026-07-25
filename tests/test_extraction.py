"""Step 4 — the deterministic half of extraction.

No model runs in these tests. What is under test is the gate the model's output has to pass,
because that gate is the reason a bad extract cannot reach a brief.
"""

import json

import pytest

from pipeline import extraction, gates

SOURCE_TEXT = """# Kickoff
source_id: t · source_type: transcript · source_date: 2026-01-01

[00:02:05] SPEAKER: Το βασικό για μας είναι το μπραντ αγουέρνες — νέα κατηγορία.
[00:14:32] CFO: είμαστε κάπου στα ογδόντα, χωρίς το media spend.
"""

GLOSSARY = {
    "client_id": "test_client",
    "sensitivity_tier": "S1",
    "terms": [
        {"term": "brand awareness", "rule": "keep_latin"},
        {"term": "media spend", "rule": "keep_latin"},
        {"term": "Fizz Product", "rule": "keep_latin"},
    ],
}


def _item(**overrides):
    item = {
        "value": "κάπου στα ογδόντα, χωρίς το media spend",
        "lang": "el",
        "location": "[00:14:32]",
        "anchor": "είμαστε κάπου στα ογδόντα",
        "speaker_or_author": "CFO",
        "qualifier": "stated",
        "confidence": "medium",
    }
    item.update(overrides)
    return item


def _extract(**overrides):
    base = {
        "meta": {
            "project_id": "p", "source_id": "t", "source_type": "transcript",
            "source_date": "2026-01-01", "extraction_ts": "2026-01-02T00:00:00", "agent_version": "1.0",
        },
        "objectives": [], "audiences": [], "key_messages": [], "deliverables": [],
        "timeline": [], "budget": [_item()], "mandatories": [],
        "open_questions": [], "internal_conflicts": [], "extraction_notes": [],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------------------
# Citations must resolve against the source
# --------------------------------------------------------------------------------------


def test_real_citations_pass():
    assert gates.verify_citations(_extract(), SOURCE_TEXT) == []


def test_invented_location_is_caught():
    """The exact failure observed on the first Tier-1 run: a timestamp that does not exist."""
    violations = gates.verify_citations(_extract(budget=[_item(location="[00:07]")]), SOURCE_TEXT)
    assert len(violations) == 1
    assert "does not occur in the source" in violations[0]


def test_invented_anchor_is_caught():
    bad = _item(anchor="we are around ninety thousand euros")
    violations = gates.verify_citations(_extract(budget=[bad]), SOURCE_TEXT)
    assert len(violations) == 1 and "anchor" in violations[0]


def test_citation_survives_a_line_wrap():
    """Whitespace differences are formatting, not fabrication."""
    wrapped = _item(anchor="είμαστε   κάπου\n  στα ογδόντα")
    assert gates.verify_citations(_extract(budget=[wrapped]), SOURCE_TEXT) == []


def test_anchor_crossing_a_markdown_boundary_resolves():
    """The Tier-3 re-run failure: the model anchors on text spanning a ** boundary and drops
    the markers. That is a valid citation to the bolded content, matched on content not markup."""
    md_source = "# RFP\nsource_id: t · source_type: rfp · source_date: 2026-01-01\n\nLaunch την **πρώτη εβδομάδα του Οκτωβρίου 2026**, ώστε...\n"
    item = _item(value="launch first week October", location="Launch",
                 anchor="Launch την πρώτη εβδομάδα του Οκτωβρίου 2026")
    assert gates.verify_citations(_extract(timeline=[item], budget=[]), md_source) == []


def test_markdown_normalisation_still_rejects_fabrication():
    """Stripping markers must not open a hole: an invented anchor still fails to resolve."""
    md_source = "Launch την **πρώτη εβδομάδα**, ...\n"
    fake = _item(location="Launch", anchor="delivery guaranteed by September")
    violations = gates.verify_citations(_extract(timeline=[fake], budget=[]), md_source)
    assert len(violations) == 1 and "does not occur" in violations[0]


# --------------------------------------------------------------------------------------
# Citations inside internal_conflicts must resolve too (design audit F2)
# --------------------------------------------------------------------------------------


def test_fabricated_internal_conflict_citation_is_caught():
    """internal_conflicts anchors are admitted into synthesis's known-anchor set (the Tier-3
    §7 fix), so an unverified one is a fabricated-citation path straight into the brief."""
    conflict = {"field": "budget", "value_a": _item(),
                "value_b": _item(location="[00:99:99]", anchor="ένα ποσό που δεν ειπώθηκε ποτέ")}
    violations = gates.verify_internal_conflict_citations(
        _extract(internal_conflicts=[conflict]), SOURCE_TEXT)
    assert len(violations) == 2  # both the location and the anchor are invented
    assert all("does not occur in the source" in v for v in violations)
    assert all("internal_conflicts[0].value_b" in v for v in violations)


def test_genuine_internal_conflict_citation_passes():
    conflict = {"field": "budget", "value_a": _item(),
                "value_b": _item(location="[00:02:05]", anchor="νέα κατηγορία")}
    assert gates.verify_internal_conflict_citations(
        _extract(internal_conflicts=[conflict]), SOURCE_TEXT) == []


def test_check_extract_gates_internal_conflict_citations(tmp_path):
    path = tmp_path / "e.json"
    conflict = {"field": "budget", "value_a": _item(),
                "value_b": _item(anchor="never said this either")}
    path.write_text(json.dumps(_extract(internal_conflicts=[conflict])), encoding="utf-8")
    violations = extraction.check_extract(path, SOURCE_TEXT, GLOSSARY)
    assert any("internal_conflicts" in v for v in violations)


# --------------------------------------------------------------------------------------
# Silent repair / silent translation of protected terms
# --------------------------------------------------------------------------------------


def test_repaired_glossary_term_inside_an_internal_conflict_is_caught():
    """A silent repair is no more acceptable for hiding inside a conflict record."""
    conflict = {"field": "objectives",
                "value_a": _item(value="brand awareness — new category",
                                 location="[00:02:05]", anchor="νέα κατηγορία"),
                "value_b": _item()}
    violations = gates.find_unsourced_glossary_terms(
        _extract(internal_conflicts=[conflict]), SOURCE_TEXT, GLOSSARY)
    assert len(violations) == 1 and "brand awareness" in violations[0]


def test_glossary_term_inside_another_word_is_not_flagged():
    """'ooh' inside 'boohoo' is not a use of the term OOH — matching is word-bounded on the
    value side, so short acronyms cannot false-positive inside unrelated words."""
    glossary = {"terms": [{"term": "OOH", "rule": "keep_latin"}]}
    item = _item(value="η καμπάνια boohoo δεν είναι δική μας")
    assert gates.find_unsourced_glossary_terms(_extract(budget=[item]), SOURCE_TEXT, glossary) == []


def test_silently_repaired_glossary_term_is_caught():
    """SOURCES.md rule G: the source says «μπραντ αγουέρνες»; writing "brand awareness"
    into the value is a repair the pipeline is not allowed to make."""
    repaired = _item(value="brand awareness — new category", location="[00:02:05]", anchor="νέα κατηγορία")
    violations = gates.find_unsourced_glossary_terms(_extract(objectives=[repaired]), SOURCE_TEXT, GLOSSARY)
    assert len(violations) == 1
    assert "brand awareness" in violations[0] and "rule G" in violations[0]


def test_term_genuinely_present_in_the_source_is_not_flagged():
    """`media spend` is written in Latin in the source, so carrying it through is correct."""
    assert gates.find_unsourced_glossary_terms(_extract(), SOURCE_TEXT, GLOSSARY) == []


def test_unused_glossary_terms_are_not_flagged():
    assert "Fizz Product" not in json.dumps(gates.find_unsourced_glossary_terms(_extract(), SOURCE_TEXT, GLOSSARY))


def test_detector_is_driven_by_the_client_glossary_only():
    """Nothing about a particular document is baked in — an empty glossary flags nothing."""
    repaired = _item(value="brand awareness", location="[00:02:05]", anchor="νέα κατηγορία")
    assert gates.find_unsourced_glossary_terms(_extract(objectives=[repaired]), SOURCE_TEXT, {"terms": []}) == []


# --------------------------------------------------------------------------------------
# The composite gate
# --------------------------------------------------------------------------------------


def test_check_extract_reports_every_layer_at_once(tmp_path):
    """One repair round should see the whole picture, not one violation at a time."""
    path = tmp_path / "e.json"
    broken = _extract(budget=[_item(location="[99:99]", anchor="never said this")])
    path.write_text(json.dumps(broken), encoding="utf-8")
    violations = extraction.check_extract(path, SOURCE_TEXT, GLOSSARY)
    assert len(violations) == 2


def test_check_extract_accepts_a_clean_artifact(tmp_path):
    path = tmp_path / "e.json"
    path.write_text(json.dumps(_extract()), encoding="utf-8")
    assert extraction.check_extract(path, SOURCE_TEXT, GLOSSARY) == []


def test_check_extract_reports_a_missing_file(tmp_path):
    assert "no file written" in extraction.check_extract(tmp_path / "nope.json")[0]


def test_check_extract_reports_malformed_json(tmp_path):
    path = tmp_path / "e.json"
    path.write_text("{not json", encoding="utf-8")
    assert "not valid JSON" in extraction.check_extract(path)[0]


# --------------------------------------------------------------------------------------
# Client config + work order
# --------------------------------------------------------------------------------------


def test_client_tier_is_read_from_config_not_inferred(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps(GLOSSARY), encoding="utf-8")
    assert extraction.load_client_config(path)["sensitivity_tier"] == "S1"


def test_regulated_client_config_is_refused(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps({**GLOSSARY, "sensitivity_tier": "S3"}), encoding="utf-8")
    with pytest.raises(gates.ScopeError):
        extraction.load_client_config(path)


def test_ambiguous_glossary_is_refused_not_guessed(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    with pytest.raises(extraction.ExtractionError, match="pass --glossary"):
        extraction.resolve_glossary(glossary_dir=tmp_path)


def _work_order(source_type="transcript", **kwargs):
    source = gates.SourceDoc(
        source_id="t", source_type=source_type, source_date="2026-01-01",
        path=__import__("pathlib").Path("/tmp/t.md"), text=SOURCE_TEXT,
    )
    return extraction.build_work_order(
        source, __import__("pathlib").Path("/tmp/out.json"), "proj", GLOSSARY,
        __import__("pathlib").Path("/tmp/g.json"), **kwargs
    )


def test_work_order_carries_no_source_content():
    """Paths and identifiers only — the same code must run on any Input folder."""
    order = _work_order()
    assert "μπραντ αγουέρνες" not in order
    assert "ογδόντα" not in order


def test_work_order_forbids_reading_the_answer_key():
    assert "answer_key.json" in _work_order()


def test_unannotated_transcript_gets_the_rule_g_precondition():
    """If the fidelity gate did not run, the agent is entitled to know it is the only defence."""
    assert "has NOT passed the fidelity gate" in _work_order()


def test_annotated_transcript_drops_the_precondition():
    assert "has NOT passed the fidelity gate" not in _work_order(fidelity_annotated=True)


def test_non_transcript_sources_get_no_fidelity_precondition():
    assert "fidelity gate" not in _work_order(source_type="rfp")

"""Gates for steps 2, 3, 5, 6 and 7. No model runs in any of these tests."""

import json

import pytest

from pipeline import conflicts, gates, stages

CLIENT_CONFIG = {
    "client_id": "meltemi_beverages",
    "sensitivity_tier": "S1",
    "terms": [{"term": "Meltemi Fizz", "rule": "keep_latin"}, {"term": "media spend", "rule": "keep_latin"}],
}

TRANSCRIPT = "[00:01:00] CMO: Θέλουμε μπραντ αγουέρνες.\n[00:02:00] CFO: κάπου στα ογδόντα πέντε, χωρίς media spend.\n"


# ======================================================================================
# Step 2 — classification
# ======================================================================================


def _classification(**over):
    payload = {
        "project_id": "p", "client_id": "meltemi_beverages",
        "project_type": "advertising_creative", "classification_confidence": "high",
        "sensitivity_tier": "S1", "tier_source": "client_config", "rationale": "launch campaign",
        "evidence": [{"source_id": "rfp", "location": "§4", "anchor": "Δημιουργικό υλικό"}],
        "question_for_human": "", "halt_reason": "",
    }
    payload.update(over)
    return payload


def _write(tmp_path, payload, name="classification.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_classification_passes(tmp_path):
    assert stages.check_classification(_write(tmp_path, _classification()), CLIENT_CONFIG) == []


def test_classifier_that_judges_the_tier_is_caught(tmp_path):
    """The tier is onboarding configuration; a classifier returning a different one judged it."""
    path = _write(tmp_path, _classification(sensitivity_tier="S0"))
    violations = stages.check_classification(path, CLIENT_CONFIG)
    assert len(violations) == 1 and "never inferred" in violations[0]


def test_routing_decision_without_a_citation_is_caught(tmp_path):
    path = _write(tmp_path, _classification(evidence=[]))
    assert any("no citation" in v for v in stages.check_classification(path, CLIENT_CONFIG))


def test_invalid_project_type_is_caught(tmp_path):
    path = _write(tmp_path, _classification(project_type="probably_creative"))
    assert any("project_type" in v for v in stages.check_classification(path, CLIENT_CONFIG))


# ======================================================================================
# Step 3 — fidelity gate
# ======================================================================================

REPORT = {
    "source_id": "t", "tokens_flagged": 2, "glossary_matches": 1, "no_match_flags": 1,
    "diarization_issues": 0, "summary_suspicion": False, "fidelity_score": "medium",
    "verdict": "pass_with_flags",
}


def _fidelity_files(tmp_path, annotated, report=None):
    report_file = tmp_path / "r.json"
    annotated_file = tmp_path / "a.md"
    report_file.write_text(json.dumps(report or REPORT), encoding="utf-8")
    annotated_file.write_text(annotated, encoding="utf-8")
    return report_file, annotated_file


def test_annotation_before_punctuation_is_not_a_modification(tmp_path):
    """Regression: an annotation inserted before a comma leaves a space when naively stripped.
    The separator whitespace is part of the insertion, so a correct transcript passed here."""
    annotated = TRANSCRIPT.replace(
        "ογδόντα πέντε", 'ογδόντα πέντε [FIDELITY: no-glossary-match, garbled-numeric]'
    )
    report_file, annotated_file = _fidelity_files(tmp_path, annotated)
    assert stages.check_fidelity(report_file, annotated_file, TRANSCRIPT) == []


def test_multiple_annotations_pass(tmp_path):
    annotated = TRANSCRIPT.replace(
        "μπραντ αγουέρνες", 'μπραντ αγουέρνες [FIDELITY: glossary-match "brand awareness", confidence high]'
    ).replace("media spend", 'media spend [FIDELITY: glossary-match "media spend", confidence high]')
    report_file, annotated_file = _fidelity_files(tmp_path, annotated)
    assert stages.check_fidelity(report_file, annotated_file, TRANSCRIPT) == []


def test_silent_repair_of_the_transcript_is_caught(tmp_path):
    """The failure this stage exists to prevent: the token replaced rather than flagged."""
    annotated = TRANSCRIPT.replace(
        "μπραντ αγουέρνες", 'brand awareness [FIDELITY: glossary-match "brand awareness"]'
    )
    report_file, annotated_file = _fidelity_files(tmp_path, annotated)
    violations = stages.check_fidelity(report_file, annotated_file, TRANSCRIPT)
    assert len(violations) == 1 and "never repairs" in violations[0]


def test_dropped_line_is_caught(tmp_path):
    report_file, annotated_file = _fidelity_files(tmp_path, TRANSCRIPT.splitlines()[0])
    assert any("more than" in v for v in stages.check_fidelity(report_file, annotated_file, TRANSCRIPT))


def test_invalid_verdict_is_caught(tmp_path):
    report_file, annotated_file = _fidelity_files(tmp_path, TRANSCRIPT, {**REPORT, "verdict": "looks_fine"})
    assert any("verdict" in v for v in stages.check_fidelity(report_file, annotated_file, TRANSCRIPT))


# ======================================================================================
# Step 5 — conflict pass (deterministic)
# ======================================================================================


def _item(value, location="[00:02:00]", anchor="κάπου στα ογδόντα"):
    return {"value": value, "lang": "el", "location": location, "anchor": anchor,
            "speaker_or_author": "CFO", "qualifier": "stated", "confidence": "high"}


def _extract(**over):
    base = {f: [] for f in gates.BRIEF_FIELDS}
    base.update({"meta": {}, "open_questions": [], "internal_conflicts": [], "extraction_notes": []})
    base.update(over)
    return base


def test_candidate_needs_two_sources():
    single = {"talk": _extract(budget=[_item("around eighty")])}
    assert conflicts.find_conflict_candidates(single) == []


def test_two_sources_on_one_field_produce_a_candidate():
    both = {
        "talk": _extract(budget=[_item("around eighty, excluding media spend")]),
        "paper": _extract(budget=[_item("€90.000 including media", location="§6", anchor="€90.000")]),
    }
    candidates = conflicts.find_conflict_candidates(both)
    assert len(candidates) == 1
    assert candidates[0]["field"] == "budget"
    assert candidates[0]["sources"] == ["paper", "talk"]
    assert len(candidates[0]["positions"]) == 2


def test_agreement_also_produces_a_candidate():
    """Candidates are high-recall by design — telling agreement from contradiction is judgment."""
    same = {
        "talk": _extract(timeline=[_item("October")]),
        "paper": _extract(timeline=[_item("October", location="§5", anchor="Οκτωβρίου")]),
    }
    assert len(conflicts.find_conflict_candidates(same)) == 1


def test_internal_conflicts_are_carried_forward_with_provenance():
    extracts = {"talk": _extract(internal_conflicts=[{"field": "deliverables", "note": "retracted"}])}
    collected = conflicts.collect_internal_conflicts(extracts)
    assert collected == [{"source_id": "talk", "field": "deliverables", "note": "retracted"}]


def test_conflict_pass_writes_its_artifact(tmp_path):
    outcome = conflicts.run_conflict_pass(
        {"talk": _extract(budget=[_item("eighty")]), "paper": _extract(budget=[_item("ninety", "§6", "€90.000")])},
        tmp_path,
    )
    payload = json.loads((tmp_path / "conflict_candidates.json").read_text(encoding="utf-8"))
    assert outcome["candidate_fields"] == ["budget"]
    assert "NOT conflicts" in payload["note"]


# ======================================================================================
# Step 6 — synthesis
# ======================================================================================


def _ref(anchor="κάπου στα ογδόντα"):
    return {"source_id": "talk", "location": "[00:02:00]", "anchor": anchor, "speaker_or_author": "CFO"}


def _entry(**over):
    entry = {"content": "Production budget around eighty, excluding media spend",
             "evidence": [_ref()], "confidence": "medium", "qualifier": "stated"}
    entry.update(over)
    return entry


def _brief(**over):
    brief = {f: [] for f in gates.BRIEF_FIELDS}
    brief.update({
        "meta": {"sensitivity_tier": "S1"}, "budget": [_entry()],
        "open_questions": [], "conflicts": [], "signoff": {"status": "draft"},
    })
    brief.update(over)
    return brief


EXTRACTS = {"talk": _extract(budget=[_item("around eighty")])}


def _brief_file(tmp_path, brief):
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_pre_readiness_brief_passes(tmp_path):
    assert stages.check_synthesis(_brief_file(tmp_path, _brief()), EXTRACTS) == []


def test_model_authored_readiness_block_is_caught(tmp_path):
    """SYNTHESIS.md rule 8 — the runner computes readiness, and the harness recomputes it."""
    brief = _brief(readiness={"fields_with_evidence": 7, "low_confidence_share": 0.0,
                              "open_question_count": 0, "verdict": "ready_for_review"})
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS)
    assert any("computed by the runner" in v for v in violations)


def test_agent_signing_off_is_caught(tmp_path):
    brief = _brief(signoff={"status": "signed_off"})
    assert any("human act" in v for v in stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS))


def test_entry_without_evidence_is_caught(tmp_path):
    brief = _brief(budget=[_entry(evidence=[])])
    assert any("no evidence" in v for v in stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS))


def test_resolved_conflict_is_caught(tmp_path):
    """Resolution is human-only (PRD DR-10) — synthesis emits 'open' and nothing else."""
    brief = _brief(conflicts=[{"field": "budget", "status": "resolved_by_human",
                               "positions": [{"statement": "a", "evidence": _ref()},
                                             {"statement": "b", "evidence": _ref()}]}])
    assert any("resolution is human-only" in v for v in stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS))


def test_altered_anchor_is_caught(tmp_path):
    """Anchors are the Greek render's fidelity source; normalising one breaks the round trip."""
    brief = _brief(budget=[_entry(evidence=[_ref(anchor="around eighty thousand euros")])])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS)
    assert any("copied verbatim" in v for v in violations)


# ======================================================================================
# Step 7 — render
# ======================================================================================

BRIEF_FOR_RENDER = {
    "meta": {"sources": [{"source_id": "talk"}, {"source_id": "paper"}]},
    "budget": [{"content": "Around eighty, excluding media spend", "evidence": [_ref()],
                "confidence": "medium", "qualifier": "stated"}],
    "open_questions": [{"field": "budget", "gap": "media unknown", "why_it_matters": "scoping",
                        "suggested_question_for_client": "What is the media budget?"}],
    "conflicts": [],
}

GOOD_RENDER = """# Brief

## 1. Objectives
Grow the category. [talk 00:01:00]

## 6. Budget
Around eighty, excluding media spend. [talk 00:02:00]

## ⚠ Open Questions for the Client
1. What is the media budget?
"""


def _renders(tmp_path, el, en):
    (tmp_path / "brief_el.md").write_text(el, encoding="utf-8")
    (tmp_path / "brief_en.md").write_text(en, encoding="utf-8")
    return tmp_path / "brief_el.md", tmp_path / "brief_en.md"


def test_well_cited_renders_pass(tmp_path):
    el, en = _renders(tmp_path, GOOD_RENDER, GOOD_RENDER)
    assert stages.check_render(el, en, BRIEF_FOR_RENDER, CLIENT_CONFIG) == []


def test_uncited_claim_line_is_caught(tmp_path):
    bad = GOOD_RENDER + "\n## 7. Mandatories & No-gos\nWe recommend a larger budget.\n"
    el, en = _renders(tmp_path, GOOD_RENDER, bad)
    violations = stages.check_render(el, en, BRIEF_FOR_RENDER, CLIENT_CONFIG)
    assert any("no citation tag" in v for v in violations)


def test_tag_naming_an_unknown_source_is_caught(tmp_path):
    bad = GOOD_RENDER.replace("[talk 00:02:00]", "[some_other_doc 00:02:00]")
    el, en = _renders(tmp_path, GOOD_RENDER, bad)
    assert any("no known source" in v for v in stages.check_render(el, en, BRIEF_FOR_RENDER, CLIENT_CONFIG))


def test_lost_glossary_term_is_caught(tmp_path):
    """`media spend` is in the brief, so it must survive character-exact in both documents."""
    bad = GOOD_RENDER.replace("media spend", "δαπάνη μέσων")
    el, en = _renders(tmp_path, bad, GOOD_RENDER)
    violations = stages.check_render(el, en, BRIEF_FOR_RENDER, CLIENT_CONFIG)
    assert any("media spend" in v and "missing from the render" in v for v in violations)


def test_missing_render_is_caught(tmp_path):
    (tmp_path / "brief_en.md").write_text(GOOD_RENDER, encoding="utf-8")
    violations = stages.check_render(tmp_path / "brief_el.md", tmp_path / "brief_en.md",
                                     BRIEF_FOR_RENDER, CLIENT_CONFIG)
    assert any("no el render" in v for v in violations)


def test_claim_line_parsing_ignores_structure(tmp_path):
    """Headings, blockquotes and the metadata block are not claims."""
    assert stages.claim_lines(GOOD_RENDER) == [
        "Grow the category. [talk 00:01:00]",
        "Around eighty, excluding media spend. [talk 00:02:00]",
    ]

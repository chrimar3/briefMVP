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


def test_annotation_containing_brackets_is_stripped_cleanly(tmp_path):
    """Design audit F6: an annotation may quote a bracketed term; the strip must own the whole
    annotation, nested brackets included, or a correctly-annotated transcript is rejected for
    the residue of its own annotation."""
    annotated = TRANSCRIPT.replace(
        "μπραντ αγουέρνες", "μπραντ αγουέρνες [FIDELITY: glossary-match [brand awareness]]"
    )
    report_file, annotated_file = _fidelity_files(tmp_path, annotated)
    assert stages.check_fidelity(report_file, annotated_file, TRANSCRIPT) == []


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


def test_provenance_wins_if_a_conflict_ever_carries_a_source_id():
    """Defensive (design audit F10): the schema forbids a `source_id` key inside an internal
    conflict, but if one ever appears, the pipeline's provenance label must win — a spread
    that lets payload override provenance is a silent-collision waiting for a schema change."""
    extracts = {"talk": _extract(internal_conflicts=[{"field": "budget", "source_id": "spoofed"}])}
    assert conflicts.collect_internal_conflicts(extracts)[0]["source_id"] == "talk"


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
    # Fully schema-valid apart from `readiness` (runner-injected) — the synthesis gate now
    # validates a readiness-carrying probe copy, so the baseline fixture must be clean.
    brief = {f: [] for f in gates.BRIEF_FIELDS}
    brief.update({
        "meta": {"project_id": "p", "client_id": "meltemi_beverages",
                 "project_type": "advertising_creative", "classification_confidence": "high",
                 "sensitivity_tier": "S1",
                 "sources": [{"source_id": "talk", "source_type": "transcript",
                              "source_date": "2026-01-01"}],
                 "created_ts": "2026-01-02T00:00:00", "pipeline_version": "1.0.0"},
        "budget": [_entry()],
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


def test_altered_anchor_in_a_conflict_position_is_caught(tmp_path):
    """Design audit F2b: conflict positions carry evidence refs too, and the Greek render
    re-anchors on them — an anchor translated during assembly breaks that round trip."""
    brief = _brief(conflicts=[{"field": "budget", "status": "open",
                               "positions": [{"statement": "a", "evidence": _ref()},
                                             {"statement": "b",
                                              "evidence": _ref(anchor="a translated anchor")}]}])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS)
    assert any("copied verbatim" in v and "conflicts[0]" in v for v in violations)


def test_altered_anchor_in_an_open_question_link_is_caught(tmp_path):
    brief = _brief(open_questions=[{"field": "budget", "gap": "g", "why_it_matters": "w",
                                    "suggested_question_for_client": "q?",
                                    "linked_evidence": [_ref(anchor="paraphrased evidence")]}])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS)
    assert any("copied verbatim" in v and "open_questions[0]" in v for v in violations)


def test_schema_violation_is_visible_to_the_synthesis_repair_loop(tmp_path):
    """Design audit F3: a schema-invalid brief must fail INSIDE the gate, where the repair
    loop can see it — not after the loop has already recorded a clean attempt. The earlier
    design validated only post-loop, so an invalid enum died with zero repair rounds and a
    repair log that read 'no violations'."""
    brief = _brief(budget=[_entry(qualifier="speculative")])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), EXTRACTS)
    assert any("speculative" in v for v in violations)


def test_anchor_from_internal_conflicts_is_accepted(tmp_path):
    """Regression (Tier-3 confirmatory run): a retracted item lives in the extract's
    internal_conflicts, and synthesis may surface it as a conditional entry citing that anchor
    byte-exact. The gate must recognise internal_conflicts anchors, not only the 7 brief fields."""
    extract_with_retraction = _extract(internal_conflicts=[{
        "field": "deliverables",
        "value_a": {"value": "OOH at metro", "lang": "el", "location": "[00:08:15]",
                    "anchor": "ίσως κάνουμε OOH στις στάσεις του μετρό", "speaker_or_author": "CMO",
                    "qualifier": "stated", "confidence": "medium"},
        "value_b": {"value": "scratch that", "lang": "mixed", "location": "[00:08:34]",
                    "anchor": "actually scratch that, το μετρό είναι πανάκριβο", "speaker_or_author": "CMO",
                    "qualifier": "stated", "confidence": "high"},
        "note": "proposed then retracted",
    }])
    ic_ref = {"source_id": "talk", "location": "[00:08:15]",
              "anchor": "ίσως κάνουμε OOH στις στάσεις του μετρό", "speaker_or_author": "CMO"}
    brief = _brief(budget=[], deliverables=[_entry(content="OOH proposed then retracted",
                                                   qualifier="conditional", evidence=[ic_ref])])
    assert stages.check_synthesis(_brief_file(tmp_path, brief), {"talk": extract_with_retraction}) == []


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


# -- ⚠ coverage (design audit F4) ------------------------------------------------------

CONFLICT_TALK_VS_PAPER = {
    "field": "budget", "status": "open",
    "positions": [{"statement": "around eighty excl. media", "evidence": _ref()},
                  {"statement": "ninety incl. media",
                   "evidence": {**_ref(), "source_id": "paper"}}],
}

FULL_RENDER = """# Brief

## 1. Objectives
Grow the category. [talk 00:01:00]

## 6. Budget
Around eighty, excluding media spend. [talk 00:02:00]

## ⚠ Open Questions for the Client
1. What is the media budget?
2. What is the launch date?

## ⚠ Unresolved Conflicts (account lead must resolve before sign-off)
**Field: Budget**
- Position A: around eighty, excluding media spend [talk 00:02:00]
- Position B: ninety thousand including media [paper §6]
"""


def test_render_covering_every_question_and_conflict_passes(tmp_path):
    brief = {**BRIEF_FOR_RENDER,
             "open_questions": BRIEF_FOR_RENDER["open_questions"] + [
                 {"field": "timeline", "gap": "date unknown", "why_it_matters": "planning",
                  "suggested_question_for_client": "What is the launch date?"}],
             "conflicts": [CONFLICT_TALK_VS_PAPER]}
    el, en = _renders(tmp_path, FULL_RENDER, FULL_RENDER)
    assert stages.check_render(el, en, brief, CLIENT_CONFIG) == []


def test_conflicts_only_brief_still_requires_the_warning_section(tmp_path):
    """A brief with conflicts but zero open questions must still render the ⚠ section —
    surfaced disagreement is the product, and dropping the section silently was legal."""
    brief = {**BRIEF_FOR_RENDER, "open_questions": [], "conflicts": [CONFLICT_TALK_VS_PAPER]}
    without_warn = GOOD_RENDER.split("## ⚠")[0]
    el, en = _renders(tmp_path, without_warn, without_warn)
    violations = stages.check_render(el, en, brief, CLIENT_CONFIG)
    assert any("⚠" in v for v in violations)


def test_render_dropping_open_questions_is_caught(tmp_path):
    """The ⚠ section existing is not the same as every question reaching it: the brief has
    two open questions, the render numbers one."""
    brief = {**BRIEF_FOR_RENDER,
             "open_questions": BRIEF_FOR_RENDER["open_questions"] + [
                 {"field": "timeline", "gap": "date unknown", "why_it_matters": "planning",
                  "suggested_question_for_client": "What is the launch date?"}]}
    el, en = _renders(tmp_path, GOOD_RENDER, GOOD_RENDER)
    violations = stages.check_render(el, en, brief, CLIENT_CONFIG)
    assert any("open question" in v for v in violations)


def test_conflict_position_sources_must_appear_in_the_warning_region(tmp_path):
    """Both sides of a conflict render with their citations; a ⚠ region that never mentions
    one position's source has dropped half the disagreement."""
    brief = {**BRIEF_FOR_RENDER, "conflicts": [CONFLICT_TALK_VS_PAPER]}
    el, en = _renders(tmp_path, GOOD_RENDER, GOOD_RENDER)
    violations = stages.check_render(el, en, brief, CLIENT_CONFIG)
    assert any("conflicts[0]" in v and "paper" in v for v in violations)


def test_render_threads_the_model_override_to_the_invocation_seam(tmp_path, monkeypatch):
    """Cost-audit C3: the render A/B swaps the model exactly like the Tier-4 creative A/B —
    through run_gated's model_override, never by editing the agent definition."""
    captured = {}

    def fake_run_gated(agent, order, check, repair, access_dirs, **kw):
        captured.update(kw, agent=agent)
        (tmp_path / "brief_el.md").write_text("x", encoding="utf-8")
        (tmp_path / "brief_en.md").write_text("x", encoding="utf-8")
        return [{"attempt": 1, "subagent": {}, "violations": []}], None

    from pipeline import agents as agents_mod
    monkeypatch.setattr(agents_mod, "run_gated", fake_run_gated)
    (tmp_path / "brief.json").write_text("{}", encoding="utf-8")
    (tmp_path / "g.json").write_text(json.dumps(CLIENT_CONFIG), encoding="utf-8")
    stages.render(tmp_path, BRIEF_FOR_RENDER, tmp_path / "g.json", [], model_override="haiku")
    assert captured["model_override"] == "haiku"


# ======================================================================================
# Currency-discipline gate (post-C4 hardening) — SYNTHESIS.md rule 5 as a machine check.
# Synthetic figures ONLY (€70, £-free): encoding the fixture's seeded values would be
# tuning against the answer key.
# ======================================================================================


def _money_extract(**over):
    """An extract whose only currency-marked source evidence is '€50.000' (dot separator)."""
    item = _item("συνολικό ποσό €50.000 για την καμπάνια", location="§6", anchor="€50.000 συνολικά")
    return _extract(budget=[item], **over)


def test_unsourced_currency_assertion_is_caught(tmp_path):
    """Slip shape 1: an entry asserts a resolved '€70k' no source ever wrote."""
    brief = _brief(budget=[_entry(content="Production budget is €70k excluding media",
                                  evidence=[_ref(anchor="κάπου στα εβδομήντα")])])
    extracts = {"talk": _extract(budget=[_item("κάπου στα εβδομήντα",
                                               anchor="κάπου στα εβδομήντα")])}
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), extracts)
    assert any("no source that wrote that mark" in v for v in violations)


def test_unsourced_currency_gloss_in_a_question_is_caught(tmp_path):
    """Slip shape 2: the question asks correctly in words, then writes the answer as a
    parenthetical gloss — '(€70k–€75k)'."""
    brief = _brief(open_questions=[{
        "field": "budget", "gap": "range unstated",
        "why_it_matters": "scoping",
        "suggested_question_for_client":
            "Το εύρος 70–75 αφορά χιλιάδες ευρώ (€70k–€75k);"}])
    extracts = {"talk": _extract(budget=[_item("κάπου στα εβδομήντα",
                                               anchor="κάπου στα εβδομήντα")])}
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), extracts)
    assert any("no source that wrote that mark" in v for v in violations)


def test_sourced_currency_passes_across_separator_styles(tmp_path):
    """The control that keeps this from teaching symbol-stripping: a figure a source DID
    write keeps its mark — in the source's dot style or the EN-pivot comma style."""
    brief = _brief(
        budget=[_entry(content="Total budget €50,000 including media",
                       evidence=[_ref(anchor="€50.000 συνολικά")])],
        open_questions=[{
            "field": "budget", "gap": "allocation of the €50.000 unspecified",
            "why_it_matters": "scoping",
            "suggested_question_for_client":
                "Από τα €50.000, πόσα αφορούν production;"}])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief),
                                        {"paper": _money_extract()})
    assert not any("wrote that mark" in v for v in violations)


def test_asking_in_words_is_never_flagged(tmp_path):
    """'σε χιλιάδες ευρώ;' is the CORRECT behavior — the word ευρώ with no mark+digit
    pairing must never trigger the gate."""
    brief = _brief(open_questions=[{
        "field": "budget", "gap": "units unstated", "why_it_matters": "scoping",
        "suggested_question_for_client":
            "Το εύρος 70–75 αφορά χιλιάδες ευρώ; Ποιο είναι το νόμισμα;"}])
    extracts = {"talk": _extract(budget=[_item("κάπου στα εβδομήντα",
                                               anchor="κάπου στα εβδομήντα")])}
    violations = stages.check_synthesis(_brief_file(tmp_path, brief), extracts)
    assert not any("wrote that mark" in v for v in violations)


def test_conflict_positions_are_exempt_like_the_harness_trap(tmp_path):
    """Conflicts quote sources verbatim — the one place a disputed figure belongs. The gate
    mirrors harness X3's conflict exemption and never scans conflicts[]."""
    brief = _brief(conflicts=[{"field": "budget", "status": "open",
                               "positions": [
                                   {"statement": "Total is €50.000 including media",
                                    "evidence": _ref(anchor="€50.000 συνολικά")},
                                   {"statement": "around seventy, units unstated",
                                    "evidence": _ref()}]}])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief),
                                        {"paper": _money_extract()})
    assert not any("wrote that mark" in v for v in violations)


def test_k_suffix_normalises_to_the_source_figure(tmp_path):
    """'€50k' is the same fact as the source's '€50.000' — formatting, not invention."""
    brief = _brief(budget=[_entry(content="Budget €50k total",
                                  evidence=[_ref(anchor="€50.000 συνολικά")])])
    violations = stages.check_synthesis(_brief_file(tmp_path, brief),
                                        {"paper": _money_extract()})
    assert not any("wrote that mark" in v for v in violations)

"""Round-2 prompt-contract gates (r2-W-R): the skill rules that now have a deterministic check.

* SOURCES.md §4 — one meaning per confidence level; every medium/low item linked from a question.
* SOURCES.md §7 rule G — the structured `garble:` note, garbled items at `low`, every fidelity flag noted.
* SOURCES.md §5 — a background document's commitment-field items are `implied`.
* SYNTHESIS.md rule 10 — a garbled token stays visible in reader-facing content (owner decision
  2026-09-23 no. 1), at no more than the garbled item's confidence.
* TRANSCRIPTS.md §4 — report counts match the annotations; the rubric's visible conditions.
* The prompt texts themselves: skill examples parse under the gates, staged-input paths, render's
  protected-path sentence, render order without paraphrased rules, sonnet-only verifier routing.

Synthetic, invented content only — no fixture text (tests/test_prompt_hygiene.py covers prompts).
"""

import json
import re
from pathlib import Path

import pytest

from pipeline import extract_rules, extraction, gates, stage_fidelity, stage_render, stage_synthesis

REPO = Path(__file__).resolve().parents[1]

SOURCE = """# Workshop
source_id: w · source_type: transcript · source_date: 2026-03-10

[00:04:10] ANNA: Θέλουμε περισσότερες εγγραφές από τη λαντινγκ πέιτζ μέσα στην άνοιξη.
[00:06:30] ANNA: Το budget είναι γύρω στα σαράντα.
"""
ANNOTATED = SOURCE.replace("λαντινγκ πέιτζ", 'λαντινγκ πέιτζ [FIDELITY: glossary-match "landing page"]')
NOTE = 'garble: «λαντινγκ πέιτζ» at [00:04:10] — proposed match "landing page"'


def _item(value, anchor, location="[00:04:10]", qualifier="stated", confidence="high"):
    return {"value": value, "lang": "el", "location": location, "anchor": anchor,
            "speaker_or_author": "ANNA", "qualifier": qualifier, "confidence": confidence}


GARBLED = _item("περισσότερες εγγραφές από τη λαντινγκ πέιτζ", "εγγραφές από τη λαντινγκ πέιτζ",
                confidence="low")
BUDGET = _item("γύρω στα σαράντα", "γύρω στα σαράντα", location="[00:06:30]", confidence="medium")


def _question(*links):
    return {"field": "x", "gap": "g", "why_it_matters": "w", "suggested_question_for_client": "q?",
            "linked_items": list(links)}


def _extract(**over):
    base = {"meta": {"project_id": "p", "source_id": "w", "source_type": "transcript",
                     "source_date": "2026-03-10", "extraction_ts": "t", "agent_version": "1.0"},
            "objectives": [GARBLED], "audiences": [], "key_messages": [], "deliverables": [],
            "timeline": [], "budget": [BUDGET], "mandatories": [],
            "open_questions": [_question("objectives[0]", "budget[0]")], "internal_conflicts": [],
            "extraction_notes": [NOTE]}
    base.update(over)
    return base


def _violations(extract, annotated=""):
    return extract_rules.check_extract_rules(extract, SOURCE, annotated)


def test_a_contract_compliant_extract_passes_every_rule():
    assert _violations(_extract(), ANNOTATED) == []


# -- SOURCES.md §4: confidence semantics --------------------------------------------------


@pytest.mark.parametrize("qualifier, confidence, field, expected", [
    ("implied", "medium", "objectives", "is `low` by definition"),
    ("implied", "high", "audiences", "is `low` by definition"),
    ("conditional", "high", "deliverables", "never an explicit commitment"),
    ("stated", "low", "timeline", "reserved for the two overrides"),
])
def test_confidence_has_one_meaning_per_level(qualifier, confidence, field, expected):
    item = _item("περίπου τον Μάιο", "γύρω στα σαράντα", qualifier=qualifier, confidence=confidence)
    extract = _extract(**{field: [item]}, open_questions=[_question("objectives[0]", "budget[0]",
                                                                    f"{field}[0]")])
    assert any(expected in v and f"{field}[0]" in v for v in _violations(extract))


def test_the_two_overrides_allow_a_stated_low_item():
    """Override G (the garbled objective in the base extract) and override M (a mandatory)."""
    mandatory = _item("χωρίς αναφορές σε ανταγωνιστές", "γύρω στα σαράντα", confidence="low")
    extract = _extract(mandatories=[mandatory],
                       open_questions=[_question("objectives[0]", "budget[0]", "mandatories[0]")])
    assert extract_rules.rule_confidence_semantics(extract) == []


# -- SOURCES.md §4: medium/low → linked open question -----------------------------------


def test_an_unlinked_medium_item_is_named():
    violations = _violations(_extract(open_questions=[_question("objectives[0]")]))
    assert any("budget[0]: confidence 'medium' but no open question links it" in v for v in violations)


@pytest.mark.parametrize("link", ["budget[3]", "the budget line", "scope[0]", "budget"])
def test_a_link_must_name_an_existing_item(link):
    extract = _extract(open_questions=[_question("objectives[0]", "budget[0]", link)])
    assert any("names no item of this extract" in v for v in _violations(extract))


# -- SOURCES.md §7 rule G ---------------------------------------------------------------


def test_a_garbled_item_above_low_is_named():
    extract = _extract(objectives=[{**GARBLED, "confidence": "high"}])
    assert any("objectives[0]: carries the garbled token «λαντινγκ πέιτζ» at confidence 'high'" in v
               for v in _violations(extract))


def test_a_garble_note_must_quote_the_source():
    extract = _extract(extraction_notes=['garble: «λάντινγκ μπέιτζ» at [00:04:10] — proposed match "landing page"'])
    assert any("does not occur in the source" in v for v in _violations(extract))


def test_every_fidelity_flag_needs_a_garble_note():
    free_form = _extract(extraction_notes=["[00:04:10] token flagged, probably landing page"])
    violations = _violations(free_form, ANNOTATED)
    assert any('glossary match "landing page" but no extraction note carries it' in v for v in violations)
    no_match = SOURCE.replace("σαράντα", "σαράντα [FIDELITY: no-glossary-match]")
    assert any("no glossary match but no extraction note" in v for v in _violations(_extract(), no_match))


def test_check_extract_runs_the_rules_with_the_annotated_text(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps(_extract()), encoding="utf-8")
    assert extraction.check_extract(path, SOURCE, {"terms": []}, annotated_text=ANNOTATED) == []
    path.write_text(json.dumps(_extract(extraction_notes=[])), encoding="utf-8")
    violations = extraction.check_extract(path, SOURCE, {"terms": []}, annotated_text=ANNOTATED)
    assert any("no extraction note carries it" in v for v in violations)
    assert any("reserved for the two overrides" in v for v in violations)  # low without its note


# -- SOURCES.md §5: background posture ---------------------------------------------------


def test_background_commitment_items_are_implied():
    stated = _item("τυπικό budget λανσαρίσματος", "γύρω στα σαράντα", confidence="medium")
    extract = _extract(budget=[stated])
    assert any("background is context, never a commitment" in v
               for v in extract_rules.rule_background_commitments(extract, "background"))
    assert extract_rules.rule_background_commitments(extract, "transcript") == []
    implied = _extract(budget=[{**stated, "qualifier": "implied", "confidence": "low"}])
    assert extract_rules.rule_background_commitments(implied, "background") == []


def test_background_brand_rules_may_be_stated():
    rule = _item("ο τόνος μένει ζεστός", "γύρω στα σαράντα")
    extract = _extract(mandatories=[rule], budget=[])
    assert extract_rules.rule_background_commitments(extract, "background") == []


# -- SYNTHESIS.md rule 10: garble carry-through ------------------------------------------


def _brief(content, confidence="low", statement=None):
    ref = {"source_id": "w", "location": "[00:04:10]", "anchor": GARBLED["anchor"],
           "speaker_or_author": "ANNA"}
    brief = {"objectives": [{"content": content, "evidence": [ref], "confidence": confidence,
                             "qualifier": "stated"}]}
    if statement is not None:
        other = {"source_id": "w", "location": "[00:06:30]", "anchor": BUDGET["anchor"],
                 "speaker_or_author": "ANNA"}
        brief["conflicts"] = [{"field": "objectives", "status": "open",
                               "positions": [{"statement": statement, "evidence": ref},
                                             {"statement": "other", "evidence": other}]}]
    return brief


CARRIED = 'More sign-ups from the landing page (heard as «λαντινγκ πέιτζ»; proposed match "landing page", unconfirmed)'


def test_a_carried_garble_passes():
    assert stage_synthesis.rule_garble_carry_through(_brief(CARRIED, statement=CARRIED), {"w": _extract()}) == []


def test_a_silently_normalised_garble_is_named():
    violations = stage_synthesis.rule_garble_carry_through(
        _brief("More sign-ups from the landing page", statement="the landing page"), {"w": _extract()})
    assert any(v.startswith("objectives[0]:") and "does not show «λαντινγκ πέιτζ»" in v for v in violations)
    assert any(v.startswith("conflicts[0].positions[0]:") for v in violations)


def test_the_token_without_its_match_is_named():
    violations = stage_synthesis.rule_garble_carry_through(
        _brief("More sign-ups (heard as «λαντινγκ πέιτζ»)"), {"w": _extract()})
    assert any("beside its proposed match 'landing page'" in v for v in violations)


def test_a_garbled_entry_above_the_item_confidence_is_named():
    violations = stage_synthesis.rule_garble_carry_through(_brief(CARRIED, confidence="high"),
                                                           {"w": _extract()})
    assert any("confidence 'high' is above the garbled item" in v for v in violations)


def test_the_rule_is_part_of_the_synthesis_gate(tmp_path):
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(_brief("More sign-ups from the landing page")), encoding="utf-8")
    assert stage_synthesis.rule_garble_carry_through in stage_synthesis.SYNTHESIS_RULES
    assert any("SYNTHESIS.md rule 10" in v for v in stage_synthesis.check_synthesis(path, {"w": _extract()}))


def test_extracts_without_garble_notes_leave_the_rule_silent():
    assert stage_synthesis.rule_garble_carry_through(_brief("anything"), {"w": _extract(extraction_notes=[])}) == []


# -- TRANSCRIPTS.md §4: counts and rubric --------------------------------------------------


def _fidelity(tmp_path, annotated, **report):
    base = {"source_id": "w", "tokens_flagged": 1, "glossary_matches": 1, "no_match_flags": 0,
            "diarization_issues": 0, "summary_suspicion": False, "fidelity_score": "high",
            "verdict": "pass_with_flags", **report}
    (tmp_path / "r.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "a.md").write_text(annotated, encoding="utf-8")
    return stage_fidelity.check_fidelity(tmp_path / "r.json", tmp_path / "a.md", SOURCE)


def test_counts_matching_the_annotations_pass(tmp_path):
    assert _fidelity(tmp_path, ANNOTATED) == []


@pytest.mark.parametrize("report, key", [({"tokens_flagged": 2}, "tokens_flagged"),
                                         ({"glossary_matches": 0, "tokens_flagged": 0}, "glossary_matches"),
                                         ({"no_match_flags": 1}, "no_match_flags")])
def test_counts_that_differ_from_the_annotations_fail(tmp_path, report, key):
    assert any(f"report {key} is" in v for v in _fidelity(tmp_path, ANNOTATED, **report))


def test_rubric_high_excludes_no_match_flags_and_pass_excludes_flags(tmp_path):
    annotated = ANNOTATED.replace("σαράντα", "σαράντα [FIDELITY: no-glossary-match]")
    report = {"tokens_flagged": 2, "no_match_flags": 1}
    assert any("`high` requires neither" in v for v in _fidelity(tmp_path, annotated, **report))
    assert _fidelity(tmp_path, annotated, fidelity_score="medium", **report) == []
    assert any("passes 'pass_with_flags'" in v for v in _fidelity(tmp_path, ANNOTATED, verdict="pass"))
    assert _fidelity(tmp_path, SOURCE, tokens_flagged=0, glossary_matches=0, verdict="pass") == []


# -- the prompt texts ---------------------------------------------------------------------


def _text(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_the_skill_examples_are_what_the_gates_parse():
    """The format taught in SOURCES.md is the format the gate reads — one source of truth."""
    sources = _text("skills/SOURCES.md")
    example = re.search(r"e\.g\. `(garble: [^`]+)`", sources).group(1)
    assert extract_rules.garble_notes({"extraction_notes": [example]}), example
    assert '"<field>[<index>]"' in sources and '"budget[0]"' in sources
    synthesis = _text("skills/SYNTHESIS.md")
    assert "10. **Garbled tokens stay visible" in synthesis and "unconfirmed" in synthesis


def test_the_fidelity_annotation_carries_a_proposal_never_a_confidence():
    transcripts = _text("skills/TRANSCRIPTS.md")
    assert "confidence high]" not in transcripts
    assert '[FIDELITY: glossary-match "<glossary term>"]' in transcripts
    assert "Scoring rubric" in transcripts and "Report counts match annotations" in transcripts


def test_sources_rule_3_and_the_email_row_agree():
    sources = _text("skills/SOURCES.md")
    assert "unless the source itself settles the matter" in sources
    assert "Per rule 3, an explicit supersession needs no `open_question`" in sources


def test_the_candidate_date_has_a_home():
    sources = _text("skills/SOURCES.md")
    assert "goes into the item's linked `open_question`" in sources
    assert "always `conditional`" not in sources
    assert "candidate date for a relative deadline" in _text(".claude/agents/verify-extract.md")


def test_client_config_paths_point_at_the_staged_copy():
    assert "glossary/<client>.json" not in _text(".claude/agents/classify.md")
    assert "inputs/client/" in _text(".claude/agents/classify.md")
    assert "glossary/*.json" not in _text("skills/TRANSLATION.md")


@pytest.mark.parametrize("agent", ["extract", "fidelity-check", "synthesize", "render"])
def test_every_skill_wrapper_carries_the_protected_path_sentence(agent):
    assert "checked by hash after your step; a write there fails the run" in _text(f".claude/agents/{agent}.md")


def test_the_render_order_supplies_parameters_not_paraphrased_rules():
    order = stage_render.build_render_order(Path("/b.json"), Path("/el.md"), Path("/en.md"), Path("/t.md"),
                                            Path("/g.json"))
    for paraphrase in ("CHARACTER-EXACT", "citation tag of the form", "no totalling", "raw enum value",
                       "blockquote note"):
        assert paraphrase not in order, f"render order restates TRANSLATION.md: {paraphrase!r}"
    assert "TRANSLATION.md" in order


def test_verifier_routing_is_declared_sonnet_only():
    policy = json.loads(_text("config/model_routing.json"))["verify_extract"]
    assert policy["strong_model"] == policy["base_model"] == "sonnet"
    assert extraction._verify_policy()["base_model"] == "sonnet"
    assert "sonnet-only" in _text("CLAUDE.md") or "always sonnet" in _text("CLAUDE.md")
    assert gates.BRIEF_FIELDS  # the risk classes still read the same seven fields

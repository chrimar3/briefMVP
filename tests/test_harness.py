"""Tests for the grader.

`eval/harness.py` freezes at the end of Tier 1, which means a broken Tier-3 check would stay
broken and quietly mark a failing run green. So the Tier-2 and Tier-3 checks are exercised here
against synthetic artifacts *now*, before the tiers that produce them exist. Every fixture below
is invented for the test — nothing is copied from `fixtures/northlight_01`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import harness  # noqa: E402

TRANSCRIPT = """# Call
source_id: talk · source_type: transcript · source_date: 2026-01-01

[00:01:00] CMO: Θέλουμε μπραντ αγουέρνες φέτος.
[00:02:00] CFO: γύρω στα πενήντα, χωρίς το media spend.
[00:03:00] CMO: maybe a TikTok dance thing, don't hold me to it.
"""

RFP = """# RFP
source_id: paper · source_type: rfp · source_date: 2026-01-02

Budget €70.000 total. Launch March 2026.
"""

ANSWER_KEY = {
    "fixture": "synthetic",
    "expected_classification": {"project_type": "advertising_creative", "sensitivity_tier": "S1"},
    "seeded_conflicts": [
        {
            "id": "C1", "field": "budget",
            "position_a": {"source_id": "paper", "signal": "70.000"},
            "position_b": {"source_id": "talk", "signal": "πενήντα"},
        }
    ],
    "seeded_gaps": [
        {"id": "G1", "field_any_of": ["budget"], "keyword_any_of": ["media spend"]},
        {"id": "G2", "field_any_of": ["objectives"], "keyword_any_of": ["KPI"]},
    ],
    "seeded_garbling": [{"id": "T1", "source_id": "talk", "corrupted": "μπραντ αγουέρνες", "intended": "brand awareness"}],
    "traps": [
        {"id": "X1", "type": "retraction", "forbidden_as_committed_keywords": ["OOH", "μετρό"]},
        {"id": "X2", "type": "speculation", "keywords": ["TikTok dance"]},
        {"id": "X3", "type": "no_invention", "forbidden_patterns": ["€50", "50.000"]},
    ],
    "scoring": {"conflicts_required": 1, "gaps_required_min": 1},
}


def _item(**over):
    item = {
        "value": "γύρω στα πενήντα, χωρίς το media spend", "lang": "el",
        "location": "[00:02:00]", "anchor": "γύρω στα πενήντα",
        "speaker_or_author": "CFO", "qualifier": "stated", "confidence": "medium",
    }
    item.update(over)
    return item


def _extract(**over):
    base = {
        "meta": {"project_id": "p", "source_id": "talk", "source_type": "transcript",
                 "source_date": "2026-01-01", "extraction_ts": "2026-01-02T00:00:00", "agent_version": "1.0"},
        "objectives": [], "audiences": [], "key_messages": [], "deliverables": [],
        "timeline": [], "budget": [_item()], "mandatories": [],
        "open_questions": [], "internal_conflicts": [],
        "extraction_notes": ["Token 'μπραντ αγουέρνες' kept as-is; probable glossary match 'brand awareness'."],
    }
    base.update(over)
    return base


def _ref(source_id="talk", location="[00:02:00]", anchor="γύρω στα πενήντα"):
    return {"source_id": source_id, "location": location, "anchor": anchor, "speaker_or_author": "CFO"}


def _entry(content="Production budget around fifty, excluding media spend", **over):
    entry = {"content": content, "evidence": [_ref()], "confidence": "medium", "qualifier": "stated"}
    entry.update(over)
    return entry


def _brief(**over):
    brief = {
        "meta": {
            "project_id": "p", "client_id": "c", "project_type": "advertising_creative",
            "classification_confidence": "high", "sensitivity_tier": "S1",
            "sources": [{"source_id": "talk", "source_type": "transcript", "source_date": "2026-01-01"},
                        {"source_id": "paper", "source_type": "rfp", "source_date": "2026-01-02"}],
            "created_ts": "2026-01-03T00:00:00", "pipeline_version": "test",
        },
        "objectives": [], "audiences": [], "key_messages": [], "deliverables": [],
        "timeline": [], "budget": [_entry()], "mandatories": [],
        "open_questions": [], "conflicts": [],
        "readiness": {"fields_with_evidence": 1, "low_confidence_share": 0.0,
                      "open_question_count": 0, "verdict": "thin_input_return_to_client"},
        "signoff": {"status": "draft"},
    }
    brief.update(over)
    return brief


@pytest.fixture
def synth(tmp_path):
    """A minimal but real run directory the harness can load."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "talk.md").write_text(TRANSCRIPT, encoding="utf-8")
    (project / "paper.md").write_text(RFP, encoding="utf-8")
    (project / "answer_key.json").write_text(json.dumps(ANSWER_KEY, ensure_ascii=False), encoding="utf-8")

    run_dir = tmp_path / "runs" / "r1"
    (run_dir / "extracts").mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "r1", "project_dir": str(project)}), encoding="utf-8"
    )

    def write(extract=None, brief=None, renders=None):
        if extract is not None:
            (run_dir / "extracts" / "talk.json").write_text(
                json.dumps(extract, ensure_ascii=False), encoding="utf-8")
        if brief is not None:
            (run_dir / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        for lang, text in (renders or {}).items():
            (run_dir / f"brief_{lang}.md").write_text(text, encoding="utf-8")
        return harness.load_run(run_dir)

    return write


def _result(run, check):
    return check(run)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


def test_run_without_manifest_cannot_be_graded(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(harness.HarnessError, match="run_manifest"):
        harness.load_run(tmp_path / "empty")


def test_run_without_answer_key_cannot_be_graded(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    (project / "t.md").write_text(TRANSCRIPT, encoding="utf-8")
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(json.dumps({"project_dir": str(project)}), encoding="utf-8")
    with pytest.raises(harness.HarnessError, match="answer_key"):
        harness.load_run(run_dir)


# --------------------------------------------------------------------------------------
# Tier 1
# --------------------------------------------------------------------------------------


def test_clean_extract_passes_every_tier_1_check(synth):
    run = synth(extract=_extract())
    for check in (harness.check_extracts_validate, harness.check_citations_present,
                  harness.check_citations_resolve, harness.check_garbling_flagged_not_fixed):
        assert check(run).status == "pass", check.__name__


def test_invented_location_is_caught(synth):
    run = synth(extract=_extract(budget=[_item(location="[09:99]")]))
    result = harness.check_citations_resolve(run)
    assert result.failed and "does not occur in the source" in result.evidence[0]


def test_silent_correction_is_caught(synth):
    """The corrupted token vanishes and the clean term takes its place."""
    run = synth(extract=_extract(extraction_notes=["Extracted brand awareness as the objective."]))
    result = harness.check_garbling_flagged_not_fixed(run)
    assert result.failed and "silently corrected" in result.evidence[0]


def test_silent_consumption_is_caught(synth):
    """The token survives but nobody proposes the glossary match — no one is warned."""
    run = synth(extract=_extract(
        objectives=[_item(value="μπραντ αγουέρνες", location="[00:01:00]", anchor="Θέλουμε μπραντ αγουέρνες")],
        extraction_notes=["Budget figures kept verbatim."],
    ))
    result = harness.check_garbling_flagged_not_fixed(run)
    assert result.failed and "silent consumption" in result.evidence[0]


def test_repair_written_into_a_value_is_caught(synth):
    """The proposal belongs in a note; putting it in the evidence is still a repair."""
    run = synth(extract=_extract(
        objectives=[_item(value="brand awareness push", location="[00:01:00]", anchor="Θέλουμε μπραντ αγουέρνες")],
        extraction_notes=["Token 'μπραντ αγουέρνες' probable glossary match 'brand awareness'."],
    ))
    result = harness.check_garbling_flagged_not_fixed(run)
    assert result.failed and "belongs in a note" in result.evidence[0]


def test_schema_check_alone_would_have_passed_the_bad_artifact(synth):
    """The finding from the first real Tier-1 run, locked in as a regression test."""
    bad = _extract(budget=[_item(location="[09:99]")],
                   extraction_notes=["Extracted brand awareness as the objective."])
    run = synth(extract=bad)
    assert harness.check_extracts_validate(run).status == "pass"
    assert harness.check_citations_present(run).status == "pass"
    assert harness.check_citations_resolve(run).failed
    assert harness.check_garbling_flagged_not_fixed(run).failed


# --------------------------------------------------------------------------------------
# Tier 2
# --------------------------------------------------------------------------------------


def test_tier_2_checks_skip_cleanly_before_tier_2_exists(synth):
    run = synth(extract=_extract())
    for check in (harness.check_brief_validates, harness.check_both_renders_exist,
                  harness.check_no_orphan_prose, harness.check_readiness_recomputes):
        assert check(run).status == "skip", check.__name__


def test_valid_brief_passes(synth):
    run = synth(extract=_extract(), brief=_brief())
    assert harness.check_brief_validates(run).status == "pass"
    assert harness.check_sensitivity_scope(run).status == "pass"


def test_regulated_tier_fails_scope(synth):
    brief = _brief()
    brief["meta"]["sensitivity_tier"] = "S2"
    run = synth(extract=_extract(), brief=brief)
    assert harness.check_sensitivity_scope(run).failed


def test_orphan_prose_is_caught(synth):
    renders = {
        "en": "# Brief\n\n## 1. Objectives\nGrow the category. [talk 00:02:00]\nWe recommend a bigger budget.\n",
        "el": "# Brief\n\n## 1. Objectives\nΑνάπτυξη κατηγορίας. [talk 00:02:00]\n",
    }
    run = synth(extract=_extract(), brief=_brief(), renders=renders)
    result = harness.check_no_orphan_prose(run)
    assert result.failed and "uncited claim line" in result.evidence[0]


def test_cited_claim_lines_pass(synth):
    renders = {lang: f"# Brief\n\n## 1. Objectives\nGrow. [talk 00:02:00]\n\n## 6. Budget\nAround fifty. [paper §6]\n"
               for lang in ("en", "el")}
    run = synth(extract=_extract(), brief=_brief(), renders=renders)
    assert harness.check_no_orphan_prose(run).status == "pass"


def test_tag_naming_an_unknown_source_is_caught(synth):
    renders = {lang: "# Brief\n\n## 1. Objectives\nGrow. [invented_source 00:02:00]\n" for lang in ("en", "el")}
    run = synth(extract=_extract(), brief=_brief(), renders=renders)
    result = harness.check_no_orphan_prose(run)
    assert result.failed and "names no known source" in result.evidence[0]


def test_readiness_mismatch_is_caught(synth):
    """A model-authored readiness block cannot survive recomputation."""
    brief = _brief()
    brief["readiness"]["verdict"] = "ready_for_review"
    run = synth(extract=_extract(), brief=brief)
    result = harness.check_readiness_recomputes(run)
    assert result.failed and "differs from recomputation" in result.detail


def test_readiness_match_passes(synth):
    from pipeline import gates

    brief = _brief()
    brief["readiness"] = gates.compute_readiness_block(brief)
    run = synth(extract=_extract(), brief=brief)
    assert harness.check_readiness_recomputes(run).status == "pass"


# --------------------------------------------------------------------------------------
# Tier 3
# --------------------------------------------------------------------------------------


def _conflict():
    return {
        "field": "budget",
        "positions": [
            {"statement": "RFP states €70.000 total", "evidence": _ref("paper", "§6", "Budget €70.000 total")},
            {"statement": "CFO said γύρω στα πενήντα excluding media", "evidence": _ref()},
        ],
        "status": "open",
    }


def test_seeded_conflict_detected_with_both_citations(synth):
    run = synth(extract=_extract(), brief=_brief(conflicts=[_conflict()]))
    assert harness.check_seeded_conflicts(run).status == "pass"


def test_conflict_citing_only_one_source_does_not_count(synth):
    half = _conflict()
    half["positions"][0]["evidence"] = _ref()  # both positions now cite the transcript
    run = synth(extract=_extract(), brief=_brief(conflicts=[half]))
    assert harness.check_seeded_conflicts(run).failed


def test_seeded_gaps_counted_against_the_minimum(synth):
    questions = [{"field": "budget", "gap": "media spend range unknown",
                  "why_it_matters": "scoping", "suggested_question_for_client": "What is the media spend?"}]
    run = synth(extract=_extract(), brief=_brief(open_questions=questions))
    result = harness.check_seeded_gaps(run)
    assert result.status == "pass" and "1/2" in result.detail


def test_no_open_questions_fails_the_gap_minimum(synth):
    assert harness.check_seeded_gaps(synth(extract=_extract(), brief=_brief())).failed


def test_uncited_brief_value_is_caught(synth):
    run = synth(extract=_extract(), brief=_brief(budget=[_entry(evidence=[_ref(anchor="  ")])]))
    result = harness.check_no_uncited_values(run)
    assert result.failed and "empty location or anchor" in result.evidence[0]


def test_x1_retracted_idea_committed_is_caught(synth):
    run = synth(extract=_extract(), brief=_brief(deliverables=[_entry(content="OOH at metro stations")]))
    assert harness.check_trap_x1_retraction(run).failed


def test_x1_retracted_idea_marked_conditional_passes(synth):
    entry = _entry(content="OOH at metro stations (retracted in the meeting)", qualifier="conditional")
    run = synth(extract=_extract(), brief=_brief(deliverables=[entry]))
    assert harness.check_trap_x1_retraction(run).status == "pass"


def test_x2_speculation_without_conditional_is_caught(synth):
    run = synth(extract=_extract(), brief=_brief(deliverables=[_entry(content="A TikTok dance challenge")]))
    result = harness.check_trap_x2_speculation(run)
    assert result.failed and "expected 'conditional'" in result.evidence[0]


def test_x2_speculation_marked_conditional_passes(synth):
    entry = _entry(content="A TikTok dance challenge — floated, not committed", qualifier="conditional")
    run = synth(extract=_extract(), brief=_brief(deliverables=[entry]))
    assert harness.check_trap_x2_speculation(run).status == "pass"


def test_x3_invented_total_in_the_brief_is_caught(synth):
    run = synth(extract=_extract(), brief=_brief(budget=[_entry(content="Total budget €50.000 confirmed")]))
    result = harness.check_trap_x3_no_invented_total(run)
    assert result.failed and "outside a conflict position" in result.evidence[0]


def test_x3_allows_a_verbatim_figure_inside_a_conflict_position(synth):
    """Quoting what a source actually said is the point of a conflict block."""
    conflict = _conflict()
    conflict["positions"][0]["statement"] = "RFP states 50.000 including media"
    run = synth(extract=_extract(), brief=_brief(conflicts=[conflict]))
    assert harness.check_trap_x3_no_invented_total(run).status == "pass"


# --------------------------------------------------------------------------------------
# End-to-end grading
# --------------------------------------------------------------------------------------


def test_grade_filters_by_tier(synth):
    run = synth(extract=_extract())
    assert {r.tier for r in harness.grade(run, tier=1)} == {1}


def test_report_writes_a_machine_readable_verdict(synth, capsys):
    run = synth(extract=_extract())
    payload = harness.report(run, harness.grade(run, tier=1))
    capsys.readouterr()
    assert payload["verdict"] == "PASS"
    written = json.loads((run.run_dir / "harness_report.json").read_text(encoding="utf-8"))
    assert written["summary"]["passed"] == 4

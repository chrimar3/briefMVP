"""Agency workflow contracts; synthetic data only, no model calls."""
import copy
import json

import pytest

from pipeline import clarifications, client_pack, handover, quality, revisions


def evidence(source="rfp", anchor="Build awareness", location="L1"):
    return {"source_id": source, "anchor": anchor, "location": location}


def brief():
    return {"meta": {"client_id": "synthetic", "project_id": "launch", "sources": [{"source_id": "rfp"}]},
            "objectives": [{"content": "Build awareness", "evidence": [evidence()]}],
            "open_questions": [], "conflicts": []}


def extracts():
    return {"rfp": {"objectives": [{"value": "Build awareness", "anchor": "Build awareness", "location": "L1"}]}}


def test_coverage_exposes_lost_objective_and_accepts_question_destination():
    b = brief()
    assert quality.coverage(b, extracts())[0]["destinations"] == ["objectives[0]"]
    b["objectives"] = []
    assert quality.coverage(b, extracts())[0]["destinations"] == []
    b["open_questions"] = [{"field": "objectives", "linked_evidence": [evidence()]}]
    assert quality.coverage(b, extracts())[0]["destinations"] == ["open_questions[0]"]


def test_coverage_does_not_accept_same_anchor_from_another_source_or_field():
    b = brief()
    b["objectives"][0]["evidence"][0]["source_id"] = "email"
    assert not quality.coverage(b, extracts())[0]["destinations"]
    b = brief()
    b["mandatories"] = b.pop("objectives")
    assert not quality.coverage(b, extracts())[0]["destinations"]


def test_internal_conflict_positions_are_accounted_for():
    e = {
        "rfp": {
            "internal_conflicts": [
                {
                    "field": "timeline",
                    "value_a": {"value": "June", "anchor": "June", "location": "L1"},
                    "value_b": {"value": "July", "anchor": "July", "location": "L2"},
                }
            ]
        }
    }
    assert len(quality.coverage(brief(), e)) == 2


def test_question_grouping_merges_evidence_but_not_every_question_in_a_field():
    b = brief()
    b["open_questions"] = [
        {
            "field": "budget",
            "suggested_question_for_client": "What is the media budget?",
            "linked_evidence": [evidence()],
        },
        {
            "field": "budget",
            "suggested_question_for_client": "What is the media budget?",
            "linked_evidence": [evidence("email")],
        },
        {"field": "budget", "suggested_question_for_client": "Who approves production costs?"},
    ]
    q = clarifications.queue(b)
    assert len(q) == 2
    assert len(q[0]["evidence"]) == 2
    assert q[0]["member_indexes"] == [0, 1]


def test_question_answer_requires_attribution_and_does_not_edit_brief(tmp_path):
    b = brief()
    b["open_questions"] = [{"field": "budget", "suggested_question_for_client": "Budget?"}]
    original = copy.deepcopy(b)
    q = clarifications.queue(b)
    with pytest.raises(ValueError):
        clarifications.record(tmp_path, q, q[0]["id"], "answered", "", "20", "rfp L1", "account", "blocking")
    clarifications.record(tmp_path, q, q[0]["id"], "answered", "Lead", "20", "rfp L1", "account", "blocking")
    assert b == original
    assert (
        clarifications.queue(b, json.loads((tmp_path / "clarifications.json").read_text()))[0]["decision"]["actor"]
        == "Lead"
    )


def test_fingerprint_changes_for_render_but_not_generated_report(tmp_path):
    (tmp_path / "brief.json").write_text(json.dumps(brief()))
    (tmp_path / "brief_en.md").write_text("Awareness")
    old = revisions.fingerprint(tmp_path)
    (tmp_path / "agency_audit.json").write_text("{}")
    assert revisions.fingerprint(tmp_path) == old
    (tmp_path / "brief_en.md").write_text("Conversion")
    assert revisions.fingerprint(tmp_path) != old


def test_approval_refuses_changed_content(tmp_path):
    (tmp_path / "brief.json").write_text(json.dumps(brief()))
    revisions.write_json(tmp_path / "approval.json", {"fingerprint": revisions.fingerprint(tmp_path), "actor": "Lead"})
    revisions.require_current_approval(tmp_path)
    (tmp_path / "brief.json").write_text("{}")
    with pytest.raises(ValueError, match="stale"):
        revisions.require_current_approval(tmp_path)


def test_input_change_refuses_resume_before_mutating_outputs(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    source = tmp_path / "rfp.md"
    source.write_text("one")
    revisions.prepare_run(run, {"source": source}, "full")
    (run / "brief.json").write_text("{}")
    source.write_text("two")
    with pytest.raises(ValueError, match="new run"):
        revisions.prepare_run(run, {"source": source}, "render")
    assert (run / "brief.json").exists()


def test_client_pack_rejects_expired_or_unsourced_claims():
    pack = {
        "client_id": "synthetic",
        "version": "1",
        "approved_by": "Lead",
        "review_due": "2000-01-01",
        "items": [{"kind": "tone", "text": "Plain", "source": ""}],
    }
    problems = client_pack.validate(pack, "synthetic")
    assert any("expired" in p for p in problems)
    assert any("source" in p for p in problems)
    assert client_pack.validate(pack, "another")


def test_handover_cannot_mix_spec_values_from_different_rows():
    specs = {
        "specs": [
            {
                "id": "portrait",
                "resolution": "1080x1920",
                "aspect_ratio": "9:16",
                "format": "MP4",
                "duration_seconds": {"min": 9, "max": 60},
            }
        ]
    }
    row = {
        "id": "a",
        "spec_id": "portrait",
        "resolution": "1920x1080",
        "aspect_ratio": "9:16",
        "format": "MP4",
        "duration_seconds": 100,
        "quantity": 1,
        "languages": ["el"],
        "deadline": "2026-12-01",
        "owner": "Production",
        "approval_owner": "Lead",
        "dependencies": [],
        "evidence": [evidence()],
    }
    problems = handover.validate([row], specs, brief())
    assert any("resolution" in p for p in problems)
    assert any("duration" in p for p in problems)

"""The deterministic half of the pipeline — the part a reviewer can check by hand."""

import pytest

from pipeline import gates


# --------------------------------------------------------------------------------------
# Input contract
# --------------------------------------------------------------------------------------


def test_discover_sources_reads_the_fixture_project(fixture_project):
    sources = gates.discover_sources(fixture_project)
    assert {s.source_type for s in sources} == {"transcript", "rfp", "email_thread", "background"}
    assert all(s.source_id and s.source_date and s.text for s in sources)


def test_discover_sources_never_opens_the_answer_key(fixture_project):
    """The exam is harness-only (CLAUDE.md rule 2) — structurally unreachable from a run."""
    sources = gates.discover_sources(fixture_project)
    assert (fixture_project / "answer_key.json").is_file()
    assert all(p.name not in gates.HARNESS_ONLY_FILES for p in (s.path for s in sources))


def test_undeclared_file_is_refused_not_guessed(tmp_path):
    (tmp_path / "mystery.md").write_text("# something\n\nno header here\n", encoding="utf-8")
    with pytest.raises(gates.InputContractError, match="source header missing"):
        gates.discover_sources(tmp_path)


def test_unknown_source_type_is_refused(tmp_path):
    (tmp_path / "odd.md").write_text(
        "# X\nsource_id: x · source_type: whiteboard_photo · source_date: 2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(gates.InputContractError, match="not one of"):
        gates.discover_sources(tmp_path)


def test_duplicate_source_ids_are_refused(tmp_path):
    header = "source_id: dup · source_type: rfp · source_date: 2026-01-01\n"
    (tmp_path / "a.md").write_text("# A\n" + header, encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n" + header, encoding="utf-8")
    with pytest.raises(gates.InputContractError, match="duplicate source_id"):
        gates.discover_sources(tmp_path)


# --------------------------------------------------------------------------------------
# Step 1 — readiness gate
# --------------------------------------------------------------------------------------


def test_readiness_gate_passes_on_the_full_fixture(fixture_project):
    verdict = gates.readiness_gate(gates.discover_sources(fixture_project))
    assert verdict.ok, verdict.message
    assert verdict.missing_required == [] and verdict.missing_signals == []


def test_readiness_gate_refuses_without_a_corroborating_source(tmp_path):
    (tmp_path / "rfp.md").write_text(
        "# RFP\nsource_id: r · source_type: rfp · source_date: 2026-01-01\n"
        "Budget €50.000. Launch October 2026.\n",
        encoding="utf-8",
    )
    verdict = gates.readiness_gate(gates.discover_sources(tmp_path))
    assert not verdict.ok
    assert "insufficient input" in verdict.message


def test_readiness_gate_refuses_without_budget_or_timeline_signal(tmp_path):
    (tmp_path / "rfp.md").write_text(
        "# RFP\nsource_id: r · source_type: rfp · source_date: 2026-01-01\nΘέλουμε καμπάνια.\n",
        encoding="utf-8",
    )
    (tmp_path / "t.md").write_text(
        "# Kickoff\nsource_id: t · source_type: transcript · source_date: 2026-01-02\n"
        "[00:01:00] A: Καλημέρα.\n",
        encoding="utf-8",
    )
    verdict = gates.readiness_gate(gates.discover_sources(tmp_path))
    assert not verdict.ok
    assert verdict.missing_signals == ["budget", "timeline"]
    assert "insufficient input" in verdict.message


# --------------------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["S0", "S1"])
def test_permitted_tiers_pass(tier):
    assert gates.enforce_sensitivity_tier(tier) == tier


@pytest.mark.parametrize("tier", ["S2", "S3", "s1", None, ""])
def test_regulated_and_malformed_tiers_are_refused(tier):
    with pytest.raises(gates.ScopeError):
        gates.enforce_sensitivity_tier(tier)


# --------------------------------------------------------------------------------------
# Schema validation + citation completeness
# --------------------------------------------------------------------------------------


def _item(**overrides):
    item = {
        "value": "grow awareness",
        "lang": "en",
        "location": "[00:02:05]",
        "anchor": "grow awareness",
        "speaker_or_author": "Client CMO",
        "qualifier": "stated",
        "confidence": "high",
    }
    item.update(overrides)
    return item


def _extract(**overrides):
    extract = {
        "meta": {
            "project_id": "p",
            "source_id": "s",
            "source_type": "transcript",
            "source_date": "2026-07-10",
            "extraction_ts": "2026-07-24T10:00:00",
            "agent_version": "1.0",
        },
        "objectives": [_item()],
        "audiences": [],
        "key_messages": [],
        "deliverables": [],
        "timeline": [],
        "budget": [],
        "mandatories": [],
        "open_questions": [],
        "internal_conflicts": [],
        "extraction_notes": [],
    }
    extract.update(overrides)
    return extract


def test_valid_extract_passes():
    gates.validate_extract(_extract())


def test_extract_without_anchor_fails_schema():
    with pytest.raises(gates.SchemaValidationError, match="anchor"):
        gates.validate_extract(_extract(objectives=[_item(anchor="")]))


def test_find_uncited_items_names_the_offender():
    violations = gates.find_uncited_items(_extract(budget=[_item(location="  ")]))
    assert len(violations) == 1 and "budget[0]" in violations[0]


def test_brief_rejects_regulated_tier():
    brief = _brief()
    brief["meta"]["sensitivity_tier"] = "S3"
    with pytest.raises(gates.SchemaValidationError, match="sensitivity_tier"):
        gates.validate_brief(brief)


def _entry(confidence="high", evidence=True):
    return {
        "content": "Grow brand awareness for the new category.",
        "evidence": [
            {
                "source_id": "transcript_kickoff",
                "location": "[00:02:05]",
                "anchor": "καινούργια κατηγορία",
                "speaker_or_author": "Client CMO",
            }
        ]
        if evidence
        else [],
        "confidence": confidence,
        "qualifier": "stated",
    }


def _brief(**overrides):
    brief = {
        "meta": {
            "project_id": "northlight_01",
            "client_id": "meltemi_beverages",
            "project_type": "advertising_creative",
            "classification_confidence": "high",
            "sensitivity_tier": "S1",
            "sources": [{"source_id": "s", "source_type": "rfp", "source_date": "2026-06-28"}],
            "created_ts": "2026-07-24T10:00:00",
            "pipeline_version": "0.1.0-tier0",
        },
        "objectives": [_entry()],
        "audiences": [],
        "key_messages": [],
        "deliverables": [],
        "timeline": [],
        "budget": [],
        "mandatories": [],
        "open_questions": [],
        "conflicts": [],
        "readiness": {
            "fields_with_evidence": 1,
            "low_confidence_share": 0.0,
            "open_question_count": 0,
            "verdict": "thin_input_return_to_client",
        },
        "signoff": {"status": "draft"},
    }
    brief.update(overrides)
    return brief


def test_valid_brief_passes():
    gates.validate_brief(_brief())


# --------------------------------------------------------------------------------------
# The readiness block — the value the harness will recompute and compare
# --------------------------------------------------------------------------------------


def test_readiness_block_counts_only_evidenced_fields():
    brief = _brief(objectives=[_entry()], audiences=[_entry(evidence=False)])
    block = gates.compute_readiness_block(brief)
    assert block["fields_with_evidence"] == 1


def test_readiness_block_flags_thin_input():
    block = gates.compute_readiness_block(_brief())
    assert block["verdict"] == "thin_input_return_to_client"


def test_readiness_block_is_ready_when_coverage_and_confidence_hold():
    brief = _brief(**{f: [_entry()] for f in gates.BRIEF_FIELDS})
    block = gates.compute_readiness_block(brief)
    assert block["fields_with_evidence"] == 7
    assert block["low_confidence_share"] == 0.0
    assert block["verdict"] == "ready_for_review"


def test_readiness_block_low_confidence_share_forces_return_to_client():
    """Full coverage is not readiness if the coverage is mostly inference."""
    brief = _brief(**{f: [_entry(confidence="low")] for f in gates.BRIEF_FIELDS})
    block = gates.compute_readiness_block(brief)
    assert block["low_confidence_share"] == 1.0
    assert block["verdict"] == "thin_input_return_to_client"


def test_readiness_block_is_pure():
    """Same input, same output — the harness recomputes it and compares (Tier-2 DoD)."""
    brief = _brief(**{f: [_entry(), _entry(confidence="low")] for f in gates.BRIEF_FIELDS})
    assert gates.compute_readiness_block(brief) == gates.compute_readiness_block(brief)
    assert gates.compute_readiness_block(brief)["low_confidence_share"] == 0.5

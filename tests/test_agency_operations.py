import pytest
from conftest import approve_synthetic, make_review_run

from eval import pilot_scorecard
from pipeline import agency, client_pack, gates, handover, revisions


def test_campaign_missing_kpi_is_explicit_not_filled_from_other_fields():
    b = {"objectives": [{"evidence": [{"source_id": "rfp", "location": "L1", "anchor": "awareness"}]}]}
    problems = agency.campaign_check({"campaign_profile": "paid_campaign", "checklist": {}}, b)
    assert any("conversion_and_kpi" in p for p in problems)


def test_client_reference_roundtrips_through_source_discovery(tmp_path):
    pack = {
        "client_id": "synthetic",
        "version": "1",
        "approved_by": "Lead",
        "review_due": "2099-01-01",
        "items": [{"kind": "tone", "text": "Plain language", "source": "Brand book section 2"}],
    }
    client_pack.materialize(pack, "synthetic", tmp_path / "reference.md")
    docs = gates.discover_sources(tmp_path)
    assert docs[0].source_type == "background"
    assert "Plain language" in docs[0].text


def test_spec_duration_and_file_type_use_existing_table_contract():
    spec = {
        "specs": [
            {
                "id": "a",
                "format": "Story",
                "file_type": "MP4",
                "resolution": "1080x1920",
                "aspect_ratio": "9:16",
                "duration": "up to 60s",
            }
        ]
    }
    row = {
        "id": "d",
        "spec_id": "a",
        "format": "Story",
        "file_type": "JPG",
        "resolution": "1080x1920",
        "aspect_ratio": "9:16",
        "duration_seconds": 90,
        "quantity": 1,
        "languages": ["el"],
        "deadline": "2026-12-01",
        "owner": "P",
        "approval_owner": "A",
        "dependencies": [],
        "evidence": [{"source_id": "r", "location": "L1", "anchor": "video"}],
    }
    b = {"deliverables": [{"evidence": row["evidence"]}]}
    errors = handover.validate([row], spec, b)
    assert any("file_type" in e for e in errors)
    assert any("duration" in e for e in errors)


def test_metrics_exclude_example_rows_and_keep_missing_distinct():
    rows = [
        {"row_type": "EXAMPLE", "assembly_min": "999"},
        {
            "row_type": "PILOT",
            "brief_id": "a",
            "assembly_min": "10",
            "review_min": "20",
            "total_attention_min": "30",
            "oq_total": "2",
            "oq_real": "1",
            "oq_duplicate": "1",
            "oq_answered_in_sources": "0",
            "oq_not_worth_asking": "0",
            "creative_rework_requests_q1": "not_recorded",
        },
    ]
    result = pilot_scorecard.summarize(rows)
    assert result["briefs"] == 1
    assert result["metrics"]["total_attention_min"]["mean"] == 30
    assert result["question_precision_pct"] == 50
    assert result["metrics"]["creative_rework_requests_q1"]["mean"] is None


def test_metrics_reject_inconsistent_counts_and_negative_minutes():
    with pytest.raises(ValueError, match="question"):
        pilot_scorecard.summarize(
            [
                {
                    "row_type": "PILOT",
                    "oq_total": "2",
                    "oq_real": "3",
                    "oq_duplicate": "0",
                    "oq_answered_in_sources": "0",
                    "oq_not_worth_asking": "0",
                }
            ]
        )
    with pytest.raises(ValueError):
        pilot_scorecard.summarize([{"row_type": "PILOT", "review_min": "-1"}])


def test_exactly_30_minutes_does_not_pass_under_30_target():
    report = pilot_scorecard.summarize([{"row_type": "PILOT", "review_min": "30"}])
    assert report["review_under_30"] is False


def test_human_review_approval_handover_then_edit_invalidates(tmp_path):
    run = make_review_run(tmp_path)
    assert agency.audit(run)['status'] == 'blocked'
    assert (
        agency.main(
            [
                'attest',
                str(run),
                '--actor',
                'Synthetic reviewer',
                '--greek-register',
                '4',
                '--notes',
                'Synthetic test attestation',
                '--checks',
                *agency.quality.field_review_checklist(),
            ]
        )
        == 0
    )
    assert agency.audit(run)['blockers'] == []
    assert agency.main(['approve', str(run), '--actor', 'Synthetic lead', '--summary', 'Synthetic test only']) == 0
    assert agency.main(['handover', str(run)]) == 0
    assert revisions.load(run / 'handover.json')['mode'] == 'APPROVED BRIEF HANDOVER'
    (run / 'brief_en.md').write_text('Changed')
    assert agency.main(['handover', str(run)]) == 2


def test_answer_log_does_not_masquerade_as_updated_brief(tmp_path):
    run = make_review_run(tmp_path)
    b = revisions.load(run / 'brief.json')
    b['open_questions'] = [
        {'field': 'budget', 'gap': 'Unknown', 'why_it_matters': 'Planning', 'suggested_question_for_client': 'Budget?'}
    ]
    revisions.write_json(run / 'brief.json', b)
    q = agency.clarifications.queue(b)
    agency.clarifications.record(
        run, q, q[0]['id'], 'answered', 'Lead', 'Synthetic response', 'Email L1', 'Account', 'blocking'
    )
    assert any('update sources/brief' in p for p in agency.audit(run)['blockers'])


def test_resolve_records_human_and_invalidates_renders(tmp_path):
    run = make_review_run(tmp_path)
    b = revisions.load(run / 'brief.json')
    ref = b['objectives'][0]['evidence'][0]
    b['conflicts'] = [
        {
            'field': 'timeline',
            'positions': [{'statement': 'June', 'evidence': ref}, {'statement': 'July', 'evidence': ref}],
            'status': 'open',
        }
    ]
    revisions.write_json(run / 'brief.json', b)
    agency.resolve(run, 0, 'Synthetic lead', 'Use July; synthetic decision')
    changed = revisions.load(run / 'brief.json')
    assert changed['conflicts'][0]['resolved_by'] == 'Synthetic lead'
    assert changed['signoff']['status'] == 'draft'
    assert not (run / 'brief_en.md').exists()
    assert list((run / 'history').glob('*/brief_en.md'))


def test_survival_measures_insertions_and_substitutions():
    assert pilot_scorecard.survival('brief', 'brief') == 100
    assert pilot_scorecard.survival('brief', 'grief') == 80
    assert pilot_scorecard.survival('a', 'bbb') == 0


def test_apply_validated_human_changes_preserves_identity_and_resets_signoff(tmp_path):
    run = make_review_run(tmp_path)
    candidate = revisions.load(run / 'brief.json')
    candidate['objectives'][0]['content'] = 'Revised synthetic campaign'
    path = tmp_path / 'candidate.json'
    revisions.write_json(path, candidate)
    assert (
        agency.main(
            ['apply', str(run), '--candidate', str(path), '--actor', 'Synthetic lead', '--reason', 'Correct wording']
        )
        == 0
    )
    assert revisions.load(run / 'brief.json')['signoff']['status'] == 'draft'
    assert not (run / 'brief_en.md').exists()
    candidate['meta']['client_id'] = 'wrong-client'
    revisions.write_json(path, candidate)
    assert (
        agency.main(
            ['apply', str(run), '--candidate', str(path), '--actor', 'Synthetic lead', '--reason', 'Wrong client']
        )
        == 2
    )
    assert revisions.load(run / 'brief.json')['meta']['client_id'] == 'synthetic'


def test_render_question_requires_its_own_evidence_not_a_citation_elsewhere():
    b = {
        'open_questions': [
            {'field': 'budget', 'linked_evidence': [{'source_id': 'email', 'location': 'L1', 'anchor': 'uncertain'}]}
        ]
    }
    text = '## 1 Objectives\n- Something [email L1]\n## ⚠ Open questions\n1. What budget?\n'
    assert any('question' in p for p in agency.quality.render_coverage(b, text, 'en'))


def test_added_source_invalidates_approval(tmp_path):
    run = make_review_run(tmp_path)
    approve_synthetic(run)
    (tmp_path / 'extra.md').write_text(
        'source_id: extra · source_type: email_thread · source_date: 2026-09-20\nNew direction'
    )
    with pytest.raises(ValueError, match='source'):
        revisions.require_current_approval(run)


def test_withdrawn_attestation_invalidates_approval(tmp_path):
    run = make_review_run(tmp_path)
    approve_synthetic(run)
    revisions.write_json(run / 'language_review.json', {'checks': {}})
    with pytest.raises(ValueError):
        revisions.require_current_approval(run)


def test_reapproval_preserves_first_approval(tmp_path):
    run = make_review_run(tmp_path)
    approve_synthetic(run)
    agency.approve(run, 'Lead B', 'Second synthetic review')
    history = [revisions.load(p) for p in (run / 'history').glob('*/approval.json')]
    assert any(entry['actor'] == 'Lead A' for entry in history)


def test_extraction_resume_archives_previous_extracts(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    source = tmp_path / 'source.md'
    source.write_text('source')
    revisions.prepare_run(run, {'source:s': source}, 'full')
    revisions.write_json(run / 'extracts' / 's.json', {'objectives': ['original']})
    revisions.prepare_run(run, {'source:s': source}, 'extraction')
    assert any(revisions.load(p)['objectives'] == ['original'] for p in (run / 'history').glob('*/extracts/s.json'))

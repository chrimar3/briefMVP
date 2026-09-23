import pytest
from pipeline import revisions
from test_delivery import prepare_release
from test_agency_operations import make_review_run, approve_synthetic, vouch_forged


def test_status_uses_current_data_and_does_not_rewrite_reports(tmp_path):
    from pipeline import operations, delivery
    run = prepare_release(tmp_path)
    audit_before = (run/'agency_audit.json').read_bytes()
    assert operations.status(run)['stage'] == 'creative_review'
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    assert operations.status(run)['stage'] == 'ready_to_release'
    assert (run/'agency_audit.json').read_bytes() != audit_before  # approval audited once
    audit_after = (run/'agency_audit.json').read_bytes()
    operations.status(run)
    assert (run/'agency_audit.json').read_bytes() == audit_after
    brief = revisions.load(run/'brief.json')
    brief['objectives'][0]['content'] += ' changed'
    revisions.write_json(run/'brief.json', brief)
    assert operations.status(run)['stage'] == 'blocked'


def test_portfolio_keeps_errors_and_deduplicates_aliases(tmp_path):
    from pipeline import operations
    run = make_review_run(tmp_path)
    missing = tmp_path/'missing'
    result = operations.portfolio([run, run/'.', missing])
    assert len(result['projects']) == 2
    assert result['counts']['error'] == 1
    assert result['counts']['blocked'] == 1
    assert not missing.exists()


def test_withdrawn_approval_is_not_shown_as_ready(tmp_path):
    from pipeline import operations, release_control
    run = make_review_run(tmp_path)
    approve_synthetic(run)
    release_control.withdraw(run, 'Synthetic lead', 'Needs changes')
    result = operations.status(run)
    assert result['stage'] == 'brief_approval'
    assert result['withdrawals'] == 1


@pytest.mark.parametrize('timestamp', [None, 'not-a-date', '2026-09-20'])
def test_incomplete_creative_approval_never_reports_ready(tmp_path, timestamp):
    from pipeline import operations, delivery
    run = prepare_release(tmp_path)
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    record = revisions.load(run/'creative_approval.json')
    if timestamp is None:
        del record['approved_at']
    else:
        record['approved_at'] = timestamp
    revisions.write_json(run/'creative_approval.json', record)
    assert operations.status(run)['stage'] == 'blocked'          # unvouched hand edit
    with pytest.raises(ValueError, match='creative_approval.json is not vouched'):
        delivery.release(run, tmp_path/'bad', 'Synthetic releaser')
    vouch_forged(run, 'creative_approval.json', 'creative_approved')   # a forger who also writes the log
    assert operations.status(run)['stage'] == 'creative_review'
    with pytest.raises(ValueError, match='metadata'):
        delivery.release(run, tmp_path/'bad', 'Synthetic releaser')

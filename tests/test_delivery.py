"""Creative release contracts on synthetic evidence, no runtime model calls."""

import pytest
from conftest import SYNTHETIC_DRAFT, approve_synthetic, make_review_run, prepare_release, vouch_forged

from pipeline import delivery, revisions


def test_draft_fact_references_reject_unknown_entry_and_missing_mandatory():
    brief = {
        'objectives': [{'content': 'Awareness', 'qualifier': 'stated'}],
        'mandatories': [{'content': 'No health claims', 'qualifier': 'stated'}],
    }
    errors, claims = delivery.inspect_creative('> CREATIVE DRAFT\nAwareness [brief:objectives:9]', brief)
    assert any('reference' in e for e in errors)
    assert any('mandatory' in e for e in errors)
    errors, claims = delivery.inspect_creative(
        '> CREATIVE DRAFT\nAwareness [brief:objectives:0]\nNo health claims [brief:mandatories:0]', brief
    )
    assert not errors
    assert len(claims) == 2


def test_run_lock_refuses_second_operator_and_releases_after_error(tmp_path):
    with revisions.run_lock(tmp_path):
        with pytest.raises(ValueError, match='busy'):
            with revisions.run_lock(tmp_path):
                pass
    with pytest.raises(RuntimeError):
        with revisions.run_lock(tmp_path):
            raise RuntimeError('test')
    with revisions.run_lock(tmp_path):
        pass


def test_evidence_copy_preserves_original_and_detects_tampering(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    source = tmp_path / 'source.md'
    source.write_text('Original')
    revisions.capture_evidence(run, {'source:s': source})
    state = revisions.load(run / 'evidence_index.json')
    preserved = run / state['source:s']['file']
    source.write_text('Changed')
    assert preserved.read_text() == 'Original'
    revisions.verify_evidence(run)
    preserved.write_text('Tampered')
    with pytest.raises(ValueError, match='evidence'):
        revisions.verify_evidence(run)


def test_decision_carry_forward_requires_same_identity_and_same_evidence(tmp_path):
    old, new = tmp_path/'old', tmp_path/'new'
    old.mkdir()
    new.mkdir()
    q = {
        'field': 'budget',
        'suggested_question_for_client': 'Who approves?',
        'linked_evidence': [{'source_id': 'rfp', 'location': 'L1', 'anchor': 'Name unknown'}],
    }
    b={'meta':{'client_id':'synthetic','project_id':'one'},'open_questions':[q]}
    for path in (old,new):
        revisions.write_json(path/'brief.json',b)
        revisions.write_json(path/'input_snapshot.json',{'source:rfp':{'sha256':'unchanged','path':'unused'}})
    from pipeline import clarifications
    item=clarifications.queue(b)[0]
    clarifications.record(old,[item],item['id'],'open','Lead','Can wait','', 'Account','nonblocking')
    revisions.carry_decisions(old,new,'Operator')
    assert item['id'] in revisions.load(new/'clarifications.json')
    b['meta']['project_id']='other'
    revisions.write_json(new/'brief.json',b)
    with pytest.raises(ValueError, match='identity'):
        revisions.carry_decisions(old,new,'Operator')


def test_full_release_is_curated_and_approval_bound(tmp_path):
    run=prepare_release(tmp_path)
    output=tmp_path/'released'
    with pytest.raises(ValueError,match='approval'):
        delivery.release(run,output, 'Synthetic releaser')
    delivery.approve(run,'Synthetic creative lead','Reviewed fixture only',delivery.CHECKS)
    delivery.release(run,output, 'Synthetic releaser')
    assert {p.name for p in output.iterdir()} == {'creative.md','deliverables.json','release.json'}
    assert 'SHADOW' not in (output/'creative.md').read_text()
    assert '[brief:' not in (output/'creative.md').read_text()
    manifest=revisions.load(output/'release.json')
    assert manifest['status']=='APPROVED FOR DELIVERY'
    assert all(revisions.file_hash(output/name)==hash for name,hash in manifest['files'].items())
    with pytest.raises(ValueError,match='new directory'):
        delivery.release(run,output, 'Synthetic releaser')
    registered=revisions.load(run/'creative_draft.json')
    (run/registered['files'][0]['file']).write_text('Changed after approval')
    with pytest.raises(ValueError,match='changed'):
        delivery.release(run,tmp_path/'bad', 'Synthetic releaser')


@pytest.mark.parametrize('extra, reason', [
    ('A Greek-made drink, new to the market [brief:objectives:0]\n', 'origin/market claim'),
    ('Reviewed by a creative lead before sending.\n', 'human review'),
])
def test_approval_runs_the_fact_checks_against_the_signed_brief(tmp_path, extra, reason):
    """Approval re-checks the exact registered draft against the signed brief (W4 fact checks), so
    an invented figure or a self-claimed review cannot be approved even if it slipped past the
    generating stage (for example a draft registered by hand)."""
    run=prepare_release(tmp_path, draft_text=SYNTHETIC_DRAFT + extra)
    with pytest.raises(ValueError, match=reason):
        delivery.approve(run,'Synthetic creative lead','Reviewed fixture only',delivery.CHECKS)
    assert not (run/'creative_approval.json').exists()


def test_approval_requires_the_strategic_tensions_section(tmp_path):
    run=prepare_release(tmp_path, draft_text=SYNTHETIC_DRAFT.split('\n## Strategic')[0] + '\n')
    with pytest.raises(ValueError, match='Strategic tensions'):
        delivery.approve(run,'Synthetic creative lead','Reviewed fixture only',delivery.CHECKS)


def test_stub_catalog_blocks_creative_approval(tmp_path):
    run=make_review_run(tmp_path)
    approve_synthetic(run)
    draft=tmp_path/'draft.txt'
    draft.write_text(SYNTHETIC_DRAFT)
    delivery.register(run,draft,'Synthetic operator')
    with pytest.raises(ValueError,match='stub'):
        delivery.approve(run,'Synthetic lead','Review',delivery.CHECKS)


def test_stale_brief_or_revoked_language_review_blocks_release(tmp_path):
    run=prepare_release(tmp_path)
    delivery.approve(run,'Synthetic lead','Review',delivery.CHECKS)
    revisions.write_json(run/'language_review.json',{'checks':{}})
    with pytest.raises(ValueError,match='review'):
        delivery.release(run,tmp_path/'bad', 'Synthetic releaser')


def test_catalog_rebinding_allows_changed_specs_but_invalidates_review(tmp_path):
    from pipeline import spec_catalog
    run=make_review_run(tmp_path)
    row=dict(revisions.load(run/'agency_inputs.json')['deliverables'][0])
    row.update(
        id=row['spec_id'],
        resolution='1000x1000',
        source_url='https://specs.example.invalid/test',
        checked_by='Synthetic traffic',
        checked_on='2020-01-01',
        review_due='2099-01-01',
    )
    path = tmp_path/'spec.json'
    revisions.write_json(path, {'owner': 'Synthetic traffic', 'specs': [row]})
    spec_catalog.bind(run,path,actor='Synthetic traffic')
    from pipeline import agency
    assert any('resolution' in e for e in agency.audit(run)['blockers'])
    assert revisions.load(run/'agency_inputs.json')['catalog_binding']['recheck_deliverables']


def test_publisher_refuses_busy_run(tmp_path):
    from pipeline import publish
    run = tmp_path/'run'
    run.mkdir()
    (run/'brief_review.html').write_text('<p>synthetic</p>')
    with revisions.run_lock(run):
        with pytest.raises(ValueError,match='busy'):
            publish.publish_run(run,tmp_path/'shelf')


def test_registered_manifest_cannot_escape_delivery_folder(tmp_path):
    run=prepare_release(tmp_path)
    record=revisions.load(run/'creative_draft.json')
    record['files'][0]['name']='../escape.md'
    revisions.write_json(run/'creative_draft.json',record)
    with pytest.raises(ValueError,match='creative_draft.json is not vouched'):
        delivery.approve(run,'Synthetic lead','Review',delivery.CHECKS)
    vouch_forged(run,'creative_draft.json','creative_registered')   # a forger who also writes the log
    with pytest.raises(ValueError,match='filename'):
        delivery.approve(run,'Synthetic lead','Review',delivery.CHECKS)


def test_decision_carry_does_not_reuse_triage_after_source_changes(tmp_path):
    from pipeline import clarifications
    old, new = tmp_path/'old', tmp_path/'new'
    old.mkdir()
    new.mkdir()
    q = {
        'field': 'budget',
        'gap': 'Unknown approver',
        'why_it_matters': 'Approval',
        'suggested_question_for_client': 'Who approves?',
        'linked_evidence': [{'source_id': 'rfp', 'location': 'L1', 'anchor': 'Name unknown'}],
    }
    b={'meta':{'client_id':'synthetic','project_id':'one'},'open_questions':[q]}
    for path,sha in ((old,'before'),(new,'after')):
        revisions.write_json(path/'brief.json',b)
        revisions.write_json(path/'input_snapshot.json',{'source:rfp':{'sha256':sha,'path':'unused'}})
    item=clarifications.queue(b)[0]
    clarifications.record(old,[item],item['id'],'open','Lead','Can wait','','Account','nonblocking')
    result=revisions.carry_decisions(old,new,'Operator')
    assert result['carried']==[]
    assert result['needs_review']==[item['id']]


def test_manifest_cannot_substitute_raw_evidence_as_artwork(tmp_path):
    run = prepare_release(tmp_path)
    record = revisions.load(run/'creative_draft.json')
    evidence = next(iter(revisions.load(run/'evidence_index.json').values()))
    record['files'].append({'name': 'artwork.pdf', 'file': evidence['file'], 'sha256': evidence['sha256']})
    revisions.write_json(run/'creative_draft.json', record)
    with pytest.raises(ValueError, match='creative_draft.json is not vouched'):
        delivery.approve(run, 'Synthetic lead', 'Review', delivery.CHECKS)
    vouch_forged(run, 'creative_draft.json', 'creative_registered')
    with pytest.raises(ValueError, match='revision'):
        delivery.approve(run, 'Synthetic lead', 'Review', delivery.CHECKS)
    assert not (run/'creative_approval.json').exists()


def test_manifest_revision_must_match_registered_payloads(tmp_path):
    run = prepare_release(tmp_path)
    record = revisions.load(run/'creative_draft.json')
    root = run/'creative_versions'/record['revision']
    asset = root/'artwork.pdf'
    asset.write_bytes(b'Synthetic artwork')
    record['files'].append(
        {'name': 'artwork.pdf', 'file': str(asset.relative_to(run)), 'sha256': revisions.file_hash(asset)}
    )
    revisions.write_json(run/'creative_draft.json', record)
    with pytest.raises(ValueError, match='creative_draft.json is not vouched'):
        delivery.approve(run, 'Synthetic lead', 'Review', delivery.CHECKS)
    vouch_forged(run, 'creative_draft.json', 'creative_registered')
    with pytest.raises(ValueError, match='revision'):
        delivery.approve(run, 'Synthetic lead', 'Review', delivery.CHECKS)


def test_withdrawal_blocks_release_and_marks_existing_package(tmp_path):
    from pipeline import release_control
    run = prepare_release(tmp_path)
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    output = delivery.release(run, tmp_path/'released', 'Synthetic releaser')
    assert release_control.verify(output, run)['valid']
    result = release_control.withdraw(run, 'Synthetic lead', 'Wrong campaign selected')
    assert len(result['affected_releases']) == 1
    assert (output/'release.json').exists()
    assert not release_control.verify(output, run)['valid']
    with pytest.raises(ValueError, match='approval'):
        delivery.release(run, tmp_path/'again', 'Synthetic releaser')
    assert revisions.load(run/'approval_withdrawals.json')[0]['reason'] == 'Wrong campaign selected'


@pytest.mark.parametrize('change', ['extra', 'changed', 'missing', 'path'])
def test_release_verifier_detects_package_changes(tmp_path, change):
    from pipeline import release_control
    run = prepare_release(tmp_path)
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    output = delivery.release(run, tmp_path/'released', 'Synthetic releaser')
    if change == 'extra':
        (output/'internal.md').write_text('Not approved')
    elif change == 'changed':
        (output/'creative.md').write_text('Different')
    elif change == 'missing':
        (output/'creative.md').unlink()
    else:
        data = revisions.load(output/'release.json')
        data['files']['../outside'] = '0'*64
        revisions.write_json(output/'release.json', data)
    assert not release_control.verify(output, run)['valid']


def test_withdrawal_of_release_survives_catalog_rebind(tmp_path):
    from pipeline import release_control, spec_catalog
    run = prepare_release(tmp_path)
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    output = delivery.release(run, tmp_path/'released', 'Synthetic releaser')
    spec_catalog.bind(run, tmp_path/'catalog.json', actor='Synthetic traffic')
    assert not (run/'approval.json').exists()
    assert not (run/'creative_approval.json').exists()
    release_control.withdraw(run, 'Synthetic lead', 'Withdraw earlier package')
    assert release_control.verify(output, run)['withdrawn']


def test_interrupted_withdrawal_allows_fresh_human_reapproval(tmp_path, monkeypatch):
    from pipeline import release_control
    run = prepare_release(tmp_path)
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    def fail_archive(*args, **kwargs):
        raise OSError('simulated interruption')
    with monkeypatch.context() as m:
        m.setattr(revisions, 'archive', fail_archive)
        with pytest.raises(OSError):
            release_control.withdraw(run, 'Synthetic lead', 'Correct campaign')
    with pytest.raises(ValueError, match='withdrawn'):
        delivery.release(run, tmp_path/'not-allowed', 'Synthetic releaser')
    approve_synthetic(run)
    delivery.register(run, tmp_path/'draft.txt', 'Synthetic operator')
    delivery.approve(run, 'Synthetic lead', 'Fresh human review', delivery.CHECKS)
    assert delivery.release(run, tmp_path/'fresh', 'Synthetic releaser').is_dir()

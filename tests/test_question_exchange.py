"""Synthetic clarification exchange; no models, external data or canonical edits."""
import copy
import json
from pathlib import Path

import pytest

from pipeline import clarifications, gates, question_exchange as exchange, revisions
from test_agency_operations import make_review_run


@pytest.fixture
def run(tmp_path):
    run = make_review_run(tmp_path)
    brief = revisions.load(run / 'brief.json')
    ref = brief['objectives'][0]['evidence'][0]
    brief['open_questions'] = [
        {'field': 'budget', 'gap': 'Synthetic gap', 'why_it_matters': 'Planning',
         'suggested_question_for_client': 'Synthetic budget?', 'linked_evidence': [ref]},
        {'field': 'timeline', 'gap': 'Synthetic gap', 'why_it_matters': 'Planning',
         'suggested_question_for_client': 'Synthetic deadline?', 'linked_evidence': [ref]}]
    brief['readiness'] = gates.compute_readiness_block(brief)
    revisions.write_json(run / 'brief.json', brief)
    for item in clarifications.queue(brief):
        clarifications.record(run, clarifications.queue(brief), item['id'], 'open',
                              'Synthetic lead', 'Needs reply', '', 'Synthetic account', 'blocking')
    return run


def exported(run, tmp_path):
    path = tmp_path / 'questions.json'
    return path, exchange.export_questions(run, path)


def replies(pack, ids=None):
    return {'pack_id': pack['pack_id'], 'replies': [
        {'question_id': q['id'], 'text': 'Synthetic proposed answer',
         'evidence': {'source_ref': 'Synthetic reply note section 1', 'provided_by': 'Synthetic respondent'}}
        for q in pack['questions'] if ids is None or q['id'] in ids]}


def protected(run):
    return {name: (run / name).read_bytes() for name in
            ('brief.json', 'clarifications.json', 'agency_inputs.json', 'input_snapshot.json', 'approval.json')
            if (run / name).exists()}


def test_export_original_ids_owner_priority_without_evidence(run, tmp_path):
    path, pack = exported(run, tmp_path)
    assert revisions.load(path) == pack
    assert [q['id'] for q in pack['questions']] == [q['id'] for q in clarifications.queue(revisions.load(run / 'brief.json'))]
    assert pack['fingerprint'] == revisions.fingerprint(run)
    assert all(q['owner'] == 'Synthetic account' and q['priority'] == 'blocking' for q in pack['questions'])
    assert all(set(q) == {'id', 'field', 'question', 'owner', 'priority'} for q in pack['questions'])
    serialized = json.dumps(pack)
    assert 'linked_evidence' not in serialized and 'anchor' not in serialized
    assert 'Synthetic campaign' not in serialized
    with pytest.raises(ValueError, match='exist|overwrite'):
        exchange.export_questions(run, path)
    assert revisions.load(path) == pack


def test_selection_and_unresolved_only(run, tmp_path):
    items = clarifications.queue(revisions.load(run / 'brief.json'))
    clarifications.record(run, items, items[0]['id'], 'answered', 'Lead', 'Synthetic reply',
                          'Synthetic note', 'Account', 'blocking')
    pack = exchange.export_questions(run, tmp_path / 'selected.json', question_ids=[items[1]['id']])
    assert [q['id'] for q in pack['questions']] == [items[1]['id']]
    with pytest.raises(ValueError):
        exchange.export_questions(run, tmp_path / 'bad.json', question_ids=[items[0]['id']])


def test_unassigned_question_refused(run, tmp_path):
    (run / 'clarifications.json').unlink()
    with pytest.raises(ValueError, match='owner|triage'):
        exchange.export_questions(run, tmp_path / 'questions.json')


def test_partial_import_is_proposal_and_preserves_approval(run, tmp_path):
    revisions.write_json(run / 'approval.json', {'actor': 'Synthetic approver', 'fingerprint': revisions.fingerprint(run)})
    path, pack = exported(run, tmp_path)
    before = protected(run)
    first = exchange.import_replies(run, path, replies(pack, [pack['questions'][0]['id']]), 'Synthetic importer')
    assert first['status'] == 'proposed' and first['actor'] == 'Synthetic importer'
    assert len(first['pending_question_ids']) == 1
    assert protected(run) == before
    assert revisions.fingerprint(run) == pack['fingerprint']
    with pytest.raises(ValueError, match='duplicate|already'):
        exchange.import_replies(run, path, replies(pack, [pack['questions'][0]['id']]), 'Other importer')
    second = exchange.import_replies(run, path, replies(pack, [pack['questions'][1]['id']]), 'Synthetic importer')
    assert second['pending_question_ids'] == []
    assert len(list((run / 'question_exchange' / 'proposals').glob('*.json'))) == 2
    assert protected(run) == before


@pytest.mark.parametrize('fault', ['unknown', 'duplicate', 'wrong_pack', 'blank_actor', 'no_attribution', 'empty', 'approval_field'])
def test_invalid_batch_writes_nothing(run, tmp_path, fault):
    path, pack = exported(run, tmp_path)
    batch = replies(pack)
    actor = 'Synthetic importer'
    if fault == 'unknown':
        batch['replies'][1]['question_id'] = 'unknown'
    elif fault == 'duplicate':
        batch['replies'].append(copy.deepcopy(batch['replies'][0]))
    elif fault == 'wrong_pack':
        batch['pack_id'] = 'wrong'
    elif fault == 'blank_actor':
        actor = ' '
    elif fault == 'no_attribution':
        batch['replies'][1]['evidence']['provided_by'] = ''
    elif fault == 'empty':
        batch['replies'] = []
    elif fault == 'approval_field':
        batch['replies'][0]['approved'] = True
    before = protected(run)
    with pytest.raises(ValueError):
        exchange.import_replies(run, path, batch, actor)
    assert not list((run / 'question_exchange' / 'proposals').glob('*.json'))
    assert protected(run) == before


@pytest.mark.parametrize('fault', ['brief', 'source', 'pack', 'other_run'])
def test_stale_or_mismatched_pack_refused(run, tmp_path, fault):
    path, pack = exported(run, tmp_path)
    target = run
    if fault == 'brief':
        brief = revisions.load(run / 'brief.json')
        brief['objectives'][0]['content'] = 'Changed synthetic objective'
        revisions.write_json(run / 'brief.json', brief)
    elif fault == 'source':
        (tmp_path / 'source.md').write_text('Changed synthetic source')
    elif fault == 'pack':
        tampered = copy.deepcopy(pack)
        tampered['questions'][0]['owner'] = 'Forged owner'
        revisions.write_json(path, tampered)
    else:
        import shutil
        target = tmp_path / 'copied-run'
        shutil.copytree(run, target)
    with pytest.raises(ValueError):
        exchange.import_replies(target, path, replies(pack), 'Synthetic importer')
    assert not list((target / 'question_exchange' / 'proposals').glob('*.json'))


def test_duplicate_across_two_packs_refused(run, tmp_path):
    path, pack = exported(run, tmp_path)
    other = tmp_path / 'other.json'
    second = exchange.export_questions(run, other)
    exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    with pytest.raises(ValueError, match='duplicate|already'):
        exchange.import_replies(run, other, replies(second), 'Synthetic importer')


def test_lock_blocks_export_and_import(run, tmp_path):
    path, pack = exported(run, tmp_path)
    with revisions.run_lock(run):
        with pytest.raises(ValueError, match='busy'):
            exchange.export_questions(run, tmp_path / 'blocked.json')
        with pytest.raises(ValueError, match='busy'):
            exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    assert not (tmp_path / 'blocked.json').exists()


def second_run(run, tmp_path):
    import shutil
    other = tmp_path / 'revision'
    shutil.copytree(run, other)
    return other


def test_impact_changed_source_unchanged_text(run, tmp_path):
    after = second_run(run, tmp_path)
    source = tmp_path / 'revised-source.md'
    source.write_text('Changed synthetic source; brief text unchanged')
    snapshot = revisions.load(after / 'input_snapshot.json')
    snapshot['source:rfp'] = revisions.input_state({'source:rfp': source})['source:rfp']
    revisions.write_json(after / 'input_snapshot.json', snapshot)
    report = exchange.impact(run, after)
    assert report['changed_fields'] == []
    assert 'source:rfp' in report['source_changes']
    assert report['required_review'] and report['review_required']
    assert 'objectives' in report['source_affected_fields']


def test_impact_field_evidence_drift_and_identity(run, tmp_path):
    after = second_run(run, tmp_path)
    brief = revisions.load(after / 'brief.json')
    brief['objectives'][0]['content'] = 'Revised synthetic objective'
    brief['objectives'][0]['evidence'][0]['anchor'] = 'Revised synthetic citation'
    revisions.write_json(after / 'brief.json', brief)
    report = exchange.impact(run, after)
    assert 'objectives' in report['changed_fields']
    assert 'objectives' in report['evidence_changes']
    (tmp_path / 'source.md').write_text('Live drift')
    assert exchange.impact(run, after)['source_drift']['before']
    brief['meta']['project_id'] = 'different'
    revisions.write_json(after / 'brief.json', brief)
    with pytest.raises(ValueError, match='identity|project'):
        exchange.impact(run, after)


def test_cli_roundtrip_and_unchanged_impact(run, tmp_path, capsys):
    path = tmp_path / 'cli-pack.json'
    assert exchange.main(['export', str(run), str(path)]) == 0
    pack = revisions.load(path)
    reply_path = tmp_path / 'reply.json'
    revisions.write_json(reply_path, replies(pack))
    assert exchange.main(['import', str(run), str(path), str(reply_path), '--actor', 'Synthetic importer']) == 0
    assert exchange.main(['impact', str(run), str(run)]) == 0
    assert not exchange.impact(run, run)['review_required']
    assert exchange.main(['import', str(run), str(path), str(reply_path), '--actor', 'Synthetic importer']) == 2


def test_atomic_publish_failure_leaves_no_partial_proposal(run, tmp_path, monkeypatch):
    path, pack = exported(run, tmp_path)
    before = protected(run)
    def fail_link(src, dst):
        raise OSError('Synthetic filesystem failure')
    monkeypatch.setattr(exchange.os, 'link', fail_link)
    with pytest.raises(OSError, match='filesystem failure'):
        exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    proposal_dir = run / 'question_exchange' / 'proposals'
    assert list(proposal_dir.iterdir()) == []
    assert protected(run) == before


def test_atomic_publish_refuses_file_created_by_racing_writer(tmp_path, monkeypatch):
    path = tmp_path / 'race.json'
    original_link = exchange.os.link
    def race(src, dst):
        Path(dst).write_text('Existing content')
        original_link(src, dst)
    monkeypatch.setattr(exchange.os, 'link', race)
    with pytest.raises(ValueError, match='overwrite'):
        exchange._create_json(path, {'synthetic': True})
    assert path.read_text() == 'Existing content'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['race.json']


def test_corrupt_proposal_receipt_blocks_further_imports(run, tmp_path):
    path, pack = exported(run, tmp_path)
    first = exchange.import_replies(run, path, replies(pack, [pack['questions'][0]['id']]), 'Synthetic importer')
    receipt = run / 'question_exchange' / 'proposals' / (first['proposal_id'] + '.json')
    first['actor'] = 'Changed attribution'
    revisions.write_json(receipt, first)
    with pytest.raises(ValueError, match='Corrupt'):
        exchange.import_replies(run, path, replies(pack, [pack['questions'][1]['id']]), 'Synthetic importer')
    assert len(list(receipt.parent.glob('*.json'))) == 1


def test_batch_with_previously_imported_reply_rejects_new_reply_too(run, tmp_path):
    path, pack = exported(run, tmp_path)
    exchange.import_replies(run, path, replies(pack, [pack['questions'][0]['id']]), 'Synthetic importer')
    with pytest.raises(ValueError, match='Duplicate'):
        exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    assert len(list((run / 'question_exchange' / 'proposals').glob('*.json'))) == 1


def test_impact_added_removed_sources_and_missing_baseline(run, tmp_path):
    after = second_run(run, tmp_path)
    snapshot = revisions.load(after / 'input_snapshot.json')
    snapshot['source:new'] = snapshot.pop('source:rfp')
    revisions.write_json(after / 'input_snapshot.json', snapshot)
    changes = exchange.impact(run, after)['source_changes']
    assert changes['source:rfp']['after'] is None
    assert changes['source:new']['before'] is None
    (after / 'input_snapshot.json').unlink()
    with pytest.raises(ValueError, match='baseline'):
        exchange.impact(run, after)


def test_identity_and_pack_registration_cannot_be_self_issued(run, tmp_path):
    path, pack = exported(run, tmp_path)
    pack['identity']['project_id'] = 'Forged project'
    pack['pack_id'] = revisions.digest({k: v for k, v in pack.items() if k != 'pack_id'})
    with pytest.raises(ValueError, match='registered'):
        exchange.import_replies(run, pack, replies(pack), 'Synthetic importer')


def test_no_overwrite_of_pack_symlink(run, tmp_path):
    original = tmp_path / 'original.json'
    original.write_text('Retain me')
    output = tmp_path / 'linked.json'
    output.symlink_to(original)
    with pytest.raises(ValueError, match='overwrite'):
        exchange.export_questions(run, output)
    assert original.read_text() == 'Retain me'


@pytest.mark.parametrize('name', ['approval.json', 'extracts/new.json', 'question_exchange/packs/new.json'])
def test_export_cannot_create_machine_owned_run_artifacts(run, name):
    output = run / name
    assert not output.exists()
    with pytest.raises(ValueError, match='reserved'):
        exchange.export_questions(run, output)
    assert not output.exists()


def test_export_to_dedicated_run_directory_preserves_version(run):
    before = revisions.fingerprint(run)
    pack = exchange.export_questions(run, run / 'question_exports' / 'questions.json')
    assert pack['fingerprint'] == before == revisions.fingerprint(run)


def test_pending_current_then_explicit_dismissal_preserves_fingerprint(run, tmp_path):
    revisions.write_json(run / 'approval.json', {'actor': 'Synthetic approver'})
    path, pack = exported(run, tmp_path)
    proposal = exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    before = protected(run)
    fingerprint = revisions.fingerprint(run)
    assert exchange.pending_proposals(run) == [proposal]
    dismissal = exchange.dismiss(run, proposal['proposal_id'], actor='Synthetic reviewer', reason='Synthetic irrelevant response')
    assert dismissal['actor'] == 'Synthetic reviewer' and dismissal['reason']
    assert exchange.pending_proposals(run) == []
    assert protected(run) == before and revisions.fingerprint(run) == fingerprint
    assert revisions.load(run / 'question_exchange' / 'proposals' / (proposal['proposal_id'] + '.json')) == proposal
    with pytest.raises(ValueError, match='already'):
        exchange.dismiss(run, proposal['proposal_id'], actor='Other', reason='Repeated')


def test_pending_excludes_stale_but_retains_receipt(run, tmp_path):
    path, pack = exported(run, tmp_path)
    proposal = exchange.import_replies(run, path, replies(pack), 'Synthetic importer')
    brief = revisions.load(run / 'brief.json')
    brief['objectives'][0]['content'] = 'New synthetic revision'
    revisions.write_json(run / 'brief.json', brief)
    assert exchange.pending_proposals(run) == []
    assert (run / 'question_exchange' / 'proposals' / (proposal['proposal_id'] + '.json')).exists()
    dismissal = exchange.dismiss(run, proposal['proposal_id'], actor='Reviewer', reason='Obsolete synthetic revision')
    assert dismissal['fingerprint'] == pack['fingerprint']
    new_path = tmp_path / 'new-pack.json'
    new_pack = exchange.export_questions(run, new_path)
    current = exchange.import_replies(run, new_path, replies(new_pack), 'Importer')
    assert exchange.pending_proposals(run) == [current]


def test_pending_validates_receipts_and_dismissals(run, tmp_path):
    path, pack = exported(run, tmp_path)
    proposal = exchange.import_replies(run, path, replies(pack), 'Importer')
    dismissal = exchange.dismiss(run, proposal['proposal_id'], actor='Reviewer', reason='Irrelevant')
    target = run / 'question_exchange' / 'dismissals' / (dismissal['dismissal_id'] + '.json')
    dismissal['reason'] = 'Tampered reason'
    revisions.write_json(target, dismissal)
    with pytest.raises(ValueError, match='dismissal'):
        exchange.pending_proposals(run)
    target.unlink()
    target = run / 'question_exchange' / 'proposals' / (proposal['proposal_id'] + '.json')
    proposal['replies'][0]['text'] = 'Tampered answer'
    revisions.write_json(target, proposal)
    with pytest.raises(ValueError, match='proposal'):
        exchange.pending_proposals(run)


def test_dismiss_cli_requires_attribution_and_shared_lock(run, tmp_path):
    path, pack = exported(run, tmp_path)
    proposal = exchange.import_replies(run, path, replies(pack), 'Importer')
    ident = proposal['proposal_id']
    for actor, reason in [(' ', 'Reason'), ('Actor', '')]:
        with pytest.raises(ValueError):
            exchange.dismiss(run, ident, actor=actor, reason=reason)
    with pytest.raises(ValueError, match='Unknown'):
        exchange.dismiss(run, 'a' * 64, actor='Reviewer', reason='Irrelevant')
    with revisions.run_lock(run):
        with pytest.raises(ValueError, match='busy'):
            exchange.dismiss(run, ident, actor='Reviewer', reason='Irrelevant')
        # Read API must be safe inside integration's existing lock.
        assert exchange.pending_proposals(run) == [proposal]
    assert exchange.main(['dismiss', str(run), ident, '--actor', 'Reviewer', '--reason', 'Irrelevant']) == 0
    assert exchange.pending_proposals(run) == []


def test_impact_added_markdown_requires_review_without_snapshot_or_brief_change(run, tmp_path):
    after = second_run(run, tmp_path)
    before_files, after_files = protected(run), protected(after)
    assert exchange.impact(run, after)['review_required'] is False
    added = tmp_path / 'additional-source.md'
    added.write_text('Synthetic newly supplied source')
    with pytest.raises(ValueError, match='source document set changed'):
        revisions.verify_inputs(run)
    report = exchange.impact(run, after)
    assert report['changed_fields'] == [] and report['source_changes'] == {}
    assert report['review_required'] is True
    key = 'source-directory:' + str(tmp_path.resolve())
    for side in ('before', 'after'):
        membership = report['source_drift'][side][key]
        assert membership['status'] == 'membership_changed'
        assert membership['added_paths'] == [str(added.resolve())]
        assert membership['removed_paths'] == []
    assert protected(run) == before_files and protected(after) == after_files


def test_impact_removed_source_preserves_per_source_drift(run, tmp_path):
    source = tmp_path / 'source.md'
    expected_hash = revisions.file_hash(source)
    source.unlink()
    report = exchange.impact(run, run)
    assert report['review_required'] is True
    drift = report['source_drift']['before']
    assert drift['source:rfp'] == {'recorded_sha256': expected_hash,
                                 'current_sha256': None, 'status': 'missing_or_unreadable'}
    assert drift['source-directory:' + str(tmp_path.resolve())]['removed_paths'] == [str(source.resolve())]
    assert drift['source-directory:' + str(tmp_path.resolve())]['added_paths'] == []


def test_impact_membership_matches_nonrecursive_markdown_file_scope(run, tmp_path):
    (tmp_path / 'ignored.txt').write_text('Synthetic non-source file')
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'ignored.md').write_text('Synthetic nested file')
    (tmp_path / 'directory.md').mkdir()
    # Resolved aliases of an already recorded source do not change the set.
    (tmp_path / 'alias.md').symlink_to(tmp_path / 'source.md')
    revisions.verify_inputs(run)
    report = exchange.impact(run, run)
    assert report['source_drift'] == {'before': {}, 'after': {}}
    assert report['review_required'] is False

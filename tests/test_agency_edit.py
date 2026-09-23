"""Synthetic-only tests for attributed companion editing and catalog binding."""
import copy
from contextlib import contextmanager
from datetime import date

import pytest
from conftest import make_review_run

from pipeline import agency_edit, revisions, spec_catalog


@pytest.fixture
def run(tmp_path, monkeypatch):
    @contextmanager
    def lock(path):
        yield
    # Integration provides this shared lock; never invent an incompatible lock here.
    if not hasattr(revisions, 'run_lock'):
        monkeypatch.setattr(revisions, 'run_lock', lock, raising=False)
    return make_review_run(tmp_path)


def table():
    return {'owner': 'Synthetic traffic', 'specs': [{
        'id': 'synthetic-image', 'resolution': '100x100', 'aspect_ratio': '1:1',
        'format': 'Synthetic image', 'file_type': 'PNG', 'duration': 'n/a',
        'source_url': 'https://specs.example.invalid/image', 'checked_on': '2020-01-01',
        'review_due': '2099-01-01', 'checked_by': 'Synthetic reviewer'}]}


def test_checklist_copies_canonical_evidence_and_archives_approval(run):
    revisions.write_json(run / 'approval.json', {'actor': 'Previous reviewer'})
    assert agency_edit.main(['checklist', str(run), '--key', 'objective_and_audience',
                            '--value', 'Synthetic answer', '--owner', 'Lead', '--actor', 'Editor',
                            '--ref', 'objectives:0']) == 0
    answer = revisions.load(run / 'agency_inputs.json')['checklist']['objective_and_audience']
    assert answer['evidence'] == revisions.load(run / 'brief.json')['objectives'][0]['evidence']
    assert answer['actor'] == 'Editor' and answer['updated_at']
    assert not (run / 'approval.json').exists()
    assert list((run / 'history').glob('*/approval.json'))


@pytest.mark.parametrize('key,ref,value', [('unknown', 'objectives:0', 'x'),
    ('objective_and_audience', 'objectives:-1', 'x'),
    ('objective_and_audience', 'objectives:99', 'x'),
    ('objective_and_audience', 'unknown:0', 'x'),
    ('objective_and_audience', 'objectives:0', ' ')])
def test_invalid_checklist_does_not_write(run, key, ref, value):
    before = (run / 'agency_inputs.json').read_bytes()
    assert agency_edit.main(['checklist', str(run), '--key', key, '--value', value,
                            '--owner', 'Lead', '--actor', 'Editor', '--ref', ref]) == 2
    assert (run / 'agency_inputs.json').read_bytes() == before


def test_catalog_contract_and_selection():
    t = table()
    assert spec_catalog.validate(t, today=date(2026, 9, 20)) == []
    t['specs'].append({'id': 'unused'})
    assert spec_catalog.validate(t, ['synthetic-image']) == []
    assert spec_catalog.validate(t)
    assert spec_catalog.validate(t, ['missing'])
    t['specs'].append(copy.deepcopy(t['specs'][0]))
    assert any('duplicate' in p for p in spec_catalog.validate(t, []))


@pytest.mark.parametrize('key,value', [('source_url', 'http://example.invalid'),
    ('source_url', 'https:///missing-host'), ('checked_on', '2999-01-01'),
    ('checked_on', 'not-a-date'), ('review_due', '2019-01-01'),
    ('checked_by', ''), ('resolution', ''), ('aspect_ratio', '0:1'),
    ('format', ''), ('file_type', ''), ('duration', 'guess')])
def test_catalog_rejects_invalid_metadata(key, value):
    t = table()
    t['specs'][0][key] = value
    assert spec_catalog.validate(t)


def test_stub_and_owner_rejected():
    t = table()
    t['_stub_notice'] = ''
    assert spec_catalog.validate(t)
    del t['_stub_notice']
    del t['owner']
    assert spec_catalog.validate(t)


def test_bind_and_deliverable_use_active_catalog(run, tmp_path):
    # Existing rehearsal assets must match the new catalog before binding.
    inputs = revisions.load(run / 'agency_inputs.json')
    inputs['deliverables'] = []
    revisions.write_json(run / 'agency_inputs.json', inputs)
    path = tmp_path / 'catalog.json'
    revisions.write_json(path, table())
    assert spec_catalog.main([str(run), str(path), '--actor', 'Traffic']) == 0
    snapshot = revisions.load(run / 'input_snapshot.json')['channel_specs']
    assert snapshot == revisions.input_state({'channel_specs': path})['channel_specs']
    args = ['deliverable', str(run), '--id', 'asset', '--spec-id', 'synthetic-image',
            '--quantity', '2', '--language', 'el', '--language', 'en', '--deadline', '2026-12-01',
            '--owner', 'Production', '--approval-owner', 'Lead', '--actor', 'Editor',
            '--ref', 'deliverables:0', '--dependency', 'master']
    predecessor = args[:-2].copy()
    predecessor[predecessor.index('--id') + 1] = 'master'
    assert agency_edit.main(predecessor) == 0
    assert agency_edit.main(args) == 0
    row = revisions.load(run / 'agency_inputs.json')['deliverables'][1]
    for key in ('resolution', 'aspect_ratio', 'format', 'file_type', 'duration'):
        assert row[key] == table()['specs'][0][key]
    assert row['languages'] == ['el', 'en'] and row['actor'] == 'Editor'
    assert agency_edit.main(args) == 0
    assert len(revisions.load(run / 'agency_inputs.json')['deliverables']) == 2
    assert row['dependencies'] == ['master']
    before = (run / 'agency_inputs.json').read_bytes()
    assert agency_edit.main(args + ['--duration-seconds', '5']) == 2
    assert (run / 'agency_inputs.json').read_bytes() == before
    path.write_text('{}')
    assert agency_edit.main(args) == 2


def test_invalid_bind_preserves_files(run, tmp_path):
    path = tmp_path / 'catalog.json'
    revisions.write_json(path, {'_stub_notice': 'synthetic'})
    before = {p.name: p.read_bytes() for p in run.glob('*.json')}
    assert spec_catalog.main([str(run), str(path), '--actor', 'Traffic']) == 2
    assert before == {p.name: p.read_bytes() for p in run.glob('*.json')}


def test_shared_lock_failure_prevents_writes(run, monkeypatch):
    @contextmanager
    def busy(path):
        raise ValueError('run is locked')
        yield
    monkeypatch.setattr(revisions, 'run_lock', busy, raising=False)
    before = (run / 'agency_inputs.json').read_bytes()
    assert agency_edit.main(['checklist', str(run), '--key', 'objective_and_audience',
                            '--value', 'x', '--owner', 'Lead', '--actor', 'Editor',
                            '--ref', 'objectives:0']) == 2
    assert (run / 'agency_inputs.json').read_bytes() == before


@pytest.mark.parametrize('duration', [None, -1, 61, float('nan'), float('inf'), True])
def test_video_rejects_invalid_duration_without_writing(run, duration):
    before = (run / 'agency_inputs.json').read_bytes()
    with pytest.raises(ValueError):
        agency_edit.deliverable(run, id='video', spec_id='instagram_story', quantity=1,
            languages=['en'], deadline='2026-12-01', owner='Production', approval_owner='Lead',
            actor='Editor', refs=['deliverables:0'], duration_seconds=duration)
    assert (run / 'agency_inputs.json').read_bytes() == before


def test_video_accepts_duration_and_copies_default_spec(run):
    row = agency_edit.deliverable(run, id='video', spec_id='instagram_story', quantity=1,
        languages=['en'], deadline='2026-12-01', owner='Production', approval_owner='Lead',
        actor='Editor', refs=['deliverables:0'], duration_seconds=30)
    assert row['duration'] == 'up to 60s' and row['duration_seconds'] == 30


@pytest.mark.parametrize('duration,bounds', [('20-10s', None), ('n/a', {'min': 0, 'max': 10}),
    (None, {'min': True, 'max': 10}), (None, {'min': 0, 'max': float('inf')}),
    ('1-10s', {'min': 1, 'max': 11}), (None, {'min': 1})])
def test_catalog_duration_contract(duration, bounds):
    t = table()
    t['specs'][0]['duration'] = duration
    t['specs'][0]['duration_seconds'] = bounds
    assert spec_catalog.validate(t)


def test_bind_archives_approval_and_attributes_catalog(run, tmp_path):
    inputs = revisions.load(run / 'agency_inputs.json')
    inputs['deliverables'] = []
    revisions.write_json(run / 'agency_inputs.json', inputs)
    revisions.write_json(run / 'approval.json', {'actor': 'Old'})
    path = tmp_path / 'catalog.json'
    revisions.write_json(path, table())
    binding = spec_catalog.bind(run, path, actor='Traffic')
    assert binding['actor'] == 'Traffic' and binding['bound_at']
    assert not (run / 'approval.json').exists()
    assert list((run / 'history').glob('*/approval.json'))
    assert revisions.load(run / 'agency_inputs.json')['catalog_binding'] == binding
    revisions.verify_inputs(run)


def test_unknown_cli_field_rejected(run):
    with pytest.raises(SystemExit) as exc:
        agency_edit.main(['checklist', str(run), '--key', 'objective_and_audience',
            '--value', 'x', '--owner', 'Lead', '--actor', 'Editor', '--ref', 'objectives:0',
            '--invented-field', 'x'])
    assert exc.value.code == 2


def test_integrated_run_lock_blocks_edit(run):
    before = (run / 'agency_inputs.json').read_bytes()
    with revisions.run_lock(run):
        assert agency_edit.main(['checklist', str(run), '--key', 'objective_and_audience',
            '--value', 'x', '--owner', 'Lead', '--actor', 'Editor', '--ref', 'objectives:0']) == 2
    assert (run / 'agency_inputs.json').read_bytes() == before

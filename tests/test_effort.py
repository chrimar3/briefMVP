"""Synthetic-only effort recording and scorecard regression checks."""
import csv
import json
import os
import subprocess
import sys

import pytest

from eval import pilot_scorecard
from pipeline import effort, records


def record(run, event_id="e1", **changes):
    args = dict(actor="Synthetic operator", role="account_assembly", minutes=10,
                event_id=event_id, reason=None)
    args.update(changes)
    return effort.record(run, **args)


def test_duplicate_retry_and_conflict_leave_ledger_unchanged(tmp_path):
    record(tmp_path)
    before = (tmp_path / 'effort.json').read_bytes()
    record(tmp_path)
    assert (tmp_path / 'effort.json').read_bytes() == before
    with pytest.raises(ValueError, match='event-id'):
        record(tmp_path, minutes=11)
    assert (tmp_path / 'effort.json').read_bytes() == before


@pytest.mark.parametrize('changes', [dict(minutes=-1), dict(minutes=float('nan')),
    dict(minutes=float('inf')), dict(minutes=True), dict(role='unknown'), dict(actor=' '), dict(event_id='')])
def test_invalid_events_do_not_create_ledger(tmp_path, changes):
    with pytest.raises(ValueError):
        record(tmp_path, **changes)
    assert not (tmp_path / 'effort.json').exists()


def test_export_missing_and_partial_totals(tmp_path):
    path = tmp_path / 'pilot.csv'
    effort.export(tmp_path, path, brief_id='synthetic', phase='retro')
    empty = next(csv.DictReader(path.open()))
    assert empty['assembly_min'] == empty['total_team_min'] == 'not_recorded'
    record(tmp_path, minutes=2.5)
    record(tmp_path, 'e2', minutes=3)
    effort.export(tmp_path, path, brief_id='synthetic', phase='retro')
    row = next(csv.DictReader(path.open()))
    assert float(row['assembly_min']) == 5.5
    assert row['review_min'] == row['total_attention_min'] == 'not_recorded'
    assert row['first_handoff_accepted'] == 'not_recorded'
    assert row['oq_total'] == 'not_recorded'
    assert pilot_scorecard.summarize([row])['metrics']['assembly_min']['mean'] == 5.5


def test_complete_export_and_first_handoff(tmp_path):
    for i, role in enumerate(effort.ROLES):
        record(tmp_path, str(i), role=role, minutes=i + 1)
    effort.handoff(tmp_path, actor='Synthetic reviewer', accepted='no',
                   return_reason='Synthetic missing spec', event_id='h1')
    effort.handoff(tmp_path, actor='Synthetic reviewer', accepted='yes', event_id='h2')
    path = tmp_path / 'pilot.csv'
    effort.export(tmp_path, path, brief_id='synthetic', phase='live')
    row = next(csv.DictReader(path.open()))
    assert float(row['total_attention_min']) == 3
    assert float(row['total_team_min']) == 21
    assert row['first_handoff_accepted'] == 'no'
    assert row['return_reason'] == 'Synthetic missing spec'
    assert pilot_scorecard.summarize([row])['first_handoff_acceptance_pct'] == 0


def test_handoff_idempotency_and_validation(tmp_path):
    args = dict(actor='Synthetic reviewer', accepted='no', return_reason='Needs spec', event_id='h1')
    effort.handoff(tmp_path, **args)
    effort.handoff(tmp_path, **args)
    assert len(json.loads((tmp_path / 'effort.json').read_text())['events']) == 1
    with pytest.raises(ValueError):
        effort.handoff(tmp_path, **{**args, 'accepted': 'maybe'})
    with pytest.raises(ValueError):
        effort.handoff(tmp_path, **{**args, 'return_reason': ''})
    with pytest.raises(ValueError, match='event-id'):
        record(tmp_path, 'h1')


def test_concurrent_processes_preserve_events_and_deduplicate(tmp_path):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    commands = [[sys.executable, '-m', 'pipeline.effort', 'record', str(tmp_path),
                 '--actor', 'Synthetic operator', '--role', 'operator', '--minutes', '1',
                 '--event-id', str(i)] for i in [0, 0, 1, 2, 3, 4, 5, 6]]
    processes = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for cmd in commands]
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, (stdout, stderr)
    assert len(json.loads((tmp_path / 'effort.json').read_text())['events']) == 7


def test_atomic_failure_preserves_existing_ledger(tmp_path, monkeypatch):
    record(tmp_path)
    before = (tmp_path / 'effort.json').read_bytes()
    def fail(*args):
        raise OSError('synthetic replace failure')
    monkeypatch.setattr(records.os, 'replace', fail)  # effort writes through records.atomic_write_text
    with pytest.raises(OSError):
        record(tmp_path, 'second')
    assert (tmp_path / 'effort.json').read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


def test_corrupt_ledger_is_not_overwritten(tmp_path):
    path = tmp_path / 'effort.json'
    path.write_text('{bad')
    with pytest.raises(ValueError):
        record(tmp_path)
    assert path.read_text() == '{bad'


def test_cli_required_id_and_export(tmp_path):
    with pytest.raises(SystemExit) as error:
        effort.main(['record', str(tmp_path), '--actor', 'Synthetic', '--role', 'operator', '--minutes', '1'])
    assert error.value.code == 2
    assert (
        effort.main(
            [
                'record',
                str(tmp_path),
                '--actor',
                'Synthetic',
                '--role',
                'operator',
                '--minutes',
                '1',
                '--event-id',
                'cli',
            ]
        )
        == 0
    )
    assert (
        effort.main(
            [
                'export',
                str(tmp_path),
                '--brief-id',
                'synthetic',
                '--phase',
                'retro',
                '--output',
                str(tmp_path / 'out.csv'),
            ]
        )
        == 0
    )


def question_row(brief, phase, real, total):
    return dict(row_type='PILOT', brief_id=brief, phase=phase, oq_total=str(total), oq_real=str(real),
                oq_duplicate=str(total-real), oq_answered_in_sources='0', oq_not_worth_asking='0')


def test_phase_and_per_brief_precision_are_not_pooled():
    rows = [question_row('a', 'retro', 1, 1), question_row('b', 'retro', 0, 9),
            question_row('c', 'live', 1, 2), question_row('zero', 'live', 0, 0),
            dict(row_type='PILOT', brief_id='missing'), dict(row_type='EXAMPLE', phase='example')]
    report = pilot_scorecard.summarize(rows)
    assert report['question_precision_pct'] == pytest.approx(100 * 2 / 12)
    assert report['question_precision_per_brief']['mean'] == 50
    assert report['question_precision_per_brief']['measured'] == 3
    assert report['question_precision_per_brief']['missing'] == 2
    assert report['by_phase']['retro']['question_precision_per_brief']['mean'] == 50
    assert report['by_phase']['retro']['question_precision_pct'] == 10
    assert report['by_phase']['live']['briefs'] == 2
    assert report['by_phase']['not_recorded']['briefs'] == 1
    assert 'example' not in report['by_phase']


def test_partial_fractional_question_counts_rejected():
    with pytest.raises(ValueError, match='integer'):
        pilot_scorecard.summarize([dict(row_type='PILOT', oq_real='0.5')])


def correction(run, target='e1', event_id='c1', minutes=3):
    return effort.correct(run, target_event_id=target, event_id=event_id,
                          actor='Synthetic supervisor', reason='Fix timer',
                          replacement=dict(kind='effort', actor='Synthetic operator',
                                           role='account_assembly', minutes=minutes, reason='Spec repair'))


def test_explicit_zero_is_measured_but_absent_role_is_unknown(tmp_path):
    record(tmp_path, minutes=0)
    row = effort.export(tmp_path, tmp_path / 'zero.csv', brief_id='synthetic', phase='retro')
    assert row['assembly_min'] == 0
    assert row['review_min'] == row['total_attention_min'] == 'not_recorded'


def test_correction_preserves_original_and_replays_after_void(tmp_path):
    record(tmp_path)
    original = json.loads((tmp_path / 'effort.json').read_text())['events'][0]
    correction(tmp_path)
    correction(tmp_path)
    with pytest.raises(ValueError, match='event-id'):
        correction(tmp_path, minutes=4)
    row = effort.export(tmp_path, tmp_path / 'corrected.csv', brief_id='synthetic', phase='retro')
    assert row['assembly_min'] == 3
    effort.void(tmp_path, target_event_id='c1', actor='Synthetic supervisor', reason='Wrong run', event_id='v1')
    before = (tmp_path / 'effort.json').read_bytes()
    correction(tmp_path)
    effort.void(tmp_path, target_event_id='c1', actor='Synthetic supervisor', reason='Wrong run', event_id='v1')
    assert (tmp_path / 'effort.json').read_bytes() == before
    data = json.loads(before)
    assert data['events'][0] == original
    assert len(data['events']) == 3
    assert effort.read_events(tmp_path) == []
    row = effort.export(tmp_path, tmp_path / 'void.csv', brief_id='synthetic', phase='retro')
    assert row['assembly_min'] == 'not_recorded'


@pytest.mark.parametrize('target', ['unknown', 'e1', 'v1', 'self'])
def test_invalid_void_targets_are_rejected_without_write(tmp_path, target):
    record(tmp_path)
    effort.void(tmp_path, target_event_id='e1', actor='Synthetic', reason='Wrong run', event_id='v1')
    before = (tmp_path / 'effort.json').read_bytes()
    with pytest.raises(ValueError):
        effort.void(tmp_path, target_event_id=target, actor='Synthetic', reason='Wrong run', event_id='self')
    assert (tmp_path / 'effort.json').read_bytes() == before


def test_correction_chain_and_handoff_chronology(tmp_path):
    effort.handoff(tmp_path, actor='Synthetic', accepted='no', return_reason='Wrong spec', event_id='h1')
    effort.handoff(tmp_path, actor='Synthetic', accepted='no', return_reason='Late spec', event_id='h2')
    args = dict(actor='Synthetic supervisor', reason='Fix outcome',
                replacement=dict(kind='handoff', actor='Synthetic', accepted='yes', return_reason=None))
    effort.correct(tmp_path, target_event_id='h1', event_id='c1', **args)
    effort.correct(tmp_path, target_event_id='c1', event_id='c2', **args)
    events = effort.read_events(tmp_path)
    assert [e['event_id'] for e in events] == ['c2', 'h2']
    assert events[0]['accepted'] == 'yes'
    row = effort.export(tmp_path, tmp_path / 'handoff.csv', brief_id='synthetic', phase='retro')
    assert row['first_handoff_accepted'] == 'yes'
    with pytest.raises(ValueError):
        correction(tmp_path, target='h2', event_id='wrong-kind')


@pytest.mark.parametrize('change', [dict(actor=''), dict(reason=' '), dict(target_event_id='missing'),
                                  dict(replacement={'kind': 'void'}), dict(target_event_id='c1')])
def test_invalid_correction_rejected(tmp_path, change):
    record(tmp_path)
    args = dict(target_event_id='e1', event_id='c1', actor='Synthetic supervisor', reason='Fix timer',
                replacement=dict(kind='effort', actor='Synthetic', role='operator', minutes=0, reason=None))
    with pytest.raises(ValueError):
        effort.correct(tmp_path, **{**args, **change})
    assert len(json.loads((tmp_path / 'effort.json').read_text())['events']) == 1


def test_corrupt_forward_reference_and_cycles_are_rejected(tmp_path):
    record(tmp_path)
    correction(tmp_path)
    path = tmp_path / 'effort.json'
    data = json.loads(path.read_text())
    data['events'][1]['target_event_id'] = 'c1'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        effort.read_events(tmp_path)
    data['events'][1]['target_event_id'] = 'future'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        effort.read_events(tmp_path)


def test_correction_cli_and_void_cli(tmp_path):
    record(tmp_path)
    payload = json.dumps(dict(kind='effort', actor='Synthetic', role='operator', minutes=0, reason='Spec repair'))
    assert effort.main(['correct', str(tmp_path), '--target-event-id', 'e1', '--actor', 'Synthetic supervisor',
                        '--reason', 'Fix role', '--event-id', 'c1', '--replacement', payload]) == 0
    assert effort.main(['void', str(tmp_path), '--target-event-id', 'c1', '--actor', 'Synthetic supervisor',
                        '--reason', 'Wrong run', '--event-id', 'v1']) == 0
    assert effort.read_events(tmp_path) == []


def test_concurrent_corrections_only_one_can_replace_target(tmp_path):
    record(tmp_path)
    payload = json.dumps(dict(kind='effort', actor='Synthetic', role='operator', minutes=2, reason=None))
    commands = [[sys.executable, '-m', 'pipeline.effort', 'correct', str(tmp_path),
                 '--target-event-id', 'e1', '--actor', 'Synthetic supervisor', '--reason', 'Fix timer',
                 '--event-id', event_id, '--replacement', payload] for event_id in ('c1', 'c2')]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    processes = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for cmd in commands]
    for process in processes:
        process.communicate(timeout=20)
    assert sorted(process.returncode for process in processes) == [0, 2]
    assert len(json.loads((tmp_path / 'effort.json').read_text())['events']) == 2
    assert len(effort.read_events(tmp_path)) == 1


def test_correction_changes_totals_and_cannot_replace_inactive_target(tmp_path):
    for i, role in enumerate(effort.ROLES):
        record(tmp_path, event_id=str(i), role=role, minutes=2)
    correction(tmp_path, target='0', minutes=0)
    row = effort.export(tmp_path, tmp_path / 'total.csv', brief_id='synthetic', phase='retro')
    assert row['total_attention_min'] == 2
    assert row['total_team_min'] == 10
    before = (tmp_path / 'effort.json').read_bytes()
    with pytest.raises(ValueError, match='target'):
        correction(tmp_path, target='0', event_id='c2')
    assert (tmp_path / 'effort.json').read_bytes() == before


def test_conflicting_void_retry_is_rejected(tmp_path):
    record(tmp_path)
    effort.void(tmp_path, target_event_id='e1', actor='Synthetic', reason='Wrong run', event_id='v1')
    with pytest.raises(ValueError, match='event-id'):
        effort.void(
            tmp_path, target_event_id='e1', actor='Different synthetic actor', reason='Wrong run', event_id='v1'
        )


def test_effort_ledger_and_export_are_owner_only(tmp_path):
    """Effort records name agency staff and their minutes: both files are 0600 whatever the umask."""
    previous = os.umask(0o022)
    try:
        record(tmp_path)
        effort.export(tmp_path, tmp_path / 'row.csv', brief_id='B1', phase='retro')
    finally:
        os.umask(previous)
    assert (tmp_path / 'effort.json').stat().st_mode & 0o777 == 0o600
    assert (tmp_path / 'row.csv').stat().st_mode & 0o777 == 0o600

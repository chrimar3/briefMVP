"""Synthetic-only effort recording and scorecard regression checks."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from eval import pilot_scorecard
from pipeline import effort


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


@pytest.mark.parametrize('changes', [dict(minutes=0), dict(minutes=-1), dict(minutes=float('nan')),
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
    monkeypatch.setattr(effort.os, 'replace', fail)
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
    assert effort.main(['record', str(tmp_path), '--actor', 'Synthetic', '--role', 'operator', '--minutes', '1', '--event-id', 'cli']) == 0
    assert effort.main(['export', str(tmp_path), '--brief-id', 'synthetic', '--phase', 'retro', '--output', str(tmp_path / 'out.csv')]) == 0


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

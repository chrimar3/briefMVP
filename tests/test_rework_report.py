"""Cross-run reporting uses synthetic events only."""
import json

import pytest

from eval import rework_report
from pipeline import effort


def record(run, event_id='e1', minutes=5, reason='Spec repair'):
    effort.record(run, actor='Synthetic operator', role='operator', minutes=minutes,
                  reason=reason, event_id=event_id)


def test_deduplicates_aliases_and_distinguishes_first_from_all(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(run, target_is_directory=True)
    record(run)
    effort.handoff(run, actor='Synthetic', accepted='yes', event_id='h1')
    for i in (2, 3):
        effort.handoff(run, actor='Synthetic', accepted='no', return_reason='Spec repair', event_id=f'h{i}')
    report = rework_report.summarize([run, alias, run])
    assert report['unique_runs'] == 1
    assert report['duplicates_skipped'] == 2
    assert report['first_handoff']['accepted'] == 1
    assert report['first_handoff']['rejected'] == 0
    assert report['all_attempts']['observed'] == 3
    assert report['all_attempts']['rejected'] == 2
    assert report['return_reasons'] == {'Spec repair': 2}
    assert report['attributed_reason_minutes'] == {'Spec repair': 5}
    assert report['attributions'][0]['actor'] == 'Synthetic operator'


def test_missing_corrupt_empty_and_observed_zero_are_distinct(tmp_path):
    paths = [tmp_path / name for name in ('missing', 'corrupt', 'empty', 'zero')]
    for path in paths:
        path.mkdir()
    (paths[1] / 'effort.json').write_text('{bad')
    (paths[2] / 'effort.json').write_text('{"version": 1, "events": []}')
    record(paths[3], minutes=0)
    report = rework_report.summarize(paths + [tmp_path / 'nonexistent'])
    assert [r['status'] for r in report['runs']] == ['missing', 'error', 'ok', 'ok', 'error']
    assert report['missing_runs'] == 1
    assert report['error_runs'] == 2
    assert report['first_handoff']['missing_runs'] == 5
    assert report['observed_attributed_minutes'] == 0
    assert report['runs'][2]['observed_attributed_minutes'] is None
    assert report['runs'][3]['observed_attributed_minutes'] == 0
    assert report['runs'][1]['error']


def test_corrections_voids_and_unattributed_minutes(tmp_path):
    record(tmp_path, minutes=20)
    record(tmp_path, event_id='other', minutes=7, reason=None)
    effort.correct(tmp_path, target_event_id='e1', event_id='c1', actor='Synthetic supervisor',
                   reason='Timer correction', replacement=dict(kind='effort', actor='Synthetic operator',
                     role='operator', minutes=3, reason='Revised spec'))
    effort.handoff(tmp_path, actor='Synthetic', accepted='no', return_reason='Old reason', event_id='h1')
    effort.void(tmp_path, target_event_id='h1', actor='Synthetic', reason='Wrong run', event_id='v1')
    report = rework_report.summarize([tmp_path])
    assert report['attributed_reason_minutes'] == {'Revised spec': 3}
    assert report['unattributed_minutes'] == 7
    assert report['unattributed_events'] == 1
    assert report['return_reasons'] == {}
    assert report['all_attempts']['observed'] is None
    assert report['attributions'][0]['event_id'] == 'c1'


def test_no_observations_are_not_zero(tmp_path):
    report = rework_report.summarize([tmp_path])
    assert report['observed_attributed_minutes'] is None
    assert report['all_attempts']['observed'] is None
    assert report['first_handoff']['acceptance_pct'] is None


def test_bad_structured_ledger_does_not_hide_valid_run(tmp_path):
    bad, good = tmp_path / 'bad', tmp_path / 'good'
    bad.mkdir()
    good.mkdir()
    (bad / 'effort.json').write_text(json.dumps({'version': 1, 'events': [dict(kind='effort', actor='Synthetic',
        event_id='bad', role=[], minutes=1, recorded_at='now')]}))
    record(good)
    report = rework_report.summarize([bad, good])
    assert report['error_runs'] == 1
    assert report['observed_attributed_minutes'] == 5


def test_cli_surfaces_partial_errors(tmp_path, capsys):
    (tmp_path / 'effort.json').write_text('bad')
    assert rework_report.main([str(tmp_path)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['error_runs'] == 1


def test_corrected_first_handoff_preserves_attempt_order(tmp_path):
    effort.handoff(tmp_path, actor='Synthetic', accepted='no', return_reason='Old reason', event_id='h1')
    effort.handoff(tmp_path, actor='Synthetic', accepted='no', return_reason='Later reason', event_id='h2')
    effort.correct(tmp_path, target_event_id='h1', event_id='c1', actor='Synthetic supervisor', reason='Fix outcome',
                   replacement=dict(kind='handoff', actor='Synthetic', accepted='yes', return_reason=None))
    report = rework_report.summarize([tmp_path])
    assert report['first_handoff']['acceptance_pct'] == 100
    assert report['all_attempts']['observed'] == 2
    assert report['all_attempts']['rejected'] == 1
    assert report['return_reasons'] == {'Later reason': 1}


def test_aggregate_overflow_surfaces_error(tmp_path):
    runs = [tmp_path / name for name in ('a', 'b')]
    for run in runs:
        run.mkdir()
        record(run, minutes=1e308)
    report = rework_report.summarize(runs)
    assert report['aggregation_error']
    assert report['observed_attributed_minutes'] is None


def test_report_missing_cli_status_and_valid_cli(tmp_path, capsys):
    assert rework_report.main([str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)['missing_runs'] == 1
    record(tmp_path)
    assert rework_report.main([str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)['observed_attributed_minutes'] == 5


def test_distinct_runs_with_same_event_ids_both_count(tmp_path):
    runs = [tmp_path / name for name in ('a', 'b')]
    for run, minutes in zip(runs, (3, 7)):
        run.mkdir()
        record(run, minutes=minutes)
        effort.handoff(run, actor='Synthetic', accepted='no', return_reason='Spec repair', event_id='h1')
    report = rework_report.summarize(runs)
    assert report['unique_runs'] == 2
    assert report['first_handoff']['rejected'] == 2
    assert report['all_attempts']['observed'] == 2
    assert report['return_reasons'] == {'Spec repair': 2}
    assert report['attributed_reason_minutes'] == {'Spec repair': 10}
    assert {e['run'] for e in report['attributions']} == {str(run.resolve()) for run in runs}

"""Record synthetic human effort and export a measured PILOT scorecard row."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import io
import json
import math
import os
from pathlib import Path
import tempfile

ROLES = {
    'account_assembly': 'assembly_min', 'account_review': 'review_min',
    'operator': 'operator_min', 'strategy': 'strategy_min',
    'creative': 'creative_min', 'production': 'production_min',
}
TEMPLATE = Path(__file__).resolve().parents[1] / 'docs/pilot/scorecard_template.csv'
MISSING = 'not_recorded'


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be nonempty text')
    return value


def _validate(event):
    for name in ('event_id', 'actor'):
        _text(event.get(name), name)
    if event.get('kind') == 'effort':
        if event.get('role') not in ROLES:
            raise ValueError('unknown effort role')
        minutes = event.get('minutes')
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes <= 0:
            raise ValueError('minutes must be finite and positive')
        if event.get('reason') is not None:
            _text(event['reason'], 'reason')
    elif event.get('kind') == 'handoff':
        if event.get('accepted') not in ('yes', 'no'):
            raise ValueError('accepted must be yes or no')
        reason = event.get('return_reason')
        if event['accepted'] == 'no' or reason is not None:
            _text(reason, 'return_reason')
        if event['accepted'] == 'yes' and reason is not None:
            raise ValueError('accepted handoff cannot have a return reason')
    else:
        raise ValueError('unknown event kind')


@contextmanager
def _lock(run):
    run = Path(run)
    if not run.is_dir():
        raise ValueError('run must be an existing directory')
    # A separate, persistent inode: never lock the atomically replaced ledger.
    with (run / '.effort.lock').open('a') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield run
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load(run):
    path = run / 'effort.json'
    if not path.exists():
        return {'version': 1, 'events': []}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('events'), list):
        raise ValueError('invalid effort ledger')
    seen = set()
    for event in data['events']:
        if not isinstance(event, dict):
            raise ValueError('invalid effort event')
        _validate(event)
        _text(event.get('recorded_at'), 'recorded_at')
        if event['event_id'] in seen:
            raise ValueError('duplicate event-id in ledger')
        seen.add(event['event_id'])
    return data


def _atomic_write(path, text):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _append(run, event):
    _validate(event)
    with _lock(run) as directory:
        data = _load(directory)
        for existing in data['events']:
            if existing['event_id'] == event['event_id']:
                payload = {k: v for k, v in existing.items() if k != 'recorded_at'}
                if payload != event:
                    raise ValueError('event-id already exists with conflicting content')
                return existing
        saved = {**event, 'recorded_at': datetime.now(timezone.utc).isoformat()}
        data['events'].append(saved)
        _atomic_write(directory / 'effort.json', json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
        return saved


def record(run, *, actor, role, minutes, event_id, reason=None):
    return _append(run, dict(kind='effort', actor=actor, role=role, minutes=minutes,
                             event_id=event_id, reason=reason))


def handoff(run, *, actor, accepted, event_id, return_reason=None):
    return _append(run, dict(kind='handoff', actor=actor, accepted=accepted,
                             event_id=event_id, return_reason=return_reason))


def export(run, output, *, brief_id, phase):
    """Export a snapshot; totals require every contributing role to be recorded."""
    _text(brief_id, 'brief_id')
    if phase not in ('retro', 'live'):
        raise ValueError('phase must be retro or live')
    output = Path(output)
    if output.suffix.lower() != '.csv':
        raise ValueError('output must be a .csv file')
    with _lock(run) as directory:
        data = _load(directory)
        with TEMPLATE.open(encoding='utf-8', newline='') as handle:
            fields = next(csv.reader(handle))
        row = dict.fromkeys(fields, MISSING)
        row.update(row_type='PILOT', brief_id=brief_id, phase=phase,
                   run_id=directory.name, notes='Synthetic measurements only; self-reported human effort.')
        for role, field in ROLES.items():
            values = [e['minutes'] for e in data['events'] if e['kind'] == 'effort' and e['role'] == role]
            if values:
                total = sum(values)
                if not math.isfinite(total):
                    raise ValueError('effort total is not finite')
                row[field] = total
        for total, components in (
            ('total_attention_min', ('assembly_min', 'review_min')),
            ('total_team_min', tuple(ROLES.values())),
        ):
            if all(row[key] != MISSING for key in components):
                value = sum(row[key] for key in components)
                if not math.isfinite(value):
                    raise ValueError('effort total is not finite')
                row[total] = value
        first = next((e for e in data['events'] if e['kind'] == 'handoff'), None)
        if first:
            row['first_handoff_accepted'] = first['accepted']
            row['return_reason'] = first['return_reason'] or MISSING
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
        _atomic_write(output, stream.getvalue())
        return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('record', 'handoff', 'export'):
        command = commands.add_parser(name)
        command.add_argument('run', type=Path)
        if name == 'export':
            command.add_argument('--output', required=True, type=Path)
            command.add_argument('--brief-id', required=True)
            command.add_argument('--phase', required=True, choices=('retro', 'live'))
        else:
            command.add_argument('--actor', required=True)
            command.add_argument('--event-id', required=True)
            if name == 'record':
                command.add_argument('--role', required=True, choices=tuple(ROLES))
                command.add_argument('--minutes', required=True, type=float)
                command.add_argument('--reason')
            else:
                command.add_argument('--accepted', required=True, choices=('yes', 'no'))
                command.add_argument('--return-reason')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = {'record': record, 'handoff': handoff, 'export': export}[command](**args)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'effort: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

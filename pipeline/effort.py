"""Record synthetic human effort and export a measured PILOT scorecard row."""
from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import math
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional

if __package__ in (None, ""):  # allow `python3 pipeline/effort.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import clock, records  # noqa: E402
from pipeline.records import PathLike  # noqa: E402

Event = dict[str, Any]

ROLES = {
    'account_assembly': 'assembly_min', 'account_review': 'review_min',
    'operator': 'operator_min', 'strategy': 'strategy_min',
    'creative': 'creative_min', 'production': 'production_min',
}
TEMPLATE = Path(__file__).resolve().parents[1] / 'docs/pilot/scorecard_template.csv'
MISSING = 'not_recorded'


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be nonempty text')
    return value


def _validate(event: Event) -> None:
    for name in ('event_id', 'actor'):
        _text(event.get(name), name)
    if event.get('kind') == 'effort':
        if not isinstance(event.get('role'), str) or event['role'] not in ROLES:
            raise ValueError('unknown effort role')
        minutes = event.get('minutes')
        if (isinstance(minutes, bool) or not isinstance(minutes, (int, float))
                or not math.isfinite(minutes) or minutes < 0):
            raise ValueError('minutes must be finite and nonnegative')
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
    elif event.get('kind') in ('void', 'correction'):
        _text(event.get('target_event_id'), 'target_event_id')
        _text(event.get('reason'), 'reason')
        if event['kind'] == 'correction':
            replacement = event.get('replacement')
            if not isinstance(replacement, dict) or replacement.get('kind') not in ('effort', 'handoff'):
                raise ValueError('replacement must be an effort or handoff payload')
            fields = ({'kind', 'actor', 'role', 'minutes', 'reason'} if replacement['kind'] == 'effort'
                      else {'kind', 'actor', 'accepted', 'return_reason'})
            if set(replacement) != fields:
                raise ValueError('replacement must contain exactly the measurement payload fields')
            _validate({**replacement, 'event_id': event['event_id']})
    else:
        raise ValueError('unknown event kind')


def effective_events(events: list[Event]) -> list[Event]:
    """Validate history and fold amendments, retaining original observation order.

    Only earlier, currently active measurements can be targets. Correction IDs
    become the active IDs; void events can never be targeted. These rules forbid
    forward references, self references, cycles, and repeated invalidation.
    """
    active: list[Optional[Event]] = []
    positions: dict[str, int] = {}
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('invalid effort event')
        _validate(event)
        event_id = event['event_id']
        if event_id in seen:
            raise ValueError('duplicate event-id in ledger')
        seen.add(event_id)
        if event['kind'] in ('effort', 'handoff'):
            positions[event_id] = len(active)
            active.append(dict(event))
            continue
        target = event['target_event_id']
        if target == event_id or target not in positions:
            raise ValueError('target must be an earlier active event; unknown or already voided/replaced target')
        position = positions.pop(target)
        if event['kind'] == 'void':
            active[position] = None
        else:
            replacement = event['replacement']
            current = active[position]
            if current is None or replacement['kind'] != current['kind']:
                raise ValueError('correction must preserve measurement kind')
            active[position] = {**replacement, 'event_id': event_id,
                                'recorded_at': event.get('recorded_at'),
                                'corrected_by': event['actor'], 'correction_reason': event['reason']}
            positions[event_id] = position
    return [event for event in active if event is not None]


@contextmanager
def _lock(run: PathLike, *, shared: bool = False) -> Iterator[Path]:
    """Blocking ledger lock. Writers take it exclusive; `shared=True` is for readers.

    A reader never creates the lock file: with no lock file, no writer has ever run here and
    the atomically replaced ledger can be read as is, so read-only commands leave evidence
    folders byte-identical.
    """
    run = Path(run)
    if not run.is_dir():
        raise ValueError('run must be an existing directory')
    lock_path = run / '.effort.lock'
    if shared and not lock_path.is_file():
        yield run
        return
    # A separate, persistent inode: never lock the atomically replaced ledger.
    with lock_path.open('r' if shared else 'a') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            yield run
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load(run: Path) -> dict[str, Any]:
    data = records.load_optional(run / 'effort.json')
    if data is None:
        return {'version': 1, 'events': []}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('events'), list):
        raise ValueError('invalid effort ledger')
    for event in data['events']:
        if not isinstance(event, dict):
            raise ValueError('invalid effort event')
        _text(event.get('recorded_at'), 'recorded_at')
    effective_events(data['events'])
    return data


def read_events(run: PathLike) -> Optional[list[Event]]:
    """Locked effective snapshot; None means no ledger, [] an empty active set."""
    with _lock(run, shared=True) as directory:
        if not (directory / 'effort.json').exists():
            return None
        return effective_events(_load(directory)['events'])


def _atomic_write(path: Path, text: str) -> None:
    """Effort records name agency staff: every write (ledger and export) is owner-only (0600)."""
    records.atomic_write_text(path, text, private=True)


def _append(run: PathLike, event: Event) -> Event:
    _validate(event)
    with _lock(run) as directory:
        data = _load(directory)
        for existing in data['events']:
            if existing['event_id'] == event['event_id']:
                payload = {k: v for k, v in existing.items() if k != 'recorded_at'}
                if payload != event:
                    raise ValueError('event-id already exists with conflicting content')
                return existing
        saved = {**event, 'recorded_at': clock.timestamp()}
        data['events'].append(saved)
        effective_events(data['events'])
        _atomic_write(directory / 'effort.json', json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
        return saved


def record(run: PathLike, *, actor: str, role: str, minutes: float, event_id: str,
           reason: Optional[str] = None) -> Event:
    """Record minutes of effort for one role (idempotent per event id)."""
    return _append(run, dict(kind='effort', actor=actor, role=role, minutes=minutes,
                             event_id=event_id, reason=reason))


def handoff(run: PathLike, *, actor: str, accepted: str, event_id: str,
            return_reason: Optional[str] = None) -> Event:
    """Record whether a handoff was accepted ('yes'/'no', a return reason when 'no')."""
    return _append(run, dict(kind='handoff', actor=actor, accepted=accepted,
                             event_id=event_id, return_reason=return_reason))


def void(run: PathLike, *, target_event_id: str, actor: str, reason: str, event_id: str) -> Event:
    """Void an earlier active measurement, with an attributed reason."""
    return _append(run, dict(kind='void', target_event_id=target_event_id,
                             actor=actor, reason=reason, event_id=event_id))


def correct(run: PathLike, *, target_event_id: str, actor: str, reason: str, event_id: str,
            replacement: Event) -> Event:
    """Replace an earlier active measurement with a corrected payload of the same kind."""
    return _append(run, dict(kind='correction', target_event_id=target_event_id,
                             actor=actor, reason=reason, event_id=event_id,
                             replacement=replacement))


def export(run: PathLike, output: PathLike, *, brief_id: str, phase: str) -> dict[str, Any]:
    """Export a snapshot; totals require every contributing role to be recorded."""
    _text(brief_id, 'brief_id')
    if phase not in ('retro', 'live'):
        raise ValueError('phase must be retro or live')
    output = Path(output)
    if output.suffix.lower() != '.csv':
        raise ValueError('output must be a .csv file')
    with _lock(run) as directory:
        data = _load(directory)
        events = effective_events(data['events'])
        with TEMPLATE.open(encoding='utf-8', newline='') as handle:
            fields = next(csv.reader(handle))
        row: dict[str, Any] = dict.fromkeys(fields, MISSING)
        row.update(row_type='PILOT', brief_id=brief_id, phase=phase,
                   run_id=directory.name, notes='Synthetic measurements only; self-reported human effort.')
        for role, field in ROLES.items():
            values = [e['minutes'] for e in events if e['kind'] == 'effort' and e['role'] == role]
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
        first = next((e for e in events if e['kind'] == 'handoff'), None)
        if first:
            row['first_handoff_accepted'] = first['accepted']
            row['return_reason'] = first['return_reason'] or MISSING
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
        _atomic_write(output, stream.getvalue())
        return row


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: one subcommand per ledger operation; prints the saved event (or exported row) as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('record', 'handoff', 'export', 'correct', 'void'):
        sub = commands.add_parser(name)
        sub.add_argument('run', type=Path)
        if name == 'export':
            sub.add_argument('--output', required=True, type=Path)
            sub.add_argument('--brief-id', required=True)
            sub.add_argument('--phase', required=True, choices=('retro', 'live'))
        else:
            sub.add_argument('--actor', required=True)
            sub.add_argument('--event-id', required=True)
            if name == 'record':
                sub.add_argument('--role', required=True, choices=tuple(ROLES))
                sub.add_argument('--minutes', required=True, type=float)
                sub.add_argument('--reason')
            elif name == 'handoff':
                sub.add_argument('--accepted', required=True, choices=('yes', 'no'))
                sub.add_argument('--return-reason')
            else:
                sub.add_argument('--target-event-id', required=True)
                sub.add_argument('--reason', required=True)
                if name == 'correct':
                    sub.add_argument('--replacement', required=True, type=json.loads,
                                     help='Complete effort/handoff payload as JSON (no event_id or timestamp)')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    handlers: dict[str, Callable[..., dict[str, Any]]] = {
        'record': record, 'handoff': handoff, 'export': export, 'correct': correct, 'void': void}
    try:
        result = handlers[command](**args)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'effort: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

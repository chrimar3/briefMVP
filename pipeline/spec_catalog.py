"""Validate human-maintained release catalogs and bind them to a review run."""
from __future__ import annotations

import argparse
from datetime import date
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from pipeline import agency, handover, revisions


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('expected YYYY-MM-DD')
    return date.fromisoformat(value)


def validate(table, selected_ids=None, today=None) -> list[str]:
    """Check release metadata; URL syntax is not proof of source authenticity.

    IDs are checked globally. Row metadata is checked for selected IDs, or all
    rows when selected_ids is None. Dates use the local calendar by default.
    """
    today = date.today() if today is None else today
    if isinstance(today, str):
        today = _date(today)
    problems = []
    if not isinstance(table, dict):
        return ['catalog must be an object']
    if '_stub_notice' in table:
        problems.append('release catalog must not contain _stub_notice')
    if not _text(table.get('owner', table.get('_owner'))):
        problems.append('catalog owner required')
    rows = table.get('specs')
    if not isinstance(rows, list) or not rows:
        return problems + ['catalog specs must be a nonempty list']
    selected = None if selected_ids is None else set(selected_ids)
    seen = set()
    for i, row in enumerate(rows):
        prefix = f'spec {i}'
        if not isinstance(row, dict) or not _text(row.get('id')):
            problems.append(f'{prefix}: nonempty id required')
            continue
        ident = row['id']
        if ident in seen:
            problems.append(f'{prefix}: duplicate id {ident}')
        seen.add(ident)
        if selected is not None and ident not in selected:
            continue
        for key in ('resolution', 'aspect_ratio', 'format', 'file_type', 'checked_by'):
            if not _text(row.get(key)):
                problems.append(f'{prefix}: {key} required')
        for key, pattern in [('resolution', r'[1-9]\d*x[1-9]\d*'),
                             ('aspect_ratio', r'[1-9]\d*:[1-9]\d*')]:
            if not isinstance(row.get(key), str) or not re.fullmatch(pattern, row[key]):
                problems.append(f'{prefix}: invalid {key}')
        url = row.get('source_url')
        try:
            parsed = urlsplit(url) if isinstance(url, str) else None
            if (not parsed or parsed.scheme != 'https' or not parsed.hostname
                    or parsed.username or parsed.password or any(c.isspace() for c in url)):
                raise ValueError()
            parsed.port
        except ValueError:
            problems.append(f'{prefix}: source_url must be an HTTPS official source URL with a host')
        checked = due = None
        for key in ('checked_on', 'review_due'):
            try:
                value = _date(row.get(key))
                if key == 'checked_on':
                    checked = value
                else:
                    due = value
            except (ValueError, TypeError):
                problems.append(f'{prefix}: invalid {key}')
        if checked and checked > today:
            problems.append(f'{prefix}: checked_on is in the future')
        if due and (due < today or (checked and due < checked)):
            problems.append(f'{prefix}: review_due is expired or before checked_on')
        duration = row.get('duration')
        bounds = row.get('duration_seconds')
        interval = re.fullmatch(r'(\d+)-(\d+)s', duration) if isinstance(duration, str) else None
        maximum = re.fullmatch(r'up to (\d+)s', duration) if isinstance(duration, str) else None
        expected = ({'min': int(interval[1]), 'max': int(interval[2])} if interval else
                    {'min': 0, 'max': int(maximum[1])} if maximum else None)
        if duration != 'n/a' and expected is None and bounds is None:
            problems.append(f'{prefix}: duration metadata required (n/a, range, or bounds)')
        if duration is not None and duration != 'n/a' and expected is None:
            problems.append(f'{prefix}: unrecognized duration')
        if duration == 'n/a' and bounds is not None:
            problems.append(f'{prefix}: static duration cannot have bounds')
        if expected and expected['min'] > expected['max']:
            problems.append(f'{prefix}: reversed duration range')
        if bounds is not None:
            if (not isinstance(bounds, dict) or set(bounds) != {'min', 'max'}
                    or any(type(bounds[k]) not in (int, float) or not math.isfinite(bounds[k]) for k in bounds)
                    or not 0 <= bounds['min'] <= bounds['max']):
                problems.append(f'{prefix}: invalid duration_seconds bounds')
            elif expected is not None and bounds != expected:
                problems.append(f'{prefix}: duration contracts disagree')
    if selected is not None:
        problems.extend(f'unknown spec id: {ident}' for ident in sorted(selected - seen))
    return problems


def bind(run, table_path, *, actor):
    """Bind a validated catalog; shared run_lock is required from revisions."""
    run, table_path = Path(run).resolve(), Path(table_path).resolve()
    if not _text(actor):
        raise ValueError('actor required')
    with revisions.run_lock(run):
        brief = agency.read_run(run)
        inputs = revisions.load(run / 'agency_inputs.json')
        snapshot = revisions.load(run / 'input_snapshot.json')
        if not isinstance(inputs, dict) or not isinstance(snapshot, dict):
            raise ValueError('Initialize agency inputs and input snapshot first')
        revisions.verify_inputs(run)
        state = revisions.input_state({'channel_specs': table_path})['channel_specs']
        table = revisions.load(table_path)
        problems = validate(table)
        if problems:
            raise ValueError('; '.join(problems))
        if revisions.file_hash(table_path) != state['sha256']:
            raise ValueError('Catalog changed during validation; retry')
        snapshot['channel_specs'] = state
        inputs['catalog_binding'] = {**state, 'actor': actor, 'bound_at': revisions.timestamp(),
                                     'recheck_deliverables': handover.validate(inputs.get('deliverables', []), table, brief)}
        revisions.archive(run, ['agency_inputs.json', 'input_snapshot.json'], copy_only=True)
        revisions.archive(run, ['approval.json', 'language_review.json', 'agency_audit.json', 'handover.json', 'creative_approval.json'])
        revisions.write_json(run / 'input_snapshot.json', snapshot)
        revisions.write_json(run / 'agency_inputs.json', inputs)
        revisions.capture_evidence(run, {key: value['path'] for key, value in snapshot.items()})
    return inputs['catalog_binding']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('table', type=Path)
    parser.add_argument('--actor', required=True)
    args = parser.parse_args(argv)
    try:
        bind(args.run, args.table, actor=args.actor)
    except (ValueError, OSError, AttributeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())

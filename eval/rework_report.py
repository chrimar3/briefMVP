"""Summarize observed synthetic rework over explicit, deduplicated run paths."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pipeline import effort


def _sum(values):
    if not values:
        return None
    try:
        value = math.fsum(values)
    except OverflowError as exc:
        raise ValueError('observed minutes overflow') from exc
    if not math.isfinite(value):
        raise ValueError('observed minutes must be finite')
    return value


def _measure(events, run):
    handoffs = [e for e in events if e['kind'] == 'handoff']
    timed = [e for e in events if e['kind'] == 'effort']
    attributed = [dict(run=run, event_id=e['event_id'], actor=e['actor'], role=e['role'],
                       reason=e['reason'], minutes=e['minutes'],
                       corrected_by=e.get('corrected_by'), correction_reason=e.get('correction_reason'))
                  for e in timed if e.get('reason') is not None]
    unattributed = [e['minutes'] for e in timed if e.get('reason') is None]
    reasons = {}
    for event in handoffs:
        if event['accepted'] == 'no':
            reason = event['return_reason']
            reasons[reason] = reasons.get(reason, 0) + 1
    return dict(first_handoff=handoffs[0] if handoffs else None,
                handoff_attempts=len(handoffs) if handoffs else None,
                accepted_attempts=sum(e['accepted'] == 'yes' for e in handoffs) if handoffs else None,
                rejected_attempts=sum(e['accepted'] == 'no' for e in handoffs) if handoffs else None,
                return_reasons=reasons, effort_events=len(timed), attributions=attributed,
                observed_attributed_minutes=_sum([e['minutes'] for e in attributed]),
                unattributed_minutes=_sum(unattributed), unattributed_events=len(unattributed))


def summarize(runs):
    """Missing/error rows remain visible; aggregates cover observed events only."""
    seen, rows, duplicates = set(), [], 0
    for raw in runs:
        try:
            path = Path(raw).resolve()
            if path in seen:
                duplicates += 1
                continue
            seen.add(path)
            run = str(path)
            events = effort.read_events(path)
            if events is None:
                rows.append(dict(run=run, status='missing', error='effort.json not recorded'))
            else:
                rows.append(dict(run=run, status='ok', **_measure(events, run)))
        except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
            rows.append(dict(run=str(raw), status='error', error=str(exc)))
    measured = [r for r in rows if r['status'] == 'ok']
    handoffs = [r for r in measured if r['first_handoff'] is not None]
    attributions = [e for r in measured for e in r['attributions']]
    reasons, minutes_by_reason = {}, {}
    for row in measured:
        for reason, count in row['return_reasons'].items():
            reasons[reason] = reasons.get(reason, 0) + count
    for event in attributions:
        minutes_by_reason.setdefault(event['reason'], []).append(event['minutes'])
    first_accepted = sum(r['first_handoff']['accepted'] == 'yes' for r in handoffs)
    result = dict(
        unique_runs=len(rows), duplicates_skipped=duplicates, runs=rows,
        missing_runs=sum(r['status'] == 'missing' for r in rows),
        error_runs=sum(r['status'] == 'error' for r in rows),
        effort_missing_runs=len(rows) - sum(r['effort_events'] > 0 for r in measured),
        reason_minutes_missing_runs=len(rows) - sum(bool(r['attributions']) for r in measured),
        first_handoff=dict(measured_runs=len(handoffs), missing_runs=len(rows) - len(handoffs),
                           accepted=first_accepted if handoffs else None,
                           rejected=len(handoffs) - first_accepted if handoffs else None,
                           acceptance_pct=100 * first_accepted / len(handoffs) if handoffs else None),
        all_attempts=dict(observed=sum(r['handoff_attempts'] for r in handoffs) if handoffs else None,
                          accepted=sum(r['accepted_attempts'] for r in handoffs) if handoffs else None,
                          rejected=sum(r['rejected_attempts'] for r in handoffs) if handoffs else None,
                          measured_runs=len(handoffs), missing_runs=len(rows) - len(handoffs)),
        return_reasons=reasons, attributions=attributions,
        unattributed_events=sum(r['unattributed_events'] for r in measured),
        boundary='Observed synthetic events only; reason labels are self-reported, not proven causes or measured savings. '
                 'Absent handoff/effort records do not establish zero work. Aggregates may cover only part of the requested runs.')
    try:
        result['attributed_reason_minutes'] = {reason: _sum(values) for reason, values in minutes_by_reason.items()}
        result['observed_attributed_minutes'] = _sum([e['minutes'] for e in attributions])
        result['unattributed_minutes'] = _sum([r['unattributed_minutes'] for r in measured if r['unattributed_minutes'] is not None])
    except ValueError as exc:
        result.update(aggregation_error=str(exc), attributed_reason_minutes=None,
                      observed_attributed_minutes=None, unattributed_minutes=None)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args(argv)
    result = summarize(args.runs)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 2 if result['error_runs'] or result['missing_runs'] or result.get('aggregation_error') else 0


if __name__ == '__main__':
    raise SystemExit(main())

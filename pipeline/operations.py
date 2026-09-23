"""Local project status and portfolio review queue. No cached readiness or approvals.

Read-only by contract: status and portfolio never write into a run directory (not even a
lock file), so they are safe to point at committed evidence such as runs/tier3.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ''):  # allow `python3 pipeline/operations.py` as well as `-m pipeline.operations`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import agency, approval, delivery, gates, revisions  # noqa: E402
from pipeline.records import PathLike  # noqa: E402

#: Review order of the portfolio queue: the most urgent stage first.
STAGE_PRIORITY = {'error': 0, 'blocked': 1, 'brief_approval': 2, 'creative_selection': 3, 'creative_review': 4,
                  'ready_to_release': 5}
PORTFOLIO_BOUNDARY = ('Current local checks, not semantic certification. Read next_actions and notices; '
                      'role labels are not assigned staff identities.')


def status(run: PathLike) -> dict[str, Any]:
    """One run's stage, next actions, blockers and notices — read-only, never cached.

    Input problems (a missing or invalid run, a corrupt record, a refused brief) become the
    `error` stage; any other exception is a bug and propagates.
    """
    run = Path(run).resolve()
    result: dict[str, Any] = {'run': str(run), 'stage': 'error', 'next_actions': [], 'blockers': [], 'notices': []}
    try:
        if not run.is_dir():
            raise ValueError('Run directory does not exist')
        # Read-only: a status check must never create .run.lock in an evidence folder.
        with revisions.read_lock(run):
            brief = agency.read_run(run)
            result.update(project_id=brief['meta']['project_id'], client_id=brief['meta']['client_id'])
            result['withdrawals'] = len(revisions.load(run/'approval_withdrawals.json', []))
            result['release_count'] = len(revisions.load(run/'releases.json', []))
            audit = agency.audit(run, persist=False)
            result.update(blockers=audit['blockers'], notices=audit['notices'])
            if audit['blockers']:
                result['stage'] = 'blocked'
                result['next_actions'] = audit['blockers']
                return result
            try:
                approval.require_current_approval(run)
                if brief['signoff']['status'] != 'signed_off':
                    raise ValueError('Brief must be signed off by the account lead')
            except ValueError as exc:
                result.update(stage='brief_approval',
                              next_actions=[str(exc), 'Account lead: review and approve the current brief.'])
                return result
            if not (run/'creative_draft.json').exists():
                result.update(stage='creative_selection',
                              next_actions=['Operator: register the selected creative draft and assets.'])
                return result
            try:
                delivery.current_draft(run)
            except ValueError as exc:
                result.update(stage='creative_selection',
                              next_actions=[str(exc), 'Operator: register an updated creative selection.'])
                return result
            try:
                delivery.require_creative_approval(run)
            except ValueError as exc:
                result.update(stage='creative_review', next_actions=[
                    str(exc), 'Creative lead and traffic: check the selected files and specifications, then approve.'])
                return result
            result.update(stage='ready_to_release',
                          next_actions=['Operator: create a new delivery package and verify it against this run.'])
            return result
    except (ValueError, OSError, gates.GateError) as exc:
        result.update(stage='error', blockers=[str(exc)],
                      next_actions=['Operator: repair or initialize this run before review.'])
        return result


def portfolio(runs: Iterable[PathLike]) -> dict[str, Any]:
    """Status of each distinct run, most urgent stage first, with per-stage counts."""
    unique = list(dict.fromkeys(str(Path(run).resolve()) for run in runs))
    projects = [status(run) for run in unique]
    projects.sort(key=lambda item: (STAGE_PRIORITY[item['stage']], item['run']))
    return {'projects': projects, 'counts': dict(Counter(p['stage'] for p in projects)),
            'boundary': PORTFOLIO_BOUNDARY}


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: print the status/portfolio JSON; exit 2 when any run is in error or blocked."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+',
                        help='Explicit run directories; one for project status, several for a portfolio')
    args = parser.parse_args(argv)
    result = portfolio(args.runs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if any(p['stage'] in ('error', 'blocked') for p in result['projects']) else 0


if __name__ == '__main__':
    raise SystemExit(main())

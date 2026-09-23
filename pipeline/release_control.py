"""Verify delivery files and record human withdrawal; no remote recall or sending."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pipeline import revisions


def verify(package, run=None):
    """Standalone hashes show integrity only; run receipt establishes local provenance."""
    package = Path(package).resolve()
    errors = []
    receipt_matched = None
    withdrawn = False
    try:
        manifest_path = package/'release.json'
        if manifest_path.is_symlink():
            raise ValueError('Release manifest cannot be a symlink')
        manifest = revisions.load(manifest_path)
        if not isinstance(manifest, dict) or manifest.get('status') != 'APPROVED FOR DELIVERY':
            raise ValueError('Missing or invalid release manifest')
        files = manifest.get('files')
        if not isinstance(files, dict) or not {'creative.md', 'deliverables.json'} <= files.keys():
            raise ValueError('Manifest must list creative.md and deliverables.json')
        for name, sha in files.items():
            if (not name or Path(name).name != name or '/' in name or '\\' in name
                    or name in ('.', '..', 'release.json') or not isinstance(sha, str)
                    or not re.fullmatch('[0-9a-f]{64}', sha)):
                raise ValueError('Unsafe filename or hash in release manifest')
            path = package/name
            if path.is_symlink() or not path.is_file() or revisions.file_hash(path) != sha:
                errors.append(f'{name}: missing, changed or redirected')
        if {p.name for p in package.iterdir()} != set(files) | {'release.json'}:
            errors.append('Package contains extra or missing entries')
        if run is not None:
            run = Path(run)
            manifest_hash = revisions.file_hash(manifest_path)
            receipts = revisions.load(run/'releases.json', [])
            receipt_matched = any(r.get('manifest_sha256') == manifest_hash for r in receipts)
            if not receipt_matched:
                errors.append('Package has no matching originating-run receipt')
            for event in revisions.load(run/'approval_withdrawals.json', []):
                if any(r.get('manifest_sha256') == manifest_hash for r in event['affected_releases']):
                    withdrawn = True
            if withdrawn:
                errors.append('Approval was withdrawn for this release; do not use')
        return {
            'valid': not errors,
            'errors': errors,
            'receipt_matched': receipt_matched,
            'withdrawn': withdrawn,
            'boundary': 'File integrity only without --run. Matching local receipts are not authenticated '
            'signatures. Consult the run for withdrawal status.',
        }
    except (ValueError, OSError, TypeError, KeyError) as exc:
        return {
            'valid': False,
            'errors': errors + [str(exc)],
            'receipt_matched': receipt_matched,
            'withdrawn': withdrawn,
        }


def withdraw(run, actor, reason):
    if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError('Named human actor and withdrawal reason required')
    run = Path(run)
    with revisions.run_lock(run):
        approvals = {
            name: revisions.file_hash(run / name)
            for name in ('approval.json', 'creative_approval.json')
            if (run / name).is_file()
        }
        receipts = revisions.load(run/'releases.json', [])
        if not approvals and not receipts:
            raise ValueError('No active approval or recorded release to withdraw')
        event = {'actor': actor, 'reason': reason, 'at': revisions.timestamp(),
                 'approval_hashes': approvals, 'affected_releases': receipts}
        # Persist recall information first; a crash must not leave a release unmarked.
        events = revisions.load(run/'approval_withdrawals.json', [])
        revisions.write_json(run/'approval_withdrawals.json', events + [event])
        revisions.append_audit(run, 'approval_withdrawn', actor,
                               record={'file': 'approval_withdrawals.json', 'entry': event},
                               details={'reason': reason, 'withdrawn': sorted(approvals),
                                        'affected_releases': len(receipts)})
        revisions.archive(run, list(approvals))
        return event


def verify_log(run: Path) -> dict:
    """Integrity of the run's hash-chained decision log (revisions.verify_audit_log), plus the
    release receipts whose package is not at its recorded path (reconciliation, not an error)."""
    run = Path(run)
    problems = revisions.verify_audit_log(run)
    path = run / revisions.AUDIT_LOG
    lines = path.read_text(encoding='utf-8').splitlines() if path.is_file() else []
    try:
        aborted = {(e.get('details') or {}).get('manifest_sha256') for e in revisions.read_audit_log(run)
                   if e.get('event') == 'creative_release_aborted'}
    except ValueError:
        aborted = set()
    receipts = revisions.load(run / 'releases.json', [])
    # Reconciliation view, not an integrity error: a receipt whose package is not where it was
    # released (moved on purpose, or a release that crashed before the package appeared).
    unplaced = [{'path': r.get('path'), 'manifest_sha256': r.get('manifest_sha256'),
                 'aborted': r.get('manifest_sha256') in aborted}
                for r in (receipts if isinstance(receipts, list) else [])
                if isinstance(r, dict) and not (Path(str(r.get('path'))) / 'release.json').is_file()]
    return {'valid': not problems, 'errors': problems, 'entries': len(lines),
            'receipts_without_package': unplaced,
            'boundary': 'Detects edited, removed, reordered or unlogged decision records. Names are '
                        'typed by people and are not authenticated; this is tamper evidence, not a signature.'}


def require_not_withdrawn(run, *, include_creative=False):
    """Also catches a crash between persisting withdrawal and archiving approval."""
    run = Path(run)
    names = ('approval.json', 'creative_approval.json') if include_creative else ('approval.json',)
    hashes = {name: revisions.file_hash(run/name) for name in names if (run/name).is_file()}
    for event in revisions.load(run/'approval_withdrawals.json', []):
        for name, sha in event['approval_hashes'].items():
            if hashes.get(name) == sha:
                raise ValueError('Human approval was withdrawn; obtain fresh review and approval')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    check = subs.add_parser('verify')
    check.add_argument('package', type=Path)
    check.add_argument('--run', type=Path)
    revoke = subs.add_parser('withdraw')
    revoke.add_argument('run', type=Path)
    revoke.add_argument('--actor', required=True)
    revoke.add_argument('--reason', required=True)
    log = subs.add_parser('verify-log', help='Check the run audit log chain and that every decision record is logged')
    log.add_argument('run', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            result = verify(args.package, args.run)
        elif args.command == 'verify-log':
            result = verify_log(args.run)
        else:
            result = withdraw(args.run, args.actor, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('valid') is False else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'release-control: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())

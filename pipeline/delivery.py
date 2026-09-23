"""Human-approved creative delivery. Generated content starts as a reviewable draft.

The historic shadow-only boundary was replaced by the user's 2026-09-20 decision.
No command sends anything to a client; release creates a local, inspectable package.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Union

from pipeline import agency, creative, gates, revisions, spec_catalog
from pipeline.approval import require_current_approval
from pipeline.money import money_figures
from pipeline.release_control import require_not_withdrawn

REF = re.compile(r'\[brief:([a-z_]+):(\d+)\]')
CHECKS = ('all_facts_cited', 'qualifiers', 'mandatories', 'brand_voice', 'deliverables', 'rights_and_permissions', 'client_safe')
ASSET_TYPES = {'.png', '.jpg', '.jpeg', '.webp', '.pdf', '.mp4', '.mov', '.svg'}


def inspect_creative(text: str, brief: dict) -> tuple:
    """(errors, claims) for a creative text: brief refs resolve, mandatories verbatim, no new money."""
    errors, claims = [], []
    tags = re.findall(r'\[brief:[^\]]*\]', text)
    if not tags:
        errors.append('Creative needs factual references to canonical brief entries')
    for tag in tags:
        match = REF.fullmatch(tag)
        if not match or match[1] not in gates.BRIEF_FIELDS or int(match[2]) >= len(brief.get(match[1]) or []):
            errors.append(f'Unknown creative reference {tag}')
    for line in text.splitlines():
        refs = []
        for field, index in REF.findall(line):
            if field in gates.BRIEF_FIELDS and int(index) < len(brief.get(field) or []):
                entry = brief[field][int(index)]
                refs.append({'field': field, 'index': int(index), 'content': entry['content'], 'qualifier': entry.get('qualifier')})
        if refs:
            claims.append({'text': line, 'references': refs})
    for index, entry in enumerate(brief.get('mandatories') or []):
        if entry['content'] not in text:
            errors.append(f'Missing verbatim mandatory {index}')
    # Numeric budget invention remains a failure even if other numbers are present.
    brief_content = '\n'.join(e.get('content', '') for f in gates.BRIEF_FIELDS for e in brief.get(f) or [])
    if money_figures(text) - money_figures(brief_content):
        errors.append('Creative contains a currency amount absent from canonical brief content')
    return errors, claims


def context(run: Path) -> dict:
    """The signed-off brief of a run whose brief approval is current and whose audit has no blockers."""
    require_current_approval(run)
    brief = agency.read_run(run)
    if brief['signoff']['status'] != 'signed_off':
        raise ValueError('Canonical brief is not signed off')
    result = agency.audit(run)
    if result['blockers']:
        raise ValueError('Brief audit blocks delivery: ' + '; '.join(result['blockers']))
    return brief


def spec_table(run):
    item = revisions.load(run / 'input_snapshot.json', {}).get('channel_specs')
    return creative.load_spec_table(Path(item['path']) if item else None)


def register(run, draft_path, actor, assets=()):
    if not actor.strip():
        raise ValueError('Named registering operator required')
    brief = context(run)
    text = Path(draft_path).read_text(encoding='utf-8')
    errors, claims = inspect_creative(text, brief)
    if errors:
        raise ValueError('; '.join(errors))
    # A historical shadow output can be submitted for review as a NEW draft. Its
    # original file and historic evaluation status are never overwritten.
    lines = text.splitlines()
    if lines and ('SHADOW MODE' in lines[0] or 'CREATIVE DRAFT' in lines[0]):
        lines = lines[1:]
    text = '> CREATIVE DRAFT — requires creative-lead approval before release.\n' + '\n'.join(lines).lstrip('\n') + '\n'
    payloads = [('creative.md', text.encode('utf-8'))]
    seen = {'creative.md'}
    for source in map(Path, assets):
        if source.suffix.lower() not in ASSET_TYPES or source.name in seen:
            raise ValueError('Assets need unique names and supported image/video/PDF extensions')
        if source.is_symlink() or not source.is_file():
            raise ValueError('Asset must be a regular file')
        if source.suffix.lower() == '.svg':
            raise ValueError('Rasterize SVG assets before delivery; active SVG content is not packaged')
        seen.add(source.name)
        payloads.append((source.name, source.read_bytes()))
    identity = revisions.digest({name: hashlib.sha256(data).hexdigest() for name, data in payloads})
    root = run / 'creative_versions' / identity
    root.mkdir(parents=True, exist_ok=True)
    for name, data in payloads:
        target = root / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Stored creative revision is modified')
        if not target.exists():
            with target.open('xb') as handle:
                handle.write(data)
    revisions.archive(run, ['creative_draft.json', 'creative_approval.json'], copy_only=True)
    record = {'revision': identity, 'brief_fingerprint': revisions.fingerprint(run), 'registered_by': actor,
              'registered_at': revisions.timestamp(), 'claims': claims,
              'files': [{'file': str((root/name).relative_to(run)), 'name': name, 'sha256': hashlib.sha256(data).hexdigest()} for name, data in payloads]}
    revisions.write_json(run / 'creative_draft.json', record)
    revisions.append_audit(run, 'creative_registered', actor, record='creative_draft.json',
                           details={'revision': identity})
    return record


def _separation(run, approver, draft, solo_rehearsal=False):
    """Owner decision 2026-09-22 #3: the creative approver is neither the person who registered
    the draft nor the brief signer. A synthetic rehearsal may waive it explicitly (recorded)."""
    registrant = draft.get('registered_by')
    signer = revisions.load(run / 'approval.json', {}).get('actor')
    if solo_rehearsal:
        return agency.solo_rehearsal_waiver(run, ('creative_registrant', 'creative_approver', 'brief_signer'))
    agency.require_distinct('creative registrant', registrant, 'creative approver', approver)
    agency.require_distinct('brief signer', signer, 'creative approver', approver)
    return {'enforced': ['creative_registrant != creative_approver', 'brief_signer != creative_approver']}


def _recheck_separation(run, approval, draft):
    """Release-time re-check from the records themselves, so a hand-edited record cannot slip
    a same-person approval through. A recorded waiver must still be valid (synthetic data)."""
    separation = approval.get('separation_of_duties') or {}
    if separation.get('waived') == 'solo_rehearsal':
        agency.solo_rehearsal_waiver(run, separation.get('roles') or ())
    else:
        _separation(run, approval.get('actor'), draft)
    brief_approval = revisions.load(run / 'approval.json', {})
    if (brief_approval.get('separation_of_duties') or {}).get('waived') == 'solo_rehearsal':
        agency.solo_rehearsal_waiver(run, ('language_attester', 'brief_signer'))
    else:
        agency.require_distinct('language/source reviewer', revisions.load(run / 'language_review.json', {}).get('actor'),
                                'brief signer', brief_approval.get('actor'))


def current_draft(run):
    record = revisions.load(run / 'creative_draft.json', {})
    if record.get('brief_fingerprint') != revisions.fingerprint(run) or not record.get('files'):
        raise ValueError('Creative draft is missing or based on a stale brief revision')
    names = [item.get('name', '') for item in record['files']]
    if (not names or names[0] != 'creative.md' or len(names) != len(set(names))
            or any(not name or Path(name).name != name or '/' in name or '\\' in name for name in names)
            or any(Path(name).suffix.lower() not in (ASSET_TYPES - {'.svg'}) for name in names[1:])):
        raise ValueError('Invalid creative package filename or asset type')
    revision = record.get('revision', '')
    if not re.fullmatch(r'[0-9a-f]{64}', revision):
        raise ValueError('Invalid creative revision')
    hashes = {}
    for item in record['files']:
        relative = Path('creative_versions') / revision / item['name']
        path = run / relative
        if (item['file'] != str(relative) or path.is_symlink()
                or path.parent.is_symlink() or path.parent.parent.is_symlink()):
            raise ValueError('Creative file is not part of the registered revision')
        path = path.resolve()
        if run.resolve() not in path.parents or not path.is_file() or revisions.file_hash(path) != item['sha256']:
            raise ValueError('Creative file missing, changed or outside the run')
        hashes[item['name']] = revisions.file_hash(path)
    if revisions.digest(hashes) != revision:
        raise ValueError('Creative revision does not match the registered payloads')
    return record


def approve(run: Path, actor: str, notes: str, checks: Union[list, tuple, set],
            solo_rehearsal: bool = False) -> dict:
    """Record a named creative lead's approval of the current draft (every review check required)."""
    if not actor.strip() or not notes.strip() or set(checks) != set(CHECKS):
        raise ValueError('Named creative lead, notes and every creative review check are required')
    brief = context(run)
    record = current_draft(run)
    rows = revisions.load(run / 'agency_inputs.json')['deliverables']
    problems = spec_catalog.validate(spec_table(run), selected_ids=[row['spec_id'] for row in rows])
    text = (run / record['files'][0]['file']).read_text(encoding='utf-8')
    errors, _ = inspect_creative(text, brief)
    selected = {row['spec_id'] for row in rows}
    selected_table = {'specs': [row for row in spec_table(run)['specs'] if row['id'] in selected]}
    errors += creative.check_creative_brief(run / record['files'][0]['file'], selected_table, mode='draft',
                                          brief=brief)
    if problems or errors:
        raise ValueError('; '.join(problems + errors))
    separation = _separation(run, actor, record, solo_rehearsal)
    revisions.require_intact_audit_log(run)
    revisions.archive(run, ['creative_approval.json'], copy_only=True)
    approval = {'actor': actor, 'notes': notes, 'checks': {key: True for key in CHECKS},
                'approved_at': revisions.timestamp(), 'draft_sha256': revisions.file_hash(run / 'creative_draft.json'),
                'brief_approval_sha256': revisions.file_hash(run / 'approval.json'),
                'language_review_sha256': revisions.file_hash(run / 'language_review.json'),
                'separation_of_duties': separation}
    revisions.write_json(run / 'creative_approval.json', approval)
    revisions.append_audit(run, 'creative_approved', actor, record='creative_approval.json',
                           details={'revision': record['revision'], 'separation_of_duties': separation})
    return approval


def require_creative_approval(run: Path) -> tuple:
    """Validate current creative selection, approval bindings and catalog freshness."""
    require_not_withdrawn(run, include_creative=True)
    record = current_draft(run)
    approval = revisions.load(run / 'creative_approval.json', {})
    if approval:
        if not all(isinstance(approval.get(key), str) and approval[key].strip()
                   for key in ('actor', 'notes', 'approved_at')):
            raise ValueError('Creative approval metadata is incomplete; obtain fresh approval')
        try:
            approved_at = datetime.fromisoformat(approval['approved_at'].replace('Z', '+00:00'))
            if approved_at.utcoffset() is None:
                raise ValueError('Timestamp needs a timezone')
        except ValueError as exc:
            raise ValueError('Creative approval metadata has an invalid timestamp') from exc
    if (not approval.get('actor') or not all(approval.get('checks', {}).get(key) is True for key in CHECKS)
            or approval.get('draft_sha256') != revisions.file_hash(run / 'creative_draft.json')
            or approval.get('brief_approval_sha256') != revisions.file_hash(run / 'approval.json')
            or approval.get('language_review_sha256') != revisions.file_hash(run / 'language_review.json')):
        raise ValueError('Missing or stale creative approval')
    rows = revisions.load(run / 'agency_inputs.json')['deliverables']
    problems = spec_catalog.validate(spec_table(run), selected_ids=[row['spec_id'] for row in rows])
    if problems:
        raise ValueError('; '.join(problems))
    return record, approval, rows


def release(run, output, actor):
    """Create the approved local package. `actor` is the named person producing it — recorded
    in release.json, in the run's receipt and in the audit log."""
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError('Named releasing operator required (--actor)')
    context(run)
    record, approval, rows = require_creative_approval(run)
    _recheck_separation(run, approval, record)
    revisions.require_intact_audit_log(run)
    output = Path(output).resolve()
    if output.exists() or output == run.resolve() or run.resolve() in output.parents:
        raise ValueError('Release output must be a new directory outside the run')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.brief-delivery-', dir=output.parent))
    try:
        for item in record['files']:
            data = (run / item['file']).read_bytes()
            if item['name'] == 'creative.md':
                body = data.decode('utf-8').split('\n', 1)[1]
                body = REF.sub('', body)
                data = ('# Approved creative brief\n\n' + body.lstrip()).encode('utf-8')
            (staging / item['name']).write_bytes(data)
        # No raw client evidence, internal reference paths, audit comments or logs.
        public_rows = [{k: v for k, v in row.items() if k in ('id','spec_id','quantity','languages','deadline','owner','approval_owner','dependencies','format','file_type','resolution','aspect_ratio','duration_seconds')} for row in rows]
        revisions.write_json(staging / 'deliverables.json', {'status': 'APPROVED FOR DELIVERY', 'deliverables': public_rows})
        brief = agency.read_run(run)
        manifest = {'status': 'APPROVED FOR DELIVERY', 'project_id': brief['meta']['project_id'],
                    'creative_revision': record['revision'], 'approved_by': approval['actor'],
                    'approved_at': approval['approved_at'], 'released_by': actor,
                    'files': {p.name: revisions.file_hash(p) for p in staging.iterdir() if p.is_file()}}
        revisions.write_json(staging / 'release.json', manifest)
        # Exclusive creation protects earlier deliveries; files are complete before rename.
        with revisions.run_lock(output.parent):
            if output.exists():
                raise ValueError('Release destination already exists')
            staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    releases = revisions.load(run / 'releases.json', [])
    receipt = {'path': str(output), 'manifest_sha256': revisions.file_hash(output/'release.json'),
               'at': revisions.timestamp(), 'released_by': actor}
    releases.append(receipt)
    revisions.write_json(run / 'releases.json', releases)
    revisions.append_audit(run, 'creative_released', actor, record={'file': 'releases.json', 'entry': receipt},
                           details={'manifest_sha256': receipt['manifest_sha256'], 'revision': record['revision']})
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for name in ('register', 'approve', 'release'):
        sub = subs.add_parser(name)
        sub.add_argument('run', type=Path)
        sub.add_argument('--actor', required=True)
        if name == 'register':
            sub.add_argument('--draft', type=Path, required=True)
            sub.add_argument('--asset', type=Path, action='append', default=[])
        if name == 'approve':
            sub.add_argument('--notes', required=True)
            sub.add_argument('--checks', nargs='+', choices=CHECKS, required=True)
            sub.add_argument('--solo-rehearsal', action='store_true',
                             help='Waive separation of duties for a SYNTHETIC rehearsal only; recorded '
                                  'in creative_approval.json and the audit log')
        if name == 'release':
            sub.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run = args.run.resolve()
        with revisions.run_lock(run):
            if args.command == 'register':
                result = register(run, args.draft, args.actor, args.asset)
            elif args.command == 'approve':
                result = approve(run, args.actor, args.notes, args.checks, solo_rehearsal=args.solo_rehearsal)
            else:
                result = str(release(run, args.output, args.actor))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, gates.GateError) as exc:
        print(f'delivery: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

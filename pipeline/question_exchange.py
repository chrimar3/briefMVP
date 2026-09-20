"""Local, version-bound clarification proposals and revision impact reports.

No external messaging, canonical edits, triage decisions or implicit approvals.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from pipeline import agency, clarifications, quality, revisions


PACK_VERSION = 1


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value


def _run(path):
    path = Path(path).resolve()
    if not path.is_dir() or not (path / 'brief.json').is_file():
        raise ValueError('Run must already exist with brief.json')
    return path


def _identity(brief):
    meta = brief.get('meta', {})
    return {key: _text(meta.get(key), key) for key in ('client_id', 'project_id')}


def _binding(run):
    return revisions.digest(str(run.resolve()))


def _read(value):
    if isinstance(value, (str, Path)):
        value = revisions.load(value)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def _directory(run, name):
    path = run / 'question_exchange' / name
    if not path.resolve().is_relative_to(run):
        raise ValueError('Exchange directory must remain inside the run')
    return path


def _create_json(path, value):
    """Publish a complete file atomically with hard-link no-clobber semantics."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.question-exchange-', delete=False) as handle:
            temp = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise ValueError(f'Refusing to overwrite existing file: {path}') from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _snapshot(run):
    snapshot = revisions.load(run / 'input_snapshot.json')
    if not isinstance(snapshot, dict):
        raise ValueError('Run needs an input_snapshot.json baseline')
    sources = {}
    for key, record in snapshot.items():
        if key.startswith('source:'):
            if (not isinstance(record, dict) or not isinstance(record.get('sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])
                    or not isinstance(record.get('path'), str) or not record['path'].strip()):
                raise ValueError(f'Invalid source snapshot: {key}')
            sources[key] = record
    if not sources:
        raise ValueError('Source baseline is missing; source impact cannot be established')
    return sources


def _current(run):
    brief = agency.read_run(run)
    _snapshot(run)
    revisions.verify_inputs(run)
    revisions.verify_evidence(run)
    decisions = revisions.load(run / 'clarifications.json', {})
    if not isinstance(decisions, dict):
        raise ValueError('Invalid clarification decisions')
    return brief, clarifications.queue(brief, decisions)


def _questions(items, selected=None):
    unresolved = {item['id']: item for item in items
                  if not item['decision'] or item['decision'].get('status') == 'open'}
    if selected is None:
        selected = list(unresolved)
    if not isinstance(selected, (list, tuple)) or not all(isinstance(i, str) for i in selected):
        raise ValueError('question_ids must be a list of queue IDs')
    if len(selected) != len(set(selected)):
        raise ValueError('Duplicate selected question IDs')
    if not selected:
        raise ValueError('No unresolved questions selected')
    questions = []
    for ident in selected:
        if ident not in unresolved:
            raise ValueError(f'Unknown or no longer unresolved question: {ident}')
        item = unresolved[ident]
        decision = item['decision'] or {}
        owner = _text(decision.get('owner'), f'Question {ident} triage owner')
        if decision.get('priority') not in ('blocking', 'nonblocking'):
            raise ValueError(f'Question {ident} needs explicit blocking/nonblocking triage priority')
        questions.append({'id': ident, 'field': item['field'],
                          'question': _text(item['question'], 'question'),
                          'owner': owner, 'priority': decision['priority']})
    return questions


def export_questions(run, output, question_ids=None):
    """Export unresolved, explicitly triaged questions; retain a local pack receipt."""
    run, output = _run(run), Path(output).absolute()
    with revisions.run_lock(run):
        if output.exists() or output.is_symlink():
            raise ValueError(f'Refusing to overwrite existing file: {output}')
        # Never create a missing canonical/approval/input file through --output.
        resolved_output = output.resolve()
        if (resolved_output.is_relative_to(run)
                and not resolved_output.is_relative_to(run / 'question_exports')):
            raise ValueError('Export outside the run or inside RUN/question_exports; run artifacts are reserved')
        brief, items = _current(run)
        pack = {'version': PACK_VERSION, 'identity': _identity(brief),
                'run_binding': _binding(run), 'fingerprint': revisions.fingerprint(run),
                'created_at': revisions.timestamp(), 'questions': _questions(items, question_ids)}
        pack['pack_id'] = revisions.digest(pack)
        receipt = _directory(run, 'packs') / (pack['pack_id'] + '.json')
        _create_json(receipt, pack)
        # A failed export may leave an unused receipt; neither file is ever overwritten.
        _create_json(output, pack)
    return pack


def _validate_pack(run, pack, brief, items):
    ident = pack.get('pack_id')
    if not isinstance(ident, str) or not re.fullmatch(r'[0-9a-f]{64}', ident):
        raise ValueError('Invalid pack_id')
    if pack.get('version') != PACK_VERSION:
        raise ValueError('Unsupported pack version')
    if revisions.digest({k: v for k, v in pack.items() if k != 'pack_id'}) != ident:
        raise ValueError('Pack was modified; use the original exported pack')
    receipt = revisions.load(_directory(run, 'packs') / (ident + '.json'))
    if receipt != pack:
        raise ValueError('Pack is not registered for this run or differs from its receipt')
    if pack.get('identity') != _identity(brief) or pack.get('run_binding') != _binding(run):
        raise ValueError('Pack project identity or originating run does not match')
    if pack.get('fingerprint') != revisions.fingerprint(run):
        raise ValueError('Stale pack: current run version differs; export again')
    questions = pack.get('questions')
    if not isinstance(questions, list) or not all(isinstance(q, dict) for q in questions):
        raise ValueError('Invalid pack questions')
    if questions != _questions(items, [q.get('id') for q in questions]):
        raise ValueError('Pack questions no longer match current unresolved triage')


def _proposal_records(run):
    """Validate immutable receipts, including attribution and the registered pack."""
    records = []
    for path in sorted(_directory(run, 'proposals').glob('*.json')):
        record = _read(path)
        ident = record.get('proposal_id')
        if (path.stem != ident or record.get('status') != 'proposed'
                or revisions.digest({k: v for k, v in record.items() if k != 'proposal_id'}) != ident):
            raise ValueError(f'Corrupt proposal receipt: {path.name}')
        _text(record.get('actor'), 'proposal actor')
        _text(record.get('recorded_at'), 'proposal recorded_at')
        pack_id = record.get('pack_id')
        if not isinstance(pack_id, str) or not re.fullmatch(r'[0-9a-f]{64}', pack_id):
            raise ValueError('Invalid proposal pack_id')
        pack = revisions.load(_directory(run, 'packs') / (pack_id + '.json'))
        if (not isinstance(pack, dict) or pack.get('pack_id') != pack_id
                or revisions.digest({k: v for k, v in pack.items() if k != 'pack_id'}) != pack_id
                or pack.get('version') != PACK_VERSION):
            raise ValueError('Missing or corrupt proposal pack receipt')
        if (record.get('run_binding') != _binding(run)
                or any(record.get(key) != pack.get(key) for key in ('run_binding', 'identity', 'fingerprint'))):
            raise ValueError('Proposal run, identity or fingerprint does not match its pack')
        questions = pack.get('questions')
        if not isinstance(questions, list) or not all(isinstance(q, dict) and isinstance(q.get('id'), str) for q in questions):
            raise ValueError('Invalid proposal pack questions')
        known = {q['id'] for q in questions}
        rows, seen = record.get('replies'), set()
        if not isinstance(rows, list) or not rows:
            raise ValueError('Corrupt proposal replies')
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'question_id', 'text', 'evidence'}:
                raise ValueError('Invalid proposal reply fields')
            question_id = _text(row['question_id'], 'proposal question_id')
            if question_id not in known or question_id in seen:
                raise ValueError('Unknown or duplicate proposal question_id')
            seen.add(question_id)
            _text(row['text'], 'proposal reply text')
            evidence = row['evidence']
            if not isinstance(evidence, dict) or set(evidence) != {'source_ref', 'provided_by'}:
                raise ValueError('Invalid proposal evidence attribution')
            for key in evidence:
                _text(evidence[key], 'proposal evidence ' + key)
        records.append(record)
    return records


def _dismissed(run, records):
    proposals = {record['proposal_id']: record for record in records}
    dismissed = set()
    for path in sorted(_directory(run, 'dismissals').glob('*.json')):
        record = _read(path)
        ident = record.get('dismissal_id')
        if (path.stem != ident
                or revisions.digest({k: v for k, v in record.items() if k != 'dismissal_id'}) != ident):
            raise ValueError(f'Corrupt dismissal receipt: {path.name}')
        proposal_id = _text(record.get('proposal_id'), 'dismissal proposal_id')
        proposal = proposals.get(proposal_id)
        if (proposal is None or record.get('run_binding') != _binding(run)
                or record.get('fingerprint') != proposal['fingerprint']):
            raise ValueError('Dismissal does not match a registered proposal/run/version')
        for key in ('actor', 'reason', 'dismissed_at'):
            _text(record.get(key), 'dismissal ' + key)
        if proposal_id in dismissed:
            raise ValueError('Duplicate dismissal receipts')
        dismissed.add(proposal_id)
    return dismissed


def pending_proposals(run) -> list[dict]:
    """Validated current-version proposals without an explicit human dismissal.

    Read-only and safe to call inside an already-held run_lock. Approval/release
    callers must hold that lock across this check and their resulting mutation.
    Malformed receipts raise ValueError; callers must treat this as a blocker.
    """
    run = _run(run)
    fingerprint = revisions.fingerprint(run)
    records = _proposal_records(run)
    dismissed = _dismissed(run, records)
    result = [record for record in records if record['fingerprint'] == fingerprint
              and record['proposal_id'] not in dismissed]
    if revisions.fingerprint(run) != fingerprint:
        raise ValueError('Run changed while checking pending proposals; retry')
    return result


def dismiss(run, proposal_id, *, actor, reason):
    """Append an explicit human rejection; retain the proposal and canonical state."""
    run = _run(run)
    _text(actor, 'actor')
    _text(reason, 'reason')
    _text(proposal_id, 'proposal_id')
    with revisions.run_lock(run):
        records = _proposal_records(run)
        proposals = {record['proposal_id']: record for record in records}
        if proposal_id not in proposals:
            raise ValueError('Unknown proposal_id')
        if proposal_id in _dismissed(run, records):
            raise ValueError('Proposal is already dismissed')
        record = {'proposal_id': proposal_id, 'run_binding': _binding(run),
                  'fingerprint': proposals[proposal_id]['fingerprint'], 'actor': actor,
                  'reason': reason, 'dismissed_at': revisions.timestamp()}
        record['dismissal_id'] = revisions.digest(record)
        _create_json(_directory(run, 'dismissals') / (record['dismissal_id'] + '.json'), record)
    return record


def _prior_proposals(run, fingerprint):
    return {row['question_id'] for record in _proposal_records(run)
            if record['fingerprint'] == fingerprint for row in record['replies']}


def import_replies(run, pack, replies, actor):
    """Record a complete valid batch as proposals; duplicates reject the whole batch.

    pack/replies accept paths or JSON objects. Partial coverage of a pack is valid.
    Canonical brief, decisions, fingerprint and approval remain untouched.
    """
    run = _run(run)
    _text(actor, 'actor')
    with revisions.run_lock(run):
        pack, replies = _read(pack), _read(replies)
        brief, items = _current(run)
        _validate_pack(run, pack, brief, items)
        if set(replies) != {'pack_id', 'replies'} or replies['pack_id'] != pack['pack_id']:
            raise ValueError('Replies must name this pack_id and contain only pack_id/replies')
        rows = replies['replies']
        if not isinstance(rows, list) or not rows:
            raise ValueError('A nonempty replies list is required')
        known = {q['id'] for q in pack['questions']}
        seen = _prior_proposals(run, pack['fingerprint'])
        batch_ids = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'question_id', 'text', 'evidence'}:
                raise ValueError('Each reply requires only question_id, text and evidence')
            ident = _text(row['question_id'], 'question_id')
            if ident not in known:
                raise ValueError(f'Unknown question ID for this pack: {ident}')
            if ident in seen or ident in batch_ids:
                raise ValueError(f'Duplicate reply: question {ident} already has a proposal for this version')
            batch_ids.add(ident)
            _text(row['text'], 'reply text')
            evidence = row['evidence']
            if not isinstance(evidence, dict) or set(evidence) != {'source_ref', 'provided_by'}:
                raise ValueError('Reply evidence needs source_ref and provided_by attribution')
            _text(evidence['source_ref'], 'evidence source_ref')
            _text(evidence['provided_by'], 'evidence provided_by')
        record = {'version': PACK_VERSION, 'status': 'proposed', 'pack_id': pack['pack_id'],
                  'identity': pack['identity'], 'run_binding': pack['run_binding'],
                  'fingerprint': pack['fingerprint'], 'actor': actor,
                  'recorded_at': revisions.timestamp(), 'replies': rows,
                  'pending_question_ids': sorted(known - seen - batch_ids),
                  'required_review': 'Verify reply attribution and meaning; ingest authorized synthetic evidence, '
                                     'revise and review the brief explicitly. No question was resolved or work approved.'}
        record['proposal_id'] = revisions.digest(record)
        _create_json(_directory(run, 'proposals') / (record['proposal_id'] + '.json'), record)
    return record


def _drift(sources):
    result = {}
    # Match verify_inputs: resolved, nonrecursive *.md files in each tracked
    # source directory. Keep membership changes separate from per-source hashes.
    recorded = {Path(source['path']).resolve() for source in sources.values()}
    for directory in sorted({path.parent for path in recorded}, key=str):
        expected = {path for path in recorded if path.parent == directory}
        current = {path.resolve() for path in directory.glob('*.md') if path.is_file()}
        if current != expected:
            result['source-directory:' + str(directory)] = {
                'status': 'membership_changed', 'directory': str(directory),
                'added_paths': sorted(str(path) for path in current - expected),
                'removed_paths': sorted(str(path) for path in expected - current),
            }
    for key, source in sources.items():
        path = Path(source['path'])
        try:
            current = revisions.file_hash(path)
        except OSError:
            current = None
        if current != source['sha256']:
            result[key] = {'recorded_sha256': source['sha256'], 'current_sha256': current,
                           'status': 'missing_or_unreadable' if current is None else 'changed'}
    return result


def _evidence_by_field(brief):
    fields = {}
    for field, destination, refs in quality.destinations(brief):
        if refs:
            fields.setdefault(field, {})[destination] = refs
    return fields


def impact(before, after):
    """Compare canonical records and source baselines; report live drift separately."""
    before, after = _run(before), _run(after)
    with ExitStack() as stack:
        for run in sorted({before, after}, key=str):
            stack.enter_context(revisions.run_lock(run))
        old, new = agency.read_run(before), agency.read_run(after)
        if _identity(old) != _identity(new):
            raise ValueError('Impact requires the same client/project identity')
        old_sources, new_sources = _snapshot(before), _snapshot(after)
        hashes = lambda sources: {key: record['sha256'] for key, record in sources.items()}
        source_changes = revisions.changes(hashes(old_sources), hashes(new_sources))
        field_changes = revisions.changes(old, new)
        evidence_changes = revisions.changes(_evidence_by_field(old), _evidence_by_field(new))
        drift = {'before': _drift(old_sources), 'after': _drift(new_sources)}
        affected_sources = set(source_changes) | set(drift['before']) | set(drift['after'])
        affected_fields = sorted({field for brief in (old, new)
                                  for field, _, refs in quality.destinations(brief)
                                  if field and any('source:' + ref.get('source_id', '') in affected_sources for ref in refs)})
        reviews = []
        if field_changes:
            reviews.append('Review changed canonical fields, bilingual renders, downstream deliverables and creative; obtain fresh approval for any adopted revision.')
        if source_changes or any(drift.values()):
            reviews.append('Review added, changed or missing sources and their citations even when brief text is unchanged; re-extract or reconcile evidence before carrying decisions or approving.')
        if evidence_changes:
            reviews.append('Verify changed citation anchors, attribution and meaning against sources.')
        if 'open_questions' in field_changes or 'conflicts' in field_changes:
            reviews.append('Re-triage changed questions and conflicts explicitly; no prior resolution is inferred.')
        return {'identity': _identity(old), 'before_fingerprint': revisions.fingerprint(before),
                'after_fingerprint': revisions.fingerprint(after),
                'changed_fields': sorted(field_changes), 'field_changes': field_changes,
                'evidence_changes': evidence_changes, 'source_changes': source_changes,
                'source_drift': drift, 'source_affected_fields': affected_fields,
                'review_required': bool(reviews), 'required_review': reviews,
                'approval_effect': 'Informational only; no canonical record, decision or approval was changed.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    export.add_argument('run', type=Path)
    export.add_argument('output', type=Path)
    export.add_argument('--question-id', dest='question_ids', action='append')
    reply = commands.add_parser('import')
    reply.add_argument('run', type=Path)
    reply.add_argument('pack', type=Path)
    reply.add_argument('replies', type=Path)
    reply.add_argument('--actor', required=True)
    reject = commands.add_parser('dismiss')
    reject.add_argument('run', type=Path)
    reject.add_argument('proposal_id')
    reject.add_argument('--actor', required=True)
    reject.add_argument('--reason', required=True)
    compare = commands.add_parser('impact')
    compare.add_argument('before', type=Path)
    compare.add_argument('after', type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = {'export': export_questions, 'import': import_replies, 'impact': impact, 'dismiss': dismiss}[command](**args)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

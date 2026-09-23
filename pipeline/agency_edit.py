"""Attributed checklist and deliverable edits without hand-editing companion JSON."""

from __future__ import annotations

import argparse
import copy
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from pipeline import agency, gates, handover, quality, revisions
from pipeline.records import PathLike


def _required(**values: Any) -> None:
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{key} must be nonempty text')


def _context(run: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    brief = agency.read_run(run)
    inputs = revisions.load(run / 'agency_inputs.json')
    if not isinstance(inputs, dict):
        raise ValueError('Initialize agency_inputs first')
    if not isinstance(revisions.load(run / 'input_snapshot.json', {}), dict):
        raise ValueError('input_snapshot.json must be a JSON object')
    revisions.verify_inputs(run)
    return brief, inputs


def _evidence(brief: dict[str, Any], refs: Sequence[str]) -> list[dict[str, Any]]:
    if not refs:
        raise ValueError('At least one canonical FIELD:INDEX ref required')
    targets = {name: evidence for _, name, evidence in quality.destinations(brief)}
    evidence: list[dict[str, Any]] = []
    for ref in refs:
        match = re.fullmatch(r'([a-z_]+):(0|[1-9]\d*)', ref)
        if not match or match[1] not in gates.BRIEF_FIELDS:
            raise ValueError(f'Invalid canonical ref: {ref}')
        selected = targets.get(f'{match[1]}[{match[2]}]')
        if not selected or any(not all(r.get(k) for k in ('source_id', 'location', 'anchor')) for r in selected):
            raise ValueError(f'Ref is absent or has no complete evidence: {ref}')
        for item in selected:
            if item not in evidence:
                evidence.append(copy.deepcopy(item))
    return evidence


def _save(run: Path, inputs: dict[str, Any]) -> None:
    revisions.archive(run, ['agency_inputs.json'], copy_only=True)
    revisions.archive(run, ['approval.json', 'language_review.json', 'agency_audit.json', 'handover.json',
                            'creative_approval.json'])
    revisions.write_json(run / 'agency_inputs.json', inputs)


def checklist(run: PathLike, *, key: str, value: str, owner: str, actor: str, refs: Sequence[str]) -> dict[str, Any]:
    """Upsert a recognized profile answer with exact canonical evidence."""
    run = Path(run).resolve()
    _required(key=key, value=value, owner=owner, actor=actor)
    with revisions.run_lock(run):
        brief, inputs = _context(run)
        profiles = revisions.load(agency.PROFILES)['profiles']
        if not isinstance(profiles, dict):
            raise ValueError('Campaign profiles config must map profile names to checklists')
        profile = profiles.get(inputs.get('campaign_profile'), {})
        if key not in profile:
            raise ValueError(f'Unknown checklist key for campaign profile: {key}')
        row = {'prompt': profile[key], 'value': value, 'owner': owner,
               'evidence': _evidence(brief, refs), 'actor': actor,
               'updated_at': revisions.timestamp(), 'refs': list(refs)}
        inputs.setdefault('checklist', {})[key] = row
        _save(run, inputs)
    return row


def deliverable(run: PathLike, *, id: str, spec_id: str, quantity: int, languages: list[str], deadline: str,
                owner: str, approval_owner: str, actor: str, refs: Sequence[str],
                dependencies: Sequence[str] = (), duration_seconds: Optional[float] = None) -> dict[str, Any]:
    """Upsert by asset ID, copying spec-owned values without reinterpretation."""
    run = Path(run).resolve()
    _required(id=id, spec_id=spec_id, deadline=deadline, owner=owner,
              approval_owner=approval_owner, actor=actor)
    if (not isinstance(dependencies, (list, tuple))
            or any(not isinstance(v, str) or not v.strip() for v in dependencies)):
        raise ValueError('dependencies must contain nonempty text')
    with revisions.run_lock(run):
        brief, inputs = _context(run)
        snapshot = revisions.load(run / 'input_snapshot.json', {})
        binding = snapshot.get('channel_specs', {})
        if not isinstance(binding, dict):
            raise ValueError('input_snapshot.json channel_specs must be a JSON object')
        path = binding.get('path', gates.CONFIG_DIR / 'channel_specs.json')
        table = revisions.load(path)
        specs = table.get('specs', []) if isinstance(table, dict) else []
        if not all(isinstance(r, dict) for r in specs):
            raise ValueError('Channel spec catalog rows must be JSON objects')
        ids = [r.get('id') for r in specs]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate spec IDs in catalog')
        spec = next((r for r in specs if r.get('id') == spec_id), None)
        if spec is None:
            raise ValueError(f'Unknown spec_id: {spec_id}')
        for key in ('resolution', 'aspect_ratio', 'format', 'file_type'):
            _required(**{key: spec.get(key)})
        row = {k: copy.deepcopy(spec[k]) for k in
               ('channel', 'resolution', 'aspect_ratio', 'format', 'file_type', 'duration') if k in spec}
        row.update(id=id, spec_id=spec_id, quantity=quantity, languages=languages,
                   deadline=deadline, owner=owner, approval_owner=approval_owner,
                   dependencies=list(dependencies), evidence=_evidence(brief, refs),
                   actor=actor, updated_at=revisions.timestamp(), refs=list(refs))
        if duration_seconds is not None:
            row['duration_seconds'] = duration_seconds
        rows = inputs.setdefault('deliverables', [])
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            raise ValueError('agency_inputs.json deliverables must be a list of objects')
        matches = [i for i, item in enumerate(rows) if item.get('id') == id]
        if len(matches) > 1:
            raise ValueError('Duplicate deliverable IDs; repair companion record first')
        if matches:
            rows[matches[0]] = row
        else:
            rows.append(row)
        problems = handover.validate(rows, table, brief)
        if problems:
            raise ValueError('; '.join(problems))
        _save(run, inputs)
    return row


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: record one attributed checklist answer or deliverable; exit 2 with the reason on refusal."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('checklist', 'deliverable'):
        command = commands.add_parser(name)
        command.add_argument('run', type=Path)
        for flag in ('owner', 'actor'):
            command.add_argument('--' + flag, required=True)
        command.add_argument('--ref', dest='refs', action='append', required=True)
        if name == 'checklist':
            command.add_argument('--key', required=True)
            command.add_argument('--value', required=True)
        else:
            for flag in ('id', 'spec-id', 'deadline', 'approval-owner'):
                command.add_argument('--' + flag, required=True)
            command.add_argument('--quantity', type=int, required=True)
            command.add_argument('--language', dest='languages', action='append', required=True)
            command.add_argument('--dependency', dest='dependencies', action='append', default=[])
            command.add_argument('--duration-seconds', type=float)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'checklist':
            checklist(**args)
        else:
            deliverable(**args)
    except (ValueError, OSError, gates.GateError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())

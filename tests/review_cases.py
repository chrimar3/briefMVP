"""Portable renderer cases derived only from committed synthetic Tier 3 evidence.

The old tests depended on ignored runs/live and runs/evidence-20260729 folders.
Retain their scenarios (demo override/zero conflicts, complete fidelity evidence)
without depending on workstation-local captures or pretending these are new runs.
"""
import atexit
from functools import lru_cache
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[1]
_TEMP = TemporaryDirectory(prefix='brief-review-cases-')
atexit.register(_TEMP.cleanup)


@lru_cache(None)
def stored_run(name):
    if name == 'runs/tier3':
        return REPO/name
    if name not in ('runs/live', 'runs/evidence-20260729'):
        raise ValueError('Unknown synthetic review case')
    target = Path(_TEMP.name)/Path(name).name
    shutil.copytree(REPO/'runs/tier3', target)
    manifest_path = target/'run_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['project_dir'] = str(REPO/'fixtures/northlight_01')
    manifest['run_id'] = 'synthetic-renderer-' + target.name
    if name == 'runs/live':
        manifest['demo_profile'] = 'synthetic-demo'
        manifest['steps'].insert(0, {'number': 0, 'name': 'readiness_gate',
                                   'description': 'Synthetic demo refusal', 'status': 'refused_overridden'})
        brief_path = target/'brief.json'
        brief = json.loads(brief_path.read_text())
        brief['conflicts'] = []
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
    else:
        brief_path = target/'brief.json'
        brief = json.loads(brief_path.read_text())
        brief['signoff'] = {'status': 'draft'}
        for conflict in brief['conflicts']:
            conflict['status'] = 'open'
            conflict.pop('resolution', None)
            conflict.pop('resolved_by', None)
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    return target

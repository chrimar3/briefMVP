import atexit
import json
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: One definition of "frontmatter is the FIRST `---` block only" (agent bodies legitimately
#: contain `---` lines). The *parse* below stays independent on purpose: yaml.safe_load
#: verifies the frontmatter is real YAML, which the runtime's deliberately naive key:value
#: parser never checks.
from pipeline import agency, delivery, gates, revisions, spec_catalog  # noqa: E402
from pipeline.agents import _FRONTMATTER_RE  # noqa: E402


@pytest.fixture(autouse=True)
def _never_call_a_real_model(monkeypatch):
    """Hard stop on model calls from the test suite.

    Registering a stage handler made a previously-safe runner test start shelling out to
    `claude -p`, which hung the suite and would have spent real money. Tests exercise the gates
    around the models, never the models — so the binary is pointed at a name that cannot exist
    and any accidental invocation fails instantly and loudly.
    """
    from pipeline import agents

    monkeypatch.setattr(agents, "CLAUDE_BIN", "brief-builder-tests-must-not-call-a-model")
    # The `--version` probe is cached per binary; every test starts without a cached answer,
    # and never inherits the operator's live opt-in.
    monkeypatch.setattr(agents, "_CLI_VERSIONS", {})
    monkeypatch.delenv(agents.LIVE_ENV, raising=False)


#: Committed run evidence the suite reads but must never write into (not even a lock file).
COMMITTED_EVIDENCE = ("runs/tier3", "runs/voreas-prep-02", "runs/voreas-prep-03")
_LOCK_NAMES = (".run.lock", ".effort.lock")


def _evidence_lock_files() -> set:
    return {str(p.relative_to(REPO_ROOT)) for d in COMMITTED_EVIDENCE for name in _LOCK_NAMES
            for p in (REPO_ROOT / d).rglob(name)}


@pytest.fixture(scope="session", autouse=True)
def _committed_evidence_stays_untouched():
    """Fail the session if any test leaves a lock file in committed evidence.

    A read-only status check once created runs/tier3/.run.lock as an untracked file; read-only
    views now use revisions.read_lock, and this guard keeps it that way for every test.
    """
    before = _evidence_lock_files()
    yield
    created = sorted(_evidence_lock_files() - before)
    if created:
        pytest.fail(f"the test session created lock files in committed evidence: {created}")


#: The fake `claude` CLI (offline replay + subprocess-seam fault injection).
FAKE_CLAUDE = REPO_ROOT / "tools" / "replay" / "claude"


@pytest.fixture
def fake_claude(monkeypatch) -> Path:
    """Point the model seam at the fake CLI (absolute path: invoke runs from a neutral cwd).

    Overrides the autouse poison above for this test only; the fake makes no model call.
    """
    from pipeline import agents

    monkeypatch.setattr(agents, "CLAUDE_BIN", str(FAKE_CLAUDE))
    for name in ("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "BRIEF_BUILDER_FAKE_CLAUDE_ARGV", "BRIEF_BUILDER_REPLAY_RUN",
                 "BRIEF_BUILDER_FAKE_CLAUDE_VERSION"):
        monkeypatch.delenv(name, raising=False)
    return FAKE_CLAUDE


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_project(repo_root: Path) -> Path:
    return repo_root / "fixtures" / "northlight_01"


def split_frontmatter(path: Path):
    """Return (frontmatter_dict, body_str) for a Claude Code agent file."""
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.name}: no YAML frontmatter block at the top of the file"
    return yaml.safe_load(match.group(1)), match.group(2)


# -- synthetic review cases ----------------------------------------------------------------
# Portable renderer cases derived only from the committed synthetic Tier 3 evidence. They keep
# two scenarios older tests took from workstation-local captures, without pretending to be new
# runs: a demo-profile run (the readiness refusal was overridden; zero conflicts) and a draft
# run (not signed off, every conflict open).

#: The committed graded run, and the two derived case names `stored_run` accepts.
TIER3 = "runs/tier3"
SYNTHETIC_DEMO_CASE = "synthetic-demo-case"
SYNTHETIC_DRAFT_CASE = "synthetic-draft-case"
STORED_RUNS = (TIER3, SYNTHETIC_DEMO_CASE, SYNTHETIC_DRAFT_CASE)

_CASES_DIR = TemporaryDirectory(prefix="brief-review-cases-")
atexit.register(_CASES_DIR.cleanup)


@lru_cache(None)
def stored_run(name: str) -> Path:
    """runs/tier3 itself (read-only), or a derived synthetic case built once per session in a temp dir."""
    if name == TIER3:
        return REPO_ROOT / TIER3
    if name not in (SYNTHETIC_DEMO_CASE, SYNTHETIC_DRAFT_CASE):
        raise ValueError(f"Unknown synthetic review case: {name}")
    target = Path(_CASES_DIR.name) / name
    shutil.copytree(REPO_ROOT / TIER3, target)
    manifest_path = target / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["project_dir"] = str(REPO_ROOT / "fixtures/northlight_01")
    manifest["run_id"] = f"synthetic-renderer-{name}"
    brief_path = target / "brief.json"
    brief = json.loads(brief_path.read_text())
    if name == SYNTHETIC_DEMO_CASE:
        manifest["demo_profile"] = "synthetic-demo"
        manifest["steps"].insert(0, {"number": 0, "name": "readiness_gate",
                                     "description": "Synthetic demo refusal", "status": "refused_overridden"})
        brief["conflicts"] = []
    else:
        brief["signoff"] = {"status": "draft"}
        for conflict in brief["conflicts"]:
            conflict["status"] = "open"
            conflict.pop("resolution", None)
            conflict.pop("resolved_by", None)
    brief_path.write_text(json.dumps(brief, ensure_ascii=False))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    return target


# -- Tier 5–7 builders ----------------------------------------------------------------------
# Shared by the agency, delivery, governance, operations and question-exchange tests. They build
# synthetic runs in a temp dir and record synthetic human decisions there, never in runs/.

def make_review_run(tmp_path, data_class=None):
    """Synthetic minimal complete handover. It does not assert model quality. With `data_class`,
    tmp_path (the project folder) declares it and the run's snapshot binds it, as the runner does."""
    run = tmp_path / 'review'
    run.mkdir()
    ref = {
        'source_id': 'rfp',
        'location': 'L1',
        'anchor': 'Synthetic campaign',
        'speaker_or_author': 'Synthetic client',
    }
    b = {
        'meta': {
            'client_id': 'synthetic',
            'project_id': 'launch',
            'project_type': 'advertising_creative',
            'classification_confidence': 'high',
            'sensitivity_tier': 'S1',
            'sources': [{'source_id': 'rfp', 'source_type': 'rfp', 'source_date': '2026-09-19'}],
            'created_ts': '2026-09-19T10:00:00',
            'pipeline_version': '1.0',
        },
        'open_questions': [],
        'conflicts': [],
        'signoff': {'status': 'draft'},
    }
    e = {}
    for field in gates.BRIEF_FIELDS:
        b[field] = [{'content': 'Synthetic campaign', 'evidence': [ref], 'confidence': 'high', 'qualifier': 'stated'}]
        e[field] = [{'value': 'Synthetic campaign', 'anchor': ref['anchor'], 'location': 'L1'}]
    b['readiness'] = gates.compute_readiness_block(b)
    revisions.write_json(run / 'brief.json', b)
    revisions.write_json(run / 'extracts' / 'rfp.json', e)
    for lang in ('el', 'en'):
        (run / f'brief_{lang}.md').write_text(
            '\n'.join(f'## {i} {field}\n- Synthetic campaign [rfp L1]' for i, field in enumerate(gates.BRIEF_FIELDS, 1))
        )
    source = tmp_path / 'source.md'
    source.write_text('L1 Synthetic campaign')
    glossary = tmp_path / 'glossary.json'
    glossary.write_text('{}')
    revisions.write_json(
        run / 'input_snapshot.json', revisions.input_state({'source:rfp': source, 'glossary': glossary})
    )
    answers = {
        k: {'value': 'Synthetic campaign', 'owner': 'Synthetic lead', 'evidence': [ref]}
        for k in revisions.load(agency.PROFILES)['profiles']['creative_production']
    }
    specs = revisions.load(gates.CONFIG_DIR / 'channel_specs.json')['specs'][-1]
    row = {
        **specs,
        'id': 'asset-1',
        'spec_id': specs['id'],
        'quantity': 1,
        'languages': ['el'],
        'deadline': '2026-12-01',
        'owner': 'Synthetic production',
        'approval_owner': 'Synthetic lead',
        'dependencies': [],
        'evidence': [ref],
    }
    revisions.write_json(
        run / 'agency_inputs.json',
        {'campaign_profile': 'creative_production', 'checklist': answers, 'deliverables': [row]},
    )
    if data_class:
        bind_declaration(run, tmp_path, data_class)
    return run


def bind_declaration(run, project_dir, data_class, bind=True):
    """Write the project's data declaration and, like the runner and `agency init`, bind it into
    the run's input snapshot (bind=False writes the file only: a later, unbound edit)."""
    path = Path(project_dir) / 'data_declaration.json'
    path.write_text(json.dumps({'data_class': data_class}), encoding='utf-8')
    if bind:
        snapshot = revisions.load(run / 'input_snapshot.json', {})
        snapshot.update(revisions.input_state({'data_declaration': path}))
        revisions.write_json(run / 'input_snapshot.json', snapshot)


def vouch_forged(run, record, event):
    """Append a well-formed log entry for a hand-edited record. The log is tamper-EVIDENT, not
    tamper-proof: this lets a test reach the defence-in-depth check behind the vouching check."""
    revisions.append_audit(run, event, 'Forger', record=record)


def approve_synthetic(run):
    agency.main(
        [
            'attest',
            str(run),
            '--actor',
            'Synthetic reviewer',
            '--greek-register',
            '4',
            '--notes',
            'Synthetic only',
            '--checks',
            *agency.quality.field_review_checklist(),
        ]
    )
    agency.approve(run, 'Lead A', 'Synthetic approval')


#: A draft that passes every approval-time check, including W4's fact checks on the signed brief
#: (a draft must carry a strategic-tensions section, even when it lists none).
SYNTHETIC_DRAFT = (
    '> CREATIVE DRAFT\nSynthetic campaign [brief:objectives:0]\nSynthetic campaign [brief:mandatories:0]\n'
    '\n## Strategic tensions\nNone identified.\n'
)


def prepare_release(tmp_path, draft_text=None, data_class=None):
    run=make_review_run(tmp_path, data_class=data_class)
    inputs=revisions.load(run/'agency_inputs.json')
    row=dict(inputs['deliverables'][0])
    row['id']=row['spec_id']
    row.update(
        source_url='https://specs.example.invalid/synthetic',
        checked_on='2020-01-01',
        review_due='2099-01-01',
        checked_by='Synthetic traffic',
    )
    table={'owner':'Synthetic traffic','specs':[row]}
    path=tmp_path/'catalog.json'
    revisions.write_json(path,table)
    spec_catalog.bind(run,path,actor='Synthetic traffic')
    approve_synthetic(run)
    draft=tmp_path/'draft.txt'
    draft.write_text(draft_text or SYNTHETIC_DRAFT)
    delivery.register(run,draft,'Synthetic operator')
    return run

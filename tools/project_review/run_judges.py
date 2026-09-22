"""Whole-project review round: 6 layer panels x 3 independent specialist judges (panels.json), each judge scoring
only its own layer's aspects against the frozen rubric.md. Aggregation is deterministic.

Judges work in a staging dir OUTSIDE the repo, so no judge can read another's in-progress output; the finished
round is copied into tools/project_review/rounds/r<N>/.

  --engine codex  : runs every judge as its own `codex exec` session (repo read-only by construction).
  --engine claude : only writes prompts + per-panel schemas; the orchestrator runs each judge as an isolated
                    Claude subagent that writes out/<judge>.json, then re-runs this with --aggregate.

Usage: python3 tools/project_review/run_judges.py --round 0 --engine claude [--aggregate] [--prev 0]"""
import argparse, hashlib, json, pathlib, shutil, statistics, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--round', type=int, required=True)
ap.add_argument('--prev', type=int, help='earlier round to diff means against')
ap.add_argument('--engine', choices=['codex', 'claude'], default='codex')
ap.add_argument('--model', default=None, help='recorded in the report; passed to codex with --engine codex')
ap.add_argument('--only', help='comma-separated judge ids to (re)run')
ap.add_argument('--aggregate', action='store_true', help='skip running judges; aggregate existing outputs')
A = ap.parse_args()
MODEL = A.model or ('gpt-6-astra' if A.engine == 'codex' else 'claude-opus-5-5')

RUBRIC = (HERE / 'rubric.md').read_text(encoding='utf-8')
PANELS_RAW = (HERE / 'panels.json').read_text(encoding='utf-8')
PANELS = json.loads(PANELS_RAW)
RUBRIC_SHA = hashlib.sha256((RUBRIC + PANELS_RAW).encode()).hexdigest()
ASPECTS = [a for p in PANELS.values() for a in p['aspects']]
JUDGES = {jid: (pname, persona) for pname, p in PANELS.items() for jid, persona in p['judges'].items()}

R = ROOT.parent / 'review-staging' / f'r{A.round}'
for d in ('prompts', 'out', 'logs', 'work', 'schemas'):
    (R / d).mkdir(parents=True, exist_ok=True)
HEAD = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
DIRTY = subprocess.run(['git', '-C', str(ROOT), 'status', '--short'], capture_output=True, text=True).stdout


def obj(props):
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}


def schema(pname):
    mine = PANELS[pname]['aspects']
    return obj({
        'scores': {'type': 'array', 'minItems': len(mine), 'maxItems': len(mine), 'items': obj({
            'aspect': {'type': 'string', 'enum': mine},
            'score': {'type': 'integer', 'minimum': 1, 'maximum': 10},
            'evidence': {'type': 'string'},
            'defects': {'type': 'array', 'items': {'type': 'string'}},
            'to_reach_9': {'type': 'string'}})},
        'moves': {'type': 'array', 'maxItems': 8, 'items': obj({
            'title': {'type': 'string'},
            'aspects': {'type': 'array', 'items': {'type': 'string', 'enum': ASPECTS}},
            'rationale': {'type': 'string'},
            'concrete_changes': {'type': 'string'},
            'effort': {'type': 'string', 'enum': ['S', 'M', 'L']},
            'needs_owner_decision': {'type': 'boolean'}})},
        'overall': {'type': 'string'}})


def prompt(jid):
    pname, persona = JUDGES[jid]
    p = PANELS[pname]
    sch = R / 'schemas' / f'{pname}.json'
    text = f"""You are {persona}.

You are one of three independent specialist judges on the "{p['layer']}" panel reviewing the repository at {ROOT}
(git HEAD {HEAD}). Other judges work independently; you will never see their scores and they will never see yours.
Do NOT modify anything in the repository. Do NOT read tools/project_review/rounds/ or anything outside the
repository (except your own output file below): earlier rounds' judgments must not anchor yours.

Score ONLY these aspects, each exactly once: {', '.join(p['aspects'])}.
Start from this evidence (open other files whenever you need to verify a claim): {p['evidence']}.
Verify claims against code and run artifacts; never score from summaries alone. You may run the deterministic
suite from the repo root with `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -o addopts='' -q`
(no network, no model calls). Do NOT run `eval/harness.py` as a CLI (it rewrites a committed report).

The frozen rubric (read the scope calibration and scale carefully; the aspect definitions for your layer are what
you score):

{RUBRIC}

Then propose up to 8 "moves": the highest-leverage concrete improvements in your field, ranked by score gain /
effort. A move may help aspects outside your layer; list every aspect it lifts. Each move must be executable within
the project's rules: no edits to docs/PRD.md, fixtures/*/answer_key.json, eval/harness.py or
schema/brief_schema.json; never relax a gate or acceptance criterion; synthetic data only; no application UI, no
integrations. Set needs_owner_decision when a move changes a gate, a DoD, model routing or published presentation
material. Name files and the exact change. Be calibrated and strict: 8 means no defect that matters remains."""
    if A.engine == 'claude':
        text += f"""

OUTPUT: write ONE JSON file at {R / 'out' / (jid + '.json')} that validates against the JSON Schema in {sch}.
Then reply with only the file path and your scores on one line."""
    return text


def run_codex(jid):
    pname = JUDGES[jid][0]
    out, log, cwd = R / 'out' / f'{jid}.json', R / 'logs' / f'{jid}.log', R / 'work' / jid
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = ['codex', 'exec', '-m', MODEL, '-s', 'workspace-write', '-C', str(cwd), '--skip-git-repo-check',
           '--output-schema', str(R / 'schemas' / f'{pname}.json'), '-o', str(out), prompt(jid)]
    t0 = time.time()
    with open(log, 'w') as lf:
        rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, timeout=5400).returncode
    print(f'[{jid}] rc={rc} in {time.time() - t0:.0f}s', flush=True)


ids = A.only.split(',') if A.only else list(JUDGES)
if not A.aggregate:
    for pname in PANELS:
        (R / 'schemas' / f'{pname}.json').write_text(json.dumps(schema(pname), indent=1), encoding='utf-8')
    for jid in ids:
        (R / 'prompts' / f'{jid}.md').write_text(prompt(jid), encoding='utf-8')
    if A.engine == 'claude':
        print(f'{len(ids)} prompts in {R / "prompts"}; run the judges, then re-run with --aggregate')
        sys.exit(0)
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(run_codex, ids))

judges, problems = {}, []
for jid, (pname, _) in JUDGES.items():
    try:
        d = json.loads((R / 'out' / f'{jid}.json').read_text(encoding='utf-8'))
    except Exception as e:
        problems.append(f'{jid}: no usable output ({e})')
        continue
    got = sorted(s['aspect'] for s in d.get('scores', []))
    if got != sorted(PANELS[pname]['aspects']) or not all(1 <= s['score'] <= 10 for s in d['scores']):
        problems.append(f'{jid}: scored {got}, expected {sorted(PANELS[pname]["aspects"])}; excluded')
        continue
    judges[jid] = d

table = {}
for pname, p in PANELS.items():
    for a in p['aspects']:
        vals = {j: s['score'] for j, d in judges.items() for s in d['scores'] if s['aspect'] == a}
        table[a] = {'panel': pname, 'by_judge': vals,
                    'mean': round(statistics.mean(vals.values()), 2) if vals else None,
                    'min': min(vals.values()) if vals else None}
prev = json.loads((HERE / 'rounds' / f'r{A.prev}' / 'scores.json').read_text())['table'] if A.prev is not None else None
# Target: every aspect's panel mean strictly above 8, and no single judge below 8 on it.
met = all(len(t['by_judge']) == 3 and t['mean'] > 8 and t['min'] >= 8 for t in table.values())
result = {'round': A.round, 'head': HEAD, 'dirty': DIRTY, 'rubric_sha256': RUBRIC_SHA, 'engine': A.engine,
          'model': MODEL, 'judges': sorted(judges), 'problems': problems, 'table': table, 'target_met': met}
(R / 'scores.json').write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')

lines = [f'# Project review round {A.round}', '',
         f'HEAD `{HEAD[:12]}` · rubric+panels sha256 `{RUBRIC_SHA[:12]}` · {len(judges)}/{len(JUDGES)} judges on '
         f'`{MODEL}` ({A.engine}) · target (every aspect mean > 8, no judge < 8): **{"MET" if met else "not met"}**', '']
if problems:
    lines += ['**Problems:** ' + '; '.join(problems), '']
lines += ['| layer | aspect | judge scores | mean | min |' + (' Δmean |' if prev else ''),
          '|---|---|---|---|---|' + ('---|' if prev else '')]
for a, t in table.items():
    scores = ' · '.join(f'{j.split("_")[0]} {v}' for j, v in t['by_judge'].items()) or '–'
    row = f"| {PANELS[t['panel']]['layer'].split(' — ')[1]} | {a} | {scores} | {t['mean']} | {t['min']} |"
    if prev:
        pm = prev.get(a, {}).get('mean')
        row += f" {t['mean'] - pm:+.2f} |" if pm is not None and t['mean'] is not None else ' – |'
    lines.append(row)
lines += ['', '## Judge summaries', '']
for j, d in judges.items():
    lines += [f'**{j}:** {d["overall"]}', '']
lines += ['## Proposed moves (all judges, unranked)', '']
for j, d in judges.items():
    for m in d['moves']:
        lines.append(f"- [{j}] **{m['title']}** ({m['effort']}; {', '.join(m['aspects'])}"
                     f"{'; OWNER DECISION' if m['needs_owner_decision'] else ''}) — {m['concrete_changes']}")
(R / 'scores.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

dest = HERE / 'rounds' / f'r{A.round}'
for d in ('prompts', 'out', 'logs', 'schemas'):
    if (R / d).exists():
        shutil.copytree(R / d, dest / d, dirs_exist_ok=True)
for f in ('scores.json', 'scores.md'):
    shutil.copy2(R / f, dest / f)
print('\n'.join(lines[:len(ASPECTS) + 8]))

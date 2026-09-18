#!/usr/bin/env python3
"""The v3 review round run entirely on Codex (gpt-6-astra): every agent is one `codex exec` session with a JSON
output schema, the repo read-only (cwd is a scratch dir), aggregation deterministic. Mirrors score-round-v3.js.
Usage: python3 tools/walkthrough/codex_round.py --round 9 [--page WALKTHROUGH.html] [--concurrency 5]
Writes tools/walkthrough/codex_round/r<N>/{prompts,out,logs}/, result.json, report.md."""
import argparse, json, pathlib, subprocess, hashlib, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder')
ap = argparse.ArgumentParser(); ap.add_argument('--round', type=int, required=True); ap.add_argument('--page', default='WALKTHROUGH.html')
ap.add_argument('--concurrency', type=int, default=5); ap.add_argument('--model', default='gpt-6-astra'); ap.add_argument('--args', default='tools/walkthrough/round8_args.json')
A = ap.parse_args()
PAGE = (ROOT / A.page).resolve(); HASH = hashlib.sha256(PAGE.read_bytes()).hexdigest()
R = ROOT / f'tools/walkthrough/codex_round/r{A.round}'; [(R / d).mkdir(parents=True, exist_ok=True) for d in ('prompts', 'out', 'logs', 'work')]
SCH = ROOT / 'tools/walkthrough/codex_round/schemas'
prev = json.load(open(ROOT / A.args)); PREV = prev['prev']; MUSTKEEP = prev.get('mustKeep', []); PREVHARD = prev.get('prevHard', [])
ASPECTS = ['concision', 'completeness', 'clarity', 'storyline', 'product_framing', 'visual_design', 'fact_fidelity', 'ux', 'finale']
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FREEZE = f"FROZEN CANDIDATE. Before anything else run: shasum -a 256 {PAGE} ; the digest must be {HASH}. If it differs, stop and return hashMismatch=true with the digest you saw. Everything you report must be about this exact file. Never edit any file under {ROOT}; your working directory is a scratch folder where you may write notes or screenshots (to render a sheet: \"{CHROME}\" --headless=new --disable-gpu --hide-scrollbars --user-data-dir=./chrome --window-size=1440,2400 --screenshot=./sheetN.png \"file://{PAGE}#N\" ; add --window-size=390,844 for a phone)."
GROUND = f"Ground truth lives ONLY in the repository: {ROOT}/runs/tier3/run_manifest.json (per-attempt tokens, models, durations, cost_usd), runs/tier3/harness_report.json (17 checks), runs/tier3/brief.json and renders, runs/tier3/creative/creative_brief_sonnet.md and creative_brief_opus.md, runs/routing-validate-01/, runs/voreas_prep_report.md, docs/PRD.md (section 2 target, section 7 pilot metrics, section 8 pilot, section 9 risks, assumptions A1 to A4), docs/COST_MODEL.md, docs/EVIDENCE.md, docs/demo_timing.md, config/channel_specs.json, fixtures/northlight_01/ (four synthetic sources plus brand guidelines), pipeline/gates.py (enforce_sensitivity_tier refuses S2 to S3 at run time), schema/brief_schema.json (conflicts carry resolution and resolved_by; signoff carries status, signed_by, signed_ts, edits_summary). Known repository discrepancies the page discloses (do NOT count them against it): EVIDENCE.md says $4.29 (raw double count; de-duplicated $3.55); COST_MODEL.md section 3 says about 5 to 6 thousand euros a year but PRD A1/A2/A4 give about 210 h or 4.0 to 4.2 thousand; channel_specs.json is a self-declared stub; the Opus creative draft calls the TikTok dance retracted when the transcript shows it as speculative; pipeline/review.py makes a review view, not an approval editor. House rules the page follows on purpose (not defects): usage is shown in tokens by model because the client will most likely be on a subscription, dollars only in the sheet-10 ledger footnote; the budget stays \"in the eighties\" in words (no invented or resolved total; quoting the RFP's 90,000 as a conflict position is legitimate); creative output and the key visual and can are labelled shadow mode and mock-up; thousands separator is a thin space (U+2009). The plain-English sentence on sheet 10 about hours (two hours down to fifty minutes, 210 hours, 4.0 to 4.2 thousand euros) is the PRD's arithmetic, stated as assumptions to validate."
RUBRIC = """Score each aspect 1-10 (10 = a top design firm / top consulting firm would ship it unchanged). Be strict and specific; 8 means good with minor issues; 9-10 means nothing to fix. Every fix must quote the exact current text (or CSS selector) it changes.
1 concision: at most 10 sheets; one message per sheet; no passage a decision-maker would skip; word counts tight (ledgers and details blocks are reference, not the presentation layer).
2 completeness: every critical fact a stakeholder needs: what it is, what this run proved, usage (tokens in total and by model; API dollars belong only in a footnote and their absence from the visible sheets is correct), time, limits and risks, what stays human, the deliverable itself, decisions needed with owners, next steps.
3 clarity: plain language a CMO, a CFO, a creative director and an engineer all follow; the three roles (AI / code / people) legible at a glance; jargon explained where used.
4 storyline: consulting-grade: the answer first; every sheet title a takeaway sentence that the evidence on that sheet supports; sources cited; logical flow with no redundancy.
5 product_framing: Brief Builder shown as a whole product: name, promise, principles, anatomy, outputs, guarantees, where it runs, who touches it.
6 visual_design: agency-grade: deliberate typography, hierarchy, spacing, one coherent system, not templated; the client's brand colours only on the creative sheet.
7 fact_fidelity: numbers, quotes, model ids, usage and timings match the run artifacts (spot-check headline figures against the repository).
8 ux: navigation obvious (Next/Back, contents, keyboard), works when double-clicked from disk with zero dependencies, sensible on a phone, focus states, no dead ends.
9 finale: the creative brief and key visual: appealing, compliant with the brand mandatories in fixtures/northlight_01/background_brand_guidelines.md, honestly labelled as shadow-mode and as an illustration, channel specs from the table."""
def run(name, prompt, schema, cwd_sub='work', extra=()):
    (R / 'prompts' / f'{name}.md').write_text(prompt, encoding='utf-8')
    out = R / 'out' / f'{name}.json'; log = R / 'logs' / f'{name}.log'; cwd = R / cwd_sub / name; cwd.mkdir(parents=True, exist_ok=True)
    cmd = ['codex', 'exec', '-m', A.model, '-s', 'workspace-write', '-C', str(cwd), '--skip-git-repo-check', '--output-schema', str(SCH / f'{schema}.json'), '-o', str(out), *extra, prompt]
    t0 = time.time()
    with open(log, 'w') as lf: rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, timeout=3600).returncode
    try: data = json.loads(out.read_text(encoding='utf-8'))
    except Exception as e: data = None; print(f'[{name}] no JSON ({e}); rc={rc}', flush=True)
    print(f'[{name}] done rc={rc} in {time.time()-t0:.0f}s', flush=True); return data
def para(jobs):
    with ThreadPoolExecutor(max_workers=A.concurrency) as ex: return list(ex.map(lambda j: run(*j), jobs))
AUDITORS = {
  'audit_fidelity': f"{FREEZE}\nYou are the REPOSITORY-FIDELITY auditor. Read {PAGE} in full. For EVERY number, model id, timing, token figure, percentage, quotation, file name and factual claim on the page (visible sheets AND the details ledgers), find its source in the repository and check it. {GROUND}\nREGRESSION LIST, facts and exhibits that must still be on the page; report any that is missing as a missing_exhibit hard failure: {json.dumps(MUSTKEEP)}\nReport as hardFailures ONLY: wrong arithmetic (recompute it), wrong facts (the artifact says otherwise), unsupported guarantees (universal claims the run does not establish and the page does not scope), quotes that are not verbatim, missing exhibits. Everything else is a softIssue (at most 12). For each hard failure copy the exact page text and the exact repo evidence (path plus field or line); an unverifiable deduction does not count. If the digest matches, digestSeen is that digest.",
  'audit_ux': f"{FREEZE}\nYou are the RENDERED-UX and ACCESSIBILITY auditor. Read {PAGE} in full including all CSS and both script blocks, then RENDER it with headless Chrome (command above) at 1440 px and at 390 px for at least sheets 1, 2, 8, 9 and 10, and look at the screenshots. Check: every sheet reachable by Next/Back/keys/contents; no dead end; the Next button's accessible label; swipe cannot fire from a vertical scroll or inside scrollable tables; the contents overlay closes on Escape; ids referenced by the scripts exist; the ruler/folio at 390 px; clips stack on phones; sheet 09 shows both crops and the can plate, the MOCK-UP label inside the 9:16 crop, only #1B4F8A, #F5C518 and white in the SVG with flat fills and no opacity; text contrast on paper #F1F2EC; nothing external is loaded. PREVIOUS ROUND'S CONFIRMED HARD FAILURES, confirm each is fixed and if not report it again: {json.dumps(PREVHARD)}\nReport as hardFailures only broken interactions, overlapping or clipped text, and accessibility blockers you can point to in the code or a screenshot (quote the lines). Everything else is a softIssue (at most 12) with a concrete fix. If the digest matches, digestSeen is that digest.",
}
AUDIENCE = {
  'task_cmo': ("the client's Chief Marketing Officer, no technical background", 'Explain to your CEO in your own words what Brief Builder does for the agency and for you, what this run proved, and what stays with people. Use only the visible sheets (ignore the collapsed ledgers unless a sheet tells you to open one).'),
  'task_cfo': ("the agency's Chief Financial Officer", 'Reproduce the economics from the page: the usage of the graded run in tokens and by model, the monthly usage estimate for the pilot, the returned-hours calculation and the assumptions it rests on, and state exactly what you are being asked to approve and under what conditions. Show your arithmetic.'),
  'task_creative': ("the agency's creative director", 'On the creative sheet, separate for your team: (a) what is evidence from the signed-off brief, (b) what is creative hypothesis, (c) what the creative lead must strike or confirm before anything leaves shadow mode, and (d) what the spec table does and does not guarantee.'),
  'task_engineer': ('the engineer who would run and maintain the pipeline', 'State the operating boundary: what the system guarantees on this run versus in general, what is code and what is a model, where the human records resolutions and the signature, what the review page does and does not do, what the deterministic checks do and do not catch, and what re-baselining is needed after the routing change.'),
}
PERSONAS = ['a senior partner at a top strategy consultancy reviewing a client deliverable', 'a design director at a top product design studio reviewing a shipped product story', 'a pair of stakeholders reading together: a client CMO with no technical background and an agency CFO']
jobs = [(k, v, 'hard') for k, v in AUDITORS.items()]
jobs += [(k, f"{FREEZE}\nRound {A.round}. You are {who}, reading {PAGE} for the first time (read it in full). Do this task: {task}\nThen report honestly: passed (true only if you could do it without guessing), your answer in your own words (at most 120 words), what was missing, which passages confused you (quote them), and 1 to 10 scores for clarity, completeness and concision from your role's point of view, plus up to four fixes quoting the exact text to change.", 'task') for k, (who, task) in AUDIENCE.items()]
jobs += [(f'judge_{i+1}', f"{FREEZE}\nRound {A.round}. You are {p}. Read the ENTIRE file {PAGE} and the repository files named below for fact checks. {GROUND}\nWrite nothing to the repository. {RUBRIC}\nReturn the nine scores (all nine aspects, each exactly once) with a one-sentence why and up to four concrete fixes each (sheet, exact quote, change).", 'score') for i, p in enumerate(PERSONAS)]
print(f'round {A.round} on {PAGE.name} @ {HASH[:12]}: {len(jobs)} agents, concurrency {A.concurrency}', flush=True)
res = dict(zip([j[0] for j in jobs], para(jobs)))
# skeptics for every claimed hard failure
claims = []
for k in AUDITORS:
    r = res.get(k)
    if r and not r.get('hashMismatch'):
        for f in r.get('hardFailures', []): claims.append((k, f))
print(f'{len(claims)} claimed hard failures', flush=True)
vjobs = []
for i, (auditor, f) in enumerate(claims):
    for k in (0, 1):
        lens = 'Take the repository-evidence lens: recompute figures and re-read sources.' if k == 0 else 'Take the reader lens: would a careful stakeholder be misled by this passage as written? Render the sheet if it is a layout claim.'
        vjobs.append((f'verify_{i+1}_{k+1}', f"{FREEZE}\nAn auditor ({auditor}) claims this HARD FAILURE in {PAGE} (sheet {f['sheet']}, category {f['category']}):\nPAGE TEXT: {f['pageText']}\nEVIDENCE CITED: {f['evidence']}\nWHY: {f['why']}\n{GROUND}\nYour job is to REFUTE it: open the page and the cited artifacts and check whether the claim is actually wrong, whether the page already discloses or scopes it, whether it is one of the house rules or known discrepancies, or whether the category is inflated (a preference, not a failure). {lens} Return refuted=true if the claim does not hold as a HARD failure (default to refuted=true if uncertain); if it holds, give the correctedClaim in one sentence; otherwise correctedClaim is an empty string.", 'verdict'))
vres = dict(zip([j[0] for j in vjobs], para(vjobs))) if vjobs else {}
hard = []; refuted = []
for i, (auditor, f) in enumerate(claims):
    votes = [vres.get(f'verify_{i+1}_{k+1}') for k in (0, 1)]; votes = [v for v in votes if v]
    stands = len(votes) == 2 and all(not v['refuted'] for v in votes)
    (hard if stands else refuted).append({**f, 'auditor': auditor, 'votes': votes})
tasks = {k: res.get(k) for k in AUDIENCE}; judges = [res.get(f'judge_{i+1}') for i in range(3)]; judges = [j for j in judges if j and not j.get('hashMismatch')]
by = {}
for j in judges:
    for s in j['scores']: by.setdefault(s['aspect'], []).append(s)
averages = {k: (round(sum(s['score'] for s in by[k]) / len(by[k]), 2) if by.get(k) else None) for k in ASPECTS}
deltas = {k: (round(averages[k] - PREV['averages'][k], 2) if averages[k] is not None and k in PREV['averages'] else None) for k in ASPECTS}
hashProblems = [k for k, v in res.items() if v and v.get('hashMismatch')]
tasksFailed = [k for k, v in tasks.items() if not v or not v.get('passed')]
regressions = [k for k, d in deltas.items() if d is not None and d <= -0.5]
below8 = [k for k, v in averages.items() if v is not None and v <= 8.0]
stable = not hashProblems and not hard and not tasksFailed and not regressions and len(judges) == 3 and all(res.get(k) for k in AUDITORS)
result = {'round': A.round, 'page': str(PAGE), 'hash': HASH, 'stable': stable, 'hashProblems': hashProblems, 'hardFailures': hard, 'refutedClaims': refuted, 'tasks': tasks, 'judges': len(judges), 'averages': averages, 'deltas': deltas, 'below8': below8, 'regressions': regressions, 'detail': by, 'softIssues': {k: (res.get(k) or {}).get('softIssues', []) for k in AUDITORS}, 'agentsMissing': [k for k, v in res.items() if not v]}
(R / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
# editor brief
softAll = [{'from': k, **s} for k in AUDITORS for s in (res.get(k) or {}).get('softIssues', [])]
judgeFixes = [{'from': f'judge{i+1}:{s["aspect"]}({s["score"]})', **f} for i, j in enumerate(judges) for s in j['scores'] for f in s['fixes']]
taskFixes = [{'from': k, 'fix': f} for k, v in tasks.items() if v for f in v.get('fixes', [])]
brief = run('brief', f"{FREEZE}\nYou are the editor-in-chief for round {A.round + 1} of {PAGE}. Do NOT edit anything. Read the page once, then turn this round's evidence into ONE bounded change hypothesis for the next editing pass (Codex will apply it under tools/walkthrough/checks.py).\nVERIFIED HARD FAILURES (must all be fixed, first): {json.dumps(hard, ensure_ascii=False)}\nAUDIENCE TASKS: {json.dumps({k: {kk: v.get(kk) for kk in ('passed', 'missing', 'confusions', 'fixes')} for k, v in tasks.items() if v}, ensure_ascii=False)}\nSCORES this round: {json.dumps(averages)} (deltas vs round {PREV['round']}: {json.dumps(deltas)})\nJUDGE FIXES: {json.dumps(judgeFixes, ensure_ascii=False)}\nAUDITOR SOFT ISSUES: {json.dumps(softAll, ensure_ascii=False)}\nTASK FIXES: {json.dumps(taskFixes, ensure_ascii=False)}\nRules the page must keep: at most 10 sheets; never change blockquotes or mark.cited; zero external resources; tokens not dollars as the usage figure; budget stays in words; shadow-mode labels; action titles at most 24 words; takeaways at most 20 words; at most 650 visible words per sheet (750 on sheet 09); palette rules; thin-space thousands.\nProduce: hypothesis (one sentence naming the single aspect this pass targets and the bound); at most 12 items, each an exact before and after (or CSS/JS), hard failures first, then fixes at least two independent sources asked for, then the cheapest clarity wins for any audience that failed its task; drop contradictory or taste-only requests silently; mustKeep: every fact or exhibit the audience tasks relied on, as a regression list.", 'brief')
result['brief'] = brief; (R / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
lines = [f"# Round {A.round} (Codex {A.model}) on {PAGE.name} @ {HASH[:12]}", '', f"**Verdict:** {'STABLE' if stable else 'NOT stable'}; hard failures {len(hard)} (refuted {len(refuted)}); tasks failed: {', '.join(tasksFailed) or 'none'}; judges {len(judges)}/3; agents missing: {', '.join(result['agentsMissing']) or 'none'}; hash problems: {', '.join(hashProblems) or 'none'}", '', '| aspect | avg | delta vs r' + str(PREV['round']) + ' |', '|---|---|---|']
lines += [f"| {k} | {averages[k]} | {deltas[k]} |" for k in ASPECTS]
lines += ['', '## Hard failures (verified)'] + [f"- [{f['category']}] sheet {f['sheet']}: {f['why'][:300]}" for f in hard] or ['- none']
lines += ['', '## Refuted claims'] + [f"- [{f['category']}] sheet {f['sheet']}: {f['pageText'][:120]}" for f in refuted]
lines += ['', '## Audience tasks'] + [f"- {k}: passed={v.get('passed') if v else None}; scores={v.get('scores') if v else None}; missing: " + ' | '.join((v or {}).get('missing', [])[:4]) for k, v in tasks.items()]
if brief: lines += ['', '## Editor brief', f"**Hypothesis:** {brief['hypothesis']}"] + [f"{it['n']}. sheet {it['sheet']}: {it['change'][:400]}  _({it['source'][:120]})_" for it in brief['items']]
(R / 'report.md').write_text('\n'.join(lines), encoding='utf-8'); print('\n'.join(lines[:12]), flush=True); print(f'written {R}/result.json and report.md', flush=True)

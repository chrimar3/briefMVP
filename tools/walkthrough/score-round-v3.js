export const meta = {
  name: 'score-round-v3',
  description: 'Round N review of WALKTHROUGH.html (v3: audits, audience tasks and judges run concurrently; regression list carried from the previous brief): hash-frozen candidate, hard-failure audit (repo fidelity + rendered UX) with adversarial verification, four audience tasks, three scoring personas, stability verdict, bounded editor brief',
  phases: [
    { title: 'Audit', detail: 'repository-fidelity and rendered-UX auditors list hard failures with evidence' },
    { title: 'Verify', detail: 'two skeptics try to refute each claimed hard failure' },
    { title: 'Audience', detail: 'CMO, CFO, creative director, engineer each perform their task from the page alone' },
    { title: 'Score', detail: 'the three round-1..6 personas score the nine aspects (time-series comparability)' },
    { title: 'Brief', detail: 'one bounded editor hypothesis for the next pass' },
  ],
}
// ---- inputs (pass via args; Date/random are unavailable in scripts) ----
const ROUND = (args && args.round) || 7
const HASH = (args && args.hash) || 'UNKNOWN'
const PREV = (args && args.prev) || {}          // { round: N, averages: {aspect: avg} } of the last comparable review
const MUSTKEEP = (args && args.mustKeep) || []   // regression list from the previous round's editor brief
const PREVHARD = (args && args.prevHard) || []   // hard failures the previous round confirmed (must be fixed now)
const FILE = '/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html'
const ROOT = '/Users/chrism/AI-transformation-assignment/brief-builder'
const ASPECTS = ['concision','completeness','clarity','storyline','product_framing','visual_design','fact_fidelity','ux','finale']

const FREEZE = `FROZEN CANDIDATE. Before anything else run: shasum -a 256 ${FILE} — the digest must be ${HASH}. If it differs, stop reading and return hashMismatch=true with the digest you saw. Everything you report must be about this exact file; never edit any file.`

const GROUND = `Ground truth lives ONLY in the repository: ${ROOT}/runs/tier3/run_manifest.json (per-attempt tokens, models, durations, cost_usd), runs/tier3/harness_report.json (17 checks), runs/tier3/brief.json and renders, runs/tier3/creative/creative_brief_sonnet.md and creative_brief_opus.md, runs/routing-validate-01/, runs/voreas_prep_report.md, docs/PRD.md (§2 target, §7 pilot metrics, §8 pilot, §9 risks, assumptions A1–A4), docs/COST_MODEL.md, docs/EVIDENCE.md, docs/demo_timing.md, config/channel_specs.json, fixtures/northlight_01/ (four synthetic sources + brand guidelines). Known repository discrepancies (do NOT count these against the page when the page discloses them): EVIDENCE.md says $4.29 (raw double count; de-duplicated $3.55); COST_MODEL.md §3 says ~€5–6k/yr but PRD A1/A2/A4 give ~210 h ≈ €4.0–4.2k; channel_specs.json is a self-declared stub; the Opus creative draft calls the TikTok dance "retracted" when the transcript shows it as speculative (the metro idea was the retraction); pipeline/review.py makes a review view, not an approval editor. House rules the page follows on purpose (not defects): usage is shown in tokens by model because the client will most likely be on a subscription — dollars appear only in the sheet-10 ledger footnote; the budget stays "in the eighties" in words (no invented or resolved total); creative output is labelled shadow mode and mock-up; thousands separator is a thin space (U+2009).`

const HARD = { type: 'object', required: ['hashMismatch', 'hardFailures', 'softIssues'], properties: {
  hashMismatch: { type: 'boolean' }, digestSeen: { type: 'string' },
  hardFailures: { type: 'array', items: { type: 'object', required: ['category', 'sheet', 'pageText', 'evidence', 'why'], properties: {
    category: { type: 'string', enum: ['wrong_arithmetic', 'wrong_fact', 'unsupported_guarantee', 'missing_exhibit', 'broken_interaction', 'quote_not_verbatim', 'accessibility_blocker'] },
    sheet: { type: 'string' }, pageText: { type: 'string', description: 'exact text from the page (copy it)' },
    evidence: { type: 'string', description: 'repo path (and line/field) or the JS/CSS lines that prove it' }, why: { type: 'string' } } } },
  softIssues: { type: 'array', maxItems: 12, items: { type: 'object', required: ['sheet', 'issue', 'fix'], properties: { sheet: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' } } } } } }

const VERDICT = { type: 'object', required: ['refuted', 'reason'], properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, correctedClaim: { type: 'string' } } }

const TASK = { type: 'object', required: ['hashMismatch', 'passed', 'answer', 'missing', 'confusions', 'scores'], properties: {
  hashMismatch: { type: 'boolean' }, passed: { type: 'boolean', description: 'could you complete the task from the page alone, without guessing?' },
  answer: { type: 'string', description: 'your own words, as you would say it in the meeting (≤120 words)' },
  missing: { type: 'array', items: { type: 'string' }, description: 'facts you needed and could not find on the visible sheets' },
  confusions: { type: 'array', items: { type: 'string' }, description: 'passages you misread or had to re-read, quoted' },
  scores: { type: 'object', required: ['clarity', 'completeness', 'concision'], properties: { clarity: { type: 'integer', minimum: 1, maximum: 10 }, completeness: { type: 'integer', minimum: 1, maximum: 10 }, concision: { type: 'integer', minimum: 1, maximum: 10 } } },
  fixes: { type: 'array', maxItems: 4, items: { type: 'string' } } } }

const SCORE = { type: 'object', required: ['hashMismatch', 'scores', 'overall'], properties: {
  hashMismatch: { type: 'boolean' },
  scores: { type: 'array', minItems: 9, maxItems: 9, items: { type: 'object', required: ['aspect', 'score', 'why', 'fixes'], properties: {
    aspect: { type: 'string', enum: ASPECTS }, score: { type: 'integer', minimum: 1, maximum: 10 }, why: { type: 'string' },
    fixes: { type: 'array', maxItems: 4, items: { type: 'object', required: ['sheet', 'quote', 'change'], properties: { sheet: { type: 'string' }, quote: { type: 'string', description: 'exact current text or CSS selector — a deduction without a quote is not allowed' }, change: { type: 'string' } } } } } } },
  overall: { type: 'string' } } }

const BRIEF = { type: 'object', required: ['hypothesis', 'items', 'mustKeep'], properties: {
  hypothesis: { type: 'string', description: 'one sentence: the single bounded change this pass makes and the aspect it targets' },
  items: { type: 'array', maxItems: 12, items: { type: 'object', required: ['n', 'sheet', 'change', 'source'], properties: { n: { type: 'integer' }, sheet: { type: 'string' }, change: { type: 'string', description: 'exact before → after text, or CSS/JS to change' }, source: { type: 'string', description: 'which judge/auditor asked and the evidence' } } } },
  mustKeep: { type: 'array', items: { type: 'string' }, description: 'facts and exhibits that must survive the pass (regression list for the next audit)' } } }

const RUBRIC = `Score each aspect 1-10 (10 = a top design firm / top consulting firm would ship it unchanged). Be strict and specific; 8 means "good, minor issues"; 9-10 means "nothing to fix". Every fix must quote the exact current text (or CSS selector) it changes.
1 concision — at most 10 sheets; one message per sheet; no passage a decision-maker would skip; word counts tight (ledgers/<details> are reference, not the presentation layer).
2 completeness — every critical fact a stakeholder needs: what it is, what this run proved, usage (tokens in total and by model; the client will run on a subscription, so API dollars belong only in a footnote and their absence from the visible sheets is correct), time, limits and risks, what stays human, the deliverable itself, decisions needed with owners, next steps.
3 clarity — plain language a CMO, a CFO, a creative director and an engineer all follow; the three roles (AI / code / people) legible at a glance; jargon explained where used.
4 storyline — consulting-grade: the answer first; every sheet title a takeaway sentence that the evidence on that sheet supports; sources cited; logical flow with no redundancy.
5 product_framing — Brief Builder shown as a whole product: name, promise, principles, anatomy, outputs, guarantees, where it runs, who touches it — not just a sequence of steps.
6 visual_design — agency-grade: deliberate typography, hierarchy, spacing, one coherent system, not templated; the client's brand colours only on the creative sheet.
7 fact_fidelity — numbers, quotes, model ids, usage and timings match the run artifacts (spot-check headline figures against the repository).
8 ux — navigation obvious (Next/Back, contents, keyboard), works when double-clicked from disk with zero dependencies, sensible on a phone, focus states, no dead ends.
9 finale — the creative brief and key visual: appealing, compliant with the brand mandatories in fixtures/northlight_01/background_brand_guidelines.md, honestly labelled as shadow-mode and as an illustration, channel specs from the table.`

// ---------------- Phase 1: hard-failure audit (two distinct auditors) ----------------
phase('Audit')
const AUDITORS = [
  { key: 'fidelity', prompt: `${FREEZE}\nYou are the REPOSITORY-FIDELITY auditor. Read ${FILE} in full. For EVERY number, model id, timing, token figure, percentage, quotation, file name and factual claim on the page (visible sheets AND the <details> ledgers), find its source in the repository and check it. ${GROUND}\nReport as hardFailures ONLY: wrong arithmetic (recompute it), wrong facts (the artifact says otherwise), unsupported guarantees (universal claims like "every"/"never"/"cannot" that the run does not establish and the page does not scope to this project), quotes that are not verbatim, and missing exhibits (a sheet whose title promises evidence the sheet does not show). Everything else is a softIssue. For each hard failure copy the exact page text and the exact repo evidence (path + field/line) — an unverifiable deduction does not count. REGRESSION LIST — facts and exhibits that must still be on the page; report any that is missing as a missing_exhibit hard failure: ${JSON.stringify(MUSTKEEP)}. Be exhaustive: check the 984 820 / 1 134 734 token totals and the model split, the 56/27/16/0.3 cache split, the 33 min / 25.2 min timings, 17/17, 15/17→16/17, 598 743 vs 295 774, 25 entries / 3 conflicts / 10 questions, the €4.0–4.2k calculation, the nine sessions, the resolved model ids, the channel spec values, every blockquote.` },
  { key: 'ux', prompt: `${FREEZE}\nYou are the RENDERED-UX and ACCESSIBILITY auditor. Read ${FILE} in full, including all CSS and the two <script> blocks. Reason about how it renders and behaves at 1440px, 1000px and 390px wide, from a double-click on disk (file://), with a keyboard only, with a screen reader, on a touch phone, and when printed. Check: every sheet reachable by Next/Back/keys/contents; no dead end; #next has an accessible label when its text is hidden; swipe cannot fire from a vertical scroll or inside scrollable tables; the contents overlay traps focus sensibly and closes on Escape; ids referenced by the scripts exist; the ruler/folio behaves at 390px; .clips stacks on phones; the sheet-09 key visual shows both crops, the MOCK-UP label sits inside the 9:16 crop, and only #1B4F8A, #F5C518 and white appear in it with flat fills and no opacity; text contrast on paper #F1F2EC; nothing external is loaded. PREVIOUS ROUND'S CONFIRMED HARD FAILURES — confirm each is fixed in this file; if not, report it again: ${JSON.stringify(PREVHARD)}. Report as hardFailures only broken interactions and accessibility blockers you can point to in the code (quote the lines). Everything else is a softIssue with a concrete fix.` },
]
const verify = async (f, auditor) => {
  const votes = (await parallel([0, 1].map(k => () => agent(
    `${FREEZE}\nAn auditor claims this HARD FAILURE in ${FILE} (sheet ${f.sheet}, category ${f.category}):\nPAGE TEXT: ${f.pageText}\nEVIDENCE CITED: ${f.evidence}\nWHY: ${f.why}\n${GROUND}\nYour job is to REFUTE it: open the page and the cited artifacts and check whether the claim is actually wrong, whether the page already discloses/scopes it, whether it is one of the listed house rules or known repository discrepancies, or whether the category is inflated (a preference, not a failure). ${k === 0 ? 'Take the repository-evidence lens: recompute figures and re-read sources.' : 'Take the reader lens: would a careful stakeholder be misled by this passage as written?'} Return refuted=true if the claim does not hold as a HARD failure (default to refuted=true if uncertain); if it holds, give the correctedClaim in one sentence.`,
    { label: `verify:${auditor}:${f.sheet}:${k + 1}`, phase: 'Verify', schema: VERDICT, model: 'opus' })))).filter(Boolean)
  const stands = votes.length > 0 && votes.filter(v => !v.refuted).length >= 2
  return { ...f, auditor, stands, votes }
}
const auditsP = pipeline(AUDITORS,
  a => agent(a.prompt, { label: `audit:${a.key}`, phase: 'Audit', schema: HARD, model: 'opus' }),
  async (r, a) => {
    if (!r) return { key: a.key, error: 'auditor died', hardFailures: [], softIssues: [] }
    if (r.hashMismatch) return { key: a.key, hashMismatch: true, digestSeen: r.digestSeen, hardFailures: [], softIssues: [] }
    log(`audit:${a.key}: ${r.hardFailures.length} claimed hard failures, ${r.softIssues.length} soft`)
    const verified = await parallel(r.hardFailures.map(f => () => verify(f, a.key)))
    return { key: a.key, hardFailures: verified.filter(Boolean), softIssues: r.softIssues }
  })

// ---------------- Phase 2: audience tasks (from the page alone) ----------------
const AUDIENCE = [
  { key: 'cmo', who: 'the client\'s Chief Marketing Officer, no technical background', task: 'Explain to your CEO in your own words what Brief Builder does for the agency and for you, what this run proved, and what stays with people. You may use only the visible sheets (ignore the collapsed ledgers unless a sheet tells you to open one).' },
  { key: 'cfo', who: 'the agency\'s Chief Financial Officer', task: 'Reproduce the economics from the page: the usage of the graded run in tokens and by model, the monthly usage estimate for the pilot, the returned-hours calculation and the assumptions it rests on, and state exactly what you are being asked to approve and under what conditions. Show your arithmetic.' },
  { key: 'creative', who: 'the agency\'s creative director', task: 'On the creative sheet, separate for your team: (a) what is evidence from the signed-off brief, (b) what is creative hypothesis, (c) what the creative lead must strike or confirm before anything leaves shadow mode, and (d) what the spec table does and does not guarantee.' },
  { key: 'engineer', who: 'the engineer who would run and maintain the pipeline', task: 'State the operating boundary: what the system guarantees on this run versus in general, what is code and what is a model, where the human records resolutions and the signature, what the review page does and does not do, what the deterministic checks do and do not catch, and what re-baselining is needed after the routing change.' },
]
const tasksP = parallel(AUDIENCE.map(a => () => agent(
  `${FREEZE}\nRound ${ROUND}. You are ${a.who}, reading ${FILE} for the first time (open it in full with Read). Do this task: ${a.task}\nThen report honestly: passed (true only if you could do it without guessing), your answer in your own words, what was missing, which passages confused you (quote them), and 1–10 scores for clarity, completeness and concision FROM YOUR ROLE'S POINT OF VIEW, plus up to four fixes quoting the exact text to change.`,
  { label: `task:${a.key}`, phase: 'Audience', schema: TASK, model: 'opus' })))

// ---------------- Phase 3: the three round-1..6 personas (comparable time series) ----------------
const PERSONAS = [
  'a senior partner at a top strategy consultancy reviewing a client deliverable',
  'a design director at a top product design studio reviewing a shipped product story',
  'a pair of stakeholders reading together: a client CMO with no technical background and an agency CFO',
]
const judgesP = parallel(PERSONAS.map((p, i) => () => agent(
  `${FREEZE}\nRound ${ROUND}. You are ${p}. Read the ENTIRE file ${FILE} (a self-contained HTML walkthrough of one graded run of the "Brief Builder" pipeline; open it with Read in full, and read the repo files named below for fact checks). ${GROUND}\nWrite nothing. ${RUBRIC}\nReturn the nine scores with a one-sentence why and up to four concrete fixes each (sheet, exact quote, change).`,
  { label: `r${ROUND}:judge:${i + 1}`, phase: 'Score', schema: SCORE, model: 'opus' })))
const audits = await auditsP
const tasks = await tasksP
const judges = (await judgesP).filter(Boolean)
const taskResults = AUDIENCE.map((a, i) => ({ key: a.key, ...(tasks[i] || { passed: false, answer: '(agent died)', missing: [], confusions: [], scores: {} }) }))
const by = {}
for (const j of judges) for (const s of j.scores) { (by[s.aspect] = by[s.aspect] || []).push(s) }
const averages = Object.fromEntries(ASPECTS.map(k => [k, by[k] ? +(by[k].reduce((a, s) => a + s.score, 0) / by[k].length).toFixed(2) : null]))
const deltas = Object.fromEntries(ASPECTS.map(k => [k, (PREV.averages && PREV.averages[k] != null && averages[k] != null) ? +(averages[k] - PREV.averages[k]).toFixed(2) : null]))

// ---------------- Verdict (deterministic) ----------------
const hardFailures = audits.filter(Boolean).flatMap(a => a.hardFailures.filter(f => f.stands))
const refutedClaims = audits.filter(Boolean).flatMap(a => a.hardFailures.filter(f => !f.stands))
const hashProblems = [...audits.filter(a => a && a.hashMismatch).map(a => a.key), ...taskResults.filter(t => t.hashMismatch).map(t => t.key), ...judges.filter(j => j.hashMismatch).map((j, i) => `judge${i + 1}`)]
const tasksFailed = taskResults.filter(t => !t.passed).map(t => t.key)
const regressions = Object.entries(deltas).filter(([k, d]) => d != null && d <= -0.5).map(([k]) => k)
const below8 = Object.entries(averages).filter(([k, v]) => v != null && v <= 8.0).map(([k]) => k)
const stable = hashProblems.length === 0 && hardFailures.length === 0 && tasksFailed.length === 0 && regressions.length === 0
log(`round ${ROUND} @${HASH.slice(0, 12)}: hard=${hardFailures.length} (refuted ${refutedClaims.length}) tasksFailed=${tasksFailed.join(',') || 'none'} regressions=${regressions.join(',') || 'none'} averages=${JSON.stringify(averages)} below8=${below8.join(',') || 'none'} → ${stable ? 'STABLE candidate (no hard failures, tasks pass, no regression)' : 'NOT stable'}`)

// ---------------- Phase 4: bounded editor brief for the next pass ----------------
phase('Brief')
const softAll = audits.filter(Boolean).flatMap(a => a.softIssues.map(s => ({ from: `audit:${a.key}`, ...s })))
const taskFixes = taskResults.flatMap(t => (t.fixes || []).map(f => ({ from: `task:${t.key}`, fix: f })))
const judgeFixes = judges.flatMap((j, i) => j.scores.flatMap(s => s.fixes.map(f => ({ from: `judge${i + 1}:${s.aspect}(${s.score})`, ...f }))))
const brief = await agent(
  `${FREEZE}\nYou are the editor-in-chief for round ${ROUND + 1} of ${FILE}. Do NOT edit anything. Read the page once, then turn this round's evidence into ONE bounded change hypothesis for the next editing pass (Codex will apply it under tools/walkthrough/checks.py).\nVERIFIED HARD FAILURES (must all be fixed, first): ${JSON.stringify(hardFailures)}\nAUDIENCE TASKS: ${JSON.stringify(taskResults.map(t => ({ key: t.key, passed: t.passed, missing: t.missing, confusions: t.confusions, fixes: t.fixes })))}\nSCORES this round: ${JSON.stringify(averages)} (deltas vs round ${PREV.round || '?'}: ${JSON.stringify(deltas)})\nJUDGE FIXES: ${JSON.stringify(judgeFixes)}\nAUDITOR SOFT ISSUES: ${JSON.stringify(softAll)}\nTASK FIXES: ${JSON.stringify(taskFixes)}\nRules the page must keep: at most 10 sheets; never change blockquotes or <mark class="cited">; zero external resources; tokens not dollars as the usage figure; budget stays in words; shadow-mode labels; action titles ≤ 24 words; takeaways ≤ 20 words; ≤ 650 visible words per sheet (750 on sheet 09); palette rules; thin-space thousands.\nProduce: (1) hypothesis — one sentence naming the single aspect this pass targets and the bound (e.g. "cut sheets 02 and 10 by 30% keeping the five listed facts"); (2) at most 12 items, each an exact before → after (or CSS/JS), hard failures first, then the fixes that at least two independent sources asked for, then the cheapest clarity wins for the audience that failed its task; drop contradictory or taste-only requests and say nothing about them; (3) mustKeep — every fact/exhibit the audience tasks relied on, as a regression list.`,
  { label: `brief:r${ROUND + 1}`, phase: 'Brief', schema: BRIEF, model: 'opus' })

return { round: ROUND, hash: HASH, stable, hashProblems, hardFailures, refutedClaims, tasks: taskResults, judges: judges.length, averages, deltas, below8, regressions, detail: by, softIssues: softAll, brief }

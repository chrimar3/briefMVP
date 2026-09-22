export const meta = {
  name: 'score-round-opus',
  description: 'Three judges score WALKTHROUGH.html on the nine-aspect rubric (one round of the improvement loop; the editor pass is applied outside)',
  phases: [{ title: 'Score', detail: 'three judges, nine aspects' }],
}
const ROUND = (args && args.round) || 2
const FILE = '/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html'
const ROOT = '/Users/chrism/AI-transformation-assignment/brief-builder'
const RUBRIC = `Score each aspect 1-10 (10 = a top design firm / top consulting firm would ship it unchanged). Be strict and specific; 8 means "good, minor issues"; 9-10 means "nothing to fix".
1 concision — at most 10 sheets; one message per sheet; no passage a decision-maker would skip; word counts tight.
2 completeness — every critical fact a stakeholder needs: what it is, what this run proved, usage (the client will run on a subscription, so cost is expressed as tokens consumed in total and by model; API dollar figures belong only in a footnote and their absence from the visible sheets is correct, not a gap), time, limits and risks, what stays human, the deliverable itself, decisions needed with owners, next steps.
3 clarity — plain language a CMO, a CFO, a creative director and an engineer all follow; the three roles (AI / code / people) legible at a glance; jargon explained where used.
4 storyline — consulting-grade: the answer first; every sheet title a takeaway sentence that the evidence on that sheet supports; sources cited; logical flow with no redundancy.
5 product_framing — Brief Builder shown as a whole product: name, promise, principles, anatomy, outputs, guarantees, where it runs, who touches it — not just a sequence of steps.
6 visual_design — agency-grade: deliberate typography, hierarchy, spacing, one coherent system, not templated; the client's brand colours only on the creative sheet.
7 fact_fidelity — numbers, quotes, model ids, costs and timings match the run artifacts (spot-check at least the headline figures against ${ROOT}/runs/tier3/harness_report.json, run_manifest.json, docs/COST_MODEL.md, docs/EVIDENCE.md, fixtures/northlight_01/).
8 ux — navigation obvious (Next/Back, contents, keyboard), works when double-clicked from disk with zero dependencies, sensible on a phone, focus states, no dead ends.
9 finale — the creative brief and key visual: appealing, compliant with the brand mandatories in fixtures/northlight_01/background_brand_guidelines.md, honestly labelled as shadow-mode and as an illustration, channel specs from the table.`
const SCHEMA = { type: 'object', required: ['scores', 'overall'], properties: {
  scores: { type: 'array', minItems: 9, maxItems: 9, items: { type: 'object', required: ['aspect', 'score', 'why', 'fixes'], properties: {
    aspect: { type: 'string', enum: ['concision','completeness','clarity','storyline','product_framing','visual_design','fact_fidelity','ux','finale'] },
    score: { type: 'integer', minimum: 1, maximum: 10 }, why: { type: 'string' }, fixes: { type: 'array', items: { type: 'string' }, maxItems: 4 } } } },
  overall: { type: 'string' } } }
const PERSONAS = [
  'a senior partner at a top strategy consultancy reviewing a client deliverable',
  'a design director at a top product design studio reviewing a shipped product story',
  'a pair of stakeholders reading together: a client CMO with no technical background and an agency CFO',
]
phase('Score')
const judges = (await parallel(PERSONAS.map((p, i) => () => agent(
  `Round ${ROUND}. You are ${p}. Read the ENTIRE file ${FILE} (a self-contained HTML walkthrough of one graded run of the "Brief Builder" pipeline; open it with Read in full, and read the repo files named in the rubric for fact checks). Write nothing. ${RUBRIC}\nReturn the nine scores with a one-sentence why and up to four concrete fixes each (exact text or CSS to change, with the sheet number).`,
  { label: `r${ROUND}:judge:${i + 1}`, phase: 'Score', schema: SCHEMA, model: 'opus' })))).filter(Boolean)
const by = {}
for (const j of judges) for (const s of j.scores) { (by[s.aspect] = by[s.aspect] || []).push(s) }
const averages = Object.fromEntries(Object.entries(by).map(([k, v]) => [k, +(v.reduce((a, s) => a + s.score, 0) / v.length).toFixed(2)]))
const failing = Object.entries(averages).filter(([k, v]) => v <= 8.0).map(([k]) => k)
log(`round ${ROUND}: ${JSON.stringify(averages)} failing=${failing.join(',') || 'none'} (judges ${judges.length}/3)`)
return { round: ROUND, judges: judges.length, averages, failing, detail: by }

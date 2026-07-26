# Exam-prep report — voreas_02 second fixture, intake tool, rehearsal findings

Session 2026-07-26, night before the solution examination. Goal set by the user: be
prepared for **any** transcript / RFP / mail the evaluators produce. Everything below was
built and measured without touching any frozen file (PRD, northlight answer key, harness,
schema) or any shared runtime spec (skills/*.md unchanged).

## What was built

| Piece | What it proves |
|---|---|
| `fixtures/voreas_02/` — 6 sources, new client/industry, tier S0, + its own `answer_key.json` (same shape as v1: 5 conflicts, 6 gaps, 4 garbles, traps X1–X3) | The pipeline and the frozen harness are fixture-generic; nothing was tuned to Meltemi |
| `fixtures/voreas_02/client_voreas.json` (client config lives *in* the project folder) | `glossary/` keeps one file, so every documented default command and all 289 existing tests stay green |
| `pipeline/intake.py` + `tests/test_intake.py` (9 tests) | Arbitrary raw docs → contract-compliant project + scaffolded client config in one command; refuses to guess types; never infers the tier (DR-11) |
| `docs/DEMO_PLAYBOOK.md` | The live-demo script: intake → run → narrate → grade, failure plays, known limits |

## Harness results (frozen harness, unchanged)

| Run | Result | Note |
|---|---|---|
| voreas-prep-02 (full pipeline) | **15/17** | T3.1 2/4 conflicts, T3.3 garble T1 dropped |
| voreas-prep-03 (synthesis re-roll, same extracts) | **16/17** | T3.1 4/4 — only T3.3 garble T1 fails |

v1 (northlight) remains 17/17. The v2 exam is harder and it found real weaknesses.

## Findings (synthesis stage, sonnet; all traced to artifacts in `runs/voreas-prep-0*/`)

1. **Garble-avoidance content loss — sticky (0/2 rolls carried).** Kickoff 00:02:18 states
   two objectives in one line: the garbled `μπραντ αγουέρνες` (brand awareness) and clean
   `δοκιμή` (trial). Both rolls built the entry from the clean clause and dropped the
   client's *primary objective* entirely. Extract level is correct both times (flagged,
   glossary match proposed — T1.4 passes). Root cause is a spec gap: SYNTHESIS.md
   constrains invention but has **no coverage rule** obliging a garble-flagged claim to
   survive assembly. v1 could not see this — its garbled term had no clean escape-hatch
   clause beside it.
2. **Contradiction-flattening — roll-dependent (1/2).** Roll 1 reinterpreted the
   guidelines-vs-CMO influencer clash into compatibility ("guidelines govern the selection
   of micro-influencers", qualifier=implied) instead of surfacing the conflict. Roll 2
   surfaced it correctly.
3. **Restatement citation-pairing — roll-dependent (1/2).** Roll 1 cited the transcript's
   *restatement* of the RFP for the RFP's position (C1, C3 both-sources check failed);
   roll 2 paired sources correctly.
4. **Spoken-number conversion in conflict statements — roll-dependent.** Roll 1 wrote
   "around 120, maybe 125" for «εκατόν είκοσι» — a numeral conversion (SOURCES rule-4
   spirit) that evades both trap X3 (needs `€`/separator patterns) and the runner currency
   gate (`_MONEY_*` regexes require a currency mark). Known blind spot: **unmarked**
   numeral conversion is machine-invisible today.
5. **Haiku formatting hazards — probabilistic, gates catch them.** (a) anchors quoted
   *around* a mid-sentence parenthetical → verbatim-citation gate refuses (3/4 attempts
   failed on one line); (b) fidelity annotator splits a two-speaker collided line →
   annotate-never-repair gate refuses (2/2 in one leg, 0/1 in another). Both recovered via
   `--stage` resume. Fixture hazard lines were re-calibrated to hard-but-fair; seeded
   graded challenges untouched (re-verified verbatim-complete after edits).

## Decisions queued for the human (shared-spec changes, not made unilaterally)

- SYNTHESIS.md: one-sentence coverage rule for garble-flagged claims (fixes finding 1).
- SOURCES.md / TRANSCRIPTS.md: one-sentence hardenings for finding 5a/5b.
- Currency gate: extend to unmarked spoken-number conversions? (finding 4 — gate change.)

## Cost & models (measured, `diagnostics/repair_log.jsonl` sums)

- voreas-prep-01 $0.83 (aborted runs, diagnostics) · voreas-prep-02 $3.81 (full) ·
  voreas-prep-03 $3.26 (synthesis+render re-roll; its log file also contains prep-02's
  copied entries — attribution corrected here). **Total $7.90.**
- Resolved model IDs: `claude-haiku-4-5-20251001` (classify, fidelity, extract),
  `claude-sonnet-5` (synthesize, render). Orchestrator: `claude-fable-5`.

## Addendum — artifact mining pass (2026-07-26, four read-only auditors, key claims re-verified)

Auditors were barred from the answer key; that they independently rediscovered the C4
key-messages drop is cross-validation. New verified findings, by importance:

1. **The 16/17 brief asserts the superseded launch date.** `voreas-prep-03/brief.json`
   timeline holds ONE entry: "mid-March 2027" (confidence high). The client's written,
   declared-final Feb 14 exists only inside the conflict object and a question. The harness
   cannot see this: T3.1/C2 passes because the conflict exists. Harness-green ≠
   account-lead-ready. Candidate deterministic gate (runner-side `check_synthesis`, not the
   frozen harness): a field with an open conflict must not carry one position as its sole
   entry.
2. **Render-stage invention:** EN render deliverable 2 says "hero video and key visuals"
   cited to `[rfp_voreas §5]` — brief.json and the RFP say only "video". "hero" leaked in
   from elsewhere in the corpus (the kickoff's garbled χίρο βίντεο is the likely vector) and
   was attributed to a source that never wrote it. T2.4 passes (tag present and resolvable).
   Candidate deterministic check: no new content tokens on cited render lines vs the brief.
3. **Email supersession collapse has a spec root cause.** Jan 31 has zero trace in the
   emails extract, `internal_conflicts: []` — and SOURCES.md licenses it: rule 3 says
   "record both", §5's email row says latest-position-wins when the reversal is explicit.
   The observed behavior is the predictable output of that contradiction. Reconcile §5 to
   defer to rule 3. (Same extract also dropped the guidelines-v2.0 fact from mandatories —
   the one field the spec calls asymmetric — and the March-plan/board-rationale context.)
4. **Open-question quality is the weakest layer** (PRD explicitly cares about this
   precision): 4–5 of 16–17 questions duplicate conflict objects; one asks the client what
   their own guidelines say; one re-asks the launch date the client declared final in
   writing; near-duplicates unmerged; most render without their linked_evidence citations.
   Candidate gate: a question whose field matches an open conflict is a duplicate.
5. **Readiness is conflict-blind:** 4 open conflicts (budget and timeline among them) still
   verdicts `ready_for_review`. Whether conflicts should gate readiness is a policy call.
6. Minor: EL render wrote "καμπάνια λανσαρίσματος" where the glossary says keep_latin
   "launch" — but the quoted source itself wrote the Greek word; keep_latin's scope over
   source-faithful paraphrase is genuinely ambiguous and worth one clarifying line in
   TRANSLATION.md. Retracted pop-up rides as `conditional` (defensible; `retracted` would
   be truer).

Provenance note: an auditor flagged prep-02/prep-03 email extracts as byte-identical — that
is the experiment's design (the re-roll held extraction constant via a copied run dir), not
a pipeline defect.

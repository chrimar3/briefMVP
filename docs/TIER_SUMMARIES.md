# What each tier delivered, in plain words

One paragraph per tier: what it added, what proved it, and what stays with people. The formal
definitions of done are in `docs/TIERS.md`; each tier's acceptance record is
`runs/tier_<N>_report.md`.

## The timebox: what was the case study, and what came later

The hiring case study asked for a working demo of an AI briefing pipeline for a ~40-person Athens
agency (`docs/PRD.md`). **The case-study deliverable is Tiers 0–4**, all committed on 24 July 2026
(`af1527d` … `fe2707e`) against a "Saturday noon" cutoff. Everything from Tier 5 on was
authorised by the owner in September 2026, after the case study, and is not part of the
submission: an agency operating layer around the pipeline (Tiers 5–7) and two rounds of an
independent whole-project review (Tiers 8–9). The build method was the same throughout: the
specification and the grader were written and frozen before the pipeline ran, one tier at a time
with a human stop after each, development agents bound by `CLAUDE.md`.

| Tier | When | In plain words | Proved by | Stays human |
|---|---|---|---|---|
| 0 | 24 Jul | The skeleton: the AI helpers defined, the plain-code checks and runner stubbed, the tests set up | deterministic tests | approving the scaffold and the readiness policy |
| 1 | 24 Jul | One document in, cited facts out: the meeting transcript is read into facts, each with the exact line it came from; the grader is written and frozen | a model run graded by the frozen harness | — |
| 2 | 24 Jul | The whole first stage: every source read, disagreements found, one brief assembled and written out in Greek and English | a model run graded by the harness | — |
| 3 | 24 Jul | The exam: 17 machine checks against the hidden answer key, all passed on the synthetic northlight project | the graded run `runs/tier3`, 17/17 | — |
| 4 | 24 Jul | Stretch: after a person signed the brief, two creative-brief drafts (Sonnet and Opus) from the same signed brief, with channel specs copied from a fixed table | two drafts, specs matched byte for byte | the sign-off; creative was then shadow-only |
| 5 | 19 Sep | Agency quality around the brief: which facts are covered, which questions matter, approvals bound to the exact version, a campaign checklist, effort and rework recording | deterministic tests and a fault-injection benchmark, no model calls | every approval and triage decision |
| 6 | 20 Sep | Creative can be delivered: a draft is registered, a named creative lead approves the exact files, and only then is a local release package made | deterministic tests, no model calls | creative approval and release |
| 7 | 20 Sep | Coordination: project status across runs, clarification packs for the client, package verification and withdrawal, deadlines between deliverables | deterministic tests, no model calls | every decision; nothing is ever sent automatically |
| 8 | 22–23 Sep | Review round 1: independent judges scored the project; the ten moves they asked for — honest documents, least-privilege AI helpers that ignore instructions hidden in sources, separation of duties with a tamper-evident log, a usage ruler in tokens, defect records, a data-declaration gate, the pilot pack | deterministic tests, no model calls | the owner's four decisions of 22 Sep |
| 9 | 23–24 Sep | Review round 2: a blind third test project written by someone who never saw the prompts; hardening of how the AI helpers are called; coding agents blocked from human decisions; then the **first measured runs of the routing now in use** — 17/17 in 5 of 7 graded runs, the blind project 17/17 with its sealed extra checks 21/21, planted instructions ignored — and a record of the defects the grader cannot see | seven live model runs graded by the frozen harness, plus deterministic tests | the owner's decisions on the regenerated brief (prepared, not yet recorded) and the creative comparison after them |

## What no tier has proved

Review time, usefulness to an account lead, adoption, Greek quality as judged by a native
editor, results on real client documents, and creative quality under the current routing. Those
are pilot measures (`docs/pilot/SCORECARD.md`) or wait for the owner's sign-off on
`runs/r2-live/nl-r1`. Every run so far is on synthetic fixtures.

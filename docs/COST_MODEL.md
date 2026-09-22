# Usage model — tokens by model, re-derived from measured runs

> **Era banner — read this first.** Every *complete* brief measured so far ran on the
> **Haiku-era routing**: haiku extraction and no verifier. That includes the graded evidence run
> `runs/tier3`. The **current routing** (human decision 2026-07-30: sonnet extraction plus a
> risk-routed `verify-extract` second check per source) has been measured on **one source only**
> (§3). It is **unmeasured end to end** until the owner-authorised live re-baseline:
> 3 rolls × `northlight_01` + `voreas_02`, round 2 (`docs/OPERATING_DECISIONS.md` § 2026-09-22,
> decision 1; protocol in `docs/EVAL_RECORD.md` §7). Every figure below carries its era.

**Unit.** The client is expected to run on a subscription, so usage is reported in **tokens by
model**: fresh input, output, cache read and cache write. Dollars appear only in the labelled
footnote at the end. Whether the value unit should be *share of a subscription usage window* or
*metered API spend* is an **open owner decision** (§5).

**Ruler.** `python3 eval/cost_report.py <runs dir | one run>` is the measuring tool. Its default
output is tokens by model per stage and in total. It counts every attempt, including repairs,
failed attempts and the per-source `verify-extract` call. Attempts copied into resumed runs are
counted once. Per-brief figures list every complete run as clean, repaired or resumed, and print
the all-runs mean next to the clean-only mean. `--tokens` gives the per-stage category view;
`--usd` gives the dollar footnote. Before round 1 the ruler dropped the verifier and silently kept
only clean runs; both faults are fixed and tested in `tests/test_cost_report.py`.

**Where the numbers come from.** Figures marked **[committed]** come from run directories
committed to this repo (`runs/tier3`, `runs/voreas-prep-02`, `runs/voreas-prep-03`), so any clone
reproduces them. Figures marked **[local store]** come from gitignored run directories on the
operator's machine (the checkout's `runs/`), measured with the same command on 2026-09-23. They are
reproducible there but not on a fresh clone.

## 1. The graded run — one client brief, Haiku-era routing [committed]

`python3 eval/cost_report.py runs/tier3`. The run was assembled from resumed legs (steps 1–7
carried from earlier runs) and includes one extraction repair, so it is neither a clean run nor a
single roll.

| stage | model | calls | fresh input | output | cache read | cache write | total |
|---|---|---:|---:|---:|---:|---:|---:|
| classification | haiku | 1 | 25 | 2,571 | 14,642 | 11,439 | 28,677 |
| fidelity check | haiku | 1 | 25 | 3,943 | 12,339 | 10,604 | 26,911 |
| extraction (4 sources + 1 repair) | haiku | 5 | 2,429 | 72,751 | 296,455 | 106,418 | 478,053 |
| synthesis | sonnet | 1 | 10 | 30,871 | 74,364 | 60,575 | 165,820 |
| bilingual render | sonnet | 1 | 10 | 49,760 | 155,278 | 80,311 | 285,359 |
| **Stage 1 / brief** | haiku 533,641 · sonnet 451,179 | 9 | | | | | **984,820** |
| creative A/B (Stage 2) | opus | 1 | 1,354 | 7,724 | 28,829 | 25,566 | 63,473 |
| creative A/B (Stage 2) | sonnet | 1 | 1,356 | 7,800 | 55,610 | 21,675 | 86,441 |
| **all stages** | | 11 | 5,209 | 175,420 | 637,517 | 316,588 | **1,134,734** |

About **0.98 M tokens for one Stage-1 brief** (54% haiku, 46% sonnet). At ~15 briefs a month
(PRD A2) that is ~15 M tokens a month, **at Haiku-era routing**.

## 2. Haiku-era spread across every complete northlight brief [local store]

`python3 eval/cost_report.py runs` over the local run store finds 10 complete Stage-1 briefs on
`northlight_01`, all Haiku-era:

| selection | n | mean tokens / brief | haiku | sonnet |
|---|---:|---:|---:|---:|
| all complete runs (clean + repaired + resumed) | 10 | 848,845 | 342,718 | 506,127 |
| clean runs only (every stage one attempt) | 7 | 754,764 | 276,181 | 478,583 |

The individual runs range from **556,121** (`tier3-confirm2`, clean) to **1,218,632**
(`evidence-20260729`, repaired and resumed). The graded run (984,820) sits above the clean mean
because it carries an extraction repair. Repairs are part of real usage: the all-runs mean is the
planning figure, and the clean-only mean is a floor. On `voreas_02` (6 sources), the two complete
Haiku-era briefs used **1,309,915** and **1,792,417** tokens [committed]. Both needed repairs, and
the second is a synthesis/render re-roll on the first's extracts.

## 3. The current routing — measured on one source [local store]

`python3 eval/cost_report.py runs/routing-validate-01`. This is an extraction-only run on the
northlight transcript made on 2026-07-29 under the routing adopted on 2026-07-30.

| stage | model | calls | fresh input | output | cache read | cache write | total |
|---|---|---:|---:|---:|---:|---:|---:|
| extraction (transcript) | sonnet | 2 | 40 | 39,621 | 424,321 | 90,066 | 554,048 |
| verify-extract | sonnet | 1 | 6 | 6,587 | 20,413 | 17,689 | 44,695 |
| **transcript leg** | sonnet | 3 | 46 | 46,208 | 444,734 | 107,755 | **598,743** |

The old ruler reported 554,048 for this run. It missed the verifier's 44,695 tokens (7.5% of the
leg).

For comparison, the same transcript leg in the Haiku era [local store]:

| run | extraction attempts | tokens |
|---|---:|---:|
| `tier3-confirm2` | 1 | 56,965 |
| `cost-c1` | 1 | 61,734 |
| `tier3-confirm` | 1 | 65,689 |
| `tier3` (graded) | 2 | 295,774 |

- **First sonnet attempt:** 91,918 tokens, against 56,965–65,689 for a clean haiku attempt.
- **Second sonnet attempt:** 20 turns and 462,130 tokens, 86% of them cache reads.
- **Where the leg goes:** 462,130 of the 598,743 tokens (77%) are the second attempt. The leg
  is 2.0× the graded run's transcript leg, which also needed two attempts.

This is one source and one roll. It says nothing reliable about a full brief under the current
routing.

**Verifier routing.** The verifier runs on sonnet whenever an extract carries any risk class,
otherwise on the base (haiku) model. `python3 eval/cost_report.py runs --risk-replay` replays
`pipeline/extraction.py:risk_classes` over every stored extract, counting byte-identical copies
once. Result: **66 of 66** unique extracts [local store] and **10 of 10** [committed] route to
sonnet. Removing `figures`, the broadest class, would move only 2 of the 66 to haiku. So on the
evidence so far, **every per-source verification runs on sonnet**. That is the planning assumption
until the owner decides otherwise (`docs/EVAL_RECORD.md` §6).

## 4. Capacity returned — reconciled to the PRD's own assumptions

All inputs are PRD assumptions, none of them measured. Validating them is pilot week 1 (PRD §8).

| input | value | source |
|---|---|---|
| A1 time per brief today | 2 h = 120 min | PRD §4 |
| A2 briefs per month | ~15 → 180 / year | PRD §4 |
| A4 loaded labour cost | ~€19–20 / h | PRD §4 |
| attention per brief with the tool | 50 min (20 assembling + 30 reviewing) | unvalidated target; `WALKTHROUGH.html` sheet 10, `docs/pilot/SCORECARD.md` §3 |

**(120 − 50) min × 180 briefs ÷ 60 = 210 h / year; 210 h × €19–20 = €3,990–4,200 / year.** The
labour per brief today is A1 × A4 = **€38–40**.

**Why "~€5–6k / year" is superseded.** PRD §10 and earlier versions of this document quoted
"~€5–6k/yr of returned hours" without showing how it was derived. The PRD's own A1 × A2 × A4
arithmetic does not produce it at the conservative attention figure. It is reachable only if
attention drops to the PRD's <30-min review target *and* assembly time is ignored:
(120 − 30) × 180 ÷ 60 = 270 h, and 270 h × €19–20 = €5,130–5,400. PRD §7 says to "quote the
conservative floor". The floor is 210 h and **€4.0–4.2k**, and that is the figure to use. The PRD
itself is frozen and keeps its original sentence.

Either way, returned hours only fund the pilot. The case rests on the variance floor and reduced
downstream rework (PRD §10), which the pilot scorecard measures (`docs/pilot/SCORECARD.md`).

## 5. Open owner decision — the value unit

The ratio "model usage vs labour" needs usage and labour in the same unit. There are two options,
and the owner has not yet chosen between them:

- **Subscription window.** Usage is a share of a plan's usage allowance per period. Tokens by
  model are the direct measure. The relevant question becomes "how many briefs a month fit in the
  window, at current routing", and that needs the round-2 re-baseline.
- **Metered API.** Usage is priced per token at list or contract rates (PRD DR-1's production
  shape: prompt caching on the static skeleton). This is the only form in which a euro ratio
  against €38–40 of labour is meaningful. The measured API path (`eval/substrate_spike.py
  --transport api`) has not run: it needs explicit credentials (CLAUDE.md rule 4).

Until the decision is made, stakeholder material leads with tokens by model and era. Dollar
figures stay footnotes.

## 6. Where the tokens go — measured decomposition, graded run (Haiku-era) [committed]

`python3 eval/cost_report.py runs/tier3 --tokens`. Two categories dominate. Output tokens are
**64%** of list-rate-attributed spend and cache writes **31%**. Cache reads are 5% and fresh input
1%, because work orders pass paths rather than content. Output tokens far exceed the artifact each
stage produces:

| stage | output tokens | deliverable ≈ | inflation |
|---|---:|---:|---:|
| render (sonnet) | 49,760 | ~6,650 tok (both renders) | ~7.5× |
| synthesis (sonnet) | 30,871 | ~7,380 tok (brief.json) | ~4.2× |
| extraction ×4+1 (haiku) | ~14,550 / call | ~1,530 tok / extract | ~7–13× |

The gap is thinking, narration between tool calls, and content echoed outside the Write call; no
deterministic gate consumes any of it. The cache-write share is the substrate itself: each stage
is a fresh CLI process that re-writes its prompt and every file it reads, across 5–10 turns.
These two numbers set the optimisation order: output shape first (cost audit C1), substrate
second (C4).

## 7. Levers already in the architecture

- **Model tiering per stage (DR-3).** Haiku for schema-following stages, sonnet for judgment. The
  2026-07-30 routing moved extraction to sonnet and added a verifier. §3 shows the first
  measurement, and the re-baseline will show the rest.
- **Prompt caching on the static skeleton.** The skeleton files and the schema are identical on
  every call. On the production API substrate that is a large discount on cached input; on the
  demo substrate it shows up as the cache-write share in §6.
- **Extract-then-synthesize (DR-2).** Synthesis runs over compact extracts rather than raw
  sources, so usage and traceability improve together.
- **Batch where latency permits.** This applies to non-interactive stages on the API substrate.

## 8. Substrate spike (cost-audit C4) — a measured negative result

`eval/substrate_spike.py --transport cli` ran extraction (Haiku-era) as single-turn, zero-tool
calls. Its usage was flat against the multi-turn pipeline: the turn structure is not what the
demo substrate charges for, the fixed per-invocation CLI overhead is (`runs/cost_c4_report.md`).
3 of 4 single-call extracts passed clean. The transcript fell into the seeded garbling trap and
silently repaired «μπραντ αγουέρνες» to "brand awareness"; the gate caught it, which is the case
for the gated repair loop. Only the metered API path (`--transport api`, the one sanctioned
non-subagent path, CLAUDE.md rule 4) can remove that overhead, and it has not run.

---

### Footnote — dollars (demo substrate, CLI-reported `cost_usd`, list price; not the stakeholder unit)

`python3 eval/cost_report.py <path> --usd`. All figures are **Haiku-era** unless stated.

| figure | value | source |
|---|---|---|
| Stage-1 per brief, the two clean full runs `tier3-confirm` / `tier3-confirm2` | $2.44 / $2.07, mean **$2.25** | [local store] |
| Stage-1 per brief, northlight, clean runs only (n=7) | mean $2.53 (range $2.07–3.20) | [local store] |
| Stage-1 per brief, northlight, all complete runs (n=10) | mean $2.60 (range $2.07–3.20) | [local store] |
| graded run `tier3`, Stage 1 / Stage 1 + creative A/B | $2.81 / **$3.55** | [committed] |
| creative A/B, both drafts (`tier3`) | $0.74 | [committed] |
| current routing, transcript leg only (`routing-validate-01`) | $1.47 (extraction $1.26 + verifier $0.21) | [local store] |

**Previously published ratio.** Against ~€38 of labour per brief (PRD A1 × A4, an assumption), the
earlier headline of $2.25/brief on the two clean runs gave **~17:1**. On the fixed ruler's clean
mean over all 7 clean northlight runs ($2.53), the ratio is ~15:1. Both are Haiku-era and both
use the demo substrate. PRD §10 projected <€0.50/brief (~76–80:1) for the production API
substrate. That is a projection: nothing in this repo has run on that substrate. The PRD's point
still holds: model usage is the smallest line in the business case, and management attention
belongs on review time, adoption and glossary/template upkeep.

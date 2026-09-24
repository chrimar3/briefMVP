# Usage model — tokens by model, re-derived from measured runs

> **Era banner — read this first.** §1 and §2 are the **current routing**
> (sonnet extraction + sonnet verify-extract, owner decision 2026-09-23 #5; classify and
> fidelity check on haiku; synthesis and render on sonnet), measured in the round-2 live
> re-baseline on 2026-09-23/24:
> six complete briefs on three synthetic fixtures, committed under `runs/r2-live/`. §3 is the
> **Haiku-era routing** of July (haiku extraction, no verifier), kept as history: it is what the
> graded run `runs/tier3` used, and it is **not** a planning figure any more. Every figure below
> carries its era.

**Unit.** The client is expected to run on a subscription, so usage is reported in **tokens by
model**: fresh input, output, cache read and cache write. Dollars appear only in the labelled
footnote at the end. Whether the value unit should be *share of a subscription usage window* or
*metered API spend* is an **open owner decision** (§5).

**Ruler.** `python3 eval/cost_report.py <runs dir | one run>` is the measuring tool. Its default
output is tokens by model per stage and in total. It counts every attempt, including repairs,
failed attempts and the per-source `verify-extract` call; attempts copied into resumed runs are
counted once, and symlinked run directories (`runs/latest`, `runs/r2-live/latest`) are skipped
so no run is counted twice. Per-brief figures list every complete run as clean, repaired or
resumed, and print the all-runs mean next to the clean-only mean (rounded to the token). `--tokens`
gives the per-stage category view, `--verifier` what happened to each verifier finding, and
`--usd` the dollar footnote. Faults fixed and tested in `tests/test_cost_report.py`: the ruler
once dropped the verifier, once kept only clean runs, and until round 2 counted a `latest`
symlink as a second brief.

**Where the numbers come from.** Figures marked **[committed]** come from run directories
committed to this repo (`runs/r2-live/*`, `runs/tier3`, `runs/voreas-prep-02`,
`runs/voreas-prep-03`, `runs/routing-validate-01`), so any clone reproduces them. Figures marked
**[local store]** come from gitignored run directories on the operator's machine, measured with
the same command on 2026-09-23; they cannot be re-derived from a clone.

## 1. The current routing — tokens by model per brief (round 2, measured) [committed]

`python3 eval/cost_report.py runs/r2-live`. Round-2 prompts, CLI 2.1.280 with `--restricted`,
`--no-session-persistence` and per-stage deny rules; resolved models `claude-haiku-4-5-20251001`
and `claude-sonnet-5` (from the manifests). Every roll ran the whole pipeline from the readiness
gate; no run resumed another. **No run was clean**: each needed at least one repair, so the
clean-only mean has n = 0 on every fixture, and the all-runs mean is the figure.

| run | fixture (sources) | frozen harness | wall time | haiku | sonnet | **total** |
|---|---|---|---:|---:|---:|---:|
| nl-r1 | northlight_01 (4) | 17/17 | 11.2 min | 54,715 | 541,984 | **596,699** |
| nl-r2 | northlight_01 (4) | 17/17 | 13.6 min | 96,701 | 625,643 | **722,344** |
| nl-r3 | northlight_01 (4) | 16/17 | 13.1 min | 66,920 | 702,009 | **768,929** |
| vo-r2 | voreas_02 (6) | 17/17 | 21.8 min | 107,357 | 1,207,277 | **1,314,634** |
| vo-r3 | voreas_02 (6) | 17/17 | 23.1 min | 128,876 | 1,140,156 | **1,269,032** |
| lv-r1 | levanta_03 (4, blind) | 17/17 | 18.1 min | 77,647 | 809,858 | **887,505** |

| per-brief mean (all complete runs) | n independent | haiku | sonnet | **total** |
|---|---:|---:|---:|---:|
| northlight_01 | 3 | 72,779 | 623,212 | **695,991** |
| voreas_02 | 2 | 118,116 | 1,173,716 | **1,291,833** |
| levanta_03 | 1 | 77,647 | 809,858 | **887,505** |
| pooled, all six briefs (three fixtures) | 6 | 88,703 | 837,821 | **926,524** |

About **90%** of the tokens are sonnet (5,026,927 of 5,559,143 over the six briefs). The spread is
driven by the fixture more than by the roll: the six-source voreas briefs use about 1.9× the
four-source northlight briefs. The pooled mean is a planning convenience across three different
synthetic projects, not a property of any one of them; `eval/cost_report.py` prints only the
per-fixture means.

**What the six briefs do not include.** The refused run `vo-r1` stopped at synthesis after two
attempts (the conflict-consistency gate; `docs/EVAL_RECORD.md` §10) and used **649,965** tokens
(haiku 97,278 · sonnet 552,687) without producing a brief. The injection canary
(`runs/r2-live/canary-injection`, extraction only, two sources) used 111,486. The whole
round-2 ledger, every attempt of all eight manifests, is 6,320,594 tokens (haiku 629,494 ·
sonnet 5,691,100).

**By stage, every attempt of the eight manifests** (`--tokens`): extraction 50 calls (sonnet),
verification 36 (sonnet), fidelity check 10 and classification 7 (haiku), synthesis 8 and render
8 (sonnet). Output tokens are 58% and cache writes 37% of list-rate-attributed spend; cache reads
5%; fresh input under 1%.

**Against the July figures.** The northlight mean under the current routing (695,991) is *lower*
than the Haiku-era all-runs mean (848,845, n = 10 [local store]) and the graded run (984,820),
while its sonnet share rose from about 60% to 90%. Round 2 changed the prompts, the repair orders
and the model seam at the same time as it measured the routing, so the drop cannot be attributed
to any one change. On a subscription, sonnet tokens draw more of the usage window than haiku
tokens, so the model split matters as much as the total.

## 2. Monthly usage — an estimate from PRD A2, not a measurement

PRD §4 assumption A2 is ~15 briefs a month. At the pooled current-routing mean:

**15 × 926,524 ≈ ~13.9 M tokens a month** (about 90% sonnet). **Estimate**, with these bounds:

| assumption | tokens / month |
|---|---:|
| every brief like northlight_01 (695,991) | ~10.4 M |
| pooled mean of the six briefs (926,524) | **~13.9 M** |
| every brief like voreas_02 (1,291,833) | ~19.4 M |
| pooled mean plus one refused run per six briefs (like vo-r1) | ~15.5 M |

The real mix of project sizes, the repair rate on real inputs and the refusal rate are unknown
until the pilot (go-live T-02 measures them). Creative drafting (Stage 2) is not in these figures:
no creative has been generated under the current routing yet (pending: owner sign-off on
`runs/r2-live/nl-r1`, then the creative A/B); the July A/B used 149,914 tokens for two drafts (§3).
The July planning figure (~15 M tokens a month at 0.98 M per brief) is superseded by this section.

## 3. The Haiku-era routing — historical [committed and local store]

These figures describe the July routing (haiku extraction, no verifier). They are kept because
the graded evidence and the tier reports quote them; they are not a planning figure.

**The graded run** (`python3 eval/cost_report.py runs/tier3`) [committed], assembled from resumed
legs with one extraction repair:

| stage | model | calls | total tokens |
|---|---|---:|---:|
| classification | haiku | 1 | 28,677 |
| fidelity check | haiku | 1 | 26,911 |
| extraction (4 sources + 1 repair) | haiku | 5 | 478,053 |
| synthesis | sonnet | 1 | 165,820 |
| bilingual render | sonnet | 1 | 285,359 |
| **Stage 1 / brief** | haiku 533,641 · sonnet 451,179 | 9 | **984,820** |
| creative A/B (Stage 2) | opus 63,473 · sonnet 86,441 | 2 | 149,914 |
| **all stages** | | 11 | **1,134,734** |

**The spread** [local store]: 10 complete Haiku-era northlight briefs, all-runs mean 848,845
(haiku 342,718 · sonnet 506,127), clean-only mean 754,764 (n = 7), range 556,121–1,218,632. On
voreas_02 the two Haiku-era briefs used 1,309,915 and 1,792,417 tokens [committed].

**The first current-routing leg** (`runs/routing-validate-01`) [committed]: one transcript
extraction leg on 2026-07-29, 598,743 tokens (extraction 554,048 in two attempts + verifier
44,695), against 295,774 for the graded run's transcript leg. It was the only current-routing
measurement until round 2; §1 replaces it as the planning basis.

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

The floor counts account-lead minutes only. Two corrections apply before it is set against what
the pilot costs:

- **Net of the Tier 5–7 roles.** The agency layer adds minutes for the bilingual reviewer,
  traffic, the creative lead, champions and the operator. The net measure is per brief,
  `baseline_team_min − total_team_min` (`net_team_minutes`, reported by `eval/pilot_scorecard.py`
  from the retro rows; `docs/pilot/SCORECARD.md` §3). Every 10 added non-lead minutes per brief
  remove 30 h a year (10 × 180 ÷ 60), about €570–600 at A4.
- **The cost side.** The pilot's people hours are a planning range of 68.8–116.2 h over four
  weeks across all roles (`docs/pilot/PILOT_INVESTMENT.md` §1); rates other than A4, seats and
  usage are owner inputs. Usage under the current routing is now measured per brief (§1) and
  estimated per month (§2); its price depends on the value-unit decision (§5).
  Net value per year = returned hours × rate − running cost (seats or usage, upkeep of glossaries
  and the spec catalog). Break-even of the pilot's hours at the 70-minute floor is 59–100 briefs,
  3.9–6.6 months at A2 (`PILOT_INVESTMENT.md` §4). Go-live decision D-27 turns this into a
  spending ceiling; an unset ceiling means no start.

Either way, returned hours only fund the pilot. The case rests on the variance floor and reduced
downstream rework (PRD §10). The pilot does not price either: it counts the variance floor
through the retro side-by-side against the briefs the agency actually wrote
(`docs/pilot/SCORECARD.md` §2, reported only), and downstream rework waits for quarter 1 (`docs/pilot/GO_LIVE_DECISIONS.md` D-19).

## 5. Open owner decision — the value unit

The ratio "model usage vs labour" needs usage and labour in the same unit. There are two options,
and the owner has not yet chosen between them:

- **Subscription window.** Usage is a share of a plan's usage allowance per period. Tokens by
  model are the direct measure (§1), and the question becomes "how many briefs a month fit in the
  window at the current routing": §2's ~13.9 M tokens a month, about 90% sonnet, is the input.
- **Metered API.** Usage is priced per token at list or contract rates (PRD DR-1's production
  shape: prompt caching on the static skeleton). This is the only form in which a euro ratio
  against €38–40 of labour is meaningful. The measured API path (`eval/substrate_spike.py
  --transport api`) has not run: it needs explicit credentials (CLAUDE.md rule 4).

Until the decision is made, stakeholder material leads with tokens by model and era. Dollar
figures stay footnotes.

## 6. Where the tokens go — measured decomposition

**Current routing** (`python3 eval/cost_report.py runs/r2-live --tokens`) [committed]: output
tokens are 58% of list-rate-attributed spend and cache writes 37%; cache reads 5%; fresh input
under 1%, because work orders pass paths rather than content. Synthesis averaged 8.0 turns and
render 7.6; extraction and verification 5.0 each.

**Haiku era, the graded run** (`python3 eval/cost_report.py runs/tier3 --tokens`) [committed]:
output 64%, cache writes 31%. Output tokens far exceeded the artifact each stage produced:

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
  2026-07-30 routing moved extraction to sonnet and added a verifier; §1 measures the result.
- **Prompt caching on the static skeleton.** The skeleton files and the schema are identical on
  every call. On the production API substrate that is a large discount on cached input; on the
  demo substrate it shows up as the cache-write share in §6.
- **Extract-then-synthesize (DR-2).** Synthesis runs over compact extracts rather than raw
  sources, so usage and traceability improve together.
- **Fewer repairs.** Every §1 run needed at least one repair; repairs are a direct usage lever
  (`python3 eval/repair_analysis.py runs/r2-live` lists the recurring gate violations).
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

`python3 eval/cost_report.py <path> --usd`.

| figure | value | era · source |
|---|---|---|
| Stage-1 per brief, northlight_01, all complete runs (n=3) | mean $1.78 (range $1.54–1.92) | current · [committed] `runs/r2-live` |
| Stage-1 per brief, voreas_02, all complete runs (n=2) | mean $3.55 ($3.55–3.55) | current · [committed] |
| Stage-1 per brief, levanta_03 (n=1) | $2.70 | current · [committed] |
| Stage-1 per brief, the two clean July runs `tier3-confirm` / `tier3-confirm2` | $2.44 / $2.07, mean $2.25 | Haiku-era · [local store] |
| Stage-1 per brief, northlight, all complete July runs (n=10) | mean $2.60 (range $2.07–3.20) | Haiku-era · [local store] |
| graded run `tier3`, Stage 1 / Stage 1 + creative A/B | $2.81 / $3.55 | Haiku-era · [committed] |
| creative A/B, both drafts (`tier3`) | $0.74 | Haiku-era · [committed] |

**Previously published ratio.** Against ~€38 of labour per brief (PRD A1 × A4, an assumption),
the July headline of $2.25/brief gave **~17:1** (Haiku-era). On the current routing's northlight
mean ($1.78) the same arithmetic gives ~21:1. Both use the demo substrate. PRD §10 projected
<€0.50/brief (~76–80:1) for the production API substrate. That is a projection: nothing in this
repo has run on that substrate. The PRD's point still holds: model usage is the smallest line in
the business case, and management attention belongs on review time, adoption and
glossary/template upkeep.

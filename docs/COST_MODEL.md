# Cost model — re-derived from measured runs

> PRD §10 estimated "<€0.50/brief" up front. This document replaces that estimate with what the
> pipeline **actually spent**, taken from `total_cost_usd` in every `run_manifest.json`.
> Reproduce it: `python eval/cost_report.py`. Costs are USD; treat $ ≈ € for a conservative ratio.

## 1. Measured cost — one client brief (Stage 1)

Across the two clean full runs (`tier3-confirm`, `tier3-confirm2` — every stage one attempt):

| Stage | Model | Mean | Range |
|---|---|---|---|
| classification | haiku | $0.035 | 0.034–0.036 |
| fidelity check | haiku | $0.042 | 0.041–0.043 |
| extraction (×4 sources) | haiku | $0.480 | 0.447–0.514 |
| synthesis | sonnet | $0.891 | 0.888–0.893 |
| bilingual render | sonnet | $0.806 | 0.654–0.959 |
| **Stage 1 / brief** | | **$2.25** | **2.07–2.44** |

**Stage 2 (creative, shadow):** the sonnet-vs-opus A/B cost **$0.74 for both drafts**
(~$0.37 for a single creative brief). In production Stage 2 is one draft, not an A/B.

Judgment work dominates: **synthesis + render (both Sonnet) are ~75% of the brief.** The four
Haiku extraction calls plus classification and fidelity are ~$0.56 combined — the model-tiering
decision (DR-3) is doing exactly what it was meant to.

## 2. This is ~4× the PRD estimate — and the gap is substrate, not arithmetic

$2.25 ≈ €2.08 against §10's €0.50 — roughly **4×**. The earlier "~7×" figure in the tier reports
included a repair round and the creative A/B in the per-brief number; the clean Stage-1 figure is
the honest one. The gap is **not** a token-counting error in §10. It is the demo substrate:

| | PRD §10 model | This demo |
|---|---|---|
| Unit of work | one metered API call per stage | one **Claude Code subagent** per stage |
| Turns per stage | 1 | ~5 (reads files, self-checks, writes) |
| Static skeleton | prompt-cached (−90% on cached input) | pays cache-**creation** each call |
| Harness/orchestration | none | Claude Code runtime overhead |

§10 modeled the **production** substrate (DR-1: enterprise API, prompt caching on the static
skeleton). The demo runs on the developer subscription via Claude Code subagents — the
"substrate-dependent" row in the README. Production removes most of the multiplier; it is a
config decision (a two-way door), not a redesign.

## 3. The number that carries the case: cost vs labour

Account-lead labour per brief is ~€38–40 (PRD A1 2h × A4 ~€19–20/h). Model cost against that:

| Substrate | Cost/brief | Ratio to labour |
|---|---|---|
| **Demo** (measured, this repo) | ~€2.08 | **~17:1** |
| **Production** (PRD §10 projection) | <€0.50 | ~76–80:1 |

**Even at 4× the estimate, the model-call line is ~17:1 against labour** — still the smallest line
in the business case, exactly as §10 argued. Honest numbers *strengthen* the PRD's own thesis:
the ~€5–6k/yr of returned hours merely funds the pilot; the prize is the variance floor and
reduced downstream rework (creative cycles, client revision rounds), priced in Q1 with real data.

**Where management attention actually goes** (unchanged from §10): review time, adoption, and
glossary/template upkeep — not the API bill.

## 4. Levers already in the architecture

- **Model tiering per stage (DR-3)** — Haiku for the schema-following ~$0.56; Sonnet reserved for
  the judgment ~$1.70. Confirmed by §1.
- **Prompt caching on the static skeleton** — the four skeleton files + schema are identical every
  call; on the production substrate that is −90% on cached input, which is most of the §2 gap.
- **Extract-then-synthesize (DR-2)** — synthesis runs over compact extracts, not raw sources; cost
  and reliability align (the same design that shrinks tokens produces the traceable intermediates).
- **Batch where latency permits** — −50% on non-interactive stages.

## 5. For the deck

Quote the **ratio, not the absolute**: "even on the demo substrate, model cost is ~17:1 against
account-lead labour; on the production API substrate the PRD projects ~80:1." Then make §10's
point — *cost is deliberately the smallest line* — and pivot to the real drivers. Do **not**
present €0.50 as measured; it is the production projection, and this demo has not run on that
substrate. What *is* measured is $2.25/brief here, and that already wins the labour argument.

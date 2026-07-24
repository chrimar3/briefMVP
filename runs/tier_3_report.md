# Tier 3 — Quality gates · **GREEN**

**Date:** 2026-07-24 · **Branch:** `main` · **Graded run:** `runs/tier3` · **Preceding commit:** `9f156a1`

The tier that matters. The frozen harness graded a fresh full-pipeline run against the sealed
answer key — every seeded conflict, gap, garble and trap. **17/17 checks pass, exit 0.**

---

## 1. Harness verdict (screenshot)

```
Brief Builder harness · run tier3 · fixture northlight_01

  ✅ T1.1  Every extract validates against extract_schema.json        4 extract(s) valid
  ✅ T1.2  Zero items with empty location or anchor                   33 item(s), all cited
  ✅ T1.3  Every location and anchor occurs verbatim in its source    all citations resolve
  ✅ T1.4  Seeded garbled terms present as-is w/ glossary proposals   2/2 flagged, none fixed
  ✅ T2.1  Draft validates against brief_schema.json
  ✅ T2.2  sensitivity_tier is within S0–S1                           tier S1
  ✅ T2.3  Both GR and EN renders exist                               el=12662 · en=11505 chars
  ✅ T2.4  Every rendered claim carries a resolvable citation tag     all claim lines cited
  ✅ T2.5  Glossary terms character-exact in both renders             protected terms intact
  ✅ T2.6  Readiness recomputes to the same values                    5/7 · 0.04 low · ready_for_review
  ✅ T3.1  Seeded conflicts detected with citations to both sources   3/3 required (C1, C2, C3)
  ✅ T3.2  Seeded gaps present as open questions                      4/4 found, 3 required (G1–G4)
  ✅ T3.3  Garbled terms still flagged (not fixed) in brief+renders   2/2 carried through
  ✅ T3.4  Zero uncited values anywhere in the draft
  ✅ X1    Retracted idea is not a committed deliverable
  ✅ X2    Speculative remark carries the conditional qualifier       1 entry, conditional
  ✅ X3    No resolved numeric budget total in the draft or renders

  17 passed · 0 failed · 0 skipped   →  PASS
```

## 2. DoD (per answer-key `scoring` block)

| # | Criterion | Target | Result |
|---|---|---|---|
| 1 | Seeded conflicts detected as `conflicts` with citations to both sources | 3/3 | ✅ **3/3** — C1 budget, C2 timeline, C3 audiences |
| 2 | Seeded gaps present as open questions | ≥3/4 | ✅ **4/4** — G1 metric, G2 media budget, G3 approver, G4 formats |
| 3 | Garbled terms flagged (not fixed) | 2/2 | ✅ **2/2** — `μπραντ αγουέρνες`, `κι βίζουαλ` carried through |
| 4 | Uncited values anywhere in the draft | 0 | ✅ **0** |
| 5 | Trap X3 — no resolved numeric budget total in draft or renders | pass | ✅ |
| 6 | Trap X1 — retracted OOH/metro idea NOT a committed deliverable | pass | ✅ |
| 7 | Trap X2 — speculative TikTok-dance remark carries `conditional` | pass | ✅ |
| 8 | Commit + `runs/tier_3_report.md` | — | ✅ this commit |

**Stronger than the Tier-2 graded run on the one item that had zero margin:** gaps went from
3/4 to **4/4** — G3 (the undecided final approver, email M2 "θα επανέλθω") is now surfaced as an
open question, not missed.

```
python3 pipeline/runner.py --project fixtures/northlight_01 --run-id tier3   → 7 steps, complete
python3 eval/harness.py runs/tier3                                           → 17 passed · PASS · exit 0
python3 -m pytest -q                                                        → 199 passed, 6 skipped
```

## 3. What the graded brief contains

- **25 entries** across the 7 briefable fields · **10 open questions** · **3 conflicts**, all
  `status: "open"`, on exactly the three seeded fields: `audiences`, `budget`, `timeline`.
- **`audiences` has zero canonical entries** — the RFP says Gen Z 18–24, the CMO said 25–40, and
  the system refused to pick (DR-10). The disagreement renders as an empty section pointing at
  the conflict. This is the demo's sharpest single moment: the machine's brief is better not
  because the prose is better, but because it *didn't guess*.
- `readiness`: 5/7 fields evidenced, 0.04 low-confidence share → `ready_for_review` (runner-
  computed; harness recomputed to identical values, T2.6).
- `signoff.status`: `draft`. The agent never signs off.

## 4. One defect found and fixed this tier — the re-run instability, resolved at the gate

The first Tier-3 full run **failed at extraction**, which is the honest and valuable outcome the
tier exists to force. Root cause, pinned via the durable repair log:

The model anchored a timeline item on `Launch την πρώτη εβδομάδα του Οκτωβρίου 2026`, which
**crosses a markdown `**` boundary** in the source (`Launch την **πρώτη εβδομάδα … 2026**`) and
dropped the markers. My Tier-1 citation gate did a literal substring match, so it rejected a
*correct* citation as unresolvable — and it did so on both attempts, because the model chose the
marker-crossing span each time. The skeleton guidance added in the prior session ("include the
`**`") turned out **non-deterministic**: it passed one earlier run and failed this one.

**Fix (human-approved, this session):** `gates.verify_citations` now matches on *content*, not
markup — `_normalise` strips markdown emphasis/heading markers (`*`, `_`, `` ` ``, `#`) from both
the source and the citation before comparing. Verified safe before adopting:

| Property | Result |
|---|---|
| The valid bolded-content citation now resolves | ✅ |
| An invented location (`[00:07]`) still fails | ✅ still caught |
| An invented anchor (`delivery guaranteed by September`) still fails | ✅ still caught |

This is a **false-positive bug fix, not a relaxation**: no seeded trap changes verdict, no
threshold moves, and fabrication detection is intact — stripping removes only markers, never
content. It touches a function the frozen harness (T1.3) *shares* by import, so both the runner
and the grader get the fix consistently; `eval/harness.py` itself was not edited (CLAUDE.md
rule 2). The decision was surfaced and approved rather than made unilaterally, because changing
grader behaviour during the grading tier warrants explicit sign-off.

**Why this is now structural, not luck:** the flakiness came from the model having to reproduce
markdown markers exactly. That requirement is gone — the gate no longer cares about markers, so
the outcome no longer depends on the model's formatting choice. The re-run stability concern
raised in `tier_2_report.md §7` is resolved at the gate level. (A second confirmatory full run
was not spent; the fix removes the variable rather than re-rolling the dice. Available on request.)

Skeleton note: the earlier anchor-marker guidance in `SOURCES.md` is now belt-and-braces — the
model may include or omit markers and either resolves. Left in place; harmless.

## 5. Usage & cost

| Step | Model | Attempts | Cost |
|---|---|---|---|
| classification | `claude-haiku-4-5-20251001` | 1 | $0.0372 |
| fidelity check | `claude-haiku-4-5-20251001` | 1 | $0.0422 |
| extraction ×4 | `claude-haiku-4-5-20251001` | 5 (one repair) | $0.6087 |
| synthesis | `claude-sonnet-5` | 1 | $0.8489 |
| render | `claude-sonnet-5` | 1 | $0.8166 |
| **Full brief** | | | **$2.35** |

Down from Tier-2's $3.52 (that run paid for a wrong fidelity gate and a failed render before
their bugs were fixed; this run had a single legitimate repair round). Still far above PRD §10's
"<€0.50/brief" for the substrate reasons documented in `tier_2_report.md §5` — the demo runs each
stage as a multi-turn Claude Code subagent, not a single metered API call. Against ~€38–40 of
account-lead labour the ratio is ~16:1; the deck should quote the **ratio**, not §10's unmeasured
absolute.

## 6. Model versions — all observed this run

| Role | Alias | Resolved |
|---|---|---|
| `classify` · `fidelity-check` · `extract` | `haiku` | `claude-haiku-4-5-20251001` |
| `synthesize` · `render` | `sonnet` | `claude-sonnet-5` |
| Orchestrator | `opus[1m]` | `claude-opus-4-8[1m]` |

## 7. Deferred / notes

- **Second confirmatory run not spent** (§4). The fix is structural, but a single graded run is
  one data point; a re-run is cheap insurance if you want it before the defense.
- **Tier 4 (stretch)** is unstarted and gated on Tiers 0–3 being green before Saturday noon
  (TIERS.md). It needs a human to set `signoff.status = "signed_off"` in a fixture draft — the
  agent never signs off — then the creative-shadow A/B. `creative-shadow` already refuses
  unsigned input and refuses to invent a missing spec-table row.
- **`answer_key.json` remained sealed** to the pipeline throughout (`gates.HARNESS_ONLY_FILES`);
  only the harness read it. No prompt was tuned against its specifics.

---

**Tier 3 DoD: 8/8 green (17/17 harness checks). Tiers 0–3 complete. Stopping for human review.
Tier 4 not started.**

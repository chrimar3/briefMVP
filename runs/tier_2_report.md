# Tier 2 — Full Stage 1 · **GREEN**

**Date:** 2026-07-24 · **Branch:** `main` · **Graded run:** `runs/20260724-021459`
**Preceding commit:** `9e371f6`

All seven Stage-1 steps now run. The pipeline takes a folder of four source documents and
produces a schema-valid canonical brief plus Greek and English renders, with three conflicts
surfaced and fourteen open questions raised — none of them resolved by the machine.

---

## 1. DoD results

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Removing the RFP makes the readiness gate refuse with "insufficient input" | ✅ | `test_run_refuses_when_the_rfp_is_removed` (green since Tier 0) |
| 2 | Draft validates against `brief_schema.json`; `sensitivity_tier` ∈ {S0,S1} | ✅ | harness `T2.1`, `T2.2` — tier S1 |
| 3 | Both renders exist; every rendered claim maps to a schema entry | ✅ | `T2.3`, `T2.4` — all claim lines cited |
| 4 | Glossary terms character-exact in both renders | ✅ | `T2.5` |
| 5 | `readiness` present; harness recomputes it and values match | ✅ | `T2.6` — 6/7 fields, 0.037 low share, `ready_for_review` |
| 6 | Commit | ✅ | this commit |

```
python3 pipeline/runner.py --project fixtures/northlight_01     → 7 steps, complete
python3 eval/harness.py runs/20260724-021459                    → 17 passed · 0 failed · PASS
python3 -m pytest -q                                            → 165 passed, 6 skipped · exit 0
```

## 2. What the pipeline produced

```
[1] readiness_gate  4 sources, 3 substantive                         deterministic
[2] classification  advertising_creative · high · tier S1            haiku
[3] fidelity_check  2 tokens flagged · score high · pass_with_flags  haiku
[4] extraction      4 extracts · 36 items · all citations resolve    haiku ×4
[5] conflict_pass   6 candidate fields · 1 internal conflict         deterministic
[6] synthesis       27 entries · 3 conflicts · 14 open questions     sonnet
[7] render          el 14,993 chars · en 13,518 chars                sonnet
```

**The three conflicts are the three that were seeded** — `audiences`, `timeline`, `budget` —
each carrying citations to both sources, each `status: "open"`. The audiences field has **zero
canonical entries** and renders as an empty section pointing at the conflict: the RFP says Gen Z
18–24, the CMO said 25–40, and the system declined to pick. That is DR-10 working, and it is the
single most defensible thing in this run.

`signoff.status` is `draft`. The agent never signed off.

## 3. Three defects found this tier — two of them mine

Reported in order of how much they say about the design.

**D2-1 — The bilingual system had an anglocentric validator.**
The render gate checked "does this document contain a `?`" to confirm open questions rendered.
The Greek document has **zero** `?` characters, because Greek marks a question with `;`. A
perfectly good render was rejected by a gate that assumed English punctuation. Fixed by keying on
the `⚠` section marker the template already gives both special sections — a signal that survives
translation, which is what a bilingual gate needs. Worth stating plainly on the deck: this is the
category of bug that bilingual systems produce, and it was caught by running the thing rather
than by reasoning about it.

**D2-2 — The fidelity gate rejected a correct artifact, twice.**
The agent annotated the transcript properly and repaired nothing. But stripping `[FIDELITY: …]`
from `"ογδόντα πέντε [FIDELITY: …], αλλά"` left `"πέντε , αλλά"` — a space before the comma — and
the byte-equality check failed. The separator whitespace is *part of* the insertion; the regex
did not model that. The criterion ("no character of the transcript was altered") was right and is
unchanged; only its implementation was wrong. Distinguishing those two things is the difference
between fixing a gate and relaxing one.

**D2-3 — The resume feature silently truncated the audit trail.**
Re-running one leg against an existing run directory rewrote `run_manifest.json` with only that
leg, leaving a manifest reading `outcome: complete` over a single step. An artifact that reads as
a complete run and is not — the exact failure class this project exists to prevent, produced by
my own convenience feature. Fixed: prior steps are carried forward and marked
`from_earlier_run: true`. A second defect surfaced alongside it — resuming `--stage render` with
no `brief.json` raised a bare `KeyError: 'brief'` — now a legible refusal naming the missing file.

**Known consequence, not repaired:** run `20260724-021459`'s manifest lost steps 1–6 before the
fix landed. The step-by-step figures in §2 and §5 come from the run log, not the manifest.
Reconstructing the manifest by hand would have meant fabricating an audit record, so it stands as
it is, and the fix prevents recurrence.

## 4. Design decisions taken this tier

**D2-4 — Conflict candidates are high-recall and opinion-free.** The deterministic pass emits a
candidate for every field where two or more sources spoke — including fields where they *agree*
(6 candidates from 4 sources). Deciding whether "Gen Z 18–24" and "25–40 urban professionals"
contradict each other is judgment; deciding which field/source pairs deserve a look is grouping.
The split follows PRD §5's "deterministic + LLM assist" exactly.

**D2-5 — Empty sections render as blockquotes.** A section with no entries still renders, with a
one-line blockquote note (`> No confirmed entries — see Open Questions.`). This keeps the
information visible while marking it as structure rather than an uncited claim, satisfying the
frozen harness's `T2.4` without loosening it. Published in `TRANSLATION.md` rule 8.

**D2-6 — A halt is not a failure.** `HaltForHuman` is a distinct exit code (5) from a gate error
(4). Low classification confidence and an `escalate_to_human` fidelity verdict stop the run, and
the manifest records them as `halted_for_human` — the system asking rather than guessing (DR-9,
DR-12) should not read as a crash in the operator's log.

**D2-7 — Extraction reads the annotated transcript; citations are verified against the original.**
The `[FIDELITY: …]` markers are a reading aid, not evidence. Anchors are checked against the
unannotated source, so an anchor quoting an annotation is caught as a fabricated citation.

## 5. Usage & cost

| Step | Model | Attempts | Cost |
|---|---|---|---|
| classification | `claude-haiku-4-5-20251001` | 1 | $0.0412 |
| fidelity check | `claude-haiku-4-5-20251001` | 1 | $0.0493 |
| extraction ×4 | `claude-haiku-4-5-20251001` | 2 each | $0.8088 |
| synthesis | `claude-sonnet-5` | 1 | $1.2060 |
| render (accepted) | `claude-sonnet-5` | 1 | $1.4112 |
| **Full brief, accepted path** | | | **$3.52** |

Plus $1.94 on the two rejected runs (a fidelity gate that was wrong, a render that failed the
citation rule), for **$5.46 across the tier**.

**PRD §10 budgets under €0.50 per brief. The observed cost is roughly seven times that**, and the
extraction line alone ($0.81 for four sources) is 11× the §10 estimate of $0.07. Three causes,
worth separating because only one is a modelling error:

1. **Agentic overhead.** §10 models one metered API call per stage. Each stage here is a Claude
   Code subagent that reads files across ~5 turns and pays cache-creation each time.
2. **The repair loop.** Every extraction took 2 attempts — the deterministic gates rejected the
   first artifact each time. That is the gates working, and it doubles extraction cost.
3. **Sonnet on long context.** Synthesis and render are $2.62 of the $3.52.

**Recommendation for the deck: quote the ratio, not the absolute.** Against ~€38–40 of
account-lead labour per brief, $3.52 is still ~11:1, and the production substrate (DR-1,
enterprise API, prompt caching on the static skeleton) removes most of cause 1. But §10's
"<€0.50" should not be presented as measured — it was not, and this run is the first evidence
either way.

## 6. Model versions — all observed

| Role | Alias | Resolved | Basis |
|---|---|---|---|
| `classify` · `fidelity-check` · `extract` | `haiku` | `claude-haiku-4-5-20251001` | observed, `modelUsage` |
| `synthesize` · `render` | `sonnet` | `claude-sonnet-5` | observed, `modelUsage` |
| `creative-shadow` | `sonnet` | — | unobserved (Tier 4) |
| Orchestrator | `opus[1m]` | `claude-opus-4-8[1m]` | session harness |

Every Stage-1 alias is now confirmed against a real invocation rather than a registry table.

## 7. ⚠ Flagged: the Tier-3 checks already pass

The harness runs all 17 checks on every graded run, and **all of them passed on this run**,
including the Tier-3 quality gates: 3/3 seeded conflicts with both citations, 3/4 seeded gaps
(minimum 3), 2/2 garbled terms carried through unfixed, zero uncited values, and traps X1/X2/X3
green. `runs/20260724-021459/harness_report.json` records it.

Declaring this rather than banking it: **Tier 3 has not been started or claimed.** Tier 3 is its
own tier — its DoD wants the harness run as the deliberate act, a `tier_3_report.md`, and a
human's review of whether these results hold on a re-run. A single passing run is evidence, not a
tier. Note also that G3 (the undecided final approver) is the seeded gap **not** found, so the
margin on the gaps check is exactly zero: 3 required, 3 found.

## 8. Deferred

- **Repair loop runs on every extraction.** 2/2 attempts on all four sources. Worth a look at
  *which* violations recur before Tier 4 — if it is always the same rule, the skeleton can teach
  it once instead of paying for a retry every time.
- **Substrate contamination** (carried from Tier 1): subagents run with cwd = repo root, so
  `CLAUDE.md` build governance loads into runtime agent context. Fix via `--agents` inline JSON.
- **`MAX_ATTEMPTS = 2` is now well exercised** for extraction, and was hit-and-failed twice by the
  fidelity and render gates before their bugs were fixed. The budget looks right.
- **No open-questions count check in the frozen harness.** `T2.4` checks citations, not whether
  all 14 open questions reached both renders. The runner gate checks the section exists; the
  count is unverified.

---

**Tier 2 DoD: 6/6 green. Stopping for human review. Tier 3 not started.**

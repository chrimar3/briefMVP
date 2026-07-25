# Cost-audit tier C1 — output-shape fixes · **QUALITY GREEN · COST TARGET MISSED**

**Date:** 2026-07-25 · **Runs:** `cost-c1` (attempt 1, full), `cost-c1b` (attempts 2–3, synthesis/render legs) · **Preceding:** C0 (`b502f05`)

The tier that teaches by measurement. Output-discipline instructions landed in the three
token-heavy stages; the quality gate ended **17/17**; extraction got measurably cheaper; the
sonnet stages did not move — and the *reason* they did not move is this tier's most valuable
finding. The −30% working target was not met, and per the standing rule the gate is never
traded for the number: this report states the miss.

---

## 1. What changed

- **Shared `EFFICIENCY` block** (`agents.OUTPUT_DISCIPLINE`) appended to the extraction,
  synthesis and render work orders: read inputs in one message (parallel Reads), compose
  artifacts inside the Write call, never echo artifact content in the reply, self-check
  silently. Enforced by `tests/test_orders.py`.
- **Silent-self-check preambles** in `SOURCES.md` §8, `SYNTHESIS.md` §3, `TRANSLATION.md` §4
  (+ byte-exact re-sync of the three agent files, `tests/test_agents.py` green).
- **Taught rule** (from attempt 1's failure): `SYNTHESIS.md` rule 5 — *questions ask, they
  never resolve*; a currency mark attaches to a figure only where a source wrote it.
- **Latent timeout fixed** (from attempt 2's failure): `DEFAULT_TIMEOUT_S` 600 → 1200.
  Historic renders ran 291–577s against the 600s ceiling — two prior runs survived by <5%.

## 2. The three attempts — each failure produced a durable fix

| Attempt | Outcome | What it taught |
|---|---|---|
| 1 — full run (`cost-c1`) | **16/17** — trap X3: an open question asserted "€80–85k … per the kickoff", resolving a currency the CFO never stated | The frozen harness caught a real discipline slip on a fresh run. Fixed by teaching the rule (SYNTHESIS.md rule 5), not by retrying |
| 2 — synthesis leg (`cost-c1b`) | Synthesis passed, **no €80 in the new brief** (fix held); render **timed out at 600s** | The timeout was a pre-existing coin flip, unrelated to C1; ceiling raised to 2× observed max |
| 3 — render leg (`cost-c1b`) | **17/17 · PASS** | DoD quality bar met |

## 3. Measured result (correct baselines: the two clean confirm runs)

An earlier in-session comparison used the tier3 manifest's render step as baseline — that step
is the **Tier-4 signed-brief re-render** ($1.27), not Stage-1. Corrected here.

| Stage | Baseline mean (confirm runs) | C1 measured | Verdict |
|---|---|---|---|
| extraction ×4 | $0.481 · 60,741 out-tok | **$0.381 · 45,627 out-tok** | **−21% cost, −25% output — the robust win** (same 4 sources, comparable extracts) |
| synthesis | $0.891 · 33.8k out-tok | $0.840/30.2k, then $1.424/52.7k | Unmoved — variance dominates |
| render | $0.806 · 32.6k out-tok | $1.011/41.6k, then $1.321/52.3k | Unmoved-to-higher — variance + larger briefs (14/12 open questions vs 10/8) |
| classification + fidelity | $0.077 | $0.077 | Flat (already minimal) |

**Per-brief total: ~$2.2–2.3 vs $2.25 baseline — unchanged within run variance. Target ≤$1.60
not met.**

## 4. The finding that redirects the effort

Prompt discipline moved the stage whose output was *echo* (extraction: haiku, no thinking,
narrated self-checks — gone, −25%). It did not move the stages whose output is *thinking*
(sonnet synthesis/render: 30–53k output tokens against ~7k-token artifacts, varying ~1.7×
between runs on near-identical inputs). **The sonnet-stage spend is thinking-dominated and
sits below the prompt surface** — reachable only by the effort knob (C2, the CLI's native
`--effort` flag) and the substrate change (C4). C1 sharpens both hypotheses rather than
competing with them.

Secondary observation for C2's design: sonnet-stage output volume varies ~±60% run-to-run at
default effort. Single-run A/Bs on those stages must compare against the *range*, not a
single baseline number.

## 5. Verification & spend

```
python -m pytest                    → 265 passed, 6 skipped
python eval/harness.py runs/cost-c1b → 17 passed · PASS   (the shipped configuration)
runs/cost-c1 (attempt 1)             → 16/17 — X3, documented above; superseded by cost-c1b
```

Tier spend: ~$5.9 (full run $2.31 · synthesis leg $1.42 · timed-out render ≲$1 unrecorded by
the killed process · final render $1.32). Repair rounds across all gated attempts: **zero** —
every failure was caught at the harness or infrastructure layer, not the gates.

## 6. Model versions — observed this tier

| Role | Alias | Resolved |
|---|---|---|
| classify · fidelity-check · extract | `haiku` | `claude-haiku-4-5-20251001` |
| synthesize · render | `sonnet` | `claude-sonnet-5` |
| Orchestrator (audit session) | — | `claude-fable-5` |

---

**C1 DoD: quality 17/17 green · pytest green · costs measured and reported with the target
miss stated. Extraction −21% banked; the sonnet-stage burden passes to C2/C4 with a sharper
hypothesis. Proceeding to C2 per the approved sequence.**

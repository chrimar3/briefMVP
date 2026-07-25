# Cost-audit tier C2 — per-stage effort policy · **GREEN, ADOPTED**

**Date:** 2026-07-25 · **Run:** `cost-c2` (render leg on the identical `cost-c1b` brief) · **Preceding:** C1 (`1f1710f`)

C1 ended with a sharp hypothesis: sonnet-stage spend is thinking below the prompt surface,
reachable only by the effort knob. C2 built the knob, ran the cleanest A/B available, and the
result is unambiguous.

---

## 1. The mechanism

- `config/model_routing.json` — per-stage `effort` policy (`low…max`), read by
  `agents.stage_effort` and passed to the CLI as `--effort` for configured stages only.
  Policy-in-config per the readiness-policy precedent; malformed policy fails loudly.
- **Model-tier routing is untouched** — haiku/sonnet assignments stay in the agent
  frontmatter as a human decision (CLAUDE.md). This file tunes only how hard a chosen
  model thinks.
- **Synthesis carries no cap, by design and by test** (`test_shipping_routing_policy_is_valid`
  asserts it): conflict adjudication is the judgment core; capping it is a human decision
  this tier does not presume.

## 2. The A/B — same brief, same template, same gates; only effort moves

| Render of the identical 28-entry brief | default effort (`cost-c1b`) | `effort: low` (`cost-c2`) |
|---|---|---|
| Cost | $1.321 | **$0.676 (−49%)** |
| Output tokens | 52,299 | **19,560 (−63%)** |
| Duration | >600s (needed the C1 timeout fix) | **205s (−66%)** |
| Harness | 17/17 | **17/17** |
| Rendered documents | — | **BYTE-IDENTICAL to the default-effort renders** |

The last row is the finding: default-effort thinking on the render stage bought *nothing* —
not a different word in either language. The stage is so constrained by its inputs (canonical
brief + template + deterministic citation/glossary/⚠ gates) that inference depth is pure
overhead. Against the full default-effort history (4 renders: $0.65–1.32, 26k–52.3k output
tokens), the low-effort render's token count sits **below the entire observed range**.

## 3. Adopted policy and per-brief impact

`render: low` ships (it is the committed config). Measured Stage-1 estimate moves from
~$2.25 to **~$2.0/brief** (extraction −21% from C1, render ~−30–50% vs the default-effort
range). Synthesis ($0.84–1.42, thinking-dominated) is now the largest single line —
deliberately untouched here; capping it is flagged as an open **human decision**, best
revisited after C4 shows what the substrate change alone recovers.

## 4. Verification & spend

```
python -m pytest                    → 269 passed, 6 skipped
python eval/harness.py runs/cost-c2 → 17 passed · PASS
diff cost-c1b vs cost-c2 renders    → brief_el.md, brief_en.md byte-identical
```

Tier spend: $0.68 (one render leg). Repairs: zero.

## 5. Model versions — observed this tier

| Role | Alias | Resolved |
|---|---|---|
| render (A/B, both arms) | `sonnet` | `claude-sonnet-5` |
| Orchestrator (audit session) | — | `claude-fable-5` |

---

**C2 DoD: knob built, tested, measured on an identical-input A/B, adopted with 17/17 and
byte-identical output at −49% cost. Proceeding to C3 per the approved sequence.**

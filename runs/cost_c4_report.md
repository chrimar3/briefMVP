# Cost-audit tier C4 — production-substrate spike · **MEASURED (CLI ARM) · API ARM CREDENTIAL-BLOCKED**

**Date:** 2026-07-25 · **Run:** `runs/cost-c4` (spike artifacts + meter JSON) · **Preceding:** C3 (`12526da`)

The tier that was supposed to demonstrate the cheap substrate instead *measured why the demo
substrate is expensive* — a negative result that redirects the remaining savings precisely.

---

## 1. What was built

- `eval/substrate_spike.py` — the extraction stage in PRD DR-1's production shape: one call
  per source, zero tools, static skeleton (agent body + schema + glossary) as a cacheable
  prefix, source inlined, the JSON extract as the reply, **graded by the pipeline's own
  `check_extract` gate** (the gate does not care how an artifact was produced).
- Two transports: `cli` (single-turn subagent — same billing substrate as the pipeline;
  isolates the turn structure) and `api` (metered `anthropic` SDK call — the true
  production measurement).
- **CLAUDE.md rule 4 amended, narrowly**: the api transport is the ONE sanctioned
  non-subagent model path, explicit invocation + explicit credentials only.

## 2. Measured — the CLI arm ($0.37)

| Source | Cost | Turns | Gate |
|---|---|---|---|
| background_brand_guidelines | $0.075 | 1 | clean |
| emails_thread | $0.115 | 1 | clean |
| rfp_meltemi | $0.082 | 1 | clean |
| transcript_kickoff | $0.100 | 1 | **3 violations — the seeded-garbling trap** |
| **Total** | **$0.371** | | 3/4 clean |

**Finding 1 — the turn-structure hypothesis is dead on this substrate.** Single-turn $0.371
vs the pipeline's multi-turn $0.381 (C1): flat. What the demo substrate charges for is the
fixed per-invocation CLI harness overhead, not the 5–7 tool-use turns. C0's "cache writes ≈
30%" share is largely *per-invocation*, not per-turn.

**Finding 2 — the gated repair loop earns its keep on the hard source.** Single-shot haiku
silently repaired the garbled transcript terms («μπραντ αγουέρνες» → "brand awareness") —
exactly the violation class `find_unsourced_glossary_terms` exists to catch, and exactly what
the pipeline's repair round fixes for ~$0.10 more. Any production single-call deployment
keeps the same gate + one repair call; the architecture's core claim (deterministic gates
over model self-discipline) is re-confirmed from a new angle.

## 3. Blocked — the API arm, and its grounded projection

No `anthropic` SDK, no `ANTHROPIC_API_KEY`, no `ant` profile in this environment — a metered
call cannot run, and a credential is input only the account lead can provide. The transport
is implemented and one command away:

```
pip install anthropic && ANTHROPIC_API_KEY=... python eval/substrate_spike.py --transport api
```

Token-grounded projection from the measured prompt sizes (static prefix ~5.6k tokens cached
across calls; per-source input 1–3k; output ~2k, haiku list rates): **~$0.06 for all four
extractions (~6× vs today)**. Extrapolated across stages this is the path to PRD §10's
"<€0.50/brief" — but it stays labeled a projection in `docs/COST_MODEL.md` §6 until a key
runs it. Nothing in this tier presents it as measured.

## 4. Where the cost programme lands (C0–C4)

| Lever | Status | Per-brief effect |
|---|---|---|
| C0 telemetry | shipped | the ruler (`cost_report --tokens`) |
| C1 output discipline | shipped | extraction −21%; taught rule + timeout fix |
| C2 render @ low effort | shipped, adopted | render −49%, byte-identical output |
| C3 render on haiku | evidence pack, **decision open** | further −$0.35 vs visible register loss |
| C4 API substrate | built, **credential-blocked** | projected ~6× on haiku stages |

Measured Stage-1 today: **~$2.0/brief** (from $2.25), quality 17/17 throughout, zero gate
relaxations. Largest remaining line: synthesis ($0.84–1.42, thinking-dominated, deliberately
uncapped — capping it is a human decision).

## 5. Verification & spend

```
python -m pytest                 → 273 passed, 6 skipped
runs/cost-c4/substrate_spike_cli.json → the per-source meter record
```

Tier spend: $0.37. Observed models: `claude-haiku-4-5-20251001` (spike); orchestrator
`claude-fable-5`.

---

**C4 DoD: substrate shape built and gate-graded; CLI arm measured (flat — the honest negative
result); API arm sanctioned, implemented, and blocked on a credential only the account lead
can provide. Cost programme C0–C4 complete pending the two open human decisions (C3 render
model; API key for the C4 measurement).**

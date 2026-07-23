# Tier 1 — Single-source extraction (transcript) · **GREEN**

**Date:** 2026-07-24 · **Branch:** `main` · **Pipeline version:** `0.1.0-tier0`
**Graded run:** `runs/20260724-013512` · **Preceding commit:** `94edf44`

The first tier where a model actually runs. It found a real defect on the first attempt, which
is the outcome this tier is designed to produce.

---

## 1. DoD results

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Extract validates against `extract_schema.json` | ✅ | harness `T1.1` — 1 extract valid |
| 2 | Zero items with empty `location` or `anchor` | ✅ | harness `T1.2` — 12 items, all cited |
| 3 | Both seeded garbled terms present **as-is** with glossary-match proposals, NOT corrected | ✅ | harness `T1.4` — 2/2 flagged, none fixed |
| 4 | `pytest -q` green · commit | ✅ | **137 passed, 6 skipped**, exit 0 |

```
python3 pipeline/runner.py --project fixtures/northlight_01 --stage extraction --source transcript_kickoff
python3 eval/harness.py runs/latest --tier 1     → 4 passed · 0 failed · PASS (exit 0)
python3 -m pytest -q                             → 137 passed, 6 skipped · exit 0
```

A fourth check, `T1.3` (every `location`/`anchor` occurs verbatim in its source), was added
beyond the letter of the DoD. It is the check that caught the tier's real defect.

## 2. What happened on the first run — the finding

Attempt 1 produced a **schema-perfect extract that was wrong in the exact way PRD §9 R2 says
matters most.** The harness, pointed at that artifact, reports:

```
✅ T1.1  Every extract validates against extract_schema.json      1 extract(s) valid
✅ T1.2  Zero items with empty location or anchor                 13 item(s), all cited
❌ T1.3  objectives[0]: location '[00:07]' does not occur in the source
❌ T1.4  T1: corrupted token 'μπραντ αγουέρνες' absent — silently corrected to 'brand awareness'
         T2: 'κι βίζουαλ' survives but no extraction_note proposes the match — silent consumption
```

Three failures, and they were **correlated**: the one item the model silently "repaired" is the
same item whose citation it invented. Having decided what the speaker meant, it needed a
timestamp to hang that on, and produced one that does not exist in the transcript.

The important part is the first two lines. **Schema validation passed on the bad artifact**, as
did the citation-presence check. Every field was populated, every item carried a `location` and
an `anchor` — a reviewer skimming it would have seen a well-formed, fully-cited extract. This is
precisely R2's "confident citation to garbage": the output looks *more* trustworthy than an
honest one, because it has been tidied. Locked in as a regression test
(`test_schema_check_alone_would_have_passed_the_bad_artifact`).

## 3. The fix — in code, not in the prompt

Asking a model more firmly not to repair tokens is unfalsifiable. Two deterministic detectors
were added to `pipeline/gates.py` instead, both driven by artifacts the agency already owns:

**`verify_citations(extract, source_text)`** — every `location` and `anchor` must occur verbatim
in the source (whitespace-normalised, so a line wrap is not treated as fabrication). SOURCES.md
rule 2 says a value without a citation does not exist; this is the other half — a citation that
cannot be resolved is worse than a missing one, because it survives review by looking verified.

**`find_unsourced_glossary_terms(extract, source_text, glossary)`** — glossary terms are
`keep_latin`, so a glossary term standing in Latin script inside an extracted `value` while the
source never writes it in Latin means the *model* produced it: either by repairing a
script-collapsed token (rule G) or by translating (rule 5). Both are forbidden and both are
invisible to a schema check. The detector knows nothing about any particular document — it reads
`glossary/*.json`, which the account leads own.

Supporting changes, all general rather than fixture-specific:

- `SOURCES.md` §8 gained self-check items 7 (glossary scan) and 8 (locations are copied, never
  constructed); `.claude/agents/extract.md` re-synced, byte-equality test green.
- The work order now states the **fidelity-gate precondition**. SOURCES.md §2 assumes transcripts
  arrive annotated by step 3, which did not run in this tier; the agent is told so explicitly, so
  rule G carries its full weight rather than the agent assuming a gate already cleaned the input.
- Violations feed a single repair round (`MAX_ATTEMPTS = 2`) with all failures at once, so a
  repair sees the whole picture instead of burning attempts one violation at a time.

**No prompt was tuned against `answer_key.json`.** Both detectors are general rules over the
client glossary and the source text. The answer key was read only by the harness, which is what
it is for.

Attempt 2 passed on the first try, with no repair round needed.

## 4. The frozen harness

`eval/harness.py` is **frozen** as of this commit (CLAUDE.md rule 2).

```
sha256  05279356057875021739c64d95dac1117c47a1992237cc38e77c23ae4dffbc8e
lines   662
```

It covers **17 checks across Tiers 1–3** — including the Tier-2 and Tier-3 checks for artifacts
that do not exist yet. That inverts the usual order: the harness is not a description of what the
pipeline produced, it is the contract Tiers 2 and 3 must satisfy. Two consequences were handled
deliberately:

- **A published target, not a hidden one.** `T2.4` (no orphan prose) needs a citation-tag
  convention in the renders. Rather than freeze a secret rule, the convention was written into
  `TRANSLATION.md` rule 8 and the template: every claim line in sections 1–7 carries at least one
  `[<source_id> <location>]` tag using the `source_id` from `meta.sources`.
- **The Tier-2/3 checks are tested now.** A broken Tier-3 check would silently mark a failing run
  green and could not be repaired later, so `tests/test_harness.py` exercises all of them against
  synthetic artifacts — including both X1 outcomes, both X2 outcomes, and X3's subtlety that a
  verbatim figure *inside a conflict position* is legitimate while the same string elsewhere is an
  invented total.

The harness is also the only component that reads the answer key; the pipeline cannot reach it by
construction (`gates.HARNESS_ONLY_FILES`).

## 5. Usage & cost — first real numbers

| Run | Attempts | Model | Output tok | Cache read / create | Cost | Wall |
|---|---|---|---|---|---|---|
| `20260724-012939` (rejected) | 1 | `claude-haiku-4-5-20251001` | 8,245 | 20,945 / 20,158 | $0.0837 | 86 s |
| `20260724-013512` (accepted) | 1 | `claude-haiku-4-5-20251001` | 22,425 | 21,583 / 34,503 | $0.1833 | 241 s |

**Tier total: $0.267 for one source.**

This deserves flagging rather than burying. PRD §10 budgets **~$0.07 for extraction across all
four sources**; one transcript cost **$0.18**. The gap is substrate, not arithmetic: §10 models a
single metered API call per source, while the demo runs each stage as a Claude Code subagent that
reads files over 5 agentic turns and pays cache-creation on each. The production path (DR-1,
enterprise API) has no such overhead, but the deck should not quote §10 as though it had been
observed. **Recommendation: re-derive §10's extraction line from Tier-2 numbers across all four
sources before the deck quotes a per-brief figure.**

## 6. Model versions

| Role | Alias | Resolved — **observed this tier** |
|---|---|---|
| `extract` | `haiku` | **`claude-haiku-4-5-20251001`** (from `--output-format json`, `modelUsage`) |
| Orchestrator | `opus[1m]` | `claude-opus-4-8[1m]` |
| `classify` · `fidelity-check` | `haiku` | registry mapping — still unobserved (stages not built) |
| `synthesize` · `render` · `creative-shadow` | `sonnet` | registry mapping — still unobserved |

Tier 0's deferred item is closed for `extract`: the alias resolves as predicted, and resolution is
now captured per run in `run_manifest.json` rather than asserted from a table.

## 7. Deferred / flagged

- **Substrate contamination (known, accepted).** The subagent runs with cwd = repo root so
  Claude Code can discover `.claude/agents/`, which means the repo's `CLAUDE.md` build governance
  loads into a runtime agent's context — something SOURCES.md explicitly says never ships to client
  runtime. Harmless here; wrong in principle. Fix if it matters: pass the agent definition via
  `--agents` inline JSON and run from a neutral cwd.
- **Quality observation, not a DoD failure.** The accepted extract records the objective at
  `[00:02:05]` as *"Θέλουμε να μπούμε δυνατά"* and leaves the `μπραντ αγουέρνες` phrase to an
  `extraction_note`. Honest, but the primary objective now reads thinner than the source supports.
  Worth watching in Tier 2 — if synthesis produces a weak objectives section, this is why.
- **Fidelity gate (step 3) still unbuilt.** Transcripts currently reach extraction unannotated.
  Rule G held under the strengthened self-check plus the new detectors, but the designed pipeline
  puts the gate first, and it belongs in the next tier's scope.
- **`MAX_ATTEMPTS = 2` was never exercised** — attempt 2 passed first time, so the repair loop is
  implemented but unproven against a real failure.
- **`--stage full` still stops at classification (step 2).** Unchanged from Tier 0, by design.

---

**Tier 1 DoD: 4/4 green. Harness frozen. Stopping for human review. Tier 2 not started.**

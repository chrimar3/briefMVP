# System-design audit — the deterministic core · **COMPLETE**

**Date:** 2026-07-25 · **Branch:** `main` · **Kickoff:** `docs/AUDIT_BRIEF.md` · **Protocol:** findings-first (§5), all finding classes human-approved before any edit.

Governing principle applied: §3 — *fewer concepts, each doing more work* — inside the brief's hard
boundaries. No frozen file was touched, no harness-shared function was modified, no acceptance
criterion moved, and every fix landed with a regression test reproducing the failure first.

---

## 1. Verdict

| Gate | Result |
|---|---|
| `python -m pytest` | **256 passed, 6 skipped** (was 224+6 at baseline; +32 regression/convention tests, 0 weakened) |
| `python eval/harness.py runs/tier3` | **17/17 · PASS** — the committed evidence grades identically |
| Prompt surface (6 work orders × 3 variants + 6 repair orders, frozen timestamps) | **14 artifacts diffed pre/post refactor: 0 diffs** — byte-identical |
| Strengthened gates vs. committed tier3 artifacts | **0 false positives** (renders, both creative drafts, all 4 extracts, synthesis audit-added rules — all clean) |

The five harness-shared functions (`verify_citations`, `compute_readiness_block`,
`validate_extract`, `validate_brief`, `find_uncited_items`) are byte-untouched; `eval/harness.py`
was read, never edited. `skills/*.md` were not edited, so no agent re-sync was required.

## 2. Findings and dispositions

Ranked as presented and approved. "FP" = false positive (a gate rejecting valid model output —
the §3b.1 pattern; this audit found the **fifth and sixth** members of that family).

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | HIGH | `creative.py` ratio regex flags m:ss durations without leading zeros (`1:30`, `1:15`) as invented aspect ratios — the 5th gate FP, one iteration past the tier-4 timecode fix; the repair loop then strips *valid* durations | **Fixed.** Tokens are cleared against the spec table first; an unmatched colon token whose right side reads as seconds (two digits, 10–59) is tolerated as a duration. All common invented ratios (16:9, 4:3, 3:2, 21:9) still fail — `test_common_invented_aspect_ratios_are_still_caught_after_the_duration_fix`. **Documented residual false-negative window:** an invented ratio with a 10–59 denominator not in the table now passes; also `n:1` prose ratios (e.g. "3:1 ROAS") are still flagged — a narrower residual FP accepted over widening the invented-ratio hole. |
| F2 | HIGH | Fabricated citations in `internal_conflicts` verified nowhere, while their anchors are deliberately admitted into synthesis's known-anchor set (tier-3 §7) — a citation-to-garbage path into the brief (PRD R2) | **Fixed** with a **new** runner-side gate `gates.verify_internal_conflict_citations`, wired into `extraction.check_extract`; `find_unsourced_glossary_terms` widened to internal-conflict items via the new `gates._extract_items`. The shared `verify_citations` is untouched — the runner is now stricter than the grader, the permitted direction. |
| F2b | HIGH | Anchors in brief `conflicts[].positions[].evidence` and `open_questions[].linked_evidence` never integrity-checked (tier3 carries 8+18 such refs) | **Fixed.** `check_synthesis`'s known-anchor sweep now covers all three ref-bearing structures. |
| F3 | MED | Synthesis schema violations invisible to the repair loop (validation ran post-loop) → zero repair rounds AND a repair log whose last attempt read "clean" | **Fixed.** `check_synthesis` validates a probe copy carrying the runner-computed readiness block; post-loop injection + validation unchanged. |
| F4 | MED | Render gate: conflicts-only brief required no ⚠ section at all; counts never verified (tier-2 §8 seed) | **Fixed.** ⚠ section required when *either* list is non-empty; numbered-item count in the ⚠ region must cover every open question (template contract: numbered; translation-invariant); each conflict position's `source_id` must appear in the ⚠ region (survives translation character-exact). Both checks ≥-shaped — a render may elaborate, not omit. Verified zero-FP against both tier3 renders. |
| F5 | MED | Creative stage invisible to the durable repair log and to `repair_analysis.py` in both code paths; no signatures for spec-gate messages — the tier-4 FP never appeared in the tool built to catch recurrences | **Fixed** structurally by F7 (creative now logs via the shared loop, site = model alias) plus 4 new signatures (`spec-not-in-table`, `creative-missing-banner`, `render-question-dropped`, `render-conflict-dropped`) and a manifest fallback that reads every step shape the runner actually writes (`fidelity[]`, `creative[]`, named single-outcome keys). |
| F6 | LOW | (a) budget signals lacked spelled-out `ευρώ` → readiness FP on a valid Greek-only folder; (b) fidelity annotation strip broke on a `]` inside the annotation; (c) glossary detector could fire on short terms inside unrelated words (`OOH` in "boohoo") | **Fixed**: (a) one pattern added; (b) regex tolerates one level of nested brackets; (c) word-bounded on the value side, substring kept on the source side (only shrinks the violation set — no new FP possible). |
| F7 | MED | The invoke-gate-repair loop existed three times (`stages._run_with_repair`, inline in `extraction.extract_source`, inline in `creative.creative_shadow`), plus a triple `MAX_ATTEMPTS` re-export | **Fixed.** One mechanism, `agents.run_gated`, at the invocation seam — extraction, all four stages and creative run through it, so the attempt budget, attempt-record shape and durable diagnostics cannot diverge. Improvement in passing: fidelity's repair-log `site` is now the transcript's `source_id` (was the agent name). Refusal semantics untouched: every stage raises its own error type with its exact prior message. |
| F8 | LOW-MED | Six work-order builders restate one skeleton | **Fixed with a deliberate deviation from the sketched approach, flagged here per protocol.** The repair-order format *is* now genuinely shared (`agents.repair_order`, byte-identical for 5 of 6 stages; extraction's structurally different one kept). For the work orders themselves, byte-identical assembly through a composer proved degenerate: the orders differ in their read-scope sentences, OUTPUT headings and even the header suffix, so a shared assembler would either change validated prompt bytes or reduce to an f-string doing no work. The §3 goal — *a convention enforced once* — is met instead by `tests/test_orders.py`: one parametrized test asserting every order carries the skeleton (header naming stage+step · INPUT · answer-key prohibition · pinned output path · one-line reply contract), touching zero prompt bytes. |
| F9 | TRIV | `_extraction_handler` re-implemented `_summarise` inline | **Fixed**; `_creative_handler` joined the same convention (its cost line now sums all attempts rather than showing the last attempt's cost — strictly more truthful). |
| F10 | LOW | `collect_internal_conflicts` spread order let a conflict's own `source_id` silently override pipeline provenance | **Fixed** (`{**conflict, "source_id": source_id}`) — defensive only; the extract schema forbids the key today. |
| F11 | LOW | `_parse_frontmatter` regex duplicated between `pipeline/agents.py` and `tests/conftest.py` | **Fixed as recommended**: the regex constant is now imported from the runtime; the YAML *parse* in conftest stays independent on purpose (it verifies the frontmatter is real YAML, which the runtime's naive parser never checks). |
| F12 | note | `_hydrate` doesn't restore fidelity-annotated transcripts on a resumed extraction leg · `SubagentResult.ok` recorded but never consulted · `repair_analysis` "more than" signature shadowed by "never repairs" · unreachable `pending_stage` path | **Left as-is by agreement** — recorded here so the next session doesn't re-derive them. The `pending_stage` path is cheap defensive refusal and stays. |

**Rejected / non-findings kept honest:** `claim_lines` twice (stages + frozen harness) — deliberate
grader independence, untouched (§4). `MAX_ATTEMPTS = 2` — a decision, untouched. High-recall
candidate pass — untouched. `_MARKDOWN_MARKERS` stripping `_` from both sides — examined; can only
mask, never reject, so not an FP source. `check_render`'s glossary substring check — presence-
direction, substring is correct there.

## 3. What structurally changed (the §3 accounting)

Concepts removed: two repair-loop copies, one triple re-export, one duplicated regex, one dead
import (`conflicts` in stages.py), ~30 lines of restated cost-summary/handler plumbing.
Concepts added: `agents.run_gated` (one mechanism, six users), `agents.repair_order`,
`gates._extract_items`, `gates.verify_internal_conflict_citations`, `stages._warning_region`,
one convention-enforcing test module. Net: the invoke-gate-repair mechanism, the repair-order
format, the item-iteration rule and the work-order convention each now exist **once**.

## 4. Verification detail

```
python -m pytest                       → 256 passed, 6 skipped        (baseline 224+6; +32, none weakened, none deleted)
python eval/harness.py runs/tier3      → 17 passed · 0 failed · PASS  (identical to pre-audit grading)
prompt-surface byte check              → 14 golden artifacts, 0 diffs (work orders incl. all 3 extraction
                                         variants; repair orders via shared helper vs. prior inline strings)
strengthened gates vs runs/tier3       → check_render clean (both languages, 10 OQs + 3 conflicts covered)
                                         check_creative_brief clean (both sonnet and opus drafts)
                                         check_extract clean (all 4 extracts, incl. new conflict-citation
                                         and widened glossary gates)
                                         check_synthesis audit-added rules clean (the only flags on the
                                         signed tier3 brief are the pre-existing draft-only rules, firing
                                         on signoff/resolution exactly as designed)
eval/repair_analysis.py runs/tier3     → classifies as before; new shapes and signatures covered by tests
```

The model-call guard (`conftest._never_call_a_real_model`) is intact; the suite still points the
CLI at a nonexistent binary. The optional end-to-end proof run (~$2.25, 6 model calls, brief §5.4)
was **not** spent — every change is covered deterministically and validated against the committed
tier3 artifacts; available on request.

## 5. Usage, cost and resolved model IDs

This audit exercised only the deterministic layer: **zero pipeline model calls, $0.00 model
spend**. No stage agent ran, so there are no runtime aliases to resolve for this session.

| Role | Alias | Resolved |
|---|---|---|
| Orchestrator (audit session) | — | `claude-fable-5` |
| Pipeline stages | `haiku` / `sonnet` / `opus` | not invoked this session — last observed resolutions in `runs/tier_3_report.md` §6 and `runs/tier_4_report.md` §6 |

---

**Audit complete. All approved findings fixed or explicitly dispositioned; pytest green (256+6);
`runs/tier3` grades 17/17 unchanged; frozen files and harness-shared functions untouched.
Stopping for human review.**

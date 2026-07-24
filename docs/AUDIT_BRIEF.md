# System-design audit brief — the deterministic core

> Kickoff document for a **post-tier audit session**. Tiers 0–4 are complete and green
> (`runs/tier_*_report.md`); this is NOT a tier, but CLAUDE.md governance still applies in full.
> Mission: audit and optimise the deterministic core — the gates, the runner, the policy files —
> for robustness and coverage. Findings first; nothing changes without the protocol in §5.

## 1. Ground rules (binding — from CLAUDE.md)

- **READ-ONLY, never edit:** `docs/PRD.md` · `fixtures/northlight_01/answer_key.json` ·
  `eval/harness.py` (frozen since Tier 1) · `schema/*.json` (frozen since Tier 0).
- **Shared-function precedent** (established Tiers 3–4, human-approved each time): functions in
  `pipeline/gates.py` that the frozen harness imports (`verify_citations`,
  `compute_readiness_block`, `validate_extract`, `validate_brief`, `find_uncited_items`) may be
  changed **only** to fix a demonstrated false positive, **never** to relax a check, and **only
  with explicit human sign-off per change** — present the finding, wait for approval.
- **Never relax an acceptance criterion.** Never tune anything against `answer_key.json` — the
  pipeline is structurally barred from reading it (`gates.HARNESS_ONLY_FILES`); the audit is too.
- **Skills↔agents sync:** any edit to `skills/*.md` requires re-syncing the corresponding
  `.claude/agents/*.md` (header = everything above the `BEGIN INJECTED SKILL` marker, then the
  skill verbatim, then the END marker). `tests/test_agents.py` enforces byte-equality.
- Fixtures only; no network beyond Anthropic models; commit style `audit: <summary>`; the final
  report records **resolved model IDs** (CLAUDE.md workflow rule).

## 2. Scope — what "the deterministic core" is

**In scope:** `pipeline/gates.py` · `runner.py` · `stages.py` (the `check_*` gates + work orders)
· `extraction.py` · `conflicts.py` · `creative.py` · `diagnostics.py` · `agents.py` ·
`config/*.json` · `eval/repair_analysis.py` · `eval/cost_report.py` · `tests/` · `skills/*.md`
(with re-sync).

**Out of scope:** the frozen files (§1) · model routing (human decision, CLAUDE.md) · prompt
tuning of agent instructions beyond what a specific finding requires · performance (the whole
deterministic layer runs in ~0.3s; speed is not a problem worth one line of churn).

## 3. What "optimise" means here, ranked

1. **Robustness — hunt the remaining too-narrow gates.** Four false positives were found and
   fixed across Tiers 2–4, all the same shape — *a deterministic gate rejecting valid model
   output it hadn't anticipated*: (a) Greek `;` treated as not-a-question-mark, (b) fidelity
   strip regex not owning the annotation's separator whitespace, (c) markdown `**` markers
   breaking verbatim citation match, (d) `internal_conflicts` anchors missing from the
   known-anchor set, (e) video timecodes `00:06` matched as aspect ratios. The tier-3/4 reports
   state plainly that nobody has proven none remain. Audit every remaining exact-match /
   regex-shaped check against that pattern: *what valid output would this wrongly reject?*
2. **Coverage gaps — checks that should exist and don't.** Known seed (tier-2 report §8): the
   render gate verifies the ⚠ sections *exist* but never that all N open questions/conflicts
   actually reached both renders (the count is unverified; the frozen harness can't be extended,
   but the runner-side `check_render` can). Find others of this class.
3. **Consistency & placement.** Precedent: readiness thresholds moved from code to
   `config/readiness_policy.json` because they're agency policy. Audit for other policy-in-code.
   Known nits: `_parse_frontmatter` duplicated between `pipeline/agents.py` and
   `tests/conftest.py`; `conflicts.collect_internal_conflicts` spreads `**conflict` after
   `source_id` (silent key collision if a conflict ever carries `source_id`).
4. **Simplification** — only where it removes real risk, and see §4.

## 4. Deliberate design — do NOT "fix" these

- **`claim_lines` exists twice** (`pipeline/stages.py` and inside frozen `eval/harness.py`) —
  deliberate: the grader must not share its subject's code. Deduplicating it breaks grader
  independence.
- **`MAX_ATTEMPTS = 2`** is a decision, not an accident: a systematic failure should surface and
  be taught in the skeleton, not be masked by retries (see tier-4 commit history).
- **Candidate pass is high-recall and opinion-free** (`conflicts.py`) — emitting candidates for
  agreeing sources is intended; distinguishing agreement from contradiction is judgment and
  belongs to synthesis (PRD §5 "deterministic + LLM assist").
- **Rounding precision lives in code, thresholds in config** — the split is the contract
  (harness compares exact values).
- Committed evidence (`runs/tier3/`) keeps its historical version stamps — never rewrite records.

## 5. Protocol (findings-first)

1. **Audit pass — no edits.** Read the core against §3. Produce a ranked findings list: each with
   `file:line`, the failure scenario (concrete input → wrong outcome), severity, and whether it
   touches a harness-shared function (§1 flag).
2. **Present findings and STOP.** The human approves per finding class. Harness-shared changes
   need explicit individual sign-off.
3. **Fix approved findings** — every fix carries a regression test reproducing the failure first.
4. **Verify, in order:**
   - `python -m pytest -q` green (224+ tests; suite is model-call-proof — a guard fixture points
     the CLI at a nonexistent binary, keep it that way).
   - `python eval/harness.py runs/tier3` still **17/17** — the committed evidence must grade
     identically after any gate change; a flipped check means a relaxation slipped in.
   - Optional end-to-end proof (~$2.25, 6 model calls): one fresh
     `python pipeline/runner.py --project fixtures/northlight_01` + harness + `eval/repair_analysis.py`
     (expect clean first attempts).
5. **Report:** `runs/design_audit_report.md` — findings (including rejected/false ones), fixes,
   verification output, resolved model IDs, cost. Commit `audit: …`; push only if asked.

## 6. Orientation for a fresh session

Read in this order: `CLAUDE.md` (loads automatically) → this file → `README.md` →
`runs/tier_3_report.md` §4+§7 and `runs/tier_4_report.md` §5 (the false-positive history) →
then the code. `docs/COST_MODEL.md` explains the cost substrate; `docs/TIERS.md` is the completed
build plan (historical). The graded evidence pack is `runs/tier3/` — treat as read-only record.

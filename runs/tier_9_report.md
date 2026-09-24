# Tier 9 report — round 2 of the whole-project review: ten moves and the live re-baseline

Date: 2026-09-24 · Integration branch `r2-integration`, merged to `main` before phase D; this
report is written by the phase-D workstream (W-D) on its own worktree branch · Status: **green on
the deterministic checks; two human steps pending** (§7).

## 1. Why this round

Round 1 (Tier 8) was re-scored by 18 independent judges on 2026-09-23: every aspect between 5.33
and 7.33, none at the 8 target (`tools/project_review/rounds/r1/scores.md`). The judges converged
on one gap seen from many sides — **the configuration that ships had never produced a graded,
complete brief** — plus prompt-contract bugs (repair orders sent without their inputs, no garble
carry-through rule), measurement-validity risks (stages able to pass on stale outputs), no
held-out fixture, governance records a model could forge, and documents that contradicted each
other. The owner answered with six decisions (`docs/OPERATING_DECISIONS.md` § 2026-09-23) and
`tools/project_review/rounds/r2/PLAN.md` grouped the moves into ten, in four phases.

## 2. The ten moves and what each delivered

| # | move | workstream · commit | delivered |
|---|---|---|---|
| 1 | behaviour-preserving architecture refactor | W-A1 · `cdb2b09` | `pipeline/stages.py` split into `stage_*.py`, `render_checks.py`, `render_template.py`, `greek_lint.py`, `money.py` behind a re-export shim; `approval.py`, `records.py` (`CorruptRecordError`), `clock.py` (UTC); retention refuses a corrupt record |
| 2 | model-seam hardening before live runs | W-S · `36bcca6` | per-stage write scope (earlier outputs denied and integrity-hashed), stale outputs archived before each step, `--restricted` and `--no-session-persistence` on every call, CLI version recorded and refused below 2.1.280, **live calls opt-in** (`--live` / `BRIEF_BUILDER_LIVE=1`, exit 7), hermetic `--out`, advisory prescreen in the manifest |
| 3 | governance vouching and the agent signing block | W-G · `497cde1` | `verify-log` vouches every human-decision record (resolutions, language attestation, triage, exclusions, creative registration, sign-off regime); a tracked `.claude/settings.json` deny list and a PreToolUse hook block coding agents from `agency approve|attest|resolve|apply` and `delivery approve|release`; audit notices for embedded instructions and prescreen findings |
| 4 | prompt-contract fixes | W-R · `a893038` | self-contained repair orders; SYNTHESIS.md garble carry-through rule with a synthesis gate (owner decision #1); single-valued confidence; linked questions gated; fidelity scoring rubric and count gate; verifier declared sonnet-only in config (decision #5) |
| 5 | engineering quality and tooling | W-Q · `6463223` | ruff widened (E,W,F,B,I,UP + SIM subset), mypy on `pipeline/` in CI, pytest-cov with a floor, `requirements-dev.lock`, macOS CI leg, typed Tier 5–8 and eval modules, layering test, walkthrough archive |
| 6 | blind third keyed fixture | W-F · `9a346fe` | `fixtures/levanta_03`, written by an author barred from prompts, gates, tests and runs; answer key and extra checks hashed into `fixtures/SEALED_KEYS.json` before any run (decision #2) |
| 7 | live re-baseline + injection canary + blind run | orchestrator · `a8a1a97`, `0b70af3` | seven graded runs and one canary committed under `runs/r2-live/` (§4) |
| 8 | owner-signed regenerated brief + creative A/B | orchestrator · `cea99b7` | **partly**: 27 suggested owner decisions for `nl-r1` prepared in `owner_decisions_part1.sh` with `OWNER_DECISIONS.md`; not yet run by the owner; creative A/B not yet run (§7) |
| 9 | value, pilot and data-protection pack | W-P · `4344f3e` | pilot investment and net return (68.8–116.2 h, break-even), D-27 spending ceiling, report template and scale/extend/stop rubric, decision capture, threats to validity, survival on the approved revision, `pipeline/prescreen.py`, declaration preconditions, Greek DPIA/ROPA items |
| 10 | documentation and stakeholder consistency with measured numbers | W-D · this branch | §5 |

Integration: phase A and B merged through `r2-integration` (`47e8bf9` carries the phase-B cross-workstream fixes:
merge debt cleared, mypy clean on `pipeline/`, protected-record list completed), `ea5cd68` (render
per-question citation gate, after the first live run), merged to `main` as `2db5b03`.

## 3. Owner decisions used (2026-09-23)

1. Garble carry-through rule adopted — applied by W-R before the live runs.
2. Blind third keyed fixture — W-F; quarantine held until `lv-r1` was committed, then lifted
   (`SEALED_KEYS.json` `quarantine_lifted`; both hashes re-verified unchanged by W-D).
3. Injection canary — `runs/r2-live/canary-injection`.
4. Coding agents blocked from human-decision commands — W-G's deny rules and a PreToolUse hook
   (`tools/hooks/`), tested on synthetic command strings.
5. Verifier routing declared sonnet-only — config, CLAUDE.md and cost documents; the round-2 era
   label is "sonnet extraction + sonnet verify-extract (owner decision 2026-09-23 #5)".
6. The owner records the human decisions on the regenerated graded brief — prepared, pending.

## 4. Live results (phase C) — `runs/r2-live/`

All under the current routing (sonnet extraction + sonnet verify-extract), round-2 prompts, CLI
2.1.280, each roll from the readiness gate with no resume:

| run | fixture | frozen harness | tokens (haiku · sonnet) | wall time |
|---|---|---|---|---:|
| nl-r1 | northlight_01 | 17/17 | 596,699 (54,715 · 541,984) | 11.2 min |
| nl-r2 | northlight_01 | 17/17 | 722,344 (96,701 · 625,643) | 13.6 min |
| nl-r3 | northlight_01 | 16/17 — T1.4 | 768,929 (66,920 · 702,009) | 13.1 min |
| vo-r1 | voreas_02 | refused at synthesis (12/17 on the partial run) | 649,965, no brief | 15.5 min |
| vo-r2 | voreas_02 | 17/17 | 1,314,634 (107,357 · 1,207,277) | 21.8 min |
| vo-r3 | voreas_02 | 17/17 | 1,269,032 (128,876 · 1,140,156) | 23.1 min |
| lv-r1 | levanta_03 (blind) | 17/17 | 887,505 (77,647 · 809,858) | 18.1 min |
| canary | `tests/injection_project` | extraction only; both planted instructions not followed | 111,486 | 1.2 min |

- **17/17 in 5 of 7 graded runs.** Per-fixture means: northlight_01 695,991 tokens (n = 3),
  voreas_02 1,291,833 (n = 2 complete), levanta_03 887,505 (n = 1); pooled 926,524, about 90%
  sonnet; no run was clean. Monthly estimate at PRD A2: ~13.9 M tokens (`docs/COST_MODEL.md` §2).
- **Blind fixture:** harness 17/17; sealed extra checks **21/21** required sub-checks
  (`eval/sealed_extras.py`; one desired item partly met).
- **Verifier:** 36 checks, **13 findings, 10 applied, 3 rejected**, none dropped; one rejected
  finding was correct and is the nl-r3 T1.4 failure (`docs/EVAL_RECORD.md` §6, §10).
- **vo-r1:** the conflict-consistency gate refused two synthesis drafts that asserted one side of a
  conflict ("resolution by omission"); the run stopped with no brief (§10 of the evaluation
  record).
- Five runs that died at the session usage limit are set aside in `runs/r2-live/_quota_aborted/`
  (not results; re-run under the same IDs).

## 5. Phase D (W-D) — measured evidence documents and consistency

- **Code, with tests:** `eval/cost_report.py` skips symlinked run directories (the
  `runs/r2-live/latest` double count), splits the round-2 era with the owner-decision label,
  rounds per-brief means, and adds `--verifier` (findings forwarded / dropped / applied / rejected
  per run); new `eval/sealed_extras.py` grades a levanta_03 run against the sealed extra checks,
  deterministic where possible and otherwise with a recorded manual verdict that lapses if its
  evidence changes (`tests/test_sealed_extras.py`, 17 tests).
- **Known defects:** `runs/r2-live/KNOWN_DEFECTS.md` — 15 verified defects and one run-level
  finding in the round-2 evidence, with a table of which July (tier3) defects no longer occur; 24
  strict xfails plus "no longer occurs" guards in `tests/test_regression_r2_live.py`.
- **Documents:** `docs/EVAL_RECORD.md` and `docs/COST_MODEL.md` rewritten on the measured
  figures with era banners; README, EVIDENCE, the docs index, TIERS (banner contradiction fixed,
  Tier 9 section, timebox note), CLAUDE.md (answer-key path `fixtures/*/answer_key.json`, sonnet-only
  routing lines, `--live`, worktree/integration workflow note), new `docs/TIER_SUMMARIES.md`, the
  pilot pack's usage placeholders filled (PILOT_INVESTMENT §3, GO_LIVE R-3/T-02, OPERATING_TERMS,
  SCORECARD), `--live` on every live-run command in the documents; `runs/tier_8_report.md` got
  a dated correction line only. WALKTHROUGH.html, START_HERE.html and SHARE_ME.html (regenerated
  by `pipeline/share.py`, now carrying the decision paper's sheets 01 and 10) were updated by a
  W-D sub-workstream: era labels, the committed/local contradiction, answer-key wording, line
  counts removed, COST_MODEL § references, one step sentence across the three pages, a "what you
  are signing" table mapping the three decisions to GO_LIVE items, and a plain-language key for
  check IDs.
- **Docs-consistency test:** `tests/test_docs_consistency.py` — every shared figure in
  `docs/facts.json` appears verbatim where listed and re-derives from `runs/r2-live`; every
  `X.md §N` reference and every repo path in the current documents resolves.
- **Prompt-hygiene guard tightened:** with the quarantine lifted, levanta_03's sources join the
  five-word-quotation guard over every runtime prompt.

## 6. New gates this round (owner-visible)

- **Coverage floor 89 %** (`pyproject.toml` `fail_under`, measured 90.1 % minus one point) in
  `scripts/check.sh` and CI; `check.sh` fails when ruff, mypy or pytest-cov is missing unless the
  skip is explicit.
- **Render per-question citation gate** (`render_checks.check_render_coverage`, `ea5cd68`): a
  render whose open question lacks its own full `[source_id location]` tag is sent back for
  repair; the agency audit applies the same check before approval.
- **Live-call opt-in** (exit 7 without `--live`), **CLI minimum version** 2.1.280, per-stage write
  scope with an integrity check, the decision-command hook for coding agents, `verify-log`
  vouching every human-decision record, and the docs-consistency test.
- Tightened, not relaxed: no assertion was removed or weakened in this round.

## 7. Deferred and pending

- **Pending, human:** the owner's resolve/attest/approve decisions on `runs/r2-live/nl-r1`
  (`OWNER_DECISIONS.md`, part 1 script prepared), then the re-render and part 2; then the
  creative A/B on the signed brief. No creative result exists under the current routing, and no
  document describes one.
- **Next-round candidates from the evidence:** the fidelity check's missed glossary match (nl-r3)
  and a verifier finding that cannot override a gate outcome; the conflict-consistency repair
  order pointing the synthesis at the right field for a competing position (vo-r1, B3); questions
  re-asking open conflicts (every brief); spoken figures as numerals in questions; three Greek
  grammar slips; stale relative dates; entry metadata leaking into a render.
- **Not measured:** review time, adoption, native-editor Greek quality, real client data; n = 3/3/1
  gives wide intervals (3/3: Wilson 0.44–1.00).
- **Known tool limits:** supplementary S3 raises false positives when an evidence anchor is an
  excerpt that stops before the garbled token (lv-r1); S4 is heuristic. `config/model_routing.json`'s
  `_provenance` note still describes the pre-round-2 measurement state (config text, not behaviour;
  left for its owner).

## 8. Checks at the end of the round

`bash scripts/check.sh --no-lint` (ruff could not run offline in this worktree; skipped loudly):
**1601 passed, 0 skipped, 72 xfailed**, coverage 91.1 % (floor 89 %), mypy clean on `pipeline/`; frozen evidence `runs/tier3` 17/17
(read-only); agency benchmark 12/12, zero model calls; decision-paper gate 0 failures on 10
sheets. No runtime model call was made in phase D.

## 9. Resolved model versions

- **Development agents** (orchestrator, workstreams, judges): `claude-opus-5-5`.
- **Runtime, as recorded in every round-2 manifest:** classify and fidelity-check
  `claude-haiku-4-5-20251001`; extract, verify-extract, synthesize and render `claude-sonnet-5`
  (aliases `haiku` → `claude-haiku-4-5-20251001`, `sonnet` → `claude-sonnet-5`). CLI `2.1.280
  (Claude Code)`. No opus runtime call this round (the creative A/B has not run).

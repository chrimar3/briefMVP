# Round 2 — ten moves in four phases

Evidence: `tools/project_review/rounds/r1/` (scores.md; every judge's defects/moves in `out/*.json`).
Owner decisions: `docs/OPERATING_DECISIONS.md` §§ 2026-09-22 and 2026-09-23.

The ten moves: (1) behaviour-preserving architecture refactor · (2) model-seam hardening before live runs ·
(3) governance vouching + coding agents blocked from human-decision commands · (4) prompt-contract fixes incl. the
garble carry-through rule and self-contained repair orders · (5) engineering quality and tooling · (6) blind third
keyed fixture · (7) live re-baseline + injection canary + blind run, committed as evidence · (8) owner-signed
regenerated brief + creative A/B · (9) value, pilot and data-protection pack round 2 · (10) documentation and
stakeholder consistency with measured numbers.

Phases: **A** = W-A1 (refactor), W-F (blind fixture), W-P (pilot/value/DP) in parallel → merge → **B** = W-S, W-G,
W-R, W-Q in parallel → merge → **C** live runs (orchestrator) + owner sign-off → **D** W-D (evidence docs +
comms) → re-score.

## Rules for every workstream (unchanged from round 1, plus three)

1. Read `CLAUDE.md`, `docs/OPERATING_DECISIONS.md`, your section, and the r1 judge findings relevant to you
   (`tools/project_review/rounds/r1/out/*.json`). Verify every finding against the code before acting.
2. READ-ONLY: `docs/PRD.md`, every existing `fixtures/*/answer_key.json`, `eval/harness.py`,
   `schema/brief_schema.json`. Do not change the behaviour of anything `eval/harness.py` imports from
   `pipeline/gates.py` (`discover_sources`, `parse_source_header`, `BRIEF_FIELDS`, `validate_extract`,
   `find_uncited_items`, `verify_citations`, `validate_brief`, `HARNESS_ONLY_FILES`, `SchemaValidationError`).
3. Never relax a gate or acceptance criterion; never delete or weaken an assertion. Tightening is allowed.
4. Committed run evidence under `runs/` is historical and never edited (adding new files is allowed where stated).
5. No model calls, no network, no `claude` invocation with a prompt (`claude --help` / `--version` are fine).
   Offline replay only: `BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude"`.
6. Stay inside your file ownership; describe needed changes elsewhere in your final report.
7. Tokens by model first; dollars only as a labelled footnote.
8. **NEW — blind fixture quarantine:** nobody except W-F may open the new fixture folder W-F creates (listed in
   `fixtures/SEALED_KEYS.json`), until the orchestrator's graded run of it is committed.
9. **NEW — human decisions:** no workstream runs `agency approve|attest|resolve|apply` or `delivery approve|release`
   against committed evidence; test code exercises them only in temp dirs.
10. **NEW — type and document what you touch:** every public function you add or modify in a Tier 5–8 module gets
    type hints and a one-line docstring, matching the Stage-1 modules.
11. Before finishing: `bash scripts/check.sh` must pass (it runs pytest, the read-only frozen grade 17/17 and the
    agency benchmark). Commit on your branch: `r2-<ID>: <summary>` + `Co-Authored-By: Claude Opus 5.5
    <noreply@anthropic.com>`. Final reply ≤ 400 words: files, what each item did, verification counts, what you
    could not do, changes needed elsewhere.

## Phase A

### W-A1 — Behaviour-preserving architecture refactor (move 1)
Owns: pipeline/stages.py → new `pipeline/stage_*.py` modules (or a `pipeline/stages/` package) with
`pipeline.stages` re-exporting every public and test-used name; pipeline/revisions.py layering; a new
`pipeline/approval.py` (require_current_approval and approval-binding policy moved out of revisions.py);
`pipeline/records.py` (one record-I/O helper: `load_strict` / `load_optional` raising a named `CorruptRecordError`
subclassing ValueError, plus atomic write) used by revisions, retention, effort, run_review, eval/supplementary;
`pipeline/clock.py` (one UTC, injectable timestamp helper) used everywhere timestamps are written; public names for
cross-module helpers (`stages._money_figures` → `money_figures`, `publish._publish_locked` → `publish_run`,
`review._load_brief_meta` → `load_brief_meta`, `gates._normalise` if used elsewhere) keeping the private alias only
if a frozen or historical caller needs it; decompose `check_synthesis` into named rule functions and
`check_render_template` / `check_render` into named helpers. retention must refuse (not default) on a corrupt
record, with a test. Everything else must be byte-for-byte behaviour-preserving: the full suite and the replay
end-to-end test must pass unchanged. Do not touch agents.py, runner.py beyond renamed imports and the clock, skills/,
.claude/, docs/.

### W-F — Blind third keyed fixture (move 6)
You are the blind author. You MUST NOT open `skills/`, `.claude/`, `pipeline/` (except nothing), `tests/`,
`tools/`, `runs/` or `docs/` other than `docs/PRD.md`. You may read: `docs/PRD.md` (input contract, source types),
`eval/harness.py` (only to learn the answer-key format it grades), `schema/*.json`, `config/readiness_policy.json`,
and the existing fixtures `fixtures/northlight_01/` and `fixtures/voreas_02/` (source header format, glossary/client
config shape, answer-key format).
Create `fixtures/<new_name>_03/` for a new synthetic Greek client in a different category and campaign type
(not beverages, not athleisure), with a kickoff transcript (Greek with natural English terms, timestamps, named
speakers), an RFP, an email thread and a background document, a client config/glossary inside the folder in the
voreas style, `data_declaration.json` = `{"data_class": "synthetic"}`, and `answer_key.json` in exactly the format
the frozen harness grades (conflicts, gaps, garbled terms, traps X1/X2/X3 and the scoring block). Include trap
*instances* of kinds not in earlier fixtures, expressed within those graded categories: a spoken number that
invites unit/currency conversion (X3 family), a claim attributed to the wrong source/person in a later email
(conflict), an email that supersedes an earlier email's date (conflict with explicit supersession), and one source
line containing an embedded instruction addressed to an AI ("ignore previous…") that the brief must not obey —
record what correct behaviour looks like for that in a separate `fixtures/<new>/SEALED_EXTRA_CHECKS.md`. Make it
hard but fair; every key entry must be answerable from the sources. Then compute SHA-256 of `answer_key.json` and
`SEALED_EXTRA_CHECKS.md` and write `fixtures/SEALED_KEYS.json` = {fixture, files: {name: sha256}, sealed_on, author:
"blind W-F subagent (claude-opus-5-5)", rule: "no pipeline developer opens this folder before its first graded run
is committed"}. Validate that the sources pass the input contract and readiness by running ONLY
`python3 -c "from pipeline import gates; ..."` calls to `discover_sources` and the readiness computation (you may
import gates; do not read its source). Commit only the fixture folder and SEALED_KEYS.json.

### W-P — Value, pilot and data-protection pack round 2 (move 9)
Owns: docs/pilot/ (all), docs/COST_MODEL.md §4 (return) only, new `pipeline/prescreen.py` + tests, pipeline/data_policy.py,
eval/pilot_scorecard.py, docs/pilot/scorecard_template.csv, README.md value table rows only (the "measured vs
assumed" table), START_HERE.html headline wording only.
Do: pilot investment worksheet (role-by-role hour ranges for 4 weeks from ROLES.md, operator time, usage/seat
placeholder tied to T-02) and net return incl. Tier 5–7 role minutes, break-even; add D-27 (cost estimate + spending
ceiling, default: no start) to GO_LIVE_DECISIONS.md; pilot report template + end-of-pilot decision rubric (scale /
extend / stop mapped to pass rules); weekly checkpoint cadence; glossary co-building procedure (PRD §8 lever #1);
decision-capture procedure (who types which command, on which seat, for non-technical decision owners); account-lead
onboarding card; threats-to-validity section (recall bias in baseline_min, retro familiarity); a countable retro
side-by-side measure for the "variance floor" prize; survival measurement redefined for the Tier 5–7 workflow
(what `agency approve` binds); SCORECARD wording updated to the agency commands; PILOT_RUNBOOK exit table complete
(exit 3 pending_stage; exit 4 incl. corrupt_artifact and demo_profile_error; exit 6) and step-1 role aligned with
ROLES.md; creative "from week 1" reconciled with the first possible release week; T-03 and D-06 get owner, date,
fallback; D-16 timing aligned with the walkthrough ("before week 1"); OPERATING_TERMS stale line citations fixed;
scorecard template example row fixed; 'quality varies by author' flagged as an assumption; front doors say
"review-ready draft", not "client-ready" (README value table + START_HERE headline) with a measured output-readiness
row citing runs/tier3/KNOWN_DEFECTS.md. Data protection: approved declaration fields `screened_by`, `screened_on`,
`processor_ref`, `dpia_ref` (validated in data_policy.py; synthetic unaffected); `pipeline/prescreen.py`
`scan(project_dir) -> dict` — deterministic, advisory personal-data / special-category pre-screen (e-mail addresses,
phone numbers, IBAN-like strings, Greek + English Art. 9 keyword list in new `config/prescreen_terms.json`), never
blocking, tests with synthetic strings (W-S wires it into the runner manifest in phase B); DATA_PROTECTION.md: Art.
30 record-of-processing entry template, Hellenic DPA Decision 65/2018 DPIA list check, Law 4624/2019 employment-data
note, classify data-minimisation analysis (option only), session persistence now disabled by default (W-S adds
`--no-session-persistence`) and the retention text updated accordingly — all legal points OWNER/DPO TO CONFIRM.

## Phase B (starts after phase A is merged)

### W-S — Model-seam hardening before live runs (move 2)
Owns: pipeline/agents.py, pipeline/runner.py, pipeline/extraction.py (policy/verification plumbing, NOT the repair
order text), the stage modules' invocation plumbing (not prompt text), demo/run_demo.py, run_full.sh, demo.sh,
pipeline/publish.py (hermetic out only), tests.
Do: per-stage write scope — every earlier-stage artifact (classification.json, fidelity/, extracts/, verification/,
conflict_candidates.json, brief.json during render and creative, …) is added to that step's deny rules AND the
post-step integrity watch, with a test of a tampering render/creative step; `--no-session-persistence` in every
invocation (test); `claude --version` recorded in the manifest with a minimum-version refusal (2.1.280); evaluate
`--restricted` against the current flags and adopt it if compatible (record the decision in docs/SECURITY.md);
**live model calls are opt-in**: runner and demo refuse to invoke a real CLI unless `--live` or `BRIEF_BUILDER_LIVE=1`
is given (the replay binary needs no opt-in), with a message pointing at the replay command; clear each stage's
stale outputs before invoking it (so a resumed leg can never be graded on an earlier leg's artifact), with a test;
`_verify_policy` fails loudly on a malformed routing config; demo/run_demo.py goes through the same data
declaration, staged inputs and integrity checks as the runner (or refuses); staged file names validated like
source_id; `--out` is hermetic — publishing to `reviews/` only when `--publish` is passed or `--out` is the default
`runs/`, never for non-synthetic runs; manifests record project_dir relative to the repo when inside it; a missing
`--project` folder fails with a clear message before any run dir is created; stdout line-buffered (runner, demo) and
`python3 -u` in run_full.sh; `open` guarded by platform in run_full.sh; demo.sh / run_full.sh accept `--replay`;
wire `pipeline.prescreen.scan` (from W-P) into the manifest as advisory `prescreen` and into agency.audit notices
via W-G's hook (coordinate by recording it in the manifest only); hermeticity test: a replay run with --out tmp
leaves `git status` and `reviews/` unchanged; record the CLI version and all argv flags in docs/SECURITY.md.

### W-G — Governance vouching and the agent signing block (move 3)
Owns: pipeline/revisions.py (audit log), pipeline/approval.py, pipeline/agency.py, pipeline/delivery.py,
pipeline/release_control.py, pipeline/publish.py (data-class refusal only), .claude/settings.json (new, tracked),
new `tools/hooks/` hook script, docs/SECURITY.md §4, runs/rehearsal-lifecycle/ (regenerate), tests.
Do: `verify_audit_log` vouches every human-decision record — each `resolved_by_human` conflict must match a
`conflict_resolved` entry (index, actor, resolution digest), language_review.json (with a rebind entry when approve
moves its fingerprint), clarifications.json triage decisions, coverage_decisions.json exclusions, creative_draft
registration — and `agency.audit` blocks approval on any unvouched decision (tests for each forged-record bypass the
trust judges reproduced); `agency approve` logs the language-review rebind; the data declaration is hashed into the
input snapshot/manifest and the --solo-rehearsal waiver and publish use the recorded class, validated through
data_policy, never the live file; `python3 -m pipeline.publish` refuses non-synthetic runs; `delivery release` writes
its receipt and audit entry so a crash can never leave an unreceipted package (or reconciles on next verify);
`agency.audit` surfaces "embedded instruction not followed" extraction notes and prescreen findings as notices, and
warns when a resolved conflict leaves its field empty or its duplicate question undispositioned; the regenerated
rehearsal must pass `release_control verify-log` (valid: true). Coding-agent block: tracked `.claude/settings.json`
with `permissions.deny` Bash rules for `python3 -m pipeline.agency approve|attest|resolve|apply` and
`python3 -m pipeline.delivery approve|release` (and `python -m` / path variants) plus a PreToolUse hook script in
`tools/hooks/` that blocks the same commands robustly (argument order, `cd … &&` prefixes), with tests of the hook
script on synthetic command strings; document the Codex equivalent as an open item. Do not run those commands
yourself.

### W-R — Prompt-contract fixes (move 4)
Owns: skills/*.md, .claude/agents/*.md, repair-order and work-order TEXT builders (extraction.build_repair_order,
build_verified_repair_order, stage work-order builders), check_synthesis garble rule, check_extract linkage checks,
config/model_routing.json (declare verify-extract sonnet-only per owner decision 5 — config text + value so routing
is honestly sonnet-only; no other routing change), CLAUDE.md "Model routing" section, tests (test_orders.py,
test_prompt_hygiene.py, new).
Do: every repair order is self-contained (restates source/glossary/contract paths and the output path; no
"your first order" references) — test; SYNTHESIS.md garble carry-through rule (owner decision 1) + deterministic
check in check_synthesis (a rule-G flagged extract item that reaches reader-facing content keeps the as-heard token
visibly next to the proposed match, confidence not above the extract's) — test with synthetic data; confidence
semantics made single-valued (explicit overrides for rule G and mandatories; remove the inline 'confidence high'
from the TRANSCRIPTS annotation example) + check_extract gate; SOURCES rule 3 vs §5 contradiction reconciled;
timeline candidate-date rule made consistent with the 7-key item schema (no field exists → the candidate date
goes into an extraction note or an open question; say which); SOURCES §4/§8.3 medium/low → linked open_question
either gated in check_extract or removed — choose gating; background 'implied' qualifier rule gated or removed —
choose what the evidence supports and say why; TRANSCRIPTS.md scoring rubric (what makes high/medium/low and
pass_with_flags) + a gate that report counts match annotations; classify.md and TRANSLATION.md client-config paths
fixed to the staged inputs; render.md gets the protected-path sentence; build_render_order stops paraphrasing
TRANSLATION.md rules (single source of truth); verifier 'garbling' class documented as sonnet-only anyway. Do not
open the W-F fixture folder.

### W-Q — Engineering quality and tooling (move 5)
Owns: pyproject.toml, requirements.txt/requirements.lock + new requirements-dev.lock (ruff, pytest-cov, mypy
pinned), scripts/check.sh, .github/workflows/quality.yml, tests/ hygiene (conftest shared helpers, filter
not-applicable parametrisations instead of skipping, dead guards), new tests/test_demo.py (run_demo --help,
refusals, replay happy path), type hints + docstrings + narrowed CLI exception handling in: effort.py, quality.py,
handover.py, question_exchange.py, operations.py, clarifications.py, client_pack.py, spec_catalog.py,
agency_edit.py, retention.py, eval/*.py (not harness.py), tools/walkthrough/*.py; `tools/walkthrough/` clean-up:
move codex_* prompts/logs/md, backups/, image variants and redesign/ into `tools/walkthrough/archive/` with a README
(git mv; keep build.py, checks.py, mustkeep.json, WALKTHROUGH sources at top level) and fix any links.
Do: widen ruff to E,W,F,B,I,UP (py39) with a SIM subset and clear the per-file-ignores in non-frozen files; mypy
(non-strict) on pipeline/ in CI; pytest-cov report in check.sh + CI with a floor at the measured value minus one
point (the floor is a new gate — record it as owner-visible in the tier report); check.sh fails if lint cannot run
unless `--no-lint` is passed; README install uses requirements.lock + requirements-dev.lock (give W-D the exact
lines); CI pins actions by commit SHA only if you can verify the SHA offline — otherwise leave the tag and record it;
add a macOS job to the CI matrix; Python floor stays 3.9 (document EOL as a known item).

## Phase C — orchestrator
Live runs under the current routing with the round-2 prompts: 3 graded rolls of northlight_01, 3 of voreas_02, 1 of
the blind fixture, and one injection canary on tests/injection_project. Commit each run (with a .gitignore
exception) as evidence, grade with the frozen harness, run pass_rates, supplementary and cost_report. Then the owner
runs the resolve/attest/approve commands on one northlight run; then the creative A/B is regenerated.

## Phase D — W-D evidence documents and communication (move 10)
After phase C: EVAL_RECORD (pass rates by era incl. the new era, verifier effectiveness, blind-fixture result, canary
result, §3 decontamination state), COST_MODEL (current-routing tokens by model per brief, n independent), README,
EVIDENCE, KNOWN_DEFECTS for the new evidence, WALKTHROUGH (era labels, committed/local contradiction, answer-key
wording, current line counts or none, COST_MODEL § refs, step count aligned with START_HERE/SHARE_ME, a "what you are
signing" box mapping the three decisions to GO_LIVE items, plain-language glossary for check IDs), TIERS banner,
tier_8 report header note, CLAUDE.md answer-key path + workflow note, a timebox note separating the case-study
deliverable from later tiers, plain-language tier summaries, SHARE_ME carrying the decision paper, and a
deterministic docs-consistency test (shared figures from one facts file; `§N` references and file paths resolve).

## Phase B addenda (from the phase A reports)

- **Quarantine paths (rule 8):** `fixtures/levanta_03/`, `fixtures/SEALED_EXTRA_CHECKS_levanta_03.md`. Do not open
  them, grep inside them, or run anything over them (tests that glob `fixtures/*` must not read their content).
  `fixtures/SEALED_KEYS.json` holds only hashes and may be read.
- Phase A moved code: `pipeline.stages` is now a re-export shim over `stage_*.py`, `render_checks.py`,
  `render_template.py`, `greek_lint.py` and `money.py`; approval policy lives in `pipeline/approval.py`; record I/O
  in `pipeline/records.py` (CorruptRecordError); timestamps via `pipeline/clock.py` (UTC). Edit the new modules, not
  the shim.
- **W-S also:** add `--screened-by`, `--screened-on`, `--processor-ref`, `--dpia-ref` to `pipeline/intake.py` for
  approved declarations, then set `data_policy.REQUIRE_PRECONDITIONS = True` (owner decision 4) with tests;
  `--no-session-persistence` makes DATA_PROTECTION §1/§6 true — verify the text matches; `prescreen.scan()` result
  recorded in the manifest; prescreen and discovery must skip any non-source file that is not a declared source.
- **W-Q also:** `effort.json` lost its owner-only (0600) permission in the phase-A records refactor — restore
  owner-only permissions for records that hold named staff data (effort, and any record W-P marked personal), with a
  test; type `clarifications.py` fully; add a layering test (Stage-1 modules may not import Tier 5–8 modules except
  the documented `stage_synthesis → quality` coverage ledger and `runner → approval`).
- **W-G also:** `creative.py` chooses between two sign-off regimes by whether `agency_inputs.json` exists — make the
  regime explicit (recorded in the run, never inferred from a file's presence) with tests.

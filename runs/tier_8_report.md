# Tier 8 report — round 1 of the whole-project review: ten moves

Date: 2026-09-23 · Branch: `round1-integration` · Status: **green, awaiting human review**
(not committed by the integrator; the orchestrator commits).

> **Correction (2026-09-24, round 2 W-D):** this report was committed to `main` as `1aaa560`
> (`tier-8: …`) after the round-1 integration; the branch and "not committed" line above describe
> the state when it was written. The rest of the report is unchanged.

## 1. Why these ten moves

The owner asked for independent judge panels to rate every aspect of the project, a baseline,
and then rounds of the ten highest-leverage moves until every aspect is above 8/10
(`docs/OPERATING_DECISIONS.md` § 2026-09-22). The baseline, round 0, scored all 17 aspects
between 5.0 and 7.0 (18 judges; [`tools/project_review/rounds/r0/scores.md`](../tools/project_review/rounds/r0/scores.md)).
The lowest were routing_usage and security_injection (5.0), evaluation_method (5.33), and
data_protection, documentation and creative_quality (5.67). The judges converged on a small
number of causes: documents behind the owner's decisions, dollar-first Haiku-era usage figures
with a ruler that skipped the verifier, prompt-level answer-key isolation and graded-fixture
text inside the runtime prompts, no injection stance, no data-protection or incident pack, a
signed brief whose renders contradicted its resolutions, and no end-to-end runner test.
`tools/project_review/rounds/r1/PLAN.md` grouped the proposed moves into ten, run as six
workstreams (W1–W6) in isolated worktrees and merged into this branch, followed by one
integration pass.

## 2. What each move did

| # | Move (workstream) | What changed |
|---|---|---|
| 1 | Truth pass on docs and front doors (W1) | README measured-vs-assumed ledger (17/17 and voreas 15/17 → 16/17; Haiku-era tokens by model; current routing unmeasured; €38–40 labelled PRD A1 × A4; 210 h / €3 990–4 200); `docs/README.md` index with status and reading order; `AGENTS.md` rewritten as a pointer; `HANDOFF_WALKTHROUGH.md` moved to `docs/history/`; START_HERE / SHARE_ME / canonical WALKTHROUGH corrected to the creative-delivery decisions; v2 walkthrough retired. |
| 2 | Least-privilege runtime agents and injection defence (W2) | Agents read byte-identical staged copies in `<run>/inputs/`, never the project folder; one writable directory; deny rules for `schema/`, `config/`, `templates/`, protected run records and any `answer_key.json`; post-step integrity check; unsafe `source_id`s refused; rule U in the extraction/synthesis prompts; graded-fixture examples replaced; verifier evidence must be verbatim. `docs/SECURITY.md`. |
| 3 | Governance hardening (W2) | `agency apply` cannot resolve or delete conflicts or questions; coverage exclusions bound to the brief hash; separation of duties (approver ≠ registrant ≠ signer; attester ≠ signer) with a recorded, synthetic-only `--solo-rehearsal` waiver; `delivery release --actor`; hash-chained `audit_log.jsonl` and `release_control verify-log`. |
| 4 | Data protection pack and declaration gate (W6) | `data_declaration.json` required (runner exit 6, intake `--data-class`); `pipeline/retention.py` inventory and purge with tombstones; `docs/pilot/DATA_PROTECTION.md`. |
| 5 | Usage ruler (W3) | `eval/cost_report.py` counts `verify-extract`, reports tokens by model per stage (fresh, output, cache read, cache write), dollars only with `--usd`, repaired and clean runs side by side; `docs/COST_MODEL.md` tokens-first with era labels. |
| 6 | Evaluation record (W3) | `eval/pass_rates.py`, `eval/supplementary.py` (unfrozen, report-only), `docs/EVAL_RECORD.md`, `runs/tier3/KNOWN_DEFECTS.md` and `creative/KNOWN_DEFECTS.md`, strict-xfail regressions (`tests/test_regression_northlight.py`); risk-routing replay (0 of 66 extracts take the haiku branch) recorded as an open owner decision. |
| 7 | Output-quality process (W4) | Per-client template sets with fixed Greek boilerplate and a label table, enforced on new renders by the blocking `check_render_template`; Greek lint (warnings only); creative fact checks (invented figures, unsourced origin/market claims, review self-claims, strategic-tensions section); byte-exact fidelity gate; TRANSCRIPTS §4 and classify rule 3 gated. |
| 8 | Engineering hygiene (W5) | `pyproject.toml` (Python ≥ 3.9, strict markers, ruff), `requirements.lock`, CI matrix 3.9/3.12, `scripts/check.sh`, `eval/grade_frozen.py`; runner reports corrupt artifacts by name instead of as a lock; read-only views create no lock files; `PIPELINE_VERSION` 1.4.0. |
| 9 | Offline replay and end-to-end test (W5) | `tools/replay/claude` + `pipeline/replay.py` replay a recording so the whole Stage-1 run completes with zero model calls; end-to-end, resume, repair and refusal tests. |
| 10 | Pilot operating pack (W6) | `PILOT_RUNBOOK.md`, `ROLES.md`, `GO_LIVE_DECISIONS.md`, `INCIDENT_RECOVERY.md`; SCORECARD / OPERATING_TERMS updated; `eval/pilot_scorecard.py` evaluates every §4 rule; `runs/rehearsal-lifecycle/` deterministic lifecycle rehearsal. |

### Integration pass (this report's author)

- **Failing tests fixed (4 → 0).** `pipeline/replay.py` accepts the render order's
  `(follows template_greek)` annotation. `tools/replay/derive_recording.py` now generates both
  recorded renders deterministically from the recording's own `brief.json` and the template label
  table, so they pass today's `check_render` and `check_render_template` unchanged (new test);
  the recording is documented as a wiring fixture, not evidence (`tools/replay/README.md`).
  `tests/test_pass_rates.py` aggregates only git-tracked harness reports.
- **Rule U aligned** with `docs/SECURITY.md` §3.1 in `TRANSLATION.md`, `render.md` and
  `creative-shadow.md`; all three joined the prompt-hygiene test, which found and removed the
  last graded-fixture strings (the agency name in a Greek-article example and in template paths).
- **Input binding.** `config/greek_style.json` joined the input snapshot (keyed on its own
  presence, so older runs still resume); templates were already bound; a test proves both are
  in the snapshot and under Write/Edit deny rules.
- **Approval re-runs the fact checks.** `delivery approve` passes the signed brief to
  `check_creative_brief`; an unsourced origin claim or a missing strategic-tensions section is
  refused at approval (tests).
- **Relative CLI path.** `agents.invoke` executes the absolute path `shutil.which` found and
  turns a CLI that cannot start into `SubagentError` (tests).
- **T-01 fixed.** `render_coverage` required a question's evidence location inside one
  `[...]` tag, which a bracketed timestamp such as `[00:03:41]` can never satisfy: correct
  evidence was rejected for 6 of the 10 tier3 questions. `quality.tag_location` drops one
  enclosing pair; a question that does not cite that exact moment, or cites it under another
  source, still fails (`tests/test_quality.py`, 7 tests, written failing first). The rehearsal no
  longer moves questions out: it keeps all ten and refuses, rather than works around, any
  question the check cannot verify.
- **Flags and retention.** Pilot docs checked against the CLIs (`--solo-rehearsal`,
  `delivery release --actor`, separation rules); `verify-log` documented in CREATIVE_DELIVERY,
  ROLES and INCIDENT_RECOVERY. `pipeline.retention` inventories and purges `<run>/inputs/`
  staged copies (area `inputs`) and never deletes `audit_log.jsonl` silently: a source purge
  never touches it, and a run purge records its hash, entry count, chain head, events and
  verification result first (tests). The rehearsal now ends with `verify-log` and a retention
  purge dry run (37 steps).
- **Evidence and wording.** `.gitignore` exceptions for `runs/rehearsal-lifecycle` and
  `runs/routing-validate-01`; the latter is staged (4 files, 32 KB) and its citations relabelled
  committed. `pipeline/gates.py` docstrings describe the real answer-key mechanism (no behaviour
  change). Documentation sweep across README, CLAUDE.md (Build and Architecture only), the docs
  index, START_HERE, SHARE_ME (regenerated), WALKTHROUGH (gate green), EVIDENCE (garbles are not
  visible in the renders, KNOWN_DEFECTS B3), DEMO_PLAYBOOK (`--data-class synthetic`),
  OPERATING_TERMS and the HANDOFF banner. The obsolete `tests/test_runner.py` F841 lint waiver
  was removed after the exit-code assertion was added.

## 3. DoD results (measured 2026-09-23 on this branch)

| Check | Result |
|---|---|
| `python3 -m pytest -q` | **948 passed, 7 skipped, 48 xfailed** (before integration: 4 failed, 915 passed) |
| Frozen evidence (`eval/grade_frozen.py runs/tier3 --expect 17`) | **17/17**, `runs/tier3` byte-identical |
| `python3 eval/agency_benchmark.py` | **12/12**, 0 model calls |
| `bash scripts/check.sh` | all deterministic checks passed (ruff not installed locally: lint step skipped; CI runs it) |
| `python3 tools/walkthrough/checks.py` | 10 sheets, 13 blockquotes, 0 failures |
| `python3 runs/rehearsal-lifecycle/regenerate.py` | 37 steps, all exit codes as expected, all 10 questions kept, `verify-log` valid (17 entries) |
| Offline replay end to end (`tests/test_end_to_end.py`) | complete, exit 0, zero model calls; resume leg re-runs render only |

The 48 expected failures are strict xfails that pin documented defects in committed evidence
(voreas 16, northlight 32); they turn red if a defect disappears without the record changing.

## 4. Owner decisions used

2026-09-20 (creative delivery after named human approval) and the four decisions of 2026-09-22:
live re-baseline authorised (not run this round), one canonical walkthrough, creative in the
pilot from week 1 under separation of duties, and the data declaration as part of the input
contract. No new owner decision was taken by the integrator.

## 5. Deferred and open

- **Live re-baseline** (decision 1): 3 graded rolls each on `northlight_01` and `voreas_02` under
  the current routing, tokens by model; protocol in `docs/EVAL_RECORD.md`. Next round.
- **Risk routing**: the haiku branch of `verify-extract` is never taken on stored evidence (0/66);
  an owner decision, recorded, not changed.
- **Committed tier3 renders** still fail the agency render check for their question citations:
  they abbreviate locations (`[emails_thread Message 1, 2026-07-11]`, `[rfp_meltemi §3]`), which
  the check correctly rejects. Historical evidence is not edited; a current-template re-render
  needs a model call.
- **`runs/routing-validate-01/run_manifest.json`** records absolute paths of the operator's
  machine (the committed tier3 manifest uses repo-relative paths). Staged byte-for-byte as
  instructed; normalising them is an owner call.
- Ruff was not run locally (not installed); pyflakes is clean on every file this pass touched.

## 6. Boundaries

No model calls, no network, no `claude` CLI invocation. Read-only files untouched (`docs/PRD.md`,
answer keys, `eval/harness.py`, `schema/brief_schema.json`), and no behaviour change to anything
the harness imports from `pipeline/gates.py`. No gate relaxed; `check_render_template` unchanged.
Committed run evidence unchanged except the regenerated `runs/rehearsal-lifecycle/` records and
the newly committed `runs/routing-validate-01/`. Test assertions changed only where behaviour
changed on purpose: the replay recording's Greek banner (now the template's fixed
«ΠΡΟΣΧΕΔΙΟ» banner, asserted exactly), the rehearsal's final step (now `verify-log`, with the
withdrawal verification still asserted), and the delivery test draft (now carries the required
strategic-tensions section).

## 7. Resolved model versions

- Orchestrator and every development subagent this round (workstreams W1–W6, the integrator):
  **claude-opus-5-5**.
- Runtime pipeline stages: **none invoked this round**. Replay attempts report the model id
  `offline-replay` and zero tokens. The committed evidence keeps its original resolved IDs
  (tier3: `claude-haiku-4-5-20251001`, `claude-sonnet-5`, `claude-opus-4-8`;
  routing-validate-01: `claude-sonnet-5`).
- Usage for this round: development-agent usage only, on the owner's subscription; no runtime
  tokens.

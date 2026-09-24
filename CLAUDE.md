# Project: Brief Builder — MVP demo (hiring case study)

Two-stage AI briefing pipeline (extraction → synthesis → bilingual render → reviewed creative) built as Claude Code subagents + deterministic Python gates, on synthetic fixtures only. Full spec: `docs/PRD.md`. Tier plan + DoD: `docs/TIERS.md`.

## CRITICAL RULES (repeated at end)

1. Work ONE tier at a time (`docs/TIERS.md`). When a tier's DoD passes: commit, STOP, await human review. Never start the next tier unprompted.
2. READ-ONLY — never edit: `docs/PRD.md`, `fixtures/*/answer_key.json`, `eval/harness.py` (after Tier-1 freeze), `schema/brief_schema.json` (after Tier-0 approval).
3. Never relax an acceptance criterion to pass a gate. 3 failed attempts on one tier → write `runs/BLOCKED.md` (cause + attempts), stop the session.
4. Fixtures only. Never ingest real client/company/personal data. No network calls except Anthropic models — via subagents, plus ONE sanctioned metered path: `eval/substrate_spike.py --transport api` (cost-audit C4; PRD DR-1's production shape), which runs only on explicit invocation with explicit credentials.
5. Scope = PRD non-goals are prohibitions: no UI, no email/calendar/drive integrations, creative may be delivered only after explicit, current human creative approval via `pipeline/delivery.py` (owner decision 2026-09-20; `docs/OPERATING_DECISIONS.md`).

## Build & test commands

- `python3 pipeline/runner.py --project fixtures/northlight_01 --live` — full Stage-1 run → `runs/<ts>/` (model calls; owner-authorised runs only; without `--live` or `BRIEF_BUILDER_LIVE=1` the runner refuses a real CLI, exit 7)
- `python3 eval/harness.py runs/latest` — score vs answer key (Tier-3 gate)
- `bash scripts/check.sh` — the one deterministic check (humans and CI; toolchain: `pip install -r requirements-dev.lock`): ruff lint, mypy on `pipeline/`, `pytest` with the coverage floor, frozen grade of `runs/tier3` via the read-only `eval/grade_frozen.py` (17/17), agency benchmark, `tools/walkthrough/checks.py`; a missing tool fails unless skipped explicitly (`--no-lint`, `--no-typecheck`, `--no-cov`)
- `python3 -m pytest -q` — deterministic suite alone, no model calls (1601 passed, 72 xfailed at Tier 9; config in `pyproject.toml`)
- `BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" python3 pipeline/runner.py --project fixtures/northlight_01 --out /tmp/bb-replay` — the full Stage-1 run offline, zero model calls (replays a wiring-fixture recording; `tools/replay/README.md`)
- `python3 eval/agency_benchmark.py` — synthetic fault-injection benchmark of the Tier 5–7 safeguards (12/12)
- `python3 eval/cost_report.py <run> [--tokens] [--usd] [--verifier]` — tokens by model per stage (dollars only with `--usd`; `--verifier`: what happened to each verify-extract finding) · `python3 eval/pass_rates.py runs --markdown` · `python3 eval/supplementary.py <run>` — the evaluation record's tools
- `python3 tools/walkthrough/checks.py --file WALKTHROUGH.html` — gate for the canonical decision paper

## Architecture

- `schema/brief_schema.json` — the data model. One-way door: renders, metrics, and creative stage all hang off it.
- `skills/SOURCES.md` · `SYNTHESIS.md` · `TRANSLATION.md` · `TRANSCRIPTS.md` — the four runtime instruction files, injected into subagent prompts verbatim (extract←SOURCES, synthesize←SYNTHESIS, render←TRANSLATION, fidelity-check←TRANSCRIPTS; classify and creative-shadow carry inline instructions). Treat as spec, not suggestions.
- `.claude/agents/` — `extract` (sonnet) · `verify-extract` (sonnet) · `classify` (haiku) · `fidelity-check` (haiku) · `synthesize` (sonnet) · `render` (sonnet) · `creative-shadow` (sonnet). Invoked with the definition passed inline (`--agents`) from a neutral cwd, so this CLAUDE.md never loads into a runtime agent. (`AGENTS.md` is a pointer for development agents such as Codex; it is not a runtime file.)
- `pipeline/`, Stage 1–2 — deterministic orchestration: `gates.py` (input contract, readiness, schema validation, citation verification, readiness block) · `runner.py` (step sequence per PRD §5, stage selections, resume, input/config/template hashes, staged read-only `inputs/` copies for agents, post-step integrity check, data-declaration refusal = exit 6) · `stages.py` (re-export shim over `stage_*.py`, `render_checks.py`, `render_template.py`, `greek_lint.py`, `money.py`: classify/fidelity/synthesize/render work orders + gates) · `extraction.py` (per-source extraction + repair loop + `verify-extract` second reader) · `conflicts.py` (deterministic cross-source candidate pass) · `creative.py` (Stage-2 sign-off gate + spec-match gate + sonnet/opus A/B; output is a CREATIVE DRAFT) · `agents.py` (clean-substrate subagent invocation seam: least-privilege permission rules, deny rules for read-only dirs, protected records and any `answer_key.json`; see `docs/SECURITY.md`) · `diagnostics.py` (durable per-attempt repair log) · `intake.py` (raw folder → contract-compliant input) · `review.py` / `run_review.py` / `docview.py` (deterministic review pages and document views) · `publish.py` (the `reviews/` shelf) · `share.py` (builds `SHARE_ME.html`) · `replay.py` (offline stand-in for the `claude` CLI, driven by `tools/replay/claude`)
- `pipeline/`, Tiers 5–7 — agency operations, all explicit human commands, no model calls: `agency.py` (audit, question triage, resolve, attest, approve, amendments, decision carry-forward, client packs) · `agency_edit.py` (sourced checklist/deliverable edits) · `quality.py` (evidence coverage) · `clarifications.py` (persistent question triage) · `client_pack.py` (approved reference material) · `revisions.py` (content-bound review, evidence copies, run locks) · `handover.py` (structured handover, deliverable dependencies) · `spec_catalog.py` (reviewed traffic catalogs) · `delivery.py` (creative register → approve → release as a local package) · `release_control.py` (package verification, withdrawal) · `operations.py` (project status, portfolio queue) · `question_exchange.py` (version-bound clarification packs, revision impact) · `effort.py` (effort and handoff records); Tier 8 added `data_policy.py` (data declaration gate) · `retention.py` (inventory and purge with tombstones, incl. staged inputs; never deletes an audit log silently), separation of duties with a recorded `--solo-rehearsal` waiver, and the hash-chained `audit_log.jsonl` checked by `release_control verify-log`
- `templates/` — per-client brief template sets (`<name>.md`, fixed Greek twin `<name>.el.md`, `<name>.labels.json`), chosen by the client-config key `brief_template`; `check_render_template` enforces them on new renders
- `config/` — `readiness_policy.json` (agency readiness thresholds) · `greek_style.json` (render-stage term preferences and banned calques; language lint is warning-only) · `channel_specs.json` (deterministic channel spec table, DR-7 — creative selects rows, never generates values; a synthetic stub that cannot pass release) · `model_routing.json` (per-stage effort; `verify-extract` sonnet-only, risk classes recorded descriptively) · `campaign_profiles.json` (checklist keys per campaign type)
- `fixtures/` — `northlight_01/` (graded: synthetic transcript, RFP, email thread, background doc + `answer_key.json` with seeded conflicts, gaps, garbled terms) · `voreas_02/` (second graded fixture) · `levanta_03/` (blind third graded fixture, written by an author who never saw the prompts; answer-key and extra-check hashes in `SEALED_KEYS.json`, extra checks in `SEALED_EXTRA_CHECKS_levanta_03.md`) · `agency_*_01/` (agency-benchmark inputs, no answer key)
- `eval/harness.py` — machine-checkable DoD for Tiers 1–3 (**frozen**; the only code allowed to read the answer key). Dev tooling beside it, never frozen: `repair_analysis.py` (recurring gate violations across runs) · `cost_report.py` (token/cost ruler per run; feeds `docs/COST_MODEL.md`) · `substrate_spike.py` (C4 substrate measurement) · `agency_benchmark.py` · `pilot_scorecard.py` · `rework_report.py` · `pass_rates.py` (per-check pass rates by fixture and routing era) · `supplementary.py` (unfrozen scorer for the harness's blind spots) · `grade_frozen.py` (read-only grader wrapper) · `sealed_extras.py` (grades a levanta_03 run against the sealed extra checks)
- `docs/` — every document with its status in `docs/README.md`; `docs/OPERATING_DECISIONS.md` records owner decisions that supersede older text; `docs/SECURITY.md` (threat model and controls), `docs/EVAL_RECORD.md` (pass rates by era, blind fixture, verifier effectiveness, blind spots, known defects), `docs/COST_MODEL.md` (tokens by model per brief), `docs/TIER_SUMMARIES.md` (plain-language tier summaries) and `docs/facts.json` (shared headline figures); `docs/pilot/` is the pilot operating pack (pilot runbook, roles, go-live decisions, data protection, incident recovery, champion runbook, creative delivery, coordination, question exchange, effort, scorecard, operating terms); `docs/history/` holds superseded working notes
- `WALKTHROUGH.html` — the canonical stakeholder decision paper (gate: `tools/walkthrough/checks.py`); `tools/walkthrough/archive/redesign/` (v2) is retired and kept as history with the rest of the review-loop records (`tools/walkthrough/archive/README.md`). `START_HERE.html` and `SHARE_ME.html` (generated by `pipeline/share.py`) are the front doors.
- `tools/project_review/` — whole-project review loop: frozen rubric, judge panels, per-round baselines and plans
- `tools/replay/` — fake `claude` binary + `recordings/northlight_01` (a wiring fixture derived from `runs/tier3` by `derive_recording.py`; not evidence) · `scripts/check.sh` — the single check command
- `runs/` — timestamped outputs; `runs/latest` symlink; one `tier_N_report.md` per tier; `runs/tier3/` is the committed evidence pack for the graded run; `runs/voreas-prep-02/`, `-03/` back `tests/test_regression_voreas.py`; `runs/routing-validate-01/` is the first current-routing leg; `runs/r2-live/` is the round-2 live re-baseline (graded runs, injection canary, `KNOWN_DEFECTS.md`); `runs/rehearsal-lifecycle/` is the regenerable agency-lifecycle rehearsal. Committed evidence is historical and never edited.

## Model routing

- Schema-following work (classify, fidelity) → haiku. Extraction → sonnet, plus an independent `verify-extract` second check per source (fresh session, **always sonnet**: `strong_model` and `base_model` are both sonnet in `config/model_routing.json`, and the agent frontmatter declares sonnet too). Judgment work (synthesize, render, creative-shadow) → sonnet. (Routing decision by the human, 2026-07-30; verifier declared sonnet-only by owner decision 5, 2026-09-23 — the risk classes routed 66 of 66 stored extracts to sonnet, so the haiku branch never ran. The classes are still recorded per extract, descriptively.)
- Never upgrade a stage's model to pass a quality gate — report the failure instead; routing changes are a human decision.

## Anti-patterns

- Never let a runtime agent silently "fix" garbled tokens — extract as-is + `extraction_note` (SOURCES.md rule G).
- Never emit prose conclusions from extraction — evidence with citations only; synthesis owns prose.
- Never merge or resolve conflicting values — emit conflict objects; resolution is human-only, by design (PRD DR-10).
- Never hardcode fixture content in pipeline code — the runner must work on any folder matching the input contract.
- Never translate inside extraction — translation lives in the render stage under `TRANSLATION.md`.
- Never invent schema fields to fit awkward evidence — awkward evidence becomes an open question.

## Workflow

- Branch: `main` only (solo). One commit per tier: `tier-N: <one-line DoD summary> [green|blocked]`.
- Review-loop rounds (Tiers 8–9) are the one exception: parallel workstreams each work in an isolated git worktree on their own branch (`<round>-<workstream>: …` commits), are merged into an integration branch (`round1-integration`, `r2-integration`), and reach `main` only after the integration pass is green; the round's tier commit or report closes it. A worktree agent never edits the shared checkout.
- End every tier with `runs/tier_N_report.md`: DoD results, deferred items, usage/cost note, **resolved model versions used** (aliases → exact model IDs).
- Shared headline figures live in `docs/facts.json`; `tests/test_docs_consistency.py` checks them against the documents and the committed runs, and checks that section references and repo paths in the documents resolve.

## Compaction instructions

When compacting, preserve: (1) current tier + DoD status, (2) file paths modified this session, (3) schema/gate decisions and rationale, (4) harness results and recurring failure patterns.

## CRITICAL RULES — repeat

One tier → DoD green → commit → STOP for human review. Read-only: PRD, answer key, frozen harness, approved schema. Never relax acceptance criteria — 3 fails → `runs/BLOCKED.md` + stop. Fixtures only; no real data; no integrations; no UI; creative delivery requires explicit human approval of the exact files.

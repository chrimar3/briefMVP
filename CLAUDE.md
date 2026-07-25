# Project: Brief Builder — MVP demo (ATCOM assignment)

Two-stage AI briefing pipeline (extraction → synthesis → bilingual render → shadow creative) built as Claude Code subagents + deterministic Python gates, on synthetic fixtures only. Full spec: `docs/PRD.md`. Tier plan + DoD: `docs/TIERS.md`.

## CRITICAL RULES (repeated at end)

1. Work ONE tier at a time (`docs/TIERS.md`). When a tier's DoD passes: commit, STOP, await human review. Never start the next tier unprompted.
2. READ-ONLY — never edit: `docs/PRD.md`, `fixtures/answer_key.json`, `eval/harness.py` (after Tier-1 freeze), `schema/brief_schema.json` (after Tier-0 approval).
3. Never relax an acceptance criterion to pass a gate. 3 failed attempts on one tier → write `runs/BLOCKED.md` (cause + attempts), stop the session.
4. Fixtures only. Never ingest real client/company/personal data. No network calls except Anthropic models — via subagents, plus ONE sanctioned metered path: `eval/substrate_spike.py --transport api` (cost-audit C4; PRD DR-1's production shape), which runs only on explicit invocation with explicit credentials.
5. Scope = PRD non-goals are prohibitions: no UI, no email/calendar/drive integrations, no live creative delivery (shadow output only).

## Build & test commands

- `python pipeline/runner.py --project fixtures/northlight_01` — full Stage-1 run → `runs/<ts>/`
- `python eval/harness.py runs/latest` — score vs answer key (Tier-3 gate)
- `pytest -q` — deterministic gates: readiness, schema validation, citation completeness

## Architecture

- `schema/brief_schema.json` — the data model. One-way door: renders, metrics, and creative stage all hang off it.
- `skills/SOURCES.md` · `SYNTHESIS.md` · `TRANSLATION.md` · `TRANSCRIPTS.md` — the four runtime instruction files, injected into subagent prompts verbatim (extract←SOURCES, synthesize←SYNTHESIS, render←TRANSLATION, fidelity-check←TRANSCRIPTS; classify and creative-shadow carry inline instructions). Treat as spec, not suggestions.
- `.claude/agents/` — `extract` (haiku) · `classify` (haiku) · `fidelity-check` (haiku) · `synthesize` (sonnet) · `render` (sonnet) · `creative-shadow` (sonnet). Invoked with the definition passed inline (`--agents`) from a neutral cwd, so this CLAUDE.md never loads into a runtime agent.
- `pipeline/` — deterministic orchestration: `gates.py` (input contract, readiness, schema validation, citation verification, readiness block) · `runner.py` (step sequence per PRD §5, stage selections, resume) · `stages.py` (classify/fidelity/synthesize/render work orders + gates) · `extraction.py` (per-source extraction + repair loop) · `conflicts.py` (deterministic cross-source candidate pass) · `creative.py` (Stage-2 sign-off gate + spec-match gate + sonnet/opus A/B) · `agents.py` (clean-substrate subagent invocation seam) · `diagnostics.py` (durable per-attempt repair log)
- `config/` — `readiness_policy.json` (agency readiness thresholds) · `channel_specs.json` (deterministic channel spec table, DR-7 — creative selects rows, never generates values)
- `fixtures/northlight_01/` — synthetic transcript, RFP, email thread, background doc + `answer_key.json` (seeded conflicts, gaps, garbled terms)
- `eval/harness.py` — machine-checkable DoD for Tiers 1–3 (**frozen**; the only code allowed to read the answer key). Dev tooling beside it, never frozen: `repair_analysis.py` (recurring gate violations across runs) · `cost_report.py` (measured per-brief cost; feeds `docs/COST_MODEL.md`)
- `runs/` — timestamped outputs; `runs/latest` symlink; one `tier_N_report.md` per tier; `runs/tier3/` is the committed evidence pack for the graded run

## Model routing

- Schema-following work (extract, classify, fidelity) → haiku. Judgment work (synthesize, render, creative-shadow) → sonnet.
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
- End every tier with `runs/tier_N_report.md`: DoD results, deferred items, usage/cost note, **resolved model versions used** (aliases → exact model IDs).

## Compaction instructions

When compacting, preserve: (1) current tier + DoD status, (2) file paths modified this session, (3) schema/gate decisions and rationale, (4) harness results and recurring failure patterns.

## CRITICAL RULES — repeat

One tier → DoD green → commit → STOP for human review. Read-only: PRD, answer key, frozen harness, approved schema. Never relax acceptance criteria — 3 fails → `runs/BLOCKED.md` + stop. Fixtures only; no real data; no integrations; no UI; creative output stays shadow.

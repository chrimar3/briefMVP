# AGENTS.md — for development agents working on this repository

This file is for coding agents that read `AGENTS.md` (for example Codex) while they **develop**
Brief Builder. It is a pointer, not a second rulebook.

## The rules are CLAUDE.md's

[`CLAUDE.md`](CLAUDE.md) governs every change to this repository, whichever agent or person
makes it: its CRITICAL RULES, read-only files, model-routing rule, anti-patterns and workflow
apply to you unchanged. Read it before editing anything. Where this file and `CLAUDE.md`
differ, `CLAUDE.md` wins. Current owner decisions that supersede older documents are in
[`docs/OPERATING_DECISIONS.md`](docs/OPERATING_DECISIONS.md).

The shortest version of those rules:

- Read-only: `docs/PRD.md`, `fixtures/*/answer_key.json`, `eval/harness.py`,
  `schema/brief_schema.json`. Do not change the behaviour of the functions the harness
  imports from `pipeline/gates.py`.
- Never relax a gate or an acceptance criterion to get green; never weaken a test assertion.
- Synthetic fixtures only; never ingest real client, company or personal data.
- Never change a stage's model to pass a gate; routing is a human decision.

## The runtime is Claude Code, not the development agent

The pipeline's model stages are **Claude Code subagents**, defined in
[`.claude/agents/`](.claude/agents/) (`extract`, `verify-extract`, `classify`,
`fidelity-check`, `synthesize`, `render`, `creative-shadow`). `pipeline/agents.py` invokes each
one through `claude -p`, with the definition passed inline and the working directory set to a
neutral folder, so neither `CLAUDE.md` nor this file loads into a runtime agent. Model routing
lives in the agents' frontmatter and in `config/model_routing.json`.

A development agent does not replace those subagents and does not run them: a live pipeline
run makes model calls on the owner's account and needs the owner's authorisation.

## Checks to run before you finish

```bash
bash scripts/check.sh            # tests, frozen grade 17/17 (read-only), agency benchmark; lint if ruff is installed
python3 tools/walkthrough/checks.py --file WALKTHROUGH.html   # only if you touched the walkthrough
```

Where to find things: [`README.md`](README.md) (overview and build view) and
[`docs/README.md`](docs/README.md) (every document with its status).

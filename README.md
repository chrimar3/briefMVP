# Brief Builder — repo guide

Two views of the same system. Both are true; they answer different questions.

## Product view (what Northlight gets — the deck's Slide 3)

```
Brief/
├── Input/          ← drop the project's source files here (transcript, RFP, emails, background)
├── Output/         ← draft brief (EL + EN renders) + open questions + conflicts, per run
├── SOURCES.md      ← extraction rules per source type
├── SYNTHESIS.md    ← cross-source assembly & canonicalization rules
├── TRANSLATION.md  ← bilingual render rules
└── TRANSCRIPTS.md  ← transcript fidelity rules
```

A folder, an input, an output, and four instruction files. The skeleton is the product.

## Build view (this repo — the factory and the exam)

| Path | Role | Ships to client? |
|---|---|---|
| `skills/*.md` (×4) | The four runtime instruction files (product) | Yes |
| `schema/`, `templates/`, `glossary/` | The executable form the 4 files depend on (product) | Yes |
| `pipeline/` | Deterministic gates + runner — "the steps that ensure quality" (product) | Yes |
| `fixtures/` incl. `answer_key.json` | Synthetic exam project with seeded conflicts/gaps/garbling | **No — test apparatus** |
| `eval/` | Harness that grades runs against the answer key | **No — test apparatus** |
| `CLAUDE.md`, `docs/PRD.md`, `docs/TIERS.md` | Build governance for the autonomous run | No — engineering docs |
| `.claude/agents/` | Execution substrate on the Max subscription; in production these become metered API calls — same skeleton, deployment decision | Substrate-dependent |

Demo naming: `fixtures/northlight_01/` plays the role of `Input/`; `runs/<timestamp>/` plays the role of `Output/`.

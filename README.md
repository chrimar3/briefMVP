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
| `config/` | Agency policy the gates read — `readiness_policy.json` (readiness thresholds) · `channel_specs.json` (deterministic channel spec table, DR-7) (product) | Yes |
| `pipeline/` | Deterministic gates + runner — "the steps that ensure quality" (product) | Yes |
| `fixtures/` incl. `answer_key.json` | Synthetic exam project with seeded conflicts/gaps/garbling | **No — test apparatus** |
| `eval/harness.py` | Frozen grader — scores a run against the answer key | **No — test apparatus** |
| `eval/repair_analysis.py`, `eval/cost_report.py` | Dev tooling over run manifests (recurring-violation + cost analysis); never read the answer key | No — engineering |
| `docs/COST_MODEL.md` | Per-brief cost re-derived from measured runs | No — engineering docs |
| `CLAUDE.md`, `docs/PRD.md`, `docs/TIERS.md` | Build governance for the autonomous run | No — engineering docs |
| `.claude/agents/` | Execution substrate on the Max subscription; in production these become metered API calls — same skeleton, deployment decision | Substrate-dependent |

Demo naming: `fixtures/northlight_01/` plays the role of `Input/`; `runs/<timestamp>/` plays the role of `Output/`.

## Two stages, one gate between them

Stage 1 (client brief) is the default flow: `python pipeline/runner.py --project <folder>` runs
readiness → classify → fidelity → extract → conflict pass → synthesize → render. Stage 2 (creative
brief) is **shadow mode** and never runs automatically — it needs a human to set
`signoff.status = "signed_off"` on the brief first (DR-8), then `--stage creative` runs
`creative-shadow` (its channel specs come only from `config/channel_specs.json`, never generated).
The sign-off gate between the stages is topology, not policy: `creative-shadow` refuses any brief
that is not signed off.

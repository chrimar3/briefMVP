# TIERS.md — Autonomous run plan (goal-tier protocol)

Governing rules live in `CLAUDE.md` (one tier at a time · commit · STOP for human review · never relax a criterion · 3 fails → `runs/BLOCKED.md`).
Every DoD below is **machine-checkable** — the run proves completion, it does not declare it.

## Models
- Subagent frontmatter uses **aliases** (`haiku`, `sonnet`) so they resolve to the latest generation automatically. At kickoff, verify with `/model` and record: current generation expected = Haiku 4.5, Sonnet 5, orchestrator Fable 5 (fall back to Opus 4.8 if Fable usage draw on the Max plan proves too heavy).
- Every `tier_N_report.md` logs resolved model IDs. Never upgrade a stage's model to pass a gate (CLAUDE.md).
- Tier-4 A/B only: creative-shadow runs twice (sonnet vs opus) on identical input.

## Tier 0 — Scaffold & wiring
Build: `.claude/agents/` definitions (extract, classify, fidelity-check → haiku; synthesize, render, creative-shadow → sonnet; injecting skills verbatim: extract←SOURCES.md, synthesize←SYNTHESIS.md, render←TRANSLATION.md, fidelity-check←TRANSCRIPTS.md; classify & creative-shadow inline), `pipeline/gates.py` + `pipeline/runner.py` skeletons, pytest scaffolding.
**DoD (all automatic):**
- [ ] Both schemas parse as valid JSON Schema (pytest)
- [ ] All 6 agent files exist with correct model alias + skill injection (pytest asserts frontmatter)
- [ ] `pytest -q` green
- [ ] Commit `tier-0: ...`

## Tier 1 — Single-source extraction (transcript)
Build: extraction path end-to-end on `fixtures/northlight_01/transcript_kickoff.md`. Freeze `eval/harness.py` core at the end of this tier.
**DoD:**
- [ ] Extract validates against `schema/extract_schema.json`
- [ ] Zero items with empty `location` or `anchor` (harness check)
- [ ] Both seeded garbled terms present **as-is** in values/notes with glossary-match proposals — NOT silently corrected (harness string check vs answer key)
- [ ] `pytest -q` green · commit

## Tier 2 — Full Stage 1
Build: readiness gate → 4 extracts → cross-source conflict pass → synthesis → `brief_schema.json`-valid draft → GR + EN renders from the same JSON → open-questions list in both renders.
**DoD:**
- [ ] Negative test: removing the RFP from Input makes the readiness gate refuse with an "insufficient input" message (pytest)
- [ ] Draft validates against `schema/brief_schema.json`; `sensitivity_tier` ∈ {S0,S1} enforced
- [ ] Both renders exist; every rendered claim maps to a schema entry (no orphan prose — harness)
- [ ] Glossary terms character-exact in both renders (harness)
- [ ] `readiness` block present; harness recomputes it deterministically and values match (no model involvement)
- [ ] Commit

## Tier 3 — Quality gates (the tier that matters)
Run: `python eval/harness.py runs/latest` against `fixtures/northlight_01/answer_key.json`.
**DoD (per answer-key `scoring` block):**
- [ ] 3/3 seeded conflicts detected as `conflicts` with citations to both sources
- [ ] ≥3/4 seeded gaps present as open questions
- [ ] 2/2 garbled terms flagged (not fixed)
- [ ] 0 uncited values anywhere in the draft
- [ ] Trap X3: no resolved numeric budget total appears in draft or renders
- [ ] Trap X1: retracted OOH idea is NOT a committed deliverable
- [ ] Trap X2: speculative TikTok remark carries `conditional` qualifier
- [ ] Commit + `runs/tier_3_report.md` (screenshot-ready)

## Tier 4 — Stretch (only if Tiers 0–3 green before Saturday noon)
- Human marks `signoff.status = "signed_off"` in the fixture draft (human action — the agent never signs off).
- Creative-shadow generates creative brief drafts: A/B sonnet vs opus on the identical signed-off brief; channel specs pulled ONLY from a deterministic spec table stub.
- **DoD:** both drafts produced · spec values match the table byte-for-byte · usage note comparing the two runs · `runs/tier_4_report.md`.

## Session & budget plan
*(Internal engineering note: this document governs the demo build only, which runs on a developer subscription. Any client deployment runs on enterprise API terms per PRD §9 R1 — the substrate separation is deliberate, not incidental.)*
- Tier 0–1: one Claude Code session (Friday night). Tier 2: own session. Tier 3: own session (Saturday morning). Tier 4: optional Saturday.
- If a Max usage window caps mid-tier: the last commit is the resume point; do not rush a tier to beat a window.
- Hard cutoff **Saturday noon**: Tiers 0–3 not green → the deck ships without a demo and the run is abandoned. The deck stands alone by design.

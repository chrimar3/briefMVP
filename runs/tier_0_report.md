# Tier 0 — Scaffold & wiring · **GREEN**

**Date:** 2026-07-24 · **Branch:** `main` · **Pipeline version:** `0.1.0-tier0`
**Preceding commit:** `af1527d tier-0-inputs: human-authored scaffold (frozen)`

Tier 0 builds the substrate and proves it is wired correctly. It runs **no models** — that is
the point of the tier, and it is why every DoD item below is checkable by a machine in 0.1 s.

---

## 1. DoD results

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Both schemas parse as valid JSON Schema (pytest) | ✅ | `tests/test_schemas.py` — `Draft7Validator.check_schema` on `brief_schema.json` + `extract_schema.json` |
| 2 | All 6 agent files exist with correct model alias + skill injection (pytest asserts frontmatter) | ✅ | `tests/test_agents.py` — 9 checks × 6 agents |
| 3 | `pytest -q` green | ✅ | **76 passed, 6 skipped**, exit 0 |
| 4 | Commit `tier-0: …` | ✅ | this commit |

The 6 skips are by design, not avoidance: `test_skill_is_injected_verbatim` skips the two
inline agents, `test_inline_agents_declare_no_skill_injection` skips the four skill-backed
ones. Every agent is covered by exactly one of the two.

**Verification commands, reproducible:**

```
python3 -m pytest -q                                  → 76 passed, 6 skipped · exit 0
python3 pipeline/runner.py --project fixtures/northlight_01
                                                      → readiness gate passes, exit 3 (pending stage)
```

## 2. What was built

```
.claude/agents/     extract · classify · fidelity-check   (haiku)
                    synthesize · render · creative-shadow (sonnet)
pipeline/gates.py   input contract · readiness gate · scope enforcement ·
                    schema validation · citation completeness · readiness block
pipeline/runner.py  PRD §5 step sequence · run dirs · manifest · runs/latest
config/             readiness_policy.json — agency thresholds (ships with the skeleton)
tests/              test_schemas · test_agents · test_gates · test_runner (+ conftest)
pytest.ini · requirements.txt · .gitignore
```

## 3. Decisions taken this tier

**D0-1 — Skill injection is byte-exact concatenation, enforced by test.**
The four skeleton files are the product (README: `skills/*.md` ships to the client). Each
skill-backed agent file is `wrapper prose + BEGIN marker + verbatim skill + END marker`, and
`test_skill_is_injected_verbatim` compares the injected block against the source file
byte-for-byte. A drifted copy is a silent spec fork; this test is what prevents one. The agent
files were assembled by concatenation rather than transcription so the first copy was exact.
*Cost:* editing a skill requires re-syncing its agent file — the test names the file and the fix.

**D0-2 — Wrapper prose is operational only; the skill is the specification.**
Each agent's own text covers input/output paths, file names, and hard stops. Every rule about
*briefing craft* lives in the injected skill, and each wrapper says explicitly that the skill
wins on any apparent disagreement. This keeps the shippable skeleton the single source of truth.

**D0-3 — Least-privilege tools on every runtime agent.**
All six declare `tools: Read, Write`. `Bash`, `WebFetch`, `WebSearch` and `Task` are asserted
*absent* by test — CLAUDE.md rule 4 ("no network calls except Anthropic models") becomes a
property of the substrate rather than a promise in a document.

**D0-4 — Model aliases, never pinned IDs.**
`test_agent_model_is_an_alias_not_a_pinned_id` fails on any `claude-*` string in frontmatter,
per TIERS.md §Models. Traceability comes from logging resolved IDs per tier, not from pinning.

**D0-5 — The runner stops honestly.**
Exit codes: `0` complete · `2` insufficient input · `3` stage not built yet · `4` input-contract
or gate error. With no model handlers registered, a run executes the readiness gate, writes
`run_manifest.json`, and stops at step 2 with exit 3. The scaffold does not pretend to have
drafted anything, and `test_no_model_handlers_are_registered_at_tier_0` fails the moment a tier
boundary moves without anyone noticing.

**D0-6 — The answer key is structurally unreachable from a run.**
`discover_sources` reads `*.md` only *and* skips `HARNESS_ONLY_FILES` explicitly, with a test
asserting the file exists on disk yet never appears in a run's source list. CLAUDE.md rule 2
enforced by topology, not by discipline.

## 4. ✅ Two policy blocks — reviewed and resolved (see §9)

Both are judgment calls I had to make to produce a working gate. Both are isolated in one
readable block at the top of `pipeline/gates.py`, and neither was tuned against the answer key.

**(a) Minimum input set** — `REQUIRED_SOURCE_TYPES = ("rfp",)` plus at least one of
`("transcript", "email_thread")`; `background` deliberately cannot satisfy the second slot,
since context creates no commitments (SOURCES.md §5). This satisfies the Tier-2 negative test
(removing the RFP ⇒ refusal), and it also permits the PRD §8 Plan-B configuration
(RFP + email + background, no transcript). **Check this against how Northlight actually works:**
if a project can legitimately arrive with no RFP at all, this rule is wrong and should be
"any two of {rfp, transcript, email_thread}".

**(b) Readiness thresholds** — `ready_for_review` requires ≥ 5 of 7 fields evidenced **and**
≤ 0.4 of entries at `low` confidence; `low_confidence_share` is rounded to 4 dp because the
harness recomputes and compares this block exactly. The 5 and the 0.4 are defensible defaults,
not measured ones — they should be revisited against real drafts in Tier 3.

## 5. Flagged: a Tier-2 DoD item is already satisfied

Tier 2's first DoD item ("removing the RFP from Input makes the readiness gate refuse with an
'insufficient input' message") passes now — `tests/test_runner.py::test_run_refuses_when_the_rfp_is_removed`.
The readiness gate is deterministic and the runner could not run at all without it, so building
it as a stub would have been the more artificial choice. Reporting it here rather than banking
it silently: **no Tier-2 work beyond this was started** — no extraction, no conflict pass, no
synthesis, no renders.

## 6. Deferred

- ~~**Agent-loading verification.**~~ **RESOLVED during review** — Claude Code registered all
  six definitions (`extract`, `classify`, `fidelity-check`, `synthesize`, `render`,
  `creative-shadow`), each with `Tools: Read, Write` exactly as declared. The frontmatter parses
  and the least-privilege tool restriction is live. Resolved model IDs still await Tier 1.
- **Resolved subagent model IDs.** Aliases resolve at invocation time; Tier 0 invokes nothing.
  The table below is the registry mapping, not an observation. **Tier 1 logs observed IDs.**
- **Skill re-sync helper.** Drift is *detected* by test but must be fixed by hand. A
  `--check/--write` sync script is worth ~20 lines if the skills churn during Tiers 1–3.
- **`eval/harness.py`** — Tier 1 owns it, frozen at that tier's end.
- **Channel spec table** — Tier 4; `creative-shadow` already refuses to invent a missing row.

## 7. Model versions

| Role | Alias in use | Resolved | Basis |
|---|---|---|---|
| Orchestrator (build agent) | `opus[1m]` (`~/.claude/settings.json`) | **`claude-opus-4-8[1m]`** — Opus 4.8, 1M ctx | Session harness |
| `extract` · `classify` · `fidelity-check` | `haiku` | Haiku 4.5 → `claude-haiku-4-5-20251001` | Registry mapping — **unobserved** |
| `synthesize` · `render` · `creative-shadow` | `sonnet` | Sonnet 5 → `claude-sonnet-5` | Registry mapping — **unobserved** |

TIERS.md expected orchestrator Fable 5 with Opus 4.8 as the documented fallback on Max-plan
usage grounds; the session resolved to the fallback. Subagent generations match expectation.
`/model` is interactive and cannot be invoked from a tool call — verification was done from the
session harness plus `~/.claude/settings.json`. CLI `2.1.218`; Python 3.9.6, `jsonschema` 4.24.0,
`pytest` 7.4.3, `PyYAML` 6.0.1.

## 8. Usage & cost

**Pipeline model calls this tier: zero.** No subagent ran; no tokens were metered against the
per-brief cost model in PRD §10, which therefore remains untested until Tier 1. The only cost
was this orchestrator session on the Max subscription (file reads, authoring, one test run at
0.1 s). Per TIERS.md §Session-plan, that substrate separation is deliberate: the demo runs on a
developer subscription, any client deployment runs on enterprise API terms (PRD §9 R1).

## 9. Post-review amendments (2026-07-24, same session)

Both §4 policy blocks were reviewed and decided by the account owner. Tests: **87 passed,
6 skipped**, exit 0.

**A9-1 — Minimum input set is now an explicit count of 2, RFP still required.**
`MIN_SUBSTANTIVE_SOURCES = 2` over `SUBSTANTIVE_SOURCE_TYPES = (rfp, transcript, email_thread)`,
with `REQUIRED_SOURCE_TYPES = ("rfp",)` unchanged. `background` cannot fill a slot — context
creates no commitments (SOURCES.md §5), so an RFP plus a brand-guidelines PDF is still a refusal.

| Input | Verdict |
|---|---|
| fixture (4 sources, 3 substantive) | pass |
| fixture − RFP (transcript + emails) | **refuse** — Tier-2 DoD holds ✅ |
| RFP + background only | refuse — 1 substantive |
| transcript + emails, no RFP | refuse — missing rfp |

The alternative reading ("any two of the three") was declined at review because it would have
made Tier-2's negative DoD test unreachable and required amending `docs/TIERS.md:30`.

**A9-2 — Readiness thresholds moved to `config/readiness_policy.json`.**
Values unchanged (5 of 7 fields, ≤0.4 low-confidence share) — this is a relocation, not a
retuning. They now sit with the glossary and template as agency config that ships with the
skeleton, so a partner can change policy without a code diff. Three properties the move buys:

- **Missing or malformed config is fatal** (`ConfigError`), never silently defaulted. The runner
  and the harness both compute this block; a hidden fallback would let them disagree about what
  "ready" means with nothing failing.
- **The do-not-tune rule is written in the file the tuner opens** — calibrate against account-lead
  judgment in the pilot, never against `answer_key.json`. Tuning against the exam would make the
  Tier-3 score meaningless. A test asserts that sentence is still there.
- **`READINESS_SHARE_PRECISION` deliberately stayed in code.** Rounding is contract, not policy:
  the harness compares this value exactly, so it must not be independently editable.

Still unmeasured. Pilot weeks 2–4 are the calibration, per PRD §7.

---

**Tier 0 DoD: 4/4 green (87 passed, 6 skipped). Both review items resolved. Tier 1 not started.**

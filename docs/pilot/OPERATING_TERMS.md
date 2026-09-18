# Operating terms for the pilot: account and data

Draft decision record, 2026-09-18. Nothing is applied; `CLAUDE.md` rule 4 stands until amended (section e).

## a. The decision

Which Anthropic account the pilot runs on, under which data terms, and so which client material may enter it; agency management decides with the executive sponsor; the PRD names the sponsor at kickoff and has them sign the pilot report (§8) but does not assign this decision, and no sponsor is named in the repository: OWNER TO CONFIRM. The operator (the AI specialist, PRD §8) enforces.

## b. What the PRD assumed, what has changed

PRD §8 (operator and handover paragraph) puts the pilot on "the agency's own Anthropic workspace", a "Team/enterprise API account with DPA, zero-retention terms, EU processing, billed as a cost center", "never on any individual's personal account or plan" (also §9 R1).

Since then, the walkthrough was written on the assumption that the client will run on a Claude subscription, where the constraint is a usage window rather than a price per brief (`HANDOFF_WALKTHROUGH.md` line 24; `WALKTHROUGH.html` sheet 10, Limits). That assumption is not a recorded decision and departs from PRD §8, §9 R1 and `docs/TIERS.md` line 55, which put any client deployment on enterprise API terms: OWNER TO CONFIRM. The demo ran on a developer subscription (`docs/COST_MODEL.md` §2; `docs/TIERS.md` line 55). The API transport (DR-1's production shape) was never measured: `runs/cost_c4_report.md` §3, credential-blocked; `docs/COST_MODEL.md` §6, projection. The runner calls `claude -p` (`pipeline/agents.py`); the account is whichever the CLI is signed into.

## c. Options

| | A. Agency Team/Enterprise workspace, subscription seats | B. Agency API account | C. Hybrid |
|---|---|---|---|
| Usage | Plan usage window (per seat or per workspace: OWNER TO CONFIRM), no price per brief (sheet 10, Limits). Graded run, Haiku-era routing: 0.98 M tokens for Stage 1, 1.13 M with the shadow creative pass that PRD §3 and §8 require on every signed-off brief (sheet 10 ledger; `HANDOFF_WALKTHROUGH.md` line 30), so about 15 to 17 M a month at PRD A2. Under the 30 July routing only the transcript leg is measured, 598 743 against 295 774 tokens (`runs/routing-validate-01`; `HANDOFF_WALKTHROUGH.md` line 32); the whole-brief figure is unmeasured. Window, seats, fee: OWNER TO CONFIRM. | Metered per token. PRD §10 projects under €0.50 per brief; the measured $2.25 (`docs/COST_MODEL.md` §1) is the subagent substrate. | Seats for daily runs, a key for measurement and overflow. |
| Data terms, confirmer | PRD §8 requires DPA, zero retention, EU processing; nothing in the repository says a subscription workspace carries them. OWNER TO CONFIRM in writing; management confirms, operator files. | The PRD's assumed shape (§8, §9 R1, DR-1); terms still OWNER TO CONFIRM. | Both confirmed; the stricter applies. |
| Administration | Agency-owned workspace; seats for the operator and two brief champions (PRD §8); no personal accounts. | Agency-held key, a cost center (PRD §8). Only `eval/substrate_spike.py` takes a key; `pipeline/agents.py` has no API transport. Whether the CLI can bill an API account: OWNER TO CONFIRM. | Two credentials to govern. |
| Sheet 10 figure | Tokens; the dollar footnote does not apply. | Dollars, once the C4 API arm has run (`runs/cost_c4_report.md` §3); until then only the PRD §10 projection (<€0.50) and the $2.25 demo-substrate measurement exist, neither of which is the API price: OWNER TO CONFIRM. | Tokens; dollars for overflow. |
| Measure before week 1 | One full fixture run under current routing: tokens by model, wall time, retries, window consumed. | The C4 API arm with the key, then one full run for a real price. | Both. |

Default direction, pending question 1: A, plus one C4 run if a key exists.

## d. Permitted data in the pilot

S0 and S1 clients only (PRD §3; §6 P0; DR-11). PRD §9 R1 defines tiers by routing: "S0/S1 standard cloud API; S2 restricted access + management-controlled visibility; S3 requires EU data residency / zero-retention enterprise terms". The PRD does not separate S0 from S1 (the fixtures use both: `glossary/meltemi.json` S1, `fixtures/voreas_02/client_voreas.json` S0); that boundary: OWNER TO CONFIRM.

Tiering is per client at onboarding (DR-11): `pipeline/intake.py --tier` writes `sensitivity_tier` into the client glossary, never inferred; classify copies it (`.claude/agents/classify.md` rule 1).

Never: S2 or S3 (schema enum S0/S1 only, `schema/brief_schema.json`; `pipeline/gates.py` `enforce_sensitivity_tier` refuses); regulated clients (PRD §3); phone-call audio (DR-12 C, v2 after legal review); kickoffs recorded without consent (PRD §8, Plan B).

## e. The fixture-only boundary

`CLAUDE.md` rule 4: "Fixtures only. Never ingest real client/company/personal data. No network calls except Anthropic models" via subagents, "plus ONE sanctioned metered path: `eval/substrate_spike.py --transport api`", which "runs only on explicit invocation with explicit credentials."

Proposed rule 4a to paste after the option is confirmed (not applied):

```
4a. Pilot data (added <date>; see docs/pilot/OPERATING_TERMS.md). Rule 4 governs
    the build. The pilot may ingest S0 and S1 client documents only, tiered at onboarding
    (DR-11), on the agency account of option <A|B|C>, after management has confirmed
    DPA, retention and processing region in writing. Pilot inputs and outputs live at
    <path>, outside this repository, never committed, shared or pushed. Tests and
    the harness stay on fixtures.
```

Blast radius (grep for fixtures and synthetic: `pipeline/`, `docs/`, `README.md`, enforcers beside them):

- Policy text: `CLAUDE.md` line 3, rule 4, line 55; `docs/AUDIT_BRIEF.md` line 22; `docs/TIERS.md` line 55.
- Exposure: `fixtures/` and `glossary/` are tracked and pushed to `origin` (`.gitignore` covers `runs/*`, not `fixtures/` or `glossary/`; `glossary/meltemi.json` is the fixture client's config); a pilot project folder or client glossary in either would be pushed. `runs/*` is ignored with exceptions (`!runs/tier3`, `!runs/tier_*_report.md`, `!runs/cost_c*_report.md`, `!runs/voreas_prep_report.md`, `!runs/design_audit_report.md`, `!runs/BLOCKED.md`), so a pilot report written under one of those names would be tracked. `pipeline/runner.py` defaults `--out` to `runs/` inside the repository and `--glossary` to the single file in `glossary/` (lines 538, 546), so a pilot run must pass `--project`, `--out` and `--glossary` explicitly, all outside the repository; `pipeline/intake.py` must be run with `--out` and `--glossary-dir` outside the repository (lines 217 to 243; `docs/DEMO_PLAYBOOK.md` line 30).
- Documented input paths: `pipeline/runner.py` 13 to 15; `pipeline/intake.py` 8, 210 (`--out` help example `fixtures/acme_01`); `eval/substrate_spike.py` default `--project`; `tests/conftest.py` 38; `README.md` 100, 117, 124; `docs/DEMO_PLAYBOOK.md` 11, 20, 30, 43; `docs/AUDIT_BRIEF.md` 10, 108; `docs/EVIDENCE.md` 10, 95; `docs/demo_timing.md` 3, 8, 48; `docs/TIERS.md` 20, 38, 50.
- Synthetic-data claims false on a pilot run: `pipeline/share.py` 99, 169; `README.md` 26, 94; `docs/DECK.md` 94, 199; `docs/EVIDENCE.md` 79; `config/channel_specs.json` `_stub_notice`. Distribution copies outside the grep scope that would be false beside a pilot page: `SHARE_ME.html` (footer "Example content is a synthetic project — no real client data"), `WALKTHROUGH.html` sheet 01 banner "Synthetic project · no real client data" and sheet 10 "synthetic project", `HANDOFF_WALKTHROUGH.md` line 29 "(all synthetic)", and `reviews/*.html` regenerated from `pipeline/share.py` 169.
- Historical captures, left as they are: `docs/full_run_console.log` 2; `docs/img/full_run_complete.svg` 4, 6; `docs/img/harness_17_17.svg` 6; `docs/EVIDENCE.md` 48.
- Enforcers that stay on fixtures by design: `config/model_routing.json` 4 and `config/readiness_policy.json` 3 (never tune against the answer key); `eval/harness.py` 12, 622, 631 (sole reader of `fixtures/*/answer_key.json`; must never be pointed at a pilot run, which has no key); `pipeline/gates.py` 33, 51, 146; `pipeline/stages.py` 259; `pipeline/extraction.py` 8; `tests/conftest.py` 38.
- No code change: the input contract "works on any folder that honours it" (`pipeline/gates.py`).

## f. Before week 1

| Line | Owner |
|---|---|
| Name the executive sponsor, the agency management contact, the operator and the two brief champions | Executive sponsor with agency management (OWNER TO CONFIRM) |
| Choose option A, B or C and record it in this file | Agency management with the executive sponsor |
| Obtain Anthropic's written terms for the chosen account (DPA, retention, processing region) and file them | Agency management |
| Set the retention period for pilot inputs and outputs, the deletion step at pilot end, and who may read the pilot path (question 4) | Agency management with the executive sponsor (OWNER TO CONFIRM) |
| Confirm the plan's usage window, seat count and fee, or the API billing arrangement | Agency management |
| Create the agency workspace or key; seat the operator and two brief champions; no personal accounts | Agency management, operator |
| Issue the API key from the agency account, never a personal key, if option B or C is chosen (`runs/cost_c4_report.md` §3 calls the credential input only the account lead can provide) | Agency management (OWNER TO CONFIRM) |
| Paste rule 4a into `CLAUDE.md`; set the out-of-repository pilot path; every pilot command passes `--project`, `--out`, `--glossary` (runner) and `--out`, `--glossary-dir` (intake) pointing at it | Operator |
| Update the share-page footer and README claims listed in section e before any real run is shared | Operator |
| Run one full fixture pass on the pilot account under the 30 July routing; record tokens by model, wall time, retries, window consumed | Operator |
| Run the C4 API arm if a key exists; record the per-brief price or mark the projection retired | Operator |
| Tier each pilot client S0 or S1 at onboarding; record it in the client glossary | Account leads with agency management |
| Confirm consent for any kickoff recorded during the pilot | Account leads |
| Confirm no S2, S3 or regulated client is among the six retrospective projects | Account leads, executive sponsor |
| Write the one-page runbook (PRD §8) and train both champions | Operator, brief champions |

## g. Open questions, verbatim

1. Management: "Which Anthropic account will the pilot run on: Team or Enterprise workspace seats, an API account, or both?"
2. Management: "Can Anthropic confirm in writing that this account provides a DPA, zero retention and EU processing (PRD §8)?"
3. Management: "What is the plan's usage window, seat count and monthly fee?"
4. Sponsor: "Where, outside this repository, will pilot inputs and outputs live, and who can read them?"
5. Account leads: "Which candidate projects are S0 or S1 clients, and where is our S0/S1 line?"
6. Operator: "Does the Claude CLI bill an API account, or does B need a transport built?"
7. Sponsor: "How long are pilot inputs and outputs kept, and who deletes them at pilot end?"

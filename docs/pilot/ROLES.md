# Pilot roles (RACI)

Who does what in the four-week pilot (PRD §8), which command each role runs, which decision
each role owns, and which scorecard columns each role records. R = does it, A = owns the
decision (exactly one per row), C = consulted, I = informed. People are named at kickoff
(`GO_LIVE_DECISIONS.md` D-01); until then these are roles, not assignments.

## Roles

| Role | Who (PRD §8 / pilot docs) | Backup |
|---|---|---|
| Executive sponsor | Named at kickoff; signs the pilot report | Agency management |
| Agency management | Account terms, data terms, retention | Sponsor |
| Data-protection lead (DPO or equivalent) | Data-policy approval, rights requests, retention decisions | Agency management |
| Operator | The AI specialist; runs the pipeline, owns run hygiene | Brief champion 1 |
| Brief champions (2) | Ops/account coordinators trained on `PILOT_RUNBOOK.md` by week 4 | Each other; operator |
| Account leads (L1, L2) | Own each brief: triage, conflicts, sign-off | The other lead for review cover, never for their own sign-off |
| Bilingual reviewer | Attests source completeness and EL/EN meaning (`agency attest`) | A second fluent reviewer |
| Traffic | Spec catalog, deliverable matrix, first-handoff record | Production lead |
| Creative lead | Reviews and approves creative for delivery (`delivery approve`) | A second creative lead |

## Separation of duties (owner decision 3, 2026-09-22)

- The creative approver is neither the person who registered the draft nor the brief signer.
- The language attester is not the brief signer.
- A `--solo-rehearsal` waiver exists for synthetic rehearsals only; it is recorded, and it is
  refused when the project's `data_declaration.json` is not `synthetic`. A pilot row with a
  waiver is flagged by `eval/pilot_scorecard.py` (`sod_waiver`).
- Attribution is a recorded name, not identity verification (`CREATIVE_DELIVERY.md` §3).
  No AI agent runs a human-decision command on anyone's behalf.

## Commands and decisions

| Activity (command) | Sponsor | Mgmt | DPO | Operator | Champion | Account lead | Bilingual | Traffic | Creative lead |
|---|---|---|---|---|---|---|---|---|---|
| Declare data class and tier (`pipeline/intake.py --tier --data-class`) | | I | A for `approved` | R | R | A for `synthetic`; C | | | |
| Special-category screening before `approved` (`DATA_PROTECTION.md` §10) | | | A | C | | R | | | |
| Run the pipeline (`pipeline/runner.py --project --out --glossary`) | | | | A | R | I | | | |
| Initialize review (`agency init`) and read the audit (`agency audit`, `queue`) | | | | A | R | I | | | |
| Triage questions (`agency answer`), exclude facts (`agency exclude`) | | | | | C | A/R | | | |
| Resolve conflicts (`agency resolve`); amend wording (`agency apply`) | | | | C | | A/R | | | |
| Campaign checklist (`agency_edit checklist`) | | | | | R | A | | C | C |
| Bind spec catalog (`spec_catalog`), deliverable rows (`agency_edit deliverable`) | | | | I | | C | | A/R | C |
| Language and source review (`agency attest`) | | | | | | I | A/R | | |
| Brief sign-off (`agency approve`); handover (`agency handover`) | | | | I | R (handover) | A/R (approve) | C | I | I |
| Client question pack (`question_exchange export/import/dismiss/impact`) | | | | C | R | A | | | |
| Register creative draft (`delivery register`) | | | | A/R | R | I | | | C |
| Approve creative (`delivery approve`) | | | | I | | C | | C | A/R |
| Release package (`delivery release --actor`) | | | | A/R | R | I | | I | I |
| Verify a package (`release_control verify --run`) | | | | R | R | | | A | |
| Verify the audit log (`release_control verify-log`) | | I | | R | R | I | | C | |
| Withdraw approval (`release_control withdraw`) | I | | | R | | A | | I | C |
| Record effort (`effort record`) / handoff (`effort handoff`) | | | | R (own) | R (own) | R (own) | R (own) | A/R (handoff) | R (own) |
| Export scorecard rows, run `eval/pilot_scorecard.py` | I | | | A/R | C | C | | | |
| Retention inventory and purge (`pipeline.retention`) | | I | A | R | | | | | |
| Incident handling (`INCIDENT_RECOVERY.md`) | I | C | A for data incidents | R | R | A for client-facing errors | | C | C |
| Stop rule / go-live decision (`SCORECARD.md` §4) | A | C | C | R (report) | | C | | | |

## Scorecard columns by role (`scorecard_template.csv`)

| Role | Columns |
|---|---|
| Account lead | `assembly_min`, `review_min`, `baseline_min` (retro), question classes (`oq_*`), `conflicts_known`, `ce_*` flags, `el_register_1to5`, `signed_off`, `creative_withdrawn` |
| Operator | `run_id`, `run_date`, `sources_count`, `total_attention_min`, `machine_wall_min`, `tokens_stage1`, `gate_repairs`, `legs_refused`, `resumes_needed`, `survival_en_pct`, `survival_el_pct`, `schema_valid`, `conflicts_caught`, `conflicts_false`, `initiated_by`, `operator_min`, `creative_released`, `sod_waiver`, `manual_fallback`, `notes` |
| Creative lead | `creative_shadow_reviewed` (read: creative draft reviewed), `creative_strikes`, `creative_approved`, `creative_min` |
| Traffic | `first_handoff_accepted`, `return_reason`, `production_min`, `creative_rework_requests_q1` |
| Strategy (if involved) | `strategy_min` |
| Account team, quarter 1 | `client_revision_rounds_q1` |

Each person records only their own minutes, once, under one role (`EFFORT_RECORDING.md`).
Effort data is for the workflow, not for evaluating individuals (`DATA_PROTECTION.md` §9).

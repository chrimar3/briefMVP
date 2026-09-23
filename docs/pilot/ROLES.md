# Pilot roles (RACI)

Who does what in the four-week pilot (PRD §8), which command each role runs, which decision
each role owns, and which scorecard columns each role records. R = does it, A = owns the
decision (exactly one per row), C = consulted, I = informed. People are named at kickoff
(`GO_LIVE_DECISIONS.md` D-01); until then these are roles, not assignments.

## Roles

Time over the four weeks is a planning range from `PILOT_INVESTMENT.md` §1 (low: 6 retro and 2
live briefs at the runbook's targets; high: 4 live briefs at twice the targets); the pilot's own
effort records replace it.

| Role | Who (PRD §8 / pilot docs) | Backup | Time, weeks 1–4 |
|---|---|---|---|
| Executive sponsor | Named at kickoff; signs the pilot report | Agency management | 4.5 – 6 h |
| Agency management | Account terms, data terms, retention | Sponsor | 3 – 6 h |
| Data-protection lead (DPO or equivalent) | Data-policy approval, rights requests, retention decisions | Agency management | 5.3 – 11.3 h |
| Operator | The AI specialist; runs the pipeline, owns run hygiene | Brief champion 1 | 16.8 – 23.8 h |
| Brief champions (2) | Ops/account coordinators trained on `PILOT_RUNBOOK.md` by week 4; key human-decision commands beside their owners (below) | Each other; operator | 11 – 17 h (both) |
| Account leads (L1, L2) | Own each brief: triage, conflicts, sign-off (`ACCOUNT_LEAD_CARD.md`) | The other lead for review cover, never for their own sign-off | 17.9 – 29.8 h (both) |
| Bilingual reviewer | Attests source completeness and EL/EN meaning (`agency attest`) | A second fluent reviewer | 2.5 – 5.5 h |
| Traffic | Spec catalog, deliverable matrix, first-handoff record | Production lead | 4 – 9 h |
| Creative lead | Reviews and approves creative for delivery (`delivery approve`) | A second creative lead | 3.7 – 7.7 h |

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
| Advisory pre-screen (`python3 -m pipeline.prescreen`) and special-category screening before `approved` (`DATA_PROTECTION.md` §10) | | | A | R (pre-screen) | | R (screening) | | | |
| Co-build and approve the client glossary (`GLOSSARY_BUILDING.md`) | | | | R | | A | C | | C |
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
| Account lead | `assembly_min`, `review_min`, `agency_steps_min` (its Tier 5–7 subset), `baseline_min` (retro, recalled), `baseline_timed_min` (one timed fresh manual brief, week 1), question classes (`oq_*`), `conflicts_known`, `ce_*` flags, `el_register_1to5`, `signed_off`, `creative_withdrawn`, retro side-by-side (`human_conflicts_missed`, `human_gaps_unasked`, `draft_facts_missing`, `human_facts_unsourced`) |
| Operator | `run_id`, `run_date`, `sources_count`, `total_attention_min`, `machine_wall_min`, `tokens_stage1`, `gate_repairs`, `legs_refused`, `resumes_needed`, `survival_en_pct`, `survival_el_pct`, `survival_canonical_pct`, `schema_valid`, `conflicts_caught`, `conflicts_false`, `initiated_by`, `operator_min` (champions' keying minutes included), `baseline_team_min` (retro, recalled from each role), `creative_released`, `sod_waiver`, `manual_fallback`, `notes` |
| Creative lead | `creative_shadow_reviewed` (read: creative draft reviewed), `creative_strikes`, `creative_approved`, `creative_min` |
| Traffic | `first_handoff_accepted`, `return_reason`, `production_min`, `creative_rework_requests_q1` |
| Strategy (if involved) | `strategy_min` |
| Account team, quarter 1 | `client_revision_rounds_q1` |

Each person records only their own minutes, once, under one role (`EFFORT_RECORDING.md`).
Effort data is for the workflow, not for evaluating individuals (`DATA_PROTECTION.md` §9).

## Recording a human decision (who keys the command)

Account leads, the bilingual reviewer and the creative lead own decisions that are recorded by a
command, but only the operator and the champions have seats (`OPERATING_TERMS.md` §c). Until
D-28 decides otherwise, a decision is recorded like this:

1. **The owner decides; the champion keys.** The champion types the command on the champion's
   seat with the decision owner present (in the room, or on a call with the screen shared). The
   owner never delegates the judgment, and a champion never records a decision the owner has not
   just stated. No AI agent keys a human-decision command, for anyone.
2. **`--actor` is always the owner's name**, never the champion's or the operator's.
3. **The owner's words go into the record.** The champion types `--text`, `--summary`,
   `--reason` or `--notes` as the owner says it, then reads back the whole line (command,
   `--actor`, the text) and presses Enter only after the owner says "confirm".
4. **IDs come from the tools**, never from memory: question IDs from
   `python3 -m pipeline.agency queue $RUN`, fact IDs and conflict indexes from `agency audit`
   (`agency_audit.md`).
5. **Wording edits (`agency apply`).** The lead marks up the render (a copy, or on paper). The
   champion copies `brief.json`, edits only the entries the lead marked, shows the lead the edited
   entries, and runs `agency apply` with the lead as `--actor` and the lead's reason. Conflicts
   still change only through `agency resolve`, and questions leave only after `agency answer`.
6. **Minutes.** The owner's minutes stay in the owner's column (the lead's in `review_min`); the
   champion records their own keying minutes under the `operator` role (`EFFORT_RECORDING.md`).

Command card (replace the placeholders; the champion reads each line back before Enter):

| Owner | Command |
|---|---|
| Account lead | `python3 -m pipeline.agency answer $RUN --id QUESTION_ID --status open --actor "LEAD" --text "LEAD'S REASON" --owner "Account lead" --priority nonblocking` |
| Account lead | `python3 -m pipeline.agency resolve $RUN --index N --actor "LEAD" --text "LEAD'S DECISION AND WHY"` |
| Account lead | `python3 -m pipeline.agency exclude $RUN --fact FACT_ID --actor "LEAD" --reason "LEAD'S REASON"` |
| Account lead | `python3 -m pipeline.agency approve $RUN --actor "LEAD" --summary "WHAT THE LEAD REVIEWED AND CHANGED"` |
| Bilingual reviewer | `python3 -m pipeline.agency attest $RUN --actor "REVIEWER" --greek-register 1-5 --notes "REVIEWER'S OBSERVATIONS" --checks ...` (`BRIEF_CHAMPION_RUNBOOK.md` §6) |
| Creative lead | `python3 -m pipeline.delivery approve $RUN --actor "CREATIVE LEAD" --notes "WHAT WAS CHECKED" --checks ...` (`CREATIVE_DELIVERY.md`) |
| Account lead | `python3 -m pipeline.release_control withdraw $RUN --actor "LEAD" --reason "WHY"` |

If D-28 gives every decision role its own seat, the owner types the same lines and steps 2–4
still apply.

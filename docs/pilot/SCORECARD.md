# Pilot scorecard: the measurable contract

The four-week pilot of `docs/PRD.md` s8, scored against s7. One row per brief goes into a copy of `docs/pilot/scorecard_template.csv`, kept outside this repository (real project identifiers, CLAUDE.md rule 4). Targets come from PRD s2 and s7 unless cited otherwise; unknown values read OWNER TO CONFIRM, and every such item is consolidated with its owner, default and deadline in `GO_LIVE_DECISIONS.md` (D-13 to D-22). Roles and who records which column: `ROLES.md`. The daily path: `PILOT_RUNBOOK.md`.

Preconditions: operating account and data terms resolved (`GO_LIVE_DECISIONS.md` D-02, D-03; PRD s8 assumes an agency-owned account, DPA, zero retention, EU processing); every project folder carries a data declaration, and real material only as `approved` (owner decision 4; `DATA_PROTECTION.md`); `tests/test_regression_voreas.py` passes with no `xfail` marks remaining, on artifacts regenerated from `fixtures/voreas_02` under `config/model_routing.json` (T-03). Today the suite is green with 16 documented defects marked strict xfail on `runs/voreas-prep-02` and `-03`, which are committed evidence (`.gitignore` exceptions), so the check runs on any clone. The agency review path's citation check for open questions that cite bracketed transcript timestamps was corrected (T-01, done).

## 1. Account-lead attention: three measures, not one

PRD s2 sets about 50 minutes of total attention, 20 assembling plus 30 reviewing, against the 2-hour baseline of A1. PRD s7 says "target <30 min of account-lead attention"; `WALKTHROUGH.html` sheet 07 says "under 30 minutes of review per draft". PRD s7's 'time-to-first-draft ... <30 min of account-lead attention' does not say which component it counts; this scorecard reads it as the review component so that it agrees with s2 (20 + 30) and records assembly and total separately so either reading can be checked; reading OWNER TO CONFIRM. PRD s7 says under 30, so the pass rule is `review_min` < 30, not <= 30.

| Measure (CSV column) | Definition, unit | Recorded by, when | Baseline | Target | Pass (median): end wk 3, 6 retro briefs / end wk 4, live |
|---|---|---|---|---|---|
| Assembly time (`assembly_min`) | Active minutes the lead spends locating, exporting and dropping the sources into the input folder, from the first search to the folder handed to the operator (the manual step PRD s2 counts); the pipeline run and the operator's time are excluded. | Lead, stopwatch, at drop | none separate | about 20 | <= 20 / <= 20 |
| Review time (`review_min`) | Active minutes the lead spends on the draft, summed across sittings, from first opening the renders to writing `signoff.status = signed_off`: reading, editing, classifying questions, resolving conflicts in `brief.json`, drafting the question list for the client. Excluded: waiting for client answers, client meetings, the operator's time. Lead, stopwatch per sitting, entered at sign-off. | Lead, stopwatch, at sign-off | none separate | under 30 | < 30 / < 30 |
| Total attention (`total_attention_min`) | `assembly_min + review_min` | Operator, computed | 120 (A1, validated week 1 on 5 recent projects); retro briefs also record `baseline_min`, the minutes the original brief took | about 50 | <= 50 / <= 50 |

Machine time (`machine_wall_min`, `tokens_stage1`) is reported only: 25.2 min continuous capture, 33 min graded stages, 0.98 M tokens, Haiku-era routing (`docs/EVIDENCE.md`; sheets 01, 10). Under the current routing it is unmeasured end to end; the owner authorized the re-baseline on 2026-09-22 (T-02).

Who counts where: the account lead's minutes on the Tier 5–7 review steps (reading `agency_audit.md`, triage, exclusions, conflicts, checklist answers) are part of `review_min`; traffic's catalog and deliverable work is `production_min`; the bilingual reviewer's attestation is recorded under `account_review`, inside `review_min`, until D-21 is decided (conservative: it can only make the target harder).

## 2. Quality

Pass reads: end of week 3 (6 retro briefs) / end of week 4 (live).

- **Draft survival** (`survival_en_pct`, `survival_el_pct`). Per language: 100 x (1 - character Levenshtein distance between the draft render and the signed-off render, divided by the character count of the draft render), floored at 0, integer. Recording step: before the lead opens anything, the operator copies `brief_en.md`, `brief_el.md` and `brief.json` from `runs/<ts>/` to `<pilot path>/<brief_id>/draft/` and treats that folder as read-only; the lead edits only copies under `<pilot path>/<brief_id>/final/`, never the run directory; after `signoff.status = signed_off` the operator runs the diff script over draft/ and final/ (script: `python3 eval/pilot_scorecard.py --draft <draft.md> --final <final.md>`; this implements the scorecard character edit-distance definition, separately from the frozen harness) and writes both percentages. Survival is measured on the lead's edited render copies, never on a regenerated render. `signoff.edits_summary` carries the lead's note. Baseline none. Target >70% by pilot end (PRD s7). Pass: reported at end of week 3 / mean >70% at end of week 4. Whether survival also gates week 4 go-live (sheet 07's recommended stop rule, not the PRD) is OWNER TO CONFIRM.
- **Question precision** (`oq_precision_pct` = `oq_real / oq_total`). During review the lead marks every entry of `open_questions` in the draft with exactly one of four classes: real (the lead would put it to the client as written or lightly reworded), duplicate (it asks the same unresolved issue as a conflict object or another question; sharing a field alone is not duplication), answered_in_sources (the lead can name the source passage that answers it), not_worth_asking (none of the above and the lead would not send it). `oq_total` = count of `open_questions` in the draft; `oq_real + oq_duplicate + oq_answered_in_sources + oq_not_worth_asking = oq_total` (all five columns are in the CSV template); `oq_precision_pct` = 100 x `oq_real` / `oq_total`, integer. Baseline none. Target >80%. Pass: mean >80% / mean >80%.
- **Question duplicates** (`oq_duplicate`, `oq_answered_in_sources`). A question that repeats the same issue as a conflict or another question, or one the sources answer; counted as not real. Lead, during review. Baseline voreas_02: 4 to 5 of 16 to 17 (`runs/voreas_prep_report.md` addendum 4). Reported.
- **Conflict catch** (`conflicts_known`, `conflicts_caught`, `conflicts_false`). Retro only. Known: contradictions the lead lists in week 1 from the project's outcome, before any draft exists (s8); `conflicts_caught` = the number of the lead's listed contradictions that appear as a conflict object in the draft with both positions cited (one listed contradiction counts once); `conflicts_false` = conflict objects in the draft the lead judges not a contradiction; a conflict object the lead did not list but accepts as real is noted in `notes` and counts in neither; operator scores after the run, lead confirms at sign-off. Fixture results: northlight_01 3/3, voreas_02 2/4 then 4/4 across rolls (`runs/voreas_prep_report.md`). Target: OWNER TO CONFIRM. A merged conflict is CE2.
- **Critical errors** (`ce_*`, `ce_total`). Count per brief by class, below. Lead flags during review; operator confirms against run artifacts. Baseline: voreas_02 shows CE1 to CE4. Target 0. Pass: 0 across the set / 0 on live briefs.
- **Greek register** (`el_register_1to5`). Lead rates EL naturalness 1 to 5 at sign-off; the EL versus EN edit comparison is `survival_el_pct` against `survival_en_pct`. No numeric floor in s7: OWNER TO CONFIRM. Reported, flagged when EL survival is below EN on most briefs (s7: "systematically more").
- **Refusal rate** (`gate_repairs`, `legs_refused`, `resumes_needed`). Gate refusals repaired on retry, legs refused twice, and `--stage` resumes needed. Operator, console and `diagnostics/repair_log.jsonl`. Baseline 3 of 10 single-document runs refused, 7/10 leg pass rate, Haiku era (`docs/demo_timing.md`). Target: OWNER TO CONFIRM after re-baseline.
- **Template conformance** (`schema_valid`). `brief.json` validates against `schema/brief_schema.json` (s7 lagging "brief consistency"). Operator. Target 100%. Pass: all / all.

Critical error classes (CE1 to CE4 are documented Voreas cases, `runs/voreas_prep_report.md`; CE5 comes from `skills/SOURCES.md` rule G and harness T3.3, with a caught instance in `docs/COST_MODEL.md` s6). Counting unit: one count per occurrence in the Stage-1 `brief.json`, `brief_en.md` or `brief_el.md`; the same defect in both renders counts once; `ce_total` is the sum of the five columns. Creative drafts are scored in `creative_strikes`, never here; a critical error in released creative that reaches a client is an immediate-stop incident (section 4). Target 0 is this scorecard's proposal (PRD s7 has no critical-error measure), OWNER TO CONFIRM (D-18).

- CE1, dropped objective: an objective a source states (transcript, RFP or email) that appears in none of `objectives`, `open_questions` or `conflicts` of the signed-off `brief.json`; the lead lists the sources' objectives at review and the operator checks each. The Voreas case (finding 1) was a garble-flagged objective; the garble is the cause, not the definition.
- CE2, asserted resolution: a field carries one position's value as its sole entry while a conflict object on that field has `status = open` (addendum 1); countable from `brief.json`.
- CE3, uncited rendered claim, or a claim attributed to a source that never wrote it (addendum 2).
- CE4, invented figure: a number, total or conversion absent from the sources (finding 4; the Draft A budget total on sheet 09 is the same defect class in a creative draft and is scored under `creative_strikes`).
- CE5, silent garble repair: a garbled token rewritten without its extraction note (`skills/SOURCES.md` rule G; harness T3.3).

## 3. Adoption and lagging

- **Voluntary adoption** (`initiated_by`). 2/2 pilot leads choose the tool for their next new project; at least 3 more leads request onboarding in month 2 (s2 goal 4, s7); absolute counts. Operator. Pass: n/a / 2/2 on week-4 briefs; month-2 count in the report.
- **Creative, in the pilot from week 1** (owner decision 3, 2026-09-22; `CREATIVE_DELIVERY.md`). This replaces the PRD's shadow-only creative (s3, s8). The creative lead reviews the CREATIVE DRAFT of each signed-off brief and counts strikes (`creative_shadow_reviewed`, kept as the column name for compatibility: read "creative draft reviewed"; `creative_strikes`). Delivery happens only after the named creative lead approves the exact files, with separation of duties (approver ≠ registrant ≠ brief signer; `ROLES.md`), and is recorded per brief: `creative_approved`, `creative_released`, `creative_withdrawn` (yes/no), `sod_waiver` (must be `no` on every PILOT row; waivers are for synthetic rehearsal and are refused for non-synthetic data). Baseline northlight: 3 strikes, 1 call (sheet 09). Reported, not gated (D-20); the PRD's promotion criterion (draft survival proving extraction quality) is replaced by the owner decision, and the evidence for keeping creative in scope is strikes, withdrawals and first-handoff acceptance.
- **Downstream** (`creative_rework_requests_q1`, `client_revision_rounds_q1`). Per brief, quarter 1, traffic log (s7 lagging). Baseline OWNER TO CONFIRM. Not pilot-scored.
- **Capacity returned.** `(baseline_min - total_attention_min)` x A2 x 12 / 60, hours per year, survival-adjusted, conservative floor; operator. On PRD assumptions: (120 - 50) min x 15 briefs x 12 / 60 = 210 h/yr, x A4 EUR 19 to 20/h = about EUR 4.0 to 4.2k (sheet 10). This is the derivation the pilot uses; the EUR 5 to 6k in PRD s10 does not follow from A1 x A2 x A4 and is superseded (`docs/COST_MODEL.md` carries the reconciliation). Both are assumptions until week 1 validates A1, A2 and A4.

### Value hypothesis for the Tier 5–7 agency layer

The agency layer adds review steps inside the same < 30-minute review target; it earns its place only if the downstream measures move by more than the minutes it adds. Nothing below is measured yet: the synthetic rehearsal (`runs/rehearsal-lifecycle/`) proves the path runs, not how long it takes a person.

| Hypothesis | Role | Measured by (CSV column) | Cost it adds | Status |
|---|---|---|---|---|
| The coverage audit and question triage stop dropped objectives and duplicate questions | Account lead | `ce_dropped_objective`, `oq_duplicate`, question precision | Lead minutes in `review_min` | Assumed |
| A separate bilingual attestation catches EL meaning drift before sign-off | Bilingual reviewer | `el_register_1to5`, `survival_el_pct` vs `survival_en_pct` | Reviewer minutes (D-21) | Assumed |
| The campaign checklist and deliverable matrix cut traffic returns | Traffic, account lead | `first_handoff_accepted`, `return_reason`, `creative_rework_requests_q1` | `production_min`, lead minutes | Assumed |
| Approved creative delivery with separation of duties shortens the creative handoff without errors reaching the client | Creative lead, operator | `creative_strikes`, `creative_approved`, `creative_released`, `creative_withdrawn`, `creative_min` | Creative lead minutes | Assumed |
| Question packs and revision-impact checks reduce client revision rounds | Account lead | `client_revision_rounds_q1` (lagging) | Lead minutes | Assumed; not pilot-scored |

If `review_min` misses the target because of these steps, that is a finding for the report, not a reason to stop counting them.

## 4. Pass rules and stop rule

- End of week 3 (2 leads x 3 past projects): every "end wk 3" rule holds; reported-only measures are not gated. `python3 eval/pilot_scorecard.py <scorecard.csv>` evaluates every rule of this section per phase (`pass_rules`: pass / fail / insufficient_data; missing data is never a pass; manual-fallback briefs are reported and excluded from timing and quality rules, and cannot fill the six-brief set).
- Stop rule (sheet 07): if weeks 2 to 3 miss the targets, week 4 does not go live; the report is still written.
- Immediate stop, any week: S2 or S3 material or unapproved real data enters the system (s3, DR-11; `pipeline/gates.py` refuses S2/S3 from the client config and `pipeline/data_policy.py` refuses undeclared folders, so this means a mis-set tier or a false declaration), or any critical error reaches a client, in a brief or in released creative. Procedure: `INCIDENT_RECOVERY.md` §1–2.
- End of week 4: live briefs meet every "end wk 4" rule and 2/2 leads chose the tool.

## 5. Protocol

- Week 1: validate A1 to A5 (A1 on 5 recent projects); glossary built with the leads; transcript retention confirmed (s12 question 3), else Plan B prospective; each lead names 3 past S0 or S1 projects, lists their known conflicts, records `baseline_min`.
- Minimum pilot path for every brief: intake with a data declaration → run → `agency init` → `audit` → triage and conflicts → campaign checklist and deliverable rows → `attest` → `approve` (`PILOT_RUNBOOK.md`). Binding a verified traffic catalog, creative registration, creative approval and release are added only for briefs whose creative is delivered.
- Weeks 2 to 3: 6 retrospective briefs. For each one the lead assembles the sources (timed, `assembly_min`), the operator runs the pipeline, the lead reviews, edits and signs off the draft as if it were live (timed, `review_min`; question classes, conflict scores, CE flags and `el_register_1to5` are recorded at that sign-off), and only then compares the signed-off draft with the brief actually written (the side-by-side of PRD s8, summarised in `notes`). The six sign-off rows are the end-of-week-3 gate set. Creative drafts are reviewed on the signed-off briefs; retro briefs are past projects, so nothing is released for them.
- Week 4: first real new projects, conditional on section 4; the lead owns sign-off; creative may be delivered after creative-lead approval; two brief champions trained on the one-page runbook (s8; `PILOT_RUNBOOK.md`, details in `BRIEF_CHAMPION_RUNBOOK.md`).
- The operator is the AI specialist (s8).
- The executive sponsor named at kickoff signs the pilot report (s8). Sponsor, leads, champions: OWNER TO CONFIRM.

## 6. The CSV

One row per brief, one column per measure above, plus identifier columns. Allowed values: `row_type` EXAMPLE or PILOT; `phase` retro or live; `week` 1 to 4 (pre-pilot on the example); `lead_id` L1 or L2, the name mapping kept outside the repository; `client_tier` S0 or S1 (from the client glossary, DR-11); `initiated_by` lead, champion or operator (the adoption measure counts live rows with `initiated_by` = lead); `schema_valid`, `signed_off`, `creative_shadow_reviewed`, `creative_approved`, `creative_released`, `creative_withdrawn`, `sod_waiver`, `manual_fallback` yes or no (a brief written by hand after a refusal is a row with `manual_fallback` = yes, `INCIDENT_RECOVERY.md` §4); `baseline_min` the lead's recalled minutes for the original brief on retro rows (PRD A1 method), blank on live rows; `machine_wall_min` from `started_ts` to `finished_ts` in `run_manifest.json`, summed across resumed legs; `tokens_stage1` an integer from `python3 eval/cost_report.py runs/<ts> --tokens`; times integer minutes; shares integer percent; a cell not measured reads `not_recorded`; no cell carries any other text, comments go in `notes`. The EXAMPLE row is the northlight_01 graded run (`runs/tier3`; sheets 07, 09, 10); cells that run did not measure read `not_recorded`.


## 7. Team effort and rework reporting (agency extension)

Run `python3 eval/pilot_scorecard.py <scorecard.csv> --output <report.json>`.
EXAMPLE rows are excluded; `not_recorded` stays missing. The report shows both sample
counts and missing values. Its pooled question precision is weighted by question count;
it is descriptive and does not replace the per-brief mean target in section 2. No overall
pilot pass is inferred from partial data. Exactly 30 minutes fails the under-30 target.

Additional columns: `operator_min`, `strategy_min`, `creative_min`, `production_min`,
`total_team_min`, `first_handoff_accepted` (yes/no/not_recorded), and `return_reason`.
Each role records active work on the brief and avoidable rework caused by the brief,
not ordinary campaign production. Avoid counting one person's time in two roles.
`total_team_min` is account total attention plus the four role columns; report it only
when all components are measured. Traffic records first-handoff acceptance and the main
return reason: missing_information, conflicting_direction, wrong_version, brand_voice,
specification, language, or other. Review recurring reasons weekly with the two champions.
This adds evidence for prioritization, not an assumed saving per employee.

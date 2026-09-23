# Pilot runbook — one page

PRD §8 shape: drop files → run one command → read the verdict → route the draft. Details live in
`BRIEF_CHAMPION_RUNBOOK.md` (review), `ACCOUNT_LEAD_CARD.md` (the lead's page), `CREATIVE_DELIVERY.md`
(creative), `ROLES.md` (who, and who keys a human decision), `GLOSSARY_BUILDING.md` (week 1),
`INCIDENT_RECOVERY.md` (when something goes wrong). Real client data only after the go-live
decisions D-01 to D-07 and D-27 are closed (`GO_LIVE_DECISIONS.md`); until then use `--data-class synthetic`.

**Preflight (once per machine, operator).** `PILOT` is the agency's access-controlled pilot
location, outside this repository (D-04): `$PILOT/projects/`, `$PILOT/clients/`, `$PILOT/runs/`,
`$PILOT/packages/`, `$PILOT/scorecard.csv`. The `claude` CLI is signed into the agency account
(D-02). In the repository checkout: `python3 -m pytest -q` is green.

| Step | Who · time budget | Command | Read |
|---|---|---|---|
| 1. Drop files | Account lead gathers and dates the files · ≤ 20 min (`assembly_min`); operator or champion types the commands with the lead (`ROLES.md`) | `python3 -m pipeline.prescreen RAW_FOLDER` (advisory), then `python3 pipeline/intake.py RAW_FOLDER --out $PILOT/projects/acme_01 --glossary-dir $PILOT/clients --client acme --tier S1 --data-class approved --approval-ref DP-REF --approved-by "Data-protection lead" --approved-on YYYY-MM-DD --screened-by "Account lead" --screened-on YYYY-MM-DD --processor-ref D03-REF --dpia-ref D09-REF` (all four preconditions are required for `approved`) | Every file typed and dated; readiness line. The pre-screen lists lines to look at, never values; the lead's special-category screening (`DATA_PROTECTION.md` §10) is the control, recorded as `screened_by` / `screened_on` in `data_declaration.json` with `processor_ref` (D-03) and `dpia_ref` (D-09). Synthetic rehearsal: `--data-class synthetic`. |
| 2. Run one command | Operator or champion · machine time only | `python3 pipeline/runner.py --project $PILOT/projects/acme_01 --glossary $PILOT/clients/client_acme.json --out $PILOT/runs --run-id acme_01-r1 --live` (live model calls are opt-in; `--out` outside `runs/` publishes nothing to `reviews/`) | Exit code, table below. |
| 3. Read the verdict | Champion · 2 min | `$PILOT/runs/acme_01-r1/run_manifest.json` (`outcome`, last step's `error` or `question`) | Route per the table. |
| 4. Route for review | Champion, then account lead · < 30 min (`review_min`) | First copy `brief_en.md`, `brief_el.md`, `brief.json` to `$PILOT/<brief_id>/draft/` (read-only; the survival baseline, `SCORECARD.md` §2). Then `python3 -m pipeline.agency init $PILOT/runs/acme_01-r1 --project $PILOT/projects/acme_01 --glossary $PILOT/clients/client_acme.json --profile creative_production --actor "Operator"` then `python3 -m pipeline.agency audit $PILOT/runs/acme_01-r1` | Lead opens `brief_review.html` and `agency_audit.md`; works the blockers (`BRIEF_CHAMPION_RUNBOOK.md` §3–6); bilingual reviewer attests; lead approves. Creative: `CREATIVE_DELIVERY.md`. |
| 5. Record | Each role · 2 min | `python3 -m pipeline.effort record ...`; after approval, survival: `python3 eval/pilot_scorecard.py --draft-dir $PILOT/<brief_id>/draft --approved-run $PILOT/runs/acme_01-r1`; scorecard row; `python3 eval/pilot_scorecard.py $PILOT/scorecard.csv` | `pass_rules` per phase: pass / fail / insufficient_data. |

**Exit codes.**

| Exit | Outcome | Do this |
|---|---|---|
| 0 | `complete` | Step 4. |
| 2 | `insufficient_input` | The readiness gate refused: ask the lead for the missing source type named in the manifest. Do not rerun the same input. |
| 3 | `pending_stage` | A pipeline step has no handler in this release: a build problem, not an input problem. Stop; the operator reports it with the manifest. Do not resume on this release. |
| 4 | `stage_failed` | Read the step's `error`. A model-stage failure after repair: `INCIDENT_RECOVERY.md` §3 (resume); a refusal close to a deadline: §4. |
| 4 | `input_contract_error`, `client_config_error` | A source header or the client config is wrong (the `error` names it): fix it and re-run intake, then a NEW `--run-id`. |
| 4 | `missing_prerequisite` | A `--stage` resume found no earlier artifact: run the earlier stage, or `--stage full`. |
| 4 | `corrupt_artifact` | An earlier leg's file is unreadable (named in `error`; the earlier manifest is copied to `history/`). Leave it for inspection and start a NEW `--run-id` (`BRIEF_CHAMPION_RUNBOOK.md` §4). |
| 4 | `demo_profile_error` | A `--demo-profile` file is invalid. Demo profiles are never used in the pilot: drop the flag. |
| 4 | no new manifest; stderr `[run lock]` or `[revision safety]` | Another command holds the run, or inputs changed under a resumed run. Wait for the other command, or use a NEW `--run-id`. |
| 5 | `halted_for_human` | Answer the question in the manifest (classification or transcript fidelity), then resume with `--stage` on the same `--run-id`. |
| 2 | no manifest; stderr `[input] project folder not found` | The `--project` path is wrong. Nothing was created; fix the path. |
| 6 | `data_declaration_refused` | Fix `data_declaration.json` from the real approval record. Never invent an approval. |
| 7 | no manifest; stderr `[live calls]` | A real `claude` CLI and no live opt-in. For an authorised run add `--live` (or `BRIEF_BUILDER_LIVE=1`); to rehearse offline use the replay command the message prints. Nothing was created. |

After exit 0, `agency approve` can still refuse: its message and `agency_audit.md` name the
blockers (for example a render that lost a question's `[source_id location]` tag). Repair through
the named command, or re-render with `--stage render` on the same `--run-id` (a model call).

**Never.** Put pilot material inside the repository (refused for `approved` data); run with a
personal account; let an AI agent run `approve`, `attest`, `resolve` or `delivery approve`
(a champion keys them only with the decision owner present, `ROLES.md`);
delete `history/`, approvals or withdrawals to make something pass; re-run until a failure
disappears (a refusal is evidence).

**Minimum pilot path** (every brief, `SCORECARD.md` §5): intake → run → `agency init` → `audit` →
triage and conflicts → campaign checklist and deliverable rows (the synthetic stub catalog is
enough for brief approval) → `attest` → `approve`. Binding a verified traffic catalog, creative
registration, creative approval and release are added only for briefs whose creative is delivered.

**Checkpoints** (sponsor, 30 minutes each; the operator brings `eval/pilot_scorecard.py` output).

| When | Decision or check | Input |
|---|---|---|
| Kickoff | Every "before week 1" item of `GO_LIVE_DECISIONS.md` closed, including D-27 (spending ceiling) and D-28 | The signed sheet; `PILOT_INVESTMENT.md` |
| End of week 1 | A1 to A5 validated; glossaries approved; timed baselines taken; retro projects and their known conflicts listed; T-08 done, T-07 scheduled | `SCORECARD.md` §5; `GLOSSARY_BUILDING.md` |
| End of week 2 | Midpoint: first retro rows, refusals, incidents, recurring return reasons; T-07 minutes against the < 30-minute target | Scorecard rows; incident log |
| End of week 3 | Go / no-go for week 4 on the six retro rows (`pass_rules.end_week_3`, stop rule) | `SCORECARD.md` §4 |
| End of week 4 | Pilot report and the scale / extend / stop decision | `PILOT_REPORT_TEMPLATE.md` |

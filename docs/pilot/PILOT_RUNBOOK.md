# Pilot runbook — one page

PRD §8 shape: drop files → run one command → read the verdict → route the draft. Details live in
`BRIEF_CHAMPION_RUNBOOK.md` (review), `CREATIVE_DELIVERY.md` (creative), `ROLES.md` (who),
`INCIDENT_RECOVERY.md` (when something goes wrong). Real client data only after the go-live
decisions D-01 to D-07 are closed (`GO_LIVE_DECISIONS.md`); until then use `--data-class synthetic`.

**Preflight (once per machine, operator).** `PILOT` is the agency's access-controlled pilot
location, outside this repository (D-04): `$PILOT/projects/`, `$PILOT/clients/`, `$PILOT/runs/`,
`$PILOT/packages/`, `$PILOT/scorecard.csv`. The `claude` CLI is signed into the agency account
(D-02). In the repository checkout: `python3 -m pytest -q` is green.

| Step | Who · time budget | Command | Read |
|---|---|---|---|
| 1. Drop files | Account lead · ≤ 20 min (`assembly_min`) | `python3 pipeline/intake.py RAW_FOLDER --out $PILOT/projects/acme_01 --glossary-dir $PILOT/clients --client acme --tier S1 --data-class approved --approval-ref DP-REF --approved-by "Data-protection lead" --approved-on YYYY-MM-DD` | Every file typed and dated; readiness line. First screen for special-category data (`DATA_PROTECTION.md` §10). Synthetic rehearsal: `--data-class synthetic`. |
| 2. Run one command | Operator or champion · machine time only | `python3 pipeline/runner.py --project $PILOT/projects/acme_01 --glossary $PILOT/clients/client_acme.json --out $PILOT/runs --run-id acme_01-r1` | Exit code, table below. |
| 3. Read the verdict | Champion · 2 min | `$PILOT/runs/acme_01-r1/run_manifest.json` (`outcome`, last step's `error` or `question`) | Route per the table. |
| 4. Route for review | Champion, then account lead · < 30 min (`review_min`) | `python3 -m pipeline.agency init $PILOT/runs/acme_01-r1 --project $PILOT/projects/acme_01 --glossary $PILOT/clients/client_acme.json --profile creative_production --actor "Operator"` then `python3 -m pipeline.agency audit $PILOT/runs/acme_01-r1` | Lead opens `brief_review.html` and `agency_audit.md`; works the blockers (`BRIEF_CHAMPION_RUNBOOK.md` §3–6); bilingual reviewer attests; lead approves. Creative: `CREATIVE_DELIVERY.md`. |
| 5. Record | Each role · 2 min | `python3 -m pipeline.effort record ...`; scorecard row; `python3 eval/pilot_scorecard.py $PILOT/scorecard.csv` | `pass_rules` per phase: pass / fail / insufficient_data. |

**Exit codes.**

| Exit | Outcome | Do this |
|---|---|---|
| 0 | `complete` | Step 4. |
| 2 | `insufficient_input` | The readiness gate refused: ask the lead for the missing source type named in the manifest. Do not rerun the same input. |
| 4 | `stage_failed`, `input_contract_error`, `client_config_error`, `missing_prerequisite` | Read the step's `error`. A model-stage failure after repair: `INCIDENT_RECOVERY.md` §3 (resume); a header problem: re-run intake. |
| 5 | `halted_for_human` | Answer the question in the manifest (classification or transcript fidelity), then resume with `--stage` on the same `--run-id`. |
| 6 | `data_declaration_refused` | Fix `data_declaration.json` from the real approval record. Never invent an approval. |

**Never.** Put pilot material inside the repository (refused for `approved` data); run with a
personal account; let an AI agent run `approve`, `attest`, `resolve` or `delivery approve`;
delete `history/`, approvals or withdrawals to make something pass; re-run until a failure
disappears (a refusal is evidence).

**Minimum pilot path** (every brief, `SCORECARD.md` §5): intake → run → `agency init` → `audit` →
triage and conflicts → campaign checklist and deliverable rows (the synthetic stub catalog is
enough for brief approval) → `attest` → `approve`. Binding a verified traffic catalog, creative
registration, creative approval and release are added only for briefs whose creative is delivered.

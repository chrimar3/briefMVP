# Incidents and recovery

What to do when something goes wrong during the pilot. Owners are roles (`ROLES.md`); time
bounds are proposals: **OWNER TO CONFIRM** (`GO_LIVE_DECISIONS.md` D-11). Every incident gets an
entry in the incident log, `$PILOT/incidents.jsonl`, one JSON object per line:
`{"id", "opened_at", "class", "run", "brief_id", "what_happened", "actions": [...], "notified": [...],
"owner", "closed_at", "scorecard_effect"}`. The log holds facts about the incident, not copies of
client material. No command in this repository contacts a client; notifications go through the
agency's existing channels.

## 1. A critical error reached a client

Trigger: a delivered brief or released creative package carries a critical error (CE1–CE5,
`SCORECARD.md` §2) or unapproved content.

1. Account lead: stop further sharing; tell the operator (immediately).
2. Operator, with the account lead as actor: withdraw the approval, which marks every release
   package from that run as withdrawn (within 1 working hour):
   `python3 -m pipeline.release_control withdraw $PILOT/runs/RUN --actor "Account lead" --reason "What was wrong"`
   then confirm: `python3 -m pipeline.release_control verify $PILOT/packages/PKG --run $PILOT/runs/RUN`
   reports `withdrawn: true`. The tool does not recall files already sent.
3. Account lead: notify the client contact through the agency's usual channel (same working
   day), with the corrected brief or a date for it.
4. Operator: log the incident; record the CE flag on the brief's scorecard row.
5. Sponsor: this is an immediate-stop trigger (`SCORECARD.md` §4). The pilot pauses until the
   sponsor decides, with the incident log in hand, whether and how it resumes.

Fixing: correct through the normal path (resolve or amend, re-render, fresh attestation and
approvals); never edit or delete withdrawal or approval history.

## 2. Unapproved real data or out-of-scope material was ingested

Trigger: a folder declared `synthetic` contains real material; an S2/S3 or regulated client was
run; special-category data went through a run; an `approved` declaration has no real approval.

1. Operator: stop all runs on that project; do not share any output (immediately).
2. DPO (A) with the operator (R): inventory every copy, then purge:
   `python3 -m pipeline.retention inventory --runs $PILOT/runs`
   `python3 -m pipeline.retention purge --run $PILOT/runs/RUN --actor "Operator" --reason "Unapproved data, incident ID"`
   (repeat per run; `--source-sha` for one document across runs). Delete the project folder
   copy, the operator's `claude -p` session files for the listed session IDs, and any release
   packages or shares made from the run. The tombstone records what was deleted.
3. DPO: assess whether this is a personal-data breach and whether the supervisory authority
   must be notified (72-hour clock, Art. 33) and the people concerned informed (Art. 34):
   **OWNER/DPO TO CONFIRM** per incident. Ask the model provider about its copy under the DPA.
4. Operator: log; record `schema_valid`/`ce_*` as usual and note the incident on the row.
5. Sponsor: immediate-stop trigger (`SCORECARD.md` §4).

Prevention in code: the data declaration gate (`pipeline/data_policy.py`), the S0/S1 tier gate,
the out-of-repository rule for approved data. The declaration records what a human asserted; it
cannot detect a false assertion, which is why the screening step (`DATA_PROTECTION.md` §10) exists.

## 3. Usage window exhausted, CLI signed out, or model outage mid-run

Symptom: exit 4, `outcome: stage_failed`, the failed step's `error` names the subagent failure
(non-zero CLI exit, empty or non-JSON output, timeout).

1. Operator: do not change the model routing to get through (routing is a human decision,
   `CLAUDE.md`); do not start a new run ID for unchanged input.
2. Restore access (wait for the window, sign the CLI back into the agency account).
3. Resume the failed leg on the same run directory; completed legs are reused:
   - extraction: `python3 pipeline/runner.py --project P --glossary G --out $PILOT/runs --run-id RUN --stage extraction --source SOURCE_ID`
     (one source; the other extracts stay), then `--stage synthesis`;
   - synthesis or render: `--stage synthesis` or `--stage render` with the same `--run-id`.
   If any input changed in between, the runner refuses the resume: start a new run ID.
4. Operator: add 1 to `resumes_needed` on the brief's scorecard row; the manifest keeps the
   earlier steps (`from_earlier_run`), so `machine_wall_min` sums the legs.

## 4. Refusal close to a client deadline

Trigger: the readiness gate refuses (exit 2), or a leg fails twice after repair (exit 4), and the
brief is due before the cause can be fixed.

1. Account lead decides (A): write the brief by hand, as today. The pipeline's gates are not
   bypassed; the demo profile is never used for client work.
2. Operator: record the brief as a PILOT row with `manual_fallback=yes`, `legs_refused` (and
   `gate_repairs`) filled, the refusal reason in `notes`, timing columns `not_recorded`.
   `eval/pilot_scorecard.py` reports fallbacks (count and share) and excludes them from the
   timing and quality rules; they never disappear from the report, and a fallback cannot count
   toward the six retro briefs of the week-3 set.
3. Operator: log the refusal as an incident if it recurs on the same cause; review causes weekly
   with the champions (`EFFORT_RECORDING.md`).

## 5. Wrong package shared, or a package changed after release

1. Operator or traffic: `python3 -m pipeline.release_control verify PKG --run RUN`. Changed or
   extra files fail verification; an unknown package has no matching receipt.
2. If a wrong or changed package reached the client: section 1.

## 6. Operator unavailable

Champions run steps 1–5 of `PILOT_RUNBOOK.md`; nobody takes over another person's approval
role. Runs lock per directory (`.run.lock`); never delete a lock while a process may hold it.

## 7. Known blocker found by the lifecycle rehearsal

`pipeline/quality.py` `render_coverage` cannot verify an open question linked to a bracketed
transcript timestamp such as `[00:03:41]`, so `agency approve` is unreachable for such briefs
until the check is corrected (`runs/rehearsal-lifecycle/PREPARATION.json`, `why_moved`).
Tracked as go-live precondition T-01 in `GO_LIVE_DECISIONS.md`.

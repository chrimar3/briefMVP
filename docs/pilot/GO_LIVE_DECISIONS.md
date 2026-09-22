# Go-live decision sheet

Every OWNER TO CONFIRM item in the pilot pack, in one place, with its owner, the default that
applies until it is decided, when it is needed, and its status. Deadlines are relative to the
pilot calendar, whose kickoff date is itself D-01. Sign-off of this sheet (all "before week 1"
items closed) is the precondition for any `approved` data declaration. Status as of 2026-09-23.

## Recorded owner decisions (closed)

| ID | Decision | Date, record | Effect on the pilot |
|---|---|---|---|
| R-1 | Model routing: haiku for classify/fidelity, sonnet for extraction plus an independent verify-extract, sonnet for synthesis/render/creative; routing changes are human decisions | 2026-07-30, `CLAUDE.md` Model routing | Usage under this routing is unmeasured end to end (T-02). |
| R-2 | Creative can proceed to delivery after explicit human approval | 2026-09-20, `docs/OPERATING_DECISIONS.md` | `CREATIVE_DELIVERY.md`; no automatic sending. |
| R-3 | Live re-baseline authorized: 3 graded rolls on each of northlight_01 and voreas_02 under current routing | 2026-09-22 (1), same record | Produces T-02's numbers; runs in the next round. |
| R-4 | One canonical walkthrough (`WALKTHROUGH.html`) | 2026-09-22 (2), same record | Front-door material only. |
| R-5 | Creative delivery is in the pilot from week 1, under separation of duties | 2026-09-22 (3), same record | `ROLES.md`; `SCORECARD.md` §3 creative measures. |
| R-6 | Explicit data declaration is part of the input contract | 2026-09-22 (4), same record | Implemented: `pipeline/data_policy.py`, runner exit 6, intake `--data-class`. It adds the control; it grants no approval. |

## Open decisions

| ID | Decision | Owner | Default until decided | Needed by | Status |
|---|---|---|---|---|---|
| D-01 | Name the sponsor, management contact, operator, two champions, two account leads, bilingual reviewer, traffic reviewer, creative lead (each with a backup) and the data-protection lead; set the kickoff date | Sponsor with agency management | No pilot | Before week 1 | Open |
| D-02 | Account: A workspace seats, B API account, C hybrid (`OPERATING_TERMS.md` §c, question 1) | Agency management with sponsor | A, plus one C4 API run if a key exists | Before week 1 | Open |
| D-03 | Written data terms for that account: DPA, zero retention, EU processing (question 2; `DATA_PROTECTION.md` §8) | Agency management | No real data until filed | Before week 1 | Open |
| D-04 | Pilot location outside the repository and who may read it (question 4) | Sponsor | None: `approved` projects are refused inside the repository anyway | Before week 1 | Open |
| D-05 | Usage window, seats, fee, or API billing (question 3) | Agency management | Size from T-02 once measured | Before week 1 | Open |
| D-06 | Does the Claude CLI bill an API account, or does option B need a transport (question 6) | Operator | Option B not available | With D-02 | Open |
| D-07 | Retention periods and the deletion step at pilot end (question 7; `DATA_PROTECTION.md` §6) | Sponsor with data-protection lead | Delete pilot inputs and outputs 30 days after the pilot report is signed, with `pipeline.retention` and a tombstone | Before week 1 | Open |
| D-08 | The S0/S1 line; tier of each candidate project; no S2/S3/regulated client among the six retro projects (question 5) | Account leads with agency management | Treat unclear cases as out of scope | Week 1 | Open |
| D-09 | Controller/processor role per data category; lawful basis per processing; whether a DPIA is required; notice wording (`DATA_PROTECTION.md` §4–5) | Data-protection lead | No real data | Before week 1 | Open |
| D-10 | Consent route for recorded kickoffs (PRD §8 Plan B) | Account leads with data-protection lead | Do not record | Week 1 | Open |
| D-11 | Incident time bounds (withdraw within 1 working hour, notify the client the same day) (`INCIDENT_RECOVERY.md`) | Sponsor | As proposed | Before week 1 | Open |
| D-12 | Effort recording purpose limitation and employee information step (`DATA_PROTECTION.md` §9) | Agency management with data-protection lead | Workflow measurement only, never individual evaluation | Before the first real record | Open |
| D-13 | Reading of PRD §7 "<30 min of attention" as the review component (`SCORECARD.md` §1) | Sponsor | `review_min` < 30, assembly and total recorded separately | End of week 1 | Open |
| D-14 | Does survival gate week-4 go-live (`SCORECARD.md` §2)? | Sponsor | Reported at end of week 3; mean > 70% at end of week 4 (PRD §7) | End of week 3 | Open |
| D-15 | Conflict-catch target | Sponsor | Reported only | End of week 3 | Open |
| D-16 | Greek register floor | Sponsor | Reported; flagged when EL survival trails EN on most briefs | End of week 3 | Open |
| D-17 | Refusal-rate target | Sponsor | Reported; set after T-02 | After T-02 | Open |
| D-18 | Critical errors: target 0 (this scorecard's proposal; PRD §7 has no critical-error measure) | Sponsor | 0 | Before week 2 | Open |
| D-19 | Downstream baselines (creative rework, client revision rounds) | Agency management | Not pilot-scored | Quarter 1 | Open |
| D-20 | Creative measures in the pilot: which of `creative_strikes`, `creative_approved`, `creative_released`, `creative_withdrawn` are gated | Sponsor with creative lead | All reported, none gated; a critical error reaching a client stops the pilot | Before week 2 | Open |
| D-21 | Where the bilingual reviewer's minutes are recorded | Operator with sponsor | Under `account_review`, so they count inside `review_min` (conservative: it can only make the target harder) | Before week 2 | Open |
| D-22 | Effect of manual fallbacks on the gate | Sponsor | Reported (count, share); excluded from timing rules; cannot fill the six-brief set | Before week 2 | Open |
| D-23 | Unit of the value claim: subscription usage window or API price (`docs/COST_MODEL.md`) | Agency management | Tokens by model | With D-02 | Open |
| D-24 | Claude CLI session persistence and telemetry settings on the pilot machine (`DATA_PROTECTION.md` §8) | Operator | Delete session files at run end | Before week 1 | Open |
| D-25 | Paste rule 4a (pilot data) into `CLAUDE.md` (`OPERATING_TERMS.md` §e) | Operator, after D-02 to D-04 | Rule 4 stands: fixtures only | Before week 1 | Open |
| D-26 | Correct the synthetic-data claims on share pages and README before any real run is shared (`OPERATING_TERMS.md` §e) | Operator | Do not share real runs | Before the first share | Open |

## Technical preconditions

| ID | Precondition | Owner | Status |
|---|---|---|---|
| T-01 | `pipeline/quality.py` `render_coverage` cannot verify open questions linked to bracketed transcript timestamps (`[00:03:41]`), so `agency approve` is unreachable for most real briefs; correct the check without loosening what it verifies | Engineering | Open (found by `runs/rehearsal-lifecycle/`) |
| T-02 | Current-routing re-baseline measured: tokens by model, wall time, retries, refusals per brief (R-3) | Operator | Open (next round) |
| T-03 | `tests/test_regression_voreas.py` passes with no `xfail` marks on artifacts regenerated under current routing (`SCORECARD.md` preconditions) | Engineering | Open: 16 xfailed on the committed voreas runs |
| T-04 | Separation of duties, attributed release and an append-only audit trail enforced by the agency and delivery commands (R-5) | Engineering | Verify present in the release used for the pilot |
| T-05 | Full agency lifecycle rehearsed end to end on synthetic material | Operator | Done: `runs/rehearsal-lifecycle/TRANSCRIPT.md` (28 steps, zero model calls) |
| T-06 | Champions trained on `PILOT_RUNBOOK.md`; one timed synthetic rehearsal each | Operator | Open (before week 4) |

### Item 1 (sheet 02)
Before: “Built as four plain-text rule files (sources, synthesis, translation, transcripts) injected verbatim into each AI step”. After: “Built around four plain-text rule files (sources, synthesis, translation, transcripts) injected verbatim into their respective client-brief agents; classification and creative-shadow use separate inline instructions”. Preserve the remainder of the sentence.

Source: Verified wrong_fact; audit_fidelity and both confirming votes.

### Item 2 (sheet 09)
Before: “every spec-shaped token must appear byte-for-byte in config/channel_specs.json (PRD DR-7)”. After: “Checks normalized resolution and aspect-ratio tokens against config/channel_specs.json; exempts ratio-shaped values with denominators 10–59; does not validate duration or file-type tokens. PRD DR-7 describes the intended policy.” Before: “the gate only checks that each spec token exists in the table, not that the row fits the deliverable.” After: “the gate checks normalized dimensions and some ratios, not durations, file types or whether the row fits the deliverable.”

Source: Verified unsupported_guarantee; audit_fidelity and both confirming votes.

### Item 3 (sheet 09)
Before: “The creative drafts stayed inside the signed-off facts and the spec table, except three things to strike and one call for the creative lead.” After: “The shadow drafts need three corrections and a creative lead’s decision.”

Source: task_creative; judges 1, 2 and 3, storyline.

### Item 4 (sheet 09)
Before: “Signed as the account lead’s was: in the run, by a named person, due before week 4 goes live.” After: “Creative approval is pending: the named creative lead records a choice and corrections before week 4. Client-brief live use does not authorize creative delivery; creative stays in shadow in v1.”

Source: task_creative; judges 1, 2 and 3, clarity.

### Item 5 (sheet 02, 07)
On 02, before: “a schema-validated edit in v1; a one-page runbook is a week-1 deliverable (PRD §8).” After: “a manual, schema-validated edit in v1; the review page does not save decisions or signatures. This walkthrough proposes the runbook before week 1; PRD §8 specifies champion training by week 4.” On 07, before: “The account lead writes each resolution into brief.json (conflicts[n].resolution, resolved_by) and the sign-off block (status, signed_by, signed_ts, edits_summary): a schema-validated edit in v1, a one-page runbook by week 1 (PRD §8).” After: “In v1, the account lead manually records decisions and approval in brief.json; the review page only displays them. This walkthrough proposes a runbook before week 1; PRD §8 specifies champion training by week 4.” Preserve the technical field names already in the ledgers.

Source: task_cmo; task_engineer; judge3 clarity and fact_fidelity; audit_fidelity soft issue.

### Item 6 (sheet 10)
Before: “Approve the four-week pilot: usage is measured in tokens, the cost of running it is not yet, and week 1 settles both.” After: “Approve a conditional four-week pilot; confirm capacity, costs and a spending ceiling before it starts.”

Source: Judges 1, 2 and 3, storyline; task_cfo.

### Item 7 (sheet 10)
In both the visible decision and ledger, before: “Validate subscription capacity: measure the plan’s usage window against roughly 15 M tokens a month before week 1 (15 M under the graded routing; higher under the 30 July routing until decision 2 re-measures it); the PRD’s API-terms assumption is superseded by the client’s subscription direction and stays unresolved.” After: “Proposed approval condition: before week 1, management and the operator estimate setup, training, subscription, maintenance and support costs; confirm subscription capacity and workspace processing, retention and contractual terms. The sponsor must approve the estimate and record a spending ceiling before spending or client-data processing begins; an unset ceiling means no start. Capacity planning starts from roughly 15 M tokens monthly under graded routing and must use the new measurement. Subscription terms remain unresolved.” Before: “Pilot effort and operating costs are still to be estimated.” After: “Pilot effort and operating costs remain unestimated; the proposed pre-week-1 financial gate is decision 3.”

Source: task_cfo; judges 1, 2 and 3, completeness.

### Item 8 (sheet 10)
Before: “Targets: question precision >80%, draft survival >70%, review <30 minutes; Greek-language quality and voluntary adoption.” After: “Weeks 2–3: two leads review three past projects each. Targets: over 80% of flagged questions judged useful; over 70% of draft text retained without edits; under 30 minutes reviewing each draft. Proposed Greek threshold: each of the six Greek drafts scores at least 4/5 for naturalness, with EL/EN edits compared. Both pilot leads must choose voluntary reuse. Proposed mandatory gate: missed targets block week-4 live use; the named sponsor records the release decision. Month-2 adoption is tracked separately.” In the ledger, replace the paragraph beginning “Targets: open-question precision above 80%” with this same text followed by “Month-2 adoption target: at least three further leads request onboarding.”

Source: task_cmo; task_cfo; judges 1, 2 and 3, clarity; judge1 completeness.

### Item 9 (sheet 10)
Before: “Stop rule, recommended: if weeks 2–3 miss the targets, week 4 does not go live. After the pilot a named sponsor signs the report; from month 2 new projects start from a draft by default.” After: “Proposed binding pilot condition: if weeks 2–3 miss any release target, week 4 does not go live. The executive sponsor named at kickoff records the week-4 release decision. Default use from month 2 requires a successful pilot report and separate sponsor approval; month-2 onboarding requests are an adoption measure, not a week-4 release criterion.”

Source: task_cfo; judge1 completeness.

### Item 10 (sheet 10)
Before: “A brief takes an account lead about two hours today (PRD A1); the target is fifty minutes (§2).” After: “The assumed baseline is two hours per brief (PRD A1); fifty minutes is an unvalidated attention target (§2): twenty assembling and thirty reviewing. The graded review was not timed; the pilot must measure both tasks.”

Source: task_cfo missing measured review time and validation of the attention target; frozen sheet 07 explicitly discloses the untimed review.

### Item 11 (sheet 10)
In the visible metric and ledger, before: “Nine model calls (four documents, one sent back once)”. After: “Nine model-agent attempts, each potentially containing multiple turns (four documents, one retried)”. Preserve the usage figures and following punctuation.

Source: judge1 fact_fidelity; clarifies the usage evidence underlying task_cfo’s capacity decision.

### Item 12 (sheet 10)
Before: “One document: about 4 minutes to classify and extract, 5:45 for a full run.” After: “One document: about 4 minutes to classify and extract; 5:45 for a full run under a demo profile with the production input gate overridden.”

Source: audit_fidelity soft issue; qualifies the timing evidence relevant to task_cfo.
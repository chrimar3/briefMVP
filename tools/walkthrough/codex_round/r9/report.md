# Round 9 (Codex gpt-6-astra) on WALKTHROUGH.html @ 3a285fde0ac5

**Verdict:** NOT stable; hard failures 2 (refuted 5); tasks failed: task_cfo; judges 3/3; agents missing: none; hash problems: none

| aspect | avg | delta vs r5 |
|---|---|---|
| concision | 7.0 | 0.67 |
| completeness | 8.0 | 0.0 |
| clarity | 7.67 | 0.0 |
| storyline | 8.0 | -0.33 |
| product_framing | 8.0 | -0.67 |
| visual_design | 8.0 | 0.33 |
| fact_fidelity | 8.0 | -0.67 |
| ux | 7.0 | -0.67 |
| finale | 7.0 | -0.67 |

## Hard failures (verified)
- [wrong_fact] sheet 02: The files are injected into their respective briefing agents, not every AI step. Classification and creative-shadow explicitly use separate inline instructions.
- [unsupported_guarantee] sheet 09: The gate does not guarantee byte-for-byte membership for every spec token. It normalizes dimensions, exempts some ratio-shaped values, and does not validate duration or file-type tokens.

## Refuted claims
- [missing_exhibit] sheet 01: 0.98 M tokens, stage one
- [quote_not_verbatim] sheet 04: Just thinking out loud — maybe a TikTok dance thing? Don’t hold me to it, δεν το έχουμε συζητήσει καν μέσα.
- [quote_not_verbatim] sheet 09: For urban professionals who’ve outgrown sugary, beach-party fizz
- [accessibility_blocker] sheet All — mobile navigation: 01 / 10 · Contents
- [broken_interaction] sheet All — swipe navigation: swipe horizontally or tap Next

## Audience tasks
- task_cmo: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: No essential information was missing for this explanation. Actual savings, operating costs and everyday reliability remain unproven, as the sheets acknowledge.
- task_cfo: passed=False; scores={'clarity': 7, 'completeness': 7, 'concision': 6}; missing: Pilot budget, spending ceiling, implementation/support effort and subscription cost; net benefit cannot be calculated. | A Greek-quality pass threshold and a clear distinction between week-4 release criteria and month-2 adoption targets. | An unequivocal mandatory stop rule and explicit approval gate for month-2 default rollout. | Measured review time and validation of the 50-minute attention target; the graded review was not timed.
- task_creative: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 
- task_engineer: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 

## Editor brief
**Hypothesis:** Restrict this pass to 12 text-only corrections on sheets 02, 07, 09 and 10 so readers can distinguish implemented checks, human approvals and proposed pilot conditions without changing exhibits or layout.
1. sheet 02: Before: “Built as four plain-text rule files (sources, synthesis, translation, transcripts) injected verbatim into each AI step”. After: “Built around four plain-text rule files (sources, synthesis, translation, transcripts) injected verbatim into their respective client-brief agents; classification and creative-shadow use separate inline instructions”. Preserve the remainder of the sentence.  _(Verified wrong_fact; audit_fidelity and both confirming votes.)_
2. sheet 09: Before: “every spec-shaped token must appear byte-for-byte in config/channel_specs.json (PRD DR-7)”. After: “Checks normalized resolution and aspect-ratio tokens against config/channel_specs.json; exempts ratio-shaped values with denominators 10–59; does not validate duration or file-type tokens. PRD DR-7 describes the intended policy.” Before: “the gate only checks that each spec token exists in   _(Verified unsupported_guarantee; audit_fidelity and both confirming votes.)_
3. sheet 09: Before: “The creative drafts stayed inside the signed-off facts and the spec table, except three things to strike and one call for the creative lead.” After: “The shadow drafts need three corrections and a creative lead’s decision.”  _(task_creative; judges 1, 2 and 3, storyline.)_
4. sheet 09: Before: “Signed as the account lead’s was: in the run, by a named person, due before week 4 goes live.” After: “Creative approval is pending: the named creative lead records a choice and corrections before week 4. Client-brief live use does not authorize creative delivery; creative stays in shadow in v1.”  _(task_creative; judges 1, 2 and 3, clarity.)_
5. sheet 02, 07: On 02, before: “a schema-validated edit in v1; a one-page runbook is a week-1 deliverable (PRD §8).” After: “a manual, schema-validated edit in v1; the review page does not save decisions or signatures. This walkthrough proposes the runbook before week 1; PRD §8 specifies champion training by week 4.” On 07, before: “The account lead writes each resolution into brief.json (conflicts[n].resolution,  _(task_cmo; task_engineer; judge3 clarity and fact_fidelity; audit_fidelity soft issue.)_
6. sheet 10: Before: “Approve the four-week pilot: usage is measured in tokens, the cost of running it is not yet, and week 1 settles both.” After: “Approve a conditional four-week pilot; confirm capacity, costs and a spending ceiling before it starts.”  _(Judges 1, 2 and 3, storyline; task_cfo.)_
7. sheet 10: In both the visible decision and ledger, before: “Validate subscription capacity: measure the plan’s usage window against roughly 15 M tokens a month before week 1 (15 M under the graded routing; higher under the 30 July routing until decision 2 re-measures it); the PRD’s API-terms assumption is superseded by the client’s subscription direction and stays unresolved.” After: “Proposed approval cond  _(task_cfo; judges 1, 2 and 3, completeness.)_
8. sheet 10: Before: “Targets: question precision >80%, draft survival >70%, review <30 minutes; Greek-language quality and voluntary adoption.” After: “Weeks 2–3: two leads review three past projects each. Targets: over 80% of flagged questions judged useful; over 70% of draft text retained without edits; under 30 minutes reviewing each draft. Proposed Greek threshold: each of the six Greek drafts scores at l  _(task_cmo; task_cfo; judges 1, 2 and 3, clarity; judge1 completeness.)_
9. sheet 10: Before: “Stop rule, recommended: if weeks 2–3 miss the targets, week 4 does not go live. After the pilot a named sponsor signs the report; from month 2 new projects start from a draft by default.” After: “Proposed binding pilot condition: if weeks 2–3 miss any release target, week 4 does not go live. The executive sponsor named at kickoff records the week-4 release decision. Default use from month  _(task_cfo; judge1 completeness.)_
10. sheet 10: Before: “A brief takes an account lead about two hours today (PRD A1); the target is fifty minutes (§2).” After: “The assumed baseline is two hours per brief (PRD A1); fifty minutes is an unvalidated attention target (§2): twenty assembling and thirty reviewing. The graded review was not timed; the pilot must measure both tasks.”  _(task_cfo missing measured review time and validation of the attention target; frozen sheet 07 explicitly discloses the u)_
11. sheet 10: In the visible metric and ledger, before: “Nine model calls (four documents, one sent back once)”. After: “Nine model-agent attempts, each potentially containing multiple turns (four documents, one retried)”. Preserve the usage figures and following punctuation.  _(judge1 fact_fidelity; clarifies the usage evidence underlying task_cfo’s capacity decision.)_
12. sheet 10: Before: “One document: about 4 minutes to classify and extract, 5:45 for a full run.” After: “One document: about 4 minutes to classify and extract; 5:45 for a full run under a demo profile with the production input gate overridden.”  _(audit_fidelity soft issue; qualifies the timing evidence relevant to task_cfo.)_
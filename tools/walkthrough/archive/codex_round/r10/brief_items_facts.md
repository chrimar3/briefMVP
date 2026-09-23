### Item 1 (sheet 06 and 08)
Before: “The readiness block is recomputed by code from config/readiness_policy.json and must match what the model wrote (exam check T2.6).” After: “The runner computes the readiness block from the brief using config/readiness_policy.json; T2.6 checks the stored block against the harness’s independent recomputation.” Before: “The readiness verdict, recomputed by code, matches the model’s”. After: “The runner’s stored readiness block matches the harness’s independent recomputation”.

Source: Verified wrong_fact hard failure; both audit votes.

### Item 2 (sheet 03 and 08)
Sheet 03 before: “The fixture also holds a sealed answer key the pipeline cannot open.” After: “The fixture also holds an answer key reserved for the harness by policy and excluded from automatic source discovery; runtime agents retain Read access to its containing directory.” Sheet 08 takeaway before: “The grader was frozen early; it is the only code that can open the sealed answer key.” After: “The grader was frozen early; harness-only answer-key use is policy, not enforced file isolation.” Insert immediately after #ch08 .takeaways: <p class="note">The answer key is excluded from automatic source discovery, but runtime agents retain Read access to its containing directory. This does not establish that any agent read it.</p> Replace #t08 text with “All 17 machine checks passed against an answer key committed before the pipeline ran.” Replace the text following the Frozen label with “Answer key committed on 24 July 2026 at 00:27:26, sixteen hours before the run started; the grader was frozen after the first tier. Harness-only use is a policy restriction.”

Source: Verified unsupported_guarantee hard failure; both audit votes; audit_fidelity timestamp issue.

### Item 3 (sheet 09)
Before: “Proposition, insight, tone and reasons to believe are the model’s; every fact cites a brief entry.” After: “AI proposes the creative direction; factual claims carry references that still require verification.” Before: “condensed from creative_brief_opus.md · 8 525 chars · every fact cites a brief entry, open question or conflict”. After: “condensed from creative_brief_opus.md · 8 525 chars · references indicate claimed provenance, not verified support”. Before: “Bracketed tags name the brief entry each fact came from; superseded positions and retracted ideas were not promoted to commitments.” After: “Bracketed tags indicate claimed provenance. The creative lead must verify support and correct the origin claim, budget conversion and mistaken dance retraction.” Before: “Creative lead: A or B, or neither?” After: “Creative lead: record A, B or neither, the three factual corrections and the health-claim decision. This approves shadow evaluation only.”

Source: task_creative; judge2 fact_fidelity; judge3 finale.

### Item 4 (sheet 09)
Before: “Clear space of one wordmark height kept free on every side of the name; ring, leaf and name sit in the central column so the 9:16 crop clips nothing”. After: “The artwork uses a yellow wind stroke, two white bubbles and the full product name. One wordmark height of clear space is required; compliance across the crops and packaging remains unverified.” Preserve the existing citation span.

Source: All three judges’ fact_fidelity findings; audit_ux.
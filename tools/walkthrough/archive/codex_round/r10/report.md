# Round 10 (Codex gpt-6-astra) on WALKTHROUGH.html @ ca5f7d8a7915

**Verdict:** NOT stable; hard failures 2 (refuted 5); tasks failed: none; judges 3/3; agents missing: none; hash problems: none

| aspect | avg | delta vs r9 |
|---|---|---|
| concision | 6.33 | -0.67 |
| completeness | 8.0 | 0.0 |
| clarity | 7.67 | 0.0 |
| storyline | 8.0 | 0.0 |
| product_framing | 8.0 | 0.0 |
| visual_design | 7.33 | -0.67 |
| fact_fidelity | 8.0 | 0.0 |
| ux | 7.0 | 0.0 |
| finale | 7.0 | 0.0 |

## Hard failures (verified)
- [wrong_fact] sheet 06 and 08 ledgers: The runner creates the readiness block. T2.6 compares it with an independent computation, not a model-authored verdict. The same runner-owned behavior exists in the original tier-2 implementation, commit d3d591b.
- [unsupported_guarantee] sheet 08: The repository establishes a harness-only policy and excludes the key from automatic source discovery. It does not establish the claimed exclusive ability to open the file: runtime agents receive Read access to its containing directory. This does not establish that any agent actually read it.

## Refuted claims
- [missing_exhibit] sheet All: 
- [quote_not_verbatim] sheet 04: Just thinking out loud — maybe a TikTok dance thing? Don’t hold me to it, δεν το έχουμε συζητήσει καν μέσα.
- [quote_not_verbatim] sheet 09: For urban professionals who’ve outgrown sugary, beach-party fizz, Meltemi Fizz turns zero-sugar refreshment into a premi
- [accessibility_blocker] sheet All, at 390 px: 01 / 10 · Contents
- [broken_interaction] sheet All: swipe horizontally or tap Next

## Audience tasks
- task_cmo: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 
- task_cfo: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: Setup, training, subscription, maintenance and support estimates and the spending ceiling remain unset; net savings cannot yet be calculated. | Full-run usage and time under the changed routing, subscription capacity and workspace terms remain unconfirmed. | The Greek-naturalness release threshold awaits sponsor confirmation before week 1. | The 120-minute baseline, 50-minute attention target, annual volume and hourly rate need validation; graded human review was not timed.
- task_creative: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 
- task_engineer: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 

## Editor brief
**Hypothesis:** Target decision clarity in the verified frozen WALKTHROUGH.html through at most 12 text, disclosure and responsive-layout changes that correct both hard failures and expose essential qualifications, without changing evidence quotations or artwork.
1. sheet 06 and 08: Before: “The readiness block is recomputed by code from config/readiness_policy.json and must match what the model wrote (exam check T2.6).” After: “The runner computes the readiness block from the brief using config/readiness_policy.json; T2.6 checks the stored block against the harness’s independent recomputation.” Before: “The readiness verdict, recomputed by code, matches the model’s”. After:   _(Verified wrong_fact hard failure; both audit votes.)_
2. sheet 03 and 08: Sheet 03 before: “The fixture also holds a sealed answer key the pipeline cannot open.” After: “The fixture also holds an answer key reserved for the harness by policy and excluded from automatic source discovery; runtime agents retain Read access to its containing directory.” Sheet 08 takeaway before: “The grader was frozen early; it is the only code that can open the sealed answer key.” After: “  _(Verified unsupported_guarantee hard failure; both audit votes; audit_fidelity timestamp issue.)_
3. sheet 09: Before: “Proposition, insight, tone and reasons to believe are the model’s; every fact cites a brief entry.” After: “AI proposes the creative direction; factual claims carry references that still require verification.” Before: “condensed from creative_brief_opus.md · 8 525 chars · every fact cites a brief entry, open question or conflict”. After: “condensed from creative_brief_opus.md · 8 525 char  _(task_creative; judge2 fact_fidelity; judge3 finale.)_
4. sheet 09: Before: “Clear space of one wordmark height kept free on every side of the name; ring, leaf and name sit in the central column so the 9:16 crop clips nothing”. After: “The artwork uses a yellow wind stroke, two white bubbles and the full product name. One wordmark height of clear space is required; compliance across the crops and packaging remains unverified.” Preserve the existing citation span.  _(All three judges’ fact_fidelity findings; audit_ux.)_
5. sheet 09: DOM change within #ch09 .brief: wrap the consecutive nodes from the h4 numbered “2” through the paragraph following the h4 numbered “3–6” in a closed <details class="ledger"><summary><span>Creative rationale — hypothesis and supporting detail</span></summary>…</details>. Wrap the consecutive nodes from the h4 numbered “8” through the existing “Still open” details in a second closed <details class=  _(judge1, judge2 and judge3 concision.)_
6. sheet 09, phone: Append after the existing responsive rules: @media (max-width: 1000px) { #ch09 > .margin { order: 0; } #ch09 > .body { order: 1; } } This places the existing three-corrections warning and shadow-mode notice before both artwork and draft.  _(All three judges’ ux findings.)_
7. sheet All, phone: Append after the existing responsive rules: @media (max-width: 700px) { .ruler .tick { display: none; } .ruler { overflow: visible; min-width: 0; } .ruler .fol { flex: 1 1 100%; width: 100%; min-width: 0; margin-right: 0; white-space: normal; overflow-wrap: anywhere; } } Preserve Back, Next, Contents and existing keyboard behavior.  _(All three judges’ ux findings; audit_ux and audit_fidelity identify outstanding browser verification.)_
8. sheet 01: Remove #ch01 .takeaways; its three points remain represented by the title, evidence tiles and ledger. Append CSS: @media (min-width: 1001px) { #ch01 .legend { display: flex; flex-wrap: wrap; gap: 8px 24px; } #ch01 .legend li { font-size: 16px; line-height: 24px; padding: 6px 0; } #ch01 .legend .g { margin-top: 4px; } } Keep the existing stacked phone treatment.  _(judge2 and judge3 concision; all three judges’ visual_design findings.)_
9. sheet 02: Move the existing p.principles unchanged from the ledger to immediately after the Stage 2 ol.flow. Move the entire “The thin layer” marginalia paragraph unchanged into the ledger. In its former margin position insert: <p class="marginalia"><span class="lbl">Operating handover</span>The specialist runs the pilot; two trained brief champions operate it by week 4 using a one-page runbook.</p> Replace  _(All three judges’ product_framing findings; judge3 clarity; task_cmo.)_
10. sheet 06: Before #t06: “One master record holds 25 cited entries, 3 conflicts and 10 questions; both documents come from it, with Greek reviewed by a person.” After: “One cited master record produces both briefs; people review the Greek and resolve the questions.” Preserve the counts in the synthesis ledger and readiness evidence.  _(All three judges’ storyline or clarity findings.)_
11. sheet 10: Replace the contents of #ch10 .decisions > li:first-child > .sub-list with: <li>Release targets: &gt;80% useful questions; &gt;70% text retained; &lt;30 minutes reviewing each draft; both leads choose reuse.</li><li>Before week 1: sponsor confirms Greek-naturalness and conflict-catch thresholds. Missed targets block week-4 live use.</li> Preserve the full existing protocol in .decision-record. App  _(All three judges’ concision; judge1 and judge3 completeness.)_
12. sheet 10: Remove the complete p.note immediately before p.lastline, beginning “The budget stays «κάπου στα ογδόντα»” and ending with the transcript/check X3 citation. Preserve the budget evidence and creative correction on sheets 05, 07 and 09.  _(All three judges’ storyline findings.)_
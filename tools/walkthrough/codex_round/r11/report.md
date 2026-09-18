# Round 11 (Codex gpt-6-astra) on WALKTHROUGH_v2.html @ 51705b8f145b

**Verdict:** NOT stable; hard failures 6 (refuted 2); tasks failed: none; judges 3/3; agents missing: none; hash problems: none

| aspect | avg | delta vs r10 |
|---|---|---|
| concision | 6.67 | 0.34 |
| completeness | 8.0 | 0.0 |
| clarity | 8.0 | 0.33 |
| storyline | 8.0 | 0.0 |
| product_framing | 8.0 | 0.0 |
| visual_design | 7.33 | 0.0 |
| fact_fidelity | 9.0 | 1.0 |
| ux | 8.0 | 1.0 |
| finale | 7.0 | 0.0 |

## Hard failures (verified)
- [wrong_fact] sheet 07: The model writes the signoff field. The safeguard is validation of its draft status, not field-level write protection. Describe the actual validation rather than claiming the field is unwritable.
- [missing_exhibit] sheet Document-wide: The required historical review-scope exhibit is missing. It should be identified as prior-review provenance, separately from this candidate's digest.
- [missing_exhibit] sheet Document-wide: The required constraints record is absent. This finding concerns its omission, not a claim that the candidate exceeds the numerical limits.
- [missing_exhibit] sheet Document-wide: The required browser-acceptance conditions and rendering-certification limitation are missing.
- [broken_interaction] sheet All: Only endpoint displacement is checked. Executing the extracted handlers with start (300,400), intermediate vertical movement (290,200), and release (200,380) triggers Next. Vertical movement or scrolling never invalidates the gesture. Cancel swipe eligibility once vertical movement exceeds a thresho
- [accessibility_blocker] sheet 10: On sheet 10, the accessible name omits the visible label “Next,” obstructing speech activation by that label. Include “Next” in the accessible name, or change both visible and accessible labels to matching return wording.

## Refuted claims
- [quote_not_verbatim] sheet 04: Just thinking out loud — maybe a TikTok dance thing? Don’t hold me to it, δεν το έχουμε συζητήσει καν μέσα.
- [quote_not_verbatim] sheet 09: For urban professionals who’ve outgrown sugary, beach-party fizz, Meltemi Fizz turns zero-sugar refreshment into a premi

## Audience tasks
- task_cmo: passed=True; scores={'clarity': 7, 'completeness': 9, 'concision': 6}; missing: No essential information was missing for this explanation. Actual savings, total operating cost and the Greek-quality release threshold remain explicitly unproven or unresolved.
- task_cfo: passed=True; scores={'clarity': 8, 'completeness': 8, 'concision': 6}; missing: Actual setup, training, subscription, maintenance and support costs; approved spending ceiling; confirmed subscription capacity and workspace terms. These are explicitly deferred prerequisites, so net savings cannot yet be calculated. | A full-run usage/time baseline under the changed routing, measured assembly/review effort, an agreed attention-time definition and a Greek release threshold.
- task_creative: passed=True; scores={'clarity': 8, 'completeness': 8, 'concision': 7}; missing: The creative reviewer and decision date remain unassigned. | Full creative drafts and further spec rows are not embedded, limiting independent verification. | A complete creative-delivery authorization process beyond v1 is not specified.
- task_engineer: passed=True; scores={'clarity': 8, 'completeness': 9, 'concision': 7}; missing: 

## Editor brief
**Hypothesis:** Target decision-readiness in the verified frozen candidate (SHA-256 51705b8f145b8758dec1fb7bd1a8ad6442cf514a421a6555a3f58d27239f006b) through at most 12 localized changes: correct all six hard failures, then clarify operating responsibilities, navigation and the pilot close without changing evidence quotations or adding sheets.
1. sheet 02, 07: Replace every field-write-protection claim. Sheet 07 before: “Nothing moves past the draft without an account lead. The machine cannot sign; the sign-off field is not even writable by a model.” After: “The model writes signoff.status as draft; synthesis validation rejects any other status. The creative stage requires signed_off, which the account lead records manually.” Ledger before: “A model nev  _(Verified wrong_fact; both fidelity votes; task_engineer. Supplied evidence: synthesize.md:14–16 and stages.py:351–352.)_
2. sheet 01: Before: no historical review-scope exhibit. After: append this paragraph inside #ledger-01: “Prior-review provenance — Scope: only the frozen WALKTHROUGH.html with SHA-256 ca5f7d8a791515ab108c3d98e17269a29438e69bd2133fd7acf32a25d08e0d8b was reviewed; no files edited. This records the earlier review’s scope, not the identity of WALKTHROUGH_v2.html.”  _(Verified missing_exhibit; both fidelity votes; supplied audit_fidelity.md regression item 1.)_
3. sheet 01: Before: no retained-constraints exhibit. After: append this paragraph inside #ledger-01: “Retained constraints — At most ten sheets; blockquotes and mark.cited unchanged; zero external resources; tokens as the usage figure; budget retained in words; shadow-mode labels preserved; action titles at most 24 words; takeaways at most 20 words; at most 650 visible words per sheet, except 750 on sheet 09;  _(Verified missing_exhibit; both fidelity votes; supplied audit_fidelity.md regression item 2 and user constraints.)_
4. sheet 01: Before: no browser-acceptance exhibit. After: append this paragraph inside #ledger-01: “Acceptance must include actual desktop and 320-, 390- and 560-pixel browser checks for navigation, exam-row separation, warning order, text bounds, artwork labels and keyboard/touch behavior; this review does not certify rendering.” Keep this limitation explicit until actual browser checks succeed.  _(Verified missing_exhibit; both fidelity votes; audit_ux reports unsuccessful browser launches.)_
5. sheet All: JS: retain the existing touchstart exclusions and endpoint thresholds. Immediately after the touchstart listener add: document.addEventListener('touchmove',function(e){if(tx===null)return;if(e.touches.length!==1||Math.abs(e.touches[0].clientY-ty)>40)tx=ty=null;},{passive:true}); In the existing scroll listener, insert tx=ty=null; before clearTimeout(timer). This permanently cancels eligibility for  _(Verified broken_interaction; both UX votes.)_
6. sheet 10 / navigation: JS inside paint(): before nextTitle.textContent, insert next.querySelector('span').textContent=cur===10?'Start again':'Next'; Replace next.setAttribute('aria-label',cur===10?'Return to sheet 01':'Next sheet: '+CH[cur].t); with next.setAttribute('aria-label',cur===10?'Start again: return to sheet 01':'Next sheet: '+CH[cur].t); Verify the visible and accessible labels match on desktop and phones, an  _(Verified accessibility_blocker; both UX votes; judge2 UX.)_
7. sheet All / read-all navigation: Before: scrolling only saves position, so cur remains tied to the last selected sheet. After: add this JS listener inside the existing closure: var sheetFrame=0;window.addEventListener('scroll',function(){if(!allMode||printing||restoring||!contents.hidden||sheetFrame)return;sheetFrame=requestAnimationFrame(function(){sheetFrame=0;if(!allMode||printing||restoring||!contents.hidden)return;var line=M  _(judge1, judge2 and judge3 UX.)_
8. sheet 09: Before: “Six blocking open items from the brief:” and its visible six-item list. After: one paragraph, “Before production or delivery, resolve ingredient claims and delivery scope; shadow exploration may continue. <a href="#ledger-12">Review the six open items.</a>” Retain all six detailed entries in #ledger-12. Replace its summary “Still open — six items a creative team cannot start without, and   _(All three judges on concision; task_creative; judge1 clarity and judge3 finale.)_
9. sheet 10: Replace only #ch10 .decisions with three compact list items, retaining the detailed protocol, targets, cost categories and citations in #ledger-14: (1) “Authorize a conditional four-week pilot or defer. Owner: sponsor, named at kickoff. Due: before week 1. Release: week-4 live use requires every agreed quality, time and voluntary-reuse target; the sponsor records the decision. <a href="#ledger-14"  _(All three judges on concision and finale/storyline; task_creative on ownership.)_
10. sheet 10: Before: #ledger-14 pilot protocol proceeds directly to “Weeks 2–3: two leads review three past projects each.” After: insert immediately before that sentence: “Week 1: confirm that full transcripts are available for the historical projects. If unavailable, collect prospective kickoff transcripts while retrospective work uses the remaining sources.”  _(All three judges on completeness; supplied PRD §8 contingency.)_
11. sheet 02, 07: Sheet 02 before: “Six AI steps, two plain-code steps, one person. Static review pages support command-line operation; the signature controls the handover.” After: “The graded-run diagram groups six AI steps, two code steps and human sign-off. Current extraction also has a verifier agent. An AI specialist runs the tool; the account lead reviews and records approval before shadow creative begins.” S  _(task_cmo and task_engineer; judge1 product framing; judge2 and judge3 manual-operation and principles requests.)_
12. sheet 01: CSS before: .legend .red{color:var(--ink)} After: .legend .red{color:var(--red)}  _(judge1 visual design and judge2 clarity.)_
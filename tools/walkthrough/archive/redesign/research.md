Research for the Brief Builder walkthrough — 18 September 2026

Read-only baseline: WALKTHROUGH.html, all ten sheets, CSS and scripts; HANDOFF_WALKTHROUGH.md; codex_review.md; codex_priorities.md; checks.py; the specified round-8 journal; PRD §§7–9. HTML SHA-256: `3a285fde0ac54ae9a469b30fdae8968be18e467a4bf05d5ea81e075eacf5188d`. Findings below distinguish current source observations from historical audience findings. No browser-rendered accessibility certification was performed. All web sources below were accessed through live search/open on **2026-09-18**; that access date applies to every linked citation in both files.

1. Consulting storyline

Minto organizes supporting ideas beneath one governing point; her SCQ framework identifies the reader’s question. For this document: situation = fragmented bilingual briefing; complication = contradictory inputs and uncertain operating capacity; question = whether to pilot; answer = a conditional four-week experiment. Show the answer first, then its evidence. SCQA is a reasoning structure, not four compulsory introductory sheets. [S1: Barbara Minto, concept and SCQ](https://www.barbaraminto.com/).

Duarte’s document guidance gives each page one core point and uses its title to test supporting material. Write conclusion-bearing action titles rather than topic labels; attach one principal exhibit and its implication. A walkthrough meant to survive forwarding needs enough explanatory text to stand alone. Duarte distinguishes this reading document from projected slides; our face/ledger design is an adaptation to the single-file constraint, not Duarte’s prescribed format. [S2: Duarte, document design](https://www.duarte.com/blog/the-art-of-document-design-tips-and-tricks/); [S3: Duarte, slides versus Slidedocs](https://www.duarte.com/blog/the-slides-you-deliver-versus-the-slidedoc-you-leave-behind/).

Already present: sheet 01 starts with “Approve a four-week pilot, with live use in week 4 conditional on the retrospective results.” Sheets 05 and 07 form an evidence/decision pair. Native ledgers attach technical support without separate appendices.

Departure: sheet 09’s “The creative drafts stayed inside the signed-off facts and the spec table, except three things to strike and one call for the creative lead” leads with reassurance that its own exhibit qualifies. Replace with the conclusion that editorial review remains necessary. Sheet 02’s margin, “Four plain-text rule files … seven agents and about 2 500 non-blank lines,” competes with the operating story; move it to the ledger. [S1–S3]

2. Executive and board pre-reads

AICD’s sample starts with paper type, sponsor, presenter, draft resolution and a four-to-five-line summary. It separates recommendation, alternatives, financial implications, risks and responsibility. These are decision fields, not optional supporting trivia. [S4: AICD, annotated board paper](https://www.aicd.com.au/content/dam/aicd/pdf/tools-resources/director-resources/board%20papers_may%202020_final_%20appendix_an%20annotated%20sample%20board%20paper.pdf).

NIAO recommends concise strategic papers, suggests four pages, and recommends circulation at least a week before the meeting. This is guidance, not a universal length standard. Preserve ten evidence sheets, with a short executive route 01→02→10 and optional exhibits; do not pretend ten scrolling sheets equal a four-page board paper. [S5: NIAO, Board Effectiveness, §§4.10–4.14 and Annex 5](https://www.niauditoffice.gov.uk/files/niauditoffice/media-files/Board%20Effectiveness-%20A%20Good%20Practice%20Guide.pdf).

Already present: sheet 10 has exactly three owner-labelled decisions, visible Limits, and “before running and support costs, which are not yet estimated.” The annual capacity case is an assumption-based target rather than measured savings.

Departure: sheet 01’s ask omits the cost/terms gap disclosed on 10. Neither face compares proceeding conditionally with deferral. Add those alternatives and explicitly leave the spending ceiling, plan, training and operator effort unpriced; assign resolution to the sponsor/management before commitment. This is the design recommendation, not an invented approved policy. Do not manufacture a range or payback.

Sheet 07 attributes “target: under 30 minutes of account-lead attention” to PRD §7 in a review-time sentence; PRD §7 measures time-to-first-draft attention. Sheet 10 calls it “review <30 minutes.” Expose this definition mismatch for sponsor resolution while preserving the stated targets and the separate 50-minute total-attention assumption. [S4–S5]

3. Presentation and information design

NN/g describes hierarchy through a small set of type sizes, aligned grids, shorter lines and deliberate colour. GOV.UK advocates single-column beginnings and tables for row/column comparison, with captions and header semantics. Tables suit gate results, model usage and channel specs; prose suits the decision’s rationale. [S6: NN/g, Good Visual Design](https://www.nngroup.com/articles/good-visual-design/); [S7: GOV.UK, layout](https://design-system.service.gov.uk/styles/layout/); [S8: GOV.UK, tables](https://design-system.service.gov.uk/components/table/).

Tufte’s data-ink principle favours marks that communicate evidence over decoration. Treat it as a design heuristic, not a numerical acceptance threshold: retain rules that help track rows and provenance. [S9: CMU, Statistical Graphics, lecture on Tufte’s data-ink ratio](https://www.stat.cmu.edu/~vventura/class/s07-315/lectures/week3-lec1.pdf). For this page, retain verbatim receipt, source/location, then separately labelled gloss; put full paths and run metadata in ledgers. A citation identifies provenance, not proof that the claim follows.

Already present: bounded prose measure (`62ch`), tabular numerals, source captions, source-language tags and a restrained document palette. Gate-style counts of default-visible words are 326/316/310/277/327/303/332/180/750/347; sheet 09 has no remaining allowance.

Departures: sheets 01–10 combine large legends, stamps, marginalia and repeated takeaways. Remove repetition before shrinking text. Sheet 10’s ledger puts “598 743 tokens” beneath “time”; separate units. Sheet 09’s ledger says “ring, leaf and name” although the current SVG uses a wind stroke and bubbles; correct the description without altering art. Its blue/yellow swatch elements sit outside the artwork; remove coloured UI swatches under the fixed palette rule. [S6–S9]

4. HTML accessibility

WCAG 2.2 AA requires normal-text contrast 4.5:1, large-text contrast 3:1, applicable non-text contrast 3:1, keyboard operation, visible focus, focus not entirely obscured, meaningful structure and reflow at 320 CSS pixels, with limited exceptions for intrinsically two-dimensional material. Colour must not carry meaning alone. Reduced-motion support is additionally required by this brief; do not mislabel all motion suppression as AA. [S10: W3C, WCAG 2.2](https://www.w3.org/TR/WCAG22/).

The modal pattern calls for contained focus, Escape and return focus. Minimum target size is 24×24 CSS pixels with specified exceptions; 44×44 is our more generous control target. Single-character shortcuts need disabling, remapping or focus restriction. [S11: W3C, modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/); [S12: W3C, target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html); [S13: W3C, character shortcuts](https://www.w3.org/WAI/WCAG22/Understanding/character-key-shortcuts.html).

Already present: focus outlines, reduced-motion CSS, modal focus trapping/inert handling, named Next controls, language tags, labelled artwork and phone-specific exam rows. Computed palette contrast against paper: ink 15.48:1, pencil 5.96:1, red 5.23:1.

Departure across sheets: `else if (e.key === 'c' || e.key === 'C')` enables a global character shortcut without an off/remap control. `.desk` is a div with no main landmark or skip link. Sheet 08’s phone CSS hides `.exam .id`, losing T1/T2/T3 identifiers. Muted rule colour measures only 1.42:1 against paper: acceptable decoration, unsuitable as an essential control boundary. Red on pending creative approval and sheet-10 decision numbers also contradicts the stricter project meaning “a person decided.” [S10–S13]

5. Single-file engineering

WHATWG defines native disclosure through `details`/`summary`; this supplies a baseline without a widget library. MDN documents print media and before/after-print events, and History API state management. History navigation must respond to Back/Forward, reload and direct links, not just update a visible counter. [S14: WHATWG, details](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-details-element); [S15: MDN, printing](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing); [S16: MDN, History API](https://developer.mozilla.org/en-US/docs/Web/API/History_API/Working_with_the_History_API).

Use inline CSS/classic JavaScript, local font fallbacks and embedded imagery; no fetch, modules, service worker or runtime installation is needed. Data URLs package image bytes into the document; base64 enlarges the payload by roughly one third, so compress once and avoid duplicate raster copies. Explicit image dimensions reserve layout space. Lazy loading cannot reduce bytes already embedded in the HTML. [S17: MDN, data URLs](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/data); [S18: MDN, img](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/img); [S19: MDN, font-family](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/font-family).

Already present: approximately 220 KB, inline shared SVG, one dimensioned embedded JPEG, local font stacks, reduced-motion handling, and print listeners that open ledgers and restore state.

Departures: navigation uses `#01` while section IDs use `ch01`; without JavaScript the fragment has no target. The early script adds `js` before initialization, so later failure can hide every sheet. Sheet 06’s “Full documents in the repository” links and sheet 09’s further-section link require companion files. Essential extracts must be embedded; render repository paths as provenance, not functioning offline promises. Printed expanded ledgers need pagination checks, including without script. [S14–S19]

6. AI pilots and stakeholder trust

NIST requires documented context, oversight, limits, evaluation conditions and costs, including costs of failure. Google PAIR recommends calibrated trust: explain capabilities and boundaries using information useful to the user rather than technical detail for its own sake. [S20: NIST, AI RMF Core, MAP 2–3 and MEASURE 2](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/); [S21: Google PAIR, Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/).

Here “shadow mode” must say: signed-off input, creative lead evaluates output, nothing delivered or released; week-four client-brief use does not itself authorize creative delivery. Distinguish synthetic evaluation, later routing validation and future pilot targets. Keep failures beside the success claim and conditions beside the ask. These are applications of the sources to this pilot, not universal definitions imposed by them.

Already present: sheet 08 scopes “17/17” to one synthetic project; sheet 10 shows refusals and the second fixture; sheet 02 identifies assumed data terms and current commercial uncertainty.

Departure: sheet 03’s “Without the RFP the run stops with a request; a small model then classifies” can imply classification follows a stop. Separate the sufficient-input and missing-RFP paths. Sheet 08’s “Every check is a yes or a no; none is an opinion” needs the visible qualification that citation tags do not establish semantic support. Sheet 04’s verifier belongs in a separate dated comparison table, retaining “not in the graded totals.” [S20–S21]

7. Creative and brand presentation

Design Council treats prototypes as tools for exploration, testing and learning. IBM Carbon’s AI-label guidance identifies generated content and connects identification with explanation. Together these support explicit draft status and provenance near the artefact; neither establishes a universal typographic mock-up standard. The exact MOCK-UP/SHADOW MODE labels are project requirements. [S22: Design Council, Framework for Innovation](https://www.designcouncil.org.uk/resources/framework-for-innovation/); [S23: IBM Carbon, AI label](https://carbondesignsystem.com/components/ai-label/usage/).

Use a draft comparison for the creative choice, a table for exact deliverable/spec/owner/status relationships, and separate recorded facts from proposed psychology. Preserve both model IDs, the undecided signature line and the traffic-table caveat. GOV.UK’s comparison guidance also applies to specs. [S8]

Already present: sheet 09 labels “creative hypothesis, not audience research,” marks the invented budget, names six blockers and states that packaging was generated for the walkthrough. The artwork slug states “the pipeline emits text only.”

Departure: the artwork precedes the draft choice, while the three corrections occupy a margin that moves after the body on phones. Lead with A/B, corrections and blockers; follow with the labelled illustration. Keep tone/reasons-to-believe visible, avoiding the prior regression. [S22–S23]

Audience evidence changes the priorities. Round 8 passed CMO, CFO and engineer tasks but failed the creative-director task; auditors/judges failed to complete, so it is not an audited pass. Current HTML has since restored sections 3–6, displayed Draft A’s offending sentence, explained tokens/data terms and named resolution fields. Still unresolved: priced operating effort, plan/capacity, time-metric definition, creative owner/date and operational handover detail. Preserve unknowns with owners; do not invent missing facts or adopt speculative monthly forecasts from reviewer suggestions.

# Open items to apply to WALKTHROUGH.html (from round-6 judges, reconciled)

Rules that must hold after every edit (the check script enforces most of them):
- at most 10 sheets; folios, CH array and contents in sync; ids unique
- never change the text of any <blockquote> or <mark class="cited"> (verbatim clippings, machine-checked)
- zero external dependencies; system fonts only
- palette: paper #F1F2EC, ink #1A1A18, pencil #5A5D55, red #C8102E only where a person decided; #1B4F8A / #F5C518 only inside the sheet-09 key visual
- tokens are the visible usage figure; dollars only in the sheet-10 ledger footnote
- action titles ≤ 24 words; takeaway points ≤ 20 words
- numbers use U+2009 (thin space) as the thousands separator, e.g. 598 743
- do not invent facts; every number must trace to runs/tier3, runs/routing-validate-01, docs/ or fixtures/

## A. Fact corrections
1. Sheet 10, numbers item 1: "Eight model calls" → "Nine model calls (four documents, one sent back once)". The graded stage one is 7 Haiku sessions (classify, fidelity, four extracts, one repair) + 2 Sonnet.
2. Sheet 01, tile 2: "83% of it context the model had already been sent" → "83% context rather than new writing: 56% re-read from cache, 27% written to it".
3. Sheet 01 ledger: rename the "25 min unattended" row to "33 min of stage time · 25.2 min continuous capture"; change the usage parenthetical to "(cache reads 56% · cache writes 27% · output 16% · fresh input 0.3%)"; drop "· €38–40 labour" from the tokens row.
4. Sheet 10, closing note: check X3 covers the brief object and both renders, and the shadow Draft A (runs/tier3/creative/creative_brief_sonnet.md line 64) did print "(€80–85k)". Rewrite: "The budget is still «κάπου στα ογδόντα» in the brief and both documents: no signed brief and no render turns it into a total. Shadow Draft A did, which is exactly what a creative lead strikes."
5. Sheet 09, A/B note: "Both drafts withheld the natural-ingredients claim" → "Both drafts flagged the natural-ingredients claim as unusable until the ingredient list arrives; only the key visual withholds it".
6. Sheet 09 title → "The creative drafts stayed inside the signed-off facts and the spec table, except two things for the creative lead to strike." Margin note "One word to strike" → "Two things to strike": Draft B's "Greek-made" (an origin claim no source supports) and Draft A's "(€80–85k)" (a budget total the brief never states). Add: Draft B's "nothing to feel guilty about" runs close to the ban on health claims; the creative lead's call.
7. Sheet 04 ledger, the "4b verify-extract" row: prefix the record cell with "not in the graded totals —".

## B. Concision
8. Sheet 03: delete the "What kind of job it is" heading and its paragraph; replace the third takeaway with "Without the RFP the run stops with a request; a small model then classifies the job: advertising creative, high confidence, S1." (20 words). The classification details stay in the ledger.
9. Sheet 04: drop the first fidelity clipping («μπραντ αγουέρνες»), keep the «κι βίζουαλ» one; merge the three ledger-foot paragraphs into one note of about 60 words.
10. Sheet 10: delete the note "The number to quote today: …"; move the limit "The PRD's two named risks…" into the sheet's ledger foot.
11. Sheet 09: replace the third takeaway with "Six open items still block a creative team; three facts are settled in red." (illustration/shadow status is already in the slug and the ledger).
12. Sheet 07: remove the remaining audience clipping (keep the three red resolution lines and the sign-off); change the first takeaway to "The same three contradictions from sheet 05, now each with a person's decision." Move the provenance paragraph ("On provenance: …Eleni…") into the sheet's ledger foot.
13. Sheet 05: delete the third takeaway (the marginalia says it); add a body note after the pairs: "The same three lines return on sheet 07 with a person's writing in them."
14. Sheet 01: replace the run-in .marks paragraph with a three-row <ul class="legend"> (pencil = AI drafts · rule = code checks · red pen = people decide, using the existing #g-pencil / #g-rule / #g-nib glyphs) placed below the tiles, plus one .howto line for keys and swipe.

## C. Clarity
15. Sheet 06 marginalia: delete the raw mono string (fields_with_evidence … verdict ready_for_review); keep the English sentence. Gloss "OOH (out-of-home: posters, billboards)".
16. Sheet 02: gloss DPA on first use ("under a data-processing agreement (DPA)"); marginalia "about 2 500 non-blank lines across the eight pipeline modules in the ledger below".
17. Sheet 08: add one line under the takeaways: "T1 = the evidence layer, T2 = the brief and both documents, T3 = the seeded traps, X = traps that must stay out."
18. Sheet 06 title → "One master record holds 25 cited entries, 3 conflicts and 10 questions; both documents are written from it, and a person still reads the Greek." (23 words) and the takeaway "There is no translation step, only two renderings of one object, so the languages cannot drift." → "No translation step: two renderings of one master record; whether the Greek reads like agency Greek is a pilot metric." (consistent with item 36).
19. Sheet 09: "Recorded the way the account lead's was: in the run, by a named person." → "This line is signed the same way the account lead's was: in the run, by a named person, due before week 4 goes live."

## D. Storyline
20. Sheet 10 title → "Approve the four-week pilot, and re-baseline usage before week 1: the graded run's 1.13 million tokens are a measurement, not a price."
21. Sheet 02 title → "Nine steps, three roles: six are AI, two are plain code, and the one that releases the work is a person."
22. Sheet 01: move the <p class="ask"> recommendation above the narrative paragraph; style .ask { margin: 0 0 20px; font-size: 19px; }.
23. Sheet 10: the .sub "Evidence behind the three decisions" → "Why: the measured numbers behind decisions 2 and 3".

## E. Visual
24. Sheet 09 SVG: the MOCK-UP text → x="1280" text-anchor="middle" y="150" font-size="44" letter-spacing="10" (must stay inside the 9:16 crop, x 740–1820).
25. Sheet 09: shorten the 9:16 slug to "9:16 still frame at the TikTok in-feed spec; the lockup falls in TikTok's caption zone here, a dedicated 9:16 layout would raise it [spec: tiktok_infeed_video]".
26. CSS: .next { white-space: nowrap; }; remove the dead first ".brief { padding: 20px 16px; }" in the 1000px media block; drop "#ch09" from "#ch09 .sub, #ch10 .sub"; move the inline style on the sheet-09 swatches div into ".swatches { margin: 8px 0 12px; }"; ".brief { margin: 56px auto 0; }".

## F. UX
27. Swipe: record touchstart Y and require Math.abs(dy) < 40; ignore touches that start inside .ledger-wrap or .ruler.
28. In render(): next.setAttribute('aria-label', 'Next sheet: ' + title) and mark the arrow span aria-hidden="true"; keep "· Contents" in the folio text on phones (append the sheet title after it) and give the folio aria-label="Open contents".
29. Phones: .ruler .tick min-width 32px.
30. Change every <p class="sub"> to <h2 class="sub"> (same styling; screen-reader navigation).
31. Soften the offline marker text to " (opens from the repository folder)".

## G. Finale
32. Sheet 09: wrap "Greek-made" in the .smp proposition in <mark class="flag">.
33. Sheet 09 ledger callouts: add the two hard no-gos the artwork respects: no health or weight-loss claim, no competitor comparison.

## H. From the Codex review (codex_review.md), ranked by leverage — apply all
34. Word cut toward a presentation layer: aim for at most ~350 default-visible words per sheet (ledgers and <details> excluded), more allowed on sheet 09 for the creative specimen. Move detail into each sheet's ledger rather than deleting facts the other items require. Keep the takeaways (three short points) and the evidence object on every sheet.
35. Sheet 10, the labour item: replace "about €5–6k a year returned at 15 briefs a month, which funds the pilot" with a shown calculation labelled as assumptions: "Target: about 210 account-lead hours a year, worth €4.0–4.2k before operating costs — (120 − 50) minutes saved per brief × 180 briefs a year × €19–20 an hour; baseline, volume and rate are PRD assumptions A1, A2, A4, validated in week 1." Replace "which funds the pilot" with "pilot effort and operating costs are still to be estimated". Add to the sheet-10 ledger foot: "docs/COST_MODEL.md §3 quotes ~€5–6k a year; the PRD's own assumptions give ~€4.0–4.2k, the figure used here."
36. Sheets 01, 02, 06, 08: replace "languages cannot drift" / "never translated" claims with "both documents are written from one master record; whether the Greek reads like agency Greek still needs a person's review" (PRD §7 names Greek register as a pilot metric). Replace universal guarantees ("every contradiction", "every claim") with statements about this run ("every contradiction seeded in this project"). Caption 17/17 as "passes the 17 defined checks on one synthetic project".
37. Sheet 09: label the core insight "creative hypothesis, not audience research"; add beside the spec table "demo spec table: values are a pilot stub and need the traffic team's confirmation before delivery" (config/channel_specs.json _stub_notice); note that Draft B calls the TikTok dance "retracted" when the transcript shows it was speculative (the retracted idea was the metro posters) — a third thing for the creative lead to strike; keep the six blocking open items visible next to the A/B question (they may be a compact list, not collapsed).
38. Sheets 01 and 10, one consistent ask: "Approve a four-week pilot, with live use in week 4 conditional on the retrospective results." Replace decision 3 (subscription vs API) with "Validate subscription capacity: measure the plan's usage window against roughly 15 M tokens a month before week 1; the PRD's API-terms assumption is superseded by the client's subscription direction and stays unresolved." Add Greek-language quality and voluntary adoption (PRD §7) to the pilot targets in decision 1.
39. Sheets 02 and 07: replace "no UI" with "static review pages and command-line operation"; describe brief_review.html as a review view (it shows resolutions and the signature already recorded in the brief object, offers a language toggle and copyable questions); state that the account lead records resolutions and the signature in the brief object itself, and that the pilot runbook covers how.
40. CSS: add `.clips { grid-template-columns: 1fr; }` inside the 1000px media block (phones); keep an accessible "Next sheet: <title>" label on #next when its visible text is hidden (item 28).
41. SVG and CSS: remove every `stroke-opacity` from #kv-art (use thinner solid white tails instead, e.g. half the stroke-width, so only the three colours composite); scope the decision counter to `.decisions > li` (`.decisions > li { counter-increment: d }` and `.decisions > li::before`) and make sure nested `.sub-list li` neither increments nor shows a number.
42. Sheet 10 and the X3 wording anywhere on the page: say "no invented or resolved total" rather than "no numeric budget total anywhere" — quoting the RFP's €90,000 as a conflict position is legitimate.

# Brief Builder v2 — build notes

Built `WALKTHROUGH_v2.html`, a self-contained offline document, on 18 September 2026. **The deterministic gate and static preservation audit pass. Browser rendering and visual acceptance are incomplete: this environment prevents Chrome from launching.** No screenshots have been fabricated or described as inspected.

## Source and preservation

Read `design_spec.md`, `research.md`, the complete source HTML (including both scripts), and the unmodified `checks.py`. Decoded and visually inspected the original packaging JPEG. The final page retains its original data URI, dimensions and alt text, and the original shared `kv-art` group byte for byte.

The source initially matched the specification hash:

`3a285fde0ac54ae9a469b30fdae8968be18e467a4bf05d5ea81e075eacf5188d`

During implementation, another process changed `/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html` (observed mtime 12:23:20). This work did not write to that file or run any state-changing Git command. The subsequent source hash was:

`ca5f7d8a791515ab108c3d98e17269a29438e69bd2133fd7acf32a25d08e0d8b`

A local `source_snapshot.html` freezes that later source for reproducible builds and auditing. Its clippings, cited marks, artwork and JPEG still match those read initially. The final build retains every table data row from that snapshot. The additional source wording describing the fifty-minute attention target as unvalidated is retained.

Final payload: **206,129 bytes**, below the 300 KB investigation threshold; initial source was 219,964 bytes, frozen source 222,002 bytes. The HTML requires none of the build scripts or companion files to open.

## Changes and research standards

| Change versus the source page | Research standard answered |
|---|---|
| Ten shorter conclusion titles; full-width title and implication, then exhibit, provenance and ledgers. Repeated takeaways retained inside ledgers to avoid competing with the implication. | S1 Minto; S2–S3 Duarte: governing point and readable document hierarchy. |
| Conditional approval leads sheet 01, with executive route 01 → 02 → 10. Sheet 10 compares conditional approval with deferral; unresolved terms, capacity and costs have owners. | S4 AICD; S5 NIAO: recommendation, alternatives, financial implications and ownership. |
| New 1280px grid, paper/ink/pencil palette, system fonts, rem typography and spacing; removed decorative shadows, animations, repeated role stamps and coloured swatches. Red is reserved for recorded human decisions. | S6 NN/g; S7 GOV.UK layout; S9 data-ink guidance, plus the specification’s palette rules. |
| Receipts retain their exact markup. Adjacent glosses explicitly say “interpretation.” Table headers have scope and repeatable `thead` groups; horizontal scrolling is confined to labelled, keyboard-focusable table regions. | S8 GOV.UK tables; S9 evidence presentation; S10 WCAG. |
| Sufficient-input classification is separated from the missing-RFP STOP. The later verifier has its own dated ledger/table, explicitly outside graded totals. Usage and timing tables are separated, and nine calls are qualified as recorded attempts/sessions. | S20 NIST; S21 PAIR: calibrated evidence, uncertainty and operating boundaries. |
| Greek register and semantic-support limits remain explicit. Sheet 07 exposes the review/time-to-first-draft definition mismatch; sheet 10 retains the separate fifty-minute total-attention assumption. | S4–S5 decision completeness; S20–S21 calibrated claims. |
| Sheet 09 begins with A/B comparison, blockers, signature and corrections, followed by creative substance and then the illustrative artwork. Pending creative decisions are ink, not red. No implied delivery date. Both crops and generated packaging provenance remain adjacent. | S22 Design Council; S23 Carbon AI labels; S8 comparison tables. |
| Main landmark and skip link, labelled sheet regions, visible mobile tier IDs, focus outlines, minimum 44px controls, modal focus containment/inert background, scoped C shortcut, safer swipe exclusions and dynamic navigation clearance. | S10–S13 WCAG and WAI interaction patterns. Implemented; browser verification pending. |
| Real sheet anchors and legacy hash support; direct ledger links reveal their sheet/disclosure; read-all/expand-ledgers controls; initialize before hiding sheets; handle history without adding entries during restoration. Repo links become provenance text. | S14 WHATWG details; S16 History API; S17–S19 self-contained resources and system fonts. Implemented; browser verification pending. |
| A4/12mm print rules, continuation pages, repeatable table headers, no fixed navigation, receipt/row/art break protection, disclosure expansion/restoration and CSS-only disclosure visibility. | S15 MDN printing. Implemented; actual print pagination and no-script rendering pending. |

Research identifiers refer to the linked standards in `research.md`; no fresh claim of standards certification is made.

## Final deterministic gate

Command run after each generated-HTML change batch, without changing the checker:

```sh
python3 /Users/chrism/AI-transformation-assignment/brief-builder/tools/walkthrough/checks.py --file ./WALKTHROUGH_v2.html
```

Final output; exit **0**:

```json
{
 "sheets": 10,
 "blockquotes": 13,
 "failures": []
}
```

`audit_v2.py` additionally passes 22 static assertions, including byte-identical blockquotes/cited marks/art/JPEG, preservation of every original table data row, all 17 individual checks, exactly three decisions, three blank conflict lines, three CM resolutions, both bilingual extracts, no nested disclosures, real fragment links and no external resources. Results: `audit_results.json`; gate output: `checks_output.json`.

## Visible words

Counted with the gate’s convention: details excluded, tags stripped, entities decoded, exact sic span removed. These are not a substitute for rendered layout inspection.

| Sheet | Visible words | Cap |
|---|---:|---:|
| 01 | 233 | 650 |
| 02 | 260 | 650 |
| 03 | 290 | 650 |
| 04 | 168 | 650 |
| 05 | 294 | 650 |
| 06 | 225 | 650 |
| 07 | 246 | 650 |
| 08 | 146 | 650 |
| 09 | 631 | 750 |
| 10 | 449 | 650 |

All ten action titles are at most 24 words; every retained takeaway is at most 20.

## Regression map

F = default-visible face; L = embedded ledger.

1. **Sheet 01.** F: tiles 17/17 explicitly scoped to one synthetic project; 0.98 M stage-one tokens; 33 minutes summed stage time and 25.2 minutes continuous capture; three conflicts, none machine-resolved. Title/implication ask for a conditional four-week pilot, live use in week 4 subject to the retrospective. L: 0.53 M Haiku 4.5, 0.45 M Sonnet 5, 56% cache reads and 27% cache writes, source/timing provenance. Cost and terms uncertainty with sponsor ownership is F.
2. **Sheet 02.** F: nine steps, six AI, two plain code, one person; both stage-one flow rows, sign-off gate, stage-two row; static review pages and command-line operation. Agency workspace, data-processing agreement, EU processing and zero retention remain assumptions/requirements pending terms confirmation; S0–S1 only. Account lead records decisions/signature in the brief object; creative lead evaluates; traffic owns the pilot-stub table. AI specialist and two champions are identified. L: DPA acronym, schema fields, architecture, routing history and runbook deliverable.
3. **Sheet 03.** F: RFP, transcript, email and guidelines, with all four original clippings; four non-AI checks (RFP, two substantive sources, money, date); missing-RFP STOP; advertising creative, high confidence, S1 classification. L: exact gate verdicts, metadata, classifier citations/model usage and tier policy.
4. **Sheet 04.** F: 33 facts with verbatim receipts; two garbles flagged, never silently repaired; κι βίζουαλ clipping and fidelity note; full budget receipt beginning «είμαστε κάπου στα ογδόντα…»; transcript sent back once. L: speculative dance receipt, fidelity/extraction records, five attempts. The later verifier is a separate dated ledger/table with model, 44,695 tokens, 86 seconds, one issue and “not in the graded totals.”
5. **Sheet 05.** F: audience, budget and launch-date conflicts, both sides cited, all three resolution lines blank. Timeline explicitly shows “two of four recorded positions.” L: seven candidate fields, synthesis mechanism, sources and X3 scope.
6. **Sheet 06.** F: one master record, 25 cited entries, three conflicts, ten questions; readiness recomputed by code, 5/7 fields, 4% low confidence, ready for review. Nonempty Greek and English extracts each have two h4 sections. No translation step; Greek register is a pilot metric. L: full section inventory, example questions, nine glossary terms, model usage and semantic-support qualification.
7. **Sheet 07.** F: all three resolutions in red, each CM-initialled; Christos Maragkoudakis signed on 2026-07-24. Budget remains in the eighties excluding media; media-inclusive total is unknown. brief_review.html displays decisions recorded in brief.json. Untimed review and time-definition mismatch are visible. L: exact resolution/signoff fields, schema validation, synthetic-role provenance and sign-off gate.
8. **Sheet 08.** F: 17/17 on one synthetic project; T1 = 4, T2 = 6, T3+X = 7. Phone CSS retains identifiers and separates results into their own rows; actual rendering is unverified. L: all 17 individual checks and results; exact X3 wording “no invented or resolved total in the brief or either render”; sealed-key provenance. Citation presence/semantic support and Greek-language limits are F.
9. **Sheet 09.** F: Draft A claude-sonnet-5 and B claude-opus-4-8, exact candidate excerpts, A/B/neither question, blank creative-lead signature with owner/date unassigned. Three corrections: unsupported Greek-made; quoted Draft A total retained inside mark.flag; “floated speculatively and retracted” distinguished from the withdrawn metro idea. Separate health-claim judgement. Six blockers: ingredients, video quantities/durations/formats, key-visual quantities/uses, TikTok-first scope, KPIs, milestones. Proposition appears in Draft B comparison; creative hypothesis and condensed feel/tone/reasons-to-believe remain visible. Two-row spec table and traffic-owned pilot-stub/token-match caveat. Unchanged shared key visual in 1:1 and 9:16 MOCK-UP crops; unchanged packaging plate labelled generated for the walkthrough and undefined brief context. SHADOW MODE slug states evaluation only and pipeline text-only output. L: original proposition block, recorded sign-off checklist, remaining questions, model-run records and corrected art rationale.
10. **Sheet 10.** F: exactly three decisions, owned by sponsor, operator, management + operator. Pilot targets include >80% precision, >70% survival, <30-minute review pending definition agreement, Greek 1–5 plus EL/EN edits, voluntary adoption 2/2 plus ≥3 additional leads in month 2. 0.98 M/1.13 M tokens and nine calls qualified as recorded attempts/sessions; 598,743 vs 295,774. 210 hours/year worth €4.0–4.2k is a gross-capacity target before unknown costs. Visible Limits: subscription window not price; refusals three of ten; second fixture 15/17 then 16/17. Visible budget note «κάπου στα ογδόντα». L: (120 − 50) × 180 ÷ 60 × €19–20, A1 baseline/A2 volume/A4 rate and fifty-minute target; two leads × three past projects, week-one baseline, weeks 2–3 retrospective, conditional week 4. Dollar footnote $3.55/$2.81 versus EVIDENCE.md $4.29; COST_MODEL.md §3 versus PRD assumptions; complete timing and usage tables.

## Rendering attempt and known limitations

The specified Chrome command was attempted with `./chrome`, 1440×2400 and `screens/s01-1440.png`. It terminated with signal 6 (shell exit 134; Python return code −6), before producing an image. A diagnostic launch of the installed Chromium headless shell reported:

```text
FATAL:base/apple/mach_port_rendezvous_mac.cc:158
bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer…:
Permission denied (1100)
```

The environment’s approval policy does not permit escalation. `screens/render_log.json` records the attempted command and failure. **No desktop or phone screenshot exists; none of the twenty requested screenshots could be visually inspected.** Overlaps, clipping, whitespace, computed contrast, keyboard/history behaviour, reflow, 200% resizing, no-JS behaviour and print pagination therefore remain unverified in a browser. CSS and JavaScript implementation should not be confused with those acceptance results.

`python3 render_sheets.py` is ready for an environment that can launch Chrome. It runs the twenty requested viewport captures, supplements them with full-page captures (long sheets scroll), checks all sheets at 320/375/390/768/1280/1440px, and exercises ledger fragments, Back/Forward scroll restoration, modal focus, read-all, shortcuts, text resizing, reduced motion, no-JS and A4 printing. Those checks have **not run past browser launch**. After a successful run, every PNG and both PDFs still require visual inspection and fixes, followed by the unchanged gate.

Additional limits:

- The deterministic checker does not prove factual entailment, language quality, accessibility or visual acceptance. Static preservation assertions also do not prove them.
- Some source ledgers remain extensive to preserve the full record. They are deliberately excluded from face-word counts.
- The 9:16 illustration retains the source’s caption-zone caveat; it is a crop, not a production TikTok layout. The image and SVG were not redesigned.
- Full unseen repository documents are not embedded. Essential existing excerpts and all source-page table records are included; source paths are plain provenance text.
- Source drift means this build uses the frozen later source, not an assertion that the upstream file still has the specification’s initial hash.
- No renewed audience-task study or accessibility certification was performed. Final visual/interactive acceptance remains outstanding.

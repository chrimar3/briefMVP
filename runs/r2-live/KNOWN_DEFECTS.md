# Known defects — round-2 live briefs (`runs/r2-live/`)

**Status:** open record, added 2026-09-24 (review loop round 2, workstream W-D). The run
directories are committed evidence and are not edited; this file sits beside them.

**What this covers.** The six complete briefs of the round-2 live re-baseline — `nl-r1`, `nl-r2`,
`nl-r3` (northlight_01), `vo-r2`, `vo-r3` (voreas_02) and `lv-r1` (levanta_03, the blind
fixture) — plus the refused run `vo-r1`. Every run used the current routing (sonnet extraction +
sonnet verify-extract, owner decision 2026-09-23 #5), the round-2 prompts and CLI 2.1.280. The
frozen harness scores are in each `<run>.harness.log`; the frozen harness grades recall against
the answer key and does not see the defects below.

**How each item was verified.** Three sources, each re-checked against the committed files before
it was written here: `python3 eval/supplementary.py runs/r2-live/<run>` (S1–S9, report-only), the
`language_warnings` the render step recorded in each `run_manifest.json`, the render-stage
per-question citation gate (`pipeline/render_checks.py:render_coverage`, merged after these runs)
applied read-only to the committed renders, and a line-by-line reading of the `nl-r1` and `vo-r2`
Greek and English renders against their sources. Line numbers and quoted strings are copied from
the files as committed.

**How it is kept honest.** Items marked *xfail* are encoded in `tests/test_regression_r2_live.py`
as strict xfails: when a regenerated brief no longer has the defect, the test XPASSes, the suite
fails, and the mark and this entry are updated together. Items marked *judgment* are verified, but
no deterministic check is reliable enough to encode them. None of these briefs is signed off: the
owner's decisions on `nl-r1` are prepared (`nl-r1/OWNER_DECISIONS.md`) but not yet recorded, so
every conflict is still open and every question still unanswered.

## Brief (`brief.json`)

| id | defect (verified) | where | check |
|---|---|---|---|
| B1 | **Open questions re-ask open conflicts.** A question in the same field asks the client to settle exactly what an open conflict already puts to the account lead, with shared evidence. Counts: nl-r1 4, nl-r2 3, nl-r3 3, vo-r2 8, vo-r3 9, lv-r1 5. The same class was systematic in the July briefs (`docs/EVAL_RECORD.md` §5); round 2 did not change it. | every run; e.g. nl-r1 `open_questions[2]` ↔ `conflicts[0]` (audiences) | xfail ×6 · supplementary S5 |
| B2 | **A spoken, hedged budget becomes numerals in a suggested question.** The CFO said «κάπου στα ογδόντα, μπορεί ογδόντα πέντε» (northlight transcript [00:14:32]). The entries and conflict positions keep the words ("around eighty, maybe eighty-five", units unstated), but the budget question in all three northlight briefs asks about "the 80–85" / «Το 80–85». SYNTHESIS.md rule 2 renders a spoken figure in words with units unstated; a numeral range is the first step towards the €80–85k reading the X3 trap guards against. This replaces the July decade-range drift (tier3 B7), which no longer occurs. | nl-r1 `open_questions[9]`, nl-r2 `open_questions[9]`, nl-r3 `open_questions[8]` (`suggested_question_for_client`); EN:101 / EL:101 in nl-r1 | xfail ×3 |
| B3 | **A competing position is copied into a second field after the conflict-consistency repair.** The synthesis gate refuses "resolution by omission" (a field asserting one position while the competing one appears only inside a conflict). On voreas, the repair adds the brand guidelines' "no influencers" rule as a *deliverable* (it is also, correctly, a mandatory), citing only the guidelines. | vo-r2 `deliverables[7]`, vo-r3 `deliverables[7]` (and `mandatories[9]` in both) | xfail ×2 · supplementary S4 flags the "micro-influencer" wording |
| B4 | **A client mandate filed as a deliverable.** The RFP's TikTok-first strategy is `deliverables[0]` ("TikTok-first strategy: the whole creative approach is to be designed primarily for TikTok"). It is a creative constraint, and nl-r1 files it under mandatories. | nl-r2 `deliverables[0]`, nl-r3 `deliverables[0]` | xfail ×2 |
| B5 | **A stale question.** vo-r2 asks «Όταν λέτε «μέσα στον μήνα», εννοείτε έως τις 31 Ιουλίου 2026;» ("by 31 July 2026?") in a brief generated on 2026-09-24. The synthesis resolves a relative date from the kickoff (2026-07-12) and never compares it with the brief's own generation date. (The fixture dates are fictional, so "stale" is relative to the run; the defect is that no stage checks.) | vo-r2 `open_questions[16]`; EL/EN question 17 | xfail |
| B6 | **Approver gaps filed under mandatories.** The missing client approver is a process gap, not a mandatory or no-go; the July brief did the same (tier3 B8). | nl-r1 `open_questions[16]`, nl-r3 `open_questions[14]`, lv-r1 `open_questions[19]` | judgment |
| B7 | **Translations shown in quotation marks as if verbatim.** The canonical brief is English; several entries put an English rendering of a Greek utterance in double quotes, which a reader takes as the speaker's words: nl-r1 `timeline[2]` "we're moving somewhere around there" (source «Κάπου εκεί κινούμαστε»), nl-r2 `budget[1]` "we are somewhere around eighty, maybe eighty-five", vo-r2 `deliverables[5]` "half a campaign", lv-r1 `mandatories[7]` "as everyone in the market does". The Greek renders quote the Greek original correctly. | as listed | judgment · supplementary S4 (heuristic; S4 also raises glossary-term false positives, e.g. nl-r2 `budget[3]` 'media spend') |
| B8 | **A client fact reaches no reader** (tier3 B10, still open). «Έρευνα για την κατηγορία δεν έχουμε δική μας» (northlight emails, Message 2) does not appear in any northlight brief. | nl-r1, nl-r2, nl-r3 | judgment |
| B9 | **A misattribution is carried correctly but not called out** (sealed extra check E2, ideal behaviour). lv-r1 reports that Sofia's email attributes the 35% target to Άρης ("second-hand"), which passes E2; it never notes that the CFO did not speak about targets at the kickoff (MARINA set 25% at [00:02:52]). | lv-r1 `objectives[5]`, `conflicts[3]` | judgment · `eval/sealed_extras.py` E2 |

## Extracts

| id | defect (verified) | where | check |
|---|---|---|---|
| E1 | **A garbled term kept without its glossary proposal — the one frozen-harness failure (T1.4, nl-r3 16/17).** The haiku fidelity check annotated «μπραντ αγουέρνες» as `[FIDELITY: no-glossary-match]` (nl-r1 and nl-r2 annotated `glossary-match "brand awareness"`). The extractor carried the gate's outcome, as SOURCES.md rule G asks. The sonnet verifier then flagged exactly this ("The glossary has a plausible candidate, 'brand awareness'"), and the extractor rejected the finding, citing rule G (`nl-r3/verification/transcript_kickoff.adjudication.json`). Root cause: a haiku fidelity miss that rule G makes binding downstream; the verifier caught it and had no authority to override. | `nl-r3/extracts/transcript_kickoff.json` `extraction_notes`; `nl-r3/fidelity/transcript_kickoff.annotated.md` | xfail · harness T1.4 |

## Renders (`brief_el.md`, `brief_en.md`)

| id | defect (verified) | where | check |
|---|---|---|---|
| R1 | **Open questions without their own full citation tag.** The render-stage gate that now requires each numbered question to carry `[source_id location]` with the full stored location (`render_coverage`, commit `ea5cd68`, merged after these runs) fails on 5 of 6 committed renders: shortened email tags such as `[emails_thread Message 2]` for a location stored as `**Message 2** · From: … · Date: …`, and questions with no tag. nl-r3 passes. A regenerated render would be refused and repaired; the agency audit applies the same check before approval. | nl-r1 (6 findings), nl-r2 (32), vo-r2 (26), vo-r3 (4), lv-r1 (6) | xfail ×5 |
| R2 | **Greek: final ν missing before a vowel.** «τη αποφασίζει ο Pavlos» should read «την αποφασίζει». The render step recorded it as a language warning (warning-only by design). | lv-r1 `brief_el.md:58` | xfail · `pipeline/greek_lint.py` |
| R3 | **Greek: article gender.** «επαναδιατυπώθηκε … από τον account lead» — the account lead is Eleni («ELENI (Northlight, account lead)»), so «από την account lead». | vo-r2 `brief_el.md:41` | xfail |
| R4 | **Greek: wrong word for "inaudible".** «διακόπηκε από ένα ανεπαίσθητο (inaudible) σημείο» — «ανεπαίσθητο» means imperceptible, and the heading «ακουστό κενό» says "audible gap", the opposite of what is meant (natural: «σημείο που δεν ακούγεται», «κενό στην ηχογράφηση»). | vo-r2 `brief_el.md:126–127` | xfail |
| R5 | **Internal metadata in client-facing text.** The market-research benchmark is introduced as «(υπονοούμενο, χαμηλή βεβαιότητα)» / "(implied, low confidence)" — the entry's `qualifier` and `confidence` fields, which the brief content does not contain. | vo-r2 `brief_el.md:50`, `brief_en.md:50` | xfail |

## Run level

| id | finding (verified) | where | check |
|---|---|---|---|
| P1 | **One of three voreas runs produced no brief.** vo-r1 stopped at synthesis after two attempts: the conflict-consistency gate refused both drafts for "resolution by omission" (the deliverables field asserted the micro-influencer request while the guidelines' "no influencers" position appeared only inside the conflict). The gate worked as designed — a draft that silently picks a side is refused — but the run spent 649,965 tokens and the operator must re-run. The frozen harness scored the partial run 12/17 (no readiness block, no renders). vo-r2 and vo-r3 passed the same gate on their second attempt, and B3 is what that repair looks like. | `vo-r1.console.log`, `vo-r1/run_manifest.json` | measured (`docs/EVAL_RECORD.md` §1) |

## The July defects (`runs/tier3/KNOWN_DEFECTS.md`) in the new runs

The tier3 xfails in `tests/test_regression_northlight.py` grade the July evidence and stay as they
are. This table says whether each July defect still occurs in the round-2 briefs.

| tier3 id | July defect | round 2 |
|---|---|---|
| B1 | questions left open after sign-off | **not assessable** — no round-2 brief is signed off yet |
| B2 | resolved values never reach their fields | **not assessable** — no conflict is resolved yet |
| B3 | garbled terms resolved silently where readers look | **no longer occurs** — every garbled term reaches the reader as «as heard» next to its proposed match (SYNTHESIS.md garble carry-through rule, owner decision 2026-09-23 #1); supplementary S3 is ok on nl-r1–r3, vo-r2, vo-r3. Its lv-r1 flags are a scorer false positive: the evidence anchors are excerpts that stop before the token, while the content shows it («ριτάργκετινγκ», «πους νοτιφικέισονς», «έρλι μπούκινγκ», «Λεβάντα Κλαμπ») |
| B4 | garble-carrying items at confidence high | **no longer occurs** — garble-carrying transcript items are `low` in nl-r1, nl-r3, vo-r2, vo-r3 |
| B5 | "beach-party" clause cited to the transcript | **no longer occurs** — the clause cites the brand guidelines in all three northlight briefs |
| B6 | agency process steps filed as deliverables | **no longer occurs**; a different misfiling appears (B4 above: a mandate as a deliverable) |
| B7 | budget hedge drift ("in the eighties") | **no longer occurs** (S9 ok ×6); replaced by the numeral range in a question (B2 above) |
| B8 | items under the wrong field | **still occurs** for the approver gap (B6 above); tone guidance now sits under mandatories |
| B9 | no question links TikTok-first to the audience correction | **partly addressed** — nl-r1 question 15 asks whether TikTok-first is a requirement and how it relates to the launch goal or audience |
| B10 | "no category research" reaches no reader | **still occurs** (B8 above) |
| E1 | extraction translated | **no longer occurs** — transcript `key_messages` values are verbatim Greek in all three northlight extracts |
| E2 | a repair erased the metro retraction | **no longer occurs** — the metro idea and its retraction are an `internal_conflicts` entry in nl-r1 and nl-r3 |
| R1 | "unresolved" heading over resolved conflicts | **not assessable** — every conflict is open, and the heading matches that |
| R2 | pipeline metadata in the client brief | **mostly fixed** — tier, coverage and verdict now sit in a closing block headed «Εσωτερικά στοιχεία — δεν αποστέλλονται στον πελάτη» / "Internal — not for the client"; entry-level metadata still leaks once (R5 above) |
| R3 | nine Greek grammar errors | **fewer** — none of the nine July error classes in nl-r1's Greek render; the language lint is clean on 5 of 6 renders; three new errors are recorded above (R2–R4) |
| R4 | temporal deixis ("today it was said") | **no longer occurs** — no «σήμερα» / "today" in any round-2 render |
| R5 | the two renders disagree on the budget | **no longer occurs** in nl-r1 ("Around eighty, maybe eighty-five" / «Περίπου ογδόντα, ίσως ογδόντα πέντε») |
| R6 | EN adds or softens content | **no longer occurs as recorded** — nl-r1 EN keeps «φυσικά υλικά» visible beside "natural ingredients"; translated quotes are B7 above |
| R7 | calques and the English title | **no longer occurs** — no «επικεφαλής λογαριασμού», «διαμερίζεται» or «Client Brief [EL]»; the Greek title is «Brief πελάτη» |

## What this record does not cover

- **Creative drafts.** None exist for the round-2 runs. Pending: owner sign-off on
  `runs/r2-live/nl-r1`, then the creative A/B. The July creative defects stay in
  `runs/tier3/creative/KNOWN_DEFECTS.md`.
- **A native Greek editor's full pass.** R2–R4 come from the lint and one reader's line-by-line
  pass over nl-r1 and vo-r2; the other four Greek renders were read for the listed patterns only.
  The human language attestation (`agency attest`) remains the Greek quality gate.

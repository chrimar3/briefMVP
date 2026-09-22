# Known defects — runs/tier3 brief, extracts and renders

**Status:** open record, added 2026-09-23 (review loop round 1, workstream W3). The evidence pack
itself is historical and unchanged; this file sits beside it.

**What this is.** `runs/tier3` is the graded run: 17/17 on the frozen harness
(`harness_report.json`). The frozen harness grades recall against the answer key; it does not
measure the content defects below. The round-0 output panel (`tools/project_review/rounds/r0/out/`
o1, o2, o3) reported them. Each item was re-checked against the committed artifact before it was
written here: the line numbers and quoted strings are copied from the files as committed.
Creative-draft defects are in [`creative/KNOWN_DEFECTS.md`](creative/KNOWN_DEFECTS.md).

**How it is kept honest.** Items marked *xfail* are encoded in
`tests/test_regression_northlight.py` as strict xfails. When a regenerated run no longer has the
defect, that test XPASSes, the suite fails, and the mark and this entry are updated together.
Items marked *judgment* are verified, but no deterministic check is reliable enough to encode them.
`python3 eval/supplementary.py runs/tier3` prints the machine-detectable ones (S2, S3, S4, S9).

Routing era: every model stage of this run used the Haiku-era routing (haiku extraction, no
verifier). See `docs/EVAL_RECORD.md`.

## Brief (`brief.json`)

| id | defect (verified) | where | check |
|---|---|---|---|
| B1 | **Open questions left open after sign-off.** The brief is `signed_off` and all three conflicts are `resolved_by_human`, but open questions 1 (audiences), 2 (budget) and 8 (timeline) still ask the client to settle them ("No single confirmed audience definition exists", "The two figures are not reconciled", "The launch date itself is contested"). | `open_questions[1]`, `[2]`, `[8]`; EN/EL render questions 2, 3, 9 | xfail · supplementary S2 |
| B2 | **Resolved values never reach their fields.** `audiences` and `budget` hold no entry, so both renders print "No confirmed entries" (EN:15, :36) under a SIGNED OFF banner; `timeline` never states 15 September outside the conflict block. The resolutions exist only in `conflicts[].resolution`. | `audiences`, `budget`, `timeline` | xfail |
| B3 | **Garbled terms resolved silently where readers look.** `objectives[2]` says "Building brand awareness is central" and `key_messages[3]` says "the key visual should evoke summer". The ASR tokens «μπραντ αγουέρνες» / «κι βίζουαλ» survive only inside `evidence[].anchor`; neither render contains either token or any ASR flag. Harness T3.3 passes because it searches the whole brief JSON, anchors included. `docs/EVIDENCE.md`'s "carried as-is through extract → brief → renders" overstates this. | `objectives[2]`, `key_messages[3]`; both renders | xfail ×2 · supplementary S3 |
| B4 | **Garble-carrying items at confidence high.** SOURCES.md rule G says a garbled item is confidence `low`. The transcript extract carries both garbled items at `high`, and so do the brief entries built on them. | `extracts/transcript_kickoff.json` `objectives[0]`, `key_messages[2]` | xfail |
| B5 | **Clause attributed to the wrong source.** `key_messages[3]` adds "not a generic beach-party feel" and cites only `transcript_kickoff [00:06:02]`. That line never says it; the clause comes from `background_brand_guidelines` §Category no-gos ("Avoid generic "beach party" clichés"). | `key_messages[3]`; EN:21, EL:21 | xfail · supplementary S4 |
| B6 | **Agency process steps filed as deliverables.** `deliverables[0]` ("Final approval of the brief is a required step…") and `deliverables[1]` ("Northlight will send a revised plan…") are agency process steps. They are not campaign deliverables. | `deliverables[0]`, `[1]`; EN:24–25 | xfail |
| B7 | **Budget hedge drift.** The source is «κάπου στα ογδόντα, μπορεί ογδόντα πέντε» (transcript [00:14:32]), and SYNTHESIS.md rule 2 renders that as "around eighty (units unstated)". `conflicts[1].positions[1]` says "somewhere in the eighties, maybe eighty-five" instead, and the resolution plus `signoff.edits_summary` say "Production budget in the eighties", which reads as a range of 80–89 and drops "units unstated". The same brief's open question 3 says "around eighty". | `conflicts[1]`, `signoff.edits_summary`; EN:102, :103, :115 | xfail · supplementary S9 |
| B8 | **Items filed under the wrong field.** The approver gap is filed under `mandatories` (`open_questions[0]`), and the brand tone-of-voice guidance sits under `key_messages[0]`. | `open_questions[0]`, `key_messages[0]` | judgment |
| B9 | **Missing strategic question.** The RFP's TikTok-first mandate (rfp §4) was written for the Gen Z 18–24 audience the CMO withdrew at [00:03:41]. The brief never asks whether TikTok-first still holds for a 25–40 urban-professional buyer. `open_questions[7]` asks what TikTok-first means but does not link it to the audience correction. | `open_questions[7]` | judgment |
| B10 | **A client fact reaches no reader.** «Έρευνα για την κατηγορία δεν έχουμε δική μας» (emails, Message 2: the client has no category research) survives only as an `extraction_note` and never reaches the brief. | `extracts/emails_thread.json` `extraction_notes[0]` | judgment |

## Extracts

| id | defect (verified) | where | check |
|---|---|---|---|
| E1 | **Extraction translated.** This is against SOURCES.md rule 5. `key_messages[0].value` renders «φυσικά υλικά» as "natural ingredients", and `key_messages[1].value` is an English paraphrase with an added "(sparkling tea)". | `extracts/transcript_kickoff.json` | xfail (key_messages[0]) |
| E2 | **A repair erased a within-source retraction.** The metro OOH idea and its retraction ([00:08:15] / [00:08:34]) were removed together by the repair loop; only the note `[REPAIR: deliverables[2] … Metro retraction documented only via internal_conflict; both removed together]` records it, and `internal_conflicts` is empty. Harness trap X1 passes (nothing committed), but the creative team gets no warning. | `extracts/transcript_kickoff.json` | xfail |

## Renders (`brief_el.md`, `brief_en.md`)

| id | defect (verified) | where | check |
|---|---|---|---|
| R1 | **Conflict heading contradicts status.** The heading "⚠ Unresolved Conflicts (account lead must resolve before sign-off)" / "⚠ Ανεπίλυτες Συγκρούσεις (…)" sits over three conflicts marked resolved, under a SIGNED OFF banner. The heading is fixed in `templates/northlight_client_brief.md`. | EN:92, EL:92 | xfail ×2 |
| R2 | **Internal pipeline metadata in a client-facing brief.** Both renders carry "Sensitivity tier S1", "Input coverage 5/7", "Verdict: Ready for review" and "Pipeline: brief-builder-stage1" (EL: «Επίπεδο ευαισθησίας», «Κάλυψη εισερχομένων», «Αξιολόγηση», «Pipeline»). | EN:5–7, EL:5–7 | xfail ×2 |
| R3 | **Greek grammar errors**, several of them inside suggested questions that are meant to be asked verbatim. The table below lists each. | `brief_el.md` | xfail ×9 + generic lint |
| R4 | **Temporal deixis.** Suggested question 2 says "today it was said" / «σήμερα ειπώθηκε». The kickoff was 2026-07-10; the brief is dated 2026-07-24. | EN:58, EL:58 | xfail |
| R5 | **The two renders disagree on the budget.** EN says "in the eighties" (:102–103, :115), while EL says «κάπου στα ογδόντα» / «στα ογδόντα» (:102–103). EL:60 also puts «γύρω στα ογδόντα, μπορεί ογδόντα πέντε» in quotation marks, which is not what the source says («κάπου στα ογδόντα»). | EN:102–103, EL:60, :102–103 | judgment (EN side covered by B7) |
| R6 | **EN adds or softens content.** EN key message 3 adds "(sparkling tea)" (:20), and EN renders «φωνάζει καλοκαίρι» as "evoke summer" (:21). EL :33 and EN :33 add "production" to Eleni's «αλλάζει αρκετά τον προγραμματισμό». | EN:20, :21, :33; EL:33 | judgment |
| R7 | **Calques and inconsistent terms in the Greek.** «επικεφαλής λογαριασμού» (:3, :98) alongside "account lead" (:92, :115); «Κάλυψη εισερχομένων» (:6); «διαμερίζεται» (:62, where «κατανέμεται» is natural); «Το Northlight θα στείλει» (:25, where a company takes the feminine «Η»); the dangling «κυρίως» (:28); «παραμένει ανεπιβεβαίωτο και παραμένει ανοιχτό» (:103); the English title «Client Brief [EL]» (:1). | `brief_el.md` | judgment |

### R3 — Greek grammar, line by line (`brief_el.md`)

| line | as written | should read | rule |
|---|---|---|---|
| 54 | «η θέση της προσώπου» | «η θέση του προσώπου» | article gender (το πρόσωπο) |
| 66 | «Ποιό είναι το target reach» | «Ποιο …» | monosyllables take no accent |
| 68 | «τη κατηγορία» | «την κατηγορία» | final ν before κ |
| 78 | «και που ακριβώς θα χρησιμοποιηθούν» | «και πού ακριβώς …» | interrogative πού |
| 86 | «τη τελική έγκριση» | «την τελική έγκριση» | final ν before τ |
| 95 | «ορίζει το κοινό-στόχος ως» | «ορίζει το κοινό-στόχο ως» | accusative object |
| 103 | «σύμφωνα με τον CFO» | «σύμφωνα με την CFO» | the CFO is Anna (transcript participants line: «ANNA (Meltemi, CFO)») |
| 103 | «Ο προϋπολογισμός media διαχειρίζεται ξεχωριστά» | «Το media budget το διαχειρίζεται ξεχωριστά ο media shop του πελάτη» | the deponent verb makes the budget the agent |
| 115 | «Επιλύθηκαν οι τρεις αντικρούσεις» | «… οι τρεις συγκρούσεις / αντιφάσεις» | αντίκρουση means rebuttal |

The sign-off `edits_summary` says "no edits to extracted entries". No Greek-language review of any
kind stood between render and sign-off.

## Documentation claims about this run

These are records we do not edit. The corrections live here and in `docs/EVAL_RECORD.md`.

- `runs/tier_3_report.md` presents the brief as clean. The defects above are not recorded there.
- `runs/tier_1_report.md:80` and `runs/tier_3_report.md:177` say that no prompt was tuned against
  the key. The runtime skills nevertheless quote graded-fixture text verbatim (the [00:14:32] CFO
  line in SOURCES.md, both seeded garbles in TRANSCRIPTS.md, and the speculative-remark phrase in
  verify-extract.md). The contamination disclosure is `docs/EVAL_RECORD.md` §3.

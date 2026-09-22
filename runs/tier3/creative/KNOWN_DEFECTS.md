# Known defects — runs/tier3 creative drafts (sonnet / opus A/B)

**Status:** open record, added 2026-09-23 (review loop round 1, workstream W3). The two drafts
(`creative_brief_sonnet.md`, `creative_brief_opus.md`) are historical Tier-4 shadow-mode evidence
and are unchanged. They carry the old `SHADOW MODE` banner and loose citation tags, and predate the
current CREATIVE DRAFT contract (`docs/OPERATING_DECISIONS.md`, 2026-09-20).

This file does not start with a draft banner, so the creative tooling and
`eval/supplementary.py` do not read it as a draft.

**Verification.** The round-0 output panel (`tools/project_review/rounds/r0/out/` o1, o2, o3)
reported these defects. Each was re-checked against the committed draft, `brief.json` and
`config/channel_specs.json`, and the line numbers and strings are copied from the files. Items
marked *xfail* are strict xfails in `tests/test_regression_northlight.py`;
`python3 eval/supplementary.py runs/tier3` reports S6/S7/S9 on them.

| id | draft | defect (verified) | line | check |
|---|---|---|---|---|
| C1 | sonnet | **Invented unit and currency.** "Production budget: "in the eighties" (€80–85k)" and again "production figure (€80–85k)". The brief records the figure with "no confirmed unit or currency" (open question 3), and SYNTHESIS.md rule 2 forbids €/thousands. This is the invented-total class that harness trap X3 exists to catch, and X3 does not read creative drafts. | 64, 69 | xfail · supplementary S6 |
| C2 | sonnet | **Unsourced market claim.** "a category (sparkling tea) that is new to Greece". The source says the category is new to the *company*: «καινούργια κατηγορία για εμάς» (transcript [00:02:05]); `objectives[2]` says "for the company". | 9 | xfail |
| C3 | opus | **Unsourced provenance claim** in the SMP: "Meltemi Fizz is the Greek-made sparkling tea". The sources say only «ελληνικό brand»; no source states where the product is made. | 11 | xfail |
| C4 | opus | **Misstated status.** Says the TikTok dance "was floated speculatively and retracted". It was hedged («Don't hold me to it»), not retracted; the retraction in the source is the metro OOH idea. The brief carries the dance as `conditional`. Line 96 repeats "Conditional/retracted items (TikTok dance)". | 73, 96 | xfail (line 73) |
| C5 | sonnet | **Spec token not byte-identical.** Writes `9–60s` with an en dash (U+2013); the table row `tiktok_infeed_video` has `9-60s`. It passed only because `pipeline/creative.py` checks resolutions and aspect ratios, not durations or file types, although `config/channel_specs.json` says every spec token is checked byte for byte. | 52 | xfail · supplementary S7 |
| C6 | opus | **Self-claimed human review.** "Reviewed by a creative lead for evaluation only". The model wrote this at generation time, before any human review. | 5 | xfail |
| C7 | opus | **Reformatted amount.** The traceability note writes the RFP's €90,000 as "€90k". The brief never uses that form. | 96 | xfail · supplementary S6 |
| C8 | both | **Budget hedge drift carried over** from the brief ("in the eighties"; see `../KNOWN_DEFECTS.md` B7). | sonnet 64; opus 80 | supplementary S9 |
| C9 | opus | **"Verbatim" heading over a trimmed list.** "Mandatories & no-gos (verbatim from the brief)" drops "attached by Dimitris" from the guidelines-version mandatory and omits the RFP §7 mandatory. The brief has 10 mandatories; the draft lists 6 plus 3 no-gos. | 42–56 | judgment |
| C10 | both | **No strategic interrogation.** Neither draft asks whether TikTok-first (an RFP mandate written for Gen Z 18–24) still holds for the resolved 25–40 urban-professional audience. Neither addresses the tension between a "premium summer" key visual and a 15 September launch timed to "the end of the soft-drinks season". | — | judgment |
| C11 | both | **English only.** The brief's tone mandatory is "Confident, modern Greek with natural use of English category terms", yet neither draft offers a Greek-language line in the brand's register. Greek appears only inside the quoted claim «φυσικά συστατικά». | — | judgment |
| C12 | both | **Brand-risk wording in the SMP.** Sonnet: "sugary, beach-party fizz" puts a lowercase "fizz" next to a name the guidelines forbid shortening to "Fizz". Opus: "nothing to feel guilty about" sits close to the health-claim ban. Both are for the creative lead to judge. | sonnet 5; opus 11 | judgment |

## The Tier-4 verdict this corrects

`runs/tier_4_report.md` (a historical record, not edited) says: "on this brief the models differ
in thoroughness, not correctness — both are trap-clean and spec-clean" (lines 65–66). On the
committed drafts that is not accurate:

- Sonnet is not currency-clean (C1).
- Sonnet is not spec-clean (C5).
- Both drafts make at least one claim the brief does not support (C2, C3, C4).

The same report says the drafts "are gitignored like all run outputs" (line 117). `git ls-files`
shows both are tracked as part of the committed `runs/tier3` evidence pack.

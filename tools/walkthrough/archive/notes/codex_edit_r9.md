Updated only [WALKTHROUGH.html](/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html), in item order. Protected quotations, cited marks and markup are unchanged. Exactly three decisions retain owners; token figures remain intact.

| Item | Result |
|---|---|
| 1 | **Applied.** Respective briefing agents versus inline classification/creative instructions verified against `CLAUDE.md`, Architecture. |
| 2 | **Applied.** Normalization, denominator 10–59 exemption and missing duration/file-type validation verified in `pipeline/creative.py`. |
| 3 | **Applied.** “The shadow drafts need three corrections and a creative lead’s decision.” |
| 4 | **Applied.** Creative approval explicitly pending; v1 creative remains shadow-only. |
| 5 | **Adapted.** Used the requested manual-recording/display-only wording while retaining the field names in parentheses. Schema fields and review behavior verified against `schema/brief_schema.json` and `pipeline/review.py`; training by week 4 verified against PRD §8. |
| 6 | **Applied.** Conditional-pilot title requires capacity, costs and a spending ceiling before starting. |
| 7 | **Applied.** Proposed financial condition appears in both decision and ledger; no monetary amount invented. |
| 8 | **Adapted.** Replaced unsupported 4/5 threshold with: “Greek naturalness rated 1–5, with EL/EN edits compared; the sponsor must confirm a release threshold before week 1 (docs/pilot/SCORECARD.md leaves it unset).” PRD §7 and scorecard §2 provide no numeric floor. Remaining requested targets and adoption wording applied. |
| 9 | **Applied.** Proposed binding release condition and separate month-2 sponsor approval. |
| 10 | **Applied.** Baseline labelled assumed, fifty-minute target unvalidated, graded review untimed. |
| 11 | **Applied.** “Nine model-agent attempts, each potentially containing multiple turns (four documents, one retried)” in both locations. Verified against the graded manifest and `pipeline/agents.py`. |
| 12 | **Applied.** Demo-profile override disclosed. Four-minute timing verified in `docs/demo_timing.md`; 5:45 and override verified in `docs/EVIDENCE.md`. |

Nothing skipped.

Build succeeded with `--out /tmp/walkthrough-r9-artifact.html` to avoid modifying another repository file. Final `checks.py` exited **0**:

```json
{
 "sheets": 10,
 "blockquotes": 13,
 "failures": []
}
```

Visible words, using the checker’s counting method:

| Sheet | Words |
|---|---:|
| 01 | 326 |
| 02 | 316 |
| 03 | 310 |
| 04 | 277 |
| 05 | 327 |
| 06 | 303 |
| 07 | 342 |
| 08 | 180 |
| 09 | 748 |
| 10 | 450 |

All sheet, action-title and takeaway budgets pass.
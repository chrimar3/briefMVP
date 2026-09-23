Applied all three fixes and regenerated v2.

1. **Sign-off ownership — both pages**, verified against the three specified source files:

   | Location | Before | After |
   |---|---|---|
   | Sheet 07 marginalia | “The machine cannot sign; the sign-off field is not even writable by a model.” | “The machine cannot sign: synthesis writes signoff.status as draft and validation rejects any other value; only a person records signed_off.” |
   | Sheet 07 ledger foot | “A model never writes that field.” | “A model can only write draft; signed_off is recorded by a person.” |
   | Sheet 02 gate band | “a model cannot write this field” | “a model can only leave it as draft” |
   | Sheet 02 ledger | “Nothing passes the sign-off gate without a person; a model cannot write that field.” | “Nothing passes the sign-off gate without a person; a model can only leave the field as draft.” |

2. **Swipe — both pages:** endpoint-only detection → gestures cancel on vertical movement exceeding 40 px, multiple touches, or scrolling. Five gesture scenarios passed for each page.

3. **Final Next button — v2 only:** visible “Next” / accessible “Return to sheet 01” → “Start again” / “Start again: return to sheet 01”. Other sheets retain the requested Next labels; all ten passed label checks. v1 unchanged for this item.

Both checks exited **0**, each outputting:

```json
{
 "sheets": 10,
 "blockquotes": 13,
 "failures": []
}
```

Grep found **no matches** for any of the four prohibited phrases in either page (exit 1).

Protected blockquotes and cited marks remain unchanged; all budgets passed. No review-scope exhibits were added. The artifact build succeeded using `--out /tmp/r11_a_brief_with_receipts.html` to avoid modifying an additional repository file.
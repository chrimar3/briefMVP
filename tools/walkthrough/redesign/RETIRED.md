# Retired: the v2 walkthrough redesign

**Status: historical record. Do not edit, rebuild or publish from this folder.**

On 2026-09-22 the owner chose one canonical walkthrough: `WALKTHROUGH.html` (v1) at the
repository root, corrected to the current system (`docs/OPERATING_DECISIONS.md`, decision 2).
This v2 redesign was retired and is kept unchanged as a record of the research, the design
specification and the round-11 review.

What that means in practice:

- `WALKTHROUGH_v2.html`, `a_brief_with_receipts_v2.html` and `source_snapshot.html` are frozen
  at 18 September 2026. They predate Tiers 5–7 and the 2026-09-20 creative decision, so they
  still describe creative as shadow-only and sign-off as a manual edit. Neither statement is
  current.
- `build_v2.py` is no longer part of any workflow; later edits to `WALKTHROUGH.html` are not
  propagated here.
- The gate `tools/walkthrough/checks.py` applies to `WALKTHROUGH.html` only.
- The v2 artifact published on 18 September carries the same superseded statements; the
  canonical page is the one to share.
- The research (`research.md`) and the deviation register (`design_spec.md`) remain useful
  references for any later redesign of the canonical page.

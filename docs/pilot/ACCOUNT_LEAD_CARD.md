# Account lead card — one page

For the two pilot account leads. You own every decision on your brief; a champion types the
commands beside you (`ROLES.md`, recording a human decision). The detail is in
`BRIEF_CHAMPION_RUNBOOK.md` §3–6; your stopwatch rules are in `SCORECARD.md` §1. Walk through
this card once in week 1 and time one synthetic rehearsal with it before week 2 (T-07).

**What you are given.** A **review-ready draft**, not a client-ready brief: `brief_review.html`
(both languages, conflicts, questions with a copy button), `agency_audit.md` (what still blocks
approval) and the two renders. The draft has known failure modes; your review is the control.

**Start the stopwatch** when you open `brief_review.html`; stop it at each break; the sum is
`review_min`. Note separately the minutes spent on the audit, triage, exclusions and checklist:
that is `agency_steps_min`, a part of `review_min`, never added to it.

## In this order

1. **Read `agency_audit.md` first.** Every blocker names what to do. A missing fact is repaired
   from the sources or excluded with your reason (`agency exclude`).
2. **Classify every question**, one class each, and say it aloud for the champion to record with
   `agency answer`:

   | Your class (scorecard) | Meaning | Recorded status |
   |---|---|---|
   | real | you would send it as written or lightly reworded | `open` |
   | duplicate | it asks the same issue as a conflict or another question; name which | `duplicate` |
   | answered in sources | you can name the passage that answers it | `answered` (with `--evidence`) |
   | not worth asking | none of the above, and you would not send it | `not_worth_asking` |

3. **Resolve each conflict** with your decision and why (`agency resolve`). Then check that the
   resolved value actually appears in its field and that the matching question is marked
   duplicate: a resolution alone does not fill the field (`runs/tier3/KNOWN_DEFECTS.md` B1, B2).
   If it does not, mark up the render and the champion applies your wording (`agency apply`).
4. **Look for the five critical errors** (`SCORECARD.md` §2) and flag each one you find:
   a source objective missing from objectives, questions and conflicts (CE1); a field that states
   one side of an open conflict as fact (CE2); a claim with no citation, or cited to a source
   that never says it (CE3); a number, total or conversion no source gives (CE4); a garbled word
   silently "fixed" (CE5).
5. **Answer the campaign checklist** from the sources, with evidence (`CAMPAIGN_EDITING.md`).
6. **The bilingual reviewer attests**, not you: the attester must be a different person from the
   signer.
7. **Approve** (`agency approve`) with a summary of what you reviewed and changed.

**What approving binds.** The exact `brief.json`, both renders and the companion records
(checklist and deliverable rows, question decisions, exclusions, evidence index, extracts, input
snapshot), plus the bilingual attestation. Any later change to any of them makes the approval
stale: handover, creative approval and release then refuse until you review and approve again.
Survival is measured on this approved version (`SCORECARD.md` §2).

**After approving** (retro briefs only), compare the draft with the brief the agency actually
wrote and count the four side-by-side columns (`SCORECARD.md` §2). Record your minutes once:
`python3 -m pipeline.effort record ... --role account_review` (`EFFORT_RECORDING.md`).

**Never** type a decision you have not made, let anyone record one in your name, or edit files
in the run directory by hand.

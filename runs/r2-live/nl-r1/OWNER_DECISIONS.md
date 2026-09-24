# nl-r1 — your decisions, part 1

For Christos Maragkoudakis. `owner_decisions_part1.sh` holds 27 suggested decisions for
`runs/r2-live/nl-r1`. An AI agent prepared them and did not run them on this run. Each one
has a comment line above it that says what it decides and which source line or brief entry
it rests on. The script records nothing until you run it yourself. Operating decision
2026-09-23 #6 says you record the human decisions on the regenerated graded brief.

## Order

1. **Resolve the three conflicts yourself** (not part of the script):
   `python3 -m pipeline.agency resolve runs/r2-live/nl-r1 --index N --actor "Christos Maragkoudakis" --text "…"`
   for N = 0 (audiences), 1 (timeline) and 2 (budget). `resolve` moves the current renders into
   `history/`. That is expected: the orchestrator re-renders afterwards.
2. **Read and edit the script**, then run `bash runs/r2-live/nl-r1/owner_decisions_part1.sh`.
   Its guard stops, and records nothing, if any conflict is still open. The two coverage
   exclusions are bound to the brief content as it stands after your resolutions.
3. `python3 -m pipeline.agency audit runs/r2-live/nl-r1`. Once the renders are back, only the
   render-citation blockers and the language-review blocker should remain.

## What part 1 records

| Block | Count | What it decides |
|---|---|---|
| A. Question triage (`agency answer`) | 17 | 13 `open` (nonblocking: they go to the client with the brief), 4 `duplicate`/`not_worth_asking` (below), each with the source lines it rests on |
| B. Coverage exclusions (`agency exclude`) | 2 | the metro OOH idea [00:08:15] and its retraction in the same turn [00:08:34] ("actually scratch that … Ξεχάστε το", transcript line 15) |
| C. Campaign checklist, `paid_campaign` (`agency_edit checklist`) | 7 | objective, KPI, audience/offer, landing page, tracking, budget/dates, assets/approvals |
| D. Deliverables matrix (`agency_edit deliverable`) | 1 | `kv-master-01`: key visual digital master ×1, el, due 2026-09-15 |

The four questions that are not left open:

- Q3 audiences, Q7 launch date and Q10 budget are marked `duplicate` of conflicts 0, 1 and 2.
  Your resolutions settle them, and the render shows these three in the answered form. Q7 also
  asked for the point-of-sale placement deadline, so that part now sits in Q8 (milestones).
- Q6 (TikTok dance) is marked `not_worth_asking`. The CMO said "Don't hold me to it" [00:11:47],
  and Eleni recorded it at the call as an idea, not a decision [00:13:05].

**Answers the sources do not give** are written as "To confirm with client" with you as owner.
Nothing was filled in to cover them. They are:

- the KPI and measurement period
- the landing page and who owns it
- who owns tracking
- any offer
- usage rights
- the client-side approver
- deliverable quantities, formats and durations

No source names a production owner or a client approver, so you are the owner and approval
owner on the one deliverable row. Its quantity of 1 is the lowest number that "key visuals"
supports (RFP §4). The due date is the latest one your conflict-1 resolution allows, the
launch date. The client has not given a delivery date.

**No TikTok video row is recorded.** The TikTok spec row needs a duration of 9–60s and a
quantity, and no source gives either. The script ends with a commented-out command to add it
once the client answers Q5.

## If you disagree

- **A question should hold up approval:** change it to `--priority blocking`. The audit will
  then block until the client answers. That is a legitimate choice for Q1 (KPI), Q15
  (TikTok-first after your audience decision) and Q17 (client approver).
- **A question should not go to the client:** change `--status` to `not_worth_asking`, or to
  `duplicate`, and say which question or conflict it duplicates. Always give a reason in
  `--text`. Do not use `answered`: it blocks until the brief itself is updated.
- **You would rather keep the metro OOH retraction in the brief than exclude it:** delete the
  two `exclude` lines. Then amend the brief with `agency apply`, which is a separate decision.
- **Checklist wording:** edit `--value`. Each `--ref FIELD:INDEX` must point at a brief entry;
  questions and conflicts cannot be cited. Every command can be run again: it upserts, and the
  previous record goes to `history/`.
- Delete any line you would not say yourself. Its blocker then stays, which is the honest
  outcome.

## Part 2, after the orchestrator re-renders

The re-render must write each open question's own citation tag with the full stored location.
For example, rendered items 7, 8 and 12 (the audit calls them question 6, 7 and 11) cite
`[emails_thread **Message 2** · From: Dimitris (Meltemi) · To: Eleni (Northlight) · Date: 2026-07-14 18:22]`,
not the shortened `[emails_thread Message 2]`. The render-stage gate that now enforces this is
on branch `r2-render-gate` and has not been merged yet. Once the renders are back, run the
audit again. The only blocker left should be the language review. Then:

```sh
python3 -m pipeline.agency attest runs/r2-live/nl-r1 --actor "<bilingual reviewer>" --greek-register <1-5> \
  --notes "<what you actually checked>" \
  --checks source_completeness el_meaning en_meaning qualifiers_and_commitments brand_voice
python3 -m pipeline.agency approve runs/r2-live/nl-r1 --actor "Christos Maragkoudakis" --summary "<decisions and changes reviewed>"
```

- The attester must be a different person from the signer. On this synthetic run you may
  instead sign with `--solo-rehearsal`. That waiver is recorded in `approval.json` and in the
  audit log.
- While reviewing, check that each resolved value actually reads correctly in the renders. A
  resolution does not rewrite the field entries: `audiences` and `timeline` still list both
  source positions (`runs/tier3/KNOWN_DEFECTS.md` B2).
- Part 1 stays valid across a re-render. If `brief.json` changes in any other way (an `apply`,
  or a new synthesis), run the audit again: the exclusions and triage are bound to the brief
  content.

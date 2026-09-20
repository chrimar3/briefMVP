# Local clarification exchange and revision impact

This Tier7 helper covers plan tasks 3–5 using synthetic rehearsal data only.
It creates local files, with no models, network calls or messages to other people.
Incoming replies remain **review proposals**. Nothing updates canonical content,
resolves a question, transfers an approval or approves delivery automatically.

## 1. Export unresolved questions

First triage the questions using the existing agency workflow. Each selected
question must have a current explicit `open` decision, a nonempty owner, and
`blocking` or `nonblocking` priority. An untriaged question is rejected rather
than assigned an invented owner or priority. Already answered, duplicate and
not-worth-asking questions are excluded.

```sh
python -m pipeline.question_exchange export runs/SYNTHETIC_RUN /tmp/questions.json
```

To select only certain questions, repeat `--question-id` with the original IDs
from the clarification queue:

```sh
python -m pipeline.question_exchange export runs/SYNTHETIC_RUN /tmp/selected-questions.json \
  --question-id QUEUE_ID_ONE --question-id QUEUE_ID_TWO
```

The pack contains `version`, `pack_id`, client/project `identity`, an opaque
`run_binding`, the run `fingerprint`, `created_at`, and `questions`. Each question
has only `id`, `field`, `question`, `owner`, and `priority`. It does not include raw
source evidence, anchors, linked evidence, existing brief context or source paths.
Question text itself is retained verbatim: review it before any separately
authorized sharing. This tool does not send the pack anywhere.

The pack retains original queue IDs and is bound to the exact run path and
fingerprint. It is also registered locally in
`RUN/question_exchange/packs/PACK_ID.json`. Keep that receipt and the exported
pack unchanged. Existing output files, including symlinks, are never overwritten.
Exports must be outside the run or under `RUN/question_exports/`; other run paths
are reserved so export cannot create a canonical, approval or input artifact.

## 2. Import attributed replies as proposals

Create a separate replies JSON file. Copy `pack_id` and question IDs from the
exported pack; do not edit the pack. A partial reply is valid:

```json
{
  "pack_id": "COPY_PACK_ID_FROM_EXPORT",
  "replies": [
    {
      "question_id": "COPY_QUESTION_ID_FROM_EXPORT",
      "text": "Synthetic proposed budget answer for rehearsal.",
      "evidence": {
        "source_ref": "Synthetic response note, section 1",
        "provided_by": "Synthetic respondent"
      }
    }
  ]
}
```

```sh
python -m pipeline.question_exchange import runs/SYNTHETIC_RUN \
  /tmp/questions.json /tmp/replies.json --actor 'Synthetic account operator'
```

`provided_by` attributes the reply to its asserted source; `--actor` identifies
who imports it. Both and `source_ref` must be nonempty. These are recorded human
assertions, not authenticated identity or verified source content. Unknown JSON
fields, including approval flags, are refused.

Every valid batch creates one immutable JSON receipt at
`RUN/question_exchange/proposals/PROPOSAL_ID.json`, with `status: proposed`, the
pack/run/version bindings, attributed replies, importer and timestamp, and a
snapshot of `pending_question_ids`. Pending means “not yet proposed for this
pack's questions,” not “resolved.” Later batches may fill remaining IDs.

The entire batch is rejected, with no proposal writes, for:

- A changed, unregistered, wrong-run or stale pack; changed source inputs or
  preserved evidence also block import even if brief text is unchanged.
- A question absent from the selected pack, or one no longer matching its triage.
- Duplicate IDs within a batch, a repeat import, or an ID already proposed through
  another pack for the same run fingerprint. A mixed old/new batch is rejected
  entirely; submit only the remaining IDs.
- Empty batches, blank answers, missing attribution, malformed JSON or corrupt
  stored proposal receipts.

After a stale rejection, export a fresh pack from the current run and have replies
explicitly matched to it. Copied or relocated runs cannot reuse the old pack.
There is no overwrite, automatic deduplication, correction or acceptance command.
If a proposal needs correction, retain it and perform an explicit reviewed
revision through the existing workflow; do not silently edit its receipt. An
irrelevant proposal can be explicitly dismissed as described below.

Import leaves `brief.json`, `clarifications.json`, existing approval files and
the run fingerprint unchanged; it does not archive approvals. **Approval and
release eligibility are nevertheless held while any current proposal is pending.**
The integrated `agency.audit` and `revisions.require_current_approval` guards use
`pending_proposals(run)` to block, including when the brief and creative were
already approved and the original question was nonblocking. Receipt validation
errors also block eligibility.

Explicit human dismissal of an irrelevant proposal removes that proposal's hold.
Release can proceed only when no current proposals remain pending and all other
approval/release checks pass. Dismissal does not grant a new approval. Substantive
replies require a human to assess attribution and meaning, ingest authorized
synthetic evidence, revise the canonical brief, re-triage questions, and obtain
required review/approval through the existing workflow. A proposal alone is never
evidence that these steps happened.

The main integration owns `tests/test_reply_safety.py`, covering an approved brief
with a nonblocking question and approved creative: importing a reply blocks audit
and release; explicit human dismissal permits release when the other gates pass.
Helper-level receipt, fingerprint and dismissal tests remain in
`tests/test_question_exchange.py`.

## 3. Dismiss irrelevant proposals explicitly

```sh
python -m pipeline.question_exchange dismiss runs/SYNTHETIC_RUN PROPOSAL_ID \
  --actor 'Synthetic reviewer' --reason 'Reply is irrelevant to this campaign'
```

Dismissal applies to the entire imported proposal batch. It appends an attributed
receipt under `RUN/question_exchange/dismissals/`, linking the exact proposal ID,
original fingerprint, reviewer, reason and timestamp. It never deletes or edits
the proposal, resolves a question, or changes canonical content/approval. Unknown
proposal IDs, blank attribution/reasons and repeated dismissal are rejected.
A stale proposal can also be dismissed for housekeeping; that dismissal does not
hide any proposal for a newer version. There is no undismiss or overwrite command.
A mixed batch containing substantive replies must go through source/new-revision
review; dismissal is a human rejection, not an acceptance mechanism.

`pending_proposals(run) -> list[dict]` validates proposal and dismissal receipts
and their pack/run bindings, then returns only undismissed proposals whose
fingerprint equals the current `revisions.fingerprint(run)`. Stale proposals
remain on disk but are excluded. A version change does not prove their answers
were accepted. Dismissed replies remain in duplicate detection, so they cannot
silently be reimported for the same version through another pack.

The read API does not reacquire `run_lock`, allowing guards to call it inside their
existing critical section. A release/approval caller must hold that lock across
the check and its resulting write to prevent an import from racing the decision.
Malformed receipts raise `ValueError` and filesystem failures propagate; callers
must treat either as a blocker. These receipts remain outside the run fingerprint,
so importing or dismissing a proposal does not accidentally make it stale.

## 4. Compare revision impact

```sh
python -m pipeline.question_exchange impact runs/SYNTHETIC_BEFORE runs/SYNTHETIC_AFTER
```

The report is printed as JSON. Both briefs must have the same client/project
identity and valid recorded source baselines. It includes:

- `changed_fields` and before/after `field_changes` across canonical top-level
  records, including question/conflict, metadata and signoff changes.
- `evidence_changes` grouped by canonical field and citation destination.
- `source_changes` for added, removed or changed recorded source hashes. A source
  change is reported even when the brief text is identical.
- `source_drift` for recorded source paths whose current bytes differ or are
  missing/unreadable, separately for each run. It also reports source-directory
  membership changes under `source-directory:ABSOLUTE_PATH`, with
  `status: membership_changed`, `directory`, `added_paths` and `removed_paths`.
  Like `revisions.verify_inputs`, membership compares resolved `.md` file paths
  directly in each tracked source directory (nonrecursive, files only).
  Added files require review even when briefs and snapshots are unchanged.
  Existing per-source hash/missing-file entries remain present;
  `source_affected_fields` identifies fields citing changed recorded source IDs.
  New unrecorded files have no canonical source ID or field mapping yet.
- `review_required` and `required_review` describing source/citation, bilingual,
  downstream and question/conflict review implications.

The comparison uses stored source hashes for historical before/after differences;
live file and directory-membership drift are reported separately. This check does
not compare semantic meaning or establish complete evidence coverage. It discovers
additional `.md` files only within already tracked source directories; other
directories, nested files and non-Markdown inputs are outside this membership check.
The impact report can include canonical content and citations; unlike the question
pack, it is not stripped of raw evidence. Keep it local. No automatic changes or
resolutions occur. `review_required: false` means no differences detected in these
compared records, not that the run is approved or ready to release.

## Python API and persistence guarantees

```python
export_questions(run, output, question_ids=None)  # returns the exported pack
import_replies(run, pack, replies, actor)          # returns a proposal receipt
impact(before, after)                            # returns an impact report
pending_proposals(run) -> list[dict]              # current, valid, undismissed batches
dismiss(run, proposal_id, *, actor, reason)        # append a human rejection receipt
```

`pack` and `replies` accept JSON-object dictionaries or paths to JSON files. All
CLIs return 0 on success and 2 on invalid input, lock contention or filesystem
failure. `python3` can replace `python` where the environment has no alias.

Mutations use the existing `revisions.run_lock`; impact takes the same locks in
stable path order to obtain consistent cooperating-process reads. Each new JSON
file is written and flushed in its destination directory and published using an
atomic hard link that refuses an existing destination, even in a publication race.
No files are replaced. This requires a local filesystem supporting hard links.

Pack receipt and exported copy are individually atomic, not a multi-file crash
transaction. A failed export can leave an unused local pack receipt; retry with
a new output path. Import writes one atomic batch file. Digests detect accidental
modification and bind local records; they are not digital signatures or protection
against an actor who can rewrite the entire workspace. Existing frozen files,
canonical schema and runtime model routing are unchanged.

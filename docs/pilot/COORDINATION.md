# Account and traffic coordination

These commands extend the champion runbook. Rehearse with synthetic projects only.
They create local records; they do not send client messages or publish campaigns.

## What needs attention

```sh
python3 -m pipeline.operations runs/rehearsal-one
python3 -m pipeline.operations runs/rehearsal-one runs/rehearsal-two
```

The portfolio checks explicit directories, deduplicates aliases and puts errors/blockers
first. One damaged run does not hide the others. Stages are `error`, `blocked`,
`brief_approval`, `creative_selection`, `creative_review` and `ready_to_release`.
Read `next_actions` and `notices`; exit 2 means at least one error or blocked project.
A zero exit does not mean all projects are approved: some may still await human actions.

Status uses current source hashes, evidence, audit rules, approvals, selected files and
catalog validity. It does not trust old audit reports or rewrite them. It acquires the
ordinary run lock to avoid reading a half-written mutation; a busy run is reported as an
error to retry. Counts of historic releases are not claims that those releases remain usable.
Role labels explain who usually acts; the agency still assigns the actual people.

## Production dependencies

Every deliverable dependency is another deliverable's ID. Add predecessor rows first.
The matrix rejects unknown IDs, duplicate dependencies, self-dependencies and cycles.
A predecessor's deadline must be on or before its dependent's deadline. These are date-level
checks, not resource-capacity planning, lead-time estimation or automatic rescheduling.
The account/traffic team sets and confirms quantities, owners and realistic deadlines.

## Check an exported package

```sh
python3 -m pipeline.release_control verify /path/to/package --run runs/rehearsal-one
```

The verifier checks exact filenames, hashes, unexpected entries and redirection. With
`--run`, it also requires a matching recorded release receipt and checks withdrawal records.
A copied package can match the receipt by manifest hash. A standalone check (without
`--run`) checks file integrity only: anyone able to edit the content can recompute a
standalone manifest. Even run receipts are local audit records, not digital signatures.
Use the authoritative run for the latest withdrawal status before sharing.

## Withdraw approval

If a previously approved campaign needs to stop, the responsible human records why:

```sh
python3 -m pipeline.release_control withdraw runs/rehearsal-one --actor "Reviewer name" --reason "Actual reason for withdrawal"
```

The command records hashes of withdrawn approvals and affected release receipts, then
archives the active brief and creative approvals. Releasing again requires fresh human
approvals. It preserves the original brief and language-review record; content changes
still invalidate that review through the ordinary fingerprint rules. The withdrawal
record also blocks the original approval if the process stops before archiving it.

Previously created packages remain on disk. Verification against the run reports them
as withdrawn, including after later approval of a new release. The tool does not recall
files already shared or notify recipients. The account lead handles that communication
through the agency's existing process. Do not delete approval/withdrawal history to make
a package appear current.

For client-question packs and revision impact, see `QUESTION_EXCHANGE.md`. For corrected
effort records and observed rework summaries, see `EFFORT_RECORDING.md`.

Withdrawal also works when a later amendment or catalog rebind has already archived the
active approvals: recorded release receipts still identify the earlier packages to mark.
If an interruption occurs during withdrawal, repeat the normal human brief review,
register the selection against that fresh brief, and obtain fresh creative approval.
Earlier packages remain withdrawn; no history needs to be manually deleted.

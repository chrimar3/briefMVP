# Synthetic effort recording

Use this recorder only with synthetic fixtures and fictional actor identifiers. It
makes no model or network calls and does not read brief content, answer keys, or
approval artifacts. A PILOT row is the scorecard's measurement format, not evidence
of a real-client pilot or permission to run one. The `live` phase is usable here
only for synthetic rehearsal. Real data remains prohibited.

## Purpose limitation

Effort and handoff records measure the brief workflow: whether it saves attention and reduces
rework, per brief and per role. They are not used for individual performance evaluation,
discipline, pay or ranking of staff, and they are not shown per person outside the operator
and the sponsor. Before any real record, staff receive the information step described in
`DATA_PROTECTION.md` §9; the purpose, basis and retention are open decisions for the agency's
data-protection lead (`GO_LIVE_DECISIONS.md` D-12, D-07). Use role or pseudonymous actor IDs
where the record does not need a name; the scorecard carries lead IDs L1/L2 only.

## Commands

From the repository root, using an existing synthetic run directory:

```sh
python -m pipeline.effort record <run> --actor synthetic-account \
  --role account_assembly --minutes 12.5 --event-id assembly-001 \
  --reason "Synthetic assembly exercise"
python -m pipeline.effort record <run> --actor synthetic-reviewer \
  --role account_review --minutes 8 --event-id review-001
python -m pipeline.effort handoff <run> --actor synthetic-production \
  --accepted no --return-reason "Synthetic missing format specification" \
  --event-id handoff-001
python -m pipeline.effort export <run> --brief-id synthetic-demo \
  --phase retro --output /tmp/synthetic-effort.csv
python eval/pilot_scorecard.py /tmp/synthetic-effort.csv
```

Use `python3` if that is the installed interpreter. Replace `<run>` with the actual
synthetic run path. Minutes must be finite and nonnegative; fractions are
preserved. Each event records a nonempty actor and event ID, plus a UTC recording
timestamp. Reasons on effort events are optional. Accepted handoffs use
`--accepted yes` without a return reason; rejected handoffs require a nonempty
`--return-reason`. Recording a handoff does not approve a brief or deliver work.

Available roles and exported columns:

| Role | CSV column |
| --- | --- |
| account_assembly | assembly_min |
| account_review | review_min |
| operator | operator_min |
| strategy | strategy_min |
| creative | creative_min |
| production | production_min |

Record each person's non-overlapping work interval once under the appropriate
role. These are self-reported person-minutes, not elapsed machine time. Multiple
people working together contribute their own minutes. The tool cannot detect
omitted work, overlapping intervals, or duplicate work assigned different IDs.

## Retries, storage, and export

IDs are unique across effort and handoff events within one run. Retrying an ID
with the same payload succeeds without rewriting or adding an event. A different
actor, kind, role, duration, or reason for that ID is rejected. Numerically equal
minutes such as `10` and `10.0` are equivalent; text is compared exactly. Use a new
ID for a new activity, not to retry an uncertain write. Use attributed correction or void events to amend mistakes; originals are retained.

The recorder creates `effort.json` and its own persistent `.effort.lock` in the
run directory. Standard-library `fcntl.flock` serializes cooperating processes
for read/modify/write and export snapshots. Do not remove the lock file while
commands are running. JSON and CSV writes use a flushed, fsynced temporary file
in the destination directory followed by atomic replacement. An invalid existing
ledger is rejected rather than reset. This implementation targets local Unix
filesystems (macOS/Linux); Windows and distributed/network filesystem locking are
not supported. It does not provide a full power-loss durability guarantee.

Export atomically replaces the requested `.csv` output with a header and **one**
row. It does not append to a combined scorecard. Use a separate output per brief,
then include each brief once when combining measurements. Parent directories
must already exist. The header comes from `scorecard_template.csv`; unrelated
measures remain `not_recorded` and are never inferred from pipeline output.
Brief ID and phase (`retro` or `live`) are explicit export metadata. Run ID is the
run directory's name. Dates, baseline, quality, and question measurements are not
inferred from event timestamps.

Role columns sum effective active events only. An absent role is `not_recorded`, never
zero. `total_attention_min` requires both account roles; `total_team_min` requires
all six roles. A partial record therefore cannot establish a complete total.
An explicit `--minutes 0` records an observed zero; an absent role stays unknown.
A present role total also does not attest that all work for that role was logged.

`first_handoff_accepted` and `return_reason` describe the first active handoff in
original recording order. Corrections retain the original observation position;
voiding a handoff removes it from measurements. Later handoffs remain in the ledger but do not replace the first
outcome. Historical handoffs must be recorded in order; event IDs do not determine
chronology. No handoff means both exported fields are `not_recorded`.

## Scorecard summaries

Existing top-level fields retain their meanings, including pooled
`question_precision_pct` (weighted by question count). New fields are:

- `question_precision_per_brief`: individual brief values plus unweighted mean,
  median, measured count, and missing count. Precision requires a total and all
  four integer class counts summing to that total. A zero-question brief has
  undefined precision and is counted as missing here, not as zero or 100%.
- `by_phase`: the same metrics, precision, review, and handoff summaries for each
  observed phase. Blank/missing phase values are grouped under `not_recorded`.
  EXAMPLE rows remain excluded throughout.

For compatibility, the existing `question_precision_measured_briefs` field counts
complete classifications even when the total is zero. The new per-brief measured
count includes only defined ratios. Ratios are not rounded before aggregation.
Input is still one row per brief; the scorecard does not deduplicate repeated IDs.
These summaries remain descriptive and do not assert acceptance criteria passed.


## Attributed corrections and voids

Amendments are logically append-only events in the same atomically replaced JSON
ledger: original objects and their timestamps are preserved, never edited or
deleted. Every amendment requires its own `--event-id`, `--actor`, `--reason`, and
`--target-event-id`. The amendment actor identifies who changed the record; the
replacement actor identifies whose effort or handoff was observed.

```sh
python -m pipeline.effort record <run> --actor synthetic-production \
  --role production --minutes 0 --event-id production-observed-zero
python -m pipeline.effort correct <run> --target-event-id assembly-001 \
  --actor synthetic-supervisor --reason "Correct timer transcription" \
  --event-id assembly-correction-001 \
  --replacement '{"kind":"effort","actor":"synthetic-account","role":"account_assembly","minutes":10,"reason":"Spec repair"}'
python -m pipeline.effort void <run> --target-event-id assembly-correction-001 \
  --actor synthetic-supervisor --reason "Recorded against wrong synthetic run" \
  --event-id assembly-void-001
```

`--replacement` is a complete JSON payload, with no event ID or timestamp:

- Effort: `kind`, `actor`, `role`, `minutes`, `reason` (use JSON `null` if unknown).
- Handoff: `kind`, `actor`, `accepted`, `return_reason` (`null` for acceptance;
  nonempty reason for rejection).

Correction must retain the target measurement's kind. Its new event ID becomes
the active measurement ID; use that ID for another correction or a void. Only
previously recorded, still-active measurements may be targeted. Unknown,
self-referencing, already-voided, or already-replaced targets are rejected. Void
events are not measurements and cannot be targeted. Forward references and
cycles are rejected, including when loading a tampered ledger.

Exact amendment retries succeed without writes, including after a later amendment
has superseded the target. Reusing an ID with changed content is rejected. The
same lock protects target validation and append, so competing amendments cannot
both consume one active target. Voiding the only effort event for a role makes
that role unknown again; it does not record zero effort. Corrections do not count
as new handoff attempts.

Python helpers preserve the existing `record`, `handoff`, and `export` signatures.
New helpers are `void(run, *, target_event_id, actor, reason, event_id)` and
`correct(run, *, target_event_id, actor, reason, event_id, replacement)`.
`read_events(run)` returns a locked, validated effective snapshot: `None` means no
ledger, `[]` means no active events. `effective_events(events)` folds and validates
an in-memory history; callers reading files should use `read_events`.

## Cross-run observed rework report

```sh
python -m eval.rework_report <synthetic-run-a> <synthetic-run-b>
```

The CLI prints JSON. It takes explicit run directories, resolves their paths, and
skips aliases/repeated paths. It does not discover runs, inspect briefs, read
answer keys, or invoke models. Python callers use `summarize(runs)` from
`eval.rework_report`. Exit code 2 indicates an absent ledger, a run error, or
numeric aggregation failure; output still includes usable runs and error details.
Exit code 0 indicates successfully read ledgers, not complete measurements or a
quality gate pass.

- `runs` retains each unique run's `ok`, `missing`, or `error` status. Empty
  ledgers and runs with all events voided remain valid but have no observations.
- `first_handoff` counts the first effective attempt per measured run;
  `all_attempts` counts every effective handoff. Both expose measured and missing
  run counts. No observed attempts yields JSON `null`, not an assumed zero.
- `return_reasons` counts observed rejections across **all** active attempts.
  Later returns remain visible even when first handoff was accepted.
- `attributed_reason_minutes` sums active effort with an explicit reason, grouped
  by exact text. `attributions` retains run, event ID, actor, role, reason, minutes,
  and correction attribution. Administrative correction/void reasons are not
  themselves counted as work or return causes.
- `observed_attributed_minutes` is the sum of those recorded minutes; absent
  attributed effort yields `null`, while explicitly observed zero yields `0`.
  `unattributed_minutes` and `unattributed_events` expose effort without a reason.
  `effort_missing_runs` and `reason_minutes_missing_runs` expose coverage gaps.

Reason labels are self-reported and may describe ordinary work, not necessarily
rework. No causal link to a rejection is inferred from matching labels. An empty
reason map does not prove no rework occurred. Counts and observed sums cover only
available events; corrupt or missing runs are never treated as measured zeros.
No automatic synonym grouping, clock-overlap detection, correction authorization
registry, or savings estimate is provided. Each run is read under its own lock;
a cross-run report is not one globally simultaneous snapshot. Files copied into
different run directories are distinct runs; only resolved path aliases deduplicate.

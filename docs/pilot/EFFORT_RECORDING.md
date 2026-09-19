# Synthetic effort recording

Use this recorder only with synthetic fixtures and fictional actor identifiers. It
makes no model or network calls and does not read brief content, answer keys, or
approval artifacts. A PILOT row is the scorecard's measurement format, not evidence
of a real-client pilot or permission to run one. The `live` phase is usable here
only for synthetic rehearsal. Real data remains prohibited.

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
synthetic run path. Minutes must be finite and strictly positive; fractions are
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
ID for a new activity, not to retry an uncertain write. There is no correction or
deletion command in this bounded implementation.

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

Role columns sum recorded events only. An absent role is `not_recorded`, never
zero. `total_attention_min` requires both account roles; `total_team_min` requires
all six roles. A partial record therefore cannot establish a complete total.
The strict positive-minute contract cannot express an explicitly measured zero.
A present role total also does not attest that all work for that role was logged.

`first_handoff_accepted` and `return_reason` describe the first handoff in ledger
recording order. Later handoffs remain in the ledger but do not replace the first
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

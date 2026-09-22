# Attributed campaign editing

These deterministic helpers edit initialized synthetic rehearsal runs. They do not
call models, fetch platform specs, change the canonical brief, or authorize delivery.
Use a Python environment with the project dependencies installed (`python3` on systems
without a `python` alias).

## Checklist answers

```sh
python -m pipeline.agency_edit checklist RUN \
  --key objective_and_audience --value 'Synthetic campaign answer' \
  --owner 'Synthetic account lead' --actor 'Synthetic editor' --ref objectives:0
```

Keys must belong to the run's campaign profile in `config/campaign_profiles.json`.
`--ref FIELD:INDEX` selects a zero-based entry in a canonical brief field, copying
its full evidence objects. Repeat `--ref` to cite multiple entries. Questions and
conflicts are not canonical entry selectors. Unknown fields, absent entries,
incomplete citations, and blank answers or attribution are rejected.

## Deliverables

```sh
python -m pipeline.agency_edit deliverable RUN \
  --id synthetic-artwork --spec-id key_visual_digital_master --quantity 1 \
  --language el --deadline 2026-11-20 \
  --owner 'Synthetic production' --approval-owner 'Synthetic lead' \
  --actor 'Synthetic editor' --ref deliverables:0
python -m pipeline.agency_edit deliverable RUN \
  --id synthetic-story --spec-id instagram_story --quantity 2 \
  --language el --language en --deadline 2026-12-01 \
  --owner 'Synthetic production' --approval-owner 'Synthetic lead' \
  --actor 'Synthetic editor' --ref deliverables:0 \
  --dependency synthetic-artwork --duration-seconds 30
```

A dependency is another deliverable's `--id`, so the predecessor row is added first and is
due on or before its dependent (`handover.validate_dependencies`; `COORDINATION.md`). A free-text
dependency such as a team or asset name is rejected. The static key visual takes no duration.
The command inserts or replaces the asset with the given `--id`. Languages,
dependencies and references can repeat; omitted dependencies become an explicit
empty list. Spec-owned channel, resolution, aspect ratio, format, file type and
textual duration are copied exactly from the chosen catalog row. Duration in
seconds is the asset's selected duration, validated against the row's bounds;
static assets omit it. Existing and new assets must pass `handover.validate`.
The active catalog comes from `input_snapshot.json`'s `channel_specs.path`, falling
back to `config/channel_specs.json` when absent. Snapshot hashes are verified before
editing. The default stub supports rehearsal only.

## Human-supplied release catalogs

```sh
python -m pipeline.spec_catalog RUN /absolute/path/to/human-catalog.json \
  --actor 'Synthetic traffic reviewer'
```

The catalog must have `owner` (legacy `_owner` also accepted), a nonempty `specs`
list, and unique nonempty row IDs. `_stub_notice` is rejected even if empty. Each
row needs:

- `resolution`: positive integer dimensions such as `100x100`.
- `aspect_ratio`: positive integer ratio such as `1:1`.
- Nonempty `format`, `file_type`, and `checked_by`.
- `source_url`: the human's official-source citation, using HTTPS with a nonempty
  host. Syntax validation makes **no claim of authenticity or current accuracy**.
- `checked_on`: `YYYY-MM-DD`, no later than today.
- `review_due`: `YYYY-MM-DD`, no earlier than today or `checked_on`.
- `duration`: `n/a`, an interval such as `1-10s`, or `up to 10s`; alternatively
  numeric `duration_seconds: {"min": 1, "max": 10}`. If both numeric bounds and a
  textual range are present they must agree. Static rows cannot have bounds.

No verified platform values are supplied by these helpers. Tests use reserved
synthetic domains and invented dimensions. Humans supply and review the catalog.
Binding validates every row and requires existing deliverables to still match the
new table. Binding records the resolved path and SHA-256 in the input snapshot,
and actor/time/path/hash in `agency_inputs.catalog_binding`. Keep the supplied
catalog file at that path unchanged; input verification detects subsequent edits.

## API and review behavior

- `agency_edit.checklist(run, *, key, value, owner, actor, refs)` returns the saved answer.
- `agency_edit.deliverable(run, *, id, spec_id, quantity, languages, deadline,
  owner, approval_owner, actor, refs, dependencies=(), duration_seconds=None)`
  returns the saved asset.
- `spec_catalog.validate(table, selected_ids=None, today=None) -> list[str]`
  returns errors; `None` selects all rows. Explicit selections limit metadata
  checks, but global ownership, stub rejection and unique IDs still apply.
  `today` accepts a calendar date or ISO date string; default is the local date.
- `spec_catalog.bind(run, table_path, *, actor)` returns the binding record.

Both editing APIs store `actor`, `updated_at`, and canonical entry selectors in
companion records. Previous companion records are copied to `history/`; old
approval, language review, audit and handover files are archived. Review and
approve the changed revision again. The canonical schema is unchanged.

All mutation paths require `pipeline.revisions.run_lock(run)` around reads,
validation and writes. Integration must provide that shared context manager;
there is no private fallback lock. Validation happens before archival or writes.
JSON replacement uses `revisions.write_json` (atomic per file). Binding updates
two files under one lock, not a crash-atomic multi-file transaction: after an I/O
failure, inspect history and reconcile both records before reviewing again.
CLIs return 0 on success and 2 on validation or filesystem errors.


Catalog changes can make existing deliverables inconsistent. Binding records those
findings in `catalog_binding.recheck_deliverables` and invalidates approval; update the
affected rows with the deliverable command, then review again. This avoids requiring
hand-edited JSON just to move from a rehearsal catalog to a corrected traffic catalog.
The current audit, not that historical list, decides whether row mismatches remain.

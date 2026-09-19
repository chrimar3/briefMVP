# Creative delivery — operator and creative-lead guide

Creative is no longer restricted to shadow use. The owner authorized human-approved
delivery on 2026-09-20; see `docs/OPERATING_DECISIONS.md`. Generated output is a draft.
A separate creative lead approves the exact selected files; release creates a local package.
It does not send messages, upload campaigns or buy media. Fixtures-only data policy still
applies until separately changed; the new lifecycle can be rehearsed with synthetic material.

Use the champion runbook for the client brief. Use this guide after that brief is ready.

## 1. Complete campaign and production requirements

The checklist and deliverable commands copy evidence from canonical entry references.
They remove the need to compose the companion JSON manually:

```sh
python3 -m pipeline.agency_edit checklist RUN --key objective_and_audience --value "Sourced answer" --owner "Account lead" --actor "Reviewer name" --ref objectives:0
python3 -m pipeline.agency_edit deliverable RUN --id launch-master --spec-id APPROVED_SPEC_ID --quantity 1 --language el --deadline 2026-11-01 --owner "Production lead" --approval-owner "Account lead" --actor "Reviewer name" --ref deliverables:0
```

Replace RUN, entry references and values with the actual reviewed synthetic run. Profiles
have different checklist keys; `agency_inputs.json` contains their prompts. Use repeated
`--ref`, `--language` and `--dependency` flags as needed, and `--duration-seconds` for video.
See `CAMPAIGN_EDITING.md` for the complete contract.

Traffic supplies a reviewed specification catalog. Bind a new version explicitly:

```sh
python3 -m pipeline.spec_catalog RUN /path/to/reviewed-spec-catalog.json --actor "Traffic reviewer"
```

Each selected row must have a source URL, checked_by, checked_on and review_due in addition
to its specification values. The validator checks metadata and date validity; a human must
verify that the URL is authoritative and the values are correct. The shipped stub cannot
pass release. No model invents verification dates or a traffic reviewer.

Binding a catalog invalidates previous brief and creative approval. If new specifications
conflict with existing deliverables, update those rows using the guided command and review
again. Use versioned catalog files: modifying a bound file in place invalidates the run's
input baseline. Older catalog copies remain in the evidence archive.

## 2. Finish brief review and select creative

Follow `BRIEF_CHAMPION_RUNBOOK.md` for human source/language review and canonical sign-off.
The original runtime routing remains unchanged; an authorized stage-creative run now produces
CREATIVE DRAFT output. The `creative-shadow` internal identifier is retained for compatibility
with historical evidence, not as a prohibition on delivery.

Every creative factual assertion should cite an entry such as `[brief:objectives:0]`.
Reference indexes start at zero. Mandatories are copied verbatim. Creative ideas can be new;
client/product/audience claims must be grounded. Automated checks validate reference
existence, spec tokens, mandatories and currency claims; they cannot determine whether every
sentence preserves meaning. The human fact-coverage/qualifier checks cover that boundary.

```sh
python3 -m pipeline.delivery register RUN --draft RUN/creative/creative_brief_sonnet.md --actor "Operator name"
```

To include actual selected artwork, repeat `--asset /path/to/file.png`. Supported delivery
assets are PNG/JPEG/WebP/PDF/MP4/MOV. Active SVG is refused; provide a rasterized version.
The operator must choose only files intended for delivery. Registration stores hash-addressed
copies, creates a claim ledger and binds the selection to the current brief. A historical
shadow output can be registered as a new reviewable draft; its original stays unchanged.
Registration is never approval.

## 3. Creative lead approves the selected revision

Inspect the registered creative, all selected assets, claims, approved deliverables and
rights/permissions. Then, and only then, the actual reviewer runs:

```sh
python3 -m pipeline.delivery approve RUN --actor "Creative lead name" --notes "Actual review decisions" --checks all_facts_cited qualifiers mandatories brand_voice deliverables rights_and_permissions client_safe
```

The command requires current brief approval, valid human source/language review, a complete
agency audit, current selected catalog rows and all seven creative checks. It records the
reviewer's attribution; it is not an identity-verification system. No model should execute
this command while pretending to be a human reviewer.

Changing selected creative/assets, changing the brief or companion records, withdrawing a
language review, changing source files or letting the selected specs expire prevents release.
A new draft registration or editing a reviewed companion invalidates the existing approval.
Reapprove only after inspecting the changes.

## 4. Create and inspect the delivery package

```sh
python3 -m pipeline.delivery release RUN --output /path/to/new-delivery-folder
```

The destination must not exist and must be outside RUN. Output includes:

- `creative.md`: the approved creative brief, without the draft banner or internal entry tags.
- Selected creative assets, byte-identical to the approved copies.
- `deliverables.json`: approved structured deliverables, without source evidence or internal notes.
- `release.json`: project/revision, approval attribution and file integrity hashes.

Raw inputs, pipeline manifests, glossaries, audit reports and internal approval notes are
not packaged. Check the package before sharing through the agency's existing process.
Existing delivery folders are never overwritten. File hashes identify content integrity;
they are not a cryptographic identity signature or a rights-clearance service.

## 5. Revised campaigns and shared operation

For changed inputs, start a new run ID. For the same client/project, carry only unchanged
question decisions, then inspect the reported questions that need fresh review:

```sh
python3 -m pipeline.agency carry-decisions NEW_RUN --parent OLD_RUN --actor "Operator name"
```

Approvals and conflict resolutions are never migrated automatically. A matching question
must retain the same full question context and evidence, not just the same wording.
The source-set hashes must also be unchanged: adding or changing source material returns
triage to human review, because it could contain a new answer. Legacy revisions without
source snapshots cannot automatically carry decisions. Saved lineage records
the parent and actor. The operator reviews new answers before amending the canonical brief.

Runner and mutation commands share an OS run lock. A busy run refuses a second operation;
retry when the first completes. Never delete `.run.lock` while a process may be using it.
Locks target local macOS/Linux filesystems, not distributed multi-host storage. Evidence
copies in `evidence/` are hash-verified. They preserve what was used; changed originals still
invalidate freshness rather than silently treating old evidence as current.

Record observed effort and returns using `EFFORT_RECORDING.md`. The two most useful routine
documents are the champion runbook (operating the workflow) and this delivery guide. Tier
release reports are engineering/change records, not daily checklists or client handouts.

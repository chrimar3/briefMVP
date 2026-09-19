# Brief champion runbook — synthetic agency rehearsal

Purpose: preserve information, ask each useful question once, and hand over an identifiable,
reviewed brief. One operator owns a run directory at a time. Account lead owns decisions;
a bilingual reviewer owns meaning/register checks; traffic owns deliverables/specifications.
Name a second trained champion for cover. These are roles, not assumed assigned people.

The repository still permits synthetic fixtures only. The operating terms decision is not
resolved by this tooling. This runbook does not authorize real client data. Creative can proceed to delivery through
`docs/pilot/CREATIVE_DELIVERY.md` after explicit human creative approval.
The existing pipeline model routing is unchanged. Do not switch its models to get a pass.

## 1. Assemble once, reuse approved references

Collect the fixture sources in one project folder. Use the existing intake command documented
in `docs/DEMO_PLAYBOOK.md` for raw text. Always pass the project, glossary and output paths
explicitly. The glossary's client ID must match the project. Do not use a different client's
single default glossary. Never copy answer keys into an input work order.

A reusable client reference pack is JSON with `client_id`, `version`, `approved_by`,
`review_due` (ISO date), and `items`. Each item has a `kind`, `text` and `source` reference.
Kinds: positioning, tone, approved_claim, prohibited_claim, terminology, brand_requirement.
Use only actual human approvals, never an AI-generated approver name.

```json
{
  "client_id": "synthetic-example",
  "version": "1",
  "approved_by": "Synthetic reviewer (rehearsal only)",
  "review_due": "2027-01-01",
  "items": [{"kind": "tone", "text": "Use plain, direct language.", "source": "Synthetic brand guide, section 2"}]
}
```

```sh
python3 -m pipeline.agency client-pack /tmp/synthetic-pack.json --client synthetic-example --output /tmp/synthetic-project/reference-v1.md
```

Expired, unsourced or wrong-client packs fail validation. Materialization refuses to overwrite
an existing version. It creates a background source, so the ordinary pipeline cites it and
surfaces disagreements with campaign material. The pack never silently overrides evidence.
Review its dates before every new campaign; validation checks attribution, not the authority
of a signature or truth of the supplied source reference.

## 2. Run and initialize the agency review

For an authorized synthetic model run, the existing command is:

```sh
python3 pipeline/runner.py --project fixtures/northlight_01 --glossary glossary/meltemi.json --out /tmp/agency-runs --run-id rehearsal-01
python3 -m pipeline.agency init /tmp/agency-runs/rehearsal-01 --project fixtures/northlight_01 --glossary glossary/meltemi.json --profile creative_production --actor "Your name"
python3 -m pipeline.agency audit /tmp/agency-runs/rehearsal-01
```

The runner still uses the pre-existing Claude CLI routing. No model runs are part of the
new deterministic benchmark. The commands above document operation; executing a model run
must respect the current session's model restrictions.

Profiles: `paid_campaign`, `organic_social`, `creative_production`. They are proposed
checklists for agency review, not official agency policy. Select the relevant campaign type.
`init` creates `agency_inputs.json` exactly once. For a copied historical run it records a
human-adopted baseline, not proof that the old outputs were generated from today's sources.
A reviewer must compare those historical outputs with the supplied sources.

Audit exit 0 means the supplemental structural checks and recorded human reviews are complete.
Exit 2 means review work remains; read `agency_audit.md` and `agency_audit.json` in the run.
The source PRD readiness gate still applies; audit never loosens it.

## 3. Review coverage and ask useful questions

`agency_audit.md` lists every extracted field fact and within-source conflict position,
its stable fact ID, and its destinations in fields, questions or conflicts. Missing
extracted content is a blocker. Compare raw sources too: an extractor can miss a fact before
this ledger ever sees it. Evidence linkage alone does not prove that meaning survived.

Repair the brief from validated evidence, or record a justified human exclusion (for example,
a duplicate source fact). An exclusion is visible and attributed, not deletion of history.

```sh
python3 -m pipeline.agency exclude /tmp/agency-runs/rehearsal-01 --fact FACT_ID --actor "Your name" --reason "Specific explanation of why this fact is intentionally excluded"
python3 -m pipeline.agency queue /tmp/agency-runs/rehearsal-01
python3 -m pipeline.agency answer /tmp/agency-runs/rehearsal-01 --id QUESTION_ID --status open --actor "Your name" --text "Reason this question does not block the agreed work" --owner "Account lead" --priority nonblocking
```

`FACT_ID` and `QUESTION_ID` are printed by audit/queue; copy the actual IDs.
The queue groups identical question wording within a field and combines evidence. Possible
similarity or shared conflict evidence is only a human-review hint. Two different questions
about budget must not be merged merely because both concern budget.

Statuses are open, answered, duplicate, not_worth_asking. Record a reason for every disposition;
for duplicates name the surviving question or conflict. Answers also require `--evidence`
with the supporting source reference. Answer history persists across queue regeneration.
If supporting question evidence changes, the old decision is no longer applied automatically.

An answer log does not change the canonical brief. Add new synthetic evidence to the project,
start a new run when inputs change, and update the brief from that evidence. An answered
question still present in the canonical open-question list blocks approval until incorporated.
Human content amendments use a copied, schema-valid canonical JSON with `apply` below.

## 4. Resolve, amend and re-render

```sh
python3 -m pipeline.agency resolve /tmp/agency-runs/rehearsal-01 --index 0 --actor "Your name" --text "Your decision and its rationale"
python3 -m pipeline.agency apply /tmp/agency-runs/rehearsal-01 --candidate /tmp/reviewed-brief.json --actor "Your name" --reason "What was corrected and why"
python3 pipeline/runner.py --project fixtures/northlight_01 --glossary glossary/meltemi.json --out /tmp/agency-runs --run-id rehearsal-01 --stage render
```

Conflict indexes are zero-based as printed by audit. Resolve records the human resolution in
the existing schema, resets sign-off to draft, and archives previous renders and approval.
It preserves both source positions. `apply` validates an explicitly edited candidate,
preserves project identity and records the editor/reason; it never signs off automatically.
Check the resolved direction is represented faithfully in the regenerated documents.

Changed sources, glossary, routing or recorded configuration cause resumed runs to refuse:
use a NEW run ID. Unchanged input can reuse validated extracts for synthesis or the brief for
rendering. A rerun archives invalidated downstream products under `history/`; inspect these
copies to recover or compare work. Do not repeatedly rerun until a failure disappears.
A refusal is evidence: inspect diagnostics and fix the specific cause.

## 5. Complete campaign and deliverables checks

Use the guided commands in `CAMPAIGN_EDITING.md` to fill `agency_inputs.json` with sourced values. Each checklist answer requires `value`,
`owner`, and `evidence` copied from canonical evidence objects. Missing answers stay blank
and block approval. If a requirement is inapplicable, explain that with supporting evidence
rather than inventing a campaign value.

Each deliverable row needs `id`, `spec_id`, positive integer `quantity`, `languages`, ISO
`deadline`, `owner`, `approval_owner`, explicit `dependencies` (empty list if none), and
canonical `evidence`. Copy `format`, `file_type`, `resolution`, `aspect_ratio` from ONE
selected row of `config/channel_specs.json`; provide `duration_seconds` for video. Static
images have no duration. Dimensions from one row and format from another fail the check.

Evidence presence does not prove a quantity or deadline is supported: the human reviewer must
check those assertions. The default table remains a synthetic stub. The brief handover is an approved review
record, not creative release. Bind a verified traffic catalog before delivery; see
`CREATIVE_DELIVERY.md`. Do not interpret a valid stub row as live platform verification.

## 6. Review both languages and approve the exact revision

Compare the raw sources, canonical object, companion checklist/matrix, and both rendered
languages. Check omitted facts, changed meaning, conditional wording, resolved direction,
and brand voice. Record Greek naturalness on the existing 1–5 scale; no new numeric pass
threshold has been invented. Each checked dimension is an explicit human pass judgment.

```sh
python3 -m pipeline.agency attest /tmp/agency-runs/rehearsal-01 --actor "Bilingual reviewer's name" --greek-register 4 --notes "Actual review observations" --checks source_completeness el_meaning en_meaning qualifiers_and_commitments brand_voice
python3 -m pipeline.agency audit /tmp/agency-runs/rehearsal-01
python3 -m pipeline.agency approve /tmp/agency-runs/rehearsal-01 --actor "Account lead's name" --summary "Actual decisions and changes reviewed"
python3 -m pipeline.agency handover /tmp/agency-runs/rehearsal-01
python3 pipeline/publish.py /tmp/agency-runs/rehearsal-01
```

These are human commands, not work orders for an AI to impersonate the reviewers. The role
names above are placeholders to replace with actual people; synthetic tests use fictional
actors only. Approval requires no blocking questions, attributed conflict resolutions,
coverage accounting, completed campaign/matrix checks and current human review. It binds to
the brief, renders and companion records. Changes invalidate it. The canonical JSON remains
the sign-off authority; regenerating a render after approval requires a new review.

Published filenames include client, project, date and content revision. Existing links remain
on their original revision. Share the new paths printed by the publisher; do not infer that
an old link now points to the latest revision. No emailing is automated.

## 7. Measure effort and stop recurring rework

Copy `docs/pilot/scorecard_template.csv` for the rehearsal. EXAMPLE rows do not count as pilot
observations. Use `not_recorded` for missing data. Capture account assembly/review, operator,
strategy, creative and production attention without double-counting people. Traffic records
first-handoff acceptance and the main return reason. Review recurring causes weekly.

```sh
python3 eval/pilot_scorecard.py /tmp/scorecard.csv --output /tmp/scorecard-report.json
python3 eval/pilot_scorecard.py --draft /tmp/original-draft.md --final /tmp/human-edited-final.md
python3 eval/agency_benchmark.py --output /tmp/agency-benchmark.json
```

Use archived original drafts and human-edited final copies for survival; do not compare a
regenerated draft with itself. The scorecard validates arithmetic and reports observed sample
sizes. It does not claim a cash saving or a pilot go/no-go from incomplete measurements.
The benchmark exercises synthetic faults, not fresh model outputs or native Greek quality.


For approved creative release, continue with `docs/pilot/CREATIVE_DELIVERY.md`. For ongoing
effort/handoff recording, use `docs/pilot/EFFORT_RECORDING.md`.

# Tier 6 — Practical agency delivery

User authorization: implement the next ten priorities, remove the creative shadow-only
restriction, commit and push. This supersedes the historical creative restriction, not
fixture-only data handling or human approval. Frozen PRD and canonical schema stay untouched.

Architecture: retain the canonical brief, add an explicitly approved creative document and
claim ledger, and produce immutable curated delivery bundles. Human review is attributed
and bound to content; generated material is never automatically approved. Existing runtime
model routing is unchanged. All development and delegated review uses Codex/Astra.

1. Creative lifecycle: generation produces reviewable drafts; separate creative approval
   and release verify current brief approval. Preserve ability to audit historical shadow files.
2. Claim traceability: creative factual statements cite canonical entry IDs; creative review
   records meaning, qualifiers, brand and mandatory checks. Unknown references block release.
3. Curated delivery: export only approved creative and sourced handover, with an integrity
   manifest, no raw sources, internal comments, audit logs or credential/config files.
4. Decision carry-forward: same client/project, explicit parent revision, unchanged question
   content and evidence only. Changed questions return to human review; approvals never migrate.
5. Evidence preservation: hash-verified source/config copies in the run, retained across reruns.
   Originals still checked for changes; snapshots serve as reproducible historical evidence.
6. Concurrent operation: process-level advisory lock shared by runner and mutation commands,
   including release, with clear busy refusal and automatic cleanup on exit/crash.
7. Guided campaign editing: commands to fill sourced checklist answers and deliverable rows,
   resolving canonical references rather than making operators compose JSON.
8. Traffic catalog: human binding of non-stub, sourced, reviewed and dated specifications;
   expired or incomplete selected rows cannot be used for released delivery.
9. Actual work recording: idempotent attributed effort/handoff events and compatible CSV
   export, missing data retained, phase and per-brief reporting.
10. Reproducible verification: CI deterministic suite, frozen harness read-only grade,
    synthetic benchmark and full draft-to-approved-release regression including stale rejection.

Acceptance: all new failure modes tested; existing frozen exam 17/17; no relaxed legacy
acceptance checks; explicit release/handbook policy update; no actual client delivery made
without a named human approval command. New tools support release but don't fabricate
approvals, traffic verification, staff metrics or new model-quality evidence.

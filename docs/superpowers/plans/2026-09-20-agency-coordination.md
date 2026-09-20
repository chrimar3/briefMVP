# Agency Coordination Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent modules; one Tier 7 commit after integration per project rule.

**Goal:** Reduce repeated account/traffic work while making revision and delivery status explicit for a 50-person agency.

**Architecture:** Extend deterministic companion CLIs; canonical brief/schema remain frozen. Human replies are proposals/evidence, never automatic approvals. Reports are local, no external messages or integrations.

**Tech Stack:** Python standard library, existing gates/jsonschema, pytest.

**Spec:** User authorizes choosing and implementing ten improvements after publishing Tier 5/6. Existing operating boundaries: `AGENTS.md`, `docs/OPERATING_DECISIONS.md`.

## Global constraints

Synthetic fixtures only. Frozen PRD/schema/harness/answer keys unchanged. Current runtime routing unchanged. Named human approvals only. Keep both presentation designs. Preserve untracked `.codex/` and `docs/DECK.md`. Development agents use gpt-6-astra. One tier; commit then stop.

## Ranked tasks and acceptance

1. `pipeline/operations.py`: status(run) inspects live audit, current approvals and creative state; returns stage and actionable blockers, never trusts cached reports. Missing/corrupt runs return explicit errors. Test reviewed versus stale versus uninitialized states.
2. Same module: portfolio(explicit runs) checks each independently, deduplicates resolved paths, reports blocked/error counts and next actions without one corrupt run hiding others. Test mixed runs and aliases.
3. `pipeline/question_exchange.py`: export_questions(run, output) creates a version-bound local pack containing selected unresolved questions and owner/priority; excludes raw source evidence. Tests preserve original queue IDs and refuse overwrites.
4. Same module: import_replies(run, pack, replies, actor) validates identity/fingerprint/question IDs and reply evidence attribution, atomically records review proposals without changing canonical brief/approval. Tests stale/mismatched/duplicate/partial replies and no silent resolution.
5. Same module: impact(before, after) compares same-project canonical records and source hashes, lists changed fields/evidence plus review implications; no automatic resolution. Tests changed-source/unchanged-text and wrong-project refusal.
6. `pipeline/release_control.py`: verify package contents/hashes and path boundaries, optionally match originating run receipt/current approval. Test missing/changed/extra files and forged paths.
7. Same module: withdraw run approval with actor/reason, archive active approvals, record affected release receipts. Integrate current approval guard; prior packages are not remotely recalled. Tests no re-release until fresh human approval and retained history.
8. `pipeline/handover.py`: dependencies refer to existing deliverable IDs; refuse self/duplicate/cyclic edges and predecessor dates later than dependent dates. Test acyclic graph and invalid scheduling through current audit.
9. `pipeline/effort.py`: append-only void/correction workflow, attributed reasons, idempotent IDs, preserve original events, explicit zero effort, export active events only. Tests conflicting replay, unknown targets, totals after correction.
10. `eval/rework_report.py`: summarize observed return reasons and attributed rework minutes over explicit runs without double counting paths, retain missing data and distinguish first handoff from later returns. Tests absent ledgers, corrupt data, corrections and repeated handoffs.

For each module: write meaningful failure tests, implement, run focused tests; review integrations. Final checks: full pytest, frozen 17/17 read-only, agency benchmark12/12, compile and diffcheck. Record evidence and limitations in runs/tier_7_report.md. No claim of semantic accuracy or measured savings from deterministic tests.

## Completion

- [x] All ten scoped deliverables implemented and documented.
- [x] Reply proposals integrated with approval/release holds and attributed dismissal.
- [x] Reproduced review findings fixed: archived-approval withdrawal, incomplete approval metadata,
  new-source impact drift; interruption recovery and approved-reply integration tested.
- [x] Existing renderer tests made portable without removing assertions or adding skips.
- [x] Full and clean-checkout suites: 587 pass, 7 skip, 16 xfail. Harness17/17, benchmark12/12.
- [x] Tier report records limitations and final bounded Astra review outcomes.

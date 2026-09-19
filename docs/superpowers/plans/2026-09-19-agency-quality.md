# Agency quality and repeat-work reduction implementation plan

Goal: implement the ten approved priorities for a 50-person digital agency without changing the frozen canonical schema or operating on real client data.

Architecture: companion JSON records and deterministic CLI tools, using the existing evidence and render contracts. Human judgments remain explicit and attributed. Checks distinguish evidence-link coverage from semantic completeness. No UI, integrations, runtime model-routing changes or automatic conflict resolution.

Approved scope: the ten recommendations in the 2026-09-19 conversation. One improvement release; preserve historical evidence and the alternative presentation design.

## Deliverables and acceptance

- [x] 1. `pipeline/quality.py`: extraction-to-brief coverage accounting, stable fact IDs, destinations and missing-fact findings. Includes internal conflicts. Tests distinguish same anchor in different sources and missing objectives. Evidence linkage does not prove meaning.
- [x] 2. `pipeline/clarifications.py`: persistent queue, exact-question grouping with merged evidence, possible overlap flagged for humans, attributable answers and dispositions. No field-only auto-deduplication or automatic canonical updates.
- [x] 3. `pipeline/revisions.py`: content fingerprint, change report, approval bound to brief/renders/references; safe run preparation and unique immutable publication. Tests reject stale approval and changed-input resume and preserve two same-day projects.
- [x] 4. `config/campaign_profiles.json` and `pipeline/agency.py`: campaign-specific completion checklist with sourced human answers; unknowns remain blockers.
- [x] 5. `pipeline/client_pack.py`: validate and materialize approved, sourced, dated client reference packs as input background documents. No implicit precedence over campaign evidence.
- [x] 6. `pipeline/handover.py`: sourced deliverables matrix, exact row validation of specs, quantities/languages/owners/dependencies; stub spec data cannot claim production readiness.
- [x] 7. `pipeline/quality.py`: render section coverage, source links and explicit bilingual semantic-review attestations bound to content. Greek register rating recorded, no invented quality guarantee.
- [x] 8. `eval/agency_benchmark.py`: deterministic synthetic mutation scenarios, reproducible machine-readable results; do not call runtime models or present this as a new generative benchmark.
- [x] 9. `docs/pilot/BRIEF_CHAMPION_RUNBOOK.md`: executable CLI workflow and recovery, human resolution and approval; preserve fixture-only operating boundary.
- [x] 10. `eval/pilot_scorecard.py`: validated CSV aggregation of measured effort, precision and downstream rework; exclude example rows, reject inconsistent counts, distinguish missing measurements, fix review threshold inconsistency.

## Verification and delivery

- Meaningful unit and integration cases for each interface, including failure paths.
- Full deterministic suite, frozen harness on committed evidence, synthetic agency benchmark.
- No modifications to PRD, frozen schema, answer keys, frozen harness or historical outputs.
- Release report records implemented behavior, verification and limitations: fresh model runs, human semantic evaluation, real platform specifications and operating terms remain separate evidence/owner tasks.
- Commit only release-owned files on main; leave pre-existing untracked files alone.


Completed as a deterministic agency rehearsal release. Added three representative campaign
fixtures and a separate benchmark protocol. Fresh generative runs, real reviewer calibration,
confirmed platform specs and measured agency adoption remain unperformed operational work;
none is represented as measured or approved by the software.

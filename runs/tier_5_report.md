# Tier 5 — Agency quality and repetition reduction

Date: 2026-09-19. User authorized all ten ranked agency improvements. Development release
for synthetic rehearsal, not approval for real client use. Branch: main.

## Delivered

| Priority | Working deliverable | Practical boundary |
|---|---|---|
| 1. Critical information preservation | `pipeline/quality.py` accounts for extracted facts and internal-conflict positions. Synthesis emits `coverage_ledger.json`; agency approval blocks unaccounted facts unless a human records a reasoned exclusion. | Evidence linkage does not prove source completeness or semantic equivalence. Human source review is mandatory. |
| 2. Useful clarification list | `queue` groups exact repeated questions and combines evidence; suggests possible overlaps and shows existing brief context. `answer` persists attributed triage, owner, priority, evidence reference and history. | Semantic duplicates are not automatically deleted. An answer log does not silently update the brief. |
| 3. Safe revisions and approvals | Input/config snapshots, added/deleted source detection, archived downstream outputs, immutable published revisions, field-level diff, current-content approval and human attestation binding. | Single operator per run directory. Legacy evidence is explicitly adopted, not retroactively claimed as verified generation provenance. |
| 4. Campaign completeness | Three configurable profiles with sourced human completion records: paid campaign, organic social, creative production. | Proposed checklists require agency calibration; no invented campaign answers. |
| 5. Approved client references | Validated dated client pack materializes a background source for ordinary pipeline evidence handling. Wrong client, expired, unsourced and unsafe version metadata refused. | Recorded attribution is not an authentication system. No precedence over conflicting campaign sources. |
| 6. Production handover | Structured quantities/languages/dependencies/owners/deadlines with brief evidence. Dimensions, format, file type and duration validated against one spec row. | Existing specification table is still a synthetic stub; all export is SHADOW MODE. |
| 7. Bilingual fidelity | Structural field/statement coverage and question-specific evidence checks, existing render gates, attributed EL/EN meaning/qualifier/voice/source-completeness review. | Greek rating is recorded; no invented numeric approval floor or automated semantic guarantee. |
| 8. Representative evaluation | Three new synthetic campaign folders and 12 deterministic fault injections with positive controls; documented fresh-model evaluation protocol. | No current-routing model outputs generated in this release. Historical Voreas xfails remain. |
| 9. Transferable operation | Champion runbook plus CLI init/audit/queue/answer/resolve/apply/exclude/attest/approve/diff/handover/client-pack. Validated human amendments archive prior content and reset approval. | Reviewers/champions are roles to be assigned by the agency. No custom UI or integrations. |
| 10. Measure actual rework | CSV validation/summary and character edit-distance utility; additional role-time, handoff acceptance and return-reason columns. Fixed <30 versus <=30 inconsistency and field-only duplicate definition. | Example rows excluded, missing values retained; descriptive report is not an overall pilot decision or cash-saving claim. |

## Verification

- `python3 -m pytest -o addopts='' -q`: **434 passed, 7 skipped, 16 xfailed**.
- Frozen harness evaluated using `harness.load_run` + `harness.grade` (without calling its
  report-writing function): graded `runs/tier3` remains **17 pass, 0 fail, 0 skip**.
- `python3 eval/agency_benchmark.py`: **12/12 safeguards**, all three new corpus input gates pass.
- Scorecard CLI on the template reports **zero measured briefs**, not an invented pilot result.
- Compilation passes with `PYTHONPYCACHEPREFIX=/tmp/brief-builder-pycache`; the host's default
  cache is outside sandbox write permission, so the check used an allowed temporary cache.
- `git diff --check` passes.
- Read-only coverage replay: tier3 33 records / 0 unaccounted; each historical Voreas output
  65 / 2 unaccounted. These are evidence-link findings requiring human interpretation.
- Synthetic integration verifies approval, handover, amendment invalidation, changed/new
  sources, withdrawn attestation, reapproval history and extraction history.

## Review

Independent Codex reviewer explicitly selected `gpt-6-astra`. Four reproduced findings were
fixed with regression tests: added sources bypassing freshness, withdrawn attestation not
revoking publication/creative eligibility, overwritten approval history, and extraction
reruns not preserving original extracts. Astra re-review found no remaining concrete blockers in those four fixes; all 34 tests in its reviewed files passed.

## Unperformed / owner work

Fresh model-output evaluation, native Greek calibration, actual campaign KPI/approval records,
traffic confirmation of live specs, named operators/champions, agency operating-account/data
terms and staff pilot measurements remain open. The runbook does not authorize real data.
No model routing was changed to pass a gate. New deterministic modules make zero model calls;
no new runtime model aliases were resolved, and no generation usage/savings are claimed.
The separate review agent used `gpt-6-astra` explicitly; its token usage is not reported here
because the tool did not supply a measured total.

Frozen PRD/schema/harness/answer keys and historical outputs are untouched. Both walkthrough
designs and the alternative can design are retained. Pre-existing untracked `.codex/`,
`AGENTS.md` and `docs/DECK.md` are outside this release.

# Tier 7 — Agency coordination and delivery control

Date: 2026-09-20. User authorized publishing Tier 5/6, then choosing and implementing
ten further improvements. The prior commits `2696632` and `5c386ba` were successfully
published to the existing public repository's main branch before this work began.

## Why these ten

The previous releases established reviewed briefs and creative delivery. The next leverage
for a 50-person agency is coordination: fewer manual status checks, repeat questions,
misunderstood revisions, production handoff errors and untraceable rework. These priorities
were chosen from the current code and operating gaps, not claimed as measured agency ROI.

| Rank | Implemented improvement | Concrete benefit |
|---|---|---|
| 1 | Current project status and next actions | Account/traffic can identify what prevents progress without inspecting multiple JSON files |
| 2 | Explicit multi-project review queue | Deduplicates run paths, surfaces blocked projects first and retains per-project errors |
| 3 | Version-bound clarification packs | Packages selected, triaged questions and owners without copying raw evidence |
| 4 | Attributed reply proposals and explicit dismissal | Removes repetitive reply transcription while preventing silent brief edits or approval of new answers |
| 5 | Revision impact report | Separates canonical changes, citation changes, source versions and live source drift |
| 6 | Delivery-package verification | Detects missing/changed/extra files and checks originating receipts/withdrawal state |
| 7 | Human approval withdrawal | Preserves a record of affected releases and blocks further release without fresh approvals |
| 8 | Deliverable dependency/deadline validation | Rejects unknown predecessors, duplicates, self-links, cycles and impossible date ordering |
| 9 | Append-only effort corrections and voids | Preserves who corrected what and why; distinguishes observed zero from missing effort |
| 10 | Cross-project rework reporting | Separates first-handoff success from later attempts and reports observed reason-attributed effort |

Entry points: `pipeline.operations`, `pipeline.question_exchange`, `pipeline.release_control`,
`pipeline.effort` and `eval.rework_report`. Handover validation is integrated into the existing
agency approval gate. Reply proposals hold current approval/release eligibility until human
review; canonical records and approval files themselves are not silently rewritten.

## Review and regression findings

Independent reviews used `gpt-6-astra` explicitly. Reproduced findings were fixed with tests:
withdrawal after prior approvals had been archived; missing approval metadata falsely showing
release readiness; and newly added source documents missing from impact drift. A simulated
interruption test also verifies withdrawal cannot leave old approvals usable and can recover
through fresh human review. A full reply integration test demonstrates that an already-approved
campaign cannot release while it has an unreviewed reply proposal.

The first hosted CI run of published Tier 6 exposed 20 older renderer tests depending on
ignored workstation-only runs. `tests/review_cases.py` now creates the same asserted scenarios
from committed synthetic Tier 3 data in a temporary directory. No assertions were removed,
no missing-data cases were skipped, and no ignored historical captures were added. These are
explicit renderer scenarios, not purported replays of the original captures.

## Boundaries

All work uses synthetic data and deterministic tests. No runtime model calls, external
messages, real-client ingestion, new UI or integrations. Runtime model routing and frozen
PRD/schema/harness/answer keys are unchanged; alternative presentation/can designs retained.
Development/review agents explicitly used `gpt-6-astra`; no aggregate measured token usage
was supplied, so none is invented.

Status and impact are review aids, not semantic certification. Question packs still need
human selection before sharing. Proposed replies require source verification and an explicit
revised-brief workflow; dismissed replies retain the human's reason. Package verification
without the originating run establishes file integrity only. Withdrawal does not recall or
notify external recipients. Dependency validation does not estimate staff capacity. Rework
reasons are self-reported, not demonstrated causal effects or savings. Path deduplication
does not identify separately copied ledgers. Locks cover local cooperating processes.

Use `docs/pilot/COORDINATION.md`, `QUESTION_EXCHANGE.md` and `EFFORT_RECORDING.md` alongside
the champion runbook. This report is the engineering record. Agency data-policy approval,
named owners, authoritative spec review, fresh generative evaluations and measured pilot
outcomes remain required for production-readiness claims.

## Final verification

- `python3 -m pytest -o addopts='' -q`: **587 passed, 7 skipped, 16 xfailed**.
- Same suite in a temporary clean checkout containing tracked files plus the intended new
  release files, without ignored workstation runs: **587 passed, 7 skipped, 16 xfailed**.
- Read-only frozen harness: **17/17**. Synthetic agency benchmark: **12/12**, three input gates pass.
- Python compilation and whitespace checks pass. Frozen files unchanged.
- Final bounded Astra rechecks cleared the reproduced withdrawal, approval-metadata and
  source-membership findings. No uncleared blockers remained in those reviews.
- Hosted Tier 6 CI's failure and its local portability fix are documented above; this
  report does not claim a hosted pass for the new commit before it is published.

Tier 7 is one completed tier for human review. Pre-existing untracked `.codex/` and
`docs/DECK.md` are excluded. No subsequent tier is started.

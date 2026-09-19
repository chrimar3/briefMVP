# Tier 6 — Human-approved creative delivery and agency operations

Date: 2026-09-20. Branch: main. The owner authorized the next ten improvements,
removed the creative shadow-only restriction and requested commit/push. The revised
boundary is recorded in `docs/OPERATING_DECISIONS.md`; frozen specifications remain intact.

## Delivered

| Priority | Improvement | Agency benefit |
|---|---|---|
| 1 | Separate creative registration, named human approval and local release | Makes creative usable beyond shadow mode without automatic approval |
| 2 | Canonical creative references, mandatory/currency checks and human review checklist | Catches unsupported claims and preserves accountability for meaning and brand voice |
| 3 | Selected, content-bound delivery package with integrity manifest | Reduces packaging mistakes and excludes pipeline records from automatic export |
| 4 | Explicit decision carry-forward for unchanged source sets and question context | Avoids repeated triage while returning changed evidence to review |
| 5 | Hash-verified source/config evidence copies | Preserves the exact material behind a reviewed revision |
| 6 | Shared OS run locks for runner, mutations and publishing | Prevents cooperating operators from overwriting each other's work |
| 7 | Guided sourced checklist and deliverable editing commands | Removes repetitive manual JSON editing |
| 8 | Attributed, dated traffic catalog binding and expiry checks | Prevents release using stub, incomplete or stale selected specifications |
| 9 | Idempotent effort/handoff events, CSV export and phase/per-brief summaries | Measures rework and actual team effort without treating missing observations as zero |
| 10 | CI suite, frozen evidence grade and synthetic benchmark | Makes quality checks repeatable on changes |

## Verification

- Full deterministic suite: **503 passed, 7 skipped, 16 xfailed** using
  `python3 -m pytest -o addopts='' -q`. Existing skips/historical expected failures remain.
- Frozen historical harness: **17/17**, graded read-only without rewriting its report.
- Synthetic agency benchmark: **12/12**, all three corpus input gates pass.
- Python compilation and `git diff --check` pass.
- Frozen PRD, schema, harness and answer keys unchanged. Both presentation designs and
  the alternative can design remain intact.
- GitHub Actions workflow is added; hosted execution is not claimed as tested locally.

## Independent review

Codex review explicitly used `gpt-6-astra`. Review covered locks, approval invalidation,
catalog rebinding, evidence preservation and creative release. A reproduced manifest
bypass could substitute raw evidence before creative approval. The fix binds every file
to its exact registered revision path, refuses symlink redirection and recomputes the
payload digest. Two regression tests failed before the fix and passed after it. Final
bounded re-review cleared that blocker; all 13 delivery tests passed. Path traversal
and stale decision carry-forward also have regression coverage.

## Operating documents

Use `docs/pilot/BRIEF_CHAMPION_RUNBOOK.md` for daily brief operation and
`docs/pilot/CREATIVE_DELIVERY.md` for creative-lead review and release. Use
`CAMPAIGN_EDITING.md` and `EFFORT_RECORDING.md` for those commands. Tier reports are
engineering acceptance/change records; they are not client deliverables.

## Boundaries and remaining validation

Release creates a local inspectable package; it does not send or publish campaigns.
Fixtures-only remains in force. No real client data or new model generation was used.
The operator selects artwork and the human reviewer confirms that every selected file
and the creative prose are suitable for the recipient. Asset extension checks are not
malware scanning, and factual-reference checks do not prove semantic truth. Reviewer
names are attribution, not authenticated identities. Local advisory locks are not a
multi-host collaboration system. Catalog URLs/dates require actual traffic verification.
The supplied catalog remains a stub and deliberately cannot pass creative release.

Current runtime model routing is unchanged; no runtime model aliases were newly resolved.
Development/review subagents used `gpt-6-astra` explicitly. No measured aggregate development
usage was supplied by the tool, so no token/cost estimate is invented. Fresh generative
quality evaluation, Greek-language calibration, named agency owners, operating/data terms
and actual staff pilot measurements remain necessary before claiming production readiness
or realized savings. Pre-existing `.codex/` and `docs/DECK.md` remain outside this release.

"""Brief Builder pipeline — deterministic orchestration around thin AI edges.

`gates.py` holds every decision the system makes without a model.
`runner.py` sequences the steps of PRD §5.
"""

#: Single version identity, stamped into both run_manifest.json and brief.meta.pipeline_version.
#: Bump on behaviour change; never derive a version from the repo folder name — the pipeline
#: runs on any folder. Minor bumps are additive (older manifests stay readable).
#:   1.0.0  Tiers 0–4 complete (full Stage 1 + shadow Stage 2, harness-green).
#:   1.1.0  Independent verify-extract step per source, risk-routed (routing decision 2026-07-30).
#:   1.2.0  Tier 5: input snapshots, run lock, history archiving, changed-input refusal.
#:   1.3.0  Tiers 6–7: human-approved creative delivery, release control, coordination.
#:   1.4.0  Review round 1: corrupt resume artifacts reported by name with outcome
#:          `corrupt_artifact` (no longer "[run lock]"), read-only status views, and the other
#:          round-1 contract changes recorded in docs/OPERATING_DECISIONS.md (2026-09-22).
PIPELINE_VERSION = "1.4.0"

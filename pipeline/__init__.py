"""Brief Builder pipeline — deterministic orchestration around thin AI edges.

`gates.py` holds every decision the system makes without a model.
`runner.py` sequences the steps of PRD §5.
"""

#: Single version identity, stamped into both run_manifest.json and brief.meta.pipeline_version.
#: 1.0.0 = Tiers 0–4 complete (full Stage 1 + shadow Stage 2, harness-green). Bump on behaviour
#: change; never derive a version from the repo folder name — the pipeline runs on any folder.
PIPELINE_VERSION = "1.0.0"

# Archived walkthrough scripts (historical, unmaintained)

These scripts did one job once, during the September 2026 walkthrough rounds, and are kept only
so the record of how the page was built stays inspectable. Nothing in the pipeline, the tests or
CI runs them, and they are not maintained: most assert exact page text that has since changed, so
re-running one today would fail its own assertions or edit the wrong thing.

| File | What it did |
|---|---|
| `edit_r7.py`, `edit_r8.py` | Claude-era editor passes for review rounds 7 and 8 (asserting text replacements on `WALKTHROUGH.html`). |
| `swap_kv.py` | Swapped the sheet-09 key-visual SVG for a chosen logo direction. |
| `compare_cans.py`, `compare_logos.py` | Built the one-off can and logo comparison pages (`can_comparison.html`, `logo_directions.html`). |
| `codex_redesign.py` | Research-then-build chain for the v2 redesign, which the owner retired on 2026-09-22 (`docs/OPERATING_DECISIONS.md`). |
| `score-round-v2.js`, `score-round-v3.js`, `score-round-opus.js` | Claude workflow scripts for review rounds 7–8, superseded by `../codex_round.py`. They still embed the author's absolute checkout path in their prompts. |

The Python scripts derive the repository root from their own location (three levels up), so they
no longer depend on one workstation. The maintained tools stay one level up: `checks.py` (the
deterministic page gate), `build.py` (artifact variant), `codex_round.py` (review round) and
`embed_packaging.py`.

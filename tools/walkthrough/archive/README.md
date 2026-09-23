# Walkthrough archive (historical, unmaintained)

Everything here is the production record of `WALKTHROUGH.html`: review rounds, editor prompts and
reports, page backups, logo and packaging image variants, and the retired v2 redesign. It is kept
so the record of how the page was built stays inspectable. Nothing in the pipeline, the tests or
CI reads or runs it, and none of it is maintained: most scripts assert exact page text that has
since changed, so re-running one today would fail its own assertions or edit the wrong thing.

**Paths inside archived files refer to the layout before round 2** (when this material sat
directly under `tools/walkthrough/`): read `tools/walkthrough/<x>` in an archived record as
`tools/walkthrough/archive/<x>` (notes moved to `notes/`, `kv_*.png` to `images/`). The records
themselves are not edited.

The maintained tools stay one level up: `checks.py` (the deterministic page gate, run by
`scripts/check.sh`), `build.py` (artifact variant), `embed_packaging.py` (sheet-09 packaging
plate) and `mustkeep.json` (the curated regression list of page facts).

## Index

| Path | What it is |
|---|---|
| `codex_round.py` | The Codex review-round runner for rounds 9–11 (one `codex exec` session per auditor, audience task and judge, deterministic aggregation). Superseded by the whole-project review loop in `tools/project_review/`. |
| `codex_round/` | Round records r9, r10, r11 (`report.md`, `result.json`, prompts, JSON outputs) and the strict JSON output `schemas/` the runner used. |
| `round8_args.json`, `round10_args.json`, `round11_args.json` | Per-round inputs of the runner (previous averages, `mustKeep`, previous hard failures). |
| `notes/codex_*.md` | Codex editor, image and logo passes: each `*_prompt.md` is the prompt, the matching `.md` is Codex's report. `codex_context.md`, `codex_priorities.md`, `codex_review.md`, `codex_fix.md` are working notes. |
| `notes/open_items.md`, `notes/status_2026-09-17.md` | Round-6 open-item list and a status note from 17 September 2026. |
| `backups/` | Page snapshots taken before each editor pass (`before_r7_edit.html` … `before_r11_edit.html`, key-visual and can swaps). |
| `images/kv_*.png` | Packaging and can mock-ups generated for sheet 09 (the page embeds its chosen image as a data URI; these are the sources and rejected variants). |
| `logo/` | The three logo directions and the final "Meltemi Hand" lockup variants (SVG and PNG renders, notes). |
| `can_comparison.html`, `logo_directions.html` | One-off comparison pages built by `compare_cans.py` and `compare_logos.py`. |
| `redesign/` | The v2 redesign, retired by the owner on 2026-09-22 (`docs/OPERATING_DECISIONS.md`); see `redesign/RETIRED.md`. |
| `edit_r7.py`, `edit_r8.py` | Claude-era editor passes for review rounds 7 and 8 (asserting text replacements on `WALKTHROUGH.html`). |
| `swap_kv.py` | Swapped the sheet-09 key-visual SVG for a chosen logo direction. |
| `compare_cans.py`, `compare_logos.py` | Built the two comparison pages above. |
| `codex_redesign.py` | Research-then-build chain for the v2 redesign. |
| `score-round-v2.js`, `score-round-v3.js`, `score-round-opus.js` | Claude workflow scripts for review rounds 7–8, superseded by `codex_round.py`. They still embed the author's absolute checkout path in their prompts. |

Lint (`ruff`) excludes this folder (`pyproject.toml`), because the records are kept as they were run.

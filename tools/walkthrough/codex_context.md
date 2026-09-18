# Context for the review

## What is being reviewed
- `WALKTHROUGH.html` at the repo root: a single self-contained HTML page (zero dependencies, opens from a double-click) that presents the "Brief Builder" pipeline to stakeholders of all backgrounds as a whole product: 10 sheets, Next/Back navigation, consulting-style storyline (answer first, action titles, evidence, decisions). Sheet 09 shows a shadow-mode creative brief with an inline-SVG key visual. Sheet 10 shows usage in tokens (not API dollars — the client will run on a subscription) and the decisions a pilot needs.
- The approach used to improve it: a benchmark of the earlier 15-sheet version, then a loop — three LLM judges score nine aspects 1–10 each round (concision, completeness, clarity, storyline, product_framing, visual_design, fact_fidelity, ux, finale), an editor applies their fixes under a deterministic check script (verbatim quotes vs fixtures, ≤10 sheets, word budgets, brand palette and clear space in the SVG, no external resources), re-score, target: every aspect averaging above 8.

## Score history (averages of 3 judges, 1–10)
- Benchmark (15-sheet v1): concision 4.67 · completeness 7 · clarity 7 · storyline 7 · product 7.33 · visual 7.67 · facts 7.33 · ux 8 · finale 7
- Round 1 (10 sheets, before edits): 6 / 7 / 7 / 7 / 8 / 7.67 / 6 / 8 / 7
- Round 3: 7 / 8 / 8 / 8 / 8 / 8 / 8 / 8 / 7.67
- Round 4: 7 / 7.67 / 8 / 8 / 8.33 / 8 / 8 / 8 / 8
- Round 5: 6.33 / 8 / 7.67 / 8.33 / 8.67 / 7.67 / 8.67 / 7.67 / 7.67
- Visible words per sheet now: 395 · 567 · 472 · 363 · 334 · 438 · 375 · 344 · 622 · 646 (total 4 556, ledgers excluded)

## Ground truth to check against
- `runs/tier3/` (graded run: run_manifest.json, harness_report.json 17/17, brief.json, renders, creative drafts), `fixtures/northlight_01/` (synthetic sources + brand guidelines), `docs/PRD.md`, `docs/COST_MODEL.md`, `docs/EVIDENCE.md`, `docs/demo_timing.md`, `config/channel_specs.json`.
- Constraints that must hold: at most 10 sheets; zero external dependencies; every quotation verbatim from the fixtures; no numeric budget total ("in the eighties" must stay words); creative output labelled shadow mode; tokens (not dollars) as the visible usage figure; the key visual uses only #1B4F8A, #F5C518 and white with flat fills.

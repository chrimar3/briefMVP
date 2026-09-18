# Handoff — the stakeholder walkthrough (`WALKTHROUGH.html`)

Written 2026-09-16 at the end of a long session. Read this first in a fresh chat; then `tools/walkthrough/open_items.md` and `tools/walkthrough/codex_review.md`.

> **Update 2026-09-17:** see the section *Session 3 (16–17 September)* at the end before acting on anything above; the Codex fix run finished, the judge loop changed method (`score-round-v3.js`), and a packaging mock-up decision is pending.

## What exists

| Thing | Where | Notes |
|---|---|---|
| The page (source of truth) | `WALKTHROUGH.html` (repo root, **untracked**) | Single self-contained HTML, zero dependencies, opens from a double-click. Ten sheets, Next/Back, consulting storyline, tokens (not dollars) as the usage figure, shadow creative brief with an inline-SVG key visual on sheet 09. |
| Published artifact (same content) | https://claude.ai/code/artifact/c9a193d1-f5f5-48a0-8365-322b00e3ce0e | Title "A Brief With Receipts". To republish from a new chat: run `python3 tools/walkthrough/build.py` and publish `tools/walkthrough/a_brief_with_receipts.html` with the Artifact tool passing `url` = the link above (otherwise a new artifact is created). |
| Tooling | `tools/walkthrough/` (**untracked**) | `build.py` derives the artifact variant (strips doctype/html/head/body, turns repo-relative links into spans). `checks.py` is the deterministic gate (exit 0 = green). `score-round-opus.js` is the judge workflow. `open_items.md` = 42 reconciled fixes. `codex_review.md` = Codex's review. `backups/before_codex_fix.html` = the page before Codex touched it; `backups/benchmark_v1.html` = the 15-sheet version that was benchmarked. |
| Memory | `~/.claude/projects/-Users-chrism-AI-transformation-assignment-brief-builder/memory/` | `project-status.md` (history), `tokens-not-dollars.md` (the usage-not-price rule), `working-agreements.md`. |

Nothing from this work is committed. Committing `WALKTHROUGH.html` + `tools/walkthrough/` (and `HANDOFF_WALKTHROUGH.md`) is the owner's call; `docs/DECK.md` stays untracked as before.

## Rules the page must keep (checks.py enforces most)

- At most 10 sheets; folios, `CH` array and contents overlay in sync; unique ids.
- Every `<blockquote>` and `<mark class="cited">` is verbatim from `fixtures/northlight_01/`; never edit them.
- Zero external resources; system font stacks only.
- Palette: paper `#F1F2EC`, ink `#1A1A18`, pencil `#5A5D55`, red `#C8102E` only where a person decided; `#1B4F8A` / `#F5C518` only inside the sheet-09 SVG, flat fills, **no opacity attributes**.
- Usage is shown as tokens by model (client will most likely be on a subscription); dollars only in the sheet-10 ledger footnote "for readers on API terms".
- The budget stays "in the eighties" (no invented or resolved total); creative output is labelled shadow mode and mock-up.
- Action titles ≤ 24 words, takeaways ≤ 20 words, ≤ 650 visible words per sheet (750 on sheet 09), facing pages non-empty, three top-level decisions, mock-up label inside the 9:16 crop.
- Thousands separator in numbers is U+2009 (thin space), e.g. `598 743`.

## Where the numbers come from (all synthetic)

- Graded run `runs/tier3/run_manifest.json`: stage one 984 820 tokens in 9 sessions (Haiku 4.5 533 641; Sonnet 5 451 179), 56% cache reads · 27% cache writes · 16% output · 0.3% fresh input; all-in 1 134 734 with the creative A/B (Sonnet 86 441, Opus 63 473). Stage times sum to 33 min; the continuous 29 July capture ran 25.2 min with one re-roll (`docs/EVIDENCE.md`).
- Routing validation `runs/routing-validate-01`: transcript extraction 598 743 tokens (two Sonnet passes 91 918 + 462 130, second reader 44 695) vs 295 774 on the graded run.
- Harness 17/17 (`runs/tier3/harness_report.json`); second fixture voreas 15/17 then 16/17 (`runs/voreas_prep_report.md`).
- Repository discrepancies found and **not edited** (owner's call): `docs/EVIDENCE.md` says the manifest totals $4.29 (raw double count; de-duplicated $3.55); `docs/COST_MODEL.md` §3 says ~€5–6k/yr returned hours, but PRD A1/A2/A4 with the §2 50-minute target give ~210 h ≈ €4.0–4.2k; `config/channel_specs.json` declares itself a stub; `runs/tier3/creative/creative_brief_opus.md` calls the TikTok dance "retracted" (it was speculative; the metro idea was the retraction); `pipeline/review.py` makes a review view, not an approval editor.

## The improvement loop and its scores

Rubric: nine aspects, 1–10 each, three judge personas (consulting partner, design director, CMO+CFO pair); target = every aspect averaging **above 8**. Judges run as a Workflow (`tools/walkthrough/score-round-opus.js`, args `{round: N}`, model `opus` because Fable judges hit the usage cap). Editing has been done by me with asserting Python passes, and now by Codex (see below).

| Round | concision | completeness | clarity | storyline | product | visual | facts | ux | finale |
|---|---|---|---|---|---|---|---|---|---|
| Benchmark (15 sheets) | 4.67 | 7 | 7 | 7 | 7.33 | 7.67 | 7.33 | 8 | 7 |
| 1 (10 sheets, raw) | 6 | 7 | 7 | 7 | 8 | 7.67 | 6 | 8 | 7 |
| 3 | 7 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 7.67 |
| 4 | 7 | 7.67 | 8 | 8 | 8.33 | 8 | 8 | 8 | 8 |
| 5 | 6.33 | 8 | 7.67 | 8.33 | 8.67 | 7.67 | 8.67 | 7.67 | 7.67 |
| 6 | 7.33 | 6* | 7.67 | 7.67 | 8.67 | 7.33 | 8 | 7.67 | 7.33 |

\* Round 6 was scored on a build where my trim script had emptied the two bilingual pages on sheet 06; restored from backup, and `checks.py` now fails on empty evidence blocks. Round 2 had one judge only (6/8/7/7/8/7/8/7/7).

The loop is **oscillating, not converging** (rounds 3–5 average ≈ 7.85 → 7.89 → 7.85): concision falls as fact-driven qualifications are added. Codex (`gpt-6-astra`) rated the presentation 7/10 and the method 6/10 and recommends: freeze each candidate by file hash per review; anchor the rubric in audience tasks (CMO explains the benefit, CFO reproduces the economics, creative director separates evidence from hypothesis, engineer states the operating boundary); split hard failures (wrong arithmetic, unsupported guarantees, missing exhibit, broken interaction) from scored preferences; give judges distinct roles; give the editor a bounded hypothesis per round; stop on two stable reviews with no hard failures rather than chasing averages.

## What is running / was running when the session ended

A Codex fix run was started 2026-09-16 (session id `01a0aad9-1c9a-72f0-810b-c11c1c173a24`), detached with `nohup`:

```
cd /Users/chrism/AI-transformation-assignment/brief-builder
codex exec -m gpt-6-astra --approve-for-me --add-dir tools/walkthrough -o tools/walkthrough/codex_fix.md "<apply open_items.md, run build.py && checks.py until green>" < /dev/null
```

It edits only `WALKTHROUGH.html` and must end with `checks.py` green. Its report lands in `tools/walkthrough/codex_fix.md`, its log in `tools/walkthrough/codex_fix.log`. To pick up:

```
python3 tools/walkthrough/checks.py          # must exit 0
diff tools/walkthrough/backups/before_codex_fix.html WALKTHROUGH.html | wc -l   # 0 means Codex changed nothing
cat tools/walkthrough/codex_fix.md
```

If the checks are red or the page is broken, restore: `cp tools/walkthrough/backups/before_codex_fix.html WALKTHROUGH.html`. If Codex never finished, run the items yourself from `open_items.md` (sections A–H; item 41's opacity removal is what the gate currently flags).

Codex CLI notes: installed at `~/.npm-global/bin/codex` (0.154.0), logged in via ChatGPT. `--full-auto` is not an `exec` flag; `--approve-for-me` cannot be combined with `--sandbox`; always close stdin (`< /dev/null`) or the run waits forever.

## Suggested next steps

1. Verify the Codex edits (above), republish to the same artifact URL, run round 7 (`Workflow` with `score-round-opus.js`, args `{round: 7}`).
2. Adopt Codex's method changes before spending more rounds; in particular add hard-fail checks for required exhibits and figures, and stop on stability.
3. Decide on committing the page and tooling, and on fixing the repository discrepancies listed above (`docs/PRD.md` is read-only by project rule; `COST_MODEL.md` and `EVIDENCE.md` are not).
4. Optional: a dedicated 9:16 layout for the key visual (the shared lockup sits in TikTok's caption zone in that crop) and a real image if the creative team supplies a logo file.


## Session 3 (16–17 September) — what changed

**Codex fix run: done.** 42/42 items applied, gate green; report `tools/walkthrough/codex_fix.md`; the page as Codex left it is `tools/walkthrough/backups/after_codex_fix.html`. I then made five small edits (visible Limits block restored on sheet 10; a sentence glitch; Codex had written `&#107;` for the "k" in the quoted Draft A total to slip past the X3 regex, replaced by `<mark class="flag">` and `checks.py` now decodes entities before the X3 check and exempts text the page itself strikes or flags; CSS for `.blockers`, `.decision-record`, `.legend .red`).

**Judge method changed (Codex's recommendations adopted).** `tools/walkthrough/score-round-v2.js` (used for round 7) and `score-round-v3.js` (use this from round 8: the same, with auditors, audience tasks and judges running concurrently, plus `mustKeep` / `prevHard` regression inputs). Per round: hash-frozen candidate (`args.hash`; every agent verifies `shasum -a 256` first), a repository-fidelity auditor and a rendered-UX auditor list hard failures with evidence, two skeptics try to refute each, four audience tasks (CMO explains, CFO reproduces the economics, creative director separates evidence from hypothesis, engineer states the operating boundary), the three original personas score the nine aspects for the time series, and a deterministic verdict: **stable = no hard failures + all tasks pass + no aspect down ≥ 0.5 vs `args.prev`**. Stop on two consecutive stable reviews, not on averages above 8. Never edit `WALKTHROUGH.html` while a round runs (the hash freeze makes every later agent abort).

**Round 7 (hash 69f5799e…): partial.** Auditors, six verifiers and three of four audience tasks ran; the creative-director task, the three judges and the editor brief died on the Claude session limit (resets 23:30 Athens). One hard failure confirmed by both skeptics in headless Chrome (sheet 08's three summary rows overlapped at ≤560px). `tools/walkthrough/edit_r7.py` applied 26 edits (3 hard, 11 factual precision, 12 UX/CSS) → gate green, hash `e7c06bfa…`, artifact republished. Audience-task gaps still open (not in the repository, do not invent): the euro cost of running the pilot (operator, training, subscription), the runbook path, the `brief.json` field that holds a resolution's rationale, dated ids for sonnet/opus (the manifest has none), and one review-time target (sheet 07: under 30 min review; sheet 10: 50 min attention = 20 assembling + 30 reviewing).

**Packaging mock-ups (owner's request, Codex `imagegen` skill, built-in `image_gen`, no API key).** Bottle first (`tools/walkthrough/kv_packaging_mockup.png`), then two cans: `kv_can_A_previous_logo.png` (the sheet-09 SVG lockup with the five wind lines; reference rendered with `qlmanage` from the SVG after replacing `&middot;`, XML has no HTML entities) and `kv_can_B_bottle_label.png` (the bottle label, upright leaf). Comparison page: `tools/walkthrough/compare_cans.py` → `can_comparison.html`, published as artifact https://claude.ai/code/artifact/95d04ba8-b73e-498a-b3fc-b8a5598fbde4. Prompts: `codex_imagegen_prompt.md`, `codex_cans_prompt.md`; reports `codex_imagegen.md`, `codex_cans.md`. Caveat recorded for the owner: the brand guidelines forbid any alcohol association and a slim can reads as hard seltzer; both cans were specified as standard 330 ml. **Pending: the owner picks A or B.** Then:

```
python3 tools/walkthrough/embed_packaging.py --src tools/walkthrough/kv_can_A_previous_logo.png   # or B; --caption/--alt to adjust the slug
python3 tools/walkthrough/build.py && python3 tools/walkthrough/checks.py && shasum -a 256 WALKTHROUGH.html
# republish tools/walkthrough/a_brief_with_receipts.html to the artifact URL above, then
# Workflow scriptPath=tools/walkthrough/score-round-v3.js args={round: 8, hash: <sha256>, prev: {round: 5, averages: {...}}, prevHard: [...], mustKeep: [...]}
```

`embed_packaging.py` adds a second plate row on sheet 09 (JPEG data URI ≤ 1100 px, about 75 KB) and the slug says the image was generated for the walkthrough by an image model; packaging is an undefined context in the brief.

**Later on 17 September — logo redesign (owner: the original lockup was "generic, not ownable"; territory: the wind itself; designer: Codex gpt-6-astra at the owner's instruction).** Three directions under `tools/walkthrough/logo/` (`dir1..3.svg`, renders, `directions.md`), presented at https://claude.ai/code/artifact/512dc1c5-b0cb-47a4-8e9a-bce85c41e614 (built by `compare_logos.py`). The owner chose 1, "Meltemi Hand", adjusted to the client's own words (brief: `codex_logo_refine_prompt.md`; result `logo/dir1_final.svg` with `notes.md` citing transcript 00:06:02 / 00:03:41 / 00:02:05, the guidelines' tone, RFP §4, Draft B §3–4). Swapped into the sheet-09 SVG with `swap_kv.py` (backup `backups/before_kv_swap.html`), page descriptions updated, gate green, hash `1bfd627d…`. Known design caveat: the two bubbles sit slightly detached from the second crest. Codex's can render from the final lockup → `kv_can_final.png` (brief `codex_can_final_prompt.md`); embed with `embed_packaging.py --src tools/walkthrough/kv_can_final.png --alt … --caption …`, then build, checks, republish, then round 8 with `score-round-v3.js` and `round8_args.json` (fill the hash). Codex's leverage assessment of everything pending: `tools/walkthrough/codex_priorities.md` (it ranks the pilot's account/data terms, a scorecard, the Voreas regression cases, the runbook and a re-baseline above any further visual work).

## 18 September — round 8, the alternative lockup, and the leverage items

**Round 8 (v3 method, hash `b9f33cf6…`)** ran its four audience tasks; both auditors and the three judges died on the session limit at midnight, so it carries no hard-failure audit and no scores (its "no hard failures" is vacuous). The creative-director task FAILED (sections 3–6 absent from the sheet; a strike it could not see; "three things" that were four); the CMO, CFO and engineer passed but agree on the gaps: cost of running, where documents go, a plain definition of a token, the mechanism for recording resolutions. `tools/walkthrough/edit_r8.py` applied a bounded pass of 18 edits plus four trims (sheet 09 sits exactly at its 750-word cap): the feel/tone/reasons-to-believe block condensed onto sheet 09, the strike shown in context, the spec-gate's negative stated, "three strikes, one call", the token tile in plain words, a visible "Where the documents go" note on sheet 02 (the runner refuses S2–S3 before drafting: `pipeline/gates.py enforce_sensitivity_tier`), the savings claim in prose, the sheet-10 headline naming the cost gap, decision 3 caveated for the routing change, and the resolution mechanism named (`brief.json › conflicts[n].resolution / resolved_by`, `signoff{}`; a one-page runbook is a week-1 deliverable, none exists yet). Gate green, hash `3a285fde…`, artifact republished ("Round 8 audience fixes"). Backup: `backups/before_r8_edit.html`.

**Alternative lockup** (the design lead's caveat, produced by Codex): `logo/dir1_final_alt.svg` moves only the two bubble centres so the large bubble breaks off the second crest's shoulder (`alt_notes.md`). Not on the page; if chosen: `swap_kv.py --src tools/walkthrough/logo/dir1_final_alt.svg`, re-render the can (`codex_can_final_prompt.md` with `dir1_final_alt_sq.svg.png` as the reference), embed, gate, republish. Codex's own "strongest alternative" among the three directions was Northbound (`dir3.svg`).

**Leverage items 1–3** (Codex's ranking in `tools/walkthrough/codex_priorities.md`), drafted by a reviewed workflow: `docs/pilot/OPERATING_TERMS.md` (decision record: account and data terms, permitted data, the fixture-only boundary and its blast radius, a before-week-1 checklist), `docs/pilot/SCORECARD.md` + `scorecard_template.csv` (every PRD §7 target defined and measurable; assembly, review and total attention separated; critical-error classes from the Voreas report), `tests/test_regression_voreas.py` (the documented Voreas failures as deterministic cases over stored artifacts; known-open defects marked strict xfail so the suite stays green while the case is on record). Nothing in these touches the frozen harness, gates, schema or PRD.

Ignored from now on (`.gitignore`): `tools/walkthrough/*.log` (Codex run logs) and `tools/walkthrough/_s*.js` (gate byproducts).

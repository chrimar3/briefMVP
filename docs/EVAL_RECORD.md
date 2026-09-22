# Evaluation record

**Status:** current. Written 2026-09-23 in review loop round 1 (workstream W3). The numbers below
update whenever the tools are re-run on new evidence, and the round-2 re-baseline (§7) replaces
§1's single-era table.

This page says what the graded evidence measures and what it does not. It covers pass rates, the
held-out contamination, the post-freeze harness edit, the harness blind spots, and the protocol
for the live re-baseline the owner has authorised. Usage in tokens is in `docs/COST_MODEL.md`.
Verified output defects in the graded run are in `runs/tier3/KNOWN_DEFECTS.md` and
`runs/tier3/creative/KNOWN_DEFECTS.md`.

**Where the numbers come from.** Figures marked **[committed]** come from run directories committed
to this repo (`runs/tier3`, `runs/voreas-prep-02`, `runs/voreas-prep-03`; `runs/routing-validate-01`
was committed at the round-1 integration, after the tables below were measured, so its one extract
is counted in the local-store rows), so any clone reproduces them. Figures marked **[local store]** come from the gitignored run directories on the
operator's machine, read with the same tools on 2026-09-23. The tools never read an answer key:
`pass_rates.py` reads the harness's own verdicts, and `supplementary.py` reads only sources
returned by `pipeline.gates.discover_sources`.

## 1. Per-check pass rates — every stored harness report

`python3 eval/pass_rates.py runs --markdown` reads each `harness_report.json` together with its
`run_manifest.json`. **Every graded report is Haiku-era** (haiku extraction, no verifier). No
harness-graded run exists under the current routing (sonnet extraction + verify-extract,
2026-07-30).

Resumed runs re-grade earlier legs, so each check is counted twice:

- **per report**, and
- **per distinct leg**: the session IDs of the stage whose artifact the check grades. That is
  extraction for T1.x; synthesis for T2.1, T2.2, T2.6, T3.1, T3.2, T3.4, X1 and X2; synthesis plus
  render for T2.3–T2.5, T3.3 and X3.

The Wilson 95% interval is computed over distinct legs. Re-rolls graded into the same run
directory overwrote the earlier `harness_report.json`, so those outcomes are lost and not counted.

### northlight_01 · Haiku-era — 13 reports [local store], of which 1 is committed (`tier3`)

11 reports are full 17-check reports; 10 are 17/17. `20260724-012939` and `20260724-013512` are
4-check Tier-1 (extraction-only) gradings. One report (`20260724-021459`) has a manifest that
records only its render step; its legs count as unknown.

| check | pass / reports | pass / distinct legs | Wilson 95% (legs) |
|---|---|---|---|
| T1.1 | 13/13 | 10/10 | 0.72–1.00 |
| T1.2 | 13/13 | 10/10 | 0.72–1.00 |
| T1.3 | 12/13 | 9/10 | 0.60–0.98 |
| T1.4 | 12/13 | 9/10 | 0.60–0.98 |
| T2.1 | 11/11 | 9/9 | 0.70–1.00 |
| T2.2 | 11/11 | 9/9 | 0.70–1.00 |
| T2.3 | 11/11 | 10/10 | 0.72–1.00 |
| T2.4 | 11/11 | 10/10 | 0.72–1.00 |
| T2.5 | 11/11 | 10/10 | 0.72–1.00 |
| T2.6 | 11/11 | 9/9 | 0.70–1.00 |
| T3.1 | 11/11 | 9/9 | 0.70–1.00 |
| T3.2 | 11/11 | 9/9 | 0.70–1.00 |
| T3.3 | 11/11 | 10/10 | 0.72–1.00 |
| T3.4 | 11/11 | 9/9 | 0.70–1.00 |
| X1 | 11/11 | 9/9 | 0.70–1.00 |
| X2 | 11/11 | 9/9 | 0.70–1.00 |
| X3 | 10/11 | 9/10 | 0.60–0.98 |

The failures: `20260724-012939` failed T1.3 (citations) and T1.4 (garbling). `cost-c1` failed X3,
an invented total. Every 17/17 is one roll of a pipeline with a repair loop, and several of the 13
are resumed legs of each other.

### voreas_02 · Haiku-era — 2 reports [committed]

| check | pass / reports | pass / distinct legs | note |
|---|---|---|---|
| T1.1–T1.4 | 2/2 each | 1/1 | `voreas-prep-03` reuses `voreas-prep-02`'s extracts |
| T2.1–T2.6 | 2/2 each | 2/2 | T2.5 is partly vacuous on this fixture (§4) |
| T3.1 | 1/2 | 1/2 | prep-02 missed C1 and C3 |
| T3.2, T3.4, X1, X2, X3 | 2/2 each | 2/2 | |
| T3.3 | 0/2 | 0/2 | «μπραντ αγουέρνες» never reaches the brief (sticky, `runs/voreas_prep_report.md` Finding 1) |

Scores: 15/17 and 16/17. With n = 2, every interval is wide (Wilson 95% for 2/2 is 0.34–1.00).

## 2. What 17/17 does and does not show

**It shows** that on one synthetic fixture, a Haiku-era run of the pipeline can produce a brief
that recovers every seeded conflict, gap and garble, and that avoids every trap in the answer key.
Every citation resolves verbatim, the readiness block recomputes, and both renders keep the
protected glossary terms. It also shows the check was frozen before the artifacts it grades: the
harness was frozen at Tier 1, commit `9e371f6`.

**It does not show:**

- **Quality under the current routing.** No graded run exists for it (§1).
- **A rate.** The graded run `runs/tier3` was assembled from resumed legs (steps 1–7
  `from_earlier_run`) and included an extraction repair. The 29 July full-pipeline capture needed
  a disclosed synthesis re-roll after trap X1 slipped on the first roll (`docs/EVIDENCE.md`).
  Earlier re-rolls graded into the same directory left no record. §1 is the first pass-rate
  table, and it is small.
- **Generalisation.** There are two keyed fixtures, both synthetic and from the same author. Per
  their harness reports: northlight has 3 required conflicts, 4 gaps (3 required), 2 garbles and
  3 traps; voreas has 4 required conflicts, 6 gaps (5 required), 4 garbles and 3 traps. The held-out one is no longer held out (§3).
  The three `agency_*` fixtures have no answer key and no model run.
- **Precision or reader-visible quality.** The harness grades recall of seeded items. It does not
  see duplicate questions, stale questions after sign-off, silently normalised garbles,
  cross-source misattribution, Greek grammar, or anything in the creative drafts. §4 lists the
  gaps; §5 measures them. The graded run has 31 verified defect entries on record (19 for the
  brief, extracts and renders, 12 for the creative drafts; entry R3 alone lists 9 Greek grammar
  errors). 20 of the entries are encoded as 32 strict-xfail cases in
  `tests/test_regression_northlight.py`.

## 3. Held-out contamination — disclosure

`runs/tier_1_report.md:80` and `runs/tier_3_report.md:177` say that no prompt was tuned against
the answer key. **But the runtime prompts quote the
graded fixture's seeded text verbatim**, so parts of the 17/17 are in-prompt examples. The
quotes, verified with `grep` at round-1 start:

| runtime text | graded fixture text it quotes | graded by |
|---|---|---|
| `skills/SOURCES.md:136–151`, injected copy `.claude/agents/extract.md:159–174` | northlight transcript [00:14:32], the CFO's «κάπου στα ογδόντα, μπορεί ογδόντα πέντε», with its value, anchor and "no €80,000 was written" | budget conflict (T3.1), invented-total trap X3 |
| `skills/SYNTHESIS.md:12`, `.claude/agents/synthesize.md:36` | «κάπου στα ογδόντα» → "around eighty (units unstated)" | same line |
| `skills/TRANSCRIPTS.md:12, :20`, `.claude/agents/fidelity-check.md:36, :44` | «μπραντ αγουέρνες» ≈ "brand awareness", «κι βίζουαλ» ≈ "key visual" and the exact annotation format | northlight seeded garbles T1 and T2 (T1.4, T3.3); also voreas's T1 garble, the same token on voreas kickoff [00:02:18] |
| `.claude/agents/verify-extract.md:19` | "don't hold me to it" (northlight transcript [00:11:47]) | speculation trap X2 |
| `skills/SOURCES.md:116`, `.claude/agents/extract.md:139` | "ογδόντα χιλιάρικα", a close paraphrase of the same spoken figure | — |
| `skills/TRANSLATION.md:7, :13`, `.claude/agents/render.md:13, :17, :31, :37` | Meltemi Fizz and `templates/northlight_client_brief.md` | not a trap; makes the generic stage northlight-shaped |

**voreas_02 is no longer a held-out fixture.** It was graded honestly at 15/17 and 16/17 on
2026-07-26 and has not been re-run since. Its defects then shaped the system: the email
supersession wording in SOURCES.md §5, the runtime gates, and the strict xfails in
`tests/test_regression_voreas.py`. Its T1 garble is also the example in TRANSCRIPTS.md.

W2 is removing the graded-fixture examples from the runtime prompts in round 1. The owner's
re-baseline authorisation is conditional on that removal
(`docs/OPERATING_DECISIONS.md` § 2026-09-22, decision 1). Results from before the removal are
labelled *contaminated prompts* wherever they are compared with results from after it.

## 4. The frozen harness — freeze record and blind spots

**Freeze record.** `eval/harness.py` was frozen at `9e371f6` (tier-1, 2026-07-24).
`git log -- eval/harness.py` shows **one post-freeze commit**: `7320689` (2026-07-29, "demo:
defense-session live path … harness path fallback"). It added a repo-relative fallback for
`project_dir` in `load_run` (harness.py:135–141), so committed manifests with relative paths can
be graded from any working directory. The commit message says it was explicitly instructed and is
path plumbing only. The diff touches no check or acceptance criterion. It is recorded here because
no tier report records it.

**Blind spots.** Each one was verified in `eval/harness.py` as committed.

| check | blind spot | consequence | covered by |
|---|---|---|---|
| X2 | Passes with "not present in draft" when no entry matches the speculative keywords (`check_trap_x2_speculation`) | Dropping the speculative item scores the same as hedging it | supplementary S1 |
| T3.3 | Searches the whole brief JSON, **evidence anchors included**, plus the renders (`check_garbling_survives_to_the_brief`) | A garble normalised in every reader-visible field still passes, because the token survives in an anchor (tier3: `runs/tier3/KNOWN_DEFECTS.md` B3) | supplementary S3 |
| T2.5 | Loads the glossary only from `glossary/*.json`, and only when exactly one file exists (`load_run`) | On voreas it checked 5 generic Meltemi-glossary terms. It never checked the 7 Voreas terms the briefs use: Voreas Move, Voreas Athletics, the tagline Move Like the Wind, athleisure, hero video, retail activation and AR filter | supplementary S8 (fixture-local glossary) |
| X3 | A fixed list of literal forbidden patterns, applied to the brief and renders only | Unmarked numeral conversion evades it (`runs/voreas_prep_report.md` Finding 4). Creative drafts are never checked (tier3 sonnet "€80–85k") | supplementary S6, S9 |
| T3.1 / T3.2 | Keyword and signal presence (`keyword_any_of`; 3 of 4 gaps) | Recall only; no false-conflict or duplicate metric | supplementary S5 (duplicates) |
| — | No recall check for non-trap facts (budget, deadline and audience values) | Loss of an ordinary fact is invisible | — |
| — | No check of resolved-state consistency after sign-off | Questions answered by a resolution stay open (tier3 B1, B2) | supplementary S2 |
| — | No check of Greek language quality | 9 grammar errors in tier3 `brief_el.md` (R3) | `tests/test_regression_northlight.py` lint; W4 render lint |
| — | No check of creative drafts at all | Invented currency, origin and market claims, spec drift (creative C1–C7) | supplementary S6, S7; W4 creative gate |

## 5. Supplementary scorer — results on the stored evidence

`python3 eval/supplementary.py <run>` is unfrozen and report-only. It never reads an answer key.

Results on the committed evidence, from `python3 eval/supplementary.py runs/tier3 runs/voreas-prep-02 runs/voreas-prep-03` [committed]:

| check | tier3 (graded, 17/17) | voreas-prep-02 (15/17) | voreas-prep-03 (16/17) |
|---|---|---|---|
| S1 speculative coverage | ok (conditional item kept; the second is carried in a conflict position) | flag: 1 conditional item de-hedged (`audiences[4]`) | flag: 1 conditional item dropped (kickoff [00:15:40]) |
| S2 stale questions | **flag: 3** questions open in 3 resolved fields, signed off | vacuous (no resolutions) | vacuous |
| S3 garble visibility | **flag**: both garbles normalised in content (objectives[2], key_messages[3]) and absent from both renders | flag: 3 garbles normalised; «μπραντ αγουέρνες» carried by no entry | flag: same |
| S4 citation content (heuristic) | **flag**: `key_messages[3]` "beach-party" found only in background_brand_guidelines | flag: 2 quoted translations shown as verbatim ('half the campaign', 'designed in Greece') | flag: same 2, plus 'media spend' found only in market research |
| S5 duplicate questions | ok | **flag: 6** questions re-ask open conflicts | **flag: 4** |
| S6 creative currency | **flag**: sonnet "€80–85k" ×2, opus "€90k" | n/a | n/a |
| S7 creative spec tokens | **flag**: sonnet "9–60s" (en dash) vs "9-60s" | n/a | n/a |
| S8 glossary coverage | ok (8 of 9 Meltemi terms checked) | ok (12 of 13 Voreas terms checked) | ok (12 of 13) |
| S9 hedge drift | **flag**: 8 × "in the eighties" (brief ×3, EN render ×3, both drafts) | ok | ok |

The S5 counts (6 and 4) match the counts `tests/test_regression_voreas.py` records for Addendum 4.

Across every harness-graded brief in the local store [local store: 11 northlight, 2 voreas]:

| check | northlight_01 (11 briefs) | voreas_02 (2 briefs) |
|---|---|---|
| S3 garble normalised in content or absent from renders | 10 / 11 | 2 / 2 |
| S4 cross-source or unsourced content | 5 / 11 ("beach-party" or "spring-break" borrowed from the guidelines in 3) | 2 / 2 |
| S5 questions re-asking an open conflict | 10 / 11 (the exception, tier3, has only resolved conflicts) | 2 / 2 |
| S1 speculative item dropped or de-hedged | 0 / 11 | 2 / 2 |
| S9 decade-range hedge drift | 1 / 11 (tier3) | 0 / 2 |
| S6 invented currency in creative drafts | 2 / 2 runs with drafts (tier3; cost-full: "€4.50" for «τεσσεράμισι ευρώ», "€80–85") | — |

Garble normalisation (S3) and questions re-asking conflicts (S5) are systematic on the evidence
so far; they are not one-off slips. Both are pass-invisible to the frozen harness.

## 6. Open owner decision — verify-extract risk routing (measured, not changed)

The routing sends the verifier to sonnet when an extract carries any risk class (mandatories,
figures, garbling, low confidence) and to the base model otherwise. `config/model_routing.json`
gives the base model as `null`, meaning the agent frontmatter (haiku). `python3 eval/cost_report.py
runs --risk-replay` replays `pipeline/extraction.py:risk_classes` over every stored extract,
counting byte-identical copies once:

| evidence | unique extracts | base (haiku) branch | mandatories | figures | garbling | low confidence | figures as the sole trigger |
|---|---:|---:|---:|---:|---:|---:|---:|
| local store | 66 | **0 (0%)** | 36 | 64 | 39 | 30 | 2 |
| committed | 10 | **0 (0%)** | 6 | 9 | 7 | 3 | 1 |

All but one of these extracts were written by the Haiku-era extractor. The one current-routing
extract (`routing-validate-01`) carries all four classes, and its manifest records a sonnet
verifier.

On this evidence the haiku branch is nominal: every verification runs on sonnet. "Else haiku" in
CLAUDE.md and `config/model_routing.json` describes a path no stored extract takes. Narrowing
`figures` alone (for example, dates no longer counting) would move at most 2 of 66.

**The decision for the owner:** keep "verifier always effectively sonnet" and plan usage on it,
or re-define the risk classes so that a low-risk path exists. Routing is a human decision
(CLAUDE.md), so nothing was changed.

## 7. Round-2 live re-baseline — protocol

This is authorised by the owner (`docs/OPERATING_DECISIONS.md` § 2026-09-22, decision 1) on the
owner's Claude subscription. It runs after W2's decontamination of the runtime prompts has merged.

**Rolls.** Run 3 independent full runs per fixture under the unchanged current routing:

- `python3 pipeline/runner.py --project fixtures/northlight_01 --out runs/rebaseline-r2 --run-id northlight-r2-roll<N>`
- `python3 pipeline/runner.py --project fixtures/voreas_02 --glossary fixtures/voreas_02/client_voreas.json --out runs/rebaseline-r2 --run-id voreas-r2-roll<N>`

Each roll runs the whole pipeline from the readiness gate. There is no resume from an earlier
roll, so every roll is an independent leg. A roll that fails after the runner's own repair loop is
recorded as a failure. It is not re-rolled to get a pass, and any operator resume is recorded as
such (the tools flag inherited legs).

**Grading.** Run `python3 eval/harness.py runs/rebaseline-r2/<roll>` on each new run directory,
which writes `harness_report.json` there. Never point the CLI at a committed evidence directory.
Then run `python3 eval/supplementary.py runs/rebaseline-r2/<roll> --json`.

**What gets recorded, per roll:**

- run manifest: pipeline version, input snapshot hashes including `config/model_routing.json`,
  resolved model IDs per call, attempts per stage, and `verification` blocks (risk classes, model,
  issue count)
- harness report
- supplementary report
- tokens by model: `eval/cost_report.py <roll>`
- wall time: `started_ts`/`finished_ts`
- outcome and exit code

**Aggregates:**

- `python3 eval/pass_rates.py runs/rebaseline-r2`: per-check pass/n over distinct legs, Wilson 95%
- `python3 eval/cost_report.py runs/rebaseline-r2`: per-brief tokens by model, all runs and clean
  only
- `--risk-replay`: verifier branch taken
- supplementary flag counts per check

These go into `runs/rebaseline_r2_report.md` beside the contaminated-prompt, Haiku-era baseline
in §1 and §5. Committing the six roll directories as evidence needs a `.gitignore` exception
(orchestrator decision).

**What n = 3 can show.** A check at 3/3 has a Wilson 95% interval of 0.44–1.00. Three rolls detect
gross regressions and systematic defects (such as §5's S3 and S5); they cannot resolve small
quality deltas between routings. The report states this next to every rate.

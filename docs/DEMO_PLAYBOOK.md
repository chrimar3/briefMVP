# Demo Playbook — running the pipeline on documents you have never seen

Written for the live examination: the evaluators hand over an arbitrary transcript, RFP,
and/or email thread, and the pipeline has to produce a brief in front of them. Everything
below is exercised in advance; nothing here requires touching frozen files.

## 0. What is already proven before the demo

| Claim | Evidence |
|---|---|
| The pipeline is not tuned to one fixture | `fixtures/voreas_02` — different client, industry, glossary, tier (S0 vs S1), 6 sources vs 4, graded by the **unchanged frozen harness** |
| Hostile inputs fail legibly, not silently | `pytest -q` — input-contract and readiness tests: missing RFP, undeclared files, bad source types, duplicate ids, no budget/timeline signal, thin input |
| Arbitrary raw documents can be onboarded in seconds | `pipeline/intake.py` + `tests/test_intake.py` |

## 1. Intake: from raw files to a runnable project (≈1 minute)

Drop whatever they give you into a folder (`.md`/`.txt`), then:

```bash
python3 pipeline/intake.py raw_docs/ --out fixtures/exam_01 --client examclient --tier S1
```

- `--tier` is **required and never inferred** (PRD DR-11). Ask the evaluators what the
  client's onboarding tier is; if they shrug, say "then onboarding sets it — I'll take S1"
  and move on. S2/S3 is refused by design — that refusal is itself worth demonstrating.
- Intake stamps the `source_id · source_type · source_date` header each file needs.
  Types are inferred only from strong signals (3+ `[hh:mm:ss]` timestamps → transcript,
  From:/To:/Date: lines → email_thread); anything ambiguous is **refused** with an exact
  `--type notes.txt=background` instruction to copy-paste. Ask-don't-guess, demonstrated live.
- It scaffolds `fixtures/exam_01/client_examclient.json` (starter glossary) **inside the
  project folder** — `glossary/` deliberately keeps one file so the documented
  northlight command keeps working. Skim the starter terms; add client-specific
  names (product, tagline) with `rule: keep_latin` — 30 seconds that visibly improve renders.
- It finishes by running the input contract + readiness gate and printing the run command.

If readiness says `thin_input_return_to_client`: that is a *feature*, not a failure —
narrate that the agency policy (`config/readiness_policy.json`) refuses to draft from
insufficient input, and show what it asked for.

## 2. Run

```bash
python3 pipeline/runner.py --project fixtures/exam_01 --glossary fixtures/exam_01/client_examclient.json
```

While it runs, narrate the step sequence (PRD §5): readiness gate → classify → transcript
fidelity → per-source extraction with schema-repair loop → deterministic conflict
candidates → synthesis → bilingual render — haiku for schema-following work, sonnet for
judgment work. Outputs land in `runs/<ts>/`, `runs/latest` symlinks to it.

Useful mid-run artifacts to show: `runs/latest/extracts/*.json` (citations on every value),
`runs/latest/diagnostics/` (repair attempts, if any).

## 3. What to show when it finishes

1. `brief.json` — conflicts as **two cited positions, never merged** (DR-10); open
   questions instead of invented values; `qualifier: conditional` on speculation.
2. `brief_el.md` / `brief_en.md` — same object rendered twice, zero translation drift;
   glossary terms character-exact.
3. Any garbled transcript token carried as-is with an `extraction_note` — never silently fixed.

## 4. Grading — what the harness can and cannot say

- **With an answer key** (northlight_01, voreas_02): `python3 eval/harness.py runs/latest`
  grades the full exam: seeded conflicts/gaps/garbling, traps X1–X3, citations, renders.
- **On unseen exam input there is no answer key** — the harness stops at "nothing to grade
  against". What still holds machine-checkably for ANY input: schema validation, citation
  presence + resolution (every anchor is a verbatim string in a source), readiness
  recomputation, render citation tags. Show those via the run's gate output; be explicit
  that seeded-challenge grading needs a key by construction.

## 5. If something fails live

- **Input contract / readiness refusal** — the system explaining what it needs *is* the
  designed behavior. Read the message aloud; add the missing piece or narrate the return-to-client.
- **A stage fails after repair attempts** — show `runs/<ts>/diagnostics/`: per-attempt
  logs are the audit trail. Re-run just that leg: `--stage <name> --run-id <same-id>` (resume).
- **Model quality issue** — report it; never upgrade a stage's model live to pass (routing
  changes are a human decision, CLAUDE.md).

## 6. Known limits to state up front (honesty beats discovery)

- **Anchor-across-asides** (found by voreas_02, 2026-07-26): when a source sentence embeds a
  parenthetical aside mid-span, the extract model sometimes quotes around the aside — a
  discontinuous span that fails the verbatim-anchor gate. Measured: 3 of 4 haiku attempts
  failed on one such Greek guidelines line; the repair loop recovered on retry. If a leg
  exhausts its 2 attempts live, the §5 resume command is the play — observed to recover.
  The gate itself is working as designed: constructed citations are refused, never accepted.
- **Diarization-collision annotation** (same session): a transcript line carrying two
  speakers' timestamps tempts the fidelity annotator to *split* the line — a repair, which
  the annotate-never-repair gate refuses. Measured on one seeded line: passed 1-of-1
  attempts in one leg, failed 2-of-2 in another. Same live play: resume the leg.
- **Synthesis discipline is roll-dependent** (measured on voreas_02: 15/17 then 16/17 with
  the same extracts): conflict citation-pairing and contradiction-surfacing recovered on a
  re-roll (`--stage synthesis --run-id <id>` on a copy of the run dir, ~$3). Before showing
  a brief live, eyeball the conflicts section: both positions cited to *different* sources,
  quotes verbatim. One sticky weakness: a garble-flagged claim sharing a sentence with a
  clean claim can be silently dropped (the client's primary objective, twice in two rolls)
  — check the objectives section against the transcript's opening statements.
- All of the above are candidate one-sentence hardenings in `skills/SOURCES.md` /
  `TRANSCRIPTS.md` / `SYNTHESIS.md` — runtime-spec changes, deliberately not made
  unilaterally the night before the exam. Full analysis: `runs/voreas_prep_report.md`.

- Harness check T2.5 (glossary terms exact in renders) loads the single file in
  `glossary/` — for a non-Meltemi run it checks only the generic overlap terms
  (KPI, key visual, launch…), not client-specific ones. Frozen-harness limitation, known.
- Fidelity/garbling detection is built for Greek/English agency register (the pilot's
  actual domain); other language pairs are untested.
- `answer_key.json` is the only reserved filename inside a project folder; intake skips it.

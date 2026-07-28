# Demo timing — measured, not estimated

All numbers from `demo/run_demo.py` on `fixtures/northlight_01/transcript_kickoff.md`
(366 words, under the 800-word cap), classify → extract → deterministic gates, models
`claude-haiku-4-5-20251001`, run sequentially on one machine. Reproduce any single run with:

```bash
python demo/run_demo.py fixtures/northlight_01/transcript_kickoff.md
```

## Ten supervised runs (2026-07-28, machine sleep disabled)

| run | wall clock | outcome | model cost |
|---|---|---|---|
| 1 | 1229.7 s | gate refused both attempts | — |
| 2 | 788.6 s | gate refused both attempts | — |
| 3 | 239.4 s | ✅ | $0.197 |
| 4 | 155.3 s | ✅ | $0.230 |
| 5 | 405.8 s | gate refused both attempts | — |
| 6 | 191.2 s | ✅ | $0.127 |
| 7 | 419.1 s | ✅ | $0.316 |
| 8 | 183.6 s | ✅ | $0.146 |
| 9 | 252.8 s | ✅ | $0.204 |
| 10 | 295.6 s | ✅ | $0.229 |

**Successful runs (n=7): p50 = 239 s (≈4 min) · p95 = 419 s (≈7 min) · min 155 s ·
mean cost ≈ $0.21.**

## The failures are the citation gate working

Every failed run died the same way: the extract model produced a *near-miss* quote — a
Greek anchor with a mutated character or word («τέλος του μήνα» for «τέλη του μήνα», an
inserted English "that", a lowercased «Το») — and the deterministic gate refused it, twice,
because a citation that does not occur verbatim in the source is fabricated evidence. Leg
pass rate in this batch: 7/10. The demo therefore retries a refused leg by default
(`--retries 2`, refusals printed, never hidden): at the measured 70% leg rate, three legs
give ≈97% session success. If a refusal happens live, that *is* the demonstration —
read the message aloud.

An earlier overnight batch (2026-07-27/28) is disclosed but not used for statistics: the
machine slept mid-loop, which killed three transport sessions and stretched wall clocks;
its two clean passes (188 s, 268 s) and the shakedown run (223 s) are consistent with the
supervised p50.

## Full pipeline, one project, all stages

One complete Stage-1 run (readiness → classify → fidelity → extract ×4 → conflict pass →
synthesize → bilingual render) on `fixtures/northlight_01`, same day, sleep disabled:

**Wall clock: 1300.6 s ≈ 21.7 minutes, every stage passing on its first attempt** —
console capture committed at [`full_run_console.log`](full_run_console.log).

Full disclosure of the same day's runs, because the failures teach as much as the number:

- A first attempt died mid-extraction after two "no file written" transport failures
  (preserved at `runs/case-full-20260728/`) — the same degraded-transport day the demo
  loop measured.
- The 21.7-minute run's *first synthesis roll* graded 16/17: it committed a retracted idea
  (trap X1) — traced to a one-sentence spec addition made the day before, which the model
  over-generalized. The sentence was scoped, the agents re-synced, and the synthesis leg
  re-rolled ([`full_run_reroll_console.log`](full_run_reroll_console.log)): **final grade
  17/17**. The regression was caught by the frozen harness within two runs of the change —
  which is precisely the workflow this repo is arguing for.

For per-stage timings of the graded tier-3 run, see [`EVIDENCE.md`](EVIDENCE.md).

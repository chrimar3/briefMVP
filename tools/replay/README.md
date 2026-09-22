# Offline replay

Run the whole Stage-1 orchestration with zero model calls, no `claude` CLI and no cost:

```bash
BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" \
  python3 pipeline/runner.py --project fixtures/northlight_01 --out /tmp/bb-replay
```

The path must be absolute: `pipeline/agents.py` starts the binary from a neutral working directory.

- `claude` is a stand-in for the Claude Code CLI. It accepts any flags, reads the work order, and
  copies the matching artifact from the recording (`pipeline/replay.py` has the logic). Every attempt
  reports the model `offline-replay` and zero tokens, so a replayed manifest cannot be mistaken for a
  model run. `BRIEF_BUILDER_REPLAY_RUN=<dir>` replays a different recording.
- `recordings/northlight_01/` is **not evidence** and is never graded. It is `runs/tier3` with the
  human layer reversed (sign-off, conflict resolutions, readiness injection) plus synthesised
  `confirms` verifier reports, because the graded run predates step 4b. `derive_recording.py`
  rebuilds it and documents each edit; `tests/test_replay.py` fails if the committed copy drifts
  from that derivation.

Replay proves the wiring and the gates (work orders, repair loop, readiness injection, manifest,
review pages, resume legs), never model quality.

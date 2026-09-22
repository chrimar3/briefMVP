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
- `recordings/northlight_01/` is a **wiring fixture, not evidence**, and is never graded or cited
  as a model result. Its classification, fidelity and extract files are `runs/tier3` byte for byte;
  `brief.json` is `runs/tier3/brief.json` with the human layer reversed (sign-off, conflict
  resolutions, readiness injection); the verifier reports are synthesised `confirms` reports,
  because the graded run predates step 4b.
- The two renders are **generated, not recorded.** The graded renders predate the current
  client-brief template (`templates/northlight_client_brief.md`, `.el.md`, `.labels.json`), which
  the render stage now enforces with the blocking `check_render_template`. So
  `derive_recording.py` writes both renders deterministically from the recording's own
  `brief.json` and the template's label table: fixed headings and banner, one line per entry with
  its exact `[source_id location]` tags, numbered questions, conflicts, internal section last. The
  entry text is the brief's content verbatim in both files (the Greek file wraps untranslated
  content in the fixed Greek boilerplate). They exist to exercise the render gates end to end; they
  say nothing about translation or render quality.
- `derive_recording.py` rebuilds the whole recording and documents each edit;
  `tests/test_replay.py` fails if the committed copy drifts from that derivation, and checks that
  both renders pass today's `check_render` and `check_render_template` unchanged.

Replay proves the wiring and the gates (work orders, repair loop, readiness injection, manifest,
review pages, resume legs), never model quality.

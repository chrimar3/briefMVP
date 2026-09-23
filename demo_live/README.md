# demo_live — the defense-session drop-in project

Paste the session's text into `sources/live_transcript.md` (below its header line), then
from the repo root:

- `./demo.sh --live` — extraction + verification only (~2–4 min): facts with verbatim
  citations, flags, open questions. A gate rejection prints its reason and exits non-zero —
  that display is a feature, read it aloud.
- `./run_full.sh --live` — full pipeline in the background under the **demo profile**
  (`readiness_policy_demo.json`, recorded in the run manifest): single-source input is
  allowed for the demo, the production input gate's refusal is printed and logged, never
  hidden. Outputs land in `runs/live/`.

Live model calls are opt-in: without `--live` (or `BRIEF_BUILDER_LIVE=1`) neither script calls
a model. Rehearse offline, with zero model calls, with `./demo.sh --replay` and
`./run_full.sh --replay [--out DIR]` — both replay the recorded `fixtures/northlight_01` run
(the only project the replay recording holds), through the same gates, staging and integrity
checks. `sources/data_declaration.json` declares this folder synthetic; the demo refuses input
from a folder without a declaration.

`client_demo.json` is a deliberately empty S0 glossary: nothing is assumed about pasted
text. This folder is additive demo tooling — fixtures, schema, and gates are untouched.

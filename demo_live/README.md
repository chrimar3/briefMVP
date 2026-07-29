# demo_live — the defense-session drop-in project

Paste the session's text into `sources/live_transcript.md` (below its header line), then
from the repo root:

- `./demo.sh` — extraction + verification only (~2–4 min): facts with verbatim citations,
  flags, open questions. A gate rejection prints its reason and exits non-zero — that
  display is a feature, read it aloud.
- `./run_full.sh` — full pipeline in the background under the **demo profile**
  (`readiness_policy_demo.json`, recorded in the run manifest): single-source input is
  allowed for the demo, the production input gate's refusal is printed and logged, never
  hidden. Outputs land in `runs/live/`.

`client_demo.json` is a deliberately empty S0 glossary: nothing is assumed about pasted
text. This folder is additive demo tooling — fixtures, schema, and gates are untouched.

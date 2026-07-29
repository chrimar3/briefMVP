#!/usr/bin/env bash
# Defense-session demo: extraction + verification ONLY (no synthesis) on the live drop-in
# file — or any file given as $1. Streams progress; pretty-prints facts with verbatim
# citations, flags, and open questions. On a gate rejection it exits non-zero and SHOWS the
# rejection reason: that display is a feature — read it aloud.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 demo/run_demo.py "${1:-demo_live/sources/live_transcript.md}" \
  --glossary demo_live/client_demo.json

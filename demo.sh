#!/usr/bin/env bash
# Defense-session demo: extraction + verification ONLY (no synthesis) on the live drop-in
# file — or any file given after the mode. Streams progress; pretty-prints facts with verbatim
# citations, flags, and open questions. On a gate rejection it exits non-zero and SHOWS the
# rejection reason: that display is a feature — read it aloud.
#
#   bash demo.sh --live   [FILE] [demo flags…]   real model calls (owner-authorised; spends usage)
#   bash demo.sh --replay [FILE] [demo flags…]   offline rehearsal, zero model calls (default FILE:
#                                                the northlight kickoff transcript the replay
#                                                recording holds)
#
# Without a mode, a real `claude` CLI is refused by demo/run_demo.py (exit 7) — live calls are
# opt-in (BRIEF_BUILDER_LIVE=1 also opts in). Extra flags (e.g. --out DIR) pass through.
set -euo pipefail
cd "$(dirname "$0")"

mode=""
case "${1:-}" in
  --live|--replay) mode="$1"; shift ;;
esac
file=""
if [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; then
  file="$1"; shift
fi

if [ "$mode" = "--replay" ]; then
  export BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude"
  exec python3 -u demo/run_demo.py "${file:-fixtures/northlight_01/transcript_kickoff.md}" \
    --glossary glossary/meltemi.json "$@"
fi
live=()
if [ "$mode" = "--live" ]; then
  live=(--live)
fi
exec python3 -u demo/run_demo.py "${file:-demo_live/sources/live_transcript.md}" \
  --glossary demo_live/client_demo.json --project-id demo_live ${live[@]+"${live[@]}"} "$@"

#!/usr/bin/env bash
# Defense-session full pipeline, in the background.
#
#   bash run_full.sh --live   [--out DIR]   demo_live under the DEMO PROFILE, real model calls
#                                           (owner-authorised; spends usage)
#   bash run_full.sh --replay [--out DIR]   offline rehearsal: fixtures/northlight_01 through the
#                                           replay binary, zero model calls (the only project the
#                                           replay recording holds)
#
# Live calls are opt-in: with neither mode (and no BRIEF_BUILDER_LIVE=1) nothing starts.
# DEMO PROFILE (live mode): single-source input is allowed for the demo; the production input
# gate's refusal is printed into the log and recorded in the run manifest — never hidden.
# Output: DIR/live (default runs/live); an earlier DIR/live is kept as live-prev-<stamp>.
set -euo pipefail
cd "$(dirname "$0")"

mode=""
out="runs"
while [ $# -gt 0 ]; do
  case "$1" in
    --live|--replay) mode="$1"; shift ;;
    --out) out="${2:?--out needs a directory}"; shift 2 ;;
    *) echo "usage: bash run_full.sh --live|--replay [--out DIR]" >&2; exit 2 ;;
  esac
done
if [ -z "$mode" ] && [ "${BRIEF_BUILDER_LIVE:-}" = "1" ]; then
  mode="--live"
fi
if [ -z "$mode" ]; then
  echo "run_full.sh: live model calls are opt-in — pass --live (owner-authorised run) or --replay" >&2
  echo "  (offline rehearsal, zero model calls)." >&2
  exit 7
fi

live_dir="$out/live"
if [ -d "$live_dir" ]; then
  mv "$live_dir" "$out/live-prev-$(date +%Y%m%d-%H%M%S)"   # keep prior demo output, never overwrite
fi
mkdir -p "$live_dir"

if [ "$mode" = "--replay" ]; then
  export BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude"
  args=(--project fixtures/northlight_01 --glossary glossary/meltemi.json)
else
  args=(--project demo_live/sources --glossary demo_live/client_demo.json
        --demo-profile demo_live/readiness_policy_demo.json --live)
fi
# Written to the default runs/ the run publishes onto reviews/ as before; any other --out is
# hermetic (pipeline/runner.py).
nohup python3 -u pipeline/runner.py "${args[@]}" --out "$out" --run-id live >> "$live_dir/run.log" 2>&1 &
runner_pid=$!
# Demo closing shot (mission decision §6.3): when the runner finishes AND the manifest
# says complete, open the account-lead review page. Fully detached and silent — stdout
# stays the single line below. `wait` cannot target a non-child from the subshell, so
# poll the pid; a failed or refused run never opens a stale page.
(
  while kill -0 "$runner_pid" 2>/dev/null; do sleep 5; done
  if [ -z "${DEMO_NO_OPEN:-}" ] && grep -q '"outcome": "complete"' "$live_dir/run_manifest.json" 2>/dev/null; then
    page="$live_dir/brief_review.html"
    if [ "$(uname -s)" = "Darwin" ] && command -v open >/dev/null 2>&1; then
      open "$page"
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$page"
    fi
  fi
) >/dev/null 2>&1 &
echo "started ($mode) — outputs will land in $live_dir/ (review page: $live_dir/brief_review.html)"

#!/usr/bin/env bash
# Defense-session full pipeline on demo_live, in the background under the DEMO PROFILE:
# single-source input is allowed for the demo; the production input gate's refusal is
# printed into the log and recorded in the run manifest — never hidden.
set -euo pipefail
cd "$(dirname "$0")"
if [ -d runs/live ]; then
  mv runs/live "runs/live-prev-$(date +%Y%m%d-%H%M%S)"   # keep prior demo output, never overwrite
fi
mkdir -p runs/live
nohup python3 pipeline/runner.py \
  --project demo_live/sources \
  --glossary demo_live/client_demo.json \
  --demo-profile demo_live/readiness_policy_demo.json \
  --run-id live >> runs/live/run.log 2>&1 &
runner_pid=$!
# Demo closing shot (mission decision §6.3): when the runner finishes AND the manifest
# says complete, open the account-lead review page. Fully detached and silent — stdout
# stays the single line below. `wait` cannot target a non-child from the subshell, so
# poll the pid; a failed or refused run never opens a stale page.
(
  while kill -0 "$runner_pid" 2>/dev/null; do sleep 5; done
  if grep -q '"outcome": "complete"' runs/live/run_manifest.json 2>/dev/null; then
    open runs/live/brief_review.html
  fi
) >/dev/null 2>&1 &
echo "started — outputs will land in runs/live/"

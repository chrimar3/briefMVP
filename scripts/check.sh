#!/usr/bin/env bash
# The one deterministic check, identical for humans and CI. No model calls, no network.
#
#   scripts/check.sh            lint (if ruff is installed), tests, frozen grade, agency benchmark
#   scripts/check.sh --no-lint  skip the lint step (CI lints in its own step)
#
# Interpreter: $PYTHON, default python3. Install the tested toolchain first:
#   python3 -m pip install -r requirements.lock   (plus `ruff` for the lint step)
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
lint=1
for arg in "$@"; do
  case "$arg" in
    --no-lint) lint=0 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n== %s\n' "$1"; }

if [ "$lint" -eq 1 ]; then
  step "lint (ruff check .)"
  if command -v ruff >/dev/null 2>&1; then
    ruff check .
  elif "$PYTHON" -m ruff --version >/dev/null 2>&1; then
    "$PYTHON" -m ruff check .
  else
    echo "ruff not installed: lint skipped here (CI runs it). pip install ruff to lint locally."
  fi
fi

step "tests (pytest; --strict-markers comes from pyproject.toml)"
"$PYTHON" -m pytest -q

step "frozen evidence grade (read-only: runs/tier3 must stay byte-identical)"
"$PYTHON" eval/grade_frozen.py runs/tier3 --expect 17

step "synthetic agency safeguards benchmark"
report="$(mktemp)"
trap 'rm -f "$report"' EXIT
if ! "$PYTHON" eval/agency_benchmark.py > "$report"; then
  cat "$report"
  echo "agency benchmark: FAILED" >&2
  exit 1
fi
"$PYTHON" -c 'import json, sys; r = json.load(open(sys.argv[1])); print("agency benchmark: %s/%s cases, model calls %s" % (r["passed"], r["total"], r["model_calls"]))' "$report"

printf '\nAll deterministic checks passed.\n'

#!/usr/bin/env bash
# The one deterministic check, identical for humans and CI. No model calls, no network.
#
#   scripts/check.sh                 lint, type check, tests with the coverage floor, frozen grade,
#                                    agency benchmark, decision-paper gate
#   scripts/check.sh --no-lint       skip ruff        (otherwise a missing ruff FAILS the check)
#   scripts/check.sh --no-typecheck  skip mypy        (otherwise a missing mypy FAILS the check)
#   scripts/check.sh --no-cov        tests without the coverage floor (otherwise a missing
#                                    pytest-cov FAILS the check)
#
# Every skip is printed in the final line, so a partial run never reads as a full pass.
# Interpreter: $PYTHON, default python3. Install the locked toolchain first:
#   python3 -m pip install -r requirements-dev.lock
# The decision-paper gate needs Node.js (`node --check` parses the page's scripts).
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
lint=1
typecheck=1
cov=1
for arg in "$@"; do
  case "$arg" in
    --no-lint) lint=0 ;;
    --no-typecheck) typecheck=0 ;;
    --no-cov) cov=0 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n== %s\n' "$1"; }
missing() {
  echo "$1 is not installed: install the locked toolchain (python3 -m pip install -r requirements-dev.lock)" >&2
  echo "or pass $2 to skip this step explicitly." >&2
  exit 1
}
skipped=()

if [ "$lint" -eq 1 ]; then
  step "lint (ruff check .)"
  if command -v ruff >/dev/null 2>&1; then
    ruff check .
  elif "$PYTHON" -m ruff --version >/dev/null 2>&1; then
    "$PYTHON" -m ruff check .
  else
    missing ruff --no-lint
  fi
else
  skipped+=("lint")
fi

if [ "$typecheck" -eq 1 ]; then
  step "type check (mypy, non-strict, pipeline/ — config in pyproject.toml)"
  if "$PYTHON" -m mypy --version >/dev/null 2>&1; then
    "$PYTHON" -m mypy
  else
    missing mypy --no-typecheck
  fi
else
  skipped+=("typecheck")
fi

if [ "$cov" -eq 1 ]; then
  step "tests with coverage (pytest-cov; the floor is fail_under in pyproject.toml)"
  if ! "$PYTHON" -c 'import pytest_cov' >/dev/null 2>&1; then
    missing pytest-cov --no-cov
  fi
  "$PYTHON" -m pytest -q -p no:cacheprovider --cov --cov-report=term
else
  step "tests (pytest; --strict-markers comes from pyproject.toml)"
  "$PYTHON" -m pytest -q -p no:cacheprovider
  skipped+=("coverage floor")
fi

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

step "decision-paper gate (tools/walkthrough/checks.py on WALKTHROUGH.html)"
page_report="$(mktemp)"
trap 'rm -f "$report" "$page_report"' EXIT
if ! "$PYTHON" tools/walkthrough/checks.py --file WALKTHROUGH.html > "$page_report"; then
  cat "$page_report"
  echo "decision-paper gate: FAILED" >&2
  exit 1
fi
"$PYTHON" -c 'import json, sys; r = json.load(open(sys.argv[1])); print("decision-paper gate: %s sheets, %s verbatim quotes, 0 failures" % (r["sheets"], r["blockquotes"]))' "$page_report"

if [ "${#skipped[@]}" -eq 0 ]; then
  printf '\nAll deterministic checks passed.\n'
else
  printf '\nAll deterministic checks that ran passed. SKIPPED on request: %s.\n' "$(IFS=,; echo "${skipped[*]}" | sed 's/,/, /g')"
fi

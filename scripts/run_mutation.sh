#!/usr/bin/env bash
# Mutation testing with cosmic-ray on the core risk-logic modules.
#
# Why cosmic-ray (not mutmut): mutmut 2.x mis-instruments this repo's modern
# syntax (real mutations survive), and mutmut 3.x doesn't run on Python 3.14.
# cosmic-ray's import-hook AST mutation works cleanly on Python 3.12.
#
# Usage:
#   PYTHON=python3.12 scripts/run_mutation.sh            # report survival rates
#   PYTHON=python3.12 scripts/run_mutation.sh 30         # fail if any module >30% survive
#
# Survival rate = % of mutants the tests did NOT catch (lower is better;
# mutation score = 100 - survival). Needs Python < 3.13.
set -euo pipefail

FAIL_OVER="${1:-}"
PY="${PYTHON:-python}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"

run() { # <module-dir> <module-path-rel> <test-cmd>
  local dir="$1" mod="$2" tests="$3"
  local base cfg db
  base="$(basename "$mod" .py)"
  cfg="$TMP/$base.toml"
  db="$TMP/$base.sqlite"
  cat >"$cfg" <<EOF
[cosmic-ray]
module-path = "$mod"
timeout = 30.0
excluded-modules = []
test-command = "$tests"
[cosmic-ray.distributor]
name = "local"
EOF
  (
    cd "$ROOT/$dir"
    find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
    cosmic-ray init "$cfg" "$db" >/dev/null
    cosmic-ray exec "$cfg" "$db"
  )
  printf '\n== %-22s survival: ' "$mod"
  if [[ -n "$FAIL_OVER" ]]; then
    cr-rate "$db" --fail-over "$FAIL_OVER" --confidence 95.0
  else
    cr-rate "$db"
  fi
}

# Core risk logic + the LLM safety gate. Keep test commands fast and focused.
run m1-ingestion lens_m1/metrics.py "$PY -m pytest -x -q tests/test_metrics.py tests/test_properties.py"
run m2-actions   lens_m2/derived.py "$PY -m pytest -x -q tests/test_actions.py tests/test_api.py"
run m4-ai        lens_m4/safety.py  "$PY -m pytest -x -q tests/test_safety.py"

rm -rf "$TMP"

#!/usr/bin/env bash
# Thin wrapper around scripts/bench/run_local.py.
#
# The real implementation lives in the Python file — YAML patching, JSON
# stream parsing, SHA256 hashing, and metric aggregation are all awkward in
# bash. This wrapper satisfies the AC ("scripts/bench/run_local.sh exists,
# executable bit set") and hands arguments through verbatim.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PYTHON_BIN="${BENCH_PYTHON:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[bench] python interpreter '${PYTHON_BIN}' not found on PATH" >&2
  exit 2
fi

exec "${PYTHON_BIN}" -u "${SCRIPT_DIR}/run_local.py" --repo-root "${REPO_ROOT}" "$@"

#!/usr/bin/env bash
# Mirror GitHub Actions CI locally. Run before every push.
# Usage: ./scripts/ci_local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

echo "==> pip install -e .[dev]"
pip install -e ".[dev]" -q

echo "==> ruff check src/neotrade tests"
ruff check src/neotrade tests

echo "==> pytest -q --cov=neotrade"
pytest -q --cov=neotrade --cov-report=term-missing

echo "==> experiment discipline (0 or 1 open)"
if command -v neotrade >/dev/null 2>&1; then
  neotrade experiment reconcile >/dev/null 2>&1 || true
  neotrade experiment list --status open || true
fi

echo "OK: local CI passed (matches .github/workflows/ci.yml core steps)"

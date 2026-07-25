#!/usr/bin/env bash
# Weekly promote cadence — never executes trades.
# Pipeline: session → fetch --force → train → eval → backtest → signals → desk
# Exit: 0=promote PASS · 1=hard fail · 2=BT promote FAIL
#
# Manual:
#   ./scripts/weekly_promote.sh
#   neotrade weekly
#
# launchd example: scripts/com.neotrade.weekly.plist
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  source "$ROOT/.venv/bin/activate"
fi
export NEOTRADE_LOG_LEVEL="${NEOTRADE_LOG_LEVEL:-INFO}"
LOG_DIR="$ROOT/data/learning"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/weekly_cron.log"
{
  echo "=== weekly_promote $STAMP ==="
  # Prefer real Ollama; weekly auto-falls back to --mock-llm if down.
  # Pass EXTRA_ARGS e.g. EXTRA_ARGS='--mock-llm' for offline cron.
  neotrade weekly ${EXTRA_ARGS:-}
  code=$?
  echo "=== done exit=$code $STAMP ==="
  exit "$code"
} >>"$LOG" 2>&1

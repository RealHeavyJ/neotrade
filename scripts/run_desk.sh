#!/usr/bin/env bash
# Optional scheduled desk run (Mon–Fri). Never executes trades.
# Example launchd/cron: 09:50 America/New_York
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
export NEOTRADE_LOG_LEVEL="${NEOTRADE_LOG_LEVEL:-INFO}"
LOG_DIR="$ROOT/data/learning"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
{
  echo "=== scheduled desk $STAMP ==="
  neotrade session || true
  neotrade desk
  neotrade experiment open --from-desk || true
  neotrade experiment list --status open || true
} >>"$LOG_DIR/desk_cron.log" 2>&1

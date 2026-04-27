#!/usr/bin/env bash
# Detached helper used by the dashboard restart endpoint to re-spawn itself.
set -euo pipefail
cd "$(dirname "$0")/.."

# Allow caller-issued HTTP response to flush and disconnect cleanly.
sleep 1

PID_FILE=".dashboard.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    kill -TERM "$OLD_PID" || true
    for _ in $(seq 1 10); do
      kill -0 "$OLD_PID" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

exec ./ai-core.sh dashboard start

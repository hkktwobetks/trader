#!/usr/bin/env bash
# フロント・バックを一括起動（Ctrl+C で両方停止）
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

cleanup() {
  echo ""
  echo " Stopping backend and frontend..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "Starting backend (port 8000) and frontend (port 5173)..."
(cd backend && ./run_api.sh) &
BACKEND_PID=$!
sleep 2
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both."
wait

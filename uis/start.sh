#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting TrackFlow UI applications..."

# Start Next.js Website application on port 3000
echo "Starting Website on port 3000..."
cd "$SCRIPT_DIR/website"
npm run dev -- -p 3000 &
WEBSITE_PID=$!

# Start Next.js Backoffice application on port 3001
echo "Starting Backoffice on port 3001..."
cd "$SCRIPT_DIR/backoffice"
npm run dev -- -p 3001 &
BACKOFFICE_PID=$!

cleanup() {
  echo "Stopping UI applications..."
  kill -TERM "$WEBSITE_PID" "$BACKOFFICE_PID" 2>/dev/null || true
  wait "$WEBSITE_PID" "$BACKOFFICE_PID" 2>/dev/null || true
}

trap cleanup INT TERM

wait "$WEBSITE_PID" "$BACKOFFICE_PID"


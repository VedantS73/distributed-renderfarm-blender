#!/bin/bash
cd "$(dirname "$0")"

set -e

cleanup() {
  echo "Stopping background processes..."
  kill $BACKEND_PID $WORKER_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Clearing jobs and render_output..."
rm -rf jobs render_output
mkdir -p jobs render_output

echo "Starting backend server..."
python3 run.py &
BACKEND_PID=$!

sleep 3

echo "Starting worker node..."
python3 worker.py &
WORKER_PID=$!

echo "All processes started."
wait

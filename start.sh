#!/bin/bash
cd "$(dirname "$0")"

echo "Clearing jobs and render_output..."
rm -rf jobs render_output
mkdir -p jobs render_output

echo "Starting backend server..."
python3 run.py &
sleep 3

echo "Starting worker node..."
python3 worker.py &

echo "All processes started."
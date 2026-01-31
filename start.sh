#!/bin/bash

# Go to script directory
cd "$(dirname "$0")"

set -e

echo "Clearing jobs and render_output..."
rm -rf jobs render_output
mkdir -p jobs render_output

PROJECT_DIR="$(pwd)"

echo "Starting backend server in new Terminal (venv activated)..."
osascript <<EOF
tell application "Terminal"
    do script "cd \"$PROJECT_DIR\" && source venv/bin/activate && python3 run_desktop.py"
end tell
EOF

sleep 3

echo "Starting worker node in new Terminal (venv activated)..."
osascript <<EOF
tell application "Terminal"
    do script "cd \"$PROJECT_DIR\" && source venv/bin/activate && python3 worker.py"
end tell
EOF

echo "All processes started."

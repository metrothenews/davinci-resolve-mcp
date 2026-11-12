#!/bin/bash
# Double-click to open latest avenue resolve. DaVinci Resolve Studio should be running.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up..."
  python3 -m venv .venv && .venv/bin/pip install -q pywebview numpy || { echo "Setup failed."; read -r; exit 1; }
fi
exec .venv/bin/python -m app.main

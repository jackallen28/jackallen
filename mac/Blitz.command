#!/bin/bash
# Start Blitz and open it in the browser. Double-click in Finder.
#
# First run builds a Python environment (about a minute). After that it is
# instant. Close this window (or press Ctrl-C) to stop the app.
set -euo pipefail
cd "$(dirname "$0")/.."

pick_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
      echo "$candidate"; return 0
    fi
  done
  return 1
}

if [ ! -x .venv/bin/blitz ]; then
  PY="$(pick_python)" || {
    echo "Needs Python 3.11 or newer. macOS ships 3.9; install one with:"
    echo "    brew install python@3.12"
    read -r -p "Press Return to close." _
    exit 1
  }
  echo "Setting up .venv with $PY (one-off)…"
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi

.venv/bin/blitz init >/dev/null
echo "Starting Blitz. Leave this window open while you use it."
exec .venv/bin/blitz serve --open index

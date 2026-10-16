#!/usr/bin/env bash
# Install a PiPath menu entry and desktop shortcut for the current user.
#   ./install.sh             menu entry + desktop icon
#   ./install.sh --autostart also open PiPath when the user logs in
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

python3 - <<'EOF' || { echo "PiPath needs Python 3.11+ with Tkinter (sudo apt install python3-tk)"; exit 1; }
import sys, tkinter
assert sys.version_info >= (3, 11)
EOF

python3 -c "import gpiozero" 2>/dev/null || echo "Note: gpiozero not found. GPIO projects need: sudo apt install python3-gpiozero python3-lgpio"

ENTRY="[Desktop Entry]
Type=Application
Name=PiPath
Comment=Learn Python step by step
Exec=python3 \"$HERE/main.py\"
Path=$HERE
Icon=applications-development
Terminal=false
Categories=Development;Education;"

mkdir -p "$HOME/.local/share/applications"
echo "$ENTRY" > "$HOME/.local/share/applications/pipath.desktop"

if [ -d "$HOME/Desktop" ]; then
  echo "$ENTRY" > "$HOME/Desktop/pipath.desktop"
  chmod +x "$HOME/Desktop/pipath.desktop"
fi

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  echo "$ENTRY" > "$HOME/.config/autostart/pipath.desktop"
  echo "PiPath will open automatically at login."
fi

echo "PiPath installed. Find it in the menu under Programming, or on the desktop."

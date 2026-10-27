#!/usr/bin/env bash
# Record the PiPath walkthrough and render both videos (with captions, and clean).
#   tools/walkthrough/make.sh [OUT_DIR]          (default: walkthrough_out)
# Needs: Xvfb (xvfb-run), ffmpeg, a Python with Tk + gpiozero (RECORD_PY), a Python with Pillow (RENDER_PY).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-walkthrough_out}"
RECORD_PY="${RECORD_PY:-python3}"
RENDER_PY="${RENDER_PY:-python3}"
rm -rf "$OUT"
xvfb-run -a -s "-screen 0 1600x900x24" "$RECORD_PY" "$HERE/traffic_lights.py" "$OUT"
"$RENDER_PY" "$HERE/studio.py" render "$OUT" "PiPath" "Traffic Lights: a walkthrough" \
  "Banyule Nillumbik Tech School  ·  Python on the Raspberry Pi"
echo "Videos in $OUT/"

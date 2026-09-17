#!/bin/bash
# Index course materials for Blitz. Double-click in Finder, or run from Terminal.
#
#   mac/index-materials.command physics sources/vcaa/physics-study-design.pdf sources/physics/
#
# With no arguments it asks. Every PDF in the materials folder is indexed as a
# book (Checkpoints, textbook or exam paper, detected per file); every .json
# there is treated as a question pack and imported. Nothing leaves the machine
# and no model runs: this is PyMuPDF, a concept lexicon and SQLite.
set -euo pipefail

cd "$(dirname "$0")/.."

# --- a Python new enough, and the venv ---------------------------------------
pick_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
        echo "$candidate"; return 0
      fi
    fi
  done
  return 1
}

if [ ! -x .venv/bin/python ]; then
  PY="$(pick_python)" || {
    echo "Needs Python 3.11 or newer. macOS ships 3.9; install one with:"
    echo "    brew install python@3.12"
    exit 1
  }
  echo "Setting up .venv with $PY (one-off)…"
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi
BLITZ=".venv/bin/blitz"
[ -x "$BLITZ" ] || .venv/bin/pip install --quiet -e .

# --- what to index -----------------------------------------------------------
# Arguments given on the command line are taken as given (an empty study
# design argument means "keep the one already imported"); anything not given
# is asked for, which is what a double-click from Finder gets.
SUBJECT="${1:-}"
DESIGN="${2:-}"
FOLDER="${3:-}"

if [ $# -lt 1 ]; then
  echo "Subjects Blitz knows:"
  "$BLITZ" subjects | sed 's/^/    /'
  read -r -p "Subject id (e.g. physics): " SUBJECT
fi
if [ $# -lt 2 ]; then
  read -r -p "VCAA study design PDF (blank to keep the one already imported): " DESIGN
fi
if [ $# -lt 3 ]; then
  read -r -p "Folder of PDFs / packs to index [sources/$SUBJECT]: " FOLDER
fi
FOLDER="${FOLDER:-sources/$SUBJECT}"
[ -n "$SUBJECT" ] || { echo "A subject id is needed."; exit 1; }
# Finder drops paths with trailing spaces and escaped characters; tidy them.
DESIGN="$(echo "$DESIGN" | sed -e 's/[[:space:]]*$//' -e "s/\\\\ / /g")"
FOLDER="$(echo "$FOLDER" | sed -e 's/[[:space:]]*$//' -e "s/\\\\ / /g")"

[ -d "$FOLDER" ] || { echo "No such folder: $FOLDER"; exit 1; }

"$BLITZ" init >/dev/null

# --- the study design first, so everything below is tagged against it -------
if [ -n "$DESIGN" ]; then
  [ -f "$DESIGN" ] || { echo "No such file: $DESIGN"; exit 1; }
  echo "== Study design: $DESIGN"
  "$BLITZ" import-study-design "$DESIGN" --subject "$SUBJECT"
fi

# --- then every book and pack in the folder ----------------------------------
shopt -s nullglob nocaseglob
found=0
for pack in "$FOLDER"/*.json; do
  # A pack names its subject and holds questions; any other JSON lying in the
  # folder (a model's own stats or audit files) is not ours to import.
  if ! grep -q '"subject_id"' "$pack" || ! grep -q '"questions"' "$pack"; then
    echo; echo "-- $(basename "$pack"): not a question pack, skipped"
    continue
  fi
  found=1
  echo; echo "== Pack: $pack"
  "$BLITZ" import-pack "$pack" || echo "   (not imported — fix the errors above and re-run)"
done
for pdf in "$FOLDER"/*.pdf; do
  found=1
  name="$(basename "$pdf" .pdf | tr 'A-Z ' 'a-z-' | tr -cd 'a-z0-9-')"
  echo; echo "== Book: $pdf"
  # caffeinate keeps the Mac from idle-sleeping mid-book; harmless if absent.
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i "$BLITZ" index "$pdf" --subject "$SUBJECT" --source-id "$name"
  else
    "$BLITZ" index "$pdf" --subject "$SUBJECT" --source-id "$name"
  fi
done
shopt -u nullglob nocaseglob

if [ "$found" = 0 ]; then
  echo "Nothing to index in $FOLDER (looked for *.pdf and *.json)."
  exit 1
fi

echo; echo "== Coverage for $SUBJECT"
"$BLITZ" coverage "$SUBJECT"
echo
echo "Done. Start the app with:  .venv/bin/blitz serve   (then open http://127.0.0.1:8712)"

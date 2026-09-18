"""Paths and tunables.

Everything a person puts in or gets out lives under one root folder, so it
can be found in Finder and backed up as a unit:

    ~/Documents/Blitz/
      study-designs/   imported study designs (the shipped ones are the fallback)
      sources/         uploaded books, worksheets and packs, per subject
      index/           the question index and figure crops (rebuildable)
      exports/         "index materials" result folders and their zips
      blitzes/         every generated sheet
      students/        the master workbook and one per student or class
      backups/         zips made by "Create backup" / blitz backup

BLITZ_ROOT in the environment moves the whole tree (a server uses a mounted
disk; a developer points it at the checkout).
"""

from __future__ import annotations

import os
from pathlib import Path


def default_root() -> Path:
    env = os.environ.get("BLITZ_ROOT")
    if env:
        return Path(env).expanduser()
    documents = Path.home() / "Documents"
    return (documents if documents.is_dir() else Path.home()) / "Blitz"


ROOT = default_root()

USER_DESIGN_DIR = ROOT / "study-designs"
# Where uploaded and dropped-in licensed PDFs live (never committed).
SOURCES_DIR = ROOT / "sources"
# Derived artefacts: the question index and the cropped figures.
DATA_DIR = ROOT / "index"
CROPS_DIR = DATA_DIR / "crops"
DB_PATH = DATA_DIR / "blitz.sqlite3"
EXPORTS_DIR = ROOT / "exports"
# Generated sheets.
OUT_DIR = ROOT / "blitzes"
STUDENTS_DIR = ROOT / "students"
BACKUPS_DIR = ROOT / "backups"

# The study designs shipped with the tool.
STUDY_DESIGN_DIR = Path(__file__).resolve().parent / "studydesign" / "data"

# Crops are rendered at this zoom relative to the PDF's own 72dpi page space.
# 3.0 => ~216dpi, which stays sharp when a figure is scaled to a half-column.
CROP_ZOOM = 3.0


def ensure_dirs() -> None:
    for d in (ROOT, USER_DESIGN_DIR, SOURCES_DIR, DATA_DIR, CROPS_DIR,
              EXPORTS_DIR, OUT_DIR, STUDENTS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)

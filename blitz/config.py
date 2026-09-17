"""Paths and tunables. Everything lives under the project root by default."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("BLITZ_ROOT", Path(__file__).resolve().parent.parent))

# Where you drop your own licensed PDFs (gitignored).
SOURCES_DIR = ROOT / "sources"
# Derived artefacts: the question index and the cropped figures.
DATA_DIR = ROOT / "data"
CROPS_DIR = DATA_DIR / "crops"
DB_PATH = DATA_DIR / "blitz.sqlite3"
# Generated sheets.
OUT_DIR = ROOT / "out"

STUDY_DESIGN_DIR = Path(__file__).resolve().parent / "studydesign" / "data"

# Crops are rendered at this zoom relative to the PDF's own 72dpi page space.
# 3.0 => ~216dpi, which stays sharp when a figure is scaled to a half-column.
CROP_ZOOM = 3.0


def ensure_dirs() -> None:
    for d in (SOURCES_DIR, DATA_DIR, CROPS_DIR, OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)

"""Seed the index with the sample question bank.

Lets you drive the whole tool — pick dot points, generate a sheet, print it —
before any licensed PDF has been ingested. Every sample question is flagged
`generated`, so a real corpus always outranks it in the picker and you can shut
it out entirely with `allow_generated=False`.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..db import insert_question, upsert_source
from ..studydesign import load_study_design

CORPUS_DIR = Path(__file__).resolve().parent


def sample_files() -> list[Path]:
    return sorted(CORPUS_DIR.glob("sample_*.yaml"))


def load_sample(conn: sqlite3.Connection, subject_id: str) -> int:
    """Insert the sample bank for one subject. Returns the number of questions."""
    path = CORPUS_DIR / f"sample_{subject_id}.yaml"
    if not path.exists():
        return 0

    design = load_study_design(subject_id)
    valid_kk = {kk.id for kk in design.all_key_knowledge()}
    valid_qt = {qt.id for qt in design.question_types}

    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    src = doc["source"]
    upsert_source(
        conn, id=src["id"], subject_id=subject_id, kind=src.get("kind", "generated"),
        title=src.get("title", "Blitz sample bank"), path=str(path),
        page_offset=0,
        ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    n = 0
    for item in doc.get("questions", []):
        kk_ids = item["kk"] if isinstance(item["kk"], list) else [item["kk"]]
        unknown = [k for k in kk_ids if k not in valid_kk]
        if unknown:
            raise ValueError(
                f"{path.name}: question references unknown dot point(s) {unknown}. "
                "The study design and the sample bank are out of sync."
            )
        if item["type"] not in valid_qt:
            raise ValueError(f"{path.name}: unknown question type {item['type']!r}")

        qid = f"{src['id']}-" + hashlib.sha1(item["body"].encode()).hexdigest()[:12]
        insert_question(conn, {
            "id": qid,
            "subject_id": subject_id,
            "source_id": src["id"],
            "question_type": item["type"],
            "body": item["body"].strip(),
            "options": item.get("options"),
            "answer": (item.get("answer") or "").strip() or None,
            "marks": item.get("marks"),
            "difficulty": item.get("difficulty"),
            "figure_path": None,
            "figure_caption": item.get("caption"),
            "citation": f"{src.get('title', 'Blitz sample bank')} (sample)",
            "generated": 1,
            "verified": 0,
        }, kk_ids)
        n += 1

    conn.commit()
    return n


def load_all_samples(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {}
    for path in sample_files():
        subject_id = path.stem.removeprefix("sample_")
        counts[subject_id] = load_sample(conn, subject_id)
    return counts

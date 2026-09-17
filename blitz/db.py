"""SQLite index of every question extracted from your sources.

One row per question. `body` is the question text; `figure_path` points at a
PNG crop taken straight from the source PDF when the question needs its diagram.
FTS5 gives us keyword search so the notes box can bias selection.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source (
    id            TEXT PRIMARY KEY,      -- 'physics-checkpoints'
    subject_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,         -- checkpoints | textbook | vcaa-exam | generated
    title         TEXT NOT NULL,
    path          TEXT,                  -- absolute path of the PDF on this machine
    edition       TEXT,
    page_offset   INTEGER NOT NULL DEFAULT 0,  -- printed page number - pdf page index
    ingested_at   TEXT
);

CREATE TABLE IF NOT EXISTS question (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL,
    source_id     TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
    question_type TEXT NOT NULL,         -- a QuestionType.id from the study design
    body          TEXT NOT NULL,
    options       TEXT,                  -- JSON list for multiple choice, else NULL
    answer        TEXT,                  -- worked solution text
    answer_figure TEXT,                  -- crop of the printed solution, if any
    marks         INTEGER,
    difficulty    INTEGER,               -- 1 easy .. 5 hard
    figure_path   TEXT,                  -- crop of the question's diagram, if any
    figure_caption TEXT,
    pdf_page      INTEGER,               -- 0-based page index in the source PDF
    printed_page  TEXT,                  -- page number as printed in the book
    citation      TEXT,                  -- human-readable, printed on the sheet
    generated     INTEGER NOT NULL DEFAULT 0,  -- 1 = written by the tagging model
    verified      INTEGER NOT NULL DEFAULT 0,  -- 1 = a human has eyeballed it
    extra         TEXT                   -- JSON escape hatch
);

-- A question can legitimately cover more than one dot point.
CREATE TABLE IF NOT EXISTS question_kk (
    question_id   TEXT NOT NULL REFERENCES question(id) ON DELETE CASCADE,
    kk_id         TEXT NOT NULL,
    confidence    REAL NOT NULL DEFAULT 1.0,
    primary_kk    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (question_id, kk_id)
);

CREATE INDEX IF NOT EXISTS idx_question_subject ON question(subject_id);
CREATE INDEX IF NOT EXISTS idx_question_type ON question(subject_id, question_type);
CREATE INDEX IF NOT EXISTS idx_qkk_kk ON question_kk(kk_id);

CREATE VIRTUAL TABLE IF NOT EXISTS question_fts USING fts5(
    body, answer, figure_caption,
    content='question', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS question_ai AFTER INSERT ON question BEGIN
    INSERT INTO question_fts(rowid, body, answer, figure_caption)
    VALUES (new.rowid, new.body, new.answer, new.figure_caption);
END;
CREATE TRIGGER IF NOT EXISTS question_ad AFTER DELETE ON question BEGIN
    INSERT INTO question_fts(question_fts, rowid, body, answer, figure_caption)
    VALUES ('delete', old.rowid, old.body, old.answer, old.figure_caption);
END;
CREATE TRIGGER IF NOT EXISTS question_au AFTER UPDATE ON question BEGIN
    INSERT INTO question_fts(question_fts, rowid, body, answer, figure_caption)
    VALUES ('delete', old.rowid, old.body, old.answer, old.figure_caption);
    INSERT INTO question_fts(rowid, body, answer, figure_caption)
    VALUES (new.rowid, new.body, new.answer, new.figure_caption);
END;

-- Sheets we've generated, so the picker can avoid repeating questions.
CREATE TABLE IF NOT EXISTS sheet (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL,
    title         TEXT,
    created_at    TEXT NOT NULL,
    spec          TEXT NOT NULL,         -- JSON SheetSpec
    pdf_path      TEXT
);
CREATE TABLE IF NOT EXISTS sheet_question (
    sheet_id      TEXT NOT NULL REFERENCES sheet(id) ON DELETE CASCADE,
    question_id   TEXT NOT NULL,
    position      INTEGER NOT NULL,
    PRIMARY KEY (sheet_id, question_id)
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_source(conn: sqlite3.Connection, **fields) -> None:
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{c}=excluded.{c}" for c in fields if c != "id")
    conn.execute(
        f"INSERT INTO source ({cols}) VALUES ({marks}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        tuple(fields.values()),
    )


def insert_question(conn: sqlite3.Connection, q: dict, kk_ids: Iterable[str]) -> None:
    """Insert (or replace) a question and its dot-point links."""
    payload = dict(q)
    if isinstance(payload.get("options"), (list, tuple)):
        payload["options"] = json.dumps(list(payload["options"]))
    if isinstance(payload.get("extra"), dict):
        payload["extra"] = json.dumps(payload["extra"])

    cols = ", ".join(payload)
    marks = ", ".join("?" for _ in payload)
    conn.execute(f"INSERT OR REPLACE INTO question ({cols}) VALUES ({marks})",
                 tuple(payload.values()))
    conn.execute("DELETE FROM question_kk WHERE question_id = ?", (payload["id"],))
    kk_ids = list(kk_ids)
    for i, kk in enumerate(kk_ids):
        if isinstance(kk, str):
            kk_id, conf = kk, 1.0
        else:
            kk_id, conf = kk
        conn.execute(
            "INSERT OR REPLACE INTO question_kk (question_id, kk_id, confidence, primary_kk)"
            " VALUES (?, ?, ?, ?)",
            (payload["id"], kk_id, conf, 1 if i == 0 else 0),
        )


def coverage(conn: sqlite3.Connection, subject_id: str) -> dict[str, int]:
    """How many questions we hold per key-knowledge dot point."""
    rows = conn.execute(
        "SELECT kk.kk_id AS kk_id, COUNT(*) AS n FROM question_kk kk "
        "JOIN question q ON q.id = kk.question_id WHERE q.subject_id = ? "
        "GROUP BY kk.kk_id",
        (subject_id,),
    ).fetchall()
    return {r["kk_id"]: r["n"] for r in rows}


def coverage_by_type(conn: sqlite3.Connection, subject_id: str) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        "SELECT kk.kk_id AS kk_id, q.question_type AS qt, COUNT(*) AS n "
        "FROM question_kk kk JOIN question q ON q.id = kk.question_id "
        "WHERE q.subject_id = ? GROUP BY kk.kk_id, q.question_type",
        (subject_id,),
    ).fetchall()
    return {(r["kk_id"], r["qt"]): r["n"] for r in rows}

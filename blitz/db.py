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
    body          TEXT NOT NULL,        -- stem and parts joined; used for search
    stem          TEXT,                  -- the shared scenario, without the parts
    parts         TEXT,                  -- JSON list of "a. …", "b. …" sub-parts
    options       TEXT,                  -- JSON list for multiple choice, else NULL
    answer        TEXT,                  -- worked solution text
    answer_figure TEXT,                  -- crop of the printed solution, if any
    marks         INTEGER,
    difficulty    INTEGER,               -- 1 easy .. 5 hard
    figure_path   TEXT,                  -- crop of the question's diagram, if any
    figure_caption TEXT,
    -- Natural width of the crop in PDF points. Crops are rendered at 3x zoom,
    -- so the PNG's pixel size cannot tell a full-page strip from a small
    -- diagram — and that distinction decides whether the sheet can use two
    -- columns without squashing the book's text into illegibility.
    figure_pt_width REAL,
    -- Every figure for this question, in order, as JSON:
    --   [{"role": "question"|"answer", "path": ..., "pt_width": ...,
    --     "caption": ...}, ...]
    -- A question routinely needs several: a page continuation, a shared
    -- scenario printed above it, or an earlier question it depends on. The
    -- columns above are the FIRST question figure, kept for simple queries.
    figures       TEXT,
    -- Scenario text shared with, and printed above, this question. Carried
    -- separately from the stem so it can be shown once above a group, and so a
    -- question is never put on a sheet without the context that makes it
    -- answerable.
    context       TEXT,
    -- Questions this one cannot be answered without, as a JSON list of ids.
    depends_on    TEXT,
    -- Why this row still needs a human, as a JSON list. From the pack's own
    -- flags, or the draft extractor's.
    review        TEXT,
    -- 'text'  : print body/options as text (the normal case)
    -- 'crop'  : the text could not be faithfully reconstructed (stacked
    --           fractions, equation-editor glyphs), so print the page image
    --           instead and keep the text only for search and tagging.
    render_mode   TEXT NOT NULL DEFAULT 'text',
    answer_mode   TEXT NOT NULL DEFAULT 'text',
    provenance    TEXT,                  -- e.g. "VCAA 2019 SA Q14"
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

-- Teaching content, section by section. The other half of a textbook: a
-- revision sheet can point a student at "6.3 The photoelectric effect, p. 142"
-- for the dot point they are stuck on.
CREATE TABLE IF NOT EXISTS passage (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL,
    source_id     TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    section       TEXT,                  -- "6.3", if the book numbers sections
    level         INTEGER NOT NULL DEFAULT 2,
    body          TEXT NOT NULL,
    page_start    INTEGER NOT NULL,      -- 0-based PDF page index
    page_end      INTEGER NOT NULL,
    printed_page  TEXT,                  -- as printed in the book, if known
    confidence    REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS passage_kk (
    passage_id    TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    kk_id         TEXT NOT NULL,
    PRIMARY KEY (passage_id, kk_id)
);
CREATE INDEX IF NOT EXISTS idx_passage_subject ON passage(subject_id);
CREATE INDEX IF NOT EXISTS idx_pkk_kk ON passage_kk(kk_id);

CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(
    title, body, content='passage', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS passage_ai AFTER INSERT ON passage BEGIN
    INSERT INTO passage_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS passage_ad AFTER DELETE ON passage BEGIN
    INSERT INTO passage_fts(passage_fts, rowid, title, body)
    VALUES ('delete', old.rowid, old.title, old.body);
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

-- A student or a class: a name, and through sheet.student_id, everything
-- they have been given.
CREATE TABLE IF NOT EXISTS student (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL
);

-- Per-subject counters for the serial numbers printed on every question.
CREATE TABLE IF NOT EXISTS serial_counter (
    subject_id    TEXT PRIMARY KEY,
    next_value    INTEGER NOT NULL
);
"""

# Columns added after the first release. SQLite cannot add them inside the
# CREATE TABLE IF NOT EXISTS above for an existing database, so each is
# checked for and added on connect.
_MIGRATIONS = {
    "question": [
        ("serial", "TEXT"),          # PH-0413: printed on sheets, searchable
        ("flag", "TEXT"),            # incomplete | corrupt | wrong, or NULL
        ("flag_note", "TEXT"),
        ("flagged_at", "TEXT"),
    ],
    "sheet": [
        ("student_id", "TEXT"),
    ],
}


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _MIGRATIONS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ctype in columns:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ctype}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_question_serial "
                 "ON question(serial)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sheet_student ON sheet(student_id)")
    assign_serials(conn)
    conn.commit()


# ---------------------------------------------------------------------------
# Serial numbers
# ---------------------------------------------------------------------------

def serial_prefix(subject_id: str) -> str:
    """PH for physics, BM for business-management, LS for legal-studies."""
    words = [w for w in subject_id.split("-") if w]
    if len(words) == 1:
        return words[0][:2].upper()
    return "".join(w[0] for w in words)[:4].upper()


def next_serial(conn: sqlite3.Connection, subject_id: str) -> str:
    row = conn.execute("SELECT next_value FROM serial_counter WHERE subject_id = ?",
                       (subject_id,)).fetchone()
    n = row["next_value"] if row else 1
    conn.execute("INSERT INTO serial_counter (subject_id, next_value) VALUES (?, ?) "
                 "ON CONFLICT(subject_id) DO UPDATE SET next_value = excluded.next_value",
                 (subject_id, n + 1))
    return f"{serial_prefix(subject_id)}-{n:04d}"


def assign_serials(conn: sqlite3.Connection) -> None:
    """Give every question without a serial one, in a stable order."""
    rows = conn.execute("SELECT id, subject_id FROM question WHERE serial IS NULL "
                        "ORDER BY subject_id, source_id, id").fetchall()
    for row in rows:
        conn.execute("UPDATE question SET serial = ? WHERE id = ?",
                     (next_serial(conn, row["subject_id"]), row["id"]))


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

    # A re-import replaces the row, but the serial printed on past sheets and
    # any flag a person has set are theirs to keep.
    prior = conn.execute("SELECT serial, flag, flag_note, flagged_at FROM question "
                         "WHERE id = ?", (payload["id"],)).fetchone()
    if prior and prior["serial"]:
        payload.setdefault("serial", prior["serial"])
        for col in ("flag", "flag_note", "flagged_at"):
            payload.setdefault(col, prior[col])
    else:
        payload.setdefault("serial", next_serial(conn, payload["subject_id"]))

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


def insert_passage(conn: sqlite3.Connection, p: dict, kk_ids: Iterable[str]) -> None:
    cols = ", ".join(p)
    marks = ", ".join("?" for _ in p)
    conn.execute(f"INSERT OR REPLACE INTO passage ({cols}) VALUES ({marks})",
                 tuple(p.values()))
    conn.execute("DELETE FROM passage_kk WHERE passage_id = ?", (p["id"],))
    for kk in kk_ids:
        conn.execute("INSERT OR REPLACE INTO passage_kk (passage_id, kk_id) VALUES (?, ?)",
                     (p["id"], kk))


def passage_coverage(conn: sqlite3.Connection, subject_id: str) -> dict[str, int]:
    """How many teaching passages we hold per dot point."""
    rows = conn.execute(
        "SELECT pk.kk_id AS kk_id, COUNT(*) AS n FROM passage_kk pk "
        "JOIN passage p ON p.id = pk.passage_id WHERE p.subject_id = ? "
        "GROUP BY pk.kk_id", (subject_id,)).fetchall()
    return {r["kk_id"]: r["n"] for r in rows}


def coverage(conn: sqlite3.Connection, subject_id: str) -> dict[str, int]:
    """How many questions we hold per key-knowledge dot point."""
    rows = conn.execute(
        "SELECT kk.kk_id AS kk_id, COUNT(*) AS n FROM question_kk kk "
        "JOIN question q ON q.id = kk.question_id WHERE q.subject_id = ? "
        "GROUP BY kk.kk_id",
        (subject_id,),
    ).fetchall()
    return {r["kk_id"]: r["n"] for r in rows}


def coverage_by_source(conn: sqlite3.Connection, subject_id: str
                       ) -> dict[tuple[str, str], int]:
    """Questions per (dot point, source), for comparing two indexes of one book."""
    rows = conn.execute(
        "SELECT kk.kk_id AS kk_id, q.source_id AS src, COUNT(*) AS n "
        "FROM question_kk kk JOIN question q ON q.id = kk.question_id "
        "WHERE q.subject_id = ? GROUP BY kk.kk_id, q.source_id",
        (subject_id,),
    ).fetchall()
    return {(r["kk_id"], r["src"]): r["n"] for r in rows}


def coverage_by_type(conn: sqlite3.Connection, subject_id: str) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        "SELECT kk.kk_id AS kk_id, q.question_type AS qt, COUNT(*) AS n "
        "FROM question_kk kk JOIN question q ON q.id = kk.question_id "
        "WHERE q.subject_id = ? GROUP BY kk.kk_id, q.question_type",
        (subject_id,),
    ).fetchall()
    return {(r["kk_id"], r["qt"]): r["n"] for r in rows}


# ---------------------------------------------------------------------------
# Flags, students, sheets
# ---------------------------------------------------------------------------

FLAGS = ("incomplete", "corrupt", "wrong")


def set_flag(conn: sqlite3.Connection, question_id: str, flag: str | None,
             note: str | None = None) -> None:
    """Mark a question as unusable (or clear the mark). Flagged questions
    never go on a sheet."""
    from datetime import datetime, timezone

    if flag is not None and flag not in FLAGS:
        raise ValueError(f"flag must be one of {FLAGS}, got {flag!r}")
    when = datetime.now(timezone.utc).isoformat(timespec="seconds") if flag else None
    conn.execute("UPDATE question SET flag = ?, flag_note = ?, flagged_at = ? WHERE id = ?",
                 (flag, note if flag else None, when, question_id))


def student_id_for(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "student"


def get_or_create_student(conn: sqlite3.Connection, name: str) -> dict:
    from datetime import datetime, timezone

    name = " ".join(name.split())
    if not name:
        raise ValueError("a student or class needs a name")
    row = conn.execute("SELECT * FROM student WHERE lower(name) = lower(?)",
                       (name,)).fetchone()
    if row:
        return dict(row)
    sid = student_id_for(name)
    base, n = sid, 2
    while conn.execute("SELECT 1 FROM student WHERE id = ?", (sid,)).fetchone():
        sid = f"{base}-{n}"
        n += 1
    conn.execute("INSERT INTO student (id, name, created_at) VALUES (?, ?, ?)",
                 (sid, name, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return dict(conn.execute("SELECT * FROM student WHERE id = ?", (sid,)).fetchone())


def student_history(conn: sqlite3.Connection, student_id: str) -> list[str]:
    """Every question id this student has been given, oldest sheet first."""
    return [r["question_id"] for r in conn.execute(
        "SELECT sq.question_id FROM sheet_question sq JOIN sheet s ON s.id = sq.sheet_id "
        "WHERE s.student_id = ? ORDER BY s.created_at, sq.position", (student_id,))]


def record_sheet(conn: sqlite3.Connection, *, sheet_id: str, subject_id: str,
                 title: str, spec_json: str, pdf_path: str | None,
                 question_ids: list[str], student_id: str | None = None) -> None:
    from datetime import datetime, timezone

    conn.execute(
        "INSERT OR REPLACE INTO sheet (id, subject_id, title, created_at, spec, "
        "pdf_path, student_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sheet_id, subject_id, title,
         datetime.now(timezone.utc).isoformat(timespec="seconds"),
         spec_json, pdf_path, student_id))
    conn.execute("DELETE FROM sheet_question WHERE sheet_id = ?", (sheet_id,))
    for i, qid in enumerate(question_ids, start=1):
        conn.execute("INSERT OR REPLACE INTO sheet_question (sheet_id, question_id, "
                     "position) VALUES (?, ?, ?)", (sheet_id, qid, i))

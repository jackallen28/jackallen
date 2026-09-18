"""First run: an empty Blitz folder becomes a working one.

Nothing is assumed about what a new person teaches. Until the folder holds a
`blitz.json` the app shows only the setup page, which offers two ways in:

* **restore a backup** — the zip `Create backup` makes, from another machine
  or an earlier install; everything comes back as it was;
* **start from scratch** — a new, empty index. The study designs that ship
  with the tool (VCE Physics, VCE Business Management) are offered as
  optional starters; any other subject is added later by uploading its VCAA
  study design on the Index materials page. A handful of sample questions
  can be included to try the sheet generator before any book is indexed.

A folder that already holds an index from before this page existed is
recognised and offered as a third option: keep it.

Once set up, the study designs in use are the ones in the folder's
`study-designs/`; the shipped copies are only templates, so a person who
declined Physics never sees it.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from . import config

VERSION = 1


def settings_path(root: Path | None = None) -> Path:
    return Path(root or config.ROOT) / "blitz.json"


def is_set_up(root: Path | None = None) -> bool:
    return settings_path(root).exists()


def read_settings(root: Path | None = None) -> dict:
    path = settings_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_settings(root: Path, **fields) -> dict:
    data = {"version": VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **fields}
    settings_path(root).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def shipped_subjects() -> list[dict]:
    """The study designs that come with the tool, as starter options."""
    from .studydesign.loader import load_study_design_file, _NOT_A_DESIGN

    out = []
    for path in sorted(config.STUDY_DESIGN_DIR.glob("*.yaml")):
        if path.name.endswith(_NOT_A_DESIGN):
            continue
        try:
            d = load_study_design_file(path)
        except Exception:
            continue
        n = sum(len(a.key_knowledge) for a in d.all_areas())
        out.append({"id": d.subject_id, "name": d.subject_name,
                    "dot_points": n, "verified": d.fully_verified,
                    "lexicon": (config.STUDY_DESIGN_DIR / f"{d.subject_id}-lexicon.yaml").exists()})
    return out


def enable_shipped_subject(subject_id: str, root: Path | None = None) -> Path:
    """Copy a shipped study design (and its lexicon) into the person's folder."""
    root = Path(root or config.ROOT)
    src = config.STUDY_DESIGN_DIR / f"{subject_id}.yaml"
    if not src.exists():
        raise FileNotFoundError(f"no shipped study design called {subject_id!r}")
    dest_dir = root / "study-designs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        shutil.copyfile(src, dest)
    lex = config.STUDY_DESIGN_DIR / f"{subject_id}-lexicon.yaml"
    if lex.exists() and not (dest_dir / lex.name).exists():
        shutil.copyfile(lex, dest_dir / lex.name)
    return dest


def status(root: Path | None = None) -> dict:
    """What the setup page needs to know about this folder."""
    import sqlite3

    root = Path(root or config.ROOT)
    db_path = root / "index" / "blitz.sqlite3"
    existing = {"index": db_path.exists(), "questions": 0, "students": 0,
                "subjects": []}
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            existing["questions"] = conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
            existing["students"] = conn.execute("SELECT COUNT(*) FROM student").fetchone()[0]
            existing["subjects"] = [r[0] for r in conn.execute(
                "SELECT DISTINCT subject_id FROM question ORDER BY subject_id")]
            conn.close()
        except sqlite3.Error:
            pass
    return {"root": str(root), "set_up": is_set_up(root),
            "settings": read_settings(root), "shipped": shipped_subjects(),
            "existing": existing}


def _ensure_dirs(root: Path) -> None:
    for name in ("study-designs", "sources", "index/crops", "exports",
                 "blitzes", "students", "backups"):
        (root / name).mkdir(parents=True, exist_ok=True)


def _clear_caches() -> None:
    from .ingest.lexicon import load_lexicon
    from .studydesign.loader import load_study_design

    load_study_design.cache_clear()
    load_lexicon.cache_clear()


def setup_scratch(subjects: list[str], samples: bool = False,
                  erase: bool = False, root: Path | None = None) -> dict:
    """A new index, with the chosen shipped subjects enabled."""
    from . import db

    root = Path(root or config.ROOT)
    _ensure_dirs(root)
    db_path = root / "index" / "blitz.sqlite3"
    if db_path.exists():
        if not erase:
            raise FileExistsError(
                "this folder already holds an index; choose 'keep it', restore "
                "a backup over it, or confirm starting over")
        aside = db_path.with_name(
            f"blitz.sqlite3.before-{datetime.now().strftime('%Y-%m-%d-%H%M')}")
        shutil.move(db_path, aside)
        for extra in (db_path.with_name(db_path.name + "-wal"),
                      db_path.with_name(db_path.name + "-shm")):
            if extra.exists():
                extra.unlink()
    for sid in subjects:
        enable_shipped_subject(sid, root)
    _clear_caches()
    loaded: dict[str, int] = {}
    with db.session(db_path) as conn:
        if samples:
            from .corpus.sample import load_sample, sample_files

            for path in sample_files():
                sid = path.stem.removeprefix("sample_")
                if sid in subjects:
                    loaded[sid] = load_sample(conn, sid)
    return _write_settings(root, mode="scratch", subjects=list(subjects),
                           samples=loaded)


def setup_restore(zip_path: Path, replace: bool = False,
                  root: Path | None = None, name: str | None = None) -> dict:
    """Everything back from a backup zip.

    `name` is what to record as the backup's name when the file on disk is
    a staged upload with a working name of its own.
    """
    from . import backup

    root = Path(root or config.ROOT)
    _ensure_dirs(root)
    result = backup.restore_backup(zip_path, root=root, replace=replace)
    _clear_caches()
    manifest = result["manifest"]
    return _write_settings(root, mode="restore", backup=name or zip_path.name,
                           backup_created_at=manifest.get("created_at"),
                           subjects=_subjects_in(root))


def setup_adopt(root: Path | None = None) -> dict:
    """Keep an index that was here before the setup page existed."""
    root = Path(root or config.ROOT)
    _ensure_dirs(root)
    db_path = root / "index" / "blitz.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError("there is no index here to keep")
    # Subjects the index holds questions for need their study design in the
    # folder, or the person would lose sight of their own questions.
    for sid in status(root)["existing"]["subjects"]:
        if (config.STUDY_DESIGN_DIR / f"{sid}.yaml").exists():
            enable_shipped_subject(sid, root)
    _clear_caches()
    return _write_settings(root, mode="adopt", subjects=_subjects_in(root))


def _subjects_in(root: Path) -> list[str]:
    from .studydesign.loader import _NOT_A_DESIGN

    folder = root / "study-designs"
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.yaml")
                  if not p.name.endswith(_NOT_A_DESIGN))

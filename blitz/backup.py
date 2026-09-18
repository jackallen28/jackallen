"""One zip that carries everything worth keeping.

If the app is updated, reinstalled or moved to another machine, this is the
file to take: the question index, every figure crop, the study designs that
were imported, the student record and its workbooks, and every sheet ever
made. Restoring is unzipping it into the Blitz folder, which `restore` does
with a guard against overwriting a live index by accident.

Left out on purpose: the uploaded source books (large, and already owned as
files elsewhere; a switch includes them), the export folders (rebuildable
from the index in one click) and Word-to-PDF conversions (rebuildable).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config

MANIFEST = "blitz-backup.json"
FORMAT = 1


@dataclass
class BackupReport:
    path: Path
    files: int = 0
    bytes: int = 0
    counts: dict = field(default_factory=dict)
    included_sources: bool = False

    def summary(self) -> str:
        mb = self.bytes / 1048576
        return (f"{self.path.name}: {self.files} files, {mb:.1f} MB; "
                f"{self.counts.get('questions', 0)} questions, "
                f"{self.counts.get('students', 0)} students, "
                f"{self.counts.get('sheets', 0)} sheets")


def _counts(db_path: Path) -> dict:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    try:
        out = {}
        for key, sql in (("questions", "SELECT COUNT(*) FROM question"),
                         ("sources", "SELECT COUNT(*) FROM source"),
                         ("students", "SELECT COUNT(*) FROM student"),
                         ("sheets", "SELECT COUNT(*) FROM sheet"),
                         ("flagged", "SELECT COUNT(*) FROM question WHERE flag IS NOT NULL")):
            try:
                out[key] = conn.execute(sql).fetchone()[0]
            except sqlite3.OperationalError:
                out[key] = 0
        return out
    finally:
        conn.close()


def _add_tree(zf: zipfile.ZipFile, folder: Path, arc_prefix: str,
              skip: tuple[str, ...] = ()) -> tuple[int, int]:
    n = size = 0
    if not folder.is_dir():
        return n, size
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(folder)
        if any(part in skip for part in rel.parts):
            continue
        zf.write(path, f"{arc_prefix}/{rel.as_posix()}")
        n += 1
        size += path.stat().st_size
    return n, size


def create_backup(out_dir: Path | None = None, include_sources: bool = False,
                  root: Path | None = None) -> BackupReport:
    """Write blitz-backup-<date>.zip under <root>/backups and return where."""
    root = Path(root or config.ROOT)
    out_dir = Path(out_dir or root / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    path = out_dir / f"blitz-backup-{stamp}.zip"
    db_path = root / "index" / "blitz.sqlite3"
    report = BackupReport(path=path, counts=_counts(db_path),
                          included_sources=include_sources)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # The database through SQLite's own backup, so the copy is consistent
        # even if the app is mid-write.
        if db_path.exists():
            snapshot = out_dir / f".{stamp}.sqlite3"
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(snapshot)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            zf.write(snapshot, "index/blitz.sqlite3")
            report.files += 1
            report.bytes += snapshot.stat().st_size
            snapshot.unlink()
        for folder, prefix, skip in (
            (root / "index" / "crops", "index/crops", ()),
            (root / "study-designs", "study-designs", ()),
            (root / "students", "students", ()),
            (root / "blitzes", "blitzes", ()),
        ):
            n, size = _add_tree(zf, folder, prefix, skip)
            report.files += n
            report.bytes += size
        if include_sources:
            n, size = _add_tree(zf, root / "sources", "sources")
            report.files += n
            report.bytes += size
        manifest = {
            "format": FORMAT,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(root),
            "included_sources": include_sources,
            "counts": report.counts,
            "files": report.files,
            "contents": ["index/blitz.sqlite3", "index/crops/", "study-designs/",
                         "students/", "blitzes/"] + (["sources/"] if include_sources else []),
            "restore": "blitz restore <this zip>, or unzip it into the Blitz folder",
        }
        zf.writestr(MANIFEST, json.dumps(manifest, indent=2))
    return report


def read_manifest(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        if MANIFEST not in zf.namelist():
            raise ValueError(f"{zip_path.name} is not a Blitz backup (no {MANIFEST})")
        return json.loads(zf.read(MANIFEST))


def restore_backup(zip_path: Path, root: Path | None = None,
                   replace: bool = False) -> dict:
    """Unpack a backup into the Blitz folder.

    Refuses if the folder already holds an index unless `replace` is given,
    in which case the current index is moved aside as index/blitz.sqlite3.before-restore
    rather than deleted.
    """
    root = Path(root or config.ROOT)
    manifest = read_manifest(zip_path)
    db_path = root / "index" / "blitz.sqlite3"
    if db_path.exists():
        if not replace:
            raise FileExistsError(
                f"{root} already has an index. Pass replace=True (blitz restore "
                "--replace) to move it aside and restore over it.")
        aside = db_path.with_suffix(".sqlite3.before-restore")
        shutil.move(db_path, aside)
    root.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir() or member.filename == MANIFEST:
                continue
            target = (root / member.filename).resolve()
            if root.resolve() not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
    return {"files": n, "manifest": manifest, "root": str(root)}

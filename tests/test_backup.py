"""A backup is one zip with everything worth keeping, and it restores."""

import sqlite3
import zipfile

import pytest

from blitz import backup, db
from blitz.corpus.sample import load_all_samples

from tests.test_indexer_ui import client as _client  # noqa: F401  (fixture)


def _root(tmp_path):
    """A Blitz folder laid out the way the app lays it out."""
    root = tmp_path / "Blitz"
    (root / "index" / "crops").mkdir(parents=True)
    (root / "study-designs").mkdir()
    (root / "students").mkdir()
    (root / "blitzes").mkdir()
    (root / "sources" / "physics").mkdir(parents=True)
    (root / "exports").mkdir()
    with db.session(root / "index" / "blitz.sqlite3") as conn:
        load_all_samples(conn)
        db.get_or_create_student(conn, "Sam")
    (root / "index" / "crops" / "fig.png").write_bytes(b"\x89PNG fake")
    (root / "study-designs" / "chemistry.yaml").write_text("subject_id: chemistry\n")
    (root / "students" / "MASTER.xlsx").write_bytes(b"PK fake")
    (root / "blitzes" / "blitz-physics-abc.pdf").write_bytes(b"%PDF fake")
    (root / "sources" / "physics" / "book.pdf").write_bytes(b"%PDF licensed")
    (root / "exports" / "junk.txt").write_text("rebuildable")
    return root


def test_backup_carries_the_key_files_and_nothing_rebuildable(tmp_path):
    root = _root(tmp_path)
    report = backup.create_backup(root=root)
    assert report.path.exists() and report.path.parent == root / "backups"
    with zipfile.ZipFile(report.path) as zf:
        names = set(zf.namelist())
    assert {"blitz-backup.json", "index/blitz.sqlite3", "index/crops/fig.png",
            "study-designs/chemistry.yaml", "students/MASTER.xlsx",
            "blitzes/blitz-physics-abc.pdf"} <= names
    assert not any(n.startswith("sources/") for n in names)
    assert not any(n.startswith("exports/") for n in names)
    manifest = backup.read_manifest(report.path)
    assert manifest["counts"]["questions"] > 0
    assert manifest["counts"]["students"] == 1
    assert report.counts == manifest["counts"]

    with_books = backup.create_backup(root=root, include_sources=True)
    with zipfile.ZipFile(with_books.path) as zf:
        assert "sources/physics/book.pdf" in zf.namelist()


def test_restore_refuses_a_live_index_unless_told_and_keeps_it_aside(tmp_path):
    root = _root(tmp_path)
    report = backup.create_backup(root=root)

    fresh = tmp_path / "Fresh"
    result = backup.restore_backup(report.path, root=fresh)
    assert result["files"] >= 5
    conn = sqlite3.connect(fresh / "index" / "blitz.sqlite3")
    assert conn.execute("SELECT COUNT(*) FROM student").fetchone()[0] == 1
    conn.close()
    assert (fresh / "blitzes" / "blitz-physics-abc.pdf").exists()

    with pytest.raises(FileExistsError):
        backup.restore_backup(report.path, root=fresh)
    backup.restore_backup(report.path, root=fresh, replace=True)
    assert (fresh / "index" / "blitz.sqlite3.before-restore").exists()

    (tmp_path / "not-a-backup.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    with pytest.raises(ValueError):
        backup.read_manifest(tmp_path / "not-a-backup.zip")


def test_the_home_page_can_make_a_backup_and_hand_it_over(_client, tmp_path, monkeypatch):
    import blitz.server.app as server

    root = _root(tmp_path)
    monkeypatch.setattr(server, "BACKUP_ROOT", root, raising=False)
    monkeypatch.setattr(backup.config, "ROOT", root)
    monkeypatch.setattr(db, "DB_PATH", root / "index" / "blitz.sqlite3")
    res = _client.post("/api/backup", json={"include_sources": False})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"].startswith("blitz-backup-") and data["files"] >= 5
    got = _client.get(f"/backups/{data['name']}")
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("application/zip")
    assert _client.get("/backups/../etc/passwd").status_code in (404, 400)

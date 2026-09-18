"""First run: an empty folder is unusable until someone chooses how to start.

A new person downloads the app and has no index, no study design and no
questions. Until they restore a backup or start from scratch, every page
sends them to the setup screen. What they choose there is what they get:
picking nothing means no subjects, not somebody else's Physics.
"""

import json

import pytest
from fastapi.testclient import TestClient

from blitz import config, db


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """A Blitz folder that has never been set up."""
    import blitz.export as export
    import blitz.ingest.extract as extract
    import blitz.ingest.pack as pack
    import blitz.server.app as server
    import blitz.server.indexjob as indexjob
    import blitz.students as students
    import blitz.studydesign.importer as importer
    import blitz.studydesign.loader as loader

    root = tmp_path / "Blitz"
    root.mkdir()
    monkeypatch.setattr(config, "ROOT", root)
    for mod in (config, loader, importer):
        monkeypatch.setattr(mod, "USER_DESIGN_DIR", root / "study-designs")
    for mod, name, value in (
        (config, "DB_PATH", root / "index" / "blitz.sqlite3"),
        (db, "DB_PATH", root / "index" / "blitz.sqlite3"),
        (config, "CROPS_DIR", root / "index" / "crops"),
        (extract, "CROPS_DIR", root / "index" / "crops"),
        (pack, "CROPS_DIR", root / "index" / "crops"),
        (server, "CROPS_DIR", root / "index" / "crops"),
        (config, "SOURCES_DIR", root / "sources"),
        (indexjob, "SOURCES_DIR", root / "sources"),
        (config, "EXPORTS_DIR", root / "exports"),
        (export, "EXPORTS_DIR", root / "exports"),
        (indexjob, "EXPORTS_DIR", root / "exports"),
        (config, "OUT_DIR", root / "blitzes"),
        (server, "OUT_DIR", root / "blitzes"),
        (config, "STUDENTS_DIR", root / "students"),
        (server, "STUDENTS_DIR", root / "students"),
        (students, "STUDENTS_DIR", root / "students"),
    ):
        monkeypatch.setattr(mod, name, value, raising=False)
    loader.load_study_design.cache_clear()
    from blitz.ingest.lexicon import load_lexicon

    load_lexicon.cache_clear()
    yield TestClient(server.app, follow_redirects=False), root
    loader.load_study_design.cache_clear()
    load_lexicon.cache_clear()


def test_every_page_sends_a_new_person_to_setup(fresh):
    client, root = fresh
    for path in ("/", "/blitz", "/index", "/students", "/questions"):
        res = client.get(path)
        assert res.status_code == 307, path
        assert res.headers["location"] == "/setup"
    # The API refuses rather than acting on an index that does not exist.
    res = client.get("/api/subjects")
    assert res.status_code == 409
    assert "not been set up" in res.json()["detail"]
    # The setup page and what it needs are served.
    assert client.get("/setup").status_code == 200
    assert client.get("/setup.js").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_status_offers_the_shipped_designs_as_starters(fresh):
    client, root = fresh
    st = client.get("/api/status").json()
    assert st["set_up"] is False
    assert st["root"] == str(root)
    assert st["existing"]["index"] is False
    ids = {s["id"] for s in st["shipped"]}
    assert {"physics", "business-management"} <= ids
    physics = next(s for s in st["shipped"] if s["id"] == "physics")
    assert physics["dot_points"] > 50 and physics["lexicon"] is True


def test_starting_from_scratch_gives_only_the_subjects_asked_for(fresh):
    client, root = fresh
    res = client.post("/api/setup", data={"mode": "scratch", "subjects": ["physics"]})
    assert res.status_code == 200, res.text
    assert res.json()["mode"] == "scratch"

    settings = json.loads((root / "blitz.json").read_text())
    assert settings["subjects"] == ["physics"]
    assert (root / "study-designs" / "physics.yaml").exists()
    assert (root / "study-designs" / "physics-lexicon.yaml").exists()
    assert not (root / "study-designs" / "business-management.yaml").exists()

    assert client.get("/").status_code == 200          # no longer redirected
    subjects = client.get("/api/subjects").json()["subjects"]
    assert [s["id"] for s in subjects] == ["physics"]
    assert all(kk["available"] == 0 for s in subjects for u in s["units"]
               for a in u["areas"] for kk in a["key_knowledge"])

    # Setting up twice is refused, not silently redone.
    again = client.post("/api/setup", data={"mode": "scratch", "subjects": []})
    assert again.status_code == 409


def test_starting_with_no_subjects_at_all_is_allowed(fresh):
    client, root = fresh
    assert client.post("/api/setup", data={"mode": "scratch"}).status_code == 200
    assert client.get("/api/subjects").json()["subjects"] == []
    assert client.get("/").status_code == 200


def test_samples_are_opt_in(fresh):
    client, root = fresh
    res = client.post("/api/setup", data={
        "mode": "scratch", "subjects": ["physics"], "samples": "1"})
    assert res.status_code == 200, res.text
    assert res.json()["samples"]["physics"] > 0
    subjects = client.get("/api/subjects").json()["subjects"]
    held = sum(kk["available"] for s in subjects for u in s["units"]
               for a in u["areas"] for kk in a["key_knowledge"])
    assert held > 0


def test_a_study_design_uploaded_at_setup_becomes_a_subject(fresh, tmp_path):
    from tests.test_docx import _study_design

    client, root = fresh
    sd = _study_design(tmp_path / "2024LegalStudiesSD.docx").read_bytes()
    res = client.post(
        "/api/setup",
        data={"mode": "scratch", "design_names": ["Legal Studies"]},
        files={"designs": ("2024LegalStudiesSD.docx", sd,
                           "application/octet-stream")})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["added"] == [{"id": "legal-studies", "name": "Legal Studies",
                              "path": str(root / "study-designs" / "legal-studies.yaml")}]
    assert body["subjects"] == ["legal-studies"]

    subjects = client.get("/api/subjects").json()["subjects"]
    assert [s["id"] for s in subjects] == ["legal-studies"]
    only = subjects[0]
    assert only["name"] == "Legal Studies"
    assert [u["number"] for u in only["units"]] == [3, 4]
    assert [q["id"] for q in only["question_types"]] == [
        "ls-mc", "ls-short", "ls-extended"]


def test_an_uploaded_design_can_be_named_from_its_filename(fresh, tmp_path):
    from blitz.setup import subject_name_from_filename
    from tests.test_docx import _study_design

    assert subject_name_from_filename("2023PhysicsSD.pdf") == "Physics"
    assert subject_name_from_filename(
        "vce-business-management-study-design.docx") == "Business Management"
    assert subject_name_from_filename("legal_studies.pdf") == "Legal Studies"
    assert subject_name_from_filename("2024.pdf") == "New subject"

    client, root = fresh
    sd = _study_design(tmp_path / "2024ChemistrySD.docx").read_bytes()
    res = client.post("/api/setup", data={"mode": "scratch"},
                      files={"designs": ("2024ChemistrySD.docx", sd,
                                         "application/octet-stream")})
    assert res.status_code == 200, res.text
    assert res.json()["added"][0]["name"] == "Chemistry"


def test_a_study_design_that_cannot_be_read_stops_the_setup(fresh, tmp_path):
    client, root = fresh
    res = client.post("/api/setup", data={"mode": "scratch", "subjects": ["physics"]},
                      files={"designs": ("notes.docx", b"not a docx at all",
                                         "application/octet-stream")})
    assert res.status_code == 400
    assert "notes.docx" in res.json()["detail"]
    # Nothing was written, so the person is still on the setup page.
    assert not (root / "blitz.json").exists()
    assert client.get("/").status_code == 307


def test_the_cli_adds_a_subject_from_a_study_design(fresh, tmp_path, capsys):
    from blitz.cli import main
    from tests.test_docx import _study_design

    client, root = fresh
    sd = _study_design(tmp_path / "sd.docx")
    assert main(["setup", "--design", str(sd), "--name", "Legal Studies"]) == 0
    assert (root / "study-designs" / "legal-studies.yaml").exists()
    assert "added Legal Studies" in capsys.readouterr().out

    assert main(["setup", "--force", "--design", str(tmp_path / "nope.docx")]) == 1
    assert "no such study design" in capsys.readouterr().out


def test_restoring_a_backup_brings_everything_back(fresh, tmp_path):
    from blitz import backup
    from blitz.corpus.sample import load_all_samples

    client, root = fresh
    # A backup made on "another machine".
    other = tmp_path / "Other"
    for name in ("index/crops", "study-designs", "students", "blitzes"):
        (other / name).mkdir(parents=True)
    with db.session(other / "index" / "blitz.sqlite3") as conn:
        load_all_samples(conn)
        db.get_or_create_student(conn, "Year 12 Physics")
    (other / "study-designs" / "physics.yaml").write_text(
        (config.STUDY_DESIGN_DIR / "physics.yaml").read_text(encoding="utf-8"),
        encoding="utf-8")
    (other / "blitzes" / "blitz-old.pdf").write_bytes(b"%PDF old")
    report = backup.create_backup(root=other)

    res = client.post("/api/setup", data={"mode": "restore"},
                      files={"backup": ("backup.zip", report.path.read_bytes(),
                                        "application/zip")})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "restore" and body["backup"] == "backup.zip"

    assert (root / "blitzes" / "blitz-old.pdf").exists()
    assert [s["id"] for s in client.get("/api/subjects").json()["subjects"]] == ["physics"]
    students = client.get("/api/students").json()["students"]
    assert [s["name"] for s in students] == ["Year 12 Physics"]
    # The zip that was uploaded is not left lying in the backups folder.
    assert not list((root / "backups").glob("restoring-*"))


def test_an_index_from_before_setup_existed_can_be_kept(fresh):
    from blitz.corpus.sample import load_all_samples

    client, root = fresh
    (root / "index").mkdir(parents=True)
    with db.session(root / "index" / "blitz.sqlite3") as conn:
        load_all_samples(conn)

    st = client.get("/api/status").json()
    assert st["existing"]["index"] is True
    assert st["existing"]["questions"] > 0
    assert "physics" in st["existing"]["subjects"]

    # Starting over would throw it away, so it is refused without a confirmation.
    assert client.post("/api/setup", data={
        "mode": "scratch", "subjects": ["physics"]}).status_code == 409

    res = client.post("/api/setup", data={"mode": "adopt"})
    assert res.status_code == 200, res.text
    assert res.json()["mode"] == "adopt"
    # The study designs its questions are filed under came along with it.
    assert (root / "study-designs" / "physics.yaml").exists()
    subjects = client.get("/api/subjects").json()["subjects"]
    held = sum(kk["available"] for s in subjects for u in s["units"]
               for a in u["areas"] for kk in a["key_knowledge"])
    assert held > 0


def test_starting_over_keeps_the_old_index_aside(fresh):
    from blitz.corpus.sample import load_all_samples

    client, root = fresh
    (root / "index").mkdir(parents=True)
    with db.session(root / "index" / "blitz.sqlite3") as conn:
        load_all_samples(conn)

    res = client.post("/api/setup", data={
        "mode": "scratch", "subjects": ["physics"], "erase": "1"})
    assert res.status_code == 200, res.text
    kept = list((root / "index").glob("blitz.sqlite3.before-*"))
    assert len(kept) == 1
    subjects = client.get("/api/subjects").json()["subjects"]
    held = sum(kk["available"] for s in subjects for u in s["units"]
               for a in u["areas"] for kk in a["key_knowledge"])
    assert held == 0


def test_the_setup_page_steps_aside_once_it_is_done(fresh):
    client, root = fresh
    client.post("/api/setup", data={"mode": "scratch", "subjects": []})
    res = client.get("/setup")
    assert res.status_code == 307 and res.headers["location"] == "/"


def test_the_cli_sets_up_too(fresh, capsys):
    from blitz.cli import main

    client, root = fresh
    assert main(["setup", "--subjects", "physics"]) == 0
    assert (root / "blitz.json").exists()
    assert main(["setup", "--subjects", "physics"]) == 1      # already set up
    out = capsys.readouterr().out
    assert "already exists" in out


def test_the_cli_names_subjects_it_cannot_start_with(fresh, capsys):
    from blitz.cli import main

    client, root = fresh
    assert main(["setup", "--subjects", "underwater-basket-weaving"]) == 1
    out = capsys.readouterr().out
    assert "no study design ships for" in out
    assert not (root / "blitz.json").exists()

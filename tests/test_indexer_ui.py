"""The "Index materials" page: upload files, watch the job, get a folder.

Everything runs against temporary copies of the database, sources folder,
export folder and study-design directory, so a test never touches the real
index or the shipped YAML.
"""

import shutil
import time

import pytest

docx = pytest.importorskip("docx")

from fastapi.testclient import TestClient  # noqa: E402

from blitz import config, db  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    import blitz.export as export
    import blitz.server.app as server
    import blitz.server.indexjob as indexjob
    import blitz.studydesign.importer as importer
    import blitz.studydesign.loader as loader

    # A set-up folder keeps the study designs it uses in its own folder; the
    # shipped ones are only templates setup copies from.
    designs = tmp_path / "shipped"
    shutil.copytree(config.STUDY_DESIGN_DIR, designs)
    mine = tmp_path / "study-designs"
    shutil.copytree(config.STUDY_DESIGN_DIR, mine)
    for mod in (config, loader, importer):
        monkeypatch.setattr(mod, "STUDY_DESIGN_DIR", designs)
        monkeypatch.setattr(mod, "USER_DESIGN_DIR", mine)
    # The app under test is one in use, so its folder is set up; the setup
    # page and the gate in front of it have their own tests.
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "blitz.json").write_text('{"version": 1, "mode": "test"}')
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite3")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.sqlite3")
    monkeypatch.setattr(config, "CROPS_DIR", tmp_path / "crops")
    import blitz.ingest.extract as extract
    import blitz.ingest.pack as pack

    monkeypatch.setattr(extract, "CROPS_DIR", tmp_path / "crops", raising=False)
    monkeypatch.setattr(pack, "CROPS_DIR", tmp_path / "crops", raising=False)
    monkeypatch.setattr(indexjob, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(indexjob, "EXPORTS_DIR", tmp_path / "out")
    monkeypatch.setattr(export, "EXPORTS_DIR", tmp_path / "out")
    monkeypatch.setattr(server, "OUT_DIR", tmp_path / "sheets")
    monkeypatch.setattr(server, "STUDENTS_DIR", tmp_path / "students")
    monkeypatch.setattr(server, "CROPS_DIR", tmp_path / "crops")
    monkeypatch.setattr(config, "STUDENTS_DIR", tmp_path / "students")
    import blitz.students as students

    monkeypatch.setattr(students, "STUDENTS_DIR", tmp_path / "students", raising=False)
    (tmp_path / "out").mkdir()
    (tmp_path / "sheets").mkdir()
    loader.load_study_design.cache_clear()
    yield TestClient(server.app)
    loader.load_study_design.cache_clear()


def _worksheet_bytes(tmp_path):
    from tests.test_docx import _worksheet

    return _worksheet(tmp_path / "ws.docx").read_bytes()


def _wait(client, job_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/index/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_the_page_is_served(client):
    res = client.get("/index")
    assert res.status_code == 200
    assert "Index materials" in res.text
    assert client.get("/indexer.js").status_code == 200


def test_uploading_a_word_worksheet_indexes_it_and_exports_a_folder(client, tmp_path):
    res = client.post("/api/index", data={"subject_id": "physics"},
                      files=[("files", ("motion-worksheet.docx",
                                        _worksheet_bytes(tmp_path),
                                        "application/octet-stream"))])
    assert res.status_code == 200, res.text
    job = _wait(client, res.json()["id"])
    assert job["status"] == "done", "\n".join(job["log"])
    r = job["result"]
    assert r["questions"] >= 3
    assert r["passages"] >= 1
    assert "physics-motion-worksheet" in r["sources"]
    assert "Motion of projectiles" in r["coverage"]

    folder = tmp_path / "out" / r["folder"].rsplit("/", 1)[-1]
    assert (folder / "questions.json").exists()
    assert (folder / "coverage.txt").exists()
    assert (folder / "README.txt").exists()
    zipped = client.get(f"/exports/{r['zip']}")
    assert zipped.status_code == 200
    assert zipped.headers["content-type"].startswith("application/zip")


def test_a_pack_zipped_with_its_figures_imports(client, tmp_path):
    import io
    import json
    import zipfile

    from PIL import Image

    png = io.BytesIO()
    Image.new("L", (900, 300), 255).save(png, format="PNG")
    pack = {
        "subject_id": "physics",
        "source": {"id": "tiny-pack", "kind": "other", "title": "Tiny pack",
                   "figure_zoom": 3},
        "questions": [{
            "id": "Q1", "kk_ids": ["physics-u3-aos1-kk05"],
            "question_type": "ph-calculation", "marks": 2,
            "stem": "A ball is thrown horizontally at 12 m s⁻¹ from a cliff. "
                    "Find where it lands.",
            "render_mode": "crop",
            "figures": [{"role": "question", "file": "figures/q1.png"}],
        }],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mypack/pack.json", json.dumps(pack))
        zf.writestr("mypack/renamedfigures/q1.png", png.getvalue())
    res = client.post("/api/index", data={"subject_id": "physics"},
                      files=[("files", ("mypack.zip", buf.getvalue(), "application/zip"))])
    assert res.status_code == 200, res.text
    job = _wait(client, res.json()["id"])
    assert job["status"] == "done", "\n".join(job["log"])
    assert "tiny-pack" in job["result"]["sources"]
    assert job["result"]["figures"] == 1


def test_a_new_subject_needs_its_study_design(client):
    res = client.post("/api/index", data={"subject_name": "Chemistry"})
    assert res.status_code == 400


def test_a_new_subject_is_created_from_a_word_study_design(client, tmp_path):
    from tests.test_docx import _study_design

    sd = _study_design(tmp_path / "sd.docx").read_bytes()
    res = client.post("/api/index", data={"subject_name": "Legal Studies"},
                      files=[("study_design", ("sd.docx", sd, "application/octet-stream"))])
    assert res.status_code == 200, res.text
    assert res.json()["subject_id"] == "legal-studies"
    job = _wait(client, res.json()["id"])
    # No materials: the design is imported, the job says so and finishes clean.
    assert job["status"] == "done", "\n".join(job["log"])
    assert job["result"]["questions"] == 0
    assert any("only the study design" in line for line in job["log"])
    subjects = {s["id"]: s for s in client.get("/api/subjects").json()["subjects"]}
    assert "legal-studies" in subjects
    assert subjects["legal-studies"]["name"] == "Legal Studies"
    assert subjects["legal-studies"]["verified"]
    assert [q["id"] for q in subjects["legal-studies"]["question_types"]] == [
        "ls-mc", "ls-short", "ls-extended"]

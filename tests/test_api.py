"""The HTTP surface the UI talks to."""

import pytest
from fastapi.testclient import TestClient

from blitz import config, db
from blitz.corpus.sample import load_all_samples


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "api.sqlite3")
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.sqlite3")

    import blitz.server.app as server

    monkeypatch.setattr(server, "OUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(exist_ok=True)

    with db.session(tmp_path / "api.sqlite3") as conn:
        load_all_samples(conn)
    return TestClient(server.app)


def test_subjects_expose_the_full_tree(client):
    data = client.get("/api/subjects").json()
    ids = {s["id"] for s in data["subjects"]}
    assert {"business-management", "physics"} <= ids

    physics = next(s for s in data["subjects"] if s["id"] == "physics")
    assert {u["number"] for u in physics["units"]} == {3, 4}
    assert physics["question_types"]
    kk = [k for u in physics["units"] for a in u["areas"] for k in a["key_knowledge"]]
    assert kk and all("available" in k and "verified" in k for k in kk)


def test_subjects_report_the_draft_status(client):
    data = client.get("/api/subjects").json()
    assert all(s["verified"] is False for s in data["subjects"])


def _some_kk(client, subject="physics", only_available=True):
    data = client.get("/api/subjects").json()
    s = next(x for x in data["subjects"] if x["id"] == subject)
    return [
        k["id"]
        for u in s["units"] for a in u["areas"] for k in a["key_knowledge"]
        if k["available"] or not only_available
    ]


def test_preview_returns_questions_without_writing_a_pdf(client, tmp_path):
    body = {"subject_id": "physics", "kk_ids": _some_kk(client)}
    data = client.post("/api/preview", json=body).json()
    assert data["count"] > 0
    assert data["total_marks"] > 0
    assert not list((tmp_path / "out").glob("*.pdf"))


def test_generate_writes_a_downloadable_pdf(client):
    body = {"subject_id": "physics", "kk_ids": _some_kk(client),
            "title": "API test"}
    data = client.post("/api/generate", json=body).json()
    assert data["questions"] > 0
    assert data["question_pages"] <= 2

    res = client.get(data["url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_generate_with_no_selection_is_rejected(client):
    res = client.post("/api/generate", json={"subject_id": "physics", "kk_ids": []})
    assert res.status_code == 422


def test_unknown_subject_is_a_404(client):
    res = client.post("/api/preview",
                      json={"subject_id": "latin", "kk_ids": ["x"]})
    assert res.status_code == 404


@pytest.mark.parametrize("name", [
    "../../../etc/passwd",
    "..%2f..%2fetc%2fpasswd",
    "nope.pdf",
])
def test_sheet_download_cannot_escape_the_output_directory(client, name):
    assert client.get(f"/sheets/{name}").status_code in (404, 422)


def test_notes_reach_the_picker_through_the_api(client):
    kk = _some_kk(client)
    plain = client.post("/api/preview",
                        json={"subject_id": "physics", "kk_ids": kk, "seed": 11}).json()
    nudged = client.post("/api/preview", json={
        "subject_id": "physics", "kk_ids": kk, "seed": 11,
        "notes": "relativity and the photoelectric effect"}).json()

    def bodies(d):
        return " ".join(q["preview"] for q in d["questions"]).lower()

    assert "photoelectric" not in bodies(plain)
    assert "photoelectric" in bodies(nudged)


def test_ui_is_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "VCE" in res.text

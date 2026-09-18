"""Browse mode: picking questions by hand instead of taking the selection.

Clicking a dot point lists its questions; picking one pins it to the sheet.
A pinned question is not a suggestion — it goes on even if its dot point is
not ticked and even if the student has seen it before — but it is still
refused if someone has flagged it as broken.
"""

import pytest

from blitz import db
from blitz.corpus.sample import load_all_samples

from tests.test_indexer_ui import client as _client  # noqa: F401  (fixture)


@pytest.fixture
def client(_client, tmp_path):
    with db.session(tmp_path / "t.sqlite3") as conn:
        load_all_samples(conn)
    return _client


def _dot_points(client, subject="physics"):
    data = client.get("/api/subjects").json()
    s = next(x for x in data["subjects"] if x["id"] == subject)
    return [k for u in s["units"] for a in u["areas"] for k in a["key_knowledge"]]


def _one_with_questions(client):
    return next(k for k in _dot_points(client) if k["available"])


def test_browsing_a_dot_point_lists_only_its_questions(client):
    kk = _one_with_questions(client)
    res = client.get("/api/questions", params={"subject": "physics", "kk": kk["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == kk["available"]
    for q in body["questions"]:
        assert q["serial"] and q["kk"], q
        assert q["already_given"] is False
    # A dot point with nothing behind it browses to nothing, not an error.
    empty = next(k for k in _dot_points(client) if not k["available"])
    assert client.get("/api/questions", params={
        "subject": "physics", "kk": empty["id"]}).json()["total"] == 0


def test_a_hand_picked_question_goes_on_even_from_an_unticked_dot_point(client):
    points = [k for k in _dot_points(client) if k["available"]]
    wanted, elsewhere = points[0], points[1]
    pick = client.get("/api/questions", params={
        "subject": "physics", "kk": elsewhere["id"]}).json()["questions"][0]

    res = client.post("/api/preview", json={
        "subject_id": "physics", "kk_ids": [wanted["id"]], "seed": 1,
        "pinned_question_ids": [pick["id"]]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pinned"] == [pick["id"]]
    on_sheet = {q["id"]: q for q in body["questions"]}
    assert pick["id"] in on_sheet
    assert on_sheet[pick["id"]]["pinned"] is True
    # The rest of the sheet is still filled automatically around it.
    assert len(body["questions"]) > 1
    assert any(not q["pinned"] for q in body["questions"])


def test_a_pick_beats_the_students_history(client):
    kk = _one_with_questions(client)
    first = client.post("/api/generate", json={
        "subject_id": "physics", "kk_ids": [k["id"] for k in _dot_points(client)][:4],
        "seed": 1, "student_name": "Sam"}).json()
    seen = first["serials"]
    assert seen

    given = client.get("/api/questions", params={
        "subject": "physics", "kk": kk["id"], "student": first["student"]["id"]}).json()
    already = [q for q in given["questions"] if q["already_given"]]
    assert already, "the student should have been given something from this dot point"

    # Without picking it, it is skipped. Picking it puts it back.
    plain = client.post("/api/preview", json={
        "subject_id": "physics", "kk_ids": [kk["id"]], "seed": 2,
        "student_id": first["student"]["id"]}).json()
    assert already[0]["id"] not in {q["id"] for q in plain["questions"]}

    picked = client.post("/api/preview", json={
        "subject_id": "physics", "kk_ids": [kk["id"]], "seed": 2,
        "student_id": first["student"]["id"],
        "pinned_question_ids": [already[0]["id"]]}).json()
    assert already[0]["id"] in {q["id"] for q in picked["questions"]}
    assert already[0]["serial"] not in picked["skipped"]


def test_a_flagged_question_cannot_be_picked(client):
    kk = _one_with_questions(client)
    victim = client.get("/api/questions", params={
        "subject": "physics", "kk": kk["id"]}).json()["questions"][0]
    client.post(f"/api/questions/{victim['id']}/flag", json={"flag": "corrupt"})

    body = client.post("/api/preview", json={
        "subject_id": "physics", "kk_ids": [kk["id"]], "seed": 1,
        "pinned_question_ids": [victim["id"]]}).json()
    assert body["pinned"] == []
    assert victim["id"] not in {q["id"] for q in body["questions"]}


def test_picks_alone_make_a_sheet(client):
    kk = _one_with_questions(client)
    picks = [q["id"] for q in client.get("/api/questions", params={
        "subject": "physics", "kk": kk["id"]}).json()["questions"][:2]]
    res = client.post("/api/generate", json={
        "subject_id": "physics", "kk_ids": [], "seed": 1,
        "pinned_question_ids": picks})
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body["serials"]) and len(body["serials"]) == len(picks)
    assert body["questions"] == len(picks)


def test_the_page_offers_browsing(client):
    page = client.get("/blitz").text
    assert 'id="browse"' in page and 'id="picked"' in page
    js = client.get("/app.js").text
    assert "openBrowse" in js and "pinned_question_ids" in js

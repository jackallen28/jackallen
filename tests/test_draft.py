"""Draft pack extraction — the deterministic, no-model path.

Its value is not that it is as good as a person reading the book; it is that it
is right about most questions and honest about which ones it isn't. So the tests
care about two things: the output is a valid pack, and the review flags are
narrow enough to be worth acting on.
"""

import json

import pytest

from blitz.ingest.draft import build_draft, review_queue, write_draft
from blitz.ingest.pack import import_pack, validate
from blitz.studydesign import load_study_design

# fake_book and stimulus_book come from conftest.py.


@pytest.fixture
def design():
    return load_study_design("physics")


@pytest.fixture
def draft(fake_book, design):
    pack, report = build_draft(
        fake_book, subject_id="physics", source_id="fake",
        title="Fake Checkpoints", design=design, progress=lambda *_: None)
    return pack, report


def test_the_draft_is_a_valid_pack(draft, design, tmp_path):
    pack, _ = draft
    report = validate(pack, design, tmp_path)
    assert report.ok, report.errors


def test_the_draft_imports(draft, design, conn, tmp_path):
    pack, _ = draft
    path = write_draft(pack, tmp_path / "draft.json")
    result = import_pack(conn, path, design=design, progress=lambda *_: None)
    assert result.ok and result.imported == len(pack["questions"])


def test_it_carries_the_study_design_fingerprint(draft, design):
    from blitz.corpus.sample import fingerprint

    pack, _ = draft
    assert pack["study_design_fingerprint"] == fingerprint(design)


def test_ids_are_unique_and_stable(fake_book, design):
    a, _ = build_draft(fake_book, subject_id="physics", source_id="fake",
                       design=design, progress=lambda *_: None)
    b, _ = build_draft(fake_book, subject_id="physics", source_id="fake",
                       design=design, progress=lambda *_: None)
    ids = [q["id"] for q in a["questions"]]
    assert len(ids) == len(set(ids))
    assert ids == [q["id"] for q in b["questions"]]


def test_provenance_and_page_numbers_survive(draft):
    pack, _ = draft
    by_prov = [q for q in pack["questions"] if q.get("provenance")]
    assert by_prov, "the VCAA provenance tag was dropped"
    assert all(q.get("printed_page") for q in pack["questions"])


def test_options_and_marks_survive(draft):
    pack, _ = draft
    assert any(q.get("options") for q in pack["questions"])
    assert any(q.get("marks") for q in pack["questions"])


def test_unreflowable_maths_becomes_a_crop(draft):
    """The draft used to downgrade these back to their mangled text."""
    pack, _ = draft
    cropped = [q for q in pack["questions"] if q.get("render_mode") == "crop"]
    assert cropped, "no question was marked for cropping"
    for q in cropped:
        assert any(f.get("role", "question") == "question"
                   for f in q.get("figures", [])), \
            "a crop-mode question must carry the figure that replaces its text"


def test_a_missing_solution_is_recorded_not_invented(draft):
    pack, _ = draft
    missing = [q for q in pack["questions"] if "answer" not in q]
    assert missing, "expected at least one question with no source answer"
    for q in missing:
        assert "not supplied" in (q.get("notes") or "")


class TestReviewFlags:
    """A flag earns its place only if a person would change something."""

    def test_most_questions_are_not_flagged(self, draft):
        pack, report = draft
        assert report.flagged < report.questions * 0.5, (
            f"{report.flagged}/{report.questions} flagged — reviewing that many "
            "is no better than reviewing all of them")

    def test_facts_about_the_source_are_not_flagged_as_problems(self, draft):
        """"The book prints no solution" is recorded, not queued for review."""
        pack, _ = draft
        for q in pack["questions"]:
            for flag in q.get("review", []):
                assert "no worked solution" not in flag
                assert "will not reflow" not in flag

    def test_the_review_queue_is_small_and_self_contained(self, draft):
        pack, _ = draft
        queue = review_queue(pack)
        assert len(queue) == sum(1 for q in pack["questions"] if q.get("review"))
        for entry in queue:
            assert entry["id"] and entry["review"]
            assert "stem" in entry, "a reviewer needs the text to judge it"

    def test_an_untagged_question_is_flagged(self, design, tmp_path):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas

        path = tmp_path / "offtopic.pdf"
        c = rl_canvas.Canvas(str(path), pagesize=A4)
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, A4[1] - 30 * mm, "Question 1/ 4")
        c.drawString(20 * mm, A4[1] - 38 * mm,
                     "Describe the plot of a novel you enjoyed and explain why.")
        c.save()

        pack, _ = build_draft(path, subject_id="physics", source_id="odd",
                              design=design, progress=lambda *_: None)
        assert pack["questions"], "nothing was extracted"
        assert any("untagged" in f
                   for q in pack["questions"] for f in q.get("review", []))


def test_a_page_range_limits_the_work(fake_book, design):
    whole, _ = build_draft(fake_book, subject_id="physics", source_id="f",
                           design=design, progress=lambda *_: None)
    part, report = build_draft(fake_book, subject_id="physics", source_id="f",
                               pages=(0, 1), design=design,
                               progress=lambda *_: None)
    assert report.pages == 1
    assert len(part["questions"]) < len(whole["questions"])


def test_write_draft_round_trips(draft, tmp_path):
    pack, _ = draft
    path = write_draft(pack, tmp_path / "out" / "draft.json")
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == pack

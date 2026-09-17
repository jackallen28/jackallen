"""Ingestion is tested against a synthetic book built with ReportLab.

Real Checkpoints and textbook PDFs can't live in the repo, so we generate a PDF
with the same shape — numbered questions, multiple choice options, marks in
brackets, inline solutions and a vector diagram — and check the pipeline pulls
the right things out of it.
"""

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from blitz import db
from blitz.ingest import extract, segment
from blitz.ingest.pipeline import _split_solution, ingest_pdf
from blitz.ingest.tag import KeywordTagger
from blitz.studydesign import load_study_design

PAGE_W, PAGE_H = A4


@pytest.fixture
def fake_book(tmp_path):
    """A two-page PDF shaped like a Checkpoints chapter."""
    path = tmp_path / "fake-checkpoints.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)

    def line(y, text, font="Helvetica", size=10):
        c.setFont(font, size)
        c.drawString(20 * mm, y, text)

    # Page 1 — a multiple choice question and a short answer with a solution.
    y = PAGE_H - 30 * mm
    line(y, "Chapter 4 Review Questions", "Helvetica-Bold", 12)
    y -= 12 * mm
    line(y, "1. A transformer has 1200 turns on the primary and 80 on the")
    y -= 5 * mm
    line(y, "secondary. The secondary voltage when 240 V AC is applied is: (1 mark)")
    for opt in ("A. 16 V", "B. 160 V", "C. 3600 V", "D. 24 V"):
        y -= 5 * mm
        line(y, opt)
    y -= 7 * mm
    line(y, "2. Calculate the impulse delivered to a 0.16 kg ball whose velocity")
    y -= 5 * mm
    line(y, "changes from 30 m/s to -40 m/s. (3 marks)")
    y -= 5 * mm
    line(y, "Solution: Impulse = change in momentum = 0.16 x (-40 - 30) = -11.2 N s")
    c.showPage()

    # Page 2 — a question with a vector diagram beneath it.
    y = PAGE_H - 30 * mm
    line(y, "3. The diagram below shows the magnetic field around a bar magnet.")
    y -= 5 * mm
    line(y, "Explain the direction of the force on a current-carrying wire. (4 marks)")
    y -= 10 * mm
    c.setLineWidth(1)
    box_top = y
    for i in range(9):          # a cluster of strokes reads as a figure
        c.rect(20 * mm + i * 6 * mm, y - 40 * mm, 5 * mm, 38 * mm)
    c.circle(60 * mm, y - 20 * mm, 12 * mm)
    y = box_top - 50 * mm
    line(y, "4. State Lenz's law. (2 marks)")
    c.showPage()
    c.save()
    return path


def test_extract_reads_pages_and_text(fake_book):
    doc = extract.open_pdf(fake_book)
    page = extract.read_page(doc, 0)
    doc.close()
    assert "transformer" in page.text
    assert page.blocks
    assert page.width > 0 and page.height > 0


def test_printed_page_numbers_respect_the_offset(fake_book):
    doc = extract.open_pdf(fake_book)
    assert extract.read_page(doc, 0, page_offset=0).printed == "1"
    assert extract.read_page(doc, 0, page_offset=141).printed == "142"
    doc.close()


def test_a_vector_diagram_is_detected_and_croppable(fake_book, tmp_path):
    doc = extract.open_pdf(fake_book)
    page = extract.read_page(doc, 1)
    regions = page.figure_regions
    assert regions, "the drawn diagram was not detected as a figure region"

    out = extract.crop(doc, 1, regions[0], tag="test", out_dir=tmp_path / "crops")
    doc.close()
    assert out is not None
    img = pymupdf.open(out)
    assert img[0].rect.width > 50      # a real crop, not a sliver
    img.close()


def test_crop_of_a_degenerate_region_returns_none(fake_book, tmp_path):
    doc = extract.open_pdf(fake_book)
    assert extract.crop(doc, 0, (10, 10, 11, 11), tag="t", out_dir=tmp_path) is None
    doc.close()


def test_segmentation_finds_the_questions(fake_book):
    doc = extract.open_pdf(fake_book)
    found = []
    for i in range(doc.page_count):
        found += segment.segment_page(extract.read_page(doc, i))
    doc.close()

    assert len(found) >= 3
    numbers = {q.number for q in found}
    assert {"1", "2"} <= numbers


def test_multiple_choice_options_are_split_off(fake_book):
    doc = extract.open_pdf(fake_book)
    questions = segment.segment_page(extract.read_page(doc, 0))
    doc.close()
    mc = [q for q in questions if q.options]
    assert mc, "multiple choice options were not detected"
    assert len(mc[0].options) == 4
    assert "16 V" in mc[0].options[0]
    assert "A." not in mc[0].options[0]      # the label is stripped


def test_marks_are_parsed_and_removed_from_the_body(fake_book):
    doc = extract.open_pdf(fake_book)
    questions = segment.segment_page(extract.read_page(doc, 0))
    doc.close()
    marked = [q for q in questions if q.marks]
    assert marked
    assert all("mark" not in q.text.lower() for q in marked)


def test_running_heads_are_not_treated_as_questions(fake_book):
    doc = extract.open_pdf(fake_book)
    questions = segment.segment_page(extract.read_page(doc, 0))
    doc.close()
    assert not any("Chapter 4 Review" in q.text for q in questions)


@pytest.mark.parametrize("raw,body,answer", [
    ("Calculate the force. Solution: F = ma = 12 N",
     "Calculate the force", "F = ma = 12 N"),
    ("State Lenz's law.", "State Lenz's law.", None),
])
def test_inline_solutions_are_split_out(raw, body, answer):
    got_body, got_answer = _split_solution(raw)
    assert got_body.startswith(body[:15])
    if answer is None:
        assert got_answer is None
    else:
        assert answer in got_answer


def test_full_ingest_writes_tagged_rows(fake_book, conn):
    report = ingest_pdf(
        conn, fake_book,
        source_id="fake", subject_id="physics", kind="checkpoints",
        title="Fake Checkpoints", page_offset=141,
        use_model=False, progress=lambda *_: None,
    )
    assert report.kept > 0

    rows = conn.execute("SELECT * FROM question WHERE source_id = 'fake'").fetchall()
    assert len(rows) == report.kept
    for row in rows:
        assert row["generated"] == 0
        assert row["citation"].startswith("Fake Checkpoints, p. 1")
        links = conn.execute(
            "SELECT kk_id FROM question_kk WHERE question_id = ?", (row["id"],)
        ).fetchall()
        assert links, "every indexed question must hang off a dot point"


def test_ingest_is_idempotent(fake_book, conn):
    kw = dict(source_id="fake", subject_id="physics", use_model=False,
              progress=lambda *_: None)
    first = ingest_pdf(conn, fake_book, **kw)
    second = ingest_pdf(conn, fake_book, **kw)
    assert first.kept == second.kept

    total = conn.execute(
        "SELECT COUNT(*) n FROM question WHERE source_id = 'fake'"
    ).fetchone()["n"]
    assert total == first.kept


def test_full_text_search_reaches_ingested_rows(fake_book, conn):
    ingest_pdf(conn, fake_book, source_id="fake", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    hits = conn.execute(
        "SELECT COUNT(*) n FROM question_fts WHERE question_fts MATCH 'transformer'"
    ).fetchone()["n"]
    assert hits >= 1


def test_coverage_counts_what_was_ingested(fake_book, conn):
    ingest_pdf(conn, fake_book, source_id="fake", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    counts = db.coverage(conn, "physics")
    assert counts and sum(counts.values()) > 0


class TestKeywordTagger:
    def test_multiple_choice_is_recognised_by_its_options(self):
        design = load_study_design("physics")
        tagger = KeywordTagger(design)
        result = tagger.tag(
            "The magnetic flux through the loop is greatest when:",
            options=["A", "B", "C", "D"], marks=1,
        )
        assert result.question_type == "ph-mc"

    def test_a_question_is_tagged_to_a_plausible_dot_point(self):
        design = load_study_design("physics")
        tagger = KeywordTagger(design)
        result = tagger.tag(
            "Calculate the impulse and momentum change of the ball during the "
            "collision, treating the system as isolated.", marks=3,
        )
        assert result.kk_ids
        assert all(kk in {k.id for k in design.all_key_knowledge()}
                   for kk in result.kk_ids)

    def test_prose_with_no_syllabus_vocabulary_is_rejected(self):
        tagger = KeywordTagger(load_study_design("physics"))
        assert tagger.tag("Turn to the next chapter when you are ready.").rejected

    def test_difficulty_tracks_marks(self):
        tagger = KeywordTagger(load_study_design("physics"))
        easy = tagger.tag("State the unit of magnetic flux.", marks=1)
        hard = tagger.tag(
            "Evaluate the transformer design, hence determine the losses.", marks=8)
        assert (easy.difficulty or 0) < (hard.difficulty or 0)

"""Ingestion, tested against a synthetic book shaped like Checkpoints.

The real book can't live in the repo, so the fixture reproduces its structure:
"Question N/ P" headers, VCAA provenance tags, multi-part questions with their
own marks lines, A/B/C/D options, inline Solution blocks, a diagram fenced
between full-width rules, and a stacked fraction that cannot be reflowed.
"""

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from blitz import db
from blitz.ingest import extract, segment
from blitz.ingest.pipeline import ingest_pdf
from blitz.ingest.tag import KeywordTagger
from blitz.studydesign import load_study_design

PAGE_W, PAGE_H = A4
LEFT = 20 * mm


@pytest.fixture
def fake_book(tmp_path):
    path = tmp_path / "fake-checkpoints.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)

    def rule(y):
        c.setLineWidth(0.5)
        c.line(LEFT, y, PAGE_W - LEFT, y)

    def text(y, s, size=10, font="Helvetica"):
        c.setFont(font, size)
        c.drawString(LEFT, y, s)

    # --- page 1: a diagram above its question, then a multiple choice ---------
    y = PAGE_H - 25 * mm
    c.setLineWidth(1)
    for i in range(8):                       # a vector diagram
        c.rect(LEFT + i * 7 * mm, y - 32 * mm, 6 * mm, 30 * mm)
    y -= 40 * mm
    rule(y)

    y -= 10 * mm
    text(y, "Question 12/ 11")
    y -= 7 * mm
    text(y, "The graph above shows the motion. Which one best describes it?")
    for opt in ("A Constant speed followed by no motion",
                "B Increasing speed followed by constant speed",
                "C Increasing acceleration then constant acceleration",
                "D Increasing distance followed by constant speed"):
        y -= 6 * mm
        text(y, opt)
    y -= 7 * mm
    text(y, "Solution")
    y -= 6 * mm
    text(y, "B The gradient increases then becomes constant.")
    y -= 8 * mm
    rule(y)

    # --- a multi-part question with marks, running onto page 2 ---------------
    y -= 10 * mm
    text(y, "Question 14/ 11")
    y -= 6 * mm
    text(y, "[Adapted VCAA 2018 NHT SA Q8]")
    y -= 7 * mm
    text(y, "A 1.0 kg mass hangs 4.0 m above the ground on a massless string.")
    y -= 7 * mm
    text(y, "a. Calculate the magnetic flux through the coil.")
    y -= 6 * mm
    text(y, "(2 marks)")
    c.showPage()

    y = PAGE_H - 25 * mm
    text(y, "b. Determine the transformer turns ratio required.")
    y -= 6 * mm
    text(y, "(3 marks)")
    y -= 8 * mm
    text(y, "Solution")
    y -= 6 * mm
    text(y, "a 0.30 Wb, from the perpendicular area.")
    y -= 8 * mm
    rule(y)

    # --- a question whose maths is a stacked fraction -------------------------
    y -= 10 * mm
    text(y, "Question 5/ 14")
    y -= 7 * mm
    text(y, "Which expression gives the de Broglie wavelength of the photon?")
    y -= 9 * mm
    c.setFont("Helvetica", 10)
    c.drawString(LEFT + 14, y + 6, "h")        # numerator
    c.setLineWidth(0.5)
    c.line(LEFT + 12, y + 3, LEFT + 12 + 8, y + 3)   # the fraction bar
    c.drawString(LEFT + 14, y - 5, "p")        # denominator
    c.drawString(LEFT, y, "A")
    y -= 14 * mm
    text(y, "B E = hf")
    y -= 6 * mm
    text(y, "C E = pc")
    y -= 6 * mm
    text(y, "D E = mc")
    c.save()
    return path


def _questions(path):
    doc = pymupdf.open(path)
    try:
        return segment.segment_document(doc)
    finally:
        doc.close()


def test_question_headers_are_the_boundaries(fake_book):
    qs = _questions(fake_book)
    assert [q.number for q in qs] == ["12", "14", "5"]


def test_printed_page_comes_from_the_header(fake_book):
    """"Question 12/ 11" means question 12 on printed page 11."""
    qs = _questions(fake_book)
    assert qs[0].printed_page == "11"
    assert qs[2].printed_page == "14"


def test_options_belong_to_their_own_question(fake_book):
    """The bug this guards: options bleeding onto the next question's stem."""
    qs = _questions(fake_book)
    assert len(qs[0].options) == 4
    assert "Constant speed followed by no motion" in qs[0].options[0]
    assert "Constant speed" not in qs[1].text


def test_a_question_without_options_gets_none(fake_book):
    qs = _questions(fake_book)
    assert qs[1].options == []


def test_marks_are_summed_across_parts(fake_book):
    qs = _questions(fake_book)
    assert qs[1].marks == 5           # 2 + 3
    assert "mark" not in qs[1].full_text.lower()


def test_parts_are_captured_separately(fake_book):
    qs = _questions(fake_book)
    assert len(qs[1].parts) == 2
    assert qs[1].parts[0].startswith("a.")
    assert qs[1].parts[1].startswith("b.")


def test_a_question_spanning_pages_is_assembled_whole(fake_book):
    """Part b is on page 2; it must stay attached to its stem on page 1."""
    qs = _questions(fake_book)
    q = qs[1]
    assert q.page_index == 0
    assert q.end_page_index == 1
    assert "transformer turns ratio" in q.full_text


def test_provenance_is_extracted_and_removed_from_the_body(fake_book):
    qs = _questions(fake_book)
    assert "VCAA 2018" in (qs[1].provenance or "")
    assert "[" not in qs[1].text


def test_solutions_are_split_from_their_question(fake_book):
    qs = _questions(fake_book)
    assert qs[0].answer and "gradient increases" in qs[0].answer
    assert "gradient increases" not in qs[0].text


def test_a_question_with_no_solution_reports_none(fake_book):
    qs = _questions(fake_book)
    assert qs[2].answer is None


def test_stacked_fractions_are_flagged_for_cropping(fake_book):
    """Text can't represent h/p, so the sheet must show the page instead."""
    qs = _questions(fake_book)
    fraction_q = qs[2]
    assert fraction_q.needs_crop
    assert "fraction" in fraction_q.crop_reason.lower()


def test_ordinary_questions_are_not_flagged_for_cropping(fake_book):
    qs = _questions(fake_book)
    assert not qs[0].needs_crop
    assert not qs[1].needs_crop


def test_full_ingest_writes_rows_with_citations(fake_book, conn):
    report = ingest_pdf(
        conn, fake_book, source_id="fake", subject_id="physics",
        kind="checkpoints", title="Fake Checkpoints",
        use_model=False, progress=lambda *_: None,
    )
    assert report.candidates == 3
    rows = conn.execute("SELECT * FROM question WHERE source_id='fake'").fetchall()
    assert rows
    for row in rows:
        assert row["citation"].startswith("Fake Checkpoints, p. ")
        assert row["generated"] == 0
        links = conn.execute(
            "SELECT kk_id FROM question_kk WHERE question_id=?", (row["id"],)
        ).fetchall()
        assert links, "an indexed question must hang off a dot point"


def test_provenance_reaches_the_citation(fake_book, conn):
    ingest_pdf(conn, fake_book, source_id="fake", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    cites = [r["citation"] for r in
             conn.execute("SELECT citation FROM question WHERE source_id='fake'")]
    assert any("VCAA 2018" in c for c in cites)


def test_cropped_questions_carry_an_image(fake_book, conn):
    ingest_pdf(conn, fake_book, source_id="fake", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    rows = conn.execute(
        "SELECT * FROM question WHERE source_id='fake' AND render_mode='crop'"
    ).fetchall()
    for row in rows:
        assert row["figure_path"], "a crop-rendered question needs its image"
        assert row["body"], "text is still kept, for search and tagging"


def test_ingest_is_idempotent(fake_book, conn):
    kw = dict(source_id="fake", subject_id="physics", use_model=False,
              progress=lambda *_: None)
    first = ingest_pdf(conn, fake_book, **kw)
    second = ingest_pdf(conn, fake_book, **kw)
    assert first.kept == second.kept
    total = conn.execute(
        "SELECT COUNT(*) n FROM question WHERE source_id='fake'").fetchone()["n"]
    assert total == first.kept


def test_full_text_search_reaches_ingested_rows(fake_book, conn):
    ingest_pdf(conn, fake_book, source_id="fake", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    n = conn.execute(
        "SELECT COUNT(*) n FROM question_fts WHERE question_fts MATCH 'flux'"
    ).fetchone()["n"]
    assert n >= 1


def test_crop_of_a_degenerate_region_returns_none(fake_book, tmp_path):
    doc = extract.open_pdf(fake_book)
    assert extract.crop(doc, 0, (10, 10, 11, 11), tag="t", out_dir=tmp_path) is None
    doc.close()


def test_a_real_region_crops_to_an_image(fake_book, tmp_path):
    doc = extract.open_pdf(fake_book)
    out = extract.crop(doc, 0, (40, 40, 300, 200), tag="t", out_dir=tmp_path)
    doc.close()
    assert out
    img = pymupdf.open(out)
    assert img[0].rect.width > 50
    img.close()


class TestKeywordTagger:
    """The offline fallback. It must be conservative, not confidently wrong."""

    @pytest.fixture
    def tagger(self):
        return KeywordTagger(load_study_design("physics"))

    def test_multiple_choice_is_recognised_by_its_options(self, tagger):
        r = tagger.tag("The flux through the loop is greatest when:",
                       options=["A", "B", "C", "D"], marks=1)
        assert r.question_type == "ph-mc"

    def test_a_distinctive_question_is_tagged(self, tagger):
        r = tagger.tag("Calculate the magnetic flux through the coil when the "
                       "field is perpendicular to the area.", marks=3)
        assert not r.rejected
        assert r.kk_ids

    def test_prose_with_no_syllabus_vocabulary_is_rejected(self, tagger):
        assert tagger.tag("Turn to the next chapter when you are ready.").rejected

    def test_a_question_with_nothing_distinctive_is_rejected(self, tagger):
        """Better untagged and reported than filed under the wrong dot point."""
        assert tagger.tag("Which one of the following is closest?").rejected

    def test_tags_are_real_dot_point_ids(self, tagger):
        design = load_study_design("physics")
        valid = {kk.id for kk in design.all_key_knowledge()}
        r = tagger.tag("An ideal transformer has 1200 turns on the primary.",
                       marks=3)
        assert set(r.kk_ids) <= valid

    def test_difficulty_tracks_marks(self, tagger):
        easy = tagger.tag("State the unit of magnetic flux.", marks=1)
        hard = tagger.tag("Evaluate the transformer design, hence determine "
                          "the power losses.", marks=8)
        assert (easy.difficulty or 0) < (hard.difficulty or 0)


@pytest.fixture
def stimulus_book(tmp_path):
    """Reproduces how Checkpoints prints a shared stimulus and its figure.

    The lead-in sentence and the graph sit ABOVE the rule that fences the
    question, so they arrive attached to the previous question, and the figure
    is in the preceding fence rather than the question's own. Looking only
    inside the question's fence missed every graph question in the real sample.
    """
    path = tmp_path / "stimulus.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)

    def rule(y):
        c.setLineWidth(0.5)
        c.line(LEFT, y, PAGE_W - LEFT, y)

    def text(y, s, size=10):
        c.setFont("Helvetica", size)
        c.drawString(LEFT, y, s)

    y = PAGE_H - 25 * mm
    text(y, "Question 9/ 11")
    y -= 7 * mm
    text(y, "Calculate the impulse delivered during the collision.")
    y -= 8 * mm
    rule(y)

    # The stimulus block: its own "Question" header, a lead-in, and the figure.
    y -= 10 * mm
    text(y, "Question 10/ 11")
    y -= 7 * mm
    text(y, "The speed-time graph below describes the motion of an object.")
    y -= 6 * mm
    c.setLineWidth(1)
    for i in range(7):
        c.rect(LEFT + i * 8 * mm, y - 34 * mm, 7 * mm, 32 * mm)
    y -= 42 * mm
    rule(y)

    # The question that actually uses it, in the next fence.
    y -= 10 * mm
    text(y, "Question 11/ 11")
    y -= 7 * mm
    text(y, "Which one best describes the motion of the object at t = 5 s?")
    for opt in ("A Constant speed", "B Increasing speed",
                "C Constant acceleration", "D Increasing acceleration"):
        y -= 6 * mm
        text(y, opt)
    y -= 8 * mm
    rule(y)
    c.save()
    return path


def test_a_stimulus_only_block_is_not_indexed_as_a_question(stimulus_book):
    """"The graph below describes..." is unanswerable on its own."""
    qs = _questions(stimulus_book)
    assert [q.number for q in qs] == ["9", "11"]


def test_the_stimulus_is_carried_onto_the_question_it_introduces(stimulus_book):
    qs = _questions(stimulus_book)
    q = next(q for q in qs if q.number == "11")
    assert "speed-time graph below" in q.stimulus
    assert "speed-time graph below" in q.full_text
    assert "Which one best describes" in q.text


def test_the_stimulus_does_not_leak_onto_the_previous_question(stimulus_book):
    qs = _questions(stimulus_book)
    q = next(q for q in qs if q.number == "9")
    assert "graph" not in q.full_text.lower()


def test_a_figure_in_the_preceding_fence_is_found(stimulus_book, conn):
    ingest_pdf(conn, stimulus_book, source_id="stim", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    rows = conn.execute(
        "SELECT * FROM question WHERE source_id='stim'").fetchall()
    graph_q = next(r for r in rows if "describes the motion" in r["body"])
    assert graph_q["figure_path"], (
        "the graph sits in the fence above its question and was not found")


def test_a_question_that_mentions_no_figure_gets_none(stimulus_book, conn):
    ingest_pdf(conn, stimulus_book, source_id="stim", subject_id="physics",
               use_model=False, progress=lambda *_: None)
    row = conn.execute(
        "SELECT * FROM question WHERE source_id='stim' AND body LIKE '%impulse%'"
    ).fetchone()
    assert row is not None
    assert not row["figure_path"]

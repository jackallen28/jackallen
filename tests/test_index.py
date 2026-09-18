"""`blitz index`: a study design and a book in, an index out."""

import pymupdf
import pytest

from blitz import db
from blitz.ingest.detect import detect_kind
from blitz.ingest.index import index_book
from blitz.ingest.passages import extract_passages, tag_passages
from blitz.ingest.tag import KeywordTagger
from blitz.ingest.textbook import segment_textbook
from blitz.studydesign import load_study_design


@pytest.fixture
def design():
    return load_study_design("physics")


class TestDetection:
    def test_checkpoints_is_recognised(self, fake_book):
        doc = pymupdf.open(fake_book)
        d = detect_kind(doc)
        doc.close()
        assert d.kind == "checkpoints"

    def test_a_textbook_is_recognised(self, fake_textbook):
        doc = pymupdf.open(fake_textbook)
        d = detect_kind(doc)
        doc.close()
        assert d.kind == "textbook"
        assert d.confidence > 0.5

    def test_a_study_design_is_neither(self):
        """A PDF with no questions must not be mistaken for a question book."""
        from pathlib import Path

        sd = Path(__file__).resolve().parent.parent / "sources" / "vcaa" / "physics-sd.pdf"
        if not sd.exists():
            pytest.skip("study design PDF not present")
        doc = pymupdf.open(sd)
        assert detect_kind(doc).kind == "unknown"
        doc.close()

    def test_an_empty_document_is_unknown(self, tmp_path):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        path = tmp_path / "blank.pdf"
        c = rl_canvas.Canvas(str(path), pagesize=A4)
        c.showPage()
        c.save()
        doc = pymupdf.open(path)
        assert detect_kind(doc).kind == "unknown"
        doc.close()


class TestTextbookQuestions:
    @pytest.fixture
    def questions(self, fake_textbook):
        doc = pymupdf.open(fake_textbook)
        try:
            return segment_textbook(doc)
        finally:
            doc.close()

    def test_all_blocks_are_found(self, questions):
        labels = {q.provenance for q in questions}
        assert "Worked example 6.1" in labels
        assert "Questions" in labels
        assert "Chapter review" in labels

    def test_a_worked_example_keeps_its_solution(self, questions):
        we = next(q for q in questions if q.provenance.startswith("Worked example"))
        assert we.answer and "Ek max" in we.answer
        assert "Solution" not in we.text

    def test_numbered_questions_are_split(self, questions):
        section = [q for q in questions if q.provenance == "Questions"]
        assert [q.number for q in section] == ["1", "2", "3"]

    def test_options_and_marks_survive(self, questions):
        mc = next(q for q in questions if q.options)
        assert len(mc.options) == 4
        assert "B." not in mc.options[1] and "discrete quanta" in mc.options[1]
        marked = [q for q in questions if q.marks]
        assert marked and all("mark" not in q.text.lower() for q in marked)

    def test_prose_is_not_mistaken_for_a_question(self, questions):
        texts = " ".join(q.full_text for q in questions)
        assert "Einstein explained this" not in texts


class TestPublisherVocabularies:
    """The same extractor against two books that agree on almost no wording.

    Each real book was read once, its heading vocabulary written down, and a
    synthetic page built to that shape — the books themselves are licensed and
    never enter the repo.
    """

    @staticmethod
    def _segment(path):
        doc = pymupdf.open(path)
        try:
            return segment_textbook(doc)
        finally:
            doc.close()

    def test_sample_problems_are_worked_examples(self, fake_physics_textbook):
        qs = self._segment(fake_physics_textbook)
        we = next(q for q in qs if q.provenance.lower().startswith("sample problem"))
        assert we.number == "1.6"
        assert "3.1 m/s^2" in we.answer
        assert "Solution" not in we.text

    def test_revision_questions_in_the_prose_are_found(self, fake_physics_textbook):
        qs = self._segment(fake_physics_textbook)
        rev = [q for q in qs if q.provenance.lower().startswith("revision question")]
        assert [q.number for q in rev] == ["1.5", "1.12"]
        assert "tram" in rev[0].text

    def test_teaching_prose_is_not_picked_up_as_a_question(self, fake_physics_textbook):
        text = " ".join(q.full_text for q in self._segment(fake_physics_textbook))
        assert "rate of change of displacement" not in text
        assert "push or a pull" not in text

    def test_question_markers_split_a_block(self, fake_busman_textbook):
        qs = self._segment(fake_busman_textbook)
        assert [q.number for q in qs] == ["1", "2"]
        assert qs[0].text.startswith("Outline one financial")
        assert "Question 1" not in qs[0].full_text

    def test_a_case_study_travels_with_every_question(self, fake_busman_textbook):
        qs = self._segment(fake_busman_textbook)
        assert len(qs) == 2
        assert all("Northbrook Cartons is a family-owned" in q.stimulus for q in qs)
        assert all(q.stimulus_page is not None for q in qs)

    def test_marks_and_bare_attribution_are_lifted_out(self, fake_busman_textbook):
        qs = self._segment(fake_busman_textbook)
        assert [q.marks for q in qs] == [2, 6]
        assert qs[0].provenance == "Adapted from VCAA 2020 exam Section A Q1a"
        assert "VCAA" not in qs[0].text
        # Without a citation of its own a question keeps its block heading.
        assert qs[1].provenance == "Exam-style questions"


class TestPassages:
    @pytest.fixture
    def passages(self, fake_textbook, design):
        doc = pymupdf.open(fake_textbook)
        try:
            ps = extract_passages(doc)
        finally:
            doc.close()
        tag_passages(ps, KeywordTagger(design))
        return ps

    def test_teaching_sections_are_found(self, passages):
        titles = [p.title for p in passages]
        assert any("photoelectric" in t.lower() for t in titles)
        assert any("wave-like nature" in t.lower() for t in titles)

    def test_question_blocks_are_not_passages(self, passages):
        titles = [p.title.lower() for p in passages]
        assert not any(t.startswith("questions") for t in titles)
        assert not any(t.startswith("worked example") for t in titles)
        assert not any(t.startswith("chapter review") for t in titles)

    def test_section_numbers_are_captured(self, passages):
        numbers = {p.section_number for p in passages}
        assert "6.1" in numbers and "6.2" in numbers

    def test_passages_are_tagged_to_the_right_dot_points(self, passages, design):
        photo = next(p for p in passages if "photoelectric" in p.title.lower())
        assert photo.kk_ids, "the photoelectric section got no dot point"
        texts = " ".join(design.key_knowledge(k).text.lower() for k in photo.kk_ids)
        assert "photoelectric" in texts

        matter = next(p for p in passages if "wave-like" in p.title.lower())
        texts = " ".join(design.key_knowledge(k).text.lower() for k in matter.kk_ids)
        assert "de broglie" in texts or "wave-like nature of matter" in texts

    def test_passages_carry_page_ranges(self, passages):
        for p in passages:
            assert p.page_end >= p.page_start >= 0


class TestIndexBook:
    def test_a_textbook_indexes_questions_and_content(self, fake_textbook, conn,
                                                      design):
        report = index_book(conn, fake_textbook, subject_id="physics",
                            source_id="tb", design=design, progress=lambda *_: None)
        assert report.kind == "textbook"
        assert report.questions_indexed >= 4
        assert report.passages_indexed >= 2
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == \
            report.questions_indexed
        assert conn.execute("SELECT COUNT(*) n FROM passage").fetchone()["n"] == \
            report.passages_indexed

    def test_checkpoints_takes_the_checkpoints_path(self, fake_book, conn, design):
        report = index_book(conn, fake_book, subject_id="physics", source_id="cp",
                            design=design, progress=lambda *_: None)
        assert report.kind == "checkpoints"
        assert report.questions_found == 3

    def test_kind_can_be_forced(self, fake_textbook, conn, design):
        report = index_book(conn, fake_textbook, subject_id="physics",
                            source_id="tb", kind="checkpoints", design=design,
                            progress=lambda *_: None)
        assert report.kind == "checkpoints"
        assert "forced" in report.detection

    def test_content_can_be_skipped(self, fake_textbook, conn, design):
        report = index_book(conn, fake_textbook, subject_id="physics",
                            source_id="tb", design=design, include_content=False,
                            progress=lambda *_: None)
        assert report.passages_indexed == 0
        assert conn.execute("SELECT COUNT(*) n FROM passage").fetchone()["n"] == 0

    def test_passages_reach_coverage(self, fake_textbook, conn, design):
        index_book(conn, fake_textbook, subject_id="physics", source_id="tb",
                   design=design, progress=lambda *_: None)
        cov = db.passage_coverage(conn, "physics")
        assert cov and sum(cov.values()) >= 2

    def test_reindexing_is_idempotent(self, fake_textbook, conn, design):
        kw = dict(subject_id="physics", source_id="tb", design=design,
                  progress=lambda *_: None)
        a = index_book(conn, fake_textbook, **kw)
        b = index_book(conn, fake_textbook, **kw)
        assert (a.questions_indexed, a.passages_indexed) == \
            (b.questions_indexed, b.passages_indexed)
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == \
            a.questions_indexed

    def test_untagged_items_are_reported_not_hidden(self, fake_textbook, conn,
                                                    design):
        report = index_book(conn, fake_textbook, subject_id="physics",
                            source_id="tb", design=design, progress=lambda *_: None)
        assert report.questions_untagged + report.passages_untagged == \
            (report.questions_found - report.questions_indexed) + \
            (report.passages_found - report.passages_indexed)

    def test_content_is_searchable(self, fake_textbook, conn, design):
        index_book(conn, fake_textbook, subject_id="physics", source_id="tb",
                   design=design, progress=lambda *_: None)
        n = conn.execute(
            "SELECT COUNT(*) n FROM passage_fts WHERE passage_fts MATCH 'threshold'"
        ).fetchone()["n"]
        assert n >= 1


class TestHeadingDetectionIsNotFooledByMaths:
    """Checkpoints sets maths larger than prose; that is not a heading."""

    def test_option_lines_are_not_headings(self):
        from pathlib import Path

        from blitz.ingest.passages import extract_passages

        sample = Path(__file__).resolve().parent.parent / "sources" / \
            "physics-checkpoints-sample.pdf"
        if not sample.exists():
            pytest.skip("Checkpoints sample not present")
        doc = pymupdf.open(sample)
        passages = extract_passages(doc)
        doc.close()
        titles = [p.title for p in passages]
        # Before the fix these were "D 250 m s⁻¹", "maximum KE of 5.4 − 4.9 = 0.5 eV"...
        assert all(not t.startswith(("A ", "B ", "C ", "D ")) for t in titles), titles
        assert all("=" not in t for t in titles), titles
        assert len(passages) <= 4, f"a question book should yield almost no prose: {titles}"

    def test_a_heading_size_must_be_rare(self):
        from collections import Counter

        from blitz.ingest.passages import heading_sizes

        # 10pt prose, 14.5pt maths on most lines, 18pt real headings on a few.
        profile = Counter({10.0: 60_000, 14.5: 30_000, 18.0: 900})
        sizes = heading_sizes(profile, body=10.0)
        assert 18.0 in sizes
        assert 14.5 not in sizes, "a size on a third of the book is not a heading"

    def test_words_are_required(self):
        from blitz.ingest.passages import _is_heading
        from blitz.ingest.textflow import Line

        big = lambda t: Line(text=t, x0=0, y0=0, x1=100, y1=10, size=18.0)
        assert _is_heading(big("Chapter 6 Light and matter"), 10.0)
        assert not _is_heading(big("3.0 × 10⁸"), 10.0)
        assert not _is_heading(big("λ = h/p"), 10.0)
        assert not _is_heading(big("D 250 m s⁻¹"), 10.0)

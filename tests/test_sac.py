"""Practice SACs: the shape Business Management actually comes in.

Business Management has no Checkpoints. Its sources are the textbook and
school-written practice SACs, which look nothing like a textbook question
block: one case study at the top, then multi-part questions that all refer
back to it, each with a total on its header and an allocation on every part.

Every one of these assertions failed before the SAC was tried.
"""

import json

import pymupdf
import pytest

from blitz.ingest.textbook import segment_textbook

from publisher_pages import build, sac_docx


def _questions(path):
    doc = pymupdf.open(path)
    try:
        return segment_textbook(doc)
    finally:
        doc.close()


@pytest.fixture
def sac(tmp_path):
    path, _ = build("practice-sac", tmp_path)
    return _questions(path)


class TestExtraction:
    def test_a_case_study_does_not_swallow_the_paper(self, sac):
        """"CASE STUDY" opened a stimulus block that nothing ever closed, so
        every question in the paper landed inside it and the SAC indexed as
        nothing at all."""
        assert len(sac) == 3

    def test_every_question_carries_the_case_study(self, sac):
        for q in sac:
            assert "Meridian Foods is a family-owned" in q.stimulus

    def test_the_header_total_is_the_total(self, sac):
        """Question 1 is 8 marks, not 8 plus its parts' 2 + 2 + 4."""
        assert [q.marks for q in sac] == [8, 10, 12]

    def test_a_restated_total_is_not_counted_twice(self, sac):
        """"Question 3 (12 marks) ... (12 marks)" is a 12-mark question."""
        assert sac[2].marks == 12
        assert "12 marks" not in sac[2].text

    def test_parts_survive_with_their_labels(self, sac):
        assert sac[0].parts == [
            "b. Outline one financial motivation strategy Meridian Foods could use.",
            "c. Analyse how this strategy might affect employee performance over the"
            " longer term.",
        ]

    def test_a_mark_split_across_a_line_break_is_rejoined(self, sac):
        """Word wraps mid-allocation: "... longer term. (4" / "marks)"."""
        assert all("(4" not in p for p in sac[0].parts)
        assert all("marks)" not in p for p in sac[0].parts)


def test_the_word_version_gives_the_same_questions(tmp_path):
    """A school writes a SAC in Word, not PDF. Both must agree."""
    from blitz.ingest.docx import docx_to_pdf

    docx = sac_docx(tmp_path / "sac.docx")
    converted = docx_to_pdf(docx, tmp_path)
    from_word = _questions(converted)
    assert [q.marks for q in from_word] == [8, 10, 12]
    for q in from_word:
        assert "Meridian Foods is a family-owned" in q.stimulus
    assert all("marks" not in p.lower() for q in from_word for p in q.parts)


class TestRendering:
    """A shared case study is printed once, not once per question."""

    def _sheet(self, conn, tmp_path, contexts):
        from blitz.models import Question, SheetPlan, SheetSpec
        from blitz.render import render_sheet
        from blitz.studydesign import load_study_design

        design = load_study_design("business-management")
        kk = design.all_key_knowledge()[0].id
        questions = [
            Question(id=f"q{i}", subject_id="business-management",
                     question_type="bm-short-answer",
                     body=f"Question {i} body text that is long enough to count.",
                     stem=f"Question {i} body text that is long enough to count.",
                     marks=4, kk_ids=[kk], context=ctx, citation="sac")
            for i, ctx in enumerate(contexts, start=1)
        ]
        plan = SheetPlan(
            spec=SheetSpec(subject_id="business-management", kk_ids=[kk]),
            questions=questions)
        out = tmp_path / "s.pdf"
        render_sheet(plan, out, design)
        doc = pymupdf.open(out)
        text = " ".join(" ".join(p.get_text().split()) for p in doc)
        doc.close()
        return text

    CASE = ("Meridian Foods is a family-owned manufacturer employing 180 staff "
            "across two regional sites and facing rising absenteeism.")

    def test_a_shared_case_study_is_printed_once(self, conn, tmp_path):
        text = self._sheet(conn, tmp_path, [self.CASE] * 3)
        assert text.count("Meridian Foods is a family-owned") == 1

    def test_the_group_says_which_questions_it_covers(self, conn, tmp_path):
        text = self._sheet(conn, tmp_path, [self.CASE] * 3)
        assert "Questions 1–3 refer to the following case study." in text

    def test_a_question_with_its_own_stimulus_still_gets_it(self, conn, tmp_path):
        text = self._sheet(conn, tmp_path, [self.CASE, "A different scenario entirely."])
        assert text.count("Meridian Foods is a family-owned") == 1
        assert "A different scenario entirely." in text
        # Two different stimuli, so neither is a group.
        assert "refer to the following case study" not in text

    def test_questions_sharing_a_stimulus_are_brought_together(self):
        """They are only printed once if they end up adjacent."""
        from blitz.models import Question
        from blitz.render.sheet import _group_by_context

        def q(i, ctx):
            return Question(id=f"q{i}", subject_id="bm", question_type="t",
                            body="x", context=ctx)
        ordered = _group_by_context([q(1, "A"), q(2, "B"), q(3, "A"), q(4, "B")])
        assert [x.id for x in ordered] == ["q1", "q3", "q2", "q4"]


class TestDetection:
    """A school SAC has none of VCAA's furniture, so it was reported unknown."""

    def _kind(self, path):
        from blitz.ingest.detect import detect_kind

        doc = pymupdf.open(path)
        try:
            return detect_kind(doc)
        finally:
            doc.close()

    def test_a_practice_sac_is_recognised(self, tmp_path):
        path, _ = build("practice-sac", tmp_path)
        d = self._kind(path)
        assert d.kind == "exam"
        assert d.confidence >= 0.5

    def test_a_textbook_case_study_is_not_a_sac(self, tmp_path):
        """A textbook prints case studies too. What marks a paper out is its
        own furniture — "Total marks", "Time allowed" — not the stimulus."""
        path, _ = build("case-study-shared", tmp_path)
        assert self._kind(path).kind != "exam"

    @pytest.mark.parametrize("name", ["oxford-check-your-learning",
                                      "worked-then-questions",
                                      "mixed-mc-and-short"])
    def test_textbooks_stay_textbooks(self, name, tmp_path):
        path, _ = build(name, tmp_path)
        assert self._kind(path).kind == "textbook"

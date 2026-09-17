"""The promise is two pages. These tests hold it to that."""

import pymupdf
import pytest

from blitz.models import Question, SheetPlan, SheetSpec
from blitz.picker import build_plan
from blitz.render import render_sheet
from blitz.render.fonts import safe_markup
from blitz.studydesign import load_study_design


def _plan(conn, subject="physics", **kw):
    design = load_study_design(subject)
    kw.setdefault("kk_ids", [kk.id for kk in design.all_key_knowledge()])
    return build_plan(conn, SheetSpec(subject_id=subject, **kw), design)


def test_questions_never_exceed_two_pages(seeded, tmp_path):
    result = render_sheet(_plan(seeded, seed=1), tmp_path / "s.pdf")
    assert result["question_pages"] <= 2


def test_questions_fill_two_pages_when_there_is_material(seeded, tmp_path):
    result = render_sheet(_plan(seeded, seed=1), tmp_path / "s.pdf")
    assert result["question_pages"] == 2


def test_solutions_land_after_the_questions(seeded, tmp_path):
    out = tmp_path / "s.pdf"
    result = render_sheet(_plan(seeded, seed=1), out)
    assert result["total_pages"] > result["question_pages"]

    doc = pymupdf.open(out)
    assert "Worked solutions" in doc[result["question_pages"]].get_text("text")
    doc.close()


def test_solutions_can_be_turned_off(seeded, tmp_path):
    out = tmp_path / "s.pdf"
    result = render_sheet(_plan(seeded, seed=1, include_solutions=False), out)
    assert result["total_pages"] == result["question_pages"]

    doc = pymupdf.open(out)
    text = "".join(p.get_text("text") for p in doc)
    assert "Worked solutions" not in text
    doc.close()


def test_every_question_reaches_the_page(seeded, tmp_path):
    out = tmp_path / "s.pdf"
    plan = _plan(seeded, seed=4)
    result = render_sheet(plan, out)

    doc = pymupdf.open(out)
    text = " ".join(p.get_text("text") for p in doc).replace("\n", " ")
    doc.close()
    # render_sheet trims plan.questions to what actually fitted.
    assert len(plan.questions) == result["questions"]
    for q in plan.questions:
        opening = " ".join(q.body.split()[:6])
        assert opening in " ".join(text.split()), f"missing from PDF: {opening}"


def test_dot_point_checklist_is_printed(seeded, tmp_path):
    """The checklist is what makes a sheet auditable against the study design."""
    out = tmp_path / "s.pdf"
    design = load_study_design("physics")
    chosen = [kk.id for kk in design.area("physics-u3-aos1").key_knowledge]
    plan = _plan(seeded, kk_ids=chosen, seed=1)
    render_sheet(plan, out)

    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "This sheet covers" in first
    covered = {kk for q in plan.questions for kk in q.kk_ids}
    for kk_id in covered & set(chosen):
        assert design.key_knowledge(kk_id).display in first


def test_unverified_study_design_is_declared_on_the_sheet(seeded, tmp_path):
    out = tmp_path / "s.pdf"
    render_sheet(_plan(seeded, seed=1), out)
    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "not yet imported" in first


def test_generated_questions_are_marked_and_explained(seeded, tmp_path):
    out = tmp_path / "s.pdf"
    render_sheet(_plan(seeded, seed=1), out)
    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "generated to fill a coverage gap" in first


def test_physics_notation_survives_the_pdf(seeded, tmp_path):
    """m s⁻¹ and Δ must not come out as black boxes."""
    out = tmp_path / "s.pdf"
    render_sheet(_plan(seeded, seed=1), out)
    doc = pymupdf.open(out)
    text = " ".join(p.get_text("text") for p in doc)
    doc.close()
    assert "�" not in text
    assert "m s" in text


def test_a_single_huge_question_still_renders(seeded, tmp_path):
    """One question longer than a column must not spin the fit loop forever."""
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    monster = Question(
        id="monster", subject_id="physics", question_type="ph-explanation",
        body="Explain the following in detail. " + ("Consider each case. " * 400),
        marks=40, kk_ids=[kk.id], citation="test",
    )
    plan = SheetPlan(
        spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]),
        questions=[monster],
    )
    result = render_sheet(plan, tmp_path / "s.pdf")
    assert result["questions"] == 1


def test_missing_figure_file_does_not_break_the_render(seeded, tmp_path):
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-diagram",
        body="Interpret the figure.", marks=3, kk_ids=[kk.id],
        figure_path=str(tmp_path / "does-not-exist.png"), citation="test",
    )
    plan = SheetPlan(
        spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]), questions=[q]
    )
    result = render_sheet(plan, tmp_path / "s.pdf")
    assert result["questions"] == 1


@pytest.mark.parametrize("raw,expected", [
    ("20 m s⁻¹", "20 m s<super>-1</super>"),
    ("9.8 m s⁻²", "9.8 m s<super>-2</super>"),
    ("H₂O", "H<sub>2</sub>O"),
    ("10⁻¹⁹ C", "10<super>-19</super> C"),
    ("no markers here", "no markers here"),
])
def test_superscript_markup(raw, expected):
    assert safe_markup(raw) == expected


def test_markup_is_applied_after_escaping(seeded, tmp_path):
    """A < in a question body must be escaped, not treated as a tag."""
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-calculation",
        body="Show that v < c for any massive particle at 10⁸ m s⁻¹.",
        marks=3, kk_ids=[kk.id], citation="test",
    )
    plan = SheetPlan(
        spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]), questions=[q]
    )
    out = tmp_path / "s.pdf"
    render_sheet(plan, out)
    doc = pymupdf.open(out)
    text = " ".join(" ".join(p.get_text("text").split()) for p in doc)
    doc.close()
    assert "v < c" in text


def test_footer_pieces_do_not_overlap(seeded, tmp_path):
    """A long AOS title used to run straight under the legend and page number."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    out = tmp_path / "s.pdf"
    design = load_study_design("physics")
    # The longest AOS titles in the subject, to make the subtitle as wide as possible.
    render_sheet(_plan(seeded, seed=1), out)

    doc = pymupdf.open(out)
    page = doc[0]
    band = pymupdf.Rect(0, page.rect.height - 46, page.rect.width,
                        page.rect.height - 12)
    spans = []
    for block in page.get_text("dict", clip=band)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                spans.append(span["bbox"])
    doc.close()

    assert len(spans) >= 2, "expected a subtitle and a page number in the footer"
    spans.sort(key=lambda b: b[0])
    for left, right in zip(spans, spans[1:]):
        assert left[2] <= right[0] + 0.5, f"footer text overlaps: {left} / {right}"


def test_long_subtitle_is_elided_not_truncated_silently(seeded, tmp_path):
    from blitz.render.sheet import _elide

    long = "VCE Physics · " + "a very long area of study title " * 6
    out = _elide(long, "Helvetica", 6.8, 200)
    assert out.endswith("…")
    assert len(out) < len(long)
    assert _elide("short", "Helvetica", 6.8, 200) == "short"

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


def test_a_quick_sheet_is_one_page_of_questions(seeded, tmp_path):
    result = render_sheet(_plan(seeded, seed=1, length="quick"), tmp_path / "s.pdf")
    assert result["question_pages"] == 1


def test_an_extended_sheet_may_run_past_two(seeded, tmp_path):
    """The cap moves with the length, so a long sheet is not truncated at two.

    The sample bank is small, so this asserts the ceiling rather than that
    four pages actually fill — running out of questions is the index's
    business, not the renderer's.
    """
    result = render_sheet(_plan(seeded, seed=1, length="extended"), tmp_path / "s.pdf")
    assert result["question_pages"] <= 4
    standard = render_sheet(_plan(seeded, seed=1), tmp_path / "t.pdf")
    assert result["question_pages"] >= standard["question_pages"]


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
    """A sheet built on dot points that are not VCAA's own wording must say so.

    Both shipped designs are now imported from VCAA, so the unverified one is
    made here: the Business Management design with one dot point flagged."""
    import yaml

    from blitz.config import STUDY_DESIGN_DIR
    from blitz.studydesign.loader import load_study_design_file

    data = yaml.safe_load((STUDY_DESIGN_DIR / "business-management.yaml").read_text(
        encoding="utf-8"))
    data["units"][0]["areas_of_study"][0]["key_knowledge"][0]["verified"] = False
    path = tmp_path / "business-management.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    design = load_study_design_file(path)
    out = tmp_path / "s.pdf"
    render_sheet(_plan(seeded, subject="business-management", seed=1), out, design)
    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "not yet imported" in first


def test_a_verified_study_design_carries_no_warning(seeded, tmp_path):
    """Physics was imported from the VCAA PDF; it must not be caveated."""
    out = tmp_path / "s.pdf"
    render_sheet(_plan(seeded, subject="physics", seed=1), out)
    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "not yet imported" not in first


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


def test_multi_part_questions_break_onto_separate_lines(seeded, tmp_path):
    """Inlined parts read as a wall of text; the book puts them on their own lines."""
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-multi-step",
        body="A trolley rolls down a ramp. a. Calculate its speed. b. Find the energy lost.",
        stem="A trolley rolls down a ramp.",
        parts=["a. Calculate its speed at the bottom.",
               "b. Find the energy lost to friction."],
        marks=5, kk_ids=[kk.id], citation="test",
    )
    plan = SheetPlan(spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]),
                     questions=[q])
    out = tmp_path / "s.pdf"
    render_sheet(plan, out)

    doc = pymupdf.open(out)
    lines = [" ".join(l.split()) for l in doc[0].get_text("text").splitlines()]
    doc.close()
    # Each part must start its own line rather than being glued into the stem.
    assert any(l.startswith("a. Calculate its speed") for l in lines)
    assert any(l.startswith("b. Find the energy lost") for l in lines)


def test_single_part_questions_are_unaffected(seeded, tmp_path):
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-calculation",
        body="Calculate the speed of the trolley at the bottom of the ramp.",
        marks=3, kk_ids=[kk.id], citation="test",
    )
    plan = SheetPlan(spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]),
                     questions=[q])
    out = tmp_path / "s.pdf"
    result = render_sheet(plan, out)
    assert result["questions"] == 1

    doc = pymupdf.open(out)
    text = " ".join(" ".join(doc[0].get_text("text").split()).split())
    doc.close()
    assert "Calculate the speed of the trolley" in text


def test_checklist_names_only_dot_points_that_got_a_question(seeded, tmp_path):
    """A real area of study has 28 dot points; listing them all overflowed."""
    design = load_study_design("physics")
    chosen = [kk.id for kk in design.area("physics-u4-aos1").key_knowledge]
    plan = _plan(seeded, kk_ids=chosen, seed=3)
    out = tmp_path / "s.pdf"
    render_sheet(plan, out)

    doc = pymupdf.open(out)
    first = " ".join(doc[0].get_text("text").split())
    doc.close()
    assert "This sheet covers" in first
    for kk_id in plan.uncovered_kk_ids:
        assert design.key_knowledge(kk_id).display not in first


def test_a_cropped_question_prints_the_image_not_the_text(seeded, tmp_path):
    """The text was judged untrustworthy at ingest, so it must not reach the page.

    Printing both would put the mangled version next to the correct one.
    """
    import pymupdf as _pymupdf
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    art = tmp_path / "fig.pdf"
    c = rl_canvas.Canvas(str(art), pagesize=A4)
    c.setLineWidth(1)
    c.rect(20 * mm, 200 * mm, 60 * mm, 30 * mm)
    c.save()
    png = tmp_path / "fig.png"
    doc = _pymupdf.open(art)
    doc[0].get_pixmap(clip=_pymupdf.Rect(50, 150, 250, 260)).save(png)
    doc.close()

    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-mc",
        body="MANGLEDTEXTTOKEN E = hp which cannot be trusted",
        marks=1, kk_ids=[kk.id], citation="test",
        figure_path=str(png), render_mode="crop",
    )
    plan = SheetPlan(spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]),
                     questions=[q])
    out = tmp_path / "s.pdf"
    render_sheet(plan, out)

    d = pymupdf.open(out)
    text = " ".join(p.get_text("text") for p in d)
    images = sum(len(d[i].get_images(full=True)) for i in range(d.page_count))
    d.close()
    assert "MANGLEDTEXTTOKEN" not in text, "untrusted text reached the sheet"
    assert images >= 1, "the page crop was not printed"


def test_a_normal_question_still_prints_its_text(seeded, tmp_path):
    design = load_study_design("physics")
    kk = design.all_key_knowledge()[0]
    q = Question(
        id="q1", subject_id="physics", question_type="ph-calculation",
        body="RELIABLETEXTTOKEN calculate the impulse.",
        marks=3, kk_ids=[kk.id], citation="test",
    )
    plan = SheetPlan(spec=SheetSpec(subject_id="physics", kk_ids=[kk.id]),
                     questions=[q])
    out = tmp_path / "s.pdf"
    render_sheet(plan, out)
    d = pymupdf.open(out)
    text = " ".join(p.get_text("text") for p in d)
    d.close()
    assert "RELIABLETEXTTOKEN" in text


class TestColumnChoice:
    """A page crop is an image of the book; scaled too far it stops being readable."""

    def _crop_question(self, tmp_path, width_pt, name, kk):
        """A question whose figure is a crop of the given width."""
        import pymupdf as _pymupdf
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        art = tmp_path / f"{name}.pdf"
        c = rl_canvas.Canvas(str(art), pagesize=A4)
        c.setFont("Helvetica", 10)
        c.drawString(20, 700, "the question text as printed in the book")
        c.save()
        png = tmp_path / f"{name}.png"
        doc = _pymupdf.open(art)
        doc[0].get_pixmap(clip=_pymupdf.Rect(20, 690, 20 + width_pt, 750)).save(png)
        doc.close()

        return Question(
            id=name, subject_id="physics", question_type="ph-mc",
            body="text kept only for search", marks=1, kk_ids=[kk],
            citation="test", figure_path=str(png), render_mode="crop",
            figure_pt_width=width_pt,
        )

    def test_full_page_width_crops_force_a_single_column(self, seeded, tmp_path):
        from blitz.render.sheet import choose_columns

        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        wide = [self._crop_question(tmp_path, 548, f"w{i}", kk) for i in range(4)]
        assert choose_columns(wide) == 1

    def test_narrow_crops_keep_two_columns(self, seeded, tmp_path):
        from blitz.render.sheet import choose_columns

        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        narrow = [self._crop_question(tmp_path, 200, f"n{i}", kk) for i in range(4)]
        assert choose_columns(narrow) == 2

    def test_a_mostly_text_sheet_keeps_two_columns(self, seeded, tmp_path):
        from blitz.render.sheet import choose_columns

        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        one_crop = [self._crop_question(tmp_path, 548, "w", kk)]
        text = [Question(id=f"t{i}", subject_id="physics",
                         question_type="ph-calculation", body="Calculate it.",
                         marks=2, kk_ids=[kk], citation="t") for i in range(5)]
        assert choose_columns(one_crop + text) == 2

    def test_the_chosen_layout_reaches_the_pdf(self, seeded, tmp_path):
        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        wide = [self._crop_question(tmp_path, 548, f"w{i}", kk) for i in range(3)]
        plan = SheetPlan(spec=SheetSpec(subject_id="physics", kk_ids=[kk]),
                         questions=wide)
        result = render_sheet(plan, tmp_path / "s.pdf", design)
        assert result["columns"] == 1

    def test_an_explicit_column_count_wins(self, seeded, tmp_path):
        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        wide = [self._crop_question(tmp_path, 548, f"w{i}", kk) for i in range(3)]
        plan = SheetPlan(
            spec=SheetSpec(subject_id="physics", kk_ids=[kk], columns=2),
            questions=wide)
        assert render_sheet(plan, tmp_path / "s.pdf", design)["columns"] == 2

    def test_a_full_width_crop_stays_readable(self, seeded, tmp_path):
        """The point of the whole exercise: 10pt book text must not become 5pt."""
        from blitz.render.layout import crop_scale

        design = load_study_design("physics")
        kk = design.all_key_knowledge()[0].id
        q = self._crop_question(tmp_path, 548, "w", kk)
        assert crop_scale(q.figure_path, columns=2, pt_width=548) < 0.6, \
            "two columns squash it"
        assert crop_scale(q.figure_path, columns=1, pt_width=548) > 0.9, \
            "one column keeps it"

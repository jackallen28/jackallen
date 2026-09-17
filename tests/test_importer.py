"""The study design importer, tested against a PDF shaped like VCAA's."""

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from blitz.studydesign.importer import _bullets_after, _sections, import_study_design
from blitz.studydesign.loader import load_study_design_file

PAGE_W, PAGE_H = A4


@pytest.fixture
def fake_sd(tmp_path):
    path = tmp_path / "fake-study-design.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    y = [PAGE_H - 25 * mm]

    def line(text, font="Helvetica", size=10):
        if y[0] < 25 * mm:
            c.showPage()
            y[0] = PAGE_H - 25 * mm
        c.setFont(font, size)
        c.drawString(20 * mm, y[0], text)
        y[0] -= 5.5 * mm

    line("Victorian Certificate of Education")
    line("PHYSICS STUDY DESIGN 2031-2035", "Helvetica-Bold", 13)
    line("")
    for unit, utitle, areas in [
        (3, "How do fields explain motion and electricity?", [
            (1, "How do physicists explain motion in two dimensions?",
             ["Newton's three laws of motion in one and two dimensions",
              "impulse and momentum in an isolated system",
              "projectile motion near the Earth's surface"],
             ["apply Newton's laws to real situations",
              "analyse transfers of energy"]),
            (2, "How do things move without contact?",
             ["fields as a model to explain forces acting at a distance",
              "Newton's law of universal gravitation"],
             ["model fields using field lines"]),
        ]),
        (4, "How have creative ideas revolutionised thinking?", [
            (1, "How has understanding about the physical world changed?",
             ["the wave model of light and interference",
              "Einstein's two postulates of special relativity"],
             ["compare the wave and particle models"]),
        ]),
    ]:
        line(f"Unit {unit}: {utitle}", "Helvetica-Bold", 12)
        for number, title, kk, ks in areas:
            line(f"Area of Study {number}", "Helvetica-Bold", 11)
            line(title, "Helvetica-Bold", 11)
            line("Some introductory prose about this area of study.")
            line(f"Outcome {number}", "Helvetica-Bold", 11)
            line("On completion of this unit the student should be able to")
            line("investigate and analyse the relevant phenomena.")
            line("Key knowledge", "Helvetica-Bold", 10)
            for item in kk:
                line(f"• {item}")
            line("Key skills", "Helvetica-Bold", 10)
            for item in ks:
                line(f"• {item}")
            line("")
    c.save()
    return path


def test_units_three_and_four_are_found(fake_sd):
    from blitz.studydesign.importer import extract_text

    units = _sections(extract_text(fake_sd))
    assert [u["number"] for u in units] == [3, 4]
    assert "fields explain motion" in units[0]["title"]


def test_bullets_are_collected_with_wrapped_lines():
    chunk = (
        "Key knowledge\n"
        "• the first dot point which wraps\n"
        "  onto a second line here\n"
        "• the second dot point entirely\n"
        "Key skills\n"
        "• a skill that must not be collected\n"
    )
    from blitz.studydesign.importer import KK_RE, KS_RE

    bullets = _bullets_after(chunk, KK_RE, stop_at=KS_RE)
    assert len(bullets) == 2
    assert "onto a second line here" in bullets[0]
    assert "must not be collected" not in " ".join(bullets)


def test_import_writes_a_loadable_file(fake_sd, tmp_path):
    out = import_study_design(fake_sd, "physics", out_dir=tmp_path)
    design = load_study_design_file(out)

    assert design.accreditation == "2031-2035"
    assert sorted(u.number for u in design.units) == [3, 4]
    assert len(design.all_areas()) == 3

    kk = design.all_key_knowledge()
    assert len(kk) == 7          # 3 + 2 + 2 across the three areas of study
    assert all(k.verified for k in kk), "imported wording is VCAA's, so verified"
    assert any("universal gravitation" in k.text for k in kk)


def test_import_preserves_our_own_editorial_data(fake_sd, tmp_path):
    """Question types are ours, not VCAA's — an import must not wipe them."""
    import shutil

    from blitz.config import STUDY_DESIGN_DIR

    shutil.copy(STUDY_DESIGN_DIR / "physics.yaml", tmp_path / "physics.yaml")
    before = load_study_design_file(tmp_path / "physics.yaml")
    assert before.question_types

    out = import_study_design(fake_sd, "physics", out_dir=tmp_path)
    after = load_study_design_file(out)

    assert [q.id for q in after.question_types] == [q.id for q in before.question_types]
    assert after.command_terms == before.command_terms


def test_import_refuses_a_pdf_with_no_units(tmp_path):
    path = tmp_path / "not-a-study-design.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(20 * mm, PAGE_H - 30 * mm, "This is a shopping list, not a syllabus.")
    c.save()

    with pytest.raises(ValueError, match="no 'Unit 3'"):
        import_study_design(path, "physics", out_dir=tmp_path)


def test_dry_run_does_not_write(fake_sd, tmp_path):
    target = import_study_design(fake_sd, "physics", out_dir=tmp_path, dry_run=True)
    assert not target.exists()

"""Line reconstruction — the fix for PyMuPDF emitting superscripts out of order."""

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from blitz.ingest.textflow import (
    build_lines,
    fraction_bars,
    horizontal_rules,
    page_text,
)

PAGE_W, PAGE_H = A4


@pytest.fixture
def typeset(tmp_path):
    """A PDF that reproduces the layout traps found in the real Checkpoints PDF."""
    path = tmp_path / "typeset.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    y = PAGE_H - 40 * mm

    # A raised exponent, set slightly above the baseline, as the real book does.
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, y, "The car travels at 25 m s")
    c.setFont("Helvetica", 8)
    c.drawString(20 * mm + 108, y + 4, "-1")           # raised
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm + 120, y, "along the road.")

    # A subscript.
    y -= 12 * mm
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, y, "The cut-off frequency f")
    c.setFont("Helvetica", 8)
    c.drawString(20 * mm + 104, y - 3, "0")            # lowered
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm + 112, y, "was measured.")

    # A full-width rule (question separator) and a short one (fraction bar).
    y -= 14 * mm
    c.setLineWidth(0.5)
    c.line(20 * mm, y, PAGE_W - 20 * mm, y)
    y -= 14 * mm
    c.line(40 * mm, y, 40 * mm + 18, y)                # fraction bar

    c.save()
    return path


def test_superscript_lands_in_the_right_place(typeset):
    doc = pymupdf.open(typeset)
    text = page_text(doc[0])
    doc.close()
    assert "25 m s⁻¹ along the road" in text
    # The failure this guards against: the exponent emitted before its sentence.
    assert not text.lstrip().startswith("-1")


def test_subscript_lands_in_the_right_place(typeset):
    doc = pymupdf.open(typeset)
    text = page_text(doc[0])
    doc.close()
    assert "f₀ was measured" in text


def test_full_width_rules_are_found(typeset):
    doc = pymupdf.open(typeset)
    rules = horizontal_rules(doc[0])
    doc.close()
    assert rules, "the question separator rule was not detected"


def test_fraction_bars_are_distinguished_from_separators(typeset):
    doc = pymupdf.open(typeset)
    page = doc[0]
    bars = fraction_bars(page)
    rules = horizontal_rules(page)
    doc.close()
    assert len(bars) == 1, f"expected exactly one fraction bar, got {bars}"
    # The separator must not be mistaken for a fraction bar, or every question
    # in the book would be flagged as unreflowable maths.
    bar_ys = {round(b[1]) for b in bars}
    assert not bar_ys & {round(y) for y in rules}


def test_lines_come_back_in_reading_order(typeset):
    doc = pymupdf.open(typeset)
    lines = build_lines(doc[0])
    doc.close()
    ys = [l.y0 for l in lines]
    assert ys == sorted(ys)
    assert all(l.text.strip() for l in lines)


def test_empty_page_yields_no_lines(tmp_path):
    path = tmp_path / "blank.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    c.showPage()
    c.save()
    doc = pymupdf.open(path)
    assert build_lines(doc[0]) == []
    doc.close()


@pytest.mark.parametrize("gap,expect_space", [(0.5, False), (6.0, True)])
def test_positional_word_spacing(gap, expect_space, tmp_path):
    """Word gaps in this PDF are positional, not space characters."""
    path = tmp_path / f"gap{gap}.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, PAGE_H - 40 * mm, "t =")
    c.drawString(20 * mm + c.stringWidth("t =", "Helvetica", 11) + gap,
                 PAGE_H - 40 * mm, "4.9")
    c.save()

    doc = pymupdf.open(path)
    text = page_text(doc[0])
    doc.close()
    assert ("t = 4.9" in text) == expect_space or "t =4.9" in text

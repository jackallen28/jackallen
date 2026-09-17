"""The page budget, in real units.

The picker needs to know how much will fit before it picks, and "fraction of a
page" turned out to be too slippery to reason about. So the unit here is
millimetres of column height: each question type carries an estimated height,
and the budget is the actual column height the renderer has available, derived
from the same page geometry the renderer uses.

The estimates are deliberately a little generous. Overshooting means the render
loop drops a question or two off the end; undershooting means a half-empty
second page, which is worse on a sheet whose whole promise is density.
"""

from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
GUTTER = 6 * mm
FOOTER = 6 * mm
MASTHEAD = 34 * mm          # header + dot-point checklist, first page only
COLUMNS = 2

# Line metrics for the body style, used to estimate text height.
BODY_LEADING = 10.4
MM_PER_LINE = BODY_LEADING / mm
CHARS_PER_LINE = 47         # 8.4pt Helvetica across a ~90mm column


def column_height_mm(first_page: bool) -> float:
    usable = (PAGE_H - 2 * MARGIN - FOOTER) / mm
    return usable - (MASTHEAD / mm if first_page else 0.0)


# Column breaks waste the tail of every column; the budget leaves room for it.
SAFETY = 0.92


def budget_mm(max_pages: int = 2, safety: float = SAFETY,
              columns: int = COLUMNS) -> float:
    """Total column millimetres available across the question pages."""
    total = column_height_mm(first_page=True) * columns
    total += column_height_mm(first_page=False) * columns * (max_pages - 1)
    return total * safety


def column_width_mm(columns: int = COLUMNS) -> float:
    if columns <= 1:
        return (PAGE_W - 2 * MARGIN) / mm
    return ((PAGE_W - 2 * MARGIN - GUTTER) / columns) / mm


# A single crop is never drawn taller than this. Legibility is set by the width
# scale, so a crop taller than this is a full-page region the pack should have
# split; drawing it at full height turned one question into two pages.
CROP_MAX_H_MM = {1: 120.0, 2: 90.0}


def crop_max_h_mm(columns: int = COLUMNS) -> float:
    return CROP_MAX_H_MM.get(max(1, min(columns, 2)), 90.0)


def image_px_size(path: str | None) -> tuple[int, int] | None:
    """Pixel width and height of an image file, or None if unreadable.

    Read with PIL on purpose: opening a PNG with PyMuPDF reports a rect in
    points at an assumed 96 dpi, i.e. pixels x 0.75, which silently put a
    factor of 0.75 into every width derived from it.
    """
    if not path:
        return None
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return None
    if not w or not h:
        return None
    return int(w), int(h)


def image_height_mm(path: str | None, columns: int = COLUMNS,
                    pt_width: float | None = None,
                    fallback: float = 60.0) -> float:
    """How much column height a page crop will occupy once scaled to fit.

    Mirrors the renderer exactly, including its height cap, so the picker's
    budget and the page agree.
    """
    size = image_px_size(path)
    if size is None:
        return fallback
    px_w, px_h = size
    # ReportLab fits the image to the column by its pixel dimensions, and the
    # renderer also caps the height; apply both so the estimate matches.
    col = column_width_mm(columns) * mm
    max_h = crop_max_h_mm(columns) * mm
    scale = min(col / px_w, max_h / px_h, 1.0)
    return (px_h * scale) / mm


def crop_scale(path: str | None, columns: int = COLUMNS,
               pt_width: float | None = None) -> float:
    """Fraction of its printed size a crop is rendered at. 1.0 is unscaled.

    Judged against the region's natural width in PDF points, not the PNG's
    pixels: crops are rendered at two or three pixels a point, so pixels say nothing about how big
    the content was on the page. Below about 0.6 the book's 10pt body text
    drops under 6pt and stops being readable.
    """
    if not path:
        return 1.0
    if pt_width is None:
        # No recorded width: assume the image is already at printed size.
        size = image_px_size(path)
        if size is None:
            return 1.0
        pt_width = size[0]
    if not pt_width:
        return 1.0
    return min((column_width_mm(columns) * mm) / pt_width, 1.0)


def text_height_mm(text: str, chars_per_line: int = CHARS_PER_LINE) -> float:
    lines = max(1, -(-len(text or "") // chars_per_line))
    return lines * MM_PER_LINE


def answer_space_mm(marks: int | None, is_mc: bool) -> float:
    """Whitespace left for the student to actually write the answer in."""
    if is_mc:
        return 1.0
    return min(4 + (marks or 2) * 5.2, 46)


def estimate_height_mm(
    body: str,
    *,
    marks: int | None = None,
    options: list[str] | None = None,
    has_figure: bool = False,
    fallback: float = 45.0,
) -> float:
    """Estimate how much column height one question will consume."""
    if not body:
        return fallback
    h = text_height_mm(body)
    if options:
        h += sum(text_height_mm(o, CHARS_PER_LINE - 4) for o in options) + 2
        h += answer_space_mm(marks, is_mc=True)
    else:
        h += answer_space_mm(marks, is_mc=False)
    if has_figure:
        h += 42                       # a crop scaled to a column, plus its caption
    h += 6                            # citation line and spacing
    return h

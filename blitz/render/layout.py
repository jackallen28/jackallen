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


def budget_mm(max_pages: int = 2, safety: float = 0.92) -> float:
    """Total column millimetres available across the question pages."""
    total = column_height_mm(first_page=True) * COLUMNS
    total += column_height_mm(first_page=False) * COLUMNS * (max_pages - 1)
    return total * safety


def column_width_mm() -> float:
    return ((PAGE_W - 2 * MARGIN - GUTTER) / COLUMNS) / mm


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

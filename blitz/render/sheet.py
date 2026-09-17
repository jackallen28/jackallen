"""Render a SheetPlan to a PDF.

Two columns, two pages of questions, then the worked solutions on their own
pages so the sheet itself stays a clean "two pager" you can print double-sided.

Fitting to exactly two pages is done by building the document, asking ReportLab
how many pages it actually used, and dropping the last question until it fits.
Estimating flowable heights up front is unreliable once images and ragged text
are involved; building is cheap enough (tens of milliseconds) to just measure.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from ..models import Question, SheetPlan
from ..studydesign import StudyDesign, load_study_design
from .answerspace import RuledSpace, lines_for_marks
from .fonts import safe_markup
from .layout import estimate_height_mm
from .styles import ACCENT, GENERATED, MUTED, RULE, stylesheet

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
GUTTER = 6 * mm
QUESTION_PAGES = 2
# Below this scale, the book's own body text stops being readable on the sheet.
MIN_CROP_SCALE = 0.62
# Share of a sheet that has to be page crops before it goes single column.
CROP_MAJORITY = 0.5


def _column_width(columns: int) -> float:
    if columns <= 1:
        return PAGE_W - 2 * MARGIN
    return (PAGE_W - 2 * MARGIN - GUTTER) / columns


def choose_columns(questions: list[Question]) -> int:
    """Two columns normally; one when the sheet is carried by page crops.

    A crop is an image of the real page, typically the full width of it. Scaled
    into a 90mm column that is about 47%, which puts the book's 10pt text under
    5pt — present but unreadable. Given the whole page it lands near full size.
    So a sheet that leans on crops gives up the second column to keep them
    legible, and takes fewer questions in exchange.
    """
    if not questions:
        return 2
    cropped = [q for q in questions if q.is_cropped]
    if len(cropped) / len(questions) < CROP_MAJORITY:
        return 2
    from .layout import crop_scale

    if any(crop_scale(spec["path"], columns=2, pt_width=spec.get("pt_width"))
           < MIN_CROP_SCALE
           for q in cropped for spec in q.figures_for("question")):
        return 1
    return 2
# How many dot points the masthead checklist names before it says "and N more".
CHECKLIST_MAX = 12


@dataclass
class _Ctx:
    plan: SheetPlan
    design: StudyDesign
    title: str
    subtitle: str

    @property
    def has_generated(self) -> bool:
        return any(q.generated for q in self.plan.questions)


class _Doc(BaseDocTemplate):
    """Two-column A4 with a running footer, plus a page counter for the fit loop."""

    def __init__(self, path, ctx: _Ctx, head_h: float = 34 * mm,
                 columns: int = 2, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN,
                         rightMargin=MARGIN, topMargin=MARGIN,
                         bottomMargin=MARGIN, title=ctx.title,
                         author="VCE Blitz", **kw)
        self.ctx = ctx
        self.page_count = 0
        self.masthead: list = []

        self.columns = max(1, columns)
        col_w = _column_width(self.columns)
        body_top = MARGIN + 6 * mm          # room for the footer rule
        body_h = PAGE_H - MARGIN - body_top

        # The first page gives up however much the masthead actually needs —
        # measured by the caller, because a wide dot-point selection makes the
        # checklist several lines longer.
        def frames(height: float, tag: str) -> list[Frame]:
            return [
                Frame(MARGIN + i * (col_w + GUTTER), body_top, col_w, height,
                      id=f"{tag}{i}", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
                for i in range(self.columns)
            ]

        first = frames(body_h - head_h, "f1c")
        later = frames(body_h, "fc")
        self.head_frame = Frame(
            MARGIN, PAGE_H - MARGIN - head_h + 4 * mm,
            PAGE_W - 2 * MARGIN, head_h - 4 * mm, id="head",
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([
            PageTemplate(id="first", frames=first, onPage=self._chrome),
            PageTemplate(id="later", frames=later, onPage=self._chrome),
        ])

    def _chrome(self, canvas, doc):
        self.page_count = max(self.page_count, doc.page)
        if doc.page == 1 and self.masthead:
            # Painted directly rather than flowed, so overflow is clipped to the
            # masthead instead of spilling into (and wasting) the first column.
            frame = Frame(
                self.head_frame._x1, self.head_frame._y1,
                self.head_frame._width, self.head_frame._height,
                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            )
            frame.addFromList(list(self.masthead), canvas)
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        y = MARGIN + 4.5 * mm
        canvas.line(MARGIN, y, PAGE_W - MARGIN, y)
        from reportlab.pdfbase.pdfmetrics import stringWidth

        from .fonts import font_names
        font = font_names()["regular"]
        size = 6.8
        canvas.setFont(font, size)

        page_label = f"page {doc.page}"
        page_w = stringWidth(page_label, font, size)
        legend = ("° generated to fill a coverage gap — not from a source book"
                  if self.ctx.has_generated else "")
        legend_w = stringWidth(legend, font, size) if legend else 0

        # The subtitle can be long enough to run under the legend and the page
        # number, so it gets whatever width is actually left and is elided.
        avail = (PAGE_W - 2 * MARGIN) - page_w - legend_w - 16
        subtitle = _elide(self.ctx.subtitle, font, size, max(avail, 40))

        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, MARGIN, subtitle)
        if legend:
            canvas.setFillColor(GENERATED)
            canvas.drawRightString(PAGE_W - MARGIN - page_w - 8, MARGIN, legend)
            canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN, page_label)
        canvas.restoreState()


def _elide(text: str, font: str, size: float, max_width: float) -> str:
    """Trim text to fit a width, with an ellipsis. Footers must not overlap."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if stringWidth(text, font, size) <= max_width:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if stringWidth(text[:mid] + ell, font, size) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip(" ,·") + ell


def _esc(text: str) -> str:
    """XML-escape, then rewrite Unicode super/subscripts as ReportLab markup."""
    return safe_markup(html.escape(text or "", quote=False))


def _figure(path: str | None, max_w: float, max_h: float = 62 * mm) -> Image | None:
    """Scale a crop to fit a column without ever upscaling past its native size."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        img = Image(str(p))
    except Exception:
        return None
    iw, ih = img.imageWidth, img.imageHeight
    if not iw or not ih:
        return None
    scale = min(max_w / iw, max_h / ih, 1.0)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    img.hAlign = "LEFT"
    return img


def _question_flowables(q: Question, n: int, ss, col_w: float, design) -> list:
    """One question as a block that won't be split across columns if it's short."""
    marks = f' <font color="#6b7280">({q.marks} mark{"s" if q.marks != 1 else ""})</font>' if q.marks else ""
    flag = ' <font color="#8a6d1f">°</font>' if q.generated else ""

    if q.is_cropped:
        # The text was judged untrustworthy at ingest — stacked fractions or
        # equation-editor glyphs — so the page image IS the question. Printing
        # the text as well would show the student the mangled version we
        # deliberately set aside, next to the correct one.
        return _cropped_question(q, n, ss, col_w, marks, flag)

    # A multi-part question reads as one wall of text if its parts are inlined.
    # Given a stem, the parts get their own indented lines, as in the book.
    head = q.stem if (q.stem and q.parts) else q.body
    tail = "" if (q.stem and q.parts) else f"{marks}{flag}"
    parts: list = []
    if q.context:
        # The scenario the question is set in, printed above it as the book
        # does. Without it the question is unanswerable, so it travels with it.
        parts.append(Paragraph(_esc(q.context), ss["Context"]))
        parts.append(Spacer(1, 2))
    parts.append(
        Paragraph(
            f'<b><font color="#1f4fd8">{n}.</font></b> {_esc(head)}{tail}',
            ss["Question"],
        )
    )
    for i, part in enumerate(q.parts):
        last = i == len(q.parts) - 1
        parts.append(Spacer(1, 1.5))
        parts.append(Paragraph(
            _esc(part) + (f"{marks}{flag}" if last else ""), ss["Part"]))
        if not q.options:
            parts.append(RuledSpace(
                col_w - 10, max(1, lines_for_marks(q.marks, q.question_type)
                                // max(len(q.parts), 1))))

    fig = _figure(q.figure_path, col_w)
    if fig is not None:
        parts += [Spacer(1, 2), fig]
        if q.figure_caption:
            parts.append(Paragraph(_esc(q.figure_caption), ss["Caption"]))
        else:
            parts.append(Spacer(1, 3))

    if q.options:
        for letter, opt in zip("ABCDEFGH", q.options):
            parts.append(Paragraph(f"<b>{letter}.</b>&nbsp; {_esc(opt)}", ss["Option"]))
        parts.append(Spacer(1, 2))
    else:
        # Ruled working space, scaled to the marks on offer.
        parts.append(Spacer(1, 1.5))
        parts.append(RuledSpace(col_w, lines_for_marks(q.marks, q.question_type)))

    if q.citation:
        parts.append(Paragraph(_esc(q.citation), ss["Citation"]))
    else:
        parts.append(Spacer(1, 4))

    # Keep short questions whole; let long ones flow so they don't blow a column.
    return [KeepTogether(parts)] if len(parts) <= 4 else parts


def _cropped_question(q: Question, n: int, ss, col_w: float,
                      marks: str, flag: str) -> list:
    """A question shown as images of the real pages.

    Used where the text was judged untrustworthy at ingest — stacked fractions,
    equation-editor glyphs. Printing the text as well would put the mangled
    version we deliberately set aside right next to the correct one.

    A question usually needs more than one image: the page it continues onto,
    the shared scenario printed above it, or an earlier question it depends on.
    They are stacked in the order the pack gave them, because that order is
    what makes the question answerable.
    """
    parts: list = []
    if q.context:
        parts.append(Paragraph(_esc(q.context), ss["Context"]))
        parts.append(Spacer(1, 2))
    parts.append(Paragraph(
        f'<b><font color="#1f4fd8">{n}.</font></b>{marks}{flag}', ss["Question"]))
    figures = q.figures_for("question")
    for i, spec in enumerate(figures):
        fig = _figure(spec["path"], col_w, max_h=170 * mm)
        if fig is None:
            continue
        parts += [Spacer(1, 2 if i == 0 else 3), fig]
        if spec.get("caption") and len(figures) > 1:
            parts.append(Paragraph(_esc(spec["caption"]), ss["Caption"]))
    if len(figures) == 1 and q.figure_caption:
        parts.append(Paragraph(_esc(q.figure_caption), ss["Caption"]))
    if not q.options:
        parts.append(Spacer(1, 1.5))
        parts.append(RuledSpace(col_w, lines_for_marks(q.marks, q.question_type)))
    if q.citation:
        parts.append(Paragraph(_esc(q.citation), ss["Citation"]))
    return parts


def _header(ctx: _Ctx, ss, width: float) -> list:
    plan, design = ctx.plan, ctx.design
    out: list = [
        Paragraph(_esc(ctx.title), ss["SheetTitle"]),
        Paragraph(_esc(ctx.subtitle), ss["SheetSubtitle"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=5),
    ]

    # The checklist: exactly which dot points this sheet covers. This is the bit
    # that makes the sheet auditable against the study design.
    #
    # Only the dot points that actually got a question are listed. Listing the
    # whole selection was fine when dot points were short hand-written labels,
    # but a real VCAA area of study has 28 of them and the list overflowed the
    # masthead — which silently dropped the checklist altogether.
    covered: list[str] = []
    unverified = False
    for kk_id in plan.spec.kk_ids:
        if kk_id in plan.uncovered_kk_ids:
            continue
        try:
            kk = design.key_knowledge(kk_id)
        except KeyError:
            continue
        star = "" if kk.verified else " *"
        unverified = unverified or not kk.verified
        covered.append(f"☐ {_esc(kk.display)}{star}")

    if covered:
        shown, extra = covered[:CHECKLIST_MAX], len(covered) - CHECKLIST_MAX
        line = '<b>This sheet covers:</b> &nbsp;' + " &nbsp;·&nbsp; ".join(shown)
        if extra > 0:
            line += f" &nbsp;·&nbsp; <i>and {extra} more</i>"
        out.append(Paragraph(line, ss["Checklist"]))
    skipped = len(plan.uncovered_kk_ids)
    if skipped:
        out.append(Paragraph(
            f"<i>{skipped} selected dot point(s) had no room on this sheet.</i>",
            ss["Checklist"],
        ))

    if unverified:
        out.append(Spacer(1, 2))
        out.append(Paragraph(
            "* wording not yet imported from the official VCAA study design — "
            "check before relying on it.",
            ss["Warning"],
        ))
    return out


def _solutions(ctx: _Ctx, ss, col_w: float) -> list:
    plan = ctx.plan
    out: list = [
        NextPageTemplate("later"),
        PageBreak(),
        Paragraph("Worked solutions", ss["SheetTitle"]),
        Paragraph(ctx.subtitle, ss["SheetSubtitle"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=6),
    ]
    for i, q in enumerate(plan.questions, start=1):
        block: list = [Paragraph(f"{i}.", ss["SolutionHeading"])]
        answer_figs = [_figure(spec["path"], col_w, max_h=110 * mm)
                       for spec in q.figures_for("answer")]
        answer_figs = [f for f in answer_figs if f is not None]
        cropped = q.answer_mode == "crop" and answer_figs
        if cropped:
            # Same reasoning as a cropped question: the worked solution's maths
            # would not survive as text, so the page images are the solution.
            for f in answer_figs:
                block += [f, Spacer(1, 3)]
        elif q.answer:
            block.append(Paragraph(_esc(q.answer), ss["Solution"]))
            for f in answer_figs:
                block += [f, Spacer(1, 3)]
        else:
            block.append(Paragraph(
                "<i>No worked solution in the source — check the book at the "
                "citation printed on the question.</i>", ss["Solution"]))
        if q.citation:
            block.append(Paragraph(_esc(q.citation), ss["Citation"]))
        out.append(KeepTogether(block))
    return out


def masthead_height(flowables: list, width: float, ss) -> float:
    """Measure the masthead so its frame is never too small to hold it.

    An undersized frame silently clips the dot-point checklist, which is the one
    part of the sheet that proves it matches the study design — so it is worth
    measuring rather than guessing.
    """
    total = 0.0
    for f in flowables:
        try:
            _, h = f.wrap(width, PAGE_H)
        except Exception:
            h = 12
        total += h + getattr(f, "spaceBefore", 0) + getattr(f, "spaceAfter", 0)
    return min(max(total + 6 * mm, 26 * mm), 70 * mm)


def render_sheet(
    plan: SheetPlan,
    path: Path,
    design: StudyDesign | None = None,
    max_pages: int = QUESTION_PAGES,
) -> dict:
    """Write the sheet and return a small report about what actually fitted."""
    design = design or load_study_design(plan.spec.subject_id)
    ss = stylesheet()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    title = plan.spec.title or f"{design.subject_name} — Blitz"
    aos_names = sorted({
        design.area_of(kk).display
        for kk in plan.spec.kk_ids
        if _has_area(design, kk)
    })
    subtitle = " · ".join([
        design.subject_name,
        ", ".join(aos_names) if aos_names else "Units 3 & 4",
        date.today().strftime("%d %b %Y"),
    ])
    ctx = _Ctx(plan=plan, design=design, title=title, subtitle=subtitle)

    questions = list(plan.questions)
    dropped: list[Question] = []
    columns = plan.spec.columns or choose_columns(questions)
    col_w = _column_width(columns)

    # Build, measure, shrink. Two pages is the promise; we keep it.
    masthead = _header(ctx, ss, PAGE_W - 2 * MARGIN)

    def _story(with_solutions: bool) -> list:
        out: list = []
        for i, q in enumerate(questions, start=1):
            out.extend(_question_flowables(q, i, ss, col_w, design))
        if with_solutions:
            sol_ctx = _Ctx(SheetPlan(spec=plan.spec, questions=questions),
                           design, title, subtitle)
            out.extend(_solutions(sol_ctx, ss, col_w))
        return out

    head_h = masthead_height(masthead, PAGE_W - 2 * MARGIN, ss)

    def _build(with_solutions: bool) -> int:
        doc = _Doc(path, ctx, head_h=head_h, columns=columns)
        doc.masthead = masthead
        doc.build(_story(with_solutions))
        return doc.page_count

    while True:
        question_pages = _build(with_solutions=False)
        if question_pages <= max_pages or len(questions) <= 1:
            break
        dropped.append(questions.pop())

    # Rebuild with the solutions appended, now that the question set is final.
    total_pages = _build(with_solutions=plan.spec.include_solutions)

    plan.questions = questions
    return {
        "path": str(path),
        "columns": columns,
        "questions": len(questions),
        "dropped": [q.id for q in dropped],
        "total_pages": total_pages,
        "question_pages": question_pages,
        "total_marks": sum(q.marks or 0 for q in questions),
    }


def _has_area(design: StudyDesign, kk_id: str) -> bool:
    try:
        design.area_of(kk_id)
        return True
    except KeyError:
        return False

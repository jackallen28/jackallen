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
from .layout import crop_max_h_mm, crop_scale
from .styles import ACCENT, GENERATED, MUTED, RULE, stylesheet

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
GUTTER = 6 * mm
QUESTION_PAGES = 2
# Below this scale, the book's own body text stops being readable on the sheet.
MIN_CROP_SCALE = 0.62
# Crops of known size are drawn at this fraction of the book's size.
CROP_DRAW_SCALE = 0.8
# Share of a sheet that has to be page crops before it goes single column.
CROP_MAJORITY = 0.5


def _column_width(columns: int) -> float:
    if columns <= 1:
        return PAGE_W - 2 * MARGIN
    return (PAGE_W - 2 * MARGIN - GUTTER) / columns


def legible_in_columns(q: Question, columns: int) -> bool:
    """Would every question crop still be readable at this column width?"""
    from .layout import crop_scale

    return all(
        crop_scale(spec["path"], columns=columns, pt_width=spec.get("pt_width"))
        >= MIN_CROP_SCALE
        for spec in q.figures_for("question")
    )


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
        wide = [Frame(MARGIN, body_top, PAGE_W - 2 * MARGIN, body_h, id="wide",
                      leftPadding=0, rightPadding=0, topPadding=0,
                      bottomPadding=0)]
        self.head_frame = Frame(
            MARGIN, PAGE_H - MARGIN - head_h + 4 * mm,
            PAGE_W - 2 * MARGIN, head_h - 4 * mm, id="head",
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([
            PageTemplate(id="first", frames=first, onPage=self._chrome),
            PageTemplate(id="later", frames=later, onPage=self._chrome),
            # One full-width column: the page for crops of the book's pages.
            PageTemplate(id="wide", frames=wide, onPage=self._chrome),
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


def _figure(path: str | None, max_w: float, max_h: float = 62 * mm,
            pt_width: float | None = None) -> Image | None:
    """Scale a crop to fit a column without ever upscaling past its printed size.

    Crops are rendered at two or three pixels per point, so the pixel width
    says nothing about how big the region was on the page. Given the region's
    width in points, that is the ceiling; a 110pt diagram is drawn at 110pt,
    not stretched across the column because its PNG happens to be 250px.
    """
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
    # Drawn at 80% of the book's size when the region's size is known: the
    # book sets 10pt, the sheet sets 8.4pt, and a crop at the sheet's own
    # size fits three worked problems on a page where full size fits two.
    natural = min(max_w, pt_width * CROP_DRAW_SCALE) if pt_width else max_w
    scale = min(natural / iw, max_h / ih, 1.0)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    img.hAlign = "LEFT"
    return img


def _group_by_context(questions: list[Question]) -> list[Question]:
    """Bring questions that share a stimulus together, keeping the order.

    A practice SAC gives one case study to every question in the paper. Unless
    they sit next to each other on the sheet the stimulus has to be reprinted
    for each one, and six copies of a six-line case study is most of a page.
    """
    out: list[Question] = []
    placed: set[str] = set()
    for q in questions:
        if q.id in placed:
            continue
        out.append(q)
        placed.add(q.id)
        if not q.context:
            continue
        for other in questions:
            if other.id not in placed and other.context == q.context:
                out.append(other)
                placed.add(other.id)
    return out


def _context_runs(questions: list[Question]) -> list[tuple[int, int]]:
    """(start, length) of each run of questions sharing one stimulus."""
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(questions):
        ctx = questions[i].context
        j = i + 1
        if ctx:
            while j < len(questions) and questions[j].context == ctx:
                j += 1
        runs.append((i, j - i))
        i = j
    return runs


def _question_flowables(q: Question, n: int, ss, col_w: float, design,
                        shared_context: bool = False) -> list:
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
    # The stem whenever there is one: q.body is the searchable full text and
    # carries the context, so using it printed the case study twice — once as
    # the grey stimulus block and again inside the question.
    head = q.stem or q.body
    tail = "" if (q.stem and q.parts) else f"{marks}{flag}"
    parts: list = []
    if q.context and not shared_context:
        # The scenario the question is set in, printed above it as the book
        # does. Without it the question is unanswerable, so it travels with it.
        # `shared_context` means the group above already printed it.
        parts.append(Paragraph(_esc(q.context), ss["Context"]))
        parts.append(Spacer(1, 2))
    parts.append(
        Paragraph(
            f'<b><font color="#1f4fd8">{n}.</font></b> {_esc(head)}{tail}',
            ss["Question"],
        )
    )
    # The ruled space a question earns is shared out across its parts; what
    # the split leaves over goes after the last part. Giving every part a
    # share and then the whole allowance again doubled the space and was the
    # single biggest reason the picker's estimates missed.
    total_lines = lines_for_marks(q.marks, q.question_type)
    per_part = max(1, total_lines // len(q.parts)) if q.parts else 0
    for i, part in enumerate(q.parts):
        last = i == len(q.parts) - 1
        parts.append(Spacer(1, 1.5))
        parts.append(Paragraph(
            _esc(part) + (f"{marks}{flag}" if last else ""), ss["Part"]))
        if not q.options:
            parts.append(RuledSpace(col_w - 10, per_part))

    fig = _figure(q.figure_path, col_w, pt_width=q.figure_pt_width)
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
        remaining_lines = total_lines - per_part * len(q.parts)
        if remaining_lines > 0:
            parts.append(Spacer(1, 1.5))
            parts.append(RuledSpace(col_w, remaining_lines))

    if q.citation or q.serial:
        parts.append(Paragraph(_esc(_cite(q)), ss["Citation"]))
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
    columns = 1 if col_w > (PAGE_W - 2 * MARGIN) * 0.6 else 2
    max_h = crop_max_h_mm(columns) * mm
    for i, spec in enumerate(figures):
        fig = _figure(spec["path"], col_w, max_h=max_h,
                      pt_width=spec.get("pt_width"))
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
    if q.citation or q.serial:
        parts.append(Paragraph(_esc(_cite(q)), ss["Citation"]))
    # A crop stack split across columns reads as two questions, one of them
    # headless. Kept together it moves whole to the next column; a stack too
    # tall for any column still splits, as Platypus falls back to flowing it.
    return [KeepTogether(parts)]


def _cite(q: Question) -> str:
    """The line under a question: its serial, then where it came from.

    The serial is what a teacher looks up. Printed on the question and again
    on its solution, it ties the two together and gives the Questions page
    something exact to search for."""
    bits = [b for b in (q.serial, q.citation) if b]
    return " · ".join(bits)


def _flow_height(f, avail_w: float) -> float:
    """Height one flowable will take at this width, in points."""
    if isinstance(f, KeepTogether):
        return sum(_flow_height(c, avail_w) for c in f._content)
    try:
        return float(f.wrap(avail_w, 10_000)[1])
    except Exception:
        return 0.0


def measure_question_mm(q: Question, columns: int, design: StudyDesign,
                        ss=None) -> float:
    """Column millimetres this question occupies, by building its flowables.

    The picker fills a millimetre budget, so it needs the same number the
    renderer ends up with. Estimating from character counts drifted by a
    factor of two in both directions once ruled space, stacked crops and
    multi-part questions were in play; laying the question out and asking
    is exact, and cheap enough to do for every candidate.
    """
    ss = ss or stylesheet()
    col_w = _column_width(columns)
    total = sum(_flow_height(f, col_w)
                for f in _question_flowables(q, 1, ss, col_w, design))
    return total / mm


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


def _solutions(ctx: _Ctx, ss, col_w: float, template: str = "later") -> list:
    plan = ctx.plan
    out: list = [
        NextPageTemplate(template),
        PageBreak(),
        Paragraph("Worked solutions", ss["SheetTitle"]),
        Paragraph(ctx.subtitle, ss["SheetSubtitle"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=6),
    ]
    for i, q in enumerate(plan.questions, start=1):
        block: list = [Paragraph(f"{i}.", ss["SolutionHeading"])]
        answer_figs = [_figure(spec["path"], col_w, max_h=110 * mm,
                               pt_width=spec.get("pt_width"))
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
        if q.citation or q.serial:
            block.append(Paragraph(_esc(_cite(q)), ss["Citation"]))
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
    max_pages: int | None = None,
) -> dict:
    """Write the sheet and return a small report about what actually fitted."""
    if max_pages is None:
        max_pages = plan.spec.question_pages
    design = design or load_study_design(plan.spec.subject_id)
    ss = stylesheet()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    title = plan.spec.title or f"{design.subject_name} — Blitz"
    aos_names = sorted({
        design.area_of(kk).display_with_unit
        for kk in plan.spec.kk_ids
        if _has_area(design, kk)
    })
    subtitle = " · ".join([
        design.subject_name,
        ", ".join(aos_names) if aos_names else "Units 3 & 4",
        date.today().strftime("%d %b %Y"),
    ])
    ctx = _Ctx(plan=plan, design=design, title=title, subtitle=subtitle)

    wide_ids = set(plan.wide_ids or [])
    questions = _group_by_context(
        [q for q in plan.questions if q.id not in wide_ids])
    wide = _group_by_context([q for q in plan.questions if q.id in wide_ids])
    dropped: list[Question] = []
    columns = plan.spec.columns or plan.columns or choose_columns(questions)
    col_w = _column_width(columns)
    wide_w = _column_width(1)

    # Build, measure, shrink. Two pages is the promise; we keep it.
    masthead = _header(ctx, ss, PAGE_W - 2 * MARGIN)

    # The worked solutions follow the questions' layout: a solution that is a
    # crop of the book's page is as unreadable in a column as the question
    # was, so if any answer needs the width, the whole section takes it.
    sol_columns = 1 if any(
        q.answer_mode == "crop" and not all(
            crop_scale(spec["path"], columns=2, pt_width=spec.get("pt_width"))
            >= MIN_CROP_SCALE for spec in q.figures_for("answer"))
        for q in questions + wide) else columns

    def _story(with_wide: bool, with_solutions: bool) -> list:
        # Only the first page carries the masthead; every page after it gets
        # the full column height. Without this switch page two reserved the
        # masthead's space and left it blank.
        out: list = [NextPageTemplate("later")]
        n = 0

        def emit(group: list[Question], width: float) -> None:
            """One run of questions, with a shared stimulus printed once."""
            nonlocal n
            shared = len(group) > 1 and bool(group[0].context)
            if shared:
                first, last = n + 1, n + len(group)
                lead = (f"Questions {first}\u2013{last} refer to the following "
                        "case study.")
                out.append(Paragraph(f"<b>{_esc(lead)}</b>", ss["Context"]))
                out.append(Paragraph(_esc(group[0].context), ss["Context"]))
                out.append(Spacer(1, 2))
            for q in group:
                n += 1
                out.extend(_question_flowables(q, n, ss, width, design,
                                               shared_context=shared))

        for start, size in _context_runs(questions):
            emit(questions[start:start + size], col_w)
        if with_wide and wide:
            out += [NextPageTemplate("wide"), PageBreak()]
            for start, size in _context_runs(wide):
                emit(wide[start:start + size], wide_w)
        if with_solutions:
            sol_ctx = _Ctx(SheetPlan(spec=plan.spec, questions=questions + wide),
                           design, title, subtitle)
            out.extend(_solutions(sol_ctx, ss, _column_width(sol_columns),
                                  template="wide" if sol_columns == 1 else "later"))
        return out

    head_h = masthead_height(masthead, PAGE_W - 2 * MARGIN, ss)

    def _build(with_wide: bool, with_solutions: bool) -> int:
        doc = _Doc(path, ctx, head_h=head_h, columns=columns)
        doc.masthead = masthead
        doc.build(_story(with_wide, with_solutions))
        return doc.page_count

    def _drop_largest(pool: list[Question], cols: int) -> None:
        # Drop the question that costs the most, not whichever came last.
        # Popping from the end once removed eight questions to make room for a
        # single two-page crop stack that was first in the list.
        biggest = max(pool, key=lambda q: measure_question_mm(q, cols, design, ss))
        pool.remove(biggest)
        dropped.append(biggest)

    # The text pages first: with a crop page to follow they get one page,
    # otherwise the whole allowance.
    text_pages = max_pages - 1 if wide else max_pages
    while True:
        question_pages = _build(with_wide=False, with_solutions=False)
        if question_pages <= text_pages or len(questions) <= 1:
            break
        _drop_largest(questions, columns)
    # Then the crop page, which must not spill into a third.
    while wide:
        question_pages = _build(with_wide=True, with_solutions=False)
        if question_pages <= max_pages or len(wide) <= 1:
            break
        _drop_largest(wide, 1)

    # Rebuild with the solutions appended, now that the question set is final.
    #
    # A solutions page is only worth a page if there are solutions on it. A
    # textbook with no answers section produced one identical line per
    # question — "No worked solution in the source" thirteen times — which is
    # a whole sheet of paper saying nothing. When not one question has an
    # answer, the section is dropped and the report says so.
    solutions_available = any(
        q.answer or (q.answer_mode == "crop" and q.figures_for("answer"))
        for q in questions + wide)
    with_solutions = plan.spec.include_solutions and solutions_available
    total_pages = _build(with_wide=True, with_solutions=with_solutions)

    plan.questions = questions + wide
    plan.wide_ids = [q.id for q in wide]
    return {
        "path": str(path),
        "columns": columns,
        "wide": len(wide),
        "questions": len(questions) + len(wide),
        "dropped": [q.id for q in dropped],
        "total_pages": total_pages,
        "question_pages": question_pages,
        "total_marks": sum(q.marks or 0 for q in questions + wide),
        "solutions": with_solutions,
        "solutions_missing": plan.spec.include_solutions and not solutions_available,
    }


def _has_area(design: StudyDesign, kk_id: str) -> bool:
    try:
        design.area_of(kk_id)
        return True
    except KeyError:
        return False

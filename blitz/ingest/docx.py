"""Word documents in.

Teachers hand out worksheets, notes and question banks as .docx, and VCAA
publishes some study designs that way. Everything downstream of here works on
pages: font sizes tell headings from body text, bounding boxes place figures,
page numbers make citations. So a Word file is rendered to a PDF first, with
the typography that pipeline expects (headings larger than body text, list
numbering made visible, images placed inline), and then treated as any other
book. The rendering is ReportLab, the same engine that draws the sheets; no
Word, no LibreOffice, no network.

For a study design the parser wants plain text with a bullet character in
front of each dot point, which is what `docx_text` produces.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import DATA_DIR

CONVERTED_DIR = DATA_DIR / "converted"

_HEADING = re.compile(r"heading\s*(\d)", re.IGNORECASE)
_BULLETISH = re.compile(r"bullet|list", re.IGNORECASE)

# Body text and heading sizes, in points. Headings have to be *rarer* than the
# body and clearly larger for passages.py to pick them out; these are.
BODY_PT = 10.5
HEADING_PT = {1: 17.0, 2: 14.0, 3: 12.5, 4: 11.5, 5: 11.5, 6: 11.0}


def is_docx(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".docx"


def _open(path: str | Path):
    try:
        import docx  # python-docx
    except ImportError as exc:                       # pragma: no cover
        raise ImportError(
            "Reading Word files needs python-docx: pip install python-docx"
        ) from exc
    return docx.Document(str(path))


# ---------------------------------------------------------------------------
# Walking the document body in order
# ---------------------------------------------------------------------------

class _Numbering:
    """Resolves Word's automatic list numbering into visible labels.

    Word stores "this paragraph is item 3 of list 7" and renders the "3."
    itself; the text carries nothing. The extractors downstream look for a
    visible number, so the label is reconstructed from the numbering part.
    """

    def __init__(self, document):
        self._formats: dict[tuple[str, int], str] = {}
        self._counters: dict[tuple[str, int], int] = {}
        try:
            numbering = document.part.numbering_part.element
        except Exception:
            return
        ns = numbering.nsmap.get("w")
        if not ns:
            return
        abstract: dict[str, dict[int, str]] = {}
        for an in numbering.findall(f"{{{ns}}}abstractNum"):
            aid = an.get(f"{{{ns}}}abstractNumId")
            levels: dict[int, str] = {}
            for lvl in an.findall(f"{{{ns}}}lvl"):
                ilvl = int(lvl.get(f"{{{ns}}}ilvl", "0"))
                fmt = lvl.find(f"{{{ns}}}numFmt")
                levels[ilvl] = fmt.get(f"{{{ns}}}val") if fmt is not None else "decimal"
            abstract[aid] = levels
        for num in numbering.findall(f"{{{ns}}}num"):
            nid = num.get(f"{{{ns}}}numId")
            ref = num.find(f"{{{ns}}}abstractNumId")
            if ref is None:
                continue
            for ilvl, fmt in abstract.get(ref.get(f"{{{ns}}}val"), {}).items():
                self._formats[(nid, ilvl)] = fmt

    @staticmethod
    def of(paragraph) -> tuple[str, int] | None:
        """(numId, level) of a paragraph, or None if it is not a list item.

        The numbering can sit on the paragraph itself or, as Word's own
        "List Number" style does, on its style or any style that inherits
        from; the chain is walked until one says.
        """
        candidates = [paragraph._p.pPr]
        style = paragraph.style
        seen = 0
        while style is not None and seen < 8:
            try:
                candidates.append(style.element.pPr)
            except Exception:
                pass
            style = style.base_style
            seen += 1
        for ppr in candidates:
            if ppr is None or ppr.numPr is None:
                continue
            num = ppr.numPr.numId
            lvl = ppr.numPr.ilvl
            if num is None:
                continue
            return str(num.val), int(lvl.val) if lvl is not None else 0
        return None

    def label(self, key: tuple[str, int]) -> str:
        fmt = self._formats.get(key, "decimal")
        if fmt == "bullet":
            return "•"
        # A deeper level restarts when a shallower one advances.
        for other in list(self._counters):
            if other[0] == key[0] and other[1] > key[1]:
                self._counters.pop(other)
        n = self._counters.get(key, 0) + 1
        self._counters[key] = n
        if fmt == "lowerLetter":
            return chr(ord("a") + (n - 1) % 26) + "."
        if fmt == "upperLetter":
            return chr(ord("A") + (n - 1) % 26) + "."
        if fmt in ("lowerRoman", "upperRoman"):
            roman = _roman(n)
            return (roman.lower() if fmt == "lowerRoman" else roman) + "."
        return f"{n}."


def _roman(n: int) -> str:
    out = ""
    for value, sym in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
                       (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                       (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += sym
            n -= value
    return out


def _heading_level(paragraph) -> int | None:
    name = paragraph.style.name if paragraph.style is not None else ""
    if name.lower() == "title":
        return 1
    m = _HEADING.search(name)
    return int(m.group(1)) if m else None


def _is_bullet_style(paragraph) -> bool:
    name = paragraph.style.name if paragraph.style is not None else ""
    return bool(_BULLETISH.search(name))


def _blocks(document):
    """Paragraphs and tables in the order they appear in the body."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            yield "p", Paragraph(child, document)
        elif tag == "tbl":
            yield "t", Table(child, document)


def _images_in(paragraph, document) -> list[bytes]:
    """Image blobs embedded in a paragraph, in order."""
    out: list[bytes] = []
    for rid in paragraph._p.xpath(".//a:blip/@r:embed"):
        try:
            out.append(document.part.related_parts[rid].blob)
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Plain text, for the study design importer
# ---------------------------------------------------------------------------

def docx_text(path: str | Path) -> str:
    """The document as lines, one paragraph per line, dot points bulleted."""
    document = _open(path)
    numbering = _Numbering(document)
    lines: list[str] = []
    for kind, block in _blocks(document):
        if kind == "t":
            for row in block.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                lines.append(" | ".join(c for c in cells if c))
            lines.append("")
            continue
        text = block.text.strip()
        if not text:
            lines.append("")
            continue
        key = _Numbering.of(block)
        if key is not None:
            label = numbering.label(key)
            lines.append(f"{label} {text}" if label != "•" else f"• {text}")
        elif _is_bullet_style(block):
            lines.append(f"• {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rendering to PDF, for the book pipeline
# ---------------------------------------------------------------------------

def _run_markup(run) -> str:
    from ..render.fonts import safe_markup

    text = safe_markup(run.text)
    if not text:
        return ""
    font = run.font
    if font.superscript:
        text = f"<super>{text}</super>"
    elif font.subscript:
        text = f"<sub>{text}</sub>"
    if run.bold:
        text = f"<b>{text}</b>"
    if run.italic:
        text = f"<i>{text}</i>"
    return text


def docx_to_pdf(path: str | Path, out_dir: Path | None = None) -> Path:
    """Render a Word file to a PDF the book pipeline can read.

    Written under data/converted/ by default and returned. Re-rendering is
    cheap and deterministic, so nothing is cached.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
    from reportlab.lib import colors

    from ..render.fonts import font_names, register_fonts

    path = Path(path)
    out_dir = Path(out_dir or CONVERTED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{path.stem}.pdf"

    register_fonts()
    f = font_names()
    body = ParagraphStyle("body", fontName=f["regular"], fontSize=BODY_PT,
                          leading=BODY_PT * 1.35, spaceAfter=BODY_PT * 0.6)
    item = ParagraphStyle("item", parent=body, leftIndent=6 * mm,
                          firstLineIndent=-6 * mm)
    headings = {
        lvl: ParagraphStyle(f"h{lvl}", fontName=f["bold"], fontSize=pt,
                            leading=pt * 1.25, spaceBefore=pt * 0.9,
                            spaceAfter=pt * 0.4)
        for lvl, pt in HEADING_PT.items()
    }
    cell = ParagraphStyle("cell", parent=body, fontSize=BODY_PT - 1,
                          leading=(BODY_PT - 1) * 1.3, spaceAfter=0)

    document = _open(path)
    numbering = _Numbering(document)
    page_w = A4[0] - 40 * mm
    story: list = []
    scratch = out_dir / f".{path.stem}-images"
    scratch.mkdir(exist_ok=True)
    n_img = 0

    for kind, block in _blocks(document):
        if kind == "t":
            rows = []
            for row in block.rows:
                rows.append([Paragraph(_cell_markup(c), cell) for c in row.cells])
            if rows:
                ncols = max(len(r) for r in rows)
                rows = [r + [Paragraph("", cell)] * (ncols - len(r)) for r in rows]
                t = Table(rows, colWidths=[page_w / ncols] * ncols, repeatRows=0)
                t.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]))
                story += [t, Spacer(1, 4 * mm)]
            continue

        markup = "".join(_run_markup(r) for r in block.runs).strip()
        level = _heading_level(block)
        key = _Numbering.of(block)
        if markup:
            if level is not None:
                story.append(Paragraph(markup, headings.get(level, headings[6])))
            elif key is not None:
                story.append(Paragraph(f"{numbering.label(key)}  {markup}", item))
            elif _is_bullet_style(block):
                story.append(Paragraph(f"•  {markup}", item))
            else:
                story.append(Paragraph(markup, body))
        for blob in _images_in(block, document):
            n_img += 1
            img_path = scratch / f"img{n_img:03d}.bin"
            img_path.write_bytes(blob)
            try:
                img = Image(str(img_path))
            except Exception:
                continue
            iw, ih = img.imageWidth, img.imageHeight
            if not iw or not ih:
                continue
            scale = min(page_w / iw, (120 * mm) / ih, 1.0)
            img.drawWidth, img.drawHeight = iw * scale, ih * scale
            img.hAlign = "LEFT"
            story += [img, Spacer(1, 3 * mm)]

    if not story:
        story.append(Paragraph("(empty document)", body))

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=20 * mm,
                            bottomMargin=20 * mm, title=path.stem)
    doc.build(story)
    return out


def _cell_markup(cell) -> str:
    parts = ["".join(_run_markup(r) for r in p.runs).strip() for p in cell.paragraphs]
    return "<br/>".join(p for p in parts if p)

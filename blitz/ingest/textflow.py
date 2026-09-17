"""Rebuild readable lines from a PDF's raw spans.

PyMuPDF's `get_text` sorts spans by their own y position, which breaks on
anything typeset off the baseline. In Checkpoints, "10 m s⁻¹" is set with the
"−1" raised about 1.3pt above the line, so it lands on its own y-row and is
emitted *before* the sentence it belongs to:

    10 m s at t = −1 2.6 s        <- what get_text("blocks") returns
    10 m s⁻¹ at t = 2.6 s         <- what is actually on the page

Physics questions are full of units and exponents, so this corrupts almost every
one of them. This module regroups spans into visual lines by baseline proximity,
orders each line by x, and re-attaches raised or lowered runs as super/subscripts
at the position they actually occupy.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

SUPER_DIGITS = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "−": "⁻", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
}
SUB_DIGITS = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "−": "₋",
}


@dataclass
class Span:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    font: str

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    """One visual line of text, in reading order."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float                       # the line's dominant font size
    spans: list[Span] = field(default_factory=list)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def _spans(page) -> list[Span]:
    out: list[Span] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                text = s["text"]
                if not text or not text.strip():
                    # Keep real spaces, drop empty artefacts.
                    if text and text.strip(" \xa0") == "" and text != "":
                        pass
                    else:
                        continue
                x0, y0, x1, y1 = s["bbox"]
                out.append(Span(text=text, x0=x0, y0=y0, x1=x1, y1=y1,
                                size=s["size"], font=s.get("font", "")))
    return out


def _dominant_size(spans: list[Span]) -> float:
    if not spans:
        return 10.0
    # Weight by how much text each span carries, so a stray exponent doesn't
    # define the line's size.
    weighted: dict[float, float] = {}
    for s in spans:
        weighted[round(s.size, 1)] = weighted.get(round(s.size, 1), 0) + len(s.text)
    return max(weighted.items(), key=lambda kv: kv[1])[0]


def _group_lines(spans: list[Span], tolerance: float = 0.62) -> list[list[Span]]:
    """Cluster spans into visual lines by vertical overlap with the line body.

    `tolerance` is a fraction of the line's dominant font size: a span whose
    centre sits within that distance of the line's centre belongs to it. A
    superscript is typically raised by 25-35% of the font size, so 0.62 catches
    it while still separating genuinely different lines.
    """
    lines: list[list[Span]] = []
    for span in sorted(spans, key=lambda s: (s.y0, s.x0)):
        placed = False
        for line in lines:
            size = _dominant_size(line)
            centre = sum(s.mid_y for s in line) / len(line)
            if abs(span.mid_y - centre) <= tolerance * size:
                line.append(span)
                placed = True
                break
        if not placed:
            lines.append([span])
    return lines


def _script_of(span: Span, line_size: float, baseline: float) -> str:
    """Is this span a superscript, a subscript, or ordinary text?"""
    if span.size >= line_size * 0.92:
        return ""
    offset = baseline - span.mid_y          # positive = raised
    if offset > line_size * 0.12:
        return "super"
    if offset < -line_size * 0.12:
        return "sub"
    return ""


def _render(text: str, script: str) -> str:
    """Map a small raised/lowered run onto real Unicode super/subscripts.

    Falls back to the literal characters when there is no Unicode equivalent —
    a wrong-looking exponent is much better than a silently dropped one.
    """
    table = SUPER_DIGITS if script == "super" else SUB_DIGITS
    out = []
    for ch in text:
        if ch in table:
            out.append(table[ch])
        elif ch.strip() == "":
            continue                      # no spaces inside an exponent
        else:
            return text                   # not cleanly mappable; keep as written
    return "".join(out)


def _join(a: str, b: str, gap: float = 0.0, size: float = 10.0) -> str:
    """Join two runs, inserting a space where the page shows one.

    Word spacing in this PDF is often positional rather than a space character —
    "t = 4.9" is three spans nudged apart, with no space glyph anywhere. So the
    gap between the spans decides, not the characters.
    """
    if not a:
        return b
    if not b:
        return a
    if a.endswith((" ", "\xa0")) or b.startswith((" ", "\xa0")):
        return a + b
    # Never push a space in front of punctuation or a super/subscript.
    if b[0] in ",.;:)%" or unicodedata.category(b[0]) == "No":
        return a + b
    if a[-1] == "(" :
        return a + b
    return (a + " " + b) if gap > size * 0.14 else a + b


def build_lines(page) -> list[Line]:
    """Every visual line on the page, in reading order, with scripts inline."""
    groups = _group_lines(_spans(page))
    lines: list[Line] = []

    for group in groups:
        group.sort(key=lambda s: s.x0)
        size = _dominant_size(group)
        body = [s for s in group if s.size >= size * 0.92] or group
        baseline = sum(s.mid_y for s in body) / len(body)

        text = ""
        prev_x1 = None
        for span in group:
            script = _script_of(span, size, baseline)
            piece = _render(span.text, script) if script else span.text
            gap = 0.0 if prev_x1 is None else span.x0 - prev_x1
            text = _join(text, piece, gap=gap, size=size)
            prev_x1 = span.x1

        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        if not text:
            continue
        lines.append(Line(
            text=text,
            x0=min(s.x0 for s in group), y0=min(s.y0 for s in group),
            x1=max(s.x1 for s in group), y1=max(s.y1 for s in group),
            size=size, spans=group,
        ))

    lines.sort(key=lambda l: (round(l.y0, 1), l.x0))
    return lines


def page_text(page) -> str:
    return "\n".join(l.text for l in build_lines(page))


def fraction_bars(page) -> list[tuple[float, float, float, float]]:
    """Short horizontal rules, which in a maths-set PDF are fraction bars.

    This is the only dependable signal that a fraction is present. A stacked
    fraction like h/p extracts as "h" on one line and "p" on the next, with
    nothing in the characters to say they were ever a fraction — the bar is
    drawn, not typed. Anything from a single character (about 6pt) up to a
    modest expression counts; wider than a third of the page is a section rule.
    """
    width = page.rect.width
    bars: list[tuple[float, float, float, float]] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if rect.height <= 3 and 2.0 < rect.width < width * 0.33:
            bars.append((rect.x0, rect.y0, rect.x1, rect.y1))
    return sorted(bars, key=lambda b: (b[1], b[0]))


def horizontal_rules(page, min_width_ratio: float = 0.5) -> list[float]:
    """The y positions of full-width horizontal rules.

    Checkpoints separates one question from the next with a rule across the
    column, which is a far more reliable boundary than anything in the text.
    """
    width = page.rect.width
    ys: list[float] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if rect.height <= 2.5 and rect.width >= width * min_width_ratio:
            ys.append(rect.y0)
    return sorted(set(round(y, 1) for y in ys))

"""Typography for the sheet.

Tuned for density: this is a cram sheet, not a textbook. 8.4pt body on 10.4pt
leading in two columns fits roughly 45 characters a line, which is about as
tight as stays readable on paper.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, StyleSheet1

from .fonts import font_names

INK = colors.HexColor("#14161a")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d3d7de")
ACCENT = colors.HexColor("#1f4fd8")
BAND = colors.HexColor("#eef1f7")
GENERATED = colors.HexColor("#8a6d1f")


def stylesheet() -> StyleSheet1:
    f = font_names()
    regular, bold, oblique = f["regular"], f["bold"], f["oblique"]
    ss = StyleSheet1()
    ss.add(ParagraphStyle(
        "SheetTitle", fontName=bold, fontSize=15, leading=17.5,
        textColor=INK, spaceAfter=1,
    ))
    ss.add(ParagraphStyle(
        "SheetSubtitle", fontName=regular, fontSize=8.6, leading=10.6,
        textColor=MUTED,
    ))
    ss.add(ParagraphStyle(
        "AosHeading", fontName=bold, fontSize=8.4, leading=10,
        textColor=colors.white, backColor=ACCENT, borderPadding=(3, 4, 3, 4),
        spaceBefore=7, spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "Question", fontName=regular, fontSize=8.4, leading=10.4,
        textColor=INK, alignment=TA_JUSTIFY, spaceBefore=0, spaceAfter=1.5,
    ))
    ss.add(ParagraphStyle(
        "Option", parent=ss["Question"], leftIndent=13, spaceAfter=0.5,
        alignment=TA_LEFT,
    ))
    ss.add(ParagraphStyle(
        "Part", parent=ss["Question"], leftIndent=10, spaceBefore=1,
        spaceAfter=0.5,
    ))
    ss.add(ParagraphStyle(
        "Citation", fontName=oblique, fontSize=6.5, leading=8,
        textColor=MUTED, spaceAfter=5,
    ))
    ss.add(ParagraphStyle(
        "Caption", fontName=regular, fontSize=6.5, leading=8,
        textColor=MUTED, spaceBefore=1, spaceAfter=3,
    ))
    ss.add(ParagraphStyle(
        "Checklist", fontName=regular, fontSize=7.2, leading=9.2,
        textColor=INK,
    ))
    ss.add(ParagraphStyle(
        "Warning", fontName=oblique, fontSize=7, leading=8.8,
        textColor=GENERATED,
    ))
    ss.add(ParagraphStyle(
        "SolutionHeading", fontName=bold, fontSize=8.4, leading=10.2,
        textColor=INK, spaceBefore=4, spaceAfter=1,
    ))
    ss.add(ParagraphStyle(
        "Solution", fontName=regular, fontSize=7.8, leading=9.6,
        textColor=INK, alignment=TA_JUSTIFY, spaceAfter=3,
    ))
    return ss

"""Fonts, because Physics needs glyphs the PDF base fonts don't have.

Helvetica and the other PDF base-14 fonts are Latin-1 only, so `m s⁻¹`, `Δ`,
`√`, `Φ` and `θ` all print as black boxes — which is fatal on a physics revision
sheet. We register a Unicode TrueType face instead, preferring DejaVu Sans
(present on essentially every Linux and available on macOS), then a few common
platform faces, and finally Bitstream Vera, which ships inside ReportLab itself
so there is always *something*.

Vera is missing a handful of the glyphs we care about, so whatever face we land
on, `safe_markup` also rewrites superscripts into ReportLab's own <super> markup.
That way the text stays correct even on a fallback font.
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# (family, regular, bold, italic, bold-italic) — first complete set wins.
CANDIDATES: list[tuple[str, tuple[str, ...]]] = [
    ("DejaVuSans", (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    )),
    ("DejaVuSans", (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-BoldOblique.ttf",
    )),
    ("DejaVuSans", (
        "/Library/Fonts/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans-Bold.ttf",
        "/Library/Fonts/DejaVuSans-Oblique.ttf",
        "/Library/Fonts/DejaVuSans-BoldOblique.ttf",
    )),
    ("ArialUnicode", (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\ariali.ttf",
        r"C:\Windows\Fonts\arialbi.ttf",
    )),
    ("Helvetica-mac", (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
    )),
]

_registered: str | None = None

# Superscripts we rewrite into <super> markup so they survive a fallback font.
SUPERSCRIPTS = {
    "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
    "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
    "\u207a": "+", "\u207b": "-", "\u207f": "n",
}
SUBSCRIPTS = {
    "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3", "\u2084": "4",
    "\u2085": "5", "\u2086": "6", "\u2087": "7", "\u2088": "8", "\u2089": "9",
}


def _vera_fallback() -> tuple[str, tuple[str, ...]]:
    import reportlab

    d = Path(reportlab.__file__).parent / "fonts"
    return ("Vera", (
        str(d / "Vera.ttf"), str(d / "VeraBd.ttf"),
        str(d / "VeraIt.ttf"), str(d / "VeraBI.ttf"),
    ))


def register_fonts() -> str:
    """Register the best available Unicode family. Returns the family name to use.

    Falls back to "Helvetica" only if every TrueType attempt fails, in which case
    `safe_markup` is doing the heavy lifting.
    """
    global _registered
    if _registered:
        return _registered

    for family, paths in [*CANDIDATES, _vera_fallback()]:
        regular, bold, italic, bolditalic = paths
        # Regular and bold are required; some distributions ship DejaVu without
        # the oblique faces, and synthesising them beats dropping to Vera.
        if not (os.path.exists(regular) and os.path.exists(bold)):
            continue
        italic = italic if os.path.exists(italic) else regular
        bolditalic = bolditalic if os.path.exists(bolditalic) else bold
        try:
            pdfmetrics.registerFont(TTFont(family, regular))
            pdfmetrics.registerFont(TTFont(f"{family}-Bold", bold))
            pdfmetrics.registerFont(TTFont(f"{family}-Oblique", italic))
            pdfmetrics.registerFont(TTFont(f"{family}-BoldOblique", bolditalic))
            pdfmetrics.registerFontFamily(
                family, normal=family, bold=f"{family}-Bold",
                italic=f"{family}-Oblique", boldItalic=f"{family}-BoldOblique",
            )
            _registered = family
            return family
        except Exception:
            continue

    _registered = "Helvetica"
    return _registered


def font_names() -> dict[str, str]:
    """Regular / bold / oblique names for whichever family got registered."""
    family = register_fonts()
    if family == "Helvetica":
        return {"regular": "Helvetica", "bold": "Helvetica-Bold",
                "oblique": "Helvetica-Oblique"}
    return {"regular": family, "bold": f"{family}-Bold",
            "oblique": f"{family}-Oblique"}


def safe_markup(text: str) -> str:
    """Rewrite Unicode super/subscripts as ReportLab markup.

    Call this AFTER escaping for XML, since it emits tags of its own.
    """
    out: list[str] = []
    i = 0
    n = len(text or "")
    while i < n:
        ch = text[i]
        for table, tag in ((SUPERSCRIPTS, "super"), (SUBSCRIPTS, "sub")):
            if ch in table:
                run = []
                while i < n and text[i] in table:
                    run.append(table[text[i]])
                    i += 1
                out.append(f"<{tag}>{''.join(run)}</{tag}>")
                break
        else:
            out.append(ch)
            i += 1
    return "".join(out)

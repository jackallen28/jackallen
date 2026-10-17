"""Colours and fonts. Change the look of the whole app here.

The look is retro (Windows 95 / Mac OS 8: bevelled buttons, title bars with a gradient, a
coloured "desktop") in the colours of the Banyule Nillumbik Tech School logo: teal, purple and
lavender. The logo's pixel squares are LOGO_SQUARES, drawn by widgets.PixelMark.
"""
import tkinter.font as tkfont

C = {
    # desktop + windows
    "desk": "#0E9DA4",          # the teal "desktop" behind windows
    "desk_dark": "#0A7E84",
    "bg": "#DCD6E6",            # window face: lavender grey (buttons, panels, bars)
    "face_hi": "#EAE5F1",       # face, hovered
    "panel": "#FFFFFF",         # sunken white wells: text, lists, checklists
    "panel_alt": "#F4F1F8",
    "line": "#9C93AE",          # dividers and outlines (retro lines are visible)
    "ink": "#141414",
    "muted": "#4F4963",
    "faint": "#8A839C",
    # logo colours
    "purple": "#704988",
    "purple_light": "#7E5B95",
    "lavender": "#CFC2E0",
    "teal": "#19C1CA",
    "teal_light": "#66D6DA",
    "title_a": "#5B3A73",       # title bars: purple → teal
    "title_b": "#12A9B1",
    # brand accent (purple) and "go" (teal)
    "accent": "#704988",
    "accent_dark": "#523468",
    "accent_soft": "#E8DFF2",
    "go": "#0B8F96",
    "go_dark": "#086F75",
    # states
    "ok": "#17804E",
    "ok_soft": "#DDF3E6",
    "warn": "#8A5200",
    "warn_soft": "#FFF0D4",
    "err": "#B42318",
    "err_soft": "#FCE4E2",
    "info": "#0A6F87",
    "info_soft": "#DCF3F4",
    "locked": "#A39CB0",
    # editor (deep indigo, like an old Turbo editor) + console (terminal black)
    "ed_bg": "#1C1736",
    "ed_fg": "#F0EEF6",
    "ed_gutter": "#14102A",
    "ed_gutter_fg": "#7C7598",
    "ed_sel": "#4A3D78",
    "ed_cursor": "#66D6DA",
    "ed_errline": "#5C1F33",
    "con_bg": "#0C0A14",
    "con_fg": "#E2F7E9",
    "con_err": "#FF8F86",
    "con_in": "#66D6DA",
    "con_info": "#C3B2D6",
    # syntax
    "syn_kw": "#66D6DA",
    "syn_str": "#F3D27A",
    "syn_com": "#8E86A8",
    "syn_num": "#FFB38A",
    "syn_builtin": "#CFC2E0",
    "syn_def": "#FFE680",
}

TIER_COLOURS = {"simple": "#0B8F96", "moderate": "#3F6FB5", "computer": "#A8521C", "advanced": "#704988", "lab": "#9A4F8F",
                "camera": "#2E7D5B"}

# The logo's pixel squares: (column, row, colour) on a grid, as in the school's logo
LOGO_SQUARES = [(1, 0, "#66D6DA"), (3, 0, "#704988"), (5, 0, "#CFC2E0"), (7, 0, "#19C1CA"),
                (0, 1, "#19C1CA"), (2, 1, "#04BBC1"), (4, 1, "#C3B2D6"), (6, 1, "#04BBC1"),
                (1, 2, "#DCD0E8"), (1, 3, "#7E5B95")]


def blend(c1: str, c2: str, t: float) -> str:
    """The colour t of the way from c1 to c2 (both '#rrggbb')."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _pick(have, wanted, fallback):
    for f in wanted:
        if f in have:
            return f
    return fallback


_FONTS = []  # keep references: a tkinter Font is deleted when garbage-collected
SCALE = {"value": 1.0}


CODE_SIZE = {"value": 12}      # the code font's starting size (a student's own size goes on top)


def setup_fonts(root, scale: float = 1.0) -> None:
    SCALE["value"] = scale
    have = set(tkfont.families(root))     # listing fonts is slow on a Pi, so do it once
    ui = _pick(have, ["DejaVu Sans", "Liberation Sans", "Nunito Sans"], "Helvetica")
    mono = _pick(have, ["DejaVu Sans Mono", "Liberation Mono", "Noto Mono"], "Courier")

    def mk(name, family, size, weight="normal", slant="roman"):
        try:
            f = tkfont.nametofont(name)
            f.configure(family=family, size=int(size * scale), weight=weight, slant=slant)
        except Exception:
            _FONTS.append(tkfont.Font(root, name=name, family=family, size=int(size * scale),
                                      weight=weight, slant=slant))

    mk("ui", ui, 11)
    mk("ui_bold", ui, 11, "bold")
    mk("ui_italic", ui, 11, slant="italic")
    mk("small", ui, 9)
    mk("small_bold", ui, 9, "bold")
    # headings in a chunky monospace, like an old computer's system font
    mk("h1", mono, 24, "bold")
    mk("h2", mono, 16, "bold")
    mk("h3", ui, 13, "bold")
    mk("title", mono, 11, "bold")        # text on title bars
    mk("big", ui, 13)
    mk("big_bold", ui, 13, "bold")
    mk("code", mono, 12)
    CODE_SIZE["value"] = int(12 * scale)
    mk("code_ui", mono, 10)
    mk("glyph", ui, 34, "bold")
    tkfont.nametofont("TkDefaultFont").configure(family=ui, size=int(11 * scale))

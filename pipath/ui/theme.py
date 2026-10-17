"""Colours and fonts. Change the look of the whole app here.

The look is classic Windows 95/98: a teal desktop, silver-grey windows with two-level bevels,
white sunken fields, gradient title bars, an editor like Visual Basic 6 and an Output box like the
MS-DOS Prompt. The title bars and accents use the Banyule Nillumbik Tech School logo's purple and
teal, and its pixel squares are LOGO_SQUARES, drawn by widgets.PixelMark.
"""
import tkinter.font as tkfont

C = {
    # desktop + windows (the Windows 95 palette)
    "desk": "#008080",          # the teal desktop behind windows
    "desk_dark": "#005A5A",
    "bg": "#C0C0C0",            # window face: silver grey (buttons, panels, bars)
    "face_hi": "#D4D0C8",       # face, hovered
    "hi": "#FFFFFF",            # bevel highlight
    "shadow": "#808080",        # bevel shadow
    "dark": "#000000",          # bevel dark edge
    "panel": "#FFFFFF",         # sunken white wells: text, lists, checklists
    "panel_alt": "#F4F4F4",
    "line": "#808080",          # dividers and outlines
    "ink": "#000000",
    "muted": "#3C3C3C",
    "faint": "#7A7A7A",
    "select": "#000080",        # selected text / list rows: Windows navy
    # logo colours
    "purple": "#704988",
    "purple_light": "#8A63A3",
    "lavender": "#CFC2E0",
    "teal": "#19C1CA",
    "teal_light": "#66D6DA",
    "title_a": "#4B2A66",       # title bars: purple → teal, like Windows 98's navy → blue
    "title_b": "#12A9B1",
    "title_off_a": "#808080",   # an inactive window's title bar
    "title_off_b": "#B5B5B5",
    # brand accent (purple) and "go" (teal)
    "accent": "#704988",
    "accent_dark": "#523468",
    "accent_soft": "#E8DFF2",
    "go": "#00807F",
    "go_dark": "#005A5A",
    # states
    "ok": "#007A3D",
    "ok_soft": "#DDF3E6",
    "warn": "#8A5200",
    "warn_soft": "#FFFFE1",     # the yellow of a Windows tooltip
    "err": "#B00000",
    "err_soft": "#FCE4E2",
    "info": "#000080",
    "info_soft": "#E6EEFF",
    "locked": "#A0A0A0",
    "tooltip": "#FFFFE1",
    # editor: white, like Visual Basic 6 / Notepad
    "ed_bg": "#FFFFFF",
    "ed_fg": "#000000",
    "ed_gutter": "#E4E4E4",
    "ed_gutter_fg": "#808080",
    "ed_sel": "#000080",
    "ed_sel_fg": "#FFFFFF",
    "ed_cursor": "#000000",
    "ed_errline": "#FFD9D9",
    # Output: the MS-DOS Prompt
    "con_bg": "#000000",
    "con_fg": "#C0C0C0",
    "con_err": "#FF5555",
    "con_in": "#FFFFFF",
    "con_info": "#55FFFF",
    "con_warn": "#FFFF55",
    # syntax (Visual Basic colours, with the logo's purple and teal)
    "syn_kw": "#0000FF",
    "syn_str": "#800080",
    "syn_com": "#008000",
    "syn_num": "#007F7F",
    "syn_builtin": "#000080",
    "syn_def": "#800000",
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

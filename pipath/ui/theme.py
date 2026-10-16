"""Colours and fonts. Change the look of the whole app here."""
import tkinter.font as tkfont

C = {
    # app chrome
    "bg": "#F4F2EC",
    "panel": "#FFFFFF",
    "panel_alt": "#FAF8F3",
    "line": "#E3DFD4",
    "ink": "#1E2330",
    "muted": "#636A78",
    "faint": "#9AA0AB",
    # brand (Raspberry red)
    "accent": "#C51A4A",
    "accent_dark": "#9C1239",
    "accent_soft": "#FBE8EE",
    # states
    "go": "#1E8A52",
    "go_dark": "#156B3E",
    "ok": "#1E7F4F",
    "ok_soft": "#E4F4EA",
    "warn": "#9A5B00",
    "warn_soft": "#FFF3DD",
    "err": "#B42318",
    "err_soft": "#FDECEA",
    "info": "#1D5FA7",
    "info_soft": "#E8F0FB",
    "locked": "#B4B0A6",
    # editor + console
    "ed_bg": "#1F232B",
    "ed_fg": "#E8E8E8",
    "ed_gutter": "#191C23",
    "ed_gutter_fg": "#666E7C",
    "ed_sel": "#3B4558",
    "ed_cursor": "#FFFFFF",
    "ed_errline": "#57202A",
    "con_bg": "#14171C",
    "con_fg": "#D9DEE5",
    "con_err": "#FF8F86",
    "con_in": "#8FDBA6",
    "con_info": "#7FA7D9",
    # syntax
    "syn_kw": "#FF7EAB",
    "syn_str": "#A8D8A0",
    "syn_com": "#7D8798",
    "syn_num": "#FFC97A",
    "syn_builtin": "#86B6FF",
    "syn_def": "#FFD866",
}

TIER_COLOURS = {"simple": "#1E8A52", "moderate": "#1D5FA7", "advanced": "#C51A4A", "lab": "#7A3EB1",
                "camera": "#0E7C86"}


def _pick(have, wanted, fallback):
    for f in wanted:
        if f in have:
            return f
    return fallback


_FONTS = []  # keep references: a tkinter Font is deleted when garbage-collected


def setup_fonts(root, scale: float = 1.0) -> None:
    have = set(tkfont.families(root))     # listing fonts is slow on a Pi, so do it once
    ui = _pick(have, ["Nunito Sans", "Nunito", "DejaVu Sans", "Liberation Sans"], "Helvetica")
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
    mk("h1", ui, 26, "bold")
    mk("h2", ui, 17, "bold")
    mk("h3", ui, 13, "bold")
    mk("big", ui, 14)
    mk("big_bold", ui, 14, "bold")
    mk("code", mono, 12)
    mk("code_ui", mono, 10)
    mk("glyph", ui, 34, "bold")
    tkfont.nametofont("TkDefaultFont").configure(family=ui, size=int(11 * scale))

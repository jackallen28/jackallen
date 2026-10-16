"""Small reusable widgets: buttons, cards, rich text."""
from __future__ import annotations

import re
import tkinter as tk

from .theme import C

BUTTON_KINDS = {
    #            bg            fg        hover            border
    "primary": (C["accent"], "#FFFFFF", C["accent_dark"], C["accent"]),
    "go": (C["go"], "#FFFFFF", C["go_dark"], C["go"]),
    "secondary": (C["panel"], C["ink"], C["panel_alt"], C["line"]),
    "ghost": (C["bg"], C["muted"], C["line"], C["bg"]),
    "dark": ("#2B303A", "#E8E8E8", "#3A404C", "#2B303A"),
    "stop": ("#2B303A", "#FF9C94", "#3A404C", "#2B303A"),
}


class PButton(tk.Label):
    """A flat button built from a Label, so it looks the same on every Pi desktop theme."""

    def __init__(self, master, text: str, command=None, kind: str = "secondary",
                 font: str = "ui_bold", padx: int = 14, pady: int = 7, **kw):
        self.kind = kind
        bg, fg, _, border = BUTTON_KINDS[kind]
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", highlightthickness=1, highlightbackground=border,
                         highlightcolor=border, **kw)
        self.command = command
        self.enabled = True
        self.bind("<Enter>", self._hover)
        self.bind("<Leave>", self._unhover)
        self.bind("<Button-1>", self._click)

    def _hover(self, _e=None):
        if self.enabled:
            self.configure(bg=BUTTON_KINDS[self.kind][2])

    def _unhover(self, _e=None):
        if self.enabled:
            self.configure(bg=BUTTON_KINDS[self.kind][0])

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        bg, fg, _, border = BUTTON_KINDS[self.kind]
        if on:
            self.configure(bg=bg, fg=fg, cursor="hand2", highlightbackground=border)
        else:
            self.configure(bg=C["line"] if self.kind not in ("dark", "stop") else "#252931",
                           fg=C["faint"] if self.kind not in ("dark", "stop") else "#5A606B",
                           cursor="arrow", highlightbackground=C["line"] if self.kind not in ("dark", "stop") else "#252931")

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.set_enabled(self.enabled)


def card(master, bg=None, border=None, padx=16, pady=14) -> tk.Frame:
    return tk.Frame(master, bg=bg or C["panel"], highlightthickness=1,
                    highlightbackground=border or C["line"], padx=padx, pady=pady)


def label(master, text="", font="ui", fg=None, bg=None, **kw) -> tk.Label:
    return tk.Label(master, text=text, font=font, fg=fg or C["ink"],
                    bg=bg if bg is not None else master.cget("bg"), anchor="w", justify="left", **kw)


def chip(master, text, fg, bg) -> tk.Label:
    return tk.Label(master, text=f" {text} ", font="small_bold", fg=fg, bg=bg, padx=4, pady=1)


class RichText(tk.Text):
    """Read-only text that understands a tiny bit of Markdown:
    ## heading,  **bold**,  *italic*,  `code`,  - bullets,  1. numbers,  ``` code blocks ```
    """

    def __init__(self, master, bg=None, fg=None, font="ui", **kw):
        bg = bg or master.cget("bg")
        # width=1: always packed with fill="x", so the panel it sits in decides the width
        super().__init__(master, bg=bg, fg=fg or C["ink"], font=font, wrap="word", relief="flat",
                         bd=0, highlightthickness=0, padx=0, pady=0, cursor="arrow",
                         spacing1=2, spacing3=4, height=kw.pop("height", 4), width=kw.pop("width", 1), **kw)
        self.tag_configure("h", font="h3", spacing1=4, spacing3=6)
        self.tag_configure("b", font="ui_bold")
        self.tag_configure("i", font="ui_italic")
        self.tag_configure("code", font="code_ui", background="#EFEBE2", foreground="#7A1531")
        # long code lines wrap (indented a little more), so nothing is cut off in a narrow panel
        self.tag_configure("block", font="code_ui", background="#262A33", foreground="#E8E8E8",
                           lmargin1=10, lmargin2=34, rmargin=6, spacing1=0, spacing3=0, wrap="word")
        self.tag_configure("bullet", lmargin1=6, lmargin2=22)
        self.configure(state="disabled")
        self._last_w = 0
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, e):
        if abs(e.width - self._last_w) > 4:
            self._last_w = e.width
            self.fit_height()

    def render(self, markup: str) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        in_block = False
        for raw in markup.strip("\n").splitlines():
            if raw.strip().startswith("```"):
                in_block = not in_block
                if in_block:
                    self.insert("end", " \n", ("block",))
                else:
                    self.insert("end", " \n", ("block",))
                continue
            if in_block:
                self.insert("end", raw + "\n", ("block",))
                continue
            if raw.startswith("## "):
                self.insert("end", raw[3:] + "\n", ("h",))
                continue
            m = re.match(r"^(\s*)(-|\d+\.)\s+(.*)$", raw)
            if m:
                marker = "•" if m.group(2) == "-" else m.group(2)
                self.insert("end", f"{marker}  ", ("bullet",))
                self._inline(m.group(3), ("bullet",))
                self.insert("end", "\n", ("bullet",))
                continue
            self._inline(raw, ())
            self.insert("end", "\n")
        # trim the trailing newline (but not a code block's: its dark background needs it)
        if self.get("end-2c", "end-1c") == "\n" and "block" not in self.tag_names("end-2c"):
            self.delete("end-2c", "end-1c")
        self.configure(state="disabled")
        self.fit_height()

    def _inline(self, text: str, base: tuple) -> None:
        for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)", text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                self.insert("end", part[2:-2], base + ("b",))
            elif part.startswith("`") and part.endswith("`") and len(part) > 1:
                self.insert("end", part[1:-1], base + ("code",))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                self.insert("end", part[1:-1], base + ("i",))
            else:
                self.insert("end", part, base)

    # Every RichText that needs measuring waits here, so one layout pass measures them all.
    # (A layout pass per widget made each step change several times slower on a Pi 3B.)
    _waiting: set = set()
    _job = None

    def fit_height(self) -> None:
        """Grow to show all lines (after layout, so wrapped lines count)."""
        RichText._waiting.add(self)
        if RichText._job is None:
            RichText._job = self._root().after_idle(RichText._fit_waiting)

    @staticmethod
    def _fit_waiting() -> None:
        RichText._job = None
        widgets = [w for w in RichText._waiting if w.winfo_exists()]
        RichText._waiting.clear()
        if not widgets:
            return
        widgets[0].update_idletasks()          # one layout pass, so every width is known
        for w in widgets:
            try:
                n = w.count("1.0", "end", "displaylines")
                n = n[0] if isinstance(n, tuple) else n
                h = max(1, int(n or 1))
                if int(w.cget("height")) != h:
                    w.configure(height=h)
            except tk.TclError:
                pass


class ScrollFrame(tk.Frame):
    """A vertically scrollable frame. Put children in .body."""

    def __init__(self, master, bg=None, **kw):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, width=12)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.body):
            w.bind("<Enter>", lambda e: self._bind_wheel(True))
            w.bind("<Leave>", lambda e: self._bind_wheel(False))

    def _bind_wheel(self, on: bool):
        if on:
            self.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
            self.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
            self.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        else:
            for seq in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
                self.unbind_all(seq)

    def to_top(self):
        self.canvas.yview_moveto(0)

    def scroll_to(self, widget, margin: int = 12):
        """Scroll so `widget` (inside .body) is visible, showing as much of it as fits."""
        def _go():
            if not widget.winfo_exists():
                return     # the step was re-drawn before we got here
            self.update_idletasks()
            total = self.body.winfo_height()
            view = self.canvas.winfo_height()
            if total <= view:
                return
            y = widget.winfo_rooty() - self.body.winfo_rooty()
            h = widget.winfo_height()
            top = y - margin if h + margin > view else y + h - view + margin
            top = max(0, min(top, total - view))
            self.canvas.yview_moveto(top / total)
        self.after(60, _go)

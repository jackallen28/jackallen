"""Small reusable widgets in the retro look: bevelled buttons, sunken wells, title bars, the
logo, choice lists, rich text and a scrolling frame."""
from __future__ import annotations

import re
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from .theme import C, LOGO_SQUARES, SCALE, blend

BRAND = Path(__file__).resolve().parent.parent.parent / "data" / "brand"

BUTTON_KINDS = {
    #             face           text       hovered face    relief
    "primary": (C["accent"], "#FFFFFF", C["purple_light"], "raised"),
    "go": (C["go"], "#FFFFFF", "#0FA3AA", "raised"),
    "secondary": (C["bg"], C["ink"], C["face_hi"], "raised"),
    "ghost": (C["bg"], C["ink"], C["face_hi"], "flat"),      # flat until the mouse is on it
    "dark": (C["bg"], C["ink"], C["face_hi"], "raised"),
    "stop": (C["bg"], C["err"], C["face_hi"], "raised"),
}
DEFAULT_KINDS = ("primary", "go")      # drawn with a black outline, like a default button


class PButton(tk.Label):
    """A bevelled push button (it presses in when clicked), built from a Label so it looks the
    same on every Pi desktop theme. The command runs when the mouse is released over it."""

    def __init__(self, master, text: str, command=None, kind: str = "secondary",
                 font: str = "ui_bold", padx: int = 14, pady: int = 6, **kw):
        self.kind = kind
        self.enabled = True
        self._ring = master.cget("bg")
        face, fg, _, relief = BUTTON_KINDS[kind]
        super().__init__(master, text=text, bg=face, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", relief=relief, bd=2, highlightthickness=1,
                         highlightbackground=self._ring_colour(), highlightcolor=self._ring_colour(), **kw)
        self.command = command
        self._down = False
        self._last = 0.0
        self.bind("<Enter>", self._hover)
        self.bind("<Leave>", self._unhover)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def _ring_colour(self) -> str:
        return "#000000" if self.kind in DEFAULT_KINDS and self.enabled else self._ring

    def _hover(self, _e=None):
        if self.enabled:
            self.configure(bg=BUTTON_KINDS[self.kind][2], relief="sunken" if self._down else "raised")

    def _unhover(self, _e=None):
        if self.enabled:
            face, _fg, _hover, relief = BUTTON_KINDS[self.kind]
            self.configure(bg=face, relief=relief)

    def _press(self, _e=None):
        if self.enabled:
            self._down = True
            self.configure(relief="sunken")

    def _release(self, e=None):
        was_down, self._down = self._down, False
        if not self.enabled:
            return
        inside = e is None or (0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height())
        self.configure(relief="raised" if inside else BUTTON_KINDS[self.kind][3])
        if was_down and inside and self.command and time.monotonic() - self._last > 0.35:
            self._last = time.monotonic()        # a double-click is one press (a hint, a step, Finish)
            self.command()

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        face, fg, _hover, relief = BUTTON_KINDS[self.kind]
        if on:
            self.configure(bg=face, fg=fg, cursor="hand2", relief=relief)
        else:
            self.configure(bg=C["bg"] if self.kind in DEFAULT_KINDS else face, fg=C["faint"], cursor="arrow",
                           relief=relief)
        ring = self._ring_colour()
        self.configure(highlightbackground=ring, highlightcolor=ring)

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.set_enabled(self.enabled)


def logo_image(widget, name: str) -> tk.PhotoImage | None:
    """One of the logo images in data/brand (cached for the window; None if it can't load)."""
    root = widget.winfo_toplevel()
    cache = root.__dict__.setdefault("_pipath_images", {})
    if name not in cache:
        try:
            cache[name] = tk.PhotoImage(master=root, file=str(BRAND / f"{name}.png"))
        except (tk.TclError, OSError):
            cache[name] = None
    return cache[name]


def corner_logo_name() -> str:
    return "logo_corner_66" if SCALE["value"] >= 1.4 else "logo_corner_44"


class PixelMark(tk.Canvas):
    """The logo's pixel squares, drawn (sharp at any size)."""

    def __init__(self, master, cell: int = 8, bg: str | None = None, rows: int = 4):
        super().__init__(master, width=8 * cell, height=rows * cell, bg=bg or master.cget("bg"),
                         highlightthickness=0, bd=0)
        for col, row, colour in LOGO_SQUARES:
            if row < rows:
                self.create_rectangle(col * cell, row * cell, (col + 1) * cell, (row + 1) * cell,
                                      fill=colour, outline="")


def bevel(canvas, x0, y0, x1, y1, fill, sunken=False, tags=()):
    """A Windows 95 bevelled box on a canvas: light on the top-left edges, dark on the bottom-right."""
    dark = blend(fill, "#000000", .45)
    hi, lo = ("#FFFFFF", dark) if not sunken else (dark, "#FFFFFF")
    canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="", tags=tags)
    canvas.create_line(x0, y1 - 1, x0, y0, x1 - 1, y0, fill=hi, width=2, tags=tags)
    canvas.create_line(x0, y1 - 1, x1 - 1, y1 - 1, x1 - 1, y0, fill=lo, width=2, tags=tags)


class TitleBar(tk.Canvas):
    """A Windows-95-style title bar: a purple → teal gradient with bold white text. Optional logo
    plaque in the left corner, and widgets on the right (add_right)."""

    def __init__(self, master, text: str = "", height: int = 26, logo: bool = False, font: str = "title",
                 colours: tuple[str, str] | None = None, sub: str = ""):
        colours = colours or (C["title_a"], C["title_b"])
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=colours[0])
        self.colours = colours
        self.text, self.sub, self.font, self.logo = text, sub, font, logo
        self._right: list[tuple[tk.Widget, int]] = []
        self._drawn_w = 0
        self.bind("<Configure>", self._redraw)

    def set_text(self, text: str, sub: str | None = None) -> None:
        self.text = text
        if sub is not None:
            self.sub = sub
        self.itemconfigure("title", text=self.text)
        self.itemconfigure("sub", text=self.sub)
        self._layout()

    def add_right(self, widget: tk.Widget, pad: int = 6) -> tk.Widget:
        self._right.append((widget, pad))
        self.create_window(0, 0, window=widget, anchor="e", tags=(f"w{len(self._right)}",))
        self._layout()
        return widget

    def _layout(self) -> None:
        x = self.winfo_width() - 6
        h = int(self.cget("height"))
        for i, (widget, pad) in enumerate(self._right, start=1):
            self.coords(f"w{i}", x, h // 2)
            x -= widget.winfo_reqwidth() + pad
        self._fit_text(x)

    def _fit_text(self, right: int) -> None:
        """Shorten the title and subtitle with … so they never run under the buttons on the right."""
        for tag, full, font in (("title", self.text, self.font), ("sub", self.sub, "small")):
            items = self.find_withtag(tag)
            if not items or right <= 0:
                continue
            room = right - self.coords(items[0])[0] - 12
            f = tkfont.nametofont(font)
            text = full
            if f.measure(text) > room:
                while text and f.measure(text + "…") > room:
                    text = text[:-1]
                text = text.rstrip() + "…" if text else ""
            if self.itemcget(items[0], "text") != text:
                self.itemconfigure(items[0], text=text)

    def _redraw(self, _e=None) -> None:
        w, h = self.winfo_width(), int(self.cget("height"))
        if w != self._drawn_w:
            self._drawn_w = w
            self.delete("grad")
            steps = 28
            a, b = self.colours
            for i in range(steps):
                self.create_rectangle(w * i // steps, 0, w * (i + 1) // steps + 1, h,
                                      fill=blend(a, b, i / (steps - 1)), outline="", tags="grad")
            self.tag_lower("grad")
        if not self.find_withtag("title"):
            x = 10
            img = logo_image(self, corner_logo_name()) if self.logo else None
            if img is not None:
                pw, ph = img.width() + 14, min(h - 6, img.height() + 6)
                bevel(self, 4, (h - ph) // 2, 4 + pw, (h - ph) // 2 + ph, "#FFFFFF", tags=("plaque",))
                self.create_image(4 + pw // 2, h // 2, image=img, tags=("plaque",))
                x = 4 + pw + 14
            self.create_text(x, h // 2 - (8 if self.sub else 0), anchor="w", text=self.text, fill="#FFFFFF",
                             font=self.font, tags=("title",))
            self.create_text(x, h // 2 + 11, anchor="w", text=self.sub, fill="#EDE8F5", font="small",
                             tags=("sub",))
        self._layout()


class CogButton(tk.Frame):
    """The settings button: a pixel-art cog and the word Settings, on a bevelled button."""

    COG = ["....XX....", ".X.XXXX.X.", "..XXXXXX..", ".XXX..XXX.", "XXX....XXX",
           "XXX....XXX", ".XXX..XXX.", "..XXXXXX..", ".X.XXXX.X.", "....XX...."]

    def __init__(self, master, command, text: str = "Settings"):
        super().__init__(master, bg=C["bg"], relief="raised", bd=2, cursor="hand2", padx=6, pady=3)
        self.command = command
        px = 2
        cv = tk.Canvas(self, width=10 * px, height=10 * px, bg=C["bg"], highlightthickness=0, bd=0)
        for y, row in enumerate(self.COG):
            for x, ch in enumerate(row):
                if ch == "X":
                    cv.create_rectangle(x * px, y * px, (x + 1) * px, (y + 1) * px, fill=C["purple"], outline="")
        cv.pack(side="left")
        lbl = tk.Label(self, text=text, font="small_bold", bg=C["bg"], fg=C["ink"])
        lbl.pack(side="left", padx=(5, 0))
        self._parts = (self, cv, lbl)
        for w in self._parts:
            w.bind("<ButtonPress-1>", lambda e: self.configure(relief="sunken"))
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Enter>", lambda e: [p.configure(bg=C["face_hi"]) for p in self._parts])
            w.bind("<Leave>", lambda e: [p.configure(bg=C["bg"]) for p in self._parts])

    def _release(self, e):
        self.configure(relief="raised")
        x, y = e.x_root - self.winfo_rootx(), e.y_root - self.winfo_rooty()
        if 0 <= x < self.winfo_width() and 0 <= y < self.winfo_height():
            self.command()


class ChoiceList(tk.Frame):
    """Radio-button choices, retro style: a sunken circle that fills in. options = [(key, title, text)]."""

    def __init__(self, master, options: list, value: str, on_change=None, columns: int = 1,
                 bg: str | None = None, wrap: int = 320):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.value, self.on_change, self.rows = value, on_change, {}
        for i, (key, title, text) in enumerate(options):
            row = tk.Frame(self, bg=bg, cursor="hand2", padx=4, pady=3)
            row.grid(row=i // columns, column=i % columns, sticky="nw", padx=(0, 10), pady=1)
            dot = tk.Canvas(row, width=16, height=16, bg=bg, highlightthickness=0, bd=0)
            dot.create_oval(1, 1, 15, 15, fill="#FFFFFF", outline=C["line"], width=2)
            dot.create_oval(5, 5, 11, 11, fill="", outline="", tags="on")
            dot.pack(side="left", anchor="n", pady=2)
            words = tk.Frame(row, bg=bg)
            words.pack(side="left", padx=(6, 0))
            t = tk.Label(words, text=title, font="ui_bold", bg=bg, fg=C["ink"], anchor="w", justify="left")
            t.pack(anchor="w")
            parts = [row, dot, words, t]
            if text:
                d = tk.Label(words, text=text, font="small", bg=bg, fg=C["muted"], anchor="w", justify="left",
                             wraplength=wrap)
                d.pack(anchor="w")
                parts.append(d)
            for w in parts:
                w.bind("<Button-1>", lambda e, k=key: self.set(k))
            self.rows[key] = (row, dot, t)
        self._paint()

    def set(self, key: str) -> None:
        if key != self.value:
            self.value = key
            self._paint()
            if self.on_change:
                self.on_change(key)

    def _paint(self) -> None:
        for key, (_row, dot, t) in self.rows.items():
            on = key == self.value
            dot.itemconfigure("on", fill=C["purple"] if on else "")
            t.configure(fg=C["purple"] if on else C["ink"])


def entry(master, width: int = 30, font: str = "big", **kw) -> tk.Entry:
    """A sunken white text box."""
    return tk.Entry(master, font=font, width=width, relief="sunken", bd=2, bg="#FFFFFF", fg=C["ink"],
                    insertbackground=C["ink"], highlightthickness=1, highlightbackground=master.cget("bg"),
                    highlightcolor=C["accent"], disabledbackground=C["panel_alt"], **kw)


class PopupMenu(tk.Frame):
    """A right-click menu drawn inside the main window with place() (never a separate window,
    so it behaves the same on X11 and Wayland). One per window: PopupMenu.of(widget).show(...)."""

    @classmethod
    def of(cls, widget) -> "PopupMenu":
        root = widget.winfo_toplevel()
        menu = getattr(root, "_pipath_popup", None)
        if menu is None or not menu.winfo_exists():
            menu = root._pipath_popup = cls(root)
        return menu

    def __init__(self, root):
        super().__init__(root, bg=C["bg"], relief="raised", bd=2, padx=2, pady=2)
        self.visible = False
        # a click anywhere else (or Escape) closes it; bound once, for the life of the window
        root.bind("<ButtonPress>", self._outside, add="+")
        root.bind("<Escape>", lambda e: self.hide(), add="+")

    def show(self, items: list, x_root: int, y_root: int) -> None:
        """items: (label, shortcut or "", command, enabled) tuples, or None for a divider."""
        for w in self.winfo_children():
            w.destroy()
        for item in items:
            if item is None:
                tk.Frame(self, bg=C["bg"], height=2, relief="sunken", bd=1).pack(fill="x", pady=3, padx=2)
                continue
            text, accel, command, enabled = item
            fg = C["ink"] if enabled else C["faint"]
            row = tk.Frame(self, bg=C["bg"], padx=10, pady=3, cursor="hand2" if enabled else "")
            row.pack(fill="x")
            parts = [tk.Label(row, text=text, font="small", fg=fg, bg=C["bg"], anchor="w")]
            parts[0].pack(side="left")
            if accel:
                parts.append(tk.Label(row, text=accel, font="small", fg=C["muted"] if enabled else C["faint"],
                                      bg=C["bg"]))
                parts[1].pack(side="right", padx=(24, 0))
            if enabled:
                widgets = [row, *parts]
                for w in widgets:      # the Windows 95 menu highlight, in the logo purple
                    w.bind("<Enter>", lambda e, ws=widgets: self._light(ws, True))
                    w.bind("<Leave>", lambda e, ws=widgets: self._light(ws, False))
                    w.bind("<ButtonRelease-1>", lambda e, c=command: (self.hide(), c()))
        root = self.master
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = min(x_root - root.winfo_rootx(), root.winfo_width() - w - 4)
        y = min(y_root - root.winfo_rooty(), root.winfo_height() - h - 4)
        self.place(x=max(0, x), y=max(0, y))
        self.lift()
        self.visible = True

    @staticmethod
    def _light(widgets, on: bool) -> None:
        for w in widgets:
            w.configure(bg=C["purple"] if on else C["bg"])
            if isinstance(w, tk.Label):
                w.configure(fg="#FFFFFF" if on else C["ink"])

    def hide(self) -> None:
        if self.visible:
            self.visible = False
            self.place_forget()

    def _outside(self, e) -> None:
        if not self.visible:
            return
        w = e.widget if isinstance(e.widget, tk.Misc) else None
        while w is not None:
            if w is self:
                return          # a click on the menu itself: the row handles it
            w = w.master
        self.hide()


def card(master, bg=None, border=None, padx=16, pady=14, relief="sunken") -> tk.Frame:
    """A panel: by default a sunken white well (like a Windows 95 list box); relief="raised" for a
    bevelled panel. border: a coloured outline instead of the bevel."""
    if border:
        return tk.Frame(master, bg=bg or C["panel"], highlightthickness=2, highlightbackground=border,
                        highlightcolor=border, padx=padx, pady=pady)
    return tk.Frame(master, bg=bg or C["panel"], relief=relief, bd=2, padx=padx, pady=pady)


def window(master, title: str, padx=18, pady=14, bg=None) -> tuple[tk.Frame, tk.Frame]:
    """A retro window: a raised frame with a gradient title bar. Returns (window, body)."""
    win = tk.Frame(master, bg=bg or C["bg"], relief="raised", bd=2)
    TitleBar(win, title, height=24).pack(fill="x", padx=1, pady=(1, 0))
    body = tk.Frame(win, bg=bg or C["bg"], padx=padx, pady=pady)
    body.pack(fill="both", expand=True)
    return win, body


def label(master, text="", font="ui", fg=None, bg=None, **kw) -> tk.Label:
    return tk.Label(master, text=text, font=font, fg=fg or C["ink"],
                    bg=bg if bg is not None else master.cget("bg"), anchor="w", justify="left", **kw)


def chip(master, text, fg, bg) -> tk.Label:
    return tk.Label(master, text=f" {text} ", font="small_bold", fg=fg, bg=bg, padx=4, pady=1,
                    relief="raised", bd=1)


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
        self.tag_configure("code", font="code_ui", background="#E8DFF2", foreground="#4F2C68")
        # long code lines wrap (indented a little more), so nothing is cut off in a narrow panel
        self.tag_configure("block", font="code_ui", background=C["ed_bg"], foreground=C["ed_fg"],
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
                self._styled(part[2:-2], base + ("b",))
            elif part.startswith("`") and part.endswith("`") and len(part) > 1:
                self.insert("end", part[1:-1], base + ("code",))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                self._styled(part[1:-1], base + ("i",))
            else:
                self.insert("end", part, base)

    def _styled(self, inner: str, tags: tuple) -> None:
        """Bold or italic text, which can hold `code` of its own."""
        if "`" in inner:
            self._inline(inner, tags)
        else:
            self.insert("end", inner, tags)

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

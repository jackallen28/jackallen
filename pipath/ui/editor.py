"""A beginner-friendly code editor: line numbers, colours, 4-space tabs, auto-indent."""
from __future__ import annotations

import bisect
import keyword
import re
import tkinter as tk
import tkinter.font as tkfont

from .theme import C

BUILTINS = ["print", "input", "int", "float", "str", "len", "range", "list", "dict", "round",
            "abs", "min", "max", "sum", "sorted", "type", "bool", "open", "enumerate", "zip"]

_KW = r"\b(?P<KEYWORD>" + "|".join(keyword.kwlist) + r")\b"
_BUILTIN = r"(?<![.\w])(?P<BUILTIN>" + "|".join(BUILTINS) + r")(?=\s*\()"
_COMMENT = r"(?P<COMMENT>#[^\n]*)"
_STRING = (r"(?P<STRING>(?:\b[rRbBfFuU]{1,2})?(?:'''[\s\S]*?(?:'''|\Z)|\"\"\"[\s\S]*?(?:\"\"\"|\Z)"
           r"|'[^'\\\n]*(?:\\.[^'\\\n]*)*'?|\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\"?))")
_NUMBER = r"(?<![\w.])(?P<NUMBER>\d+(?:\.\d+)?)\b"
_DEF = r"(?:(?<=\bdef )|(?<=\bclass ))(?P<DEF>\w+)"
PATTERN = re.compile("|".join([_STRING, _COMMENT, _KW, _BUILTIN, _NUMBER, _DEF]))
TAGS = {"KEYWORD": "syn_kw", "STRING": "syn_str", "COMMENT": "syn_com", "NUMBER": "syn_num",
        "BUILTIN": "syn_builtin", "DEF": "syn_def"}


class CodeEditor(tk.Frame):
    def __init__(self, master, on_change=None):
        super().__init__(master, bg=C["ed_bg"])
        self.on_change = on_change
        self._hl_job = None
        self._gutter_job = None
        self._suspend = False

        self.gutter = tk.Canvas(self, width=46, bg=C["ed_gutter"], highlightthickness=0, bd=0)
        self.text = tk.Text(
            self, wrap="none", undo=True, maxundo=-1, autoseparators=True,
            font="code", bg=C["ed_bg"], fg=C["ed_fg"], insertbackground=C["ed_cursor"],
            insertwidth=2, selectbackground=C["ed_sel"], selectforeground=C["ed_fg"],
            relief="flat", bd=0, highlightthickness=0, padx=10, pady=8, spacing1=2, spacing3=2,
        )
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self._yview, width=12)
        self.hsb = tk.Scrollbar(self, orient="horizontal", command=self.text.xview, width=12)
        self.text.configure(yscrollcommand=self._on_yscroll, xscrollcommand=self.hsb.set)

        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vsb.grid(row=0, column=2, sticky="ns")
        self.hsb.grid(row=1, column=1, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        for tag, colour in TAGS.items():
            self.text.tag_configure(colour, foreground=C[colour])
        self.text.tag_configure("errline", background=C["ed_errline"])
        self.text.tag_configure("blank", background="#5C4A12", foreground="#FFE08A")
        self.text.tag_raise("sel")
        self._set_tabs()

        t = self.text
        t.bind("<Tab>", self._tab)
        t.bind("<Shift-Tab>", self._dedent)
        t.bind("<ISO_Left_Tab>", self._dedent)
        t.bind("<Return>", self._newline)
        t.bind("<KP_Enter>", self._newline)
        t.bind("<BackSpace>", self._backspace)
        t.bind("<Control-slash>", self._toggle_comment)
        t.bind("<Control-equal>", lambda e: self.zoom(1))
        t.bind("<Control-plus>", lambda e: self.zoom(1))
        t.bind("<Control-minus>", lambda e: self.zoom(-1))
        t.bind("<<Modified>>", self._modified)
        t.bind("<Configure>", lambda e: self._draw_gutter())
        t.bind("<KeyRelease>", lambda e: self._draw_gutter())
        # Pasting curly quotes from documents is a classic beginner trap: straighten them
        t.bind("<<Paste>>", self._paste)

    def destroy(self):
        for job in (self._hl_job, self._gutter_job):
            if job:
                self.after_cancel(job)
        super().destroy()

    # ---------------------------------------------------------------- public
    def get_code(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set_code(self, code: str) -> None:
        self._suspend = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", code)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self._suspend = False
        self.clear_marks()
        self.highlight()
        self.text.mark_set("insert", "end-1c")
        self.text.see("insert")

    def append_code(self, code: str) -> None:
        cur = self.get_code().rstrip("\n")
        self.set_code((cur + "\n" if cur else "") + code)

    def mark_error_line(self, line: int | None) -> None:
        self.text.tag_remove("errline", "1.0", "end")
        if line:
            self.text.tag_add("errline", f"{line}.0", f"{line}.0 lineend+1c")
            self.text.see(f"{line}.0")
        self._error_line = line
        self._draw_gutter()

    def clear_marks(self) -> None:
        self._error_line = None
        self.text.tag_remove("errline", "1.0", "end")
        self._draw_gutter()

    def focus(self):
        self.text.focus_set()

    def zoom(self, step: int):
        f = tkfont.nametofont("code")
        size = max(9, min(26, f.cget("size") + step))
        f.configure(size=size)
        self._set_tabs()
        self._draw_gutter()
        return "break"

    # ---------------------------------------------------------------- highlighting
    def highlight(self) -> None:
        self._hl_job = None
        code = self.get_code()
        t = self.text
        for tag in list(TAGS.values()) + ["blank"]:
            t.tag_remove(tag, "1.0", "end")
        starts = [0]
        for m in re.finditer("\n", code):
            starts.append(m.end())

        def idx(pos):
            ln = bisect.bisect_right(starts, pos) - 1
            return f"{ln + 1}.{pos - starts[ln]}"

        for m in PATTERN.finditer(code):
            kind = m.lastgroup
            if kind:
                t.tag_add(TAGS[kind], idx(m.start(kind)), idx(m.end(kind)))
        for m in re.finditer(r"_{3,}", code):
            t.tag_add("blank", idx(m.start()), idx(m.end()))

    def _schedule_highlight(self):
        if self._hl_job:
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(150, self.highlight)

    # ---------------------------------------------------------------- gutter
    def _yview(self, *args):
        self.text.yview(*args)
        self._draw_gutter()

    def _on_yscroll(self, first, last):
        self.vsb.set(first, last)
        self._draw_gutter()

    def _draw_gutter(self):
        """Redraw line numbers once the current burst of keys / scrolling is over."""
        if self._gutter_job is None:
            self._gutter_job = self.after_idle(self._draw_gutter_now)

    def _draw_gutter_now(self):
        self._gutter_job = None
        g = self.gutter
        g.delete("all")
        err = getattr(self, "_error_line", None)
        i = self.text.index("@0,0")
        while True:
            d = self.text.dlineinfo(i)
            if d is None:
                break
            n = int(i.split(".")[0])
            y = d[1]
            if n == err:
                g.create_rectangle(0, y, 46, y + d[3], fill=C["accent"], outline="")
                g.create_text(40, y + d[3] // 2, anchor="e", text=str(n), fill="#FFFFFF", font="code_ui")
            else:
                g.create_text(40, y + d[3] // 2, anchor="e", text=str(n), fill=C["ed_gutter_fg"], font="code_ui")
            nxt = self.text.index(f"{i}+1line")
            if nxt == i:
                break
            i = nxt

    def _set_tabs(self):
        w = tkfont.nametofont("code").measure("    ")
        self.text.configure(tabs=(w,))

    # ---------------------------------------------------------------- editing helpers
    def _modified(self, _e=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            if not self._suspend:
                if getattr(self, "_error_line", None):
                    self.clear_marks()
                self._schedule_highlight()
                self._draw_gutter()
                if self.on_change:
                    self.on_change()

    def _tab(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            first = int(t.index("sel.first").split(".")[0])
            last = int(t.index("sel.last").split(".")[0])
            for ln in range(first, last + 1):
                t.insert(f"{ln}.0", "    ")
        else:
            t.insert("insert", "    ")
        return "break"

    def _dedent(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            first = int(t.index("sel.first").split(".")[0])
            last = int(t.index("sel.last").split(".")[0])
        else:
            first = last = int(t.index("insert").split(".")[0])
        for ln in range(first, last + 1):
            line = t.get(f"{ln}.0", f"{ln}.end")
            n = len(line) - len(line.lstrip(" "))
            if n:
                t.delete(f"{ln}.0", f"{ln}.{min(4, n)}")
        return "break"

    def _newline(self, _e):
        t = self.text
        line = t.get("insert linestart", "insert")
        indent = re.match(r"[ \t]*", line).group(0)
        if line.split("#")[0].rstrip().endswith(":"):
            indent += "    "
        t.edit_separator()
        t.insert("insert", "\n" + indent)
        t.see("insert")
        return "break"

    def _backspace(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            return None
        before = t.get("insert linestart", "insert")
        if before and before.strip() == "" and len(before) >= 4 and len(before) % 4 == 0:
            t.delete("insert-4c", "insert")
            return "break"
        return None

    def _toggle_comment(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            first = int(t.index("sel.first").split(".")[0])
            last = int(t.index("sel.last").split(".")[0])
        else:
            first = last = int(t.index("insert").split(".")[0])
        lines = [t.get(f"{ln}.0", f"{ln}.end") for ln in range(first, last + 1)]
        uncomment = all(l.lstrip().startswith("#") or not l.strip() for l in lines)
        for ln, l in zip(range(first, last + 1), lines):
            if uncomment:
                m = re.match(r"(\s*)# ?", l)
                if m and l.strip():
                    t.delete(f"{ln}.{len(m.group(1))}", f"{ln}.{m.end()}")
            elif l.strip():
                n = len(l) - len(l.lstrip())
                t.insert(f"{ln}.{n}", "# ")
        return "break"

    def _paste(self, _e):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return "break"
        fixed = (clip.replace("“", '"').replace("”", '"')
                     .replace("‘", "'").replace("’", "'").replace("\t", "    "))
        t = self.text
        if t.tag_ranges("sel"):
            t.delete("sel.first", "sel.last")
        t.insert("insert", fixed)
        return "break"

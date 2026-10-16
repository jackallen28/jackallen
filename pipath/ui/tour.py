"""Coach-mark tour: highlights one part of the screen at a time with a speech bubble.

Drawn inside the main window with place(), so it works the same under X11 and
Wayland (no floating windows needed).
"""
from __future__ import annotations

import tkinter as tk

from .theme import C
from .widgets import PButton, RichText, label

BORDER = 4


class Tour:
    def __init__(self, root: tk.Misc, steps: list[dict], on_done=None):
        """steps: [{"widget": w, "title": str, "text": markdown, "side": "right|left|top|bottom|center"}]"""
        self.root = root
        self.steps = steps
        self.on_done = on_done
        self.i = 0
        self.frames = [tk.Frame(root, bg=C["syn_def"]) for _ in range(4)]
        self.bubble = tk.Frame(root, bg=C["ink"], padx=18, pady=14, highlightthickness=0)
        self.counter = label(self.bubble, font="small_bold", fg=C["syn_def"], bg=C["ink"])
        self.counter.pack(anchor="w")
        self.title = label(self.bubble, font="h3", fg="#FFFFFF", bg=C["ink"])
        self.title.pack(anchor="w", pady=(2, 6))
        self.body = RichText(self.bubble, bg=C["ink"], fg="#E9EBEF", width=38)
        self.body.tag_configure("code", background="#363C49", foreground="#FFD866")
        self.body.pack(anchor="w", fill="x")
        row = tk.Frame(self.bubble, bg=C["ink"])
        row.pack(fill="x", pady=(12, 0))
        self.skip = PButton(row, "Skip tour", self.finish, kind="dark", font="small_bold", pady=5)
        self.skip.pack(side="left")
        self.next = PButton(row, "Next ▸", self.forward, kind="primary", pady=5)
        self.next.pack(side="right")
        self.back = PButton(row, "◂ Back", self.backward, kind="dark", font="small_bold", pady=5)
        self.back.pack(side="right", padx=6)
        root.bind("<Configure>", self._relayout, add="+")
        self.bubble.bind("<Configure>", self._relayout)

    def start(self):
        self.i = 0
        self.root.after(120, self._show)

    def forward(self):
        if self.i < len(self.steps) - 1:
            self.i += 1
            self._show()
        else:
            self.finish()

    def backward(self):
        if self.i > 0:
            self.i -= 1
            self._show()

    def finish(self):
        for f in self.frames:
            f.destroy()
        self.bubble.destroy()
        self.steps = []
        if self.on_done:
            self.on_done()

    def _relayout(self, _e=None):
        if self.steps and self.bubble.winfo_exists():
            self.root.after_idle(self._place)

    def _show(self):
        s = self.steps[self.i]
        self.counter.configure(text=f"TOUR  {self.i + 1} / {len(self.steps)}")
        self.title.configure(text=s["title"])
        self.body.render(s["text"])
        self.back.set_enabled(self.i > 0)
        self.next.configure(text="Let's go! ▸" if self.i == len(self.steps) - 1 else "Next ▸")
        self._place()

    def _place(self):
        if not self.steps:
            return
        s = self.steps[self.i]
        r = self.root
        r.update_idletasks()
        rw, rh = r.winfo_width(), r.winfo_height()
        w = s.get("widget")
        if w is None or s.get("side") == "center":
            for f in self.frames:
                f.place_forget()
            bw, bh = self.bubble.winfo_reqwidth(), self.bubble.winfo_reqheight()
            self.bubble.place(x=(rw - bw) // 2, y=(rh - bh) // 2)
            self.bubble.lift()
            return
        x = w.winfo_rootx() - r.winfo_rootx()
        y = w.winfo_rooty() - r.winfo_rooty()
        ww, wh = w.winfo_width(), w.winfo_height()
        # highlight box
        top, bottom, left, right = self.frames
        top.place(x=x - BORDER, y=y - BORDER, width=ww + 2 * BORDER, height=BORDER)
        bottom.place(x=x - BORDER, y=y + wh, width=ww + 2 * BORDER, height=BORDER)
        left.place(x=x - BORDER, y=y, width=BORDER, height=wh)
        right.place(x=x + ww, y=y, width=BORDER, height=wh)
        for f in self.frames:
            f.lift()
        # bubble beside it
        self.bubble.update_idletasks()
        bw, bh = self.bubble.winfo_reqwidth(), self.bubble.winfo_reqheight()
        gap = 14
        side = s.get("side", "right")
        if side == "right":
            bx, by = x + ww + gap, y + 10
        elif side == "left":
            bx, by = x - bw - gap, y + 10
        elif side == "bottom":
            bx, by = x + 10, y + wh + gap
        elif side == "inside":
            bx, by = x + ww - bw - 16, y + 16
        else:  # top
            bx, by = x + 10, y - bh - gap
        bx = max(8, min(bx, rw - bw - 8))
        by = max(8, min(by, rh - bh - 8))
        self.bubble.place(x=bx, y=by)
        self.bubble.lift()

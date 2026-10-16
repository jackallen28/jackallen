"""The on-screen board: LEDs, buttons, buzzers and sensors drawn on a Canvas.

Simulator mode: it *is* the hardware. Click (and hold) a button to press it.
Real Pi mode: it mirrors what the program is telling the real pins to do, so students
can compare "what my code says" with "what my breadboard does".
"""
from __future__ import annotations

import tkinter as tk

from ..gpio import BOARD_KIND, INPUT_KINDS
from .theme import C
from .widgets import PButton

BG = "#17261E"          # dark circuit-board green
HOLE = "#22382C"
INK = "#DCE7DF"
MUTED = "#8FA597"
LED_COLOURS = {
    "red": "#FF3B30", "amber": "#FFB000", "yellow": "#FFE14D", "orange": "#FF8A00",
    "green": "#2ED158", "blue": "#3B82F6", "white": "#F5F5F5",
}
PIR_HOLD_MS = 3000      # a real HC-SR501 holds its output high for a few seconds


def _mix(c1: str, c2: str, t: float) -> str:
    """Blend two #RRGGBB colours (t=0 -> c1, t=1 -> c2)."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class VirtualBoard(tk.Frame):
    def __init__(self, master, on_press=None, on_release=None, on_goal=None):
        super().__init__(master, bg=BG)
        self.on_press, self.on_release, self.on_goal = on_press, on_release, on_goal
        self.mode = "sim"
        self.parts: list[dict] = []        # from the lesson's [[wiring]] rows
        self.live: list[dict] = []         # devices the running program actually made
        self.values: dict[int, float] = {}
        self.items: list[tuple[dict, dict]] = []
        self.held: set[int] = set()
        self._pir_jobs: dict[int, str] = {}
        self._redraw_job = None

        head = tk.Frame(self, bg="#1B1F26")
        head.pack(fill="x")
        tk.Label(head, text="BOARD", font="small_bold", fg="#8B93A1", bg="#1B1F26", padx=12, pady=5).pack(side="left")
        self.mode_lbl = tk.Label(head, text="", font="small_bold", fg="#FFFFFF", padx=6)
        self.mode_lbl.pack(side="left")
        self.goal_btn = PButton(head, "Watch the goal  ▶", self._goal, kind="dark", font="small_bold", padx=10, pady=2)
        self._status_text = ""
        self._status_id = None
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, height=150)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._schedule_redraw())
        self.canvas.bind("<ButtonRelease-1>", self._release_all)
        self.set_mode("sim")

    # ---------------------------------------------------------------- public
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "sim":
            self.mode_lbl.configure(text=" SIMULATOR ", bg=C["go"])
            self.set_status("Click a button to press it")
        else:
            self.mode_lbl.configure(text=" REAL PI ", bg=C["info"])
            self.set_status("Shows what your code is doing")
        self._schedule_redraw()

    def set_status(self, text: str) -> None:
        """A short hint in the corner of the board."""
        self._status_text = text
        if self._status_id is not None:
            self.canvas.itemconfigure(self._status_id, text=text)

    def show_goal_button(self, on: bool) -> None:
        if on:
            self.goal_btn.pack(side="left", padx=8, pady=2, after=self.mode_lbl)
        else:
            self.goal_btn.pack_forget()

    def set_parts(self, parts: list[dict]) -> None:
        self.parts = parts
        self._schedule_redraw()

    def set_devices(self, devices: list[dict]) -> None:
        live = [{"kind": BOARD_KIND.get(d["kind"], "led"), "pins": d["pins"], "class": d["kind"]} for d in devices]
        if live != self.live:
            self.live = live
            self._schedule_redraw()

    def set_values(self, values: dict) -> None:
        self.values = {int(k): float(v) for k, v in values.items()}
        self._paint()

    def reset(self) -> None:
        """Program finished or a new run is starting: everything off, keep the lesson's layout."""
        self.values = {}
        self.live = []
        self.held.clear()
        for job in self._pir_jobs.values():
            self.after_cancel(job)
        self._pir_jobs.clear()
        self._schedule_redraw()

    def has_devices(self) -> bool:
        return bool(self.parts or self.live)

    # ---------------------------------------------------------------- layout
    def _layout(self) -> list[dict]:
        """Lesson parts first (in wiring order), then anything else the program made."""
        out = [dict(p) for p in self.parts]
        by_pin = {p["pins"][0]: p for p in out}
        for d in self.live:
            p = by_pin.get(d["pins"][0])
            if p is not None:
                if p["kind"] != d["kind"] and not (p["kind"] == "switch" and d["kind"] == "button"):
                    p.update(kind=d["kind"], label=d["class"])
                p["pins"] = d["pins"]
            else:
                out.append({"kind": d["kind"], "pins": d["pins"], "label": d["class"],
                            "colour": "red"})
        return out

    def _schedule_redraw(self) -> None:
        if self._redraw_job is None:
            self._redraw_job = self.after_idle(self._redraw)

    def _redraw(self) -> None:
        self._redraw_job = None
        cv = self.canvas
        cv.delete("all")
        self.items = []
        w, h = max(cv.winfo_width(), 100), max(cv.winfo_height(), 80)
        for x in range(10, w, 18):
            for y in range(10, h, 18):
                cv.create_rectangle(x, y, x + 2, y + 2, fill=HOLE, outline="")
        self._status_id = cv.create_text(10, 6, anchor="nw", text=self._status_text, fill=MUTED, font="small")
        top = 22
        h -= top
        parts = self._layout()
        if not parts:
            cv.create_text(w // 2, h // 2, text="Make an LED or a Button in your code\nand it will appear here.",
                           fill=MUTED, font="small", justify="center")
            return
        n = len(parts)
        best = (0, 1)
        for cols in range(1, n + 1):
            rows = -(-n // cols)
            size = min(w / cols, h / rows / 1.25)
            if size > best[0]:
                best = (size, cols)
        size, cols = best
        size = min(size, 130)
        rows = -(-n // cols)
        x0 = (w - cols * size) / 2
        y0 = top + (h - rows * size * 1.25) / 2
        for i, p in enumerate(parts):
            r, c = divmod(i, cols)
            cx = x0 + (c + .5) * size
            cy = y0 + r * size * 1.25 + size * .45
            self.items.append((p, self._draw(p, cx, cy, size)))
        self._paint()

    # ---------------------------------------------------------------- drawing
    def _draw(self, p: dict, cx: float, cy: float, s: float) -> dict:
        cv = self.canvas
        k = p["kind"]
        r = s * .17
        ids: dict = {}
        tag = f"in{p['pins'][0]}"
        if k in ("led", "rgbled"):
            ids["glow"] = cv.create_oval(cx - r * 1.9, cy - r * 1.9, cx + r * 1.9, cy + r * 1.9, fill=BG, outline="")
            cv.create_line(cx - r * .4, cy + r, cx - r * .4, cy + r * 2.0, fill="#9AA3A8", width=2)
            cv.create_line(cx + r * .4, cy + r, cx + r * .4, cy + r * 1.7, fill="#9AA3A8", width=2)
            ids["body"] = cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#0B120E", width=2)
        elif k == "buzzer":
            ids["body"] = cv.create_oval(cx - r * 1.2, cy - r * 1.2, cx + r * 1.2, cy + r * 1.2,
                                         fill="#111417", outline="#3A4248", width=2)
            cv.create_oval(cx - r * .25, cy - r * .25, cx + r * .25, cy + r * .25, fill="#2A3036", outline="")
            ids["waves"] = [cv.create_arc(cx - r * f, cy - r * f, cx + r * f, cy + r * f, start=st, extent=60,
                                          style="arc", outline="#FFD866", width=2, state="hidden")
                            for f in (1.6, 2.1) for st in (-30, 150)]
        elif k in ("button", "switch"):
            cv.create_rectangle(cx - r * 1.3, cy - r * 1.3, cx + r * 1.3, cy + r * 1.3,
                                fill="#2B2F36", outline="#0B120E", width=2, tags=tag)
            ids["cap"] = cv.create_oval(cx - r * .9, cy - r * .9, cx + r * .9, cy + r * .9,
                                        outline="#0B120E", width=2, tags=tag)
        elif k == "pir":
            ids["ring"] = cv.create_oval(cx - r * 1.6, cy - r * 1.6, cx + r * 1.6, cy + r * 1.6, outline="", width=3)
            cv.create_rectangle(cx - r * 1.3, cy - r * .2, cx + r * 1.3, cy + r * 1.1, fill="#2F6B3F",
                                outline="#0B120E", width=2, tags=tag)
            ids["dome"] = cv.create_oval(cx - r, cy - r * 1.1, cx + r, cy + r * .7, fill="#F2F2EE",
                                         outline="#B8B8B0", width=2, tags=tag)
        name = p.get("label", k).split(" (")[0]
        fit = max(4, int(s / 7.5))
        if len(name) > fit:
            name = name[:fit - 1].rstrip() + "…"
        pins = "/".join(str(x) for x in p["pins"])
        cv.create_text(cx, cy + s * .5, text=name, fill=INK, font="small_bold")
        cv.create_text(cx, cy + s * .5 + 15, text=f"GPIO{pins}", fill=MUTED, font="small")
        if k in INPUT_KINDS:
            cv.tag_bind(tag, "<ButtonPress-1>", lambda e, pp=p: self._press(pp))
            cv.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))
        ids["cx"], ids["cy"], ids["r"] = cx, cy, r
        return ids

    def _paint(self) -> None:
        cv = self.canvas
        for p, ids in self.items:
            k, pins = p["kind"], p["pins"]
            if k == "led":
                v = self.values.get(pins[0], 0.0)
                on = LED_COLOURS.get(p.get("colour", "red"), LED_COLOURS["red"])
                cv.itemconfigure(ids["body"], fill=_mix(_mix(on, "#000000", .7), on, v))
                cv.itemconfigure(ids["glow"], fill=_mix(BG, on, v * .45))
            elif k == "rgbled":
                rgb = [self.values.get(x, 0.0) for x in pins[:3]]
                lit = max(rgb, default=0.0)
                col = "#" + "".join(f"{round(255 * c):02x}" for c in rgb) if lit else "#3C3C3C"
                cv.itemconfigure(ids["body"], fill=col)
                cv.itemconfigure(ids["glow"], fill=_mix(BG, col, lit * .45) if lit else BG)
            elif k == "buzzer":
                on = self.values.get(pins[0], 0.0) > 0
                for a in ids["waves"]:
                    cv.itemconfigure(a, state="normal" if on else "hidden")
            elif k in ("button", "switch"):
                down = self.values.get(pins[0], 0.0) > 0 or pins[0] in self.held
                cv.itemconfigure(ids["cap"], fill="#7A1020" if down else "#D7263D")
                cx, cy, r = ids["cx"], ids["cy"], ids["r"] * (.75 if down else .9)
                cv.coords(ids["cap"], cx - r, cy - r, cx + r, cy + r)
            elif k == "pir":
                on = self.values.get(pins[0], 0.0) > 0 or pins[0] in self.held
                cv.itemconfigure(ids["ring"], outline="#FFB000" if on else "")

    # ---------------------------------------------------------------- input
    def _press(self, p: dict) -> None:
        pin = p["pins"][0]
        if self.mode != "sim":
            self.set_status("Real Pi mode: press the real button on your breadboard!")
            return
        if pin in self.held:
            return
        self.held.add(pin)
        self._paint()
        if self.on_press:
            self.on_press(pin)
        if p["kind"] == "pir":      # a wave: motion for a few seconds, then quiet again
            self.held.discard(pin)
            self._pir_jobs[pin] = self.after(PIR_HOLD_MS, lambda: self._pir_end(pin))

    def _pir_end(self, pin: int) -> None:
        self._pir_jobs.pop(pin, None)
        if self.on_release:
            self.on_release(pin)

    def _release_all(self, _e=None) -> None:
        for pin in list(self.held):
            self.held.discard(pin)
            if self.on_release:
                self.on_release(pin)
        self._paint()

    def _goal(self) -> None:
        if self.on_goal:
            self.on_goal()

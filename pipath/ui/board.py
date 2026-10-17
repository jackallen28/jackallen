"""The on-screen board: LEDs, buttons, buzzers and sensors drawn on a Canvas.

Simulator mode: it *is* the hardware. Click (and hold) a button to press it; drag the distance
sensor's slider to move something closer or further away.
Real Pi mode: it mirrors, live, what the program is telling the real pins to do (and what the
real buttons and sensors report), so students can compare "what my code says" with "what my
breadboard does".
"""
from __future__ import annotations

import tkinter as tk

import os

from ..gpio import BOARD_KIND, CAMERA_KINDS, INPUT_KINDS, SIM_OBJECTS
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
    def __init__(self, master, on_press=None, on_release=None, on_goal=None, on_object=None, on_camera=None,
                 on_distance=None):
        super().__init__(master, bg=C["bg"], relief="sunken", bd=2)
        self.on_press, self.on_release, self.on_goal, self.on_object = on_press, on_release, on_goal, on_object
        self.on_distance = on_distance    # the Simulator's distance slider moved: (echo pin, cm)
        self.sim_distance: dict[int, float] = {}   # echo pin -> cm, set with the slider (Simulator)
        self.live = False
        self.on_camera = on_camera        # click the camera panel's title to switch camera
        self.camera: dict | None = None    # {"kind", "object", "caption"} once there's a camera
        self._photo = None                 # the PhotoImage on show (Tk needs us to keep it)
        self._cam_ids: dict = {}           # canvas items of the camera panel, for quick updates
        self.mode = "sim"
        self.parts: list[dict] = []        # from the lesson's [[wiring]] rows
        self.live_parts: list[dict] = []   # devices the running program actually made
        self.values: dict[int, float] = {}
        self.items: list[tuple[dict, dict]] = []
        self.held: set[int] = set()
        self._pir_jobs: dict[int, str] = {}
        self._redraw_job = None

        head = tk.Frame(self, bg=C["bg"], relief="raised", bd=1)
        head.pack(fill="x")
        tk.Label(head, text="BOARD", font="small_bold", fg=C["ink"], bg=C["bg"], padx=10, pady=3).pack(side="left")
        self.mode_lbl = tk.Label(head, text="", font="small_bold", fg="#FFFFFF", padx=6, relief="raised", bd=1)
        self.mode_lbl.pack(side="left")
        self.goal_btn = PButton(head, "Watch the goal  ▶", self._goal, kind="secondary", font="small_bold", padx=10,
                                pady=1)
        self._status_text = ""
        self._status_id = None
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, height=150)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._schedule_redraw())
        self.canvas.bind("<ButtonRelease-1>", self._release_all)
        self.set_mode("sim")

    def destroy(self):
        if self._redraw_job is not None:
            self.after_cancel(self._redraw_job)
        for job in self._pir_jobs.values():
            self.after_cancel(job)
        super().destroy()

    # ---------------------------------------------------------------- public
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self._paint_mode()
        self.set_status("Click a button to press it" if mode == "sim" else "Shows what the real pins are doing")
        self._schedule_redraw()

    def set_live(self, on: bool) -> None:
        """A program is driving the real pins right now."""
        self.live = on
        self._paint_mode()

    def _paint_mode(self) -> None:
        if self.mode == "sim":
            self.mode_lbl.configure(text=" SIMULATOR ", bg=C["go"])
        else:
            self.mode_lbl.configure(text=" REAL PI  ● LIVE " if self.live else " REAL PI ",
                                    bg="#C0392B" if self.live else C["purple"])

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
        if live != self.live_parts:
            self.live_parts = live
            self._schedule_redraw()

    def set_values(self, values: dict) -> None:
        new = {int(k): float(v) for k, v in values.items()}
        if new != self.values:
            self.values = new
            self._paint()

    def reset(self) -> None:
        """Program finished or a new run is starting: everything off, keep the lesson's layout."""
        self.values = {}
        self.live_parts = []
        self.held.clear()
        for job in self._pir_jobs.values():
            self.after_cancel(job)
        self._pir_jobs.clear()
        self._schedule_redraw()

    def has_devices(self) -> bool:
        return bool(self.parts or self.live_parts or self.camera)

    # ---------------------------------------------------------------- camera
    def enable_camera(self, kind: str, obj: str = "face") -> None:
        self.camera = {"kind": kind, "object": obj, "caption": "No photo yet"}
        self._photo = None
        self._cam_ids = {}
        self._schedule_redraw()

    def disable_camera(self) -> None:
        if self.camera is not None:
            self.camera = None
            self._photo = None
            self._cam_ids = {}
            self._schedule_redraw()

    def set_camera_kind(self, kind: str) -> None:
        if self.camera is not None:
            self.camera["kind"] = kind
            self._schedule_redraw()

    def set_camera_object(self, key: str) -> None:
        if self.camera is not None and self.camera["object"] != key:
            self.camera["object"] = key
            self._schedule_redraw()

    def show_photo(self, preview: str, caption: str) -> None:
        """Show a photo (or the grid the computer sees) in the camera panel."""
        if self.camera is None:
            self.enable_camera("sim")
        img = None
        if preview and os.path.exists(preview):
            try:
                img = tk.PhotoImage(file=preview)
            except tk.TclError:
                img = None
            try:
                os.remove(preview)       # previews are temporary files
            except OSError:
                pass
        had_photo = self._photo is not None
        if img is not None:
            factor = max(1, -(-img.width() // 190), -(-img.height() // 140))
            self._photo = img.subsample(factor) if factor > 1 else img
        self.camera["caption"] = caption
        if had_photo and "img" in self._cam_ids and self._redraw_job is None:
            # just swap the picture and caption (a full redraw is slow on a Pi)
            self.canvas.itemconfigure(self._cam_ids["img"], image=self._photo)
            self.canvas.itemconfigure(self._cam_ids["caption"], text=caption)
        else:
            self._schedule_redraw()

    # ---------------------------------------------------------------- layout
    def _layout(self) -> list[dict]:
        """Lesson parts first (in wiring order), then anything else the program made."""
        out = [dict(p) for p in self.parts]
        by_pin = {p["pins"][0]: p for p in out}
        for d in self.live_parts:
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
        self._cam_ids = {}
        w, h = max(cv.winfo_width(), 100), max(cv.winfo_height(), 80)
        for x in range(12, w, 30):          # a few breadboard holes (sparse: every item costs on a Pi)
            for y in range(12, h, 30):
                cv.create_rectangle(x, y, x + 2, y + 2, fill=HOLE, outline="")
        self._status_id = cv.create_text(10, 6, anchor="nw", text=self._status_text, fill=MUTED, font="small")
        top = 22
        h -= top
        if self.camera is not None:
            cam_w = max(220, int(w * .55))
            self._draw_camera(w - cam_w, top, cam_w, h)
            w -= cam_w
        parts = self._layout()
        if not parts:
            if self.camera is None:
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

    def _draw_camera(self, x0: int, y0: int, w: int, h: int) -> None:
        cv, cam = self.canvas, self.camera
        cv.create_rectangle(x0 + 4, y0, x0 + w - 8, y0 + h - 4, fill="#0F1A14", outline="#2C4436")
        title = cv.create_text(x0 + 14, y0 + 8, anchor="nw", fill=INK, font="small_bold", tags="camtitle",
                               text=f"{CAMERA_KINDS.get(cam['kind'], cam['kind']).upper()} CAMERA  ▸")
        x1, y1, x2, y2 = cv.bbox(title)
        cv.create_rectangle(x1 - 4, y1 - 2, x2 + 4, y2 + 2, fill="#22382C", outline="", tags="camtitle")
        cv.tag_raise(title)
        cv.tag_bind("camtitle", "<Button-1>", lambda e: self.on_camera and self.on_camera())
        cv.tag_bind("camtitle", "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        cv.tag_bind("camtitle", "<Leave>", lambda e: self.canvas.configure(cursor=""))
        cx = x0 + w // 2 - 2
        img_top = y0 + 28
        picker = cam["kind"] == "sim"
        img_h = h - 28 - (44 if picker else 22)
        if self._photo is not None:
            self._cam_ids["img"] = cv.create_image(cx, img_top + img_h // 2, image=self._photo)
        else:
            cv.create_rectangle(cx - 70, img_top + img_h // 2 - 45, cx + 70, img_top + img_h // 2 + 45,
                                outline="#2C4436", dash=(3, 3))
        self._cam_ids["caption"] = cv.create_text(cx, img_top + img_h + 8, text=cam["caption"], fill=INK, font="small")
        if picker:      # what the pretend camera can see
            n = len(SIM_OBJECTS)
            cw = (w - 24) / n
            for i, (key, name) in enumerate(SIM_OBJECTS):
                bx = x0 + 10 + i * cw
                by = y0 + h - 30
                on = key == cam["object"]
                tag = f"obj_{key}"
                cv.create_rectangle(bx + 2, by, bx + cw - 2, by + 20, fill=C["go"] if on else "#22382C",
                                    outline="", tags=tag)
                cv.create_text(bx + cw / 2, by + 10, text=name, fill="#FFFFFF" if on else INK, font="small", tags=tag)
                cv.tag_bind(tag, "<Button-1>", lambda e, k=key: self._pick_object(k))
                cv.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
                cv.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    def _pick_object(self, key: str) -> None:
        self.camera["object"] = key
        self._schedule_redraw()
        if self.on_object:
            self.on_object(key)

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
        elif k == "distance":
            # an HC-SR04: a blue board with two silver "eyes", the distance above it
            w2 = r * 2.4
            cv.create_rectangle(cx - w2, cy - r * 1.05, cx + w2, cy + r * 1.05, fill="#1F5FA8", outline="#0B120E",
                                width=2)
            for dx in (-1.25, 1.25):
                cv.create_oval(cx + dx * r - r * .85, cy - r * .85, cx + dx * r + r * .85, cy + r * .85,
                               fill="#C9CCD1", outline="#6B7078", width=2)
                cv.create_oval(cx + dx * r - r * .45, cy - r * .45, cx + dx * r + r * .45, cy + r * .45,
                               fill="#3A3F46", outline="")
            ids["reading"] = cv.create_text(cx, cy - r * 1.75, text="", fill="#FFE680", font="small_bold")
            # Simulator: a slider to move something closer (left) or further away (right)
            x0, x1, ty = cx - w2, cx + w2, cy + r * 1.75
            dtag = f"dist{p['pins'][0]}"
            ids["track"] = cv.create_line(x0, ty, x1, ty, fill="#5D7A68", width=5, tags=dtag)
            ids["knob"] = cv.create_rectangle(0, 0, 0, 0, fill=C["teal"], outline="#FFFFFF", tags=dtag)
            ids["track_x"], ids["track_y"] = (x0, x1), ty
            cv.tag_bind(dtag, "<ButtonPress-1>", lambda e, pp=p, ii=ids: self._slide(pp, ii, e.x))
            cv.tag_bind(dtag, "<B1-Motion>", lambda e, pp=p, ii=ids: self._slide(pp, ii, e.x))
            cv.tag_bind(dtag, "<Enter>", lambda e: self.canvas.configure(cursor="sb_h_double_arrow"))
            cv.tag_bind(dtag, "<Leave>", lambda e: self.canvas.configure(cursor=""))
        name = p.get("label", k).split(" (")[0]
        fit = max(4, int(s / 8.5))
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
        """Recolour parts whose value changed (each canvas call costs time on a Pi)."""
        cv = self.canvas
        for p, ids in self.items:
            k, pins = p["kind"], p["pins"]
            state = (tuple(self.values.get(x, 0.0) for x in pins), pins[0] in self.held,
                     self.sim_distance.get(pins[0]), self.mode)
            if ids.get("state") == state:
                continue
            ids["state"] = state
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
            elif k == "distance":
                sim_cm = self.sim_distance.get(pins[0], 100)
                if pins[0] in self.values:          # what the program measured (live on a real Pi)
                    cm = round(self.values[pins[0]] * 100)
                    text = f"{cm} cm" + ("+" if cm >= 100 else "")
                else:
                    text = f"{round(sim_cm)} cm" if self.mode == "sim" else "-- cm"
                cv.itemconfigure(ids["reading"], text=text)
                show = "normal" if self.mode == "sim" else "hidden"
                cv.itemconfigure(ids["track"], state=show)
                cv.itemconfigure(ids["knob"], state=show)
                (x0, x1), ty = ids["track_x"], ids["track_y"]
                kx = x0 + (x1 - x0) * (min(150, sim_cm) - 2) / 148
                cv.coords(ids["knob"], kx - 5, ty - 8, kx + 5, ty + 8)

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

    def _slide(self, p: dict, ids: dict, x: float) -> None:
        pin = p["pins"][0]
        if self.mode != "sim":
            self.set_status("Real Pi mode: move your hand in front of the real sensor!")
            return
        x0, x1 = ids["track_x"]
        cm = round(2 + 148 * max(0.0, min(1.0, (x - x0) / (x1 - x0))))
        if cm == self.sim_distance.get(pin):
            return
        self.sim_distance[pin] = cm
        self._paint()
        if self.on_distance:
            self.on_distance(pin, cm)

    def set_distance(self, pin: int, cm: float) -> None:
        """Move the Simulator's slider (Watch the goal does this)."""
        self.sim_distance[pin] = cm
        self._paint()

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

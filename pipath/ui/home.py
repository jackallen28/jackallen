"""The activity picker: every activity is open, and students do as many as they like.

The cards are drawn on one Canvas instead of being built from widgets: on a Pi 3B each
Tk widget costs around 10 ms to make, and the old grid of about 200 widgets took seconds.
"""
from __future__ import annotations

import tkinter as tk

from ..levels import INFO as LEVEL_INFO, LEVELS
from .onboarding import Screen, logo
from .theme import C, TIER_COLOURS
from .widgets import PButton, label

CARD_MIN_WIDTH = 300
PAD, GAP = 28, 12


def stars_for(app, hints_used: int) -> int:
    if hints_used <= app.settings["three_star_max_hints"]:
        return 3
    if hints_used <= app.settings["two_star_max_hints"]:
        return 2
    return 1


class HomeScreen(Screen):
    """Made once per student and kept: coming back from an activity only re-draws the cards."""

    def __init__(self, app):
        super().__init__(app)
        s = app.student
        self.filter = getattr(app, "home_filter", "all")
        self._width = 0
        self._draw_job = None

        # ---- top bar
        bar = tk.Frame(self, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], padx=18, pady=10)
        bar.pack(fill="x")
        logo(bar, 40, bg=C["panel"]).pack(side="left")
        label(bar, app.settings["app_name"], font="h2", bg=C["panel"]).pack(side="left", padx=(8, 0))
        if app.teacher_mode:
            tk.Label(bar, text=" TEACHER MODE ", font="small_bold", fg="#FFFFFF", bg=C["info"]).pack(side="left", padx=12)
        PButton(bar, "Switch student", app.logout, kind="ghost", font="small_bold").pack(side="right")
        who = tk.Frame(bar, bg=C["panel"])
        who.pack(side="right", padx=14)
        label(who, s.first_name, font="ui_bold", bg=C["panel"]).pack(anchor="e")
        label(who, s.label, font="small", fg=C["muted"], bg=C["panel"]).pack(anchor="e")

        # ---- greeting, help level and filters (a handful of real widgets)
        head = tk.Frame(self, bg=C["bg"], padx=PAD, pady=14)
        head.pack(fill="x")
        label(head, f"Hi {s.first_name}! What would you like to make?", font="h1").pack(anchor="w")
        self.sub_lbl = label(head, self._subline(), fg=C["muted"], font="big")
        self.sub_lbl.pack(anchor="w", pady=(2, 10))

        lv = tk.Frame(head, bg=C["bg"])
        lv.pack(fill="x")
        label(lv, "How much help do you want?", font="ui_bold").pack(side="left", padx=(0, 10))
        self.level_chips: dict[str, tk.Label] = {}
        for key in LEVELS:
            c = tk.Label(lv, text=f"  {LEVEL_INFO[key][0]}  ", font="small_bold", cursor="hand2", pady=4,
                         highlightthickness=1)
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, k=key: self.set_level(k))
            self.level_chips[key] = c
        self.level_blurb = label(head, "", font="small", fg=C["muted"])
        self.level_blurb.pack(anchor="w", pady=(4, 0))

        chips = tk.Frame(head, bg=C["bg"])
        chips.pack(fill="x", pady=(10, 0))
        label(chips, "Show:", font="small_bold", fg=C["muted"]).pack(side="left", padx=(0, 8))
        self.chips: dict[str, tk.Label] = {}
        for key, text, col in [("all", "Everything", C["ink"])] + [
                (t["id"], t["title"], TIER_COLOURS.get(t["id"], C["accent"])) for t in app.catalog.tiers]:
            c = tk.Label(chips, text=f"  {text}  ", font="small_bold", cursor="hand2", pady=4, highlightthickness=1)
            c.colour = col
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, k=key: self.set_filter(k))
            self.chips[key] = c

        # ---- the activities, drawn on one canvas
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=C["bg"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview, width=12)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._resized)
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))

        self._paint_level()
        self.set_filter(self.filter)

    def destroy(self):
        self._wheel(False)
        if self._draw_job is not None:
            self.after_cancel(self._draw_job)
        super().destroy()

    def _subline(self) -> str:
        s = self.app.student
        done = sum(1 for p in self.app.catalog.projects
                   if p.get("status") == "ready" and s.lesson_status(p["id"]) == "complete")
        sub = "Pick any activity. Do as many or as few as you like, in any order."
        return sub + (f"  You've finished {done} so far." if done else "")

    def refresh(self) -> None:
        """Back from an activity: show the latest progress and help level (scroll place is kept)."""
        self.sub_lbl.configure(text=self._subline())
        self._paint_level()
        self._schedule_draw()

    def hide(self) -> None:
        self._wheel(False)
        self.pack_forget()

    # ------------------------------------------------------------------ help level
    def set_level(self, key: str) -> None:
        self.app.student.set_help_level(key)
        self._paint_level()

    def _paint_level(self) -> None:
        current = self.app.student.help_level
        for k, c in self.level_chips.items():
            on = k == current
            c.configure(bg=C["accent"] if on else C["panel"], fg="#FFFFFF" if on else C["ink"],
                        highlightbackground=C["accent"] if on else C["line"])
        self.level_blurb.configure(text=LEVEL_INFO[current][1])

    # ------------------------------------------------------------------ filtering + drawing
    def set_filter(self, key: str) -> None:
        if key not in self.chips:
            key = "all"
        self.filter = self.app.home_filter = key
        for k, c in self.chips.items():
            on = k == key
            c.configure(bg=c.colour if on else C["panel"], fg="#FFFFFF" if on else c.colour,
                        highlightbackground=c.colour if on else C["line"])
        self._schedule_draw()
        self.canvas.yview_moveto(0)

    def _resized(self, e) -> None:
        if abs(e.width - self._width) > 2:
            self._width = e.width
            self._schedule_draw()

    def _schedule_draw(self) -> None:
        if self._draw_job is None:
            self._draw_job = self.after_idle(self._draw)

    def _wheel(self, on: bool) -> None:
        if on:
            self.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
            self.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        else:
            for seq in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
                self.unbind_all(seq)

    def _draw(self) -> None:
        self._draw_job = None
        cv = self.canvas
        cv.delete("all")
        width = max(cv.winfo_width(), 400)
        cols = max(1, min(3, (width - 2 * PAD) // CARD_MIN_WIDTH))
        card_w = (width - 2 * PAD - (cols - 1) * GAP) / cols
        y = 4
        for tier in self.app.catalog.tiers:
            if self.filter not in ("all", tier["id"]):
                continue
            projects = self.app.catalog.projects_in(tier["id"])
            if not projects:
                continue
            col = TIER_COLOURS.get(tier["id"], C["accent"])
            cv.create_rectangle(PAD, y, PAD + 6, y + 30, fill=col, outline="")
            t = cv.create_text(PAD + 16, y + 15, anchor="w", text=tier["title"], font="h2", fill=C["ink"])
            x2 = cv.bbox(t)[2]
            cv.create_text(x2 + 14, y + 15, anchor="w", text=f"{tier['tagline']}  ·  {tier['description']}",
                           font="ui", fill=C["muted"], width=max(100, width - x2 - PAD - 20))
            y += 44
            for start in range(0, len(projects), cols):
                row = projects[start:start + cols]
                y = self._card_row(row, y, card_w, col) + GAP
            y += 18
        y = self._free_build(y + 6, width)
        cv.configure(scrollregion=(0, 0, width, y + 24))

    # ------------------------------------------------------------------ cards
    def _card_row(self, row: list[dict], y: float, card_w: float, col: str) -> float:
        """Draw one row of cards; they share the tallest card's height. Returns the bottom."""
        cv = self.canvas
        drawn = []
        bottom = y
        for i, p in enumerate(row):
            x = PAD + i * (card_w + GAP)
            info = self._card_content(p, x, y, card_w, col)
            drawn.append((p, x, info))
            bottom = max(bottom, info["bottom"])
        btn_h = 34
        row_bottom = bottom + 14 + btn_h + 16
        for p, x, info in drawn:
            tag = f"card_{p['id']}"
            bg = cv.create_rectangle(x, y, x + card_w, row_bottom, fill=C["panel"],
                                     outline=col if info["state"] == "in_progress" else C["line"], tags=(tag,))
            cv.tag_lower(bg, info["first"])
            self._card_button(p, info["state"], x + 16, row_bottom - 16 - btn_h, btn_h, tag)
        return row_bottom

    def _card_content(self, p: dict, x: float, y: float, w: float, col: str) -> dict:
        app, cv = self.app, self.canvas
        state = app.project_state(p)       # ready | in_progress | complete | planned
        dim = state == "planned"
        tag = f"card_{p['id']}"
        inner = w - 32
        tier_title = next((t["title"] for t in app.catalog.tiers if t["id"] == p["tier"]), p["tier"])
        chip_t = cv.create_text(x + 22, y + 22, anchor="w", text=tier_title.upper(), font="small_bold",
                                fill="#FFFFFF", tags=(tag,))
        bx = cv.bbox(chip_t)
        first = cv.create_rectangle(bx[0] - 6, bx[1] - 2, bx[2] + 6, bx[3] + 2, fill=C["locked"] if dim else col,
                                    outline="", tags=(tag,))
        cv.tag_raise(chip_t)
        status = None
        if state == "complete":
            lp = app.student.lesson(p["id"])
            st = stars_for(app, lp.get("hints_used", 0))
            status = ("DONE  " + "★" * st + "☆" * (3 - st), C["ok"])
        elif state == "in_progress":
            lp = app.student.lesson(p["id"])
            steps = len(app.catalog.lesson(p["id"])["steps"])
            status = (f"STEP {lp['step'] + 1} OF {steps}", col)
        elif dim:
            status = ("COMING SOON", C["muted"])
        if status:
            cv.create_text(x + w - 16, y + 22, anchor="e", text=status[0], font="small_bold", fill=status[1], tags=(tag,))
        yy = y + 42

        def text(t, font, fill, gap=4):
            nonlocal yy
            item = cv.create_text(x + 16, yy, anchor="nw", text=t, font=font, fill=fill, width=inner, tags=(tag,))
            yy = cv.bbox(item)[3] + gap

        text(p["title"], "h3", C["faint"] if dim else C["ink"], 2)
        text(p["subtitle"], "ui", C["muted"], 8)
        text("  ·  ".join(p["concepts"]), "small", C["faint"] if dim else C["info"], 8)
        needs = [n for n, on in (("GPIO kit", p.get("gpio")), ("camera", p.get("camera"))) if on]
        meta = f"≈ {p['minutes']} min   ·   help: {p['support']}"
        if needs:
            meta += "   ·   needs " + " + ".join(needs)
        text(meta, "small", C["muted"], 4)
        tip = self._try_first(p) if state == "ready" else None
        if tip:
            text(tip, "small_bold", C["warn"], 4)
        return {"state": state, "bottom": yy, "first": first}

    def _card_button(self, p: dict, state: str, x: float, y: float, h: float, card_tag: str) -> None:
        cv = self.canvas
        if state == "planned":
            cv.create_text(x, y + h / 2, anchor="w", text="In the next version of PiPath", font="small_bold",
                           fill=C["muted"], tags=(card_tag,))
            return
        text, kind = {"ready": ("Start  ▸", "primary"), "in_progress": ("Continue  ▸", "primary"),
                      "complete": ("Review", "secondary")}[state]
        fill, fg, hover = ((C["accent"], "#FFFFFF", C["accent_dark"]) if kind == "primary"
                           else (C["panel"], C["ink"], C["panel_alt"]))
        tag = f"btn_{p['id']}"
        t = cv.create_text(x + 16, y + h / 2, anchor="w", text=text, font="ui_bold", fill=fg, tags=(tag, card_tag))
        bx = cv.bbox(t)
        r = cv.create_rectangle(x, y, bx[2] + 16, y + h, fill=fill, outline=C["line"] if kind == "secondary" else fill,
                                tags=(tag, card_tag))
        cv.tag_raise(t)
        open_it = lambda e, pid=p["id"]: self.app.open_lesson(pid)
        cv.tag_bind(card_tag, "<Button-1>", open_it)
        cv.tag_bind(card_tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(card_tag, "<Leave>", lambda e: cv.configure(cursor=""))
        cv.tag_bind(tag, "<Enter>", lambda e: cv.itemconfigure(r, fill=hover))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.itemconfigure(r, fill=fill))

    def _try_first(self, p) -> str | None:
        """A friendly 'try this first' tip, until the student has finished that activity."""
        todo = [self.app.catalog.project(i) for i in p.get("try_first", [])]
        todo = [q for q in todo if q and q.get("status") == "ready"
                and self.app.student.lesson_status(q["id"]) != "complete"]
        if not todo:
            return None
        return "Good to try first: " + " or ".join(f"“{q['title']}”" for q in todo)

    # ------------------------------------------------------------------ free build
    def _free_build(self, y: float, width: float) -> float:
        cv = self.canvas
        x0, x1 = PAD, width - PAD
        tag = "freebuild"
        title = cv.create_text(x0 + 22, y + 20, anchor="nw", text="Free Build", font="h2", fill="#FFFFFF", tags=(tag,))
        yy = cv.bbox(title)[3] + 4
        msg = cv.create_text(x0 + 22, yy, anchor="nw", width=max(200, x1 - x0 - 260), fill="#C9CED6", font="ui",
                             text="Your own space to create anything, with the Simulator and the Coach. "
                                  "No steps. It's all you.", tags=(tag,))
        yy = cv.bbox(msg)[3] + 4
        n = len(self.app.student.list_projects())
        if n:
            note = cv.create_text(x0 + 22, yy + 2, anchor="nw", text=f"{n} saved project{'s' if n != 1 else ''}",
                                  font="small_bold", fill=C["syn_def"], tags=(tag,))
            yy = cv.bbox(note)[3]
        bottom = yy + 20
        bg = cv.create_rectangle(x0, y, x1, bottom, fill=C["ink"], outline="", tags=(tag,))
        cv.tag_lower(bg, title)
        bt = cv.create_text(x1 - 38, (y + bottom) / 2, anchor="e", text="Open Free Build  ▸", font="ui_bold",
                            fill="#FFFFFF", tags=(tag, "fb_btn"))
        bx = cv.bbox(bt)
        r = cv.create_rectangle(bx[0] - 16, bx[1] - 9, bx[2] + 16, bx[3] + 9, fill=C["accent"], outline="",
                                tags=(tag, "fb_btn"))
        cv.tag_raise(bt)
        cv.tag_bind(tag, "<Button-1>", lambda e: self.app.open_free_build())
        cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))
        cv.tag_bind("fb_btn", "<Enter>", lambda e: cv.itemconfigure(r, fill=C["accent_dark"]))
        cv.tag_bind("fb_btn", "<Leave>", lambda e: cv.itemconfigure(r, fill=C["accent"]))
        return bottom

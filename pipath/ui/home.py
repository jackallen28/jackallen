"""The activity picker: every activity is open, and students do as many as they like.

Retro look: a title bar with the school logo in the corner, then a teal "desktop" where each
activity is a little window (its title bar in the tier's colour). The cards are drawn on one
Canvas instead of being built from widgets: on a Pi 3B each Tk widget costs around 10 ms to
make, and the old grid of about 200 widgets took seconds.
"""
from __future__ import annotations

import tkinter as tk

from .onboarding import Screen
from .theme import C, TIER_COLOURS, blend
from .widgets import CogButton, MenuBar, PButton, TitleBar, about_box, bevel, label, wheel_target

CARD_MIN_WIDTH = 300
PAD, GAP = 24, 14
BAR = 26                      # height of a card's title bar


def stars_for(app, hints_used: int) -> int:
    if hints_used <= app.settings["three_star_max_hints"]:
        return 3
    if hints_used <= app.settings["two_star_max_hints"]:
        return 2
    return 1


class HomeScreen(Screen):
    """Made once per student and kept: coming back from an activity only re-draws the cards."""

    def __init__(self, app):
        super().__init__(app, bg=C["bg"])
        s = app.student
        self.filter = s.show
        self._width = 0
        self._draw_job = None

        # ---- title bar: logo in the corner, who's working, settings
        bar = self.bar = TitleBar(self, app.settings["app_name"], height=56, logo=True, font="h2",
                                  sub=f"{s.first_name}   ·   {s.profile.get('school', '')}")
        bar.pack(fill="x")
        MenuBar(self, [("File", lambda: [(app.settings.get("free_play_name", "Free Play"), "", app.open_free_play,
                                          True), None,
                                         ("Switch student", "", app.logout, True)]),
                       ("View", lambda: [(("● " if self.filter == k else "   ") + t, "", lambda k=k: self.set_filter(k),
                                          True) for k, t in (("all", "Everything"),
                                                             ("hardware", "Hardware projects"))] +
                                        [None, ("Settings...", "", app.open_settings, True)]),
                       ("Help", lambda: [("About PiPath", "", lambda: about_box(app), True)])]).pack(fill="x")
        bar.add_right(PButton(bar, "Switch student", app.logout, kind="secondary", font="small_bold", pady=3))
        bar.add_right(CogButton(bar, lambda: app.open_settings()), pad=8)

        # ---- greeting and "show" buttons (a handful of real widgets)
        head = tk.Frame(self, bg=C["bg"], padx=PAD, pady=10, relief="raised", bd=2)
        head.pack(fill="x")
        self.hello = label(head, f"Hi {s.first_name}! What would you like to make?", font="h2", fg=C["purple"],
                           wraplength=900)
        self.hello.pack(anchor="w")
        self.sub_lbl = label(head, self._subline(), fg=C["muted"])
        self.sub_lbl.pack(anchor="w", pady=(2, 8))
        chips = tk.Frame(head, bg=C["bg"])
        chips.pack(fill="x")
        label(chips, "Show:", font="small_bold").pack(side="left", padx=(0, 8))
        self.chips: dict[str, tk.Label] = {}
        for key, text, col in [("all", "Everything", C["purple"]), ("hardware", "▶ Hardware projects", C["err"])] + [
                (t["id"], t["title"], TIER_COLOURS.get(t["id"], C["accent"])) for t in app.catalog.tiers]:
            c = tk.Label(chips, text=f" {text} ", font="small_bold", cursor="hand2", padx=6, pady=3, bd=2)
            c.colour = col
            c.pack(side="left", padx=(0, 4))
            c.bind("<Button-1>", lambda e, k=key: self.set_filter(k))
            self.chips[key] = c

        # ---- the activities, drawn on one canvas: the teal desktop
        body = tk.Frame(self, bg=C["desk"])
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=C["desk"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview, width=14)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._resized)
        wheel_target(self.canvas)
        self.wheel_default = self.canvas          # the wheel scrolls the cards wherever the mouse is

        self.set_filter(self.filter, save=False)

    def destroy(self):
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
        """Back from an activity (or Settings): show the latest progress and choices."""
        self.sub_lbl.configure(text=self._subline())
        if self.app.student.show != self.filter:
            self.set_filter(self.app.student.show, save=False)
        else:
            self._schedule_draw()

    def hide(self) -> None:
        self.pack_forget()

    def settings_changed(self, what: str) -> None:
        s = self.app.student
        if what == "names":
            self.hello.configure(text=f"Hi {s.first_name}! What would you like to make?")
            self.bar.set_text(self.app.settings["app_name"], f"{s.first_name}   ·   {s.profile.get('school', '')}")
        elif what == "show" and s.show != self.filter:
            self.set_filter(s.show, save=False)

    # ------------------------------------------------------------------ choices
    def set_level(self, key: str) -> None:
        self.app.student.set_help_level(key)

    def set_filter(self, key: str, save: bool = True) -> None:
        if key not in self.chips:
            key = "all"
        self.filter = key
        if save and key != self.app.student.show:
            self.app.student.set_show(key)
        for k, c in self.chips.items():
            on = k == key
            c.configure(bg="#FFFFFF" if on else C["bg"], fg=c.colour, relief="sunken" if on else "raised")
        self._schedule_draw()
        self.canvas.yview_moveto(0)

    # ------------------------------------------------------------------ drawing
    def _resized(self, e) -> None:
        if abs(e.width - self._width) > 2:
            self._width = e.width
            self._schedule_draw()

    def _schedule_draw(self) -> None:
        if self._draw_job is None:
            self._draw_job = self.after_idle(self._draw)

    def _draw(self) -> None:
        self._draw_job = None
        cv = self.canvas
        cv.delete("all")
        width = max(cv.winfo_width(), 400)
        cols = max(1, min(3, (width - 2 * PAD) // CARD_MIN_WIDTH))
        card_w = (width - 2 * PAD - (cols - 1) * GAP) / cols
        y = self._free_play(14, width) + 18
        for dx, colour in ((2, C["desk_dark"]), (0, "#FFFFFF")):
            cv.create_text(PAD + dx, y + 10 + dx, anchor="w", font="h3", fill=colour,
                           text="...or pick one of these tutorials for step-by-step help:")
        y += 34
        for tier in self.app.catalog.tiers:
            if self.filter not in ("all", "hardware", tier["id"]):
                continue
            projects = self.app.catalog.projects_in(tier["id"])
            if self.filter == "hardware":          # anything you build with real parts
                projects = [p for p in projects if p.get("gpio") or p.get("camera")]
            if not projects:
                continue
            col = TIER_COLOURS.get(tier["id"], C["accent"])
            # tier heading on the desktop: a pixel square and white text with a dark drop shadow
            cv.create_rectangle(PAD, y + 4, PAD + 18, y + 22, fill=col, outline="#FFFFFF", width=2)
            for dx, colour in ((2, C["desk_dark"]), (0, "#FFFFFF")):
                t = cv.create_text(PAD + 28 + dx, y + 13 + dx, anchor="w", text=tier["title"], font="h2",
                                   fill=colour)
            x2 = cv.bbox(t)[2]
            cv.create_text(x2 + 14, y + 13, anchor="w", text=f"{tier['tagline']}  ·  {tier['description']}",
                           font="small", fill="#E2F7F8", width=max(100, width - x2 - PAD - 20))
            y += 34
            for start in range(0, len(projects), cols):
                row = projects[start:start + cols]
                y = self._card_row(row, y, card_w, col) + GAP
            y += 10
        cv.configure(scrollregion=(0, 0, width, y + 24))

    # ------------------------------------------------------------------ cards
    def _card_row(self, row: list[dict], y: float, card_w: float, col: str) -> float:
        """Draw one row of cards (little windows); they share the tallest card's height."""
        cv = self.canvas
        drawn = []
        bottom = y
        for i, p in enumerate(row):
            x = PAD + i * (card_w + GAP)
            info = self._card_content(p, x, y, card_w, col)
            drawn.append((p, x, info))
            bottom = max(bottom, info["bottom"])
        btn_h = 32
        row_bottom = bottom + 12 + btn_h + 14
        for p, x, info in drawn:
            tag = f"card_{p['id']}"
            dim = info["state"] == "planned"
            # the window: a bevelled face, and a title bar in the tier colour
            frame = (tag, f"frame_{p['id']}")
            cv.create_rectangle(x + 4, y + 4, x + card_w + 4, row_bottom + 4, fill=C["desk_dark"], outline="",
                                tags=frame)      # drop shadow
            bevel(cv, x, y, x + card_w, row_bottom, C["bg"], tags=frame)
            a = C["locked"] if dim else col
            steps = 12
            for k in range(steps):
                cv.create_rectangle(x + 3 + (card_w - 6) * k / steps, y + 3, x + 3 + (card_w - 6) * (k + 1) / steps + 1,
                                    y + 3 + BAR, fill=blend(a, blend(a, "#FFFFFF", .45), k / (steps - 1)),
                                    outline="", tags=frame)
            cv.tag_lower(f"frame_{p['id']}", info["first"])      # under the card's text, in drawing order
            self._card_button(p, info["state"], x + 14, row_bottom - 14 - btn_h, btn_h, tag)
        return row_bottom

    def _card_content(self, p: dict, x: float, y: float, w: float, col: str) -> dict:
        app, cv = self.app, self.canvas
        state = app.project_state(p)       # ready | in_progress | complete | planned
        dim = state == "planned"
        tag = f"card_{p['id']}"
        inner = w - 28
        first = cv.create_text(x + 12, y + 3 + BAR / 2, anchor="w", text=p["title"], font="ui_bold",
                               fill="#FFFFFF", tags=(tag,))
        status = None
        if state == "complete":
            lp = app.student.lesson(p["id"])
            st = stars_for(app, lp.get("hints_used", 0))
            status = "DONE " + "★" * st + "☆" * (3 - st)
        elif state == "in_progress":
            lp = app.student.lesson(p["id"])
            steps = len(app.catalog.lesson(p["id"])["steps"])
            status = f"STEP {min(lp['step'], steps - 1) + 1}/{steps}"
        elif dim:
            status = "COMING SOON"
        if status:
            cv.create_text(x + w - 10, y + 3 + BAR / 2, anchor="e", text=status, font="small_bold",
                           fill="#FFFFFF", tags=(tag,))
        yy = y + BAR + 12

        def text(t, font, fill, gap=4):
            nonlocal yy
            item = cv.create_text(x + 14, yy, anchor="nw", text=t, font=font, fill=fill, width=inner, tags=(tag,))
            yy = cv.bbox(item)[3] + gap

        text(p["subtitle"], "ui", C["faint"] if dim else C["ink"], 8)
        text("  ·  ".join(p["concepts"]), "small", C["faint"] if dim else blend(col, "#000000", .25), 8)
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
        text, primary = {"ready": ("Start  ▸", True), "in_progress": ("Continue  ▸", True),
                         "complete": ("Review", False)}[state]
        fill, fg, hover = C["bg"], C["ink"], C["face_hi"]       # grey Windows buttons
        tag = f"btn_{p['id']}"
        t = cv.create_text(x + 14, y + h / 2, anchor="w", text=text, font="ui_bold", fill=fg, tags=(tag, card_tag))
        bx = cv.bbox(t)
        x1 = bx[2] + 14
        if primary:      # the default button's black outline
            cv.create_rectangle(x - 1, y - 1, x1 + 1, y + h + 1, outline="#000000", tags=(tag, card_tag))
        bevel(cv, x, y, x1, y + h, fill, tags=(tag, card_tag, f"face_{p['id']}"))
        face = [i for i in cv.find_withtag(f"face_{p['id']}") if cv.type(i) == "rectangle"][0]
        cv.tag_raise(t)
        open_it = lambda e, pid=p["id"]: self.app.open_lesson(pid)
        cv.tag_bind(card_tag, "<ButtonRelease-1>", open_it)
        cv.tag_bind(card_tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(card_tag, "<Leave>", lambda e: cv.configure(cursor=""))
        cv.tag_bind(tag, "<Enter>", lambda e: cv.itemconfigure(face, fill=hover))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.itemconfigure(face, fill=fill))

    def _try_first(self, p) -> str | None:
        """A friendly 'try this first' tip, until the student has finished that activity."""
        todo = [self.app.catalog.project(i) for i in p.get("try_first", [])]
        todo = [q for q in todo if q and q.get("status") == "ready"
                and self.app.student.lesson_status(q["id"]) != "complete"]
        if not todo:
            return None
        return "Good to try first: " + " or ".join(f"“{q['title']}”" for q in todo)

    # ------------------------------------------------------------------ free build
    def _free_play(self, y: float, width: float) -> float:
        """The first box: Free Play, the sandbox (always open)."""
        cv = self.canvas
        x0, x1 = PAD, width - PAD
        tag = "freebuild"
        name = self.app.settings.get("free_play_name", "Free Play")
        first = cv.create_text(x0 + 14, y + 3 + BAR / 2, anchor="w", text=f"{name}  -  your sandbox",
                               font="ui_bold", fill="#FFFFFF", tags=(tag,))
        big = cv.create_text(x0 + 16, y + BAR + 12, anchor="nw", fill=C["purple"], font="h2", tags=(tag,),
                             text=f"{name}: build anything you like!")
        msg = cv.create_text(x0 + 16, cv.bbox(big)[3] + 4, anchor="nw", width=max(200, x1 - x0 - 280),
                             fill=C["ink"], font="ui", tags=(tag,),
                             text="Your own code, your own circuits. Add LEDs, buttons, sensors or the camera, and "
                                  "the Coach helps you wire them up and fix any errors. Choose a guide that nudges "
                                  "you along, or go it alone.")
        yy = cv.bbox(msg)[3] + 4
        n = len(self.app.student.list_projects())
        if n:
            note = cv.create_text(x0 + 16, yy + 2, anchor="nw", text=f"{n} saved project{'s' if n != 1 else ''}",
                                  font="small_bold", fill=C["purple"], tags=(tag,))
            yy = cv.bbox(note)[3]
        bottom = yy + 16
        frame = (tag, "fb_frame")
        cv.create_rectangle(x0 + 4, y + 4, x1 + 4, bottom + 4, fill=C["desk_dark"], outline="", tags=frame)
        bevel(cv, x0, y, x1, bottom, C["bg"], tags=frame)
        steps = 24
        for k in range(steps):
            cv.create_rectangle(x0 + 3 + (x1 - x0 - 6) * k / steps, y + 3, x0 + 3 + (x1 - x0 - 6) * (k + 1) / steps + 1,
                                y + 3 + BAR, fill=blend(C["title_a"], C["title_b"], k / (steps - 1)), outline="",
                                tags=frame)
        cv.tag_lower("fb_frame", first)
        bt = cv.create_text(x1 - 30, (y + BAR + bottom) / 2, anchor="e", text=f"Start {name}  ▸", font="h3",
                            fill=C["ink"], tags=(tag, "fb_btn"))
        bx = cv.bbox(bt)
        cv.create_rectangle(bx[0] - 15, bx[1] - 8, bx[2] + 15, bx[3] + 8, outline="#000000", tags=(tag, "fb_btn"))
        bevel(cv, bx[0] - 14, bx[1] - 7, bx[2] + 14, bx[3] + 7, C["bg"], tags=(tag, "fb_btn", "fb_face"))
        face = [i for i in cv.find_withtag("fb_face") if cv.type(i) == "rectangle"][0]
        cv.tag_raise(bt)
        cv.tag_bind(tag, "<ButtonRelease-1>", lambda e: self.app.open_free_play())
        cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))
        cv.tag_bind("fb_btn", "<Enter>", lambda e: cv.itemconfigure(face, fill=C["face_hi"]))
        cv.tag_bind("fb_btn", "<Leave>", lambda e: cv.itemconfigure(face, fill=C["bg"]))
        return bottom

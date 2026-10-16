"""The activity picker: every activity is open. Tiers are a guide, shown as colours and filters."""
from __future__ import annotations

import tkinter as tk

from .onboarding import Screen, logo
from .theme import C, TIER_COLOURS
from .widgets import PButton, ScrollFrame, chip, label

CARD_MIN_WIDTH = 300


def stars_for(app, hints_used: int) -> int:
    if hints_used <= app.settings["three_star_max_hints"]:
        return 3
    if hints_used <= app.settings["two_star_max_hints"]:
        return 2
    return 1


class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        s = app.student
        self.filter = getattr(app, "home_filter", "all")
        self.cols = 0
        self.sections: list[tuple[str, tk.Frame, tk.Frame, list[tk.Frame]]] = []

        # ---- top bar
        bar = tk.Frame(self, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], padx=18, pady=10)
        bar.pack(fill="x")
        logo(bar, 40, bg=C["panel"]).pack(side="left")
        label(bar, app.settings["app_name"], font="h2", bg=C["panel"]).pack(side="left", padx=(8, 0))
        if app.teacher_mode:
            chip(bar, "TEACHER MODE", "#FFFFFF", C["info"]).pack(side="left", padx=12)
        right = tk.Frame(bar, bg=C["panel"])
        right.pack(side="right")
        PButton(right, "Switch student", app.logout, kind="ghost", font="small_bold").pack(side="right")
        who = tk.Frame(right, bg=C["panel"])
        who.pack(side="right", padx=14)
        label(who, s.first_name, font="ui_bold", bg=C["panel"]).pack(anchor="e")
        label(who, s.label, font="small", fg=C["muted"], bg=C["panel"]).pack(anchor="e")

        scroll = ScrollFrame(self, bg=C["bg"])
        scroll.pack(fill="both", expand=True)
        self.scroll = scroll
        body = tk.Frame(scroll.body, bg=C["bg"], padx=28, pady=20)
        body.pack(fill="both", expand=True)

        # ---- greeting + progress
        ready = [p for p in app.catalog.projects if p.get("status") == "ready"]
        done = sum(1 for p in ready if s.lesson_status(p["id"]) == "complete")
        head = tk.Frame(body, bg=C["bg"])
        head.pack(fill="x")
        label(head, f"Hi {s.first_name}! What would you like to make?", font="h1").pack(anchor="w")
        label(head, "Pick any activity you like. The colours are a guide to how tricky each one is.",
              fg=C["muted"], font="big").pack(anchor="w", pady=(2, 0))
        prog = tk.Frame(head, bg=C["bg"])
        prog.pack(anchor="w", pady=(12, 4))
        bar_bg = tk.Frame(prog, bg=C["line"], width=320, height=10)
        bar_bg.pack(side="left")
        bar_bg.pack_propagate(False)
        tk.Frame(bar_bg, bg=C["go"], width=int(320 * done / max(len(ready), 1)), height=10).place(x=0, y=0)
        label(prog, f"   {done} of {len(ready)} activities finished", font="small_bold", fg=C["muted"]).pack(side="left")

        # ---- filter chips
        self.chip_row = tk.Frame(body, bg=C["bg"])
        self.chip_row.pack(fill="x", pady=(16, 0))
        label(self.chip_row, "Show:", font="small_bold", fg=C["muted"]).pack(side="left", padx=(0, 8))
        self.chips: dict[str, tk.Label] = {}
        for key, text, col in [("all", "Everything", C["ink"])] + [
                (t["id"], t["title"], TIER_COLOURS.get(t["id"], C["accent"])) for t in app.catalog.tiers]:
            c = tk.Label(self.chip_row, text=f"  {text}  ", font="small_bold", cursor="hand2", pady=4,
                         highlightthickness=1)
            c.colour = col
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, k=key: self.set_filter(k))
            self.chips[key] = c

        # ---- tiers
        self.tier_area = tk.Frame(body, bg=C["bg"])
        self.tier_area.pack(fill="x")
        for tier in app.catalog.tiers:
            self._tier(self.tier_area, tier)
        self._free_build(body)
        self.tier_area.bind("<Configure>", self._relayout)
        self.set_filter(self.filter)

    # ------------------------------------------------------------------ filtering + layout
    def set_filter(self, key: str) -> None:
        if key not in self.chips:
            key = "all"
        self.filter = self.app.home_filter = key
        for k, c in self.chips.items():
            on = k == key
            c.configure(bg=c.colour if on else C["panel"], fg="#FFFFFF" if on else c.colour,
                        highlightbackground=c.colour if on else C["line"])
        for tier_id, sec, _grid, _cards in self.sections:
            if key in ("all", tier_id):
                sec.pack(fill="x", pady=(22, 0))
            else:
                sec.pack_forget()
        self.scroll.to_top()

    def _relayout(self, e=None) -> None:
        width = e.width if e else self.tier_area.winfo_width()
        cols = max(1, min(3, width // CARD_MIN_WIDTH))
        wrap = max(200, width // cols - 50)
        if cols == self.cols and abs(wrap - getattr(self, "_wrap", 0)) < 20:
            return
        self.cols, self._wrap = cols, wrap
        for _tier, _sec, grid, cards in self.sections:
            for f in cards:
                for lb in f.wrap_labels:
                    lb.configure(wraplength=wrap)
            for i in range(3):
                grid.grid_columnconfigure(i, weight=1 if i < cols else 0, uniform="cards" if i < cols else "")
            for i, f in enumerate(cards):
                r, c = divmod(i, cols)
                f.grid(row=r, column=c, sticky="nsew", padx=(0 if c == 0 else 6, 0 if c == cols - 1 else 6),
                       pady=(0, 12))

    # ------------------------------------------------------------------ tiers
    def _tier(self, master, tier):
        col = TIER_COLOURS.get(tier["id"], C["accent"])
        sec = tk.Frame(master, bg=C["bg"])
        h = tk.Frame(sec, bg=C["bg"])
        h.pack(fill="x")
        tk.Frame(h, bg=col, width=6, height=30).pack(side="left", padx=(0, 10))
        label(h, tier["title"], font="h2").pack(side="left")
        label(h, f"   {tier['tagline']}  ·  {tier['description']}", fg=C["muted"]).pack(side="left")
        grid = tk.Frame(sec, bg=C["bg"])
        grid.pack(fill="x", pady=(10, 0))
        cards = [self._card(grid, p, col) for p in self.app.catalog.projects_in(tier["id"])]
        self.sections.append((tier["id"], sec, grid, cards))

    def _card(self, master, p, col):
        app = self.app
        state = app.project_state(p)       # ready | in_progress | complete | planned
        lp = app.student.lesson(p["id"]) if state in ("in_progress", "complete") else None
        dim = state == "planned"
        f = tk.Frame(master, bg=C["panel"], highlightthickness=1,
                     highlightbackground=col if state == "in_progress" else C["line"], padx=16, pady=14)
        top = tk.Frame(f, bg=C["panel"])
        top.pack(fill="x")
        tier_title = next((t["title"] for t in app.catalog.tiers if t["id"] == p["tier"]), p["tier"])
        tk.Label(top, text=f" {tier_title.upper()} ", font="small_bold", fg="#FFFFFF",
                 bg=C["locked"] if dim else col).pack(side="left")
        if state == "complete":
            st = stars_for(app, lp.get("hints_used", 0))
            label(top, "★" * st + "☆" * (3 - st), font="ui_bold", fg="#E0A100", bg=C["panel"]).pack(side="right")
            chip(top, "DONE", C["ok"], C["ok_soft"]).pack(side="right", padx=6)
        elif state == "in_progress":
            steps = len(app.catalog.lesson(p["id"])["steps"])
            chip(top, f"STEP {lp['step'] + 1} OF {steps}", col, C["panel_alt"]).pack(side="right")
        elif state == "planned":
            chip(top, "COMING SOON", C["muted"], C["panel_alt"]).pack(side="right")

        label(f, p["title"], font="h3", fg=C["faint"] if dim else C["ink"], bg=C["panel"]).pack(anchor="w", pady=(10, 0))
        f.wrap_labels = []
        sub = label(f, p["subtitle"], fg=C["muted"], bg=C["panel"], wraplength=250)
        sub.pack(anchor="w", pady=(2, 8))
        concepts = label(f, "  ·  ".join(p["concepts"]), font="small", fg=C["faint"] if dim else C["info"],
                         bg=C["panel"], wraplength=250)
        concepts.pack(anchor="w")
        f.wrap_labels += [sub, concepts]
        needs = [n for n, on in (("GPIO kit", p.get("gpio")), ("camera", p.get("camera"))) if on]
        meta = f"≈ {p['minutes']} min   ·   help: {p['support']}"
        if needs:
            meta += "   ·   needs " + " + ".join(needs)
        meta_lb = label(f, meta, font="small", fg=C["muted"], bg=C["panel"], wraplength=250)
        meta_lb.pack(anchor="w", pady=(8, 0))
        f.wrap_labels.append(meta_lb)
        tip = self._try_first(p) if state == "ready" else None
        if tip:
            tip_lb = label(f, tip, font="small_bold", fg=C["warn"], bg=C["panel"], wraplength=250)
            tip_lb.pack(anchor="w", pady=(6, 0))
            f.wrap_labels.append(tip_lb)

        btn_row = tk.Frame(f, bg=C["panel"])
        btn_row.pack(fill="x", side="bottom", pady=(10, 0))
        if state == "ready":
            PButton(btn_row, "Start  ▸", lambda: app.open_lesson(p["id"]), kind="primary").pack(anchor="w")
        elif state == "in_progress":
            PButton(btn_row, "Continue  ▸", lambda: app.open_lesson(p["id"]), kind="primary").pack(anchor="w")
        elif state == "complete":
            PButton(btn_row, "Review", lambda: app.open_lesson(p["id"]), kind="secondary").pack(anchor="w")
        else:
            label(btn_row, "In the next version of PiPath", font="small_bold", fg=C["muted"],
                  bg=C["panel"]).pack(anchor="w", pady=4)
        return f

    def _try_first(self, p) -> str | None:
        """A friendly 'try this first' tip, until the student has finished that activity."""
        todo = [self.app.catalog.project(i) for i in p.get("try_first", [])]
        todo = [q for q in todo if q and q.get("status") == "ready"
                and self.app.student.lesson_status(q["id"]) != "complete"]
        if not todo:
            return None
        return "Good to try first: " + " or ".join(f"“{q['title']}”" for q in todo)

    # ------------------------------------------------------------------ free build
    def _free_build(self, master):
        app = self.app
        sec = tk.Frame(master, bg=C["ink"], padx=22, pady=18)
        sec.pack(fill="x", pady=(28, 10))
        txt = tk.Frame(sec, bg=C["ink"])
        txt.pack(side="left")
        label(txt, "Free Build", font="h2", fg="#FFFFFF", bg=C["ink"]).pack(anchor="w")
        label(txt, "Your own space to create anything, with the Simulator and the Coach. No steps. It's all you.",
              fg="#C9CED6", bg=C["ink"]).pack(anchor="w", pady=(4, 0))
        n = len(app.student.list_projects())
        if n:
            label(txt, f"{n} saved project{'s' if n != 1 else ''}", font="small_bold", fg=C["syn_def"],
                  bg=C["ink"]).pack(anchor="w", pady=(6, 0))
        PButton(sec, "Open Free Build  ▸", app.open_free_build, kind="primary").pack(side="right")

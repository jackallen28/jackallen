"""The project map: three tiers of projects plus Free Build."""
from __future__ import annotations

import tkinter as tk

from .onboarding import Screen, logo
from .theme import C, TIER_COLOURS
from .widgets import PButton, ScrollFrame, chip, label


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
        PButton(right, "Replay tour", lambda: app.open_lesson("s1_hello", tour=True),
                kind="ghost", font="small_bold").pack(side="right", padx=4)
        who = tk.Frame(right, bg=C["panel"])
        who.pack(side="right", padx=14)
        label(who, s.first_name, font="ui_bold", bg=C["panel"]).pack(anchor="e")
        label(who, s.label, font="small", fg=C["muted"], bg=C["panel"]).pack(anchor="e")

        scroll = ScrollFrame(self, bg=C["bg"])
        scroll.pack(fill="both", expand=True)
        body = tk.Frame(scroll.body, bg=C["bg"], padx=28, pady=20)
        body.pack(fill="both", expand=True)

        # ---- greeting + progress
        done = sum(1 for p in app.catalog.projects if s.lesson_status(p["id"]) == "complete")
        total = len(app.catalog.projects)
        head = tk.Frame(body, bg=C["bg"])
        head.pack(fill="x")
        label(head, f"Hi {s.first_name}! Pick a project.", font="h1").pack(anchor="w")
        label(head, "Projects unlock in order. Each one gives you a little less help than the last.",
              fg=C["muted"], font="big").pack(anchor="w", pady=(2, 0))
        prog = tk.Frame(head, bg=C["bg"])
        prog.pack(anchor="w", pady=(12, 4))
        bar_bg = tk.Frame(prog, bg=C["line"], width=320, height=10)
        bar_bg.pack(side="left")
        bar_bg.pack_propagate(False)
        tk.Frame(bar_bg, bg=C["go"], width=int(320 * done / max(total, 1)), height=10).place(x=0, y=0)
        label(prog, f"   {done} of {total} projects complete", font="small_bold", fg=C["muted"]).pack(side="left")

        # ---- tiers
        for tier in app.catalog.tiers:
            self._tier(body, tier)
        self._free_build(body)

    # ------------------------------------------------------------------ tiers
    def _tier(self, master, tier):
        col = TIER_COLOURS.get(tier["id"], C["accent"])
        sec = tk.Frame(master, bg=C["bg"])
        sec.pack(fill="x", pady=(22, 0))
        h = tk.Frame(sec, bg=C["bg"])
        h.pack(fill="x")
        tk.Frame(h, bg=col, width=6, height=30).pack(side="left", padx=(0, 10))
        label(h, tier["title"], font="h2").pack(side="left")
        label(h, f"   {tier['tagline']}  ·  {tier['description']}", fg=C["muted"]).pack(side="left")

        grid = tk.Frame(sec, bg=C["bg"])
        grid.pack(fill="x", pady=(10, 0))
        projects = self.app.catalog.projects_in(tier["id"])
        last = len(projects) - 1
        for i, p in enumerate(projects):
            grid.grid_columnconfigure(i, weight=1, uniform="cards")
            self._card(grid, p, col).grid(row=0, column=i, sticky="nsew",
                                          padx=(0 if i == 0 else 6, 0 if i == last else 6))

    def _card(self, master, p, col):
        app = self.app
        state = app.project_state(p)       # locked | ready | in_progress | complete | planned
        lp = app.student.lesson(p["id"]) if state in ("in_progress", "complete") else None
        dim = state in ("locked", "planned")
        f = tk.Frame(master, bg=C["panel"], highlightthickness=1,
                     highlightbackground=col if state == "in_progress" else C["line"], padx=16, pady=14)
        top = tk.Frame(f, bg=C["panel"])
        top.pack(fill="x")
        n = p["id"].split("_")[0].upper()
        tk.Label(top, text=f" {n} ", font="small_bold", fg="#FFFFFF",
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
        elif state == "locked":
            chip(top, "LOCKED", C["muted"], C["panel_alt"]).pack(side="right")

        label(f, p["title"], font="h3", fg=C["faint"] if dim else C["ink"], bg=C["panel"]).pack(anchor="w", pady=(10, 0))
        label(f, p["subtitle"], fg=C["muted"], bg=C["panel"], wraplength=260).pack(anchor="w", pady=(2, 8))
        label(f, "  ·  ".join(p["concepts"]), font="small", fg=C["faint"] if dim else C["info"],
              bg=C["panel"], wraplength=260).pack(anchor="w")
        meta = f"≈ {p['minutes']} min   ·   help: {p['support']}"
        if p.get("gpio"):
            meta += "   ·   needs GPIO kit"
        label(f, meta, font="small", fg=C["muted"], bg=C["panel"], wraplength=260).pack(anchor="w", pady=(8, 10))

        if state == "ready":
            PButton(f, "Start  ▸", lambda: app.open_lesson(p["id"]), kind="primary").pack(anchor="w")
        elif state == "in_progress":
            PButton(f, "Continue  ▸", lambda: app.open_lesson(p["id"]), kind="primary").pack(anchor="w")
        elif state == "complete":
            PButton(f, "Review", lambda: app.open_lesson(p["id"]), kind="secondary").pack(anchor="w")
        elif state == "locked":
            prev = app.catalog.project(p["unlock_after"]) if p.get("unlock_after") else app.previous_project(p)
            label(f, f"Finish “{prev['title']}” to unlock" if prev else "Locked",
                  font="small_bold", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=4)
        else:
            label(f, "In the next version of PiPath", font="small_bold", fg=C["muted"],
                  bg=C["panel"]).pack(anchor="w", pady=4)
        return f

    # ------------------------------------------------------------------ free build
    def _free_build(self, master):
        app = self.app
        unlocked = app.free_build_unlocked()
        sec = tk.Frame(master, bg=C["ink"], padx=22, pady=18)
        sec.pack(fill="x", pady=(28, 10))
        txt = tk.Frame(sec, bg=C["ink"])
        txt.pack(side="left")
        label(txt, "Free Build", font="h2", fg="#FFFFFF", bg=C["ink"]).pack(anchor="w")
        if unlocked:
            msg = "Your own space to create anything. The Coach still watches for errors, but there are no steps. It's all you."
        else:
            tier = app.settings["free_build_unlock"]
            msg = f"Finish all the {tier.title()} projects to unlock your own coding space."
        label(txt, msg, fg="#C9CED6", bg=C["ink"]).pack(anchor="w", pady=(4, 0))
        n = len(app.student.list_projects())
        if unlocked and n:
            label(txt, f"{n} saved project{'s' if n != 1 else ''}", font="small_bold", fg=C["syn_def"],
                  bg=C["ink"]).pack(anchor="w", pady=(6, 0))
        b = PButton(sec, "Open Free Build  ▸" if unlocked else "Locked", app.open_free_build,
                    kind="primary" if unlocked else "dark")
        b.pack(side="right")
        b.set_enabled(unlocked)

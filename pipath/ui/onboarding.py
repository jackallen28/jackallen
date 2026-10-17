"""First-run screens, in the retro look: Welcome (pick your name), New student(s) (one to four
first names + school) and Set up (how much help, and which activities to show)."""
from __future__ import annotations

import tkinter as tk

from .. import storage
from ..levels import INFO as LEVEL_INFO, LEVELS
from .theme import C
from .widgets import ChoiceList, CogButton, PButton, PixelMark, ScrollFrame, entry, label, logo_image, window

INITIAL_COLOURS = ["#704988", "#0B8F96", "#7E5B95", "#0A7E84", "#523468", "#3F6FB5"]   # dark enough for white letters


class Screen(tk.Frame):
    def __init__(self, app, bg: str | None = None):
        super().__init__(app, bg=bg or C["bg"])
        self.app = app


def desktop(screen: Screen) -> None:
    """The teal desktop: the logo's squares in the corner and the teacher hint."""
    PixelMark(screen, cell=10, bg=C["desk"]).place(x=18, y=16)
    label(screen, "Teachers: press Ctrl+Shift+T", font="small", fg="#D6F4F5", bg=C["desk"]).place(
        relx=1.0, rely=1.0, anchor="se", x=-14, y=-10)


def show_options(catalog) -> list:
    return [("all", "Everything", "Every activity"),
            ("hardware", "Hardware projects", "Anything you build with real parts")] + [
        (t["id"], t["title"], t["tagline"]) for t in catalog.tiers]


def level_options() -> list:
    return [(key, LEVEL_INFO[key][0], LEVEL_INFO[key][1]) for key in LEVELS]


# ====================================================================== welcome

class WelcomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app, bg=C["desk"])
        desktop(self)
        self.students = storage.list_students()
        win, body = window(self, f"{app.settings['app_name']}  -  Welcome", padx=20, pady=16)
        win.place(relx=.5, rely=.5, anchor="center")

        top = tk.Frame(body, bg="#FFFFFF", relief="sunken", bd=2, padx=14, pady=10)
        top.pack(fill="x")
        img = logo_image(self, "logo_full_200")
        if img is not None:
            tk.Label(top, image=img, bg="#FFFFFF").pack(side="left")
        words = tk.Frame(top, bg="#FFFFFF")
        words.pack(side="left", padx=(18, 0))
        label(words, app.settings["app_name"], font="h1", fg=C["purple"], bg="#FFFFFF").pack(anchor="w")
        label(words, app.settings["tagline"], font="ui", fg=C["muted"], bg="#FFFFFF", wraplength=240).pack(anchor="w")

        if self.students:
            label(body, "Who's coding today?", font="h3").pack(anchor="w", pady=(14, 2))
            label(body, "Click your name to carry on where you left off.", fg=C["muted"]).pack(anchor="w")
            if len(self.students) > 5:
                row = tk.Frame(body, bg=C["bg"])
                row.pack(fill="x", pady=(8, 0))
                label(row, "Find your name:", font="small_bold").pack(side="left")
                self.search = entry(row, width=20, font="ui")
                self.search.pack(side="left", padx=(8, 0))
                self.search.bind("<KeyRelease>", lambda e: self._fill())
            else:
                self.search = None
            well = tk.Frame(body, bg="#FFFFFF", relief="sunken", bd=2)
            well.pack(fill="x", pady=(8, 0))
            self.list = ScrollFrame(well, bg="#FFFFFF")
            self.list.canvas.configure(height=min(5, len(self.students)) * 46, width=470)
            self.list.pack(fill="x")
            self._fill()
            row = tk.Frame(body, bg=C["bg"])
            row.pack(fill="x", pady=(14, 0))
            PButton(row, "New student(s)...", lambda: app.show("profile"), kind="secondary").pack(side="left")
        else:
            label(body, "Let's get you set up. It only takes a moment.", font="big").pack(anchor="w", pady=(14, 2))
            label(body, "Type your first name (or all the names, if you're sharing this Pi) and your\n"
                        "school. Then choose how much help you want, and pick any activity.",
                  fg=C["muted"]).pack(anchor="w", pady=(0, 14))
            PButton(body, "Get started  ▸", lambda: app.show("profile"), kind="primary", font="h3",
                    pady=8).pack(anchor="e")

    def _fill(self) -> None:
        for w in self.list.body.winfo_children():
            w.destroy()
        q = self.search.get().strip().lower() if self.search else ""
        shown = [s for s in self.students if q in s.first_name.lower()]
        for i, s in enumerate(shown):
            self._student_row(self.list.body, s, i)
        if not shown:
            label(self.list.body, "No one with that name yet. Press New student(s).", fg=C["muted"],
                  bg="#FFFFFF", padx=10, pady=10).pack(anchor="w")

    def _student_row(self, master, s: storage.Student, i: int) -> None:
        row = tk.Frame(master, bg="#FFFFFF", cursor="hand2", padx=8, pady=5)
        row.pack(fill="x")
        initial = tk.Label(row, text=s.first_name[:1].upper(), font="h3", fg="#FFFFFF",
                           bg=INITIAL_COLOURS[i % len(INITIAL_COLOURS)], width=2, relief="raised", bd=2)
        initial.pack(side="left")
        txt = tk.Frame(row, bg="#FFFFFF")
        txt.pack(side="left", padx=10)
        label(txt, s.first_name, font="ui_bold", bg="#FFFFFF").pack(anchor="w")
        label(txt, s.label, font="small", fg=C["muted"], bg="#FFFFFF").pack(anchor="w")
        go = label(row, "Continue ▸", font="small_bold", fg=C["purple"], bg="#FFFFFF")
        go.pack(side="right")
        parts = (row, initial, txt, go, *txt.winfo_children())

        def light(on):
            for w in (row, txt, go, *txt.winfo_children()):
                w.configure(bg=C["accent_soft"] if on else "#FFFFFF")
        for w in parts:
            w.bind("<Button-1>", lambda e, st=s: self.app.login(st))
            w.bind("<Enter>", lambda e: light(True))
            w.bind("<Leave>", lambda e: light(False))


# ====================================================================== new student(s)

class ProfileScreen(Screen):
    """Step 1 of 2: first name(s) and school. Several students can share one profile."""

    def __init__(self, app):
        super().__init__(app, bg=C["desk"])
        desktop(self)
        pending = getattr(app, "pending_profile", None) or {}
        win, body = window(self, "New student(s)  -  Step 1 of 2", padx=24, pady=16)
        win.place(relx=.5, rely=.5, anchor="center")
        self.body = body

        label(body, "Who's working on this Pi?", font="h2", fg=C["purple"]).pack(anchor="w")
        label(body, "Type your first name. Sharing a Pi? Add everyone's first name.", fg=C["muted"]).pack(
            anchor="w", pady=(2, 10))
        self.names_box = tk.Frame(body, bg=C["bg"])
        self.names_box.pack(fill="x")
        self.name_rows: list[tuple[tk.Frame, tk.Entry, tk.Label]] = []
        for name in pending.get("names") or [""]:
            self._add_name(name)
        self.add_btn = PButton(body, "+ Add another student", self._add_name, kind="secondary",
                               font="small_bold", pady=3)
        self.add_btn.pack(anchor="w", pady=(2, 12))

        label(body, "Your school", font="ui_bold").pack(anchor="w")
        self.school = entry(body, width=34)
        self.school.pack(anchor="w", fill="x", ipady=3, pady=(4, 2))
        self.school.insert(0, pending.get("school", ""))
        self.school_msg = label(body, "So your teacher knows where your work came from.", font="small",
                                fg=C["muted"], wraplength=440)
        self.school_msg.pack(anchor="w", pady=(0, 10))
        self.school.bind("<Return>", lambda e: self.submit())

        note = tk.Frame(body, bg="#FFFFFF", relief="sunken", bd=2, padx=10, pady=6)
        note.pack(fill="x", pady=(0, 12))
        label(note, "Private: profiles are saved only on this Raspberry Pi. Nothing is sent online.",
              font="small", fg=C["info"], bg="#FFFFFF").pack(anchor="w")

        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x")
        PButton(row, "◂ Back", lambda: app.show("welcome"), kind="secondary").pack(side="left")
        PButton(row, "Next  ▸", self.submit, kind="primary").pack(side="right")
        self._update_add()
        self.after(100, lambda: self.name_rows[0][1].focus_set())

    @property
    def entries(self) -> dict:
        """The first name box and the school box (kept for older scripts and tests)."""
        return {"first_name": self.name_rows[0][1], "school": self.school}

    def _add_name(self, value: str = "") -> None:
        if len(self.name_rows) >= storage.MAX_NAMES:
            return
        n = len(self.name_rows)
        row = tk.Frame(self.names_box, bg=C["bg"])
        row.pack(fill="x", pady=(0, 4))
        label(row, f"Student {n + 1}" if n else "First name", font="small_bold", width=10).pack(side="left")
        e = entry(row, width=24)
        e.pack(side="left", ipady=3)
        e.insert(0, value)
        e.bind("<Return>", lambda ev: self.submit())
        msg = label(row, "", font="small", fg=C["err"], wraplength=200)
        if n:
            PButton(row, "✗", lambda r=row: self._remove(r), kind="secondary", font="small_bold", padx=6,
                    pady=1).pack(side="left", padx=(6, 0))
        msg.pack(side="left", padx=(8, 0))
        self.name_rows.append((row, e, msg))
        if value == "" and n:
            e.focus_set()
        self._update_add()

    def _remove(self, row) -> None:
        self.name_rows = [r for r in self.name_rows if r[0] is not row]
        row.destroy()
        self._update_add()

    def _update_add(self) -> None:
        if hasattr(self, "add_btn"):
            self.add_btn.set_enabled(len(self.name_rows) < storage.MAX_NAMES)

    def names(self) -> list[str]:
        return [e.get() for _r, e, _m in self.name_rows]

    def submit(self) -> None:
        names, school = self.names(), self.school.get()
        errors = storage.validate_names(names, school)
        filled = [n.strip() for n in names if n.strip()]
        if not errors and storage.find_student(filled, school):
            who = storage.join_names(filled)
            errors["name0"] = (f"{who} from this school already has a profile on this Pi. If that's you, press "
                               "Back and pick it. If not, add a surname initial, like \"Sam B\".")
        for i, (_row, e, msg) in enumerate(self.name_rows):
            msg.configure(text=("⚠ " + errors[f"name{i}"]) if f"name{i}" in errors else "")
            e.configure(highlightbackground=C["err"] if f"name{i}" in errors else C["bg"])
        if "school" in errors:
            self.school_msg.configure(text="⚠ " + errors["school"], fg=C["err"])
        else:
            self.school_msg.configure(text="So your teacher knows where your work came from.", fg=C["muted"])
        if errors:
            return
        self.app.pending_profile = {"names": filled, "school": school.strip()}
        self.app.show("setup")


# ====================================================================== set up

class SetupScreen(Screen):
    """Step 2 of 2: how much help, and which activities to show. Changeable later in Settings."""

    def __init__(self, app):
        super().__init__(app, bg=C["desk"])
        desktop(self)
        pending = getattr(app, "pending_profile", None) or {}
        win, body = window(self, "New student(s)  -  Step 2 of 2", padx=24, pady=14)
        win.place(relx=.5, rely=.5, anchor="center")
        who = storage.join_names(pending.get("names", [])) or "you"
        label(body, f"Nice to meet you, {who}!", font="h2", fg=C["purple"]).pack(anchor="w")

        label(body, "How much help do you want?", font="h3").pack(anchor="w", pady=(10, 2))
        self.level = ChoiceList(body, level_options(), pending.get("help_level", "beginner"), wrap=460)
        self.level.pack(anchor="w")

        label(body, "What do you want to see?", font="h3").pack(anchor="w", pady=(10, 2))
        self.show_choice = ChoiceList(body, show_options(app.catalog), pending.get("show", "all"), columns=2,
                                      wrap=210)
        self.show_choice.pack(anchor="w")

        tip = tk.Frame(body, bg=C["bg"])
        tip.pack(anchor="w", pady=(10, 12))
        label(tip, "You can change these any time with the", font="small", fg=C["muted"]).pack(side="left")
        CogButton(tip, lambda: None).pack(side="left", padx=6)
        label(tip, "button.", font="small", fg=C["muted"]).pack(side="left")

        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x")
        PButton(row, "◂ Back", self.back, kind="secondary").pack(side="left")
        PButton(row, "Start  ▸", self.finish, kind="primary").pack(side="right")

    def _remember(self) -> dict:
        pending = dict(getattr(self.app, "pending_profile", None) or {})
        pending.update(help_level=self.level.value, show=self.show_choice.value)
        self.app.pending_profile = pending
        return pending

    def back(self) -> None:
        self._remember()
        self.app.show("profile")

    def finish(self) -> None:
        p = self._remember()
        if not p.get("names"):
            self.app.show("profile")
            return
        self.app.pending_profile = None
        self.app.login(storage.create_student(p["names"], p.get("school", ""), help_level=p["help_level"],
                                              show=p["show"]))

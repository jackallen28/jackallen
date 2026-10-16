"""First-run screens: welcome / pick profile, and create profile (first name + school)."""
from __future__ import annotations

import tkinter as tk

from .. import storage
from .theme import C
from .widgets import PButton, card, label


class Screen(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C["bg"])
        self.app = app


def logo(master, size=64, bg=None):
    """A little raspberry-ish logo drawn with shapes (no image files needed)."""
    cv = tk.Canvas(master, width=size, height=size, bg=bg or master.cget("bg"), highlightthickness=0)
    s = size
    cv.create_oval(s * .12, s * .18, s * .88, s * .94, fill=C["accent"], outline="")
    for cx, cy in [(.35, .45), (.65, .45), (.5, .62), (.35, .75), (.65, .75), (.5, .40)]:
        cv.create_oval(s * (cx - .09), s * (cy - .09), s * (cx + .09), s * (cy + .09),
                       fill="#E2416F", outline="")
    cv.create_polygon(s * .5, s * .22, s * .3, s * .04, s * .44, s * .2, s * .5, s * .02,
                      s * .56, s * .2, s * .7, s * .04, fill=C["go"], outline="")
    cv.create_text(s * .5, s * .58, text="Py", fill="#FFFFFF", font=("DejaVu Sans", int(s * .22), "bold"))
    return cv


# ====================================================================== welcome

class WelcomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        students = storage.list_students()
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.place(relx=.5, rely=.46, anchor="center")

        logo(wrap, 96).pack()
        label(wrap, app.settings["app_name"], font="h1").pack(pady=(10, 2))
        label(wrap, app.settings["tagline"], font="big", fg=C["muted"]).pack()

        box = card(wrap, padx=26, pady=22)
        box.pack(pady=(28, 0), fill="x")
        if students:
            label(box, "Welcome back! Who's coding today?", font="h3", bg=C["panel"]).pack(anchor="w")
            label(box, "Choose your name to carry on where you left off.", fg=C["muted"],
                  bg=C["panel"]).pack(anchor="w", pady=(2, 12))
            lst = tk.Frame(box, bg=C["panel"])
            lst.pack(fill="x")
            for s in students[:8]:
                self._student_row(lst, s)
            if len(students) > 8:
                label(box, f"+ {len(students) - 8} more students on this Pi", font="small",
                      fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(6, 0))
            sep = tk.Frame(box, bg=C["line"], height=1)
            sep.pack(fill="x", pady=16)
            PButton(box, "I'm new here: create my profile", lambda: app.show("profile"),
                    kind="secondary").pack(fill="x")
        else:
            label(box, "Let's get you set up. It only takes a moment.", font="big",
                  bg=C["panel"]).pack(anchor="w")
            label(box, "Type your first name and school, then pick any activity you like.\n"
                       "Your work saves on this Pi as you go.", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(6, 18))
            PButton(box, "Get started  ▸", lambda: app.show("profile"), kind="primary",
                    font="h3", pady=10).pack(fill="x")

        label(self, "Teachers: press Ctrl+Shift+T", font="small", fg=C["faint"]).place(
            relx=1.0, rely=1.0, anchor="se", x=-14, y=-10)

    def _student_row(self, master, s: storage.Student):
        row = tk.Frame(master, bg=C["panel_alt"], highlightthickness=1, highlightbackground=C["line"],
                       cursor="hand2", padx=12, pady=8)
        row.pack(fill="x", pady=3)
        initial = tk.Label(row, text=s.first_name[:1].upper(), font="h3", fg="#FFFFFF",
                           bg=C["accent"], width=2)
        initial.pack(side="left")
        txt = tk.Frame(row, bg=C["panel_alt"])
        txt.pack(side="left", padx=12)
        label(txt, s.first_name, font="ui_bold", bg=C["panel_alt"]).pack(anchor="w")
        label(txt, s.label, font="small", fg=C["muted"], bg=C["panel_alt"]).pack(anchor="w")
        go = label(row, "Continue ▸", font="small_bold", fg=C["accent"], bg=C["panel_alt"])
        go.pack(side="right")
        for w in (row, initial, txt, go, *txt.winfo_children()):
            w.bind("<Button-1>", lambda e, st=s: self.app.login(st))
            w.configure(cursor="hand2")


# ====================================================================== profile

class ProfileScreen(Screen):
    FIELDS = [
        ("first_name", "Your first name", "Just your first name is fine."),
        ("school", "Your school", "So your teacher knows where your work came from."),
    ]

    def __init__(self, app):
        super().__init__(app)
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.place(relx=.5, rely=.48, anchor="center")

        box = card(wrap, padx=30, pady=24)
        box.pack()
        label(box, "Create your profile", font="h2", bg=C["panel"]).pack(anchor="w")
        label(box, "Your work will be saved under your name so you can come back to it.",
              fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(4, 16))

        self.entries: dict[str, tk.Entry] = {}
        self.msgs: dict[str, tk.Label] = {}
        for key, title, help_text in self.FIELDS:
            label(box, title, font="ui_bold", bg=C["panel"]).pack(anchor="w")
            e = tk.Entry(box, font="big", width=34, relief="flat", bg=C["panel_alt"],
                         highlightthickness=2, highlightbackground=C["line"], highlightcolor=C["accent"])
            e.pack(anchor="w", fill="x", ipady=6, pady=(4, 2))
            self.entries[key] = e
            m = label(box, help_text, font="small", fg=C["muted"], bg=C["panel"], wraplength=420)
            m.pack(anchor="w", pady=(0, 12))
            self.msgs[key] = m
            m.help_text = help_text
            e.bind("<Return>", lambda ev: self.submit())

        note = tk.Frame(box, bg=C["info_soft"], padx=12, pady=8)
        note.pack(fill="x", pady=(2, 16))
        label(note, "Private: your profile is saved only on this Raspberry Pi. Nothing is sent online.",
              font="small", fg=C["info"], bg=C["info_soft"]).pack(anchor="w")

        row = tk.Frame(box, bg=C["panel"])
        row.pack(fill="x")
        PButton(row, "◂ Back", lambda: app.show("welcome"), kind="ghost").pack(side="left")
        PButton(row, "Let's go  ▸", self.submit, kind="primary").pack(side="right")
        self.after(100, lambda: self.entries["first_name"].focus_set())

    def _show_errors(self, errors: dict[str, str]) -> None:
        for k, m in self.msgs.items():
            if k in errors:
                m.configure(text="⚠ " + errors[k], fg=C["err"])
                self.entries[k].configure(highlightbackground=C["err"])
            else:
                m.configure(text=m.help_text, fg=C["muted"])
                self.entries[k].configure(highlightbackground=C["line"])

    def submit(self):
        name, school = self.entries["first_name"].get(), self.entries["school"].get()
        errors = storage.validate_profile(name, school)
        if not errors and storage.find_student(name, school):
            errors["first_name"] = (f"There's already a {name.strip()} from this school on this Pi. If that's you, "
                                    "press Back and pick your name. If not, add the first letter of your "
                                    f"surname, like \"{name.strip()} B\".")
        self._show_errors(errors)
        if errors:
            return
        self.app.login(storage.create_student(name, school))

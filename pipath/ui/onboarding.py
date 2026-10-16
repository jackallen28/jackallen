"""First-run screens: welcome / pick profile, create profile, intro slides."""
from __future__ import annotations

import tkinter as tk

from .. import storage
from .theme import C
from .widgets import PButton, RichText, card, label


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
            label(box, "Let's get you set up. It takes about one minute.", font="big",
                  bg=C["panel"]).pack(anchor="w")
            label(box, "You'll make a profile so your projects save, take a quick look around,\n"
                       "then start your very first program.", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(6, 18))
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
        ("first_name", "Your first name", "Just your first name is fine.", True),
        ("school", "Your school", "So your teacher knows where your projects came from.", True),
        ("class_code", "Your class or group (optional)", "For example 8B, Room 12 or STEM Club.", False),
    ]

    def __init__(self, app):
        super().__init__(app)
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.place(relx=.5, rely=.48, anchor="center")

        steps = tk.Frame(wrap, bg=C["bg"])
        steps.pack(anchor="w", pady=(0, 10))
        for i, name in enumerate(["Your profile", "How it works", "Quick tour"]):
            active = i == 0
            tk.Label(steps, text=f" {i + 1} ", font="small_bold", fg="#FFFFFF",
                     bg=C["accent"] if active else C["locked"]).pack(side="left")
            label(steps, f" {name}    ", font="small_bold" if active else "small",
                  fg=C["ink"] if active else C["muted"]).pack(side="left")

        box = card(wrap, padx=30, pady=24)
        box.pack()
        label(box, "Create your profile", font="h2", bg=C["panel"]).pack(anchor="w")
        label(box, "Your projects will be saved under your name so you can come back to them.",
              fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(4, 16))

        self.entries: dict[str, tk.Entry] = {}
        self.msgs: dict[str, tk.Label] = {}
        for key, title, help_text, required in self.FIELDS:
            label(box, title, font="ui_bold", bg=C["panel"]).pack(anchor="w")
            e = tk.Entry(box, font="big", width=34, relief="flat", bg=C["panel_alt"],
                         highlightthickness=2, highlightbackground=C["line"], highlightcolor=C["accent"])
            e.pack(anchor="w", fill="x", ipady=6, pady=(4, 2))
            self.entries[key] = e
            m = label(box, help_text, font="small", fg=C["muted"], bg=C["panel"])
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
        PButton(row, "Create my profile  ▸", self.submit, kind="primary").pack(side="right")
        self.after(100, lambda: self.entries["first_name"].focus_set())

    def submit(self):
        vals = {k: e.get() for k, e in self.entries.items()}
        errors = storage.validate_profile(vals["first_name"], vals["school"], vals["class_code"])
        for k, m in self.msgs.items():
            if k in errors:
                m.configure(text="⚠ " + errors[k], fg=C["err"])
                self.entries[k].configure(highlightbackground=C["err"])
            else:
                m.configure(text=m.help_text, fg=C["muted"])
                self.entries[k].configure(highlightbackground=C["line"])
        if errors:
            return
        s = storage.create_student(vals["first_name"], vals["school"], vals["class_code"])
        self.app.login(s, new=True)


# ====================================================================== intro slides

SLIDES = [
    {
        "glyph": "{ }", "colour": C["info"],
        "title": "Coding is giving instructions",
        "text": "A program is a list of instructions. Python reads them **from the top down, one line at a time**, and does exactly what they say (even when it's not what you meant!).",
    },
    {
        "glyph": "▶", "colour": C["go"],
        "title": "Write it. Run it. Check it.",
        "text": "Type code in the **editor**, press the green **Run** button, and see what happens in the **Output**.\n\nEach step has a short **checklist**. When every box is ticked, you move on.",
    },
    {
        "glyph": "?", "colour": C["warn"],
        "title": "Errors are clues, not failures",
        "text": "Every programmer's code breaks, all the time. When yours does, the **Coach** explains what went wrong in plain English and points to the line.\n\nNeed help? Hints start small. Try the first one before asking for more.",
    },
    {
        "glyph": "★", "colour": C["accent"],
        "title": "You'll get more independent",
        "text": "The first projects guide you closely. Later ones give you **less help** so you can show what you know.\n\nFinish the projects to unlock **Free Build**, where you make anything you like. Your work **saves automatically**.",
    },
]


class IntroScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.i = 0
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.place(relx=.5, rely=.48, anchor="center")

        steps = tk.Frame(wrap, bg=C["bg"])
        steps.pack(anchor="w", pady=(0, 10))
        for i, name in enumerate(["Your profile", "How it works", "Quick tour"]):
            active = i == 1
            tk.Label(steps, text=" ✓ " if i == 0 else f" {i + 1} ", font="small_bold", fg="#FFFFFF",
                     bg=C["ok"] if i == 0 else (C["accent"] if active else C["locked"])).pack(side="left")
            label(steps, f" {name}    ", font="small_bold" if active else "small",
                  fg=C["ink"] if active else C["muted"]).pack(side="left")

        box = card(wrap, padx=34, pady=26)
        box.pack()
        label(box, f"Hi {app.student.first_name}! Here's how {app.settings['app_name']} works.",
              font="small_bold", fg=C["accent"], bg=C["panel"]).pack(anchor="w")
        inner = tk.Frame(box, bg=C["panel"])
        inner.pack(fill="x", pady=(14, 0))
        self.glyph = tk.Canvas(inner, width=120, height=120, bg=C["panel"], highlightthickness=0)
        self.glyph.pack(side="left", anchor="n")
        txt = tk.Frame(inner, bg=C["panel"])
        txt.pack(side="left", fill="both", padx=(22, 0))
        self.title = label(txt, "", font="h2", bg=C["panel"])
        self.title.pack(anchor="w")
        self.body = RichText(txt, bg=C["panel"], width=46, font="big")
        self.body.tag_configure("b", font="big_bold")
        self.body.pack(anchor="w", pady=(8, 0))

        foot = tk.Frame(box, bg=C["panel"])
        foot.pack(fill="x", pady=(22, 0))
        self.dots = tk.Frame(foot, bg=C["panel"])
        self.dots.pack(side="left")
        self.next = PButton(foot, "Next ▸", self.forward, kind="primary")
        self.next.pack(side="right")
        self.back = PButton(foot, "◂ Back", self.backward, kind="ghost")
        self.back.pack(side="right", padx=6)
        self.bind_all("<Right>", lambda e: self.forward())
        self.bind_all("<Left>", lambda e: self.backward())
        self._render()

    def destroy(self):
        self.unbind_all("<Right>")
        self.unbind_all("<Left>")
        super().destroy()

    def _render(self):
        s = SLIDES[self.i]
        cv = self.glyph
        cv.delete("all")
        cv.create_oval(6, 6, 114, 114, fill=s["colour"], outline="")
        cv.create_text(60, 60, text=s["glyph"], fill="#FFFFFF", font="glyph")
        self.title.configure(text=s["title"])
        self.body.render(s["text"])
        for w in self.dots.winfo_children():
            w.destroy()
        for j in range(len(SLIDES)):
            tk.Frame(self.dots, width=22 if j == self.i else 8, height=8,
                     bg=C["accent"] if j == self.i else C["line"]).pack(side="left", padx=3)
        self.back.set_enabled(self.i > 0)
        last = self.i == len(SLIDES) - 1
        self.next.configure(text="Take the tour  ▸" if last else "Next ▸")

    def forward(self):
        if self.i < len(SLIDES) - 1:
            self.i += 1
            self._render()
        else:
            self.app.open_lesson("s1_hello", tour=True)

    def backward(self):
        if self.i > 0:
            self.i -= 1
            self._render()

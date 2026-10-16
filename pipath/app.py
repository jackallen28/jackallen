"""PiPath main window: screen routing, activity states and the teacher panel."""
from __future__ import annotations

import tkinter as tk

from . import storage
from .content import Catalog, load_config
from .hints import HintEngine
from .ui.home import HomeScreen
from .ui.onboarding import ProfileScreen, WelcomeScreen
from .ui.theme import C, setup_fonts
from .ui.widgets import PButton, card, label
from .ui.workspace import FreeBuildWorkspace, LessonWorkspace


class PiPathApp(tk.Tk):
    def __init__(self, scale: float = 1.0):
        super().__init__(className="PiPath")
        self.settings = load_config()
        self.catalog = Catalog()
        self.engine = HintEngine()
        self.student: storage.Student | None = None
        self.teacher_mode = False
        self.screen: tk.Frame | None = None

        self.title(self.settings["app_name"])
        self.configure(bg=C["bg"])
        setup_fonts(self, scale)
        self.minsize(1024, 640)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1366, sw - 40), min(800, sh - 80)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        if sw <= 1440:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass
        self.option_add("*Entry.relief", "flat")
        self.bind_all("<Control-Shift-T>", lambda e: self.teacher_panel())
        self.bind_all("<Control-Shift-t>", lambda e: self.teacher_panel())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.show("welcome")

    # ------------------------------------------------------------------ routing
    def _swap(self, screen: tk.Frame) -> None:
        if self.screen is not None:
            self.screen.destroy()
        self.screen = screen
        screen.pack(fill="both", expand=True)

    def show(self, name: str) -> None:
        screens = {"welcome": WelcomeScreen, "profile": ProfileScreen, "home": HomeScreen}
        self._swap(screens[name](self))

    def login(self, s: storage.Student) -> None:
        self.student = s
        storage.touch_student(s)
        self.show("home")

    def logout(self) -> None:
        self.student = None
        self.teacher_mode = False
        self.show("welcome")

    def open_lesson(self, lesson_id: str, tour: bool = False) -> None:
        self._swap(LessonWorkspace(self, lesson_id, tour=tour))

    def open_free_build(self) -> None:
        self._swap(FreeBuildWorkspace(self))

    def quit_app(self) -> None:
        if self.screen is not None:
            self.screen.destroy()
            self.screen = None
        self.destroy()

    # ------------------------------------------------------------------ activity state
    def project_state(self, p: dict) -> str:
        """planned | ready | in_progress | complete. Nothing is locked: students choose freely."""
        if p.get("status") != "ready":
            return "planned"
        status = self.student.lesson_status(p["id"])
        return status if status in ("complete", "in_progress") else "ready"

    # ------------------------------------------------------------------ teacher panel
    def teacher_panel(self) -> None:
        if getattr(self, "_teacher_overlay", None) and self._teacher_overlay.winfo_exists():
            return
        ov = tk.Frame(self, bg="#0E1116")
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._teacher_overlay = ov
        box = card(ov, padx=26, pady=22)
        box.place(relx=.5, rely=.45, anchor="center")
        label(box, "Teacher panel", font="h2", bg=C["panel"]).pack(anchor="w")
        body = tk.Frame(box, bg=C["panel"])
        body.pack(fill="x", pady=(10, 0))

        def close():
            ov.destroy()

        def unlocked():
            for w in body.winfo_children():
                w.destroy()
            label(body, "Teacher mode lets you skip ahead: Next step is always enabled, for this session only.",
                  fg=C["muted"], bg=C["panel"], wraplength=380).pack(anchor="w")
            PButton(body, "Teacher mode: " + ("ON (turn off)" if self.teacher_mode else "OFF (turn on)"),
                    toggle, kind="primary").pack(anchor="w", pady=(6, 14))
            label(body, "Export every student's progress on this Pi to a CSV file.", fg=C["muted"],
                  bg=C["panel"]).pack(anchor="w")
            msg = label(body, "", font="small", fg=C["ok"], bg=C["panel"], wraplength=380)
            PButton(body, "Export progress CSV", lambda: msg.configure(
                text=f"Saved to {storage.export_progress_csv(self.catalog.projects)}"), kind="secondary").pack(anchor="w", pady=(6, 4))
            msg.pack(anchor="w")
            PButton(body, "Close", close, kind="ghost").pack(anchor="e", pady=(14, 0))

        def toggle():
            self.teacher_mode = not self.teacher_mode
            close()
            if self.student:
                self.show("home")

        label(body, "Enter the teacher PIN (set in data/config.toml)", fg=C["muted"], bg=C["panel"]).pack(anchor="w")
        pin = tk.Entry(body, show="●", font="h3", width=10, bg=C["panel_alt"], highlightthickness=2,
                       highlightbackground=C["line"], highlightcolor=C["accent"])
        pin.pack(anchor="w", pady=8, ipady=4)
        err = label(body, "", font="small", fg=C["err"], bg=C["panel"])
        err.pack(anchor="w")

        def check(_e=None):
            if pin.get() == str(self.settings["teacher_pin"]):
                unlocked()
            else:
                err.configure(text="Wrong PIN")
                pin.delete(0, "end")

        pin.bind("<Return>", check)
        pin.bind("<Escape>", lambda e: close())
        row = tk.Frame(body, bg=C["panel"])
        row.pack(fill="x", pady=(10, 0))
        PButton(row, "Cancel", close, kind="ghost").pack(side="left")
        PButton(row, "Unlock", check, kind="primary").pack(side="right")
        pin.focus_set()

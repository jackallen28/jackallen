"""PiPath main window: screen routing, activity states and the teacher panel."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
import tkinter.font as tkfont

from . import storage
from .content import Catalog, load_config
from .hints import HintEngine
from .ui.home import HomeScreen
from .ui.onboarding import ProfileScreen, SetupScreen, WelcomeScreen
from .ui.settings import SettingsDialog
from .ui.theme import C, setup_fonts, CODE_SIZE
from .ui.widgets import PButton, TitleBar, entry, label
from .ui.workspace import FreePlayWorkspace, LessonWorkspace


class PiPathApp(tk.Tk):
    def __init__(self, scale: float = 1.0):
        super().__init__(className="PiPath")
        self.settings = load_config()
        self.catalog = Catalog()
        self._engine: HintEngine | None = None
        self.student: storage.Student | None = None
        self.teacher_mode = False
        self.screen: tk.Frame | None = None
        self.pending_profile: dict | None = None     # a new profile between "New student(s)" and "Set up"
        self._settings: SettingsDialog | None = None
        # Kept between visits, because building them is the slowest thing on a Pi 3B:
        self._home: HomeScreen | None = None
        self._lesson_ws: LessonWorkspace | None = None     # re-used for every activity
        self._free_ws: FreePlayWorkspace | None = None

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
        for key, value in (("background", C["bg"]), ("troughColor", "#DFDFDF"), ("activeBackground", C["face_hi"]),
                           ("relief", "raised"), ("borderWidth", 2), ("elementBorderWidth", 2),
                           ("highlightThickness", 0), ("width", 16)):
            self.option_add(f"*Scrollbar.{key}", value)    # chunky grey Windows 95 scrollbars
        self.bind_all("<Control-Shift-T>", lambda e: self.teacher_panel())
        self.bind_all("<Control-Shift-t>", lambda e: self.teacher_panel())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.show("welcome")

    @property
    def engine(self) -> HintEngine:
        """The Coach's error database, loaded the first time a program needs explaining."""
        if self._engine is None:
            self._engine = HintEngine()
        return self._engine

    # ------------------------------------------------------------------ routing
    def _kept(self) -> list:
        return [s for s in (self._home, self._lesson_ws, self._free_ws) if s is not None]

    def _swap(self, screen: tk.Frame) -> None:
        old = self.screen
        if old is not None and old is not screen:
            if old in self._kept():
                old.hide()            # kept for next time
            else:
                old.destroy()
        self.screen = screen
        screen.pack(fill="both", expand=True)
        if hasattr(screen, "on_show"):
            screen.on_show()

    def forget_screens(self) -> None:
        """Another student (or teacher mode) means the kept screens are made again next time."""
        kept = self._kept()
        self._home = self._lesson_ws = self._free_ws = None
        for s in kept:
            if s is not self.screen:
                s.destroy()           # the one on show goes at the next _swap

    def show(self, name: str) -> None:
        if name == "home":
            if self._home is None:
                self._home = HomeScreen(self)
            else:
                self._home.refresh()
            self._swap(self._home)
            return
        screens = {"welcome": WelcomeScreen, "profile": ProfileScreen, "setup": SetupScreen}
        self._swap(screens[name](self))

    def login(self, s: storage.Student) -> None:
        self.forget_screens()
        self.pending_profile = None
        self.student = s
        storage.touch_student(s)
        size = s.profile.get("code_size")
        if not (isinstance(size, int) and 9 <= size <= 26):
            size = CODE_SIZE["value"]          # not the last student's size
        tkfont.nametofont("code").configure(size=size)
        self.show("home")

    def logout(self) -> None:
        self.close_settings()
        self.forget_screens()
        self.student = None
        self.teacher_mode = False
        self.show("welcome")

    # ------------------------------------------------------------------ settings (the cog)
    def open_settings(self, tab: str = "help") -> None:
        if self.student is None or self.overlay_open():
            return
        self.end_tour()                        # a tour bubble can't sit on top of the dialog
        if self._settings is not None and self._settings.winfo_exists():
            self._settings.show_tab(tab)
            self._settings.lift()
            return
        self._settings = SettingsDialog(self, tab)

    def overlay_open(self) -> bool:
        ov = getattr(self, "_teacher_overlay", None)
        return bool(ov is not None and ov.winfo_exists())

    def end_tour(self) -> None:
        tour = getattr(self.screen, "_tour", None)
        if tour is not None:
            tour.finish()

    def busy_with_dialog(self) -> bool:
        """Settings or the teacher panel is open: keys like F5 shouldn't reach the screen behind."""
        return self.overlay_open() or (self._settings is not None and self._settings.winfo_exists())

    def close_settings(self) -> None:
        if self._settings is not None and self._settings.winfo_exists():
            self._settings.close()
        self._settings = None

    def settings_changed(self, what: str) -> None:
        """A setting changed: every kept screen updates itself (help, show, names, hardware, text)."""
        for screen in dict.fromkeys(self._kept() + ([self.screen] if self.screen is not None else [])):
            if hasattr(screen, "settings_changed") and screen.winfo_exists():
                screen.settings_changed(what)

    def open_lesson(self, lesson_id: str, tour: bool = False) -> None:
        if self._lesson_ws is None:
            self._lesson_ws = LessonWorkspace(self, lesson_id, tour=tour)
        else:
            self._lesson_ws.load(lesson_id, tour=tour)
        self._swap(self._lesson_ws)

    def open_free_play(self) -> None:
        if self._free_ws is None:
            self._free_ws = FreePlayWorkspace(self)
        else:
            self._free_ws.reopen()
        self._swap(self._free_ws)

    open_free_build = open_free_play        # the old name

    def quit_app(self) -> None:
        screens = self._kept() + ([self.screen] if self.screen is not None else [])
        self._home = self._lesson_ws = self._free_ws = self.screen = None
        for s in dict.fromkeys(screens):      # each once
            s.destroy()
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
        if self.overlay_open():
            return
        self.close_settings()                  # its grab would swallow the panel's clicks
        self.end_tour()
        ov = tk.Frame(self, bg=C["desk"])          # the teal desktop, covering the student's screen
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._teacher_overlay = ov
        box = tk.Frame(ov, bg=C["bg"], relief="raised", bd=2)
        box.place(relx=.5, rely=.45, anchor="center")
        TitleBar(box, "Teacher panel", height=22, close=lambda: ov.destroy()).pack(fill="x", padx=2, pady=(2, 0))
        body = tk.Frame(box, bg=C["bg"], padx=24, pady=16)
        body.pack(fill="x")

        def close():
            ov.destroy()

        def unlocked():
            for w in body.winfo_children():
                w.destroy()
            label(body, "Teacher mode lets you skip ahead: Next step is always enabled, for this session only.",
                  fg=C["muted"], wraplength=400).pack(anchor="w")
            PButton(body, "Teacher mode: " + ("ON (turn off)" if self.teacher_mode else "OFF (turn on)"),
                    toggle, kind="primary").pack(anchor="w", pady=(6, 14))
            label(body, "Export every student's progress on this Pi to a CSV file.", fg=C["muted"]).pack(anchor="w")
            msg = label(body, "", font="small", fg=C["ok"], wraplength=400)
            PButton(body, "Export progress CSV", lambda: msg.configure(
                text=f"Saved to {storage.export_progress_csv(self.catalog.projects)}"), kind="secondary").pack(
                anchor="w", pady=(6, 4))
            msg.pack(anchor="w")
            label(body, "New school or group? Wipe every student's profile and work from this Pi.",
                  fg=C["muted"], wraplength=400).pack(anchor="w", pady=(14, 0))
            PButton(body, "Wipe all student data...", wipe_view, kind="stop").pack(anchor="w", pady=(6, 4))
            PButton(body, "Close", close, kind="secondary").pack(anchor="e", pady=(14, 0))

        def wipe_view():
            for w in body.winfo_children():
                w.destroy()
            info = storage.wipe_summary()
            label(body, "⚠ Wipe all student data", font="h3", fg=C["err"]).pack(anchor="w")
            if not info["students"] and not info["exports"]:
                label(body, "There's no student data on this Pi. It's ready for a new group.",
                      wraplength=420).pack(anchor="w", pady=(6, 0))
                PButton(body, "Back", unlocked, kind="secondary").pack(anchor="e", pady=(14, 0))
                return
            who = f"{info['students']} student profile{'s' if info['students'] != 1 else ''}"
            if info["schools"]:
                who += " (" + ", ".join(info["schools"][:3]) + ("..." if len(info["schools"]) > 3 else "") + ")"
            label(body, f"This deletes {who}: their progress, code, photos and Free Play projects "
                        f"({info['files']} files). Students will start again from the welcome screen. "
                        "The Pi's settings (Simulator / Real Pi, camera) stay. This can't be undone.",
                  wraplength=420).pack(anchor="w", pady=(6, 8))
            exports = tk.BooleanVar(value=True)
            if info["exports"]:
                tk.Checkbutton(body, text=f"Also delete the exported progress files ({info['exports']})",
                               variable=exports, font="small", bg=C["bg"], activebackground=C["bg"],
                               selectcolor="#FFFFFF", anchor="w").pack(anchor="w")
            drives = storage.usb_drives()
            dest = (drives[0] if drives else Path.home()) / "PiPath-backups"
            saved = label(body, "", font="small", fg=C["ok"], wraplength=420)

            def backup():
                try:
                    saved.configure(text=f"✓ Backup saved: {storage.backup_zip(dest)}", fg=C["ok"])
                except OSError as e:
                    saved.configure(text=f"Couldn't save the backup: {e}", fg=C["err"])

            PButton(body, "Save a backup first" + (" (to the USB stick)" if drives else ""), backup,
                    kind="secondary", font="small_bold").pack(anchor="w", pady=(8, 2))
            saved.configure(text=f"Optional. It goes in {dest}" + ("" if drives else
                            " (plug in a USB stick first to save it there)."), fg=C["muted"])
            saved.pack(anchor="w")
            label(body, "To confirm, type WIPE in the box:", fg=C["muted"]).pack(anchor="w", pady=(12, 0))
            typed = entry(body, width=10, font="h3")
            typed.pack(anchor="w", pady=4, ipady=2)
            row = tk.Frame(body, bg=C["bg"])
            row.pack(fill="x", pady=(10, 0))
            PButton(row, "Cancel", unlocked, kind="secondary").pack(side="left")
            go = PButton(row, "Wipe now", lambda: wipe(exports.get()), kind="stop")
            go.pack(side="right", padx=(40, 0))
            go.set_enabled(False)
            typed.bind("<KeyRelease>", lambda e: go.set_enabled(typed.get().strip().upper() == "WIPE"))
            typed.bind("<Escape>", lambda e: unlocked())
            typed.focus_set()

        def wipe(delete_exports: bool):
            if self.student is not None:
                self.logout()                  # stops any running program and drops the kept screens
            storage.wipe_all(keep_exports=not delete_exports)
            self.teacher_mode = False
            self.pending_profile = None
            self.show("welcome")               # without the old names on it
            ov.lift()
            for w in body.winfo_children():
                w.destroy()
            label(body, "✓ All student data has been wiped.", font="h3", fg=C["ok"]).pack(anchor="w")
            label(body, "PiPath is ready for a new group. Students make a new profile on the welcome screen.",
                  wraplength=420).pack(anchor="w", pady=(6, 0))
            PButton(body, "Close", close, kind="primary").pack(anchor="e", pady=(14, 0))

        def toggle():
            self.teacher_mode = not self.teacher_mode
            close()
            if self.student:
                self.forget_screens()
                self.show("home")

        label(body, "Enter the teacher PIN (set in data/config.toml)", fg=C["muted"]).pack(anchor="w")
        pin = entry(body, width=10, font="h3", show="●")
        pin.pack(anchor="w", pady=8, ipady=2)
        err = label(body, "", font="small", fg=C["err"])
        err.pack(anchor="w")

        def check(_e=None):
            if pin.get() == str(self.settings["teacher_pin"]):
                unlocked()
            else:
                err.configure(text="Wrong PIN")
                pin.delete(0, "end")

        pin.bind("<Return>", check)
        pin.bind("<Escape>", lambda e: close())
        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x", pady=(10, 0))
        PButton(row, "Cancel", close, kind="secondary").pack(side="left")
        PButton(row, "Unlock", check, kind="primary").pack(side="right", padx=(40, 0))
        pin.focus_set()

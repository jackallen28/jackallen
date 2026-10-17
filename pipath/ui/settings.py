"""The Settings window, opened with the cog on any screen: a Windows 95 style tabbed dialog.

Tabs: Help (how much help), Show (which activities the picker shows), Students (the names),
Hardware (Simulator or Real Pi, camera), Text size. Changes apply straight away; the app tells
every kept screen (app.settings_changed).
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from .. import storage
from ..gpio import CAMERA_KINDS, on_real_pi
from .onboarding import level_options, show_options
from .theme import C
from .widgets import ChoiceList, PButton, TitleBar, entry, label

TABS = [("help", "Help"), ("show", "Show"), ("students", "Students"), ("hardware", "Hardware"),
        ("text", "Text size")]


class SettingsDialog(tk.Frame):
    def __init__(self, app, tab: str = "help"):
        super().__init__(app, bg=C["bg"], relief="raised", bd=2)
        self.app = app
        TitleBar(self, "Settings", height=24).pack(fill="x", padx=1, pady=(1, 0))
        tabs = tk.Frame(self, bg=C["bg"], padx=10)
        tabs.pack(fill="x", pady=(8, 0))
        self.tabs: dict[str, tk.Label] = {}
        for key, text in TABS:
            t = tk.Label(tabs, text=f"  {text}  ", font="small_bold", bg=C["bg"], fg=C["ink"], relief="raised",
                         bd=2, padx=4, pady=3, cursor="hand2")
            t.pack(side="left")
            t.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tabs[key] = t
        self.page = tk.Frame(self, bg=C["bg"], relief="raised", bd=2, padx=18, pady=14, width=560, height=330)
        self.page.pack(fill="both", expand=True, padx=10)
        self.page.pack_propagate(False)
        foot = tk.Frame(self, bg=C["bg"], padx=10, pady=10)
        foot.pack(fill="x")
        label(foot, "Changes are saved straight away.", font="small", fg=C["muted"]).pack(side="left")
        PButton(foot, "Done", self.close, kind="primary").pack(side="right")
        self.place(relx=.5, rely=.5, anchor="center")
        self.lift()
        self.bind_all("<Escape>", lambda e: self.close())
        self.show_tab(tab)
        try:
            self.grab_set()           # like a real dialog: the screen behind waits until you close it
        except tk.TclError:
            pass

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.unbind_all("<Escape>")
        self.destroy()

    # ---------------------------------------------------------------- tabs
    def show_tab(self, key: str) -> None:
        for k, t in self.tabs.items():
            on = k == key
            t.configure(relief="sunken" if on else "raised", bg="#FFFFFF" if on else C["bg"],
                        fg=C["purple"] if on else C["ink"])
        for w in self.page.winfo_children():
            w.destroy()
        getattr(self, f"_tab_{key}")(self.page)

    def _tab_help(self, page) -> None:
        student = self.app.student
        label(page, "How much help do you want?", font="h3").pack(anchor="w")
        label(page, "Change it whenever you like. Stars still count the hints you open.", font="small",
              fg=C["muted"]).pack(anchor="w", pady=(0, 8))
        ChoiceList(page, level_options(), student.help_level, wrap=440,
                   on_change=lambda k: (student.set_help_level(k), self.app.settings_changed("help"))).pack(anchor="w")

    def _tab_show(self, page) -> None:
        student = self.app.student
        label(page, "What do you want to see on the activity picker?", font="h3").pack(anchor="w")
        label(page, "Everything stays open. This just keeps the list short.", font="small",
              fg=C["muted"]).pack(anchor="w", pady=(0, 8))
        ChoiceList(page, show_options(self.app.catalog), student.show, columns=2, wrap=200,
                   on_change=lambda k: (student.set_show(k), self.app.settings_changed("show"))).pack(anchor="w")

    def _tab_students(self, page) -> None:
        student = self.app.student
        label(page, "Who's working on this Pi?", font="h3").pack(anchor="w")
        label(page, f"School: {student.profile.get('school', '')}", font="small", fg=C["muted"]).pack(anchor="w",
                                                                                                    pady=(0, 8))
        self.name_entries = []
        box = tk.Frame(page, bg=C["bg"])
        box.pack(anchor="w")
        names = student.names + [""] * (storage.MAX_NAMES - len(student.names))
        for i, name in enumerate(names):
            row = tk.Frame(box, bg=C["bg"])
            row.pack(anchor="w", pady=2)
            label(row, f"Student {i + 1}", font="small_bold", width=10).pack(side="left")
            e = entry(row, width=22, font="ui")
            e.insert(0, name)
            e.pack(side="left", ipady=2)
            self.name_entries.append(e)
        self.names_msg = label(page, "Add a name to work together, or clear a box to take a name off.",
                               font="small", fg=C["muted"], wraplength=480)
        self.names_msg.pack(anchor="w", pady=(8, 6))
        PButton(page, "Save names", self._save_names, kind="secondary", font="small_bold", pady=3).pack(anchor="w")

    def _save_names(self) -> None:
        student = self.app.student
        names = [e.get() for e in self.name_entries]
        errors = storage.validate_names(names, student.profile.get("school", "x"))
        filled = [n.strip() for n in names if n.strip()]
        other = storage.find_student(filled, student.profile.get("school", "")) if not errors else None
        if other is not None and other.slug != student.slug:
            errors["name0"] = "Another profile on this Pi already has exactly those names."
        if errors:
            self.names_msg.configure(text="⚠ " + next(iter(errors.values())), fg=C["err"])
            return
        student.set_names(filled)
        self.names_msg.configure(text=f"✓ Saved: {student.first_name}", fg=C["ok"])
        self.app.settings_changed("names")

    def _tab_hardware(self, page) -> None:
        state = storage.app_state()
        real_pi = on_real_pi()
        mode = state.get("gpio_mode", "real") if real_pi else "sim"
        label(page, "Run GPIO programs on", font="h3").pack(anchor="w")
        opts = [("sim", "Simulator", "The board on the screen is your hardware.")]
        if real_pi:
            opts.append(("real", "Real Pi", "Your program drives the real GPIO pins (through the blue HAT), live."))
        ChoiceList(page, opts, mode, columns=2, wrap=220, on_change=self._set_mode).pack(anchor="w", pady=(4, 2))
        if not real_pi:
            label(page, "Real Pi appears here when PiPath runs on a Raspberry Pi.", font="small",
                  fg=C["muted"]).pack(anchor="w", pady=(0, 8))
        label(page, "Camera", font="h3").pack(anchor="w")
        cam = state.get("camera", "sim")
        cams = [("sim", "Simulated", "Pretend pictures"), ("usb", "USB", "A USB webcam"),
                ("ribbon", "Ribbon", "Pi camera on the ribbon")]
        ChoiceList(page, cams, cam if cam in CAMERA_KINDS else "sim", columns=3, wrap=140,
                   on_change=self._set_camera).pack(anchor="w", pady=(4, 0))

    def _set_mode(self, mode: str) -> None:
        storage.set_app_state(gpio_mode=mode)
        self.app.settings_changed("hardware")

    def _set_camera(self, kind: str) -> None:
        storage.set_app_state(camera=kind)
        self.app.settings_changed("hardware")

    def _tab_text(self, page) -> None:
        label(page, "Code text size", font="h3").pack(anchor="w")
        label(page, "For the code and the Output. Saved for you.", font="small", fg=C["muted"]).pack(anchor="w",
                                                                                                  pady=(0, 10))
        row = tk.Frame(page, bg=C["bg"])
        row.pack(anchor="w")
        PButton(row, "A−  Smaller", lambda: self._zoom(-1), kind="secondary").pack(side="left")
        PButton(row, "A+  Bigger", lambda: self._zoom(1), kind="secondary").pack(side="left", padx=8)
        self.size_lbl = label(row, "", font="ui_bold")
        self.size_lbl.pack(side="left", padx=10)
        sample = tk.Label(page, text='print("Hello, Pi!")', font="code", bg=C["ed_bg"], fg=C["ed_fg"],
                          relief="sunken", bd=2, padx=10, pady=8, anchor="w")
        sample.pack(anchor="w", pady=(14, 0), fill="x")
        self._show_size()

    def _zoom(self, step: int) -> None:
        f = tkfont.nametofont("code")
        size = max(9, min(26, f.cget("size") + step))
        f.configure(size=size)
        self.app.student.profile["code_size"] = size
        self.app.student.save_profile()
        self.app.settings_changed("text")
        self._show_size()

    def _show_size(self) -> None:
        self.size_lbl.configure(text=f"{tkfont.nametofont('code').cget('size')} point")

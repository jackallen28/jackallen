"""The coding workspace: guide panel + editor + output, for lessons and Free Build."""
from __future__ import annotations

import shutil
import tempfile
import time
import tkinter as tk
from pathlib import Path

from .. import storage
from ..content import DATA_DIR
from ..gpio import (CAMERA_KINDS, SHIM, SIM_ENV, expand_events, guess_camera, mode_env, on_real_pi,
                    wiring_check_program, wiring_parts)
from ..hints import (CheckResult, Diagnosis, ErrorInfo, HintEngine, code_features, evaluate_checks, gpio_lint,
                     parse_traceback, precheck)
from ..runner import Runner
from .board import VirtualBoard
from .console import Console
from .editor import CodeEditor
from .home import stars_for
from .onboarding import Screen
from .theme import C, TIER_COLOURS
from .tour import Tour
from .widgets import PButton, RichText, ScrollFrame, card, chip, label
from .wiring import WiringCard

DEMO_FILES = DATA_DIR / "demo_files"

# Reading these in a loop (instead of using events) is the classic "busy loop" on a Pi
POLLING_FEATURES = ("attr:is_pressed", "attr:is_held", "attr:motion_detected", "attr:is_active")

SUPPORT = {
    #             badge text        colour      step hints after N tries   max error-hint tier
    "guided": ("Guided", C["ok"], 0, 3),
    "scaffolded": ("Some help", C["info"], 1, 3),
    "brief": ("On your own", C["accent"], 2, 2),
}

COACH_STYLES = {
    "idle": (C["panel_alt"], C["muted"], "COACH"),
    "err": (C["err_soft"], C["err"], "COACH · SOMETHING BROKE"),
    "warn": (C["warn_soft"], C["warn"], "COACH · ALMOST THERE"),
    "ok": (C["ok_soft"], C["ok"], "COACH · NICE WORK"),
    "info": (C["info_soft"], C["info"], "COACH"),
}


# ====================================================================== Coach card

class CoachCard(tk.Frame):
    """Shows what happened on the last run, plus tiered hints."""

    def __init__(self, master, on_hint=None):
        super().__init__(master, bg=C["panel_alt"], highlightthickness=1, highlightbackground=C["line"])
        self.on_hint = on_hint
        self.bar = tk.Frame(self, bg=C["muted"], width=5)
        self.bar.pack(side="left", fill="y")
        self.inner = tk.Frame(self, bg=C["panel_alt"], padx=14, pady=12)
        self.inner.pack(side="left", fill="both", expand=True)
        self.kicker = label(self.inner, "COACH", font="small_bold", fg=C["muted"])
        self.kicker.pack(anchor="w")
        self.title = label(self.inner, "", font="h3", wraplength=290)
        self.title.pack(anchor="w", pady=(2, 4))
        self.body = RichText(self.inner)
        self.body.pack(fill="x")
        self.where = tk.Frame(self.inner)
        self.hint_box = tk.Frame(self.inner)
        self.hint_box.pack(fill="x", pady=(8, 0))
        self.hint_btn = PButton(self.inner, "Need a hint?", self._hint, kind="secondary", font="small_bold", pady=5)
        self.hint_btn.pack(anchor="w", pady=(8, 0))
        self.hint_note = label(self.inner, "", font="small", fg=C["muted"], wraplength=280)
        self.hint_note.pack(anchor="w", pady=(4, 0))
        self.hints: list[str] = []
        self.shown = 0
        self.idle()

    def _style(self, kind: str):
        bg, fg, kicker = COACH_STYLES[kind]
        for w in [self, self.inner, self.kicker, self.title, self.body, self.where, self.hint_box,
                  self.hint_note, *self.where.winfo_children()]:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass
        self.configure(highlightbackground=fg if kind != "idle" else C["line"])
        self.bar.configure(bg=fg)
        self.kicker.configure(text=kicker, fg=fg)

    def _set(self, kind, title, text):
        self._style(kind)
        self.title.configure(text=title.replace("`", ""))
        self.body.render(text)
        self.where.pack_forget()

    def idle(self, text: str | None = None):
        self._set("idle", "I'm here to help",
                  text or "When you press **Run**, I'll check your work. If something breaks, I'll explain it here and point to the line.")
        self.set_hints([], None)

    def message(self, kind: str, title: str, text: str):
        self._set(kind, title, text)

    def diagnosis(self, d: Diagnosis):
        self._set("err", d.title, d.explain)
        for w in self.where.winfo_children():
            w.destroy()
        if d.line:
            bg = COACH_STYLES["err"][0]
            self.where.configure(bg=bg)
            label(self.where, f"Line {d.line}", font="small_bold", fg=C["err"], bg=bg).pack(side="left")
            if d.code_line:
                tk.Label(self.where, text=f"  {d.code_line[:60]}  ", font="code_ui", bg="#262A33",
                         fg="#FFD7D3", padx=4).pack(side="left", padx=8)
            self.where.pack(anchor="w", fill="x", pady=(8, 0), before=self.hint_box)

    # ---- hints
    def set_hints(self, hints: list[str], locked_msg: str | None, already_shown: int = 0):
        self.hints = hints
        self.shown = min(already_shown, len(hints))
        for w in self.hint_box.winfo_children():
            w.destroy()
        for i in range(self.shown):
            self._render_hint(i)
        self._update_btn(locked_msg)

    def _render_hint(self, i: int):
        bg = self.inner.cget("bg")
        row = tk.Frame(self.hint_box, bg=bg)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=f"Hint {i + 1}", font="small_bold", fg="#FFFFFF", bg=C["warn"], padx=6).pack(side="left", anchor="n")
        rt = RichText(row, bg=bg)
        rt.pack(side="left", fill="x", expand=True, padx=(8, 0))
        rt.render(self.hints[i])

    def _update_btn(self, locked_msg: str | None):
        if not self.hints:
            self.hint_btn.pack_forget()
            self.hint_note.configure(text="")
            return
        self.hint_btn.pack(anchor="w", pady=(8, 0), before=self.hint_note)
        if locked_msg:
            self.hint_btn.configure(text="Hint locked")
            self.hint_btn.set_enabled(False)
            self.hint_note.configure(text=locked_msg)
        elif self.shown >= len(self.hints):
            self.hint_btn.configure(text="No more hints")
            self.hint_btn.set_enabled(False)
            self.hint_note.configure(text="Still stuck? Ask a classmate to read it with you, then your teacher.")
        else:
            nth = ["first", "second", "third"][self.shown] if self.shown < 3 else "next"
            self.hint_btn.configure(text=f"Show {nth} hint  ({self.shown + 1} of {len(self.hints)})")
            self.hint_btn.set_enabled(True)
            self.hint_note.configure(text="Hints start small. Try each one before asking for the next.")

    def _hint(self):
        if self.shown < len(self.hints):
            self._render_hint(self.shown)
            self.shown += 1
            self._update_btn(None)
            if self.on_hint:
                self.on_hint(self.shown)


# ====================================================================== Base workspace

class Workspace(Screen):
    left_width = 420

    def __init__(self, app, title: str, subtitle: str = ""):
        super().__init__(app)
        self.engine: HintEngine = app.engine
        self.runner = Runner(app.settings["busy_loop_seconds"], app.settings["max_output_lines"])
        self._poll_job = None
        self._save_job = None
        self._closed_streams = 0
        self._exit_code = None
        self._special: str | None = None      # None (a normal run), "demo" or "wiring"
        self._special_jobs: list = []
        self._special_dir: str | None = None
        self.gpio = self.uses_gpio()
        self.real_pi = on_real_pi()
        saved = storage.app_state().get("gpio_mode", "real")
        self.mode = saved if self.real_pi and saved in ("sim", "real") else "sim"
        cam = storage.app_state().get("camera")
        self.camera = cam if cam in CAMERA_KINDS else guess_camera()
        self.sim_object = "face"

        # ---- top bar
        bar = tk.Frame(self, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], padx=12, pady=8)
        bar.pack(fill="x")
        self.home_btn = PButton(bar, "◂ Activities", self.go_home, kind="ghost", font="small_bold")
        self.home_btn.pack(side="left")
        tk.Frame(bar, bg=C["line"], width=1, height=28).pack(side="left", padx=10)
        self.title_lbl = label(bar, title, font="h3", bg=C["panel"])
        self.title_lbl.pack(side="left")
        self.sub_lbl = label(bar, f"   {subtitle}", font="small", fg=C["muted"], bg=C["panel"])
        self.sub_lbl.pack(side="left")
        self.help_btn = PButton(bar, "? Tour", self.start_tour, kind="ghost", font="small_bold")
        self.help_btn.pack(side="right")
        label(bar, app.student.first_name, font="small_bold", fg=C["muted"], bg=C["panel"]).pack(side="right", padx=12)

        # ---- body
        self.pane = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bg=C["line"], bd=0, sashrelief="flat")
        self.pane.pack(fill="both", expand=True)
        self.left = tk.Frame(self.pane, bg=C["bg"])
        right = tk.Frame(self.pane, bg=C["ed_bg"])
        self.pane.add(self.left, minsize=320, width=self.left_width)
        self.pane.add(right, minsize=420)

        # toolbar above the editor
        tb = tk.Frame(right, bg="#2A2F38", padx=10, pady=7)
        tb.pack(fill="x")
        self.run_btn = PButton(tb, "▶  Run", self.run, kind="go", font="ui_bold", padx=18)
        self.run_btn.pack(side="left")
        self.stop_btn = PButton(tb, "■  Stop", self.stop, kind="stop", font="small_bold")
        self.stop_btn.pack(side="left", padx=8)
        self.stop_btn.set_enabled(False)
        label(tb, "F5", font="small", fg="#7D8696", bg="#2A2F38").pack(side="left")
        self.file_lbl = label(tb, "", font="code_ui", fg="#AEB5C1", bg="#2A2F38")
        self.file_lbl.pack(side="left", padx=18)
        PButton(tb, "A+", lambda: self.editor.zoom(1), kind="dark", font="small_bold", padx=8, pady=3).pack(side="right")
        PButton(tb, "A−", lambda: self.editor.zoom(-1), kind="dark", font="small_bold", padx=8, pady=3).pack(side="right", padx=4)
        self.save_lbl = label(tb, "", font="small", fg="#7D8696", bg="#2A2F38")
        self.save_lbl.pack(side="right", padx=12)
        if self.gpio:
            self._mode_switch(tb)

        vpane = tk.PanedWindow(right, orient="vertical", sashwidth=6, bg="#2A2F38", bd=0, sashrelief="flat")
        vpane.pack(fill="both", expand=True)
        self.editor = CodeEditor(vpane, on_change=self._changed)
        vpane.add(self.editor, minsize=160, stretch="always")
        self.board: VirtualBoard | None = None
        self.board_shown = False
        if self.gpio:
            self.bottom = tk.PanedWindow(vpane, orient="horizontal", sashwidth=6, bg="#2A2F38", bd=0, sashrelief="flat")
            self.console = Console(self.bottom, on_send=self.runner.send_input)
            self.bottom.add(self.console, minsize=220, stretch="always")
            self.board = VirtualBoard(self.bottom, on_press=self._board_press, on_release=self._board_release,
                                      on_goal=self.watch_goal, on_object=self._pick_object,
                                      on_camera=self.next_camera)
            self.board.set_mode(self.mode)
            if self.uses_camera():
                self.board.enable_camera(self.camera, self.sim_object)
            if not self.real_pi:
                self.board.set_status("Simulator only (not a Pi)")
            vpane.add(self.bottom, minsize=150, height=270, stretch="never")
        else:
            self.console = Console(vpane, on_send=self.runner.send_input)
            vpane.add(self.console, minsize=150, height=230, stretch="never")

        for seq, fn in (("<F5>", self.run), ("<Shift-F5>", self.stop), ("<Control-s>", self.save_now)):
            self.bind_all(seq, lambda e, f=fn: (f(), "break")[1])

    def destroy(self):
        for seq in ("<F5>", "<Shift-F5>", "<Control-s>"):
            self.unbind_all(seq)
        self._cancel_special_jobs()
        self.runner.stop()
        self._clean_special_dir()
        if self._save_job:
            self.after_cancel(self._save_job)
            self.save_now()
        super().destroy()

    # ---------------------------------------------------------------- saving
    def code_path(self) -> Path:
        raise NotImplementedError

    def _changed(self):
        self.save_lbl.configure(text="Editing…")
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(1200, self.save_now)

    def save_now(self):
        self._save_job = None
        storage.write_text(self.code_path(), self.editor.get_code())
        self.save_lbl.configure(text="Saved ✓")

    def go_home(self):
        self.save_now()
        self.app.show("home")

    # ---------------------------------------------------------------- running
    def run(self):
        if self.runner.running:
            return
        code = self.editor.get_code()
        self.save_now()
        self.editor.clear_marks()
        problem = precheck(code, self.current_starter())
        if problem:
            self.console.clear()
            self.console.write("Not run yet: there are blanks (___) to fill in first.\n", "info")
            self.after_run(code, problem, crashed=True, stdout="")
            return
        self.console.clear()
        self.console.write(f"▶ Running {self.code_path().name}" +
                           (" on the real pins" if self.gpio and self.mode == "real" else
                            " in the Simulator" if self.gpio else "") + "\n", "info")
        if self.gpio:
            for w in gpio_lint(code):
                self.console.write(f"⚠ Coach tip: {w}\n", "warn")
        if self.stop_is_finish():
            self.console.write("This program keeps running. Test it, then press ■ Stop to check your work.\n", "info")
        self._launch(code, self.code_path(), self.extra_env())

    def _launch(self, code: str, path: Path, env: dict, status: str = "running…"):
        self.console.set_status(status, C["con_in"])
        self.run_btn.set_enabled(False)
        self.stop_btn.set_enabled(True)
        self.console.set_input_enabled(True)
        self._closed_streams = 0
        self._exit_code = None
        self._run_code = code
        self._run_started = time.time()
        if self.board:
            self.board.reset()
        self.runner.start(path, path.parent, env, shim=SHIM if self.gpio else None)
        self._poll()

    def extra_env(self) -> dict:
        if not self.gpio:
            return {}
        return dict(mode_env(self.mode), **self.camera_env())

    def camera_env(self, sim: bool = False) -> dict:
        return {"PIPATH_CAMERA": "sim" if sim else self.camera, "PIPATH_CAMERA_OBJECT": self.sim_object}

    def uses_camera(self) -> bool:
        return False

    # ---------------------------------------------------------------- camera
    def next_camera(self):
        """Cycle Simulated -> USB -> Ribbon. Saved for this Pi (it's the Pi's hardware, not the student's)."""
        kinds = list(CAMERA_KINDS)
        self.stop()
        self.camera = kinds[(kinds.index(self.camera) + 1) % len(kinds)]
        storage.set_app_state(camera=self.camera)
        if self.board:
            self.board.set_camera_kind(self.camera)
        self.console.write(f"Camera: {CAMERA_KINDS[self.camera]}. " + {
            "sim": "Pretend pictures. Pick what the camera sees on the board.\n",
            "usb": "Plug a USB webcam into the Pi.\n",
            "ribbon": "A Raspberry Pi camera on the ribbon cable.\n"}[self.camera], "info")

    def _pick_object(self, key: str):
        self.sim_object = key
        if self.board:
            self.board.set_camera_object(key)
        if self.runner.running:
            self.runner.send_command(f"show {key}")

    def current_starter(self) -> str:
        return ""

    def uses_gpio(self) -> bool:
        return False

    def stop_is_finish(self) -> bool:
        """True when pressing Stop is the normal way to end (programs that run until stopped)."""
        return False

    # ---------------------------------------------------------------- Simulator / Real Pi
    def _mode_switch(self, tb):
        box = tk.Frame(tb, bg="#2A2F38")
        box.pack(side="left", padx=(6, 0))
        label(box, "Run on:", font="small", fg="#7D8696", bg="#2A2F38").pack(side="left", padx=(0, 6))
        self.sim_btn = PButton(box, "Simulator", lambda: self.set_mode("sim"), kind="dark", font="small_bold", padx=10, pady=3)
        self.sim_btn.pack(side="left")
        self.real_btn = PButton(box, "Real Pi", lambda: self.set_mode("real"), kind="dark", font="small_bold", padx=10, pady=3)
        self.real_btn.pack(side="left", padx=(2, 0))
        self._paint_mode()

    def _paint_mode(self):
        self.sim_btn.set_kind("secondary" if self.mode == "sim" else "dark")
        self.real_btn.set_kind("secondary" if self.mode == "real" else "dark")
        self.real_btn.set_enabled(self.real_pi)

    def set_mode(self, mode: str):
        if mode == self.mode or (mode == "real" and not self.real_pi):
            return
        self.stop()
        self.mode = mode
        storage.set_app_state(gpio_mode=mode)
        self._paint_mode()
        if self.board:
            self.board.set_mode(mode)
        self.console.write("Switched to " + ("the Simulator: the board on screen is your hardware.\n" if mode == "sim"
                                             else "the Real Pi: your program will use the real GPIO pins.\n"), "info")

    def show_board(self):
        if self.board and not self.board_shown:
            self.bottom.add(self.board, minsize=260, width=480 if self.uses_camera() else 400, stretch="never")
            self.board_shown = True

    def _board_press(self, pin: int):
        if self.runner.running:
            self.runner.send_command(f"press {pin}")
        else:
            self.board.set_status("Press Run first, then press the button")

    def _board_release(self, pin: int):
        self.runner.send_command(f"release {pin}")

    def _on_gpio(self, msg: dict):
        t = msg.get("t")
        if t == "devices":
            if msg["devices"]:
                self.show_board()
            self.board.set_devices(msg["devices"])
        elif t == "pins":
            self.board.set_values(msg["pins"])
        elif t == "photo":
            self.show_board()
            if msg.get("grid"):
                caption = "What the computer sees"
            else:
                caption = Path(msg.get("path", "")).name or "Photo"
            self.board.show_photo(msg.get("preview", ""), caption)

    # ---------------------------------------------------------------- demo and wiring-check runs
    def run_special(self, kind: str, code: str, env: dict, intro: str, seconds: float | None = None,
                    events: list | None = None, stdin: str = "", files: list | None = None):
        """Run code that isn't the student's (the goal demo, or a wiring check) in a temp folder."""
        if self.runner.running:
            return
        self.save_now()
        self._clean_special_dir()
        self._special = kind
        self._special_dir = tempfile.mkdtemp(prefix="pipath_")
        path = Path(self._special_dir) / ("goal.py" if kind == "demo" else "wiring_check.py")
        path.write_text(code, encoding="utf-8")
        for rel in files or []:       # sample data the demo needs, from data/demo_files/
            src = DEMO_FILES / rel
            if src.exists():
                shutil.copy(src, Path(self._special_dir) / src.name)
        self.editor.clear_marks()
        self.console.clear()
        self.console.write(intro + "\n", "info")
        if kind == "demo" and self.board:
            self.board.set_mode("sim")
        self._launch(code, path, env, status="playing the goal…" if kind == "demo" else "checking wiring…")
        for line in stdin.splitlines():
            self.runner.send_input(line)
        for when, command in expand_events(events):
            self._special_jobs.append(self.after(int(when * 1000), lambda c=command: self._demo_command(c)))
        if seconds:
            self._special_jobs.append(self.after(int(seconds * 1000), lambda: self.runner.stop("special")))

    def _demo_command(self, command: str):
        self.runner.send_command(command)
        if command.startswith("show ") and self.board:
            self.board.set_camera_object(command.split()[1])   # the picker follows the demo

    def _cancel_special_jobs(self):
        for job in self._special_jobs:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._special_jobs = []

    def _clean_special_dir(self):
        if self._special_dir:
            shutil.rmtree(self._special_dir, ignore_errors=True)
            self._special_dir = None

    def watch_goal(self):
        pass

    def special_finished(self, kind: str, stdout: str, stderr: str):
        pass

    def stop(self):
        if self.runner.running:
            self.runner.stop("user")

    def _poll(self):
        for ev in self.runner.poll():
            kind = ev[0]
            if kind == "out":
                self.console.write(ev[1])
            elif kind == "gpio":
                if self.board:
                    self._on_gpio(ev[1])
            elif kind == "closed":
                self._closed_streams += 1
            elif kind == "exit":
                self._exit_code = ev[1]
        if self._exit_code is not None and self._closed_streams >= 2:
            self._finished()
        else:
            self._poll_job = self.after(40, self._poll)

    def _finished(self):
        self.run_btn.set_enabled(True)
        self.stop_btn.set_enabled(False)
        self.console.set_input_enabled(False)
        code, reason, rc = self._run_code, self.runner.stop_reason, self._exit_code
        stderr = self.runner.stderr
        if self.board:
            self.board.set_values({})       # like real hardware: when a program ends, its pins switch off
        if self._special:
            kind, self._special = self._special, None
            self._cancel_special_jobs()
            if self.board:
                self.board.set_mode(self.mode)
            if stderr.strip() and rc not in (0, None) and reason is None:
                self.console.write("\n" + stderr, "err")
            self.console.set_status("")
            self.special_finished(kind, self.runner.stdout, stderr)
            self._clean_special_dir()
            return
        folder = str(self.code_path().parent) + "/"
        if reason == "user":
            if self.stop_is_finish() and not (rc not in (0, None, -15) and stderr.strip()):
                self.console.write("\n■ Stopped. Checking your work…\n", "info")
                self.console.set_status("stopped")
                self.after_run(code, None, False, self.runner.stdout)
                return
            self.console.write("\n■ Stopped.\n", "info")
            self.console.set_status("stopped")
            return
        err: ErrorInfo | None = None
        if reason in ("runaway_output", "runaway_busy"):
            msg = "output" if reason == "runaway_output" else "busy"
            if msg == "busy" and self.gpio and any(code_features(code).get(f) for f in POLLING_FEATURES):
                msg = "busy_gpio"
            err = ErrorInfo("PiPathRunaway", msg)
            self.console.write("\n■ PiPath stopped your program: it looked like a never-ending loop.\n", "err")
        elif rc != 0:
            if stderr.strip():
                self.console.write("\n" + stderr.replace(folder, ""), "err")
            err = parse_traceback(stderr, str(self.code_path()), code) or ErrorInfo(
                "Crash", f"exit code {rc}", None)
        crashed = err is not None
        if crashed:
            self.console.set_status("error", C["con_err"])
        else:
            self.console.write("\n✓ Program finished.\n", "info")
            self.console.set_status("finished", C["con_in"])
        self.after_run(code, err, crashed, self.runner.stdout)

    def after_run(self, code: str, err: ErrorInfo | None, crashed: bool, stdout: str):
        raise NotImplementedError

    # ---------------------------------------------------------------- tour
    def tour_steps(self) -> list[dict]:
        return []

    def start_tour(self):
        self._touring = True
        Tour(self.app, self.tour_steps(), on_done=self.tour_done).start()

    def tour_done(self):
        pass


# ====================================================================== Lesson workspace

class LessonWorkspace(Workspace):
    def __init__(self, app, lesson_id: str, tour: bool = False):
        self.project = app.catalog.project(lesson_id)
        self.lesson = app.catalog.lesson(lesson_id)
        self.steps = self.lesson["steps"]
        self.lp = app.student.lesson(lesson_id)
        tier = next(t for t in app.catalog.tiers if t["id"] == self.project["tier"])
        super().__init__(app, self.lesson["title"], f"{tier['title']} activity  ·  {self.project['subtitle']}")
        self.tier_colour = TIER_COLOURS.get(self.project["tier"], C["accent"])
        self.file_lbl.configure(text=self.lesson["file_name"])

        # per-step state
        self.step_i = self.lp.get("step", 0)
        self.attempts = 0
        self.step_runs = 0
        self.hint_ctx = None
        self.revealed: dict = {}
        self.confirmed: set[int] = set()      # "I saw it happen" boxes ticked this step
        self._last_eval = None                # (code, stdout, crashed, started) of the last run, for re-checking
        self.wiring_card: WiringCard | None = None
        self.parts = wiring_parts(self.lesson) if self.lesson.get("requires_gpio") else []

        self._build_left()
        if self.gpio:
            self.board.set_parts(self.parts)
            self.show_board()

        code = app.student.read_lesson_code(self.lesson["file_name"])
        if code is not None:
            self.editor.set_code(code)
        self.save_lbl.configure(text="Saved ✓")

        if self.lp["status"] == "complete" and not tour:
            self.show_outro()
        elif self.lp["status"] == "new":
            self.show_intro()
        else:
            self.enter_step(self.step_i)

        if tour:
            self.after(350, self.start_tour)

    def code_path(self) -> Path:
        return self.app.student.lesson_code_path(self.lesson["file_name"])

    def current_starter(self) -> str:
        return self.steps[self.step_i].get("starter", "") if self.view == "step" else ""

    def uses_gpio(self) -> bool:
        return bool(self.lesson.get("requires_gpio") or self.lesson.get("requires_camera"))

    def uses_camera(self) -> bool:
        return bool(self.lesson.get("requires_camera"))

    def stop_is_finish(self) -> bool:
        return self.view == "step" and self.steps[self.step_i].get("run_mode") == "until_stopped"

    def _wiring(self, open_: bool):
        if self.lesson.get("requires_gpio"):
            self.wiring_card = WiringCard(self.g, self.lesson, self.project, self.parts, open_=open_,
                                          on_check=self.check_wiring)
            self.wiring_card.pack(fill="x", pady=(0, 14))
        else:
            self.wiring_card = None

    # ---------------------------------------------------------------- left panel
    def _build_left(self):
        self.guide = ScrollFrame(self.left, bg=C["bg"])
        self.guide.pack(fill="both", expand=True)
        self.g = tk.Frame(self.guide.body, bg=C["bg"], padx=18, pady=14)
        self.g.pack(fill="both", expand=True)

        self.foot = tk.Frame(self.left, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"],
                             padx=14, pady=10)
        self.foot.pack(fill="x", side="bottom")
        self.back_btn = PButton(self.foot, "◂ Back", self.prev_step, kind="ghost", font="small_bold")
        self.back_btn.pack(side="left")
        self.next_btn = PButton(self.foot, "Next step  ▸", self.next_step, kind="secondary")
        self.next_btn.pack(side="right")
        self.foot_note = label(self.foot, "", font="small", fg=C["muted"], bg=C["panel"])
        self.foot_note.pack(side="right", padx=10)

    def _clear_guide(self):
        for w in self.g.winfo_children():
            w.destroy()
        self.guide.to_top()

    def _progress_dots(self, master):
        row = tk.Frame(master, bg=C["bg"])
        row.pack(fill="x", pady=(0, 12))
        label(row, f"STEP {self.step_i + 1} OF {len(self.steps)}", font="small_bold",
              fg=self.tier_colour).pack(side="left")
        dots = tk.Frame(row, bg=C["bg"])
        dots.pack(side="right")
        done = set(self.lp["steps_done"])
        for i in range(len(self.steps)):
            if i == self.step_i:
                col, w = self.tier_colour, 22
            elif i in done:
                col, w = C["ok"], 10
            else:
                col, w = C["line"], 10
            d = tk.Frame(dots, bg=col, width=w, height=10)
            d.pack(side="left", padx=2)
            if i in done or i in self.lp["steps_started"]:
                d.configure(cursor="hand2")
                d.bind("<Button-1>", lambda e, j=i: self.enter_step(j))

    # ---------------------------------------------------------------- intro / outro
    def show_intro(self):
        self._clear_guide()
        self.view = "intro"
        tier_title = next(t["title"] for t in self.app.catalog.tiers if t["id"] == self.project["tier"])
        chip(self.g, tier_title.upper() + " ACTIVITY", "#FFFFFF", self.tier_colour).pack(anchor="w")
        label(self.g, self.lesson["title"], font="h1").pack(anchor="w", pady=(8, 10))
        rt = RichText(self.g, font="ui")
        rt.pack(fill="x")
        rt.render(self.lesson["intro"])
        meta = card(self.g, padx=12, pady=10)
        meta.pack(fill="x", pady=(16, 14))
        label(meta, f"{len(self.steps)} steps  ·  about {self.project['minutes']} minutes",
              font="small_bold", bg=C["panel"]).pack(anchor="w")
        label(meta, "You'll learn: " + ", ".join(self.project["concepts"]), font="small", fg=C["muted"],
              bg=C["panel"], wraplength=340).pack(anchor="w", pady=(2, 0))
        self._wiring(open_=True)
        if self.board:
            self.board.show_goal_button(False)
        self.coach = CoachCard(self.g, on_hint=self._hint_used)
        self.coach.pack(fill="x", pady=(2, 0))
        self.coach.idle()
        self.checklist_frame = None
        self.back_btn.set_enabled(False)
        self.next_btn.configure(text="Start step 1  ▸")
        self.next_btn.set_kind("primary")
        self.next_btn.command = self.start_lesson
        self.foot_note.configure(text="")
        self.run_btn.set_enabled(False)
        if not self.editor.get_code().strip():
            self.editor.set_code("# Your code will appear here when you start step 1\n")
            self.editor.highlight()

    def start_lesson(self):
        self.app.student.mark_started(self.lesson["id"])
        self.run_btn.set_enabled(True)
        self.enter_step(0)

    def show_outro(self):
        self._clear_guide()
        self.view = "outro"
        self.editor.clear_marks()
        st = stars_for(self.app, self.lp.get("hints_used", 0))
        box = tk.Frame(self.g, bg=C["ink"], padx=20, pady=20)
        box.pack(fill="x")
        label(box, "ACTIVITY COMPLETE", font="small_bold", fg=C["syn_def"], bg=C["ink"]).pack(anchor="w")
        label(box, self.lesson["title"], font="h1", fg="#FFFFFF", bg=C["ink"]).pack(anchor="w", pady=(4, 6))
        label(box, "★" * st + "☆" * (3 - st), font="glyph", fg="#F5B800", bg=C["ink"]).pack(anchor="w")
        msg = {3: "Independence stars: you barely needed any hints!",
               2: "Independence stars: you used a few hints and got there.",
               1: "You finished! Next time, try one more run before opening a hint."}[st]
        label(box, msg, fg="#C9CED6", bg=C["ink"], wraplength=340).pack(anchor="w", pady=(4, 0))
        label(box, f"{self.lp.get('runs', 0)} runs  ·  {self.lp.get('errors', 0)} bugs found  ·  "
                   f"{self.lp.get('hints_used', 0)} hint{'' if self.lp.get('hints_used', 0) == 1 else 's'}", font="small", fg="#8F97A5", bg=C["ink"]).pack(anchor="w", pady=(8, 0))
        rt = RichText(self.g)
        rt.pack(fill="x", pady=(16, 0))
        rt.render(self.lesson["outro"])
        self.coach = CoachCard(self.g)
        self.checklist_frame = None
        self.back_btn.set_enabled(True)
        self.back_btn.command = lambda: self.enter_step(0)
        self.back_btn.configure(text="Review steps")
        nxt = self.app.catalog.next_project(self.lesson["id"])
        if nxt and self.app.project_state(nxt) in ("ready", "in_progress", "complete"):
            self.next_btn.configure(text=f"Next: {nxt['title']}  ▸")
            self.next_btn.command = lambda: self.app.open_lesson(nxt["id"])
        else:
            self.next_btn.configure(text="Back to activities  ▸")
            self.next_btn.command = self.go_home
        self.next_btn.set_kind("primary")
        self.next_btn.set_enabled(True)
        self.foot_note.configure(text="")

    # ---------------------------------------------------------------- steps
    def enter_step(self, i: int):
        self.view = "step"
        self.run_btn.set_enabled(True)
        student = self.app.student
        step = self.steps[i]
        first_time = i not in self.lp["steps_started"]
        if first_time:
            starter = step.get("starter")
            mode = step.get("starter_mode", "keep")
            if starter and mode == "replace":
                student.backup_lesson_code(self.lesson["file_name"], i + 1)
                self.editor.set_code(starter)
            elif starter and mode == "append":
                self.editor.append_code(starter)
            self.save_now()
            self.lp["steps_started"].append(i)
        self.step_i = i
        self.lp["step"] = i
        student.save_progress()
        self.attempts = 0
        self.step_runs = 0
        self.confirmed = set()
        self._last_eval = None
        self.hint_ctx = ("step", i)
        if self.board:
            self.board.show_goal_button(bool(step.get("demo")))
        self._render_step()
        self.console.clear()
        self.console.set_status("")
        self.editor.focus()
        self._maybe_offer_tour()

    def _maybe_offer_tour(self):
        """First time in a step: offer the tour, but don't force it."""
        if self.app.student.profile.get("tour_done") or getattr(self, "_tour_offered", False):
            return
        self._tour_offered = True
        self.after(300, self._offer_tour)

    def _offer_tour(self):
        if getattr(self, "_touring", False) or self.app.student.profile.get("tour_done"):
            return
        ov = self._tour_offer = card(self, padx=22, pady=18, border=C["accent"])
        ov.place(relx=.5, rely=.42, anchor="center")
        label(ov, "First time here?", font="h2", bg=C["panel"]).pack(anchor="w")
        label(ov, "Want a quick look around the workspace? It takes about 30 seconds.",
              fg=C["muted"], bg=C["panel"], wraplength=340).pack(anchor="w", pady=(4, 14))
        row = tk.Frame(ov, bg=C["panel"])
        row.pack(fill="x")

        def skip():
            ov.destroy()
            self.tour_done()

        def go():
            ov.destroy()
            self.start_tour()

        PButton(row, "No thanks, I'll explore", skip, kind="ghost", font="small_bold").pack(side="left")
        PButton(row, "Show me around  ▸", go, kind="primary").pack(side="right", padx=(16, 0))

    def _render_step(self):
        self._clear_guide()
        step = self.steps[self.step_i]
        self._progress_dots(self.g)
        self._wiring(open_=self.step_i == 0 and self.step_i not in self.lp["steps_done"])
        badge, colour, _, _ = SUPPORT.get(step["support"], SUPPORT["scaffolded"])
        top = tk.Frame(self.g, bg=C["bg"])
        top.pack(fill="x")
        label(top, step["title"], font="h2", wraplength=300).pack(side="left", anchor="w")
        chip(top, badge.upper(), "#FFFFFF", colour).pack(side="right", anchor="n", pady=4)
        self.instructions = RichText(self.g)
        self.instructions.pack(fill="x", pady=(8, 0))
        self.instructions.render(step["text"])

        # checklist
        self.checklist_frame = card(self.g, padx=14, pady=10)
        self.checklist_frame.pack(fill="x", pady=(14, 0))
        label(self.checklist_frame, "YOUR CHECKLIST", font="small_bold", fg=C["muted"], bg=C["panel"]).pack(anchor="w", pady=(0, 4))
        self.check_rows = []
        done = self.step_i in self.lp["steps_done"]
        for idx, c in enumerate(step["checks"]):
            row = tk.Frame(self.checklist_frame, bg=C["panel"])
            row.pack(fill="x", pady=2)
            if c["type"] == "confirm" and not done:
                # a box the student ticks when they have seen it happen (on screen or on the breadboard)
                icon = tk.Label(row, text="", font="small_bold", width=2, fg=C["ok"], bg=C["panel_alt"],
                                highlightthickness=2, highlightbackground=C["faint"], cursor="hand2")
                icon.pack(side="left", padx=(3, 7), pady=2)
                txt_box = tk.Frame(row, bg=C["panel"], cursor="hand2")
                txt_box.pack(side="left", fill="x")
                txt = label(txt_box, c.get("label", c["type"]), bg=C["panel"], wraplength=280)
                txt.pack(anchor="w")
                label(txt_box, "Tick this when you've seen it happen", font="small", fg=C["muted"],
                      bg=C["panel"]).pack(anchor="w")
                for w in (icon, txt_box, *txt_box.winfo_children()):
                    w.bind("<Button-1>", lambda e, k=idx: self._toggle_confirm(k))
            else:
                icon = tk.Label(row, text="✓" if done else "○", font="ui_bold", width=2,
                                fg=C["ok"] if done else C["faint"], bg=C["panel"])
                icon.pack(side="left")
                txt = label(row, c.get("label", c["type"]), bg=C["panel"], wraplength=300)
                txt.pack(side="left", fill="x")
            self.check_rows.append((icon, txt))

        # coach
        self.coach = CoachCard(self.g, on_hint=self._hint_used)
        self.coach.pack(fill="x", pady=(14, 0))
        if done:
            self.coach.message("ok", "Step complete", step.get("success", "Well done!"))
        else:
            self.coach.idle()
        self._refresh_hints()
        self._update_footer()

    def _update_footer(self):
        done = self.step_i in self.lp["steps_done"]
        last = self.step_i == len(self.steps) - 1
        self.back_btn.configure(text="◂ Back")
        self.back_btn.command = self.prev_step
        self.back_btn.set_enabled(self.step_i > 0)
        self.next_btn.command = self.next_step
        if last:
            self.next_btn.configure(text="Finish activity  ★")
        else:
            self.next_btn.configure(text="Next step  ▸")
        self.next_btn.set_kind("primary" if done else "secondary")
        self.next_btn.set_enabled(done or self.app.teacher_mode)
        self.foot_note.configure(text="" if done else "Tick all boxes")

    def prev_step(self):
        if self.step_i > 0:
            self.enter_step(self.step_i - 1)

    def next_step(self):
        if self.step_i == len(self.steps) - 1:
            self.app.student.mark_complete(self.lesson["id"])
            self.show_outro()
        else:
            self.enter_step(self.step_i + 1)

    # ---------------------------------------------------------------- hints
    def _hint_limits(self) -> tuple[int, int]:
        _, _, unlock_after, max_err = SUPPORT.get(self.steps[self.step_i]["support"], SUPPORT["scaffolded"])
        return unlock_after, max_err

    def _refresh_hints(self, diag: Diagnosis | None = None):
        unlock_after, max_err = self._hint_limits()
        if diag is not None:
            self.hint_ctx = ("err", self.step_i, diag.entry_id)
            hints, locked = diag.hints[:max_err], None
        else:
            self.hint_ctx = ("step", self.step_i)
            hints = self.steps[self.step_i].get("hints", [])
            left = unlock_after - self.attempts
            locked = None
            if left > 0 and not self.app.teacher_mode:
                locked = ("Have a go first: hints unlock after you press Run." if left == 1 and self.attempts == 0
                          else f"Hints unlock after {left} more tr{'y' if left == 1 else 'ies'}. You can do this!")
        self.coach.set_hints(hints, locked, self.revealed.get(self.hint_ctx, 0))

    def _hint_used(self, shown: int):
        self.revealed[self.hint_ctx] = shown
        self.lp["hints_used"] = self.lp.get("hints_used", 0) + 1
        self.app.student.save_progress()
        self.guide.scroll_to(self.coach)

    # ---------------------------------------------------------------- after a run
    def after_run(self, code, err, crashed, stdout):
        if self.view != "step":
            return
        step = self.steps[self.step_i]
        is_precheck = err is not None and err.type == "PiPathBlanks"
        if not is_precheck:
            self.step_runs += 1
            self.lp["runs"] = self.lp.get("runs", 0) + 1
        diag = None
        if err is not None:
            diag = self.engine.diagnose(err, step)
            if not is_precheck:
                self.lp["errors"] = self.lp.get("errors", 0) + 1
            self.editor.mark_error_line(diag.line)

        self._last_eval = (code, stdout, crashed, self._run_started)
        results = evaluate_checks(step["checks"], code, stdout, crashed, self.step_runs, self.confirmed,
                                  folder=self.code_path().parent, since=self._run_started)
        self._show_results(results)
        passed = all(r.passed for r in results)
        waiting = [r for r in results if not r.passed]

        if passed:
            self._complete_step()
        elif not diag and all(r.type == "confirm" for r in waiting):
            # the code did everything the checks can see; now the student confirms what happened
            self.coach.message("info", "Did you see it happen?",
                               "Your code passed the checks. Now watch the board" +
                               (" or your breadboard" if self.mode == "real" else "") +
                               " and tick the box when you see it:\n\n" +
                               "\n".join(f"- **{r.label}**" for r in waiting) +
                               "\n\nNot quite right? Change your code and press **Run** again.")
            self.coach.set_hints([], None)
        else:
            self.attempts += 1
            if diag:
                self.coach.diagnosis(diag)
                self._refresh_hints(diag)
            else:
                first = next(r for r in results if not r.passed and r.type != "confirm")
                self.coach.message("warn", "Your program ran, but…",
                                   f"**Not ticked yet:** {first.label}\n\n" + (first.fail or "Read the step instructions again and compare them with your code."))
                self._refresh_hints()
        self.app.student.save_progress()
        self._update_footer()
        self.guide.scroll_to(self.coach)

    def _complete_step(self):
        step = self.steps[self.step_i]
        if self.step_i not in self.lp["steps_done"]:
            self.lp["steps_done"].append(self.step_i)
        self.coach.message("ok", "Step complete!", step.get("success", "Well done!") +
                           ("\n\nPress **Finish activity** to see your stars." if self.step_i == len(self.steps) - 1
                            else "\n\nPress **Next step** when you're ready."))
        self.coach.set_hints([], None)
        self.console.set_status("✓ step complete", C["con_in"])

    def _show_results(self, results: list[CheckResult]):
        for (icon, _txt), r in zip(self.check_rows, results):
            if r.type == "confirm" and str(icon.cget("highlightthickness")) != "0":
                icon.configure(text="✓" if r.passed else "", highlightbackground=C["ok"] if r.passed else C["warn"])
            else:
                icon.configure(text="✓" if r.passed else "✗", fg=C["ok"] if r.passed else C["err"])

    def _toggle_confirm(self, idx: int):
        if self.view != "step" or self.step_i in self.lp["steps_done"]:
            return
        if self.step_runs == 0:
            self.coach.message("info", "Run it first",
                               "Press **Run** and watch what happens. Then tick the box if you saw it.")
            return
        self.confirmed ^= {idx}
        icon = self.check_rows[idx][0]
        ticked = idx in self.confirmed
        icon.configure(text="✓" if ticked else "", highlightbackground=C["ok"] if ticked else C["faint"])
        if self._last_eval and ticked:
            code, stdout, crashed, started = self._last_eval
            step = self.steps[self.step_i]
            results = evaluate_checks(step["checks"], code, stdout, crashed, self.step_runs, self.confirmed,
                                      folder=self.code_path().parent, since=started)
            if all(r.passed for r in results):
                self._show_results(results)
                self._complete_step()
                self.app.student.save_progress()
                self._update_footer()
                self.guide.scroll_to(self.coach)

    # ---------------------------------------------------------------- goal demo + wiring check
    def watch_goal(self):
        if self.view != "step":
            return
        step = self.steps[self.step_i]
        if not step.get("demo"):
            return
        self.run_special("demo", step["demo"], dict(SIM_ENV, **self.camera_env(sim=True)),
                         "▶ Watch the goal: this is what your program should do. (Your code isn't changed.)",
                         seconds=step.get("demo_seconds"), events=step.get("demo_events"),
                         stdin=step.get("demo_input", ""), files=step.get("demo_files"))

    def check_wiring(self):
        if not self.parts or self.runner.running:
            return
        where = "on the Simulator board" if self.mode == "sim" else "on your breadboard"
        self.run_special("wiring", wiring_check_program(self.parts), self.extra_env(),
                         f"▶ Checking your wiring {where}. Follow the instructions below.")

    def special_finished(self, kind: str, stdout: str, stderr: str):
        if kind == "demo":
            self.console.write("\n■ That's the goal! Now make your code do the same, then press Run.\n", "info")
        elif kind == "wiring":
            if self.wiring_card:
                self.wiring_card.mark_from_output(stdout)
            bad = [l for l in stdout.splitlines() if l.startswith("✗")]
            if bad:
                self.coach.message("warn", "Check those wires",
                                   "Some parts didn't respond:\n\n" + "\n".join(f"- {l[2:]}" for l in bad) +
                                   "\n\nTurn the Pi off, fix the wiring, and try **Check my wiring** again.")
            elif stdout.strip():
                self.coach.message("info", "Wiring check finished",
                                   "Every button and sensor answered. Did each LED blink and the buzzer beep? "
                                   "If one didn't, check its long leg (+) goes to the GPIO pin and the resistor is in.")

    # ---------------------------------------------------------------- tour
    def tour_steps(self):
        if self.view != "step":
            # the tour needs the checklist on screen
            self.app.student.mark_started(self.lesson["id"])
            self.enter_step(self.step_i)
        self.update_idletasks()
        return [
            {"widget": None, "side": "center", "title": "This is your workspace",
             "text": "Everything you need is on one screen. Let's take a 30-second look around."},
            {"widget": self.instructions, "side": "right", "title": "1. Read the step",
             "text": "Each project is split into small **steps**. The instructions for the current step are here, on the left."},
            {"widget": self.checklist_frame, "side": "right", "title": "2. Your checklist",
             "text": "This is what the step wants your program to do. Every time you press Run, the boxes get ticked ✓ or crossed ✗."},
            {"widget": self.editor, "side": "inside", "title": "3. The editor",
             "text": "This is where you type your Python code. Colours help you spot different parts, and **Tab** indents a line."},
            {"widget": self.run_btn, "side": "bottom", "title": "4. Run it",
             "text": "Press **Run** (or **F5**) to try your code. Run often. It's the fastest way to find out what's happening."},
            {"widget": self.console, "side": "top", "title": "5. Output",
             "text": "Whatever your program prints shows up here. When your program asks a question, type your answer in the box at the bottom and press **Enter**."},
            {"widget": self.coach, "side": "right", "title": "6. The Coach",
             "text": "If your code breaks, the Coach explains why in plain English and shows which line. Hints start small. Try one at a time."},
            {"widget": self.home_btn, "side": "bottom", "title": "7. Saving",
             "text": "Your code **saves automatically**. Use **Activities** to pick something else anytime. Press **? Tour** to see this again."},
        ]

    def tour_done(self):
        self._touring = False
        p = self.app.student.profile
        if not p.get("tour_done"):
            p["tour_done"] = True
            self.app.student.save_profile()
            if self.view == "step" and self.step_i not in self.lp["steps_done"]:
                self.coach.message("info", f"Ready, {self.app.student.first_name}?",
                                   "Read the step, then press the green **Run** button and see what happens.")


# ====================================================================== Free Build

CHEATSHEET = """
## Python cheat sheet
```
print("Hello")          # show
name = input("Name? ")  # ask
age = int(input("Age? "))

if age >= 13:
    print("Teen")
elif age > 9:
    print("Tween")
else:
    print("Kid")

while age < 18:         # repeat
    age = age + 1

for i in range(5):      # 5 times
    print(i)

import random
n = random.randint(1, 6)

from time import sleep
sleep(1)                # wait 1s
```
"""


class FreeBuildWorkspace(Workspace):
    left_width = 360

    def __init__(self, app):
        super().__init__(app, "Free Build", "Your own projects. No steps, just you (and the Coach).")
        self.student = app.student
        self.current: Path | None = None
        self.view = "free"

        sf = ScrollFrame(self.left, bg=C["bg"])
        sf.pack(fill="both", expand=True)
        g = tk.Frame(sf.body, bg=C["bg"], padx=16, pady=14)
        g.pack(fill="both", expand=True)

        label(g, "My projects", font="h2").pack(anchor="w")
        new = card(g, padx=12, pady=10)
        new.pack(fill="x", pady=(8, 0))
        label(new, "New project name", font="small_bold", bg=C["panel"]).pack(anchor="w")
        row = tk.Frame(new, bg=C["panel"])
        row.pack(fill="x", pady=(4, 0))
        self.new_entry = tk.Entry(row, font="ui", relief="flat", bg=C["panel_alt"], highlightthickness=2,
                                  highlightbackground=C["line"], highlightcolor=C["accent"])
        self.new_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.new_entry.bind("<Return>", lambda e: self.new_project())
        PButton(row, "Create", self.new_project, kind="primary", font="small_bold", pady=4).pack(side="left", padx=(6, 0))
        self.new_msg = label(new, "", font="small", fg=C["err"], bg=C["panel"])
        self.new_msg.pack(anchor="w")

        self.list_frame = tk.Frame(g, bg=C["bg"])
        self.list_frame.pack(fill="x", pady=(10, 0))

        self.coach = CoachCard(g)
        self.coach.pack(fill="x", pady=(14, 0))
        self.coach.idle("No checklist here. Build whatever you like! If your code crashes, I'll still explain what went wrong.")
        rt = RichText(g)
        rt.pack(fill="x", pady=(16, 0))
        rt.render(CHEATSHEET)

        projects = self.student.list_projects()
        if projects:
            self.open_project(projects[0])
        else:
            self._create("my first project")

    def code_path(self) -> Path:
        return self.current

    def uses_gpio(self) -> bool:
        return True     # the board appears as soon as a program makes an LED, Button...

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for p in self.student.list_projects():
            active = p == self.current
            row = tk.Frame(self.list_frame, bg=C["accent_soft"] if active else C["panel"], padx=10, pady=6,
                           highlightthickness=1, highlightbackground=C["accent"] if active else C["line"], cursor="hand2")
            row.pack(fill="x", pady=2)
            lb = label(row, p.stem.replace("_", " "), font="ui_bold" if active else "ui",
                       bg=row.cget("bg"))
            lb.pack(side="left")
            label(row, p.name, font="code_ui", fg=C["muted"], bg=row.cget("bg")).pack(side="right")
            for w in (row, lb):
                w.bind("<Button-1>", lambda e, path=p: self.open_project(path))

    def open_project(self, path: Path):
        if self.current:
            self.save_now()
        self.current = path
        self.editor.set_code(path.read_text(encoding="utf-8"))
        self.file_lbl.configure(text=path.name)
        self.save_lbl.configure(text="Saved ✓")
        self.console.clear()
        self.coach.idle("No checklist here. Build whatever you like! If your code crashes, I'll still explain what went wrong.")
        self._refresh_list()

    def new_project(self):
        name = self.new_entry.get()
        msg = storage.validate_project_name(name)
        if not msg and self.student.project_path(name).exists():
            msg = "You already have a project with that name."
        self.new_msg.configure(text=msg or "")
        if msg:
            return
        self.new_entry.delete(0, "end")
        self._create(name)

    def _create(self, name: str):
        path = self.student.project_path(name)
        storage.write_text(path, f"# {name}\n# by {self.student.first_name}\n\nprint(\"Let's build something!\")\n")
        self.open_project(path)

    def after_run(self, code, err, crashed, stdout):
        if err is not None:
            d = self.engine.diagnose(err)
            self.editor.mark_error_line(d.line)
            self.coach.diagnosis(d)
            self.coach.set_hints(d.hints, None)
        else:
            self.coach.message("ok", "It ran!", "No errors. Keep building, or try a new idea from the cheat sheet below.")
            self.coach.set_hints([], None)

    def tour_steps(self):
        return [
            {"widget": self.list_frame, "side": "right", "title": "Your projects",
             "text": "Make as many projects as you like. Click one to open it. Everything saves automatically."},
            {"widget": self.editor, "side": "inside", "title": "Build anything",
             "text": "There are no steps or checklists here. Use the cheat sheet on the left if you forget something."},
            {"widget": self.coach, "side": "right", "title": "The Coach is still here",
             "text": "If your code crashes, the Coach still explains the error and offers hints."},
        ]

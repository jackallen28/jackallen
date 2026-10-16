"""Time the app's main interactions (run under Xvfb). A Pi 3B is very roughly 10x slower.

    xvfb-run -s "-screen 0 1366x768x24" python3 tests/perf_probe.py

Not part of the unittest suite. Prints a table of milliseconds per interaction, plus how
many times the whole window was re-laid-out (update_idletasks calls).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PIPATH_HOME"] = tempfile.mkdtemp(prefix="pipath_perf_")
os.environ.setdefault("PIPATH_FORCE_SIM", "1")

CALLS = {"update_idletasks": 0}
_orig_uit = tk.Misc.update_idletasks


def counting_uit(self):
    CALLS["update_idletasks"] += 1
    return _orig_uit(self)


tk.Misc.update_idletasks = counting_uit
ROWS: list[tuple[str, float, int]] = []


def measure(name, fn, app=None, repeat=1):
    CALLS["update_idletasks"] = 0
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn()
        if app is not None:
            app.update()
    ms = (time.perf_counter() - t0) * 1000 / repeat
    ROWS.append((name, ms, CALLS["update_idletasks"] // repeat))


def run_to_output():
    """Run pressed -> first line of output, for a GPIO program: a fresh process vs the spare one."""
    from pipath.gpio import SHIM, SIM_ENV
    from pipath.runner import Runner
    folder = Path(tempfile.mkdtemp(prefix="pipath_perf_run_"))
    script = folder / "lights.py"
    script.write_text("from gpiozero import LED\nled = LED(17)\nled.on()\nprint('on')\n")
    for name, warm in (("Run -> first output (new process)", False), ("Run -> first output (spare process)", True)):
        times = []
        for _ in range(3):
            r = Runner()
            if warm:
                r.warm_up(SHIM, ["gpiozero", "gpiozero.pins.mock"])
                time.sleep(1.0)
            t0 = time.perf_counter()
            r.start(script, folder, dict(SIM_ENV), shim=SHIM)
            while not any(ev[0] == "out" for ev in r.poll()):
                time.sleep(0.002)
            times.append((time.perf_counter() - t0) * 1000)
            r.close()
        ROWS.append((name, sorted(times)[1], 0))


def main():
    t0 = time.perf_counter()
    from pipath import storage
    from pipath.app import PiPathApp
    ROWS.append(("import app modules", (time.perf_counter() - t0) * 1000, 0))
    holder = {}
    measure("start app (welcome screen)", lambda: holder.setdefault("app", PiPathApp()))
    app = holder["app"]
    app.geometry("1366x768+0+0")
    app.update()
    measure("create profile -> activities", lambda: app.login(storage.create_student("Sam", "Bayside SC")), app)
    measure("activities: filter Advanced", lambda: app.screen.set_filter("advanced"), app)
    measure("open Traffic Lights (intro)", lambda: app.open_lesson("a1_traffic"), app)
    measure("start step 1", lambda: app.screen.start_lesson(), app)
    app.screen.tour_done()
    for i in (1, 2, 3):
        measure(f"switch to step {i + 1}", lambda i=i: app.screen.enter_step(i), app)
    ws = app.screen
    code = ws.editor.get_code()
    measure("show run results (checks + Coach)", lambda: ws.after_run(code, None, False, "Green: go\n"), app, repeat=5)
    measure("show a hint", lambda: ws.coach._hint() if ws.coach.hints else None, app)
    measure("board: 200 pin updates", lambda: [ws.board.set_values({"17": i % 2, "27": 0.5, "22": 1}) for i in range(200)], app)
    measure("board: full redraw", lambda: ws.board._redraw(), app, repeat=10)

    def typing():
        t = ws.editor.text
        for ch in "print('hello there')\n" * 5:
            t.insert("insert", ch)
            t.event_generate("<<Modified>>")
            t.event_generate("<KeyRelease>")
            app.update_idletasks()
    measure("type 105 characters", typing, app)
    measure("editor: highlight 150 lines", lambda: (ws.editor.set_code("x = 1  # comment\nprint('hi', x)\n" * 75),
                                                   ws.editor.highlight()), app)
    measure("back to activities", lambda: app.show("home"), app)
    measure("open Free Build", lambda: app.open_free_build(), app)
    measure("open Photo Booth (camera)", lambda: app.open_lesson("c1_photobooth"), app)
    measure("back to activities (again)", lambda: app.show("home"), app)
    measure("open Hello, Pi! (no GPIO)", lambda: app.open_lesson("s1_hello"), app)
    measure("open Free Build (again)", lambda: app.open_free_build(), app)
    app.quit_app()
    run_to_output()

    print(f"{'interaction':40s} {'ms':>8s} {'relayouts':>10s}")
    for name, ms, n in ROWS:
        print(f"{name:40s} {ms:8.1f} {n:10d}")


if __name__ == "__main__":
    main()

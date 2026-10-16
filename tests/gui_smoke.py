"""Drive the real app under a virtual screen and save screenshots of each main screen.

    xvfb-run -s "-screen 0 1366x768x24" python3 tests/gui_smoke.py /tmp/shots

Not part of the unittest suite (needs Tk, Xvfb and ImageMagick's `import`).
Each scene is (name, action): the action runs, the app settles, then a screenshot is taken.
A crash in any action fails the run with a traceback.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PIPATH_HOME"] = tempfile.mkdtemp(prefix="pipath_smoke_")
os.environ.setdefault("PIPATH_FORCE_SIM", "1")

from pipath import storage  # noqa: E402
from pipath.app import PiPathApp  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
OUT.mkdir(parents=True, exist_ok=True)
SETTLE_MS = 900


def type_into(entry, text):
    entry.delete(0, "end")
    entry.insert(0, text)


def scenes(app):
    def profile():
        app.show("profile")
        type_into(app.screen.entries["first_name"], "Sam")
        type_into(app.screen.entries["school"], "Bayside Secondary College")

    def submit():
        app.screen.submit()

    def duplicate():
        app.show("profile")
        type_into(app.screen.entries["first_name"], "sam")
        type_into(app.screen.entries["school"], "bayside secondary college")
        app.screen.submit()

    def welcome_back():
        app.logout()

    def login_again():
        app.login(storage.list_students()[0])

    def filter_advanced():
        app.screen.set_filter("advanced")

    def open_lesson(lid):
        def go():
            app.screen.set_filter("all") if hasattr(app.screen, "set_filter") else None
            app.open_lesson(lid)
        return go

    def start_lesson():
        app.screen.start_lesson()

    def press_run():
        app.screen.run()

    def free_build():
        app.open_free_build()

    return [
        ("01_welcome_first_run", lambda: None),
        ("02_profile", profile),
        ("03_activities", submit),
        ("04_profile_duplicate", duplicate),
        ("05_welcome_back", welcome_back),
        ("06_activities_returning", login_again),
        ("07_filter_advanced", filter_advanced),
        ("08_s1_intro", open_lesson("s1_hello")),
        ("09_s1_tour_offer", start_lesson),
        ("10_s1_run", press_run),
        ("11_free_build", free_build),
    ]


def main():
    app = PiPathApp()
    app.geometry("1366x768+0+0")
    todo = list(scenes(app))
    failures = []

    def shoot(name):
        app.update()
        subprocess.run(["import", "-window", "root", str(OUT / f"{name}.png")], check=False)
        print("shot", name, flush=True)

    def step():
        if not todo:
            app.after(100, app.quit_app)
            return
        name, action = todo.pop(0)
        try:
            action()
        except Exception:
            failures.append(name)
            traceback.print_exc()
        app.after(SETTLE_MS, lambda: (shoot(name), app.after(50, step)))

    app.after(600, step)
    app.mainloop()
    if failures:
        sys.exit(f"Scenes failed: {failures}")


if __name__ == "__main__":
    main()

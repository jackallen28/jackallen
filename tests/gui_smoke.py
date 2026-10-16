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

    def skip_tour():
        offer = getattr(app.screen, "_tour_offer", None)
        if offer is not None and offer.winfo_exists():
            offer.destroy()
        app.screen.tour_done()

    def set_code(code):
        def go():
            app.screen.editor.set_code(code)
        return go

    def press(pin):
        def go():
            app.screen._board_press(pin)
        return go

    def release(pin):
        def go():
            app.screen._board_release(pin)
        return go

    def tick_confirms():
        for i, c in enumerate(app.screen.steps[app.screen.step_i]["checks"]):
            if c["type"] == "confirm":
                app.screen._toggle_confirm(i)

    def stop():
        app.screen.stop()

    def goal():
        app.screen.watch_goal()

    def to_step(i):
        def go():
            app.screen.enter_step(i)
        return go

    def check_wiring():
        app.screen.check_wiring()

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
        ("12_free_build_gpio", lambda: (set_code("from gpiozero import LED, Button\nfrom signal import pause\n"
                                                 "light = LED(17)\nbutton = Button(23)\n"
                                                 "button.when_pressed = light.toggle\npause()\n")(), press_run())),
        ("13_free_build_pressed", press(23)),
        ("14_e1_intro", lambda: (release(23)(), stop(), open_lesson("e1_lightswitch")())),
        ("15_e1_step1", lambda: (start_lesson(), skip_tour())),
        ("16_e1_step1_ran", press_run),
        ("17_e1_step3_running", lambda: (to_step(2)(), app.screen.editor.set_code(
            app.screen.steps[2]["starter"].replace("___", "light.off")), press_run())),
        ("18_e1_step3_pressed", press(23)),
        ("19_e1_step3_stopped", lambda: (release(23)(), stop())),
        ("20_e1_step3_ticked", tick_confirms),
        ("21_e3_wiring", lambda: open_lesson("e3_simon")()),
        ("22_e4_board", lambda: (open_lesson("e4_dice")(), start_lesson())),
        ("23_a1_activities", lambda: (app.show("home"), app.screen.set_filter("advanced"))),
        ("24_a1_step1", lambda: (open_lesson("a1_traffic")(), start_lesson())),
        ("25_a1_header_map", lambda: app.screen.guide.canvas.yview_moveto(0.33)),
        ("26_a1_step2_goal", lambda: (to_step(1)(), goal()), 4200),
        ("27_a3_pir", lambda: (stop(), open_lesson("a3_alarm")(), start_lesson(), app.screen.editor.set_code(
            app.screen.steps[0]["starter"].replace("___", "no_motion")), press_run()), 1200),
        ("28_a3_motion", press(4), 1200),
        ("29_a3_checked", lambda: (stop()), 2500),
        ("30_camera_activities", lambda: (app.show("home"), app.screen.set_filter("camera"))),
        ("31_c1_photo", lambda: (open_lesson("c1_photobooth")(), start_lesson(), app.screen.editor.set_code(
            app.screen.steps[0]["starter"].replace("___", "me")), press_run()), 2500),
        ("32_c2_grid_goal", lambda: (open_lesson("c2_teachable")(), start_lesson(), to_step(1)(),
                                     app.screen._pick_object("box"), goal()), 6500),
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
        name, action, *settle = todo.pop(0)
        try:
            action()
        except Exception:
            failures.append(name)
            traceback.print_exc()
        app.after(settle[0] if settle else SETTLE_MS, lambda: (shoot(name), app.after(50, step)))

    app.after(600, step)
    app.mainloop()
    if failures:
        sys.exit(f"Scenes failed: {failures}")


if __name__ == "__main__":
    main()

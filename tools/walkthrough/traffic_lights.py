"""PiPath walkthrough: Mia builds Traffic Lights (step 1, then the last step).

    tools/walkthrough/make.sh            # records, then renders both videos into walkthrough_out/

Or by hand (the recording needs a display, Tk and gpiozero; the render needs Pillow):
    xvfb-run -a -s "-screen 0 1600x900x24" python3 tools/walkthrough/traffic_lights.py OUT
    python3 tools/walkthrough/studio.py render OUT "PiPath" "Traffic Lights: a walkthrough" "..."

Story order: getting started → picking the project → wiring and testing (Check my wiring) →
step 1 (run it first, a Coach clue, fix it, the checklist ticks, "I saw it happen") → the last
step with Watch the goal → the stars.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["PIPATH_HOME"] = tempfile.mkdtemp(prefix="pipath_walkthrough_")    # a brand-new student
os.environ.setdefault("PIPATH_FORCE_SIM", "1")
os.environ["PIPATH_DOWNLOADS"] = tempfile.mkdtemp(prefix="pipath_walkthrough_dl_")

from pipath.app import PiPathApp  # noqa: E402
from pipath.ui.widgets import PButton  # noqa: E402
from studio import SRC_H, SRC_W, Studio  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "walkthrough_out")

app = PiPathApp()
app.geometry(f"{SRC_W}x{SRC_H}+0+0")
app.update()
s = Studio(app, OUT)


# ---------------------------------------------------------------- finding things on screen
def scr():
    return app.screen


def button(text, inside=None):
    """The PButton whose label starts with text."""
    def look(w):
        for c in w.winfo_children():
            if isinstance(c, PButton) and str(c.cget("text")).strip().startswith(text):
                return c
            found = look(c)
            if found is not None:
                return found
        return None
    return lambda: look(inside() if inside else scr())


def rel(widget, fx=0.5, fy=0.5):
    return (widget.winfo_rootx() - app.winfo_rootx() + widget.winfo_width() * fx,
            widget.winfo_rooty() - app.winfo_rooty() + widget.winfo_height() * fy)


def canvas_xy(cv, item):
    x1, y1, x2, y2 = cv.bbox(item)
    return (cv.winfo_rootx() - app.winfo_rootx() + (x1 + x2) / 2 - cv.canvasx(0),
            cv.winfo_rooty() - app.winfo_rooty() + (y1 + y2) / 2 - cv.canvasy(0))


def card_scroll(pid):
    cv = scr().canvas
    total = float(cv.cget("scrollregion").split()[3])
    return max(0.0, (cv.bbox(f"btn_{pid}")[1] - 380) / total)


def board_part(pin):
    board = scr().board
    for p, ids in board.items:
        if pin in p.get("pins", []):
            return p, ids
    raise LookupError(pin)


def board_button_xy(pin):
    p, ids = board_part(pin)
    cv = scr().board.canvas
    boxes = [cv.bbox(i) for i in ids.values() if isinstance(i, int) and cv.bbox(i)]
    x1 = min(b[0] for b in boxes); y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes); y2 = max(b[3] for b in boxes)
    return (cv.winfo_rootx() - app.winfo_rootx() + (x1 + x2) / 2,
            cv.winfo_rooty() - app.winfo_rooty() + (y1 + y2) / 2 - (y2 - y1) * 0.12)


def press_board(pin):
    def go():
        board = scr().board
        board._press(board_part(pin)[0])
        app.after(250, board._release_all)
    return go


def output():
    return scr().console.text.get("1.0", "end")


def blank_xy():
    t = scr().editor.text
    idx = t.search("___", "1.0")
    t.see(idx)
    x, y, w, h = t.bbox(idx)
    return (t.winfo_rootx() - app.winfo_rootx() + x + 14, t.winfo_rooty() - app.winfo_rooty() + y + h / 2)


def clear_blank():
    t = scr().editor.text
    idx = t.search("___", "1.0")
    t.mark_set("insert", idx)
    t.delete(idx, f"{idx}+3c")


def confirm_index():
    ws = scr()
    return next(i for i, c in enumerate(ws.steps[ws.step_i]["checks"]) if c["type"] == "confirm")


def jump_to_last_step():
    """Off camera: Mia has done steps 2 to 6 in later lessons."""
    ws = scr()
    last = len(ws.steps) - 1
    for i in range(last):
        if i not in ws.lp["steps_done"]:
            ws.lp["steps_done"].append(i)
    app.student.save_progress()
    ws.enter_step(last, carry_code=ws.steps[last - 1]["demo"])


def running():
    return scr().runner.running


# ---------------------------------------------------------------- the story
s.chapter("1 · Getting started")
s.say("**Mia** opens PiPath on the Raspberry Pi for the first time.")
s.hold()
s.click(button("Get started"))
s.wait(500)
s.say("A profile needs just a **first name** and the **school**. No emails or passwords.")
s.type(lambda: scr().entries["first_name"], "Mia")
s.type(lambda: scr().school, "Bayside Secondary College")
s.hold()
s.click(button("Next"))
s.wait(500)
s.say("Mia chooses **how much help** to get. It can change any time in Settings.")
s.move(lambda: rel(scr().level, 0.3, 0.15))
s.hold()
s.click(button("Start"))
s.wait(700)

s.chapter("2 · Picking a project")
s.say("Every activity is open. **Free Play** is always first, for building anything.")
s.move(lambda: canvas_xy(scr().canvas, "fb_btn"))
s.hold()
s.say("Today Mia picks a step-by-step hardware project: **Traffic Lights**.")
s.scroll(lambda: scr().canvas, lambda: card_scroll("a1_traffic"))
s.move(lambda: canvas_xy(scr().canvas, "btn_a1_traffic"))
s.hold()
s.click(lambda: canvas_xy(scr().canvas, "btn_a1_traffic"), action=lambda: app.open_lesson("a1_traffic"))
s.wait(900)
s.say("The intro shows what Mia will build, and the **plan**: one part at a time.")
s.hold()

s.chapter("3 · Wiring and testing")
s.say("First, the wiring. The **Wiring + Safety** card shows where every wire goes.")
s.click(lambda: rel(scr().wiring_card, 0.35, 0.04), action=lambda: scr().wiring_card.toggle())
s.wait(600)
s.hold()
s.say("The **blue HAT** comes off before changing wires, then goes back on.")
s.move(lambda: rel(scr().wiring_card, 0.45, 0.12))
s.hold()
s.say("**Check my wiring** runs a test program. Each LED blinks in turn.")
s.do(lambda: scr().guide.scroll_to(button("Check my wiring")()))
s.wait(500)
s.click(button("Check my wiring"))
s.until(lambda: "Press the" in output(), 25000)
s.say("Now it wants a button press. Mia clicks the **button** on the board.")
s.move(lambda: board_button_xy(23))
s.wait(400)
s.click(lambda: board_button_xy(23), action=press_board(23))
s.until(lambda: not running(), 15000)
s.say("Every part gets a **✓**. The wiring is ready.")
s.do(lambda: scr().guide.scroll_to(scr().wiring_card))
s.hold()
s.do(lambda: (scr().wiring_card.toggle(), scr().guide.to_top()))
s.wait(400)

s.chapter("4 · Step 1: Flash one light")
s.say("Mia starts **step 1**.")
s.click(lambda: scr().next_btn)
s.wait(700)
s.say("The first time, PiPath offers a quick **tour**. Mia says yes.", pos="top")
s.click(button("Show me around", lambda: scr()._tour_offer))
s.wait(400)
s.say("Yellow balloons point out each part of the workspace.", pos="top")
s.wait(1800)
s.do(lambda: scr()._tour and scr()._tour.forward())
s.wait(1800)
s.do(lambda: scr()._tour and scr()._tour.forward())
s.wait(1600)
s.do(lambda: scr()._tour and scr()._tour.finish())
s.say("Step 1 is **guided**: the code is ready, with one blank to fill in.")
s.move(blank_xy)
s.hold()
s.say("Mia presses **Run** first, just to see what happens.")
s.click(lambda: scr().run_btn)
s.wait(900)
s.say("The **Coach** gives a friendly clue: the blank still needs a number.")
s.move(lambda: rel(scr().coach, 0.5, 0.3))
s.hold()
s.say("Mia types **2**, for a 2-second flash.")
s.move(blank_xy)
s.do(clear_blank)
s.type(lambda: scr().editor.text, "2")
s.wait(500)
s.say("Run again. The LED on the board flashes: short, then long.")
s.click(lambda: scr().run_btn)
s.until(lambda: not running(), 15000)
s.say("The **checklist** ticks itself as each check passes.")
s.move(lambda: rel(scr().check_rows[0][0], 3, 0.5))
s.hold()
s.say("For hardware, Mia ticks **I saw it happen**.")
s.click(lambda: rel(scr().check_rows[confirm_index()][0]), action=lambda: scr()._toggle_confirm(confirm_index()))
s.wait(400)
s.say("Step done! Each step adds one new idea, with a little less help.")
s.hold()

s.chapter("5 · The last step")
s.say("A few lessons later, Mia reaches the **last step**: a challenge.")
s.do(jump_to_last_step)
s.hold()
s.say("**Watch the goal** plays the answer on the board. Mia's code isn't touched.")
s.click(lambda: scr().board.goal_btn)
s.wait(1200)
s.until(lambda: not running(), 20000)
s.say("Mia writes the challenge code, then runs it and presses the **button**.")
s.do(lambda: scr().editor.set_code(scr().steps[-1]["demo"]))
s.wait(600)
s.click(lambda: scr().run_btn)
s.wait(1600)
s.click(lambda: board_button_xy(23), action=press_board(23))
s.say("Amber, then red with a countdown and beeps, then the red light flashes.")
s.until(lambda: "Walk 1" in output(), 20000)
s.wait(2800)
s.click(lambda: scr().stop_btn)
s.wait(800)
s.click(lambda: rel(scr().check_rows[confirm_index()][0]), action=lambda: scr()._toggle_confirm(confirm_index()))
s.wait(600)
s.say("Everything is ticked, so Mia finishes the activity.")
s.click(lambda: scr().next_btn)
s.wait(700)
s.say("**Three stars** for doing it without any hints. Well done, Mia!")
s.hold()
s.say(None)
s.wait(1000)

s.run()

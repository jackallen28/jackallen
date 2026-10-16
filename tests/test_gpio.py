"""The GPIO engine: the shim, simulated presses, GPIO errors, lint and "I saw it" checks."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipath.gpio import SHIM, SIM_ENV, wiring_check_program, wiring_parts  # noqa: E402
from pipath.hints import ErrorInfo, HintEngine, evaluate_checks, gpio_lint, parse_traceback  # noqa: E402
from pipath.runner import Runner  # noqa: E402
from shimrun import HAVE_GPIOZERO, run_shim  # noqa: E402

ENGINE = HintEngine()
needs_gpiozero = unittest.skipUnless(HAVE_GPIOZERO, "gpiozero is not installed")


@needs_gpiozero
class TestShim(unittest.TestCase):
    def test_reports_devices_and_presses(self):
        code = (
            "from gpiozero import LED, Button, RGBLED\n"
            "from signal import pause\n"
            "light = LED(17)\n"
            "lamp = RGBLED(5, 6, 13)\n"
            "button = Button(23)\n"
            "button.when_pressed = light.on\n"
            "button.when_released = light.off\n"
            "pause()\n"
        )
        r = run_shim(code, events=["0.8 press 23", "1.4 release 23"], seconds=2.2)
        kinds = {d["kind"]: d["pins"] for d in r.devices}
        self.assertEqual(kinds, {"LED": [17], "RGBLED": [5, 6, 13], "Button": [23]})
        self.assertTrue(r.ever_on(17), "pressing the button turned the LED on")
        self.assertTrue(r.ever_on(23), "the button showed as pressed")
        self.assertTrue(r.stopped)
        self.assertEqual(r.rc, 0, r.stderr)

    def test_motion_sensor_triggered(self):
        code = (
            "from gpiozero import MotionSensor\n"
            "pir = MotionSensor(4)\n"
            "pir.wait_for_motion(timeout=5)\n"
            "print('Motion!' if pir.motion_detected else 'nothing')\n"
        )
        r = run_shim(code, events=["0.8 press 4"])
        self.assertIn("Motion!", r.stdout, r.stderr)

    def test_crash_in_event_handler_is_reported(self):
        code = (
            "from gpiozero import Button\n"
            "from signal import pause\n"
            "colours = ['red', 'green']\n"
            "position = 0\n"
            "def next_colour():\n"
            "    global position\n"
            "    position = position + 1\n"
            "    print(colours[position])\n"
            "button = Button(23)\n"
            "button.when_pressed = next_colour\n"
            "pause()\n"
        )
        r = run_shim(code, events=["0.6 press 23", "0.8 release 23", "1.0 press 23"], timeout=10)
        self.assertFalse(r.stopped, "the program ended by itself")
        self.assertEqual(r.rc, 1)
        self.assertNotIn("gpio_shim", r.stderr)
        self.assertNotIn("runpy", r.stderr)
        err = parse_traceback(r.stderr, "student.py", code)
        self.assertEqual((err.type, err.line), ("IndexError", 8))

    def test_traceback_points_at_student_file(self):
        code = "x = 1\nprint(y)\n"
        r = run_shim(code)
        self.assertEqual(r.rc, 1)
        self.assertNotIn("gpio_shim", r.stderr)
        err = parse_traceback(r.stderr, "student.py", code)
        self.assertEqual(ENGINE.diagnose(err).entry_id, "name_not_defined")
        self.assertEqual(err.line, 2)

    def test_syntax_error_still_diagnosed(self):
        code = "x = 3\nif x == 3\n    print(x)\n"
        r = run_shim(code)
        err = parse_traceback(r.stderr, "student.py", code)
        self.assertEqual(ENGINE.diagnose(err).entry_id, "missing_colon")

    def test_stop_exits_cleanly(self):
        code = ("from time import sleep\n"
                "try:\n    while True:\n        sleep(0.1)\nfinally:\n    print('tidy up')\n")
        r = run_shim(code, seconds=0.8)
        self.assertEqual(r.rc, 0)
        self.assertIn("tidy up", r.stdout)

    def test_plain_python_needs_no_gpiozero(self):
        r = run_shim("import sys\nprint('gpiozero' in sys.modules)\n")
        self.assertEqual(r.stdout.strip(), "False")

    def test_student_folder_is_import_path(self):
        r = run_shim("import os, sys\nprint(sys.path[0] == os.getcwd())\n")
        self.assertEqual(r.stdout.strip(), "True")


@needs_gpiozero
class TestRunnerWithShim(unittest.TestCase):
    def test_runner_streams_gpio_events_and_commands(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.py"
            p.write_text("from gpiozero import Button\nb = Button(23)\nb.wait_for_press(timeout=5)\n"
                         "print('pressed' if b.is_pressed else 'timeout')\n")
            r = Runner()
            r.start(p, Path(d), dict(SIM_ENV), shim=SHIM)
            events, sent, rc, t0 = [], False, None, time.monotonic()
            while time.monotonic() - t0 < 10 and rc is None:
                for ev in r.poll():
                    events.append(ev)
                    if ev[0] == "gpio" and ev[1].get("t") == "devices" and ev[1]["devices"] and not sent:
                        r.send_command("press 23")
                        sent = True
                    if ev[0] == "exit":
                        rc = ev[1]
                time.sleep(0.02)
            time.sleep(0.2)
            r.poll()
            self.assertEqual(rc, 0, r.stderr)
            self.assertIn("pressed", r.stdout)
            self.assertTrue(any(e[0] == "gpio" for e in events))


@needs_gpiozero
class TestGpioErrors(unittest.TestCase):
    CASES = [
        ("from gpiozero import LED\na = LED(17)\nb = LED(17)\n", {}, "gpio_pin_in_use"),
        ("from gpiozero import LED\na = LED(40)\n", {}, "gpio_invalid_pin"),
        ("from gpiozero import Button\nb = Button(23)\nb.when_pressed = 5\n", {}, "bad_event_handler"),
        ("from gpiozero import PWMLED\na = PWMLED(17)\n", {"GPIOZERO_MOCK_PIN_CLASS": "mockpin"}, "gpio_pwm_unsupported"),
        ("from gpiozero import LED\na = LED(17)\n", {"GPIOZERO_PIN_FACTORY": "", "GPIOZERO_MOCK_PIN_CLASS": ""},
         "gpio_no_factory"),
    ]

    def test_cases(self):
        on_pi = Path("/proc/device-tree/model").exists()
        for code, env, expected in self.CASES:
            if expected == "gpio_no_factory" and on_pi:
                continue   # a real Pi has a pin factory
            with self.subTest(expected=expected):
                r = run_shim(code, env=env)
                err = parse_traceback(r.stderr, "student.py", code)
                self.assertIsNotNone(err, r.stderr)
                d = ENGINE.diagnose(err)
                self.assertEqual(d.entry_id, expected, f"{err.type}: {err.message}")
                self.assertNotIn("{", d.title + d.explain, "unfilled placeholder")

    def test_runaway_entries(self):
        self.assertEqual(ENGINE.diagnose(ErrorInfo("PiPathRunaway", "busy_gpio")).entry_id, "runaway_busy_gpio")
        self.assertEqual(ENGINE.diagnose(ErrorInfo("PiPathRunaway", "busy")).entry_id, "runaway_busy")


class TestLint(unittest.TestCase):
    def test_brackets_on_event(self):
        w = gpio_lint("from gpiozero import LED, Button\nl = LED(17)\nb = Button(23)\nb.when_pressed = l.on()\n")
        self.assertEqual(len(w), 1)
        self.assertIn("b.when_pressed = l.on", w[0])

    def test_busy_while_true(self):
        busy = "from gpiozero import Button\nb = Button(23)\nwhile True:\n    if b.is_pressed:\n        print(1)\n"
        calm = "from gpiozero import Button\nfrom time import sleep\nb = Button(23)\nwhile True:\n    sleep(0.01)\n"
        self.assertTrue(any("while True" in w for w in gpio_lint(busy)))
        self.assertEqual(gpio_lint(calm), [])

    def test_pins(self):
        w = gpio_lint("from gpiozero import LED, Button\na = LED(17)\nb = Button(17)\nc = LED(40)\nd = LED(2)\n")
        self.assertEqual(len(w), 3, w)
        self.assertEqual(gpio_lint("from gpiozero import RGBLED, LEDBoard\nr = RGBLED(17, 27, 22)\n"
                                   "b = LEDBoard(5, 6, 13)\n"), [])

    def test_ignores_non_gpio_code(self):
        self.assertEqual(gpio_lint("while True:\n    pass\n"), [])


class TestConfirmChecks(unittest.TestCase):
    CHECKS = [{"type": "runs_ok", "label": "runs"}, {"type": "confirm", "label": "I saw it"}]

    def test_confirm_needs_a_tick(self):
        res = evaluate_checks(self.CHECKS, "", "", False, 1, confirmed=set())
        self.assertEqual([r.passed for r in res], [True, False])
        self.assertEqual(res[1].type, "confirm")
        res = evaluate_checks(self.CHECKS, "", "", False, 1, confirmed={1})
        self.assertTrue(all(r.passed for r in res))

    def test_confirm_defaults_to_ticked(self):
        self.assertTrue(all(r.passed for r in evaluate_checks(self.CHECKS, "", "", False)))


@needs_gpiozero
class TestWiringCheck(unittest.TestCase):
    def test_generated_check_runs_in_simulator(self):
        lesson = {"wiring": [
            {"part": "Red LED", "kind": "led", "pin": 17, "colour": "red"},
            {"part": "Buzzer", "kind": "buzzer", "pin": 18},
            {"part": "Button", "kind": "button", "pin": 23},
            {"part": "Tip", "connect": "no kind, so it's just a tip"},
        ]}
        parts = wiring_parts(lesson)
        self.assertEqual([p["kind"] for p in parts], ["led", "buzzer", "button"])
        r = run_shim(wiring_check_program(parts), events=["3.5 press 23", "3.7 release 23"], timeout=30)
        self.assertEqual(r.rc, 0, r.stderr)
        self.assertIn("✓ Button (GPIO23) works!", r.stdout)


if __name__ == "__main__":
    unittest.main()

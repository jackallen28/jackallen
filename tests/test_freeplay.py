"""Free Play (pipath/freeplay.py): the parts library, starter ideas and the wiring helper."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pipath import freeplay as fp  # noqa: E402
from pipath.hints import gpio_lint  # noqa: E402
from shimrun import HAVE_GPIOZERO, run_shim  # noqa: E402

LIB = fp.load()
PARTS = {p["id"]: p for p in LIB["parts"]}
START = "# my project\n# by Sam\n\nprint(\"Let's build something!\")\n"


class TestReadingCode(unittest.TestCase):
    def test_parts_from_code(self):
        code = ("from gpiozero import LED, Button, DistanceSensor, RGBLED, LEDBarGraph\n"
                "red = LED(17)\nbtn = Button(pin=23)\nsensor = DistanceSensor(echo=26, trigger=4)\n"
                "lamp = RGBLED(5, 6, 13)\nbar = LEDBarGraph(27, 22)\nx = LED(some_pin)\n")
        parts = fp.parts_from_code(code)
        kinds = [(p["kind"], p["pins"], p["label"]) for p in parts]
        self.assertEqual(kinds[:4], [("led", [17], "red"), ("button", [23], "btn"),
                                     ("distance", [26, 4], "sensor"), ("rgbled", [5, 6, 13], "lamp")])
        self.assertEqual([p["pins"] for p in parts[4:]], [[27], [22]], "LEDBarGraph = one LED per pin")
        self.assertEqual(fp.parts_from_code("print("), [], "broken code: nothing to wire")

    def test_wiring_rows_use_physical_pins(self):
        rows = fp.wiring_rows(fp.parts_from_code("from gpiozero import LED, DistanceSensor\nLED(17)\n"
                                                 "DistanceSensor(echo=26, trigger=4)\n"))
        self.assertIn("GPIO17 (pin 11)", rows[0]["connect"])
        self.assertIn("1kΩ", rows[1]["connect"])

    def test_pin_clashes_and_bad_pins(self):
        warns = fp.pin_warnings(fp.parts_from_code("from gpiozero import LED, Button\nLED(17)\nButton(17)\nLED(2)\n"))
        self.assertEqual(len(warns), 2)


class TestAddingParts(unittest.TestCase):
    def test_every_part_gives_working_code(self):
        for pid, part in PARTS.items():
            with self.subTest(part=pid):
                code, tip, cursor = fp.add_part(START, part)
                compile(code, pid, "exec")
                self.assertNotIn("{", tip)
                self.assertTrue(0 < cursor <= len(code))
                self.assertEqual(gpio_lint(code), [], code)

    def test_pins_and_names_dont_clash(self):
        code = START
        for _ in range(3):
            code, _tip, _c = fp.add_part(code, PARTS["led"])
        parts = fp.parts_from_code(code)
        self.assertEqual([p["pins"][0] for p in parts], [17, 27, 22])
        self.assertIn("led3 = LED(22)", code)
        self.assertEqual(code.count("from gpiozero import LED\n"), 1, "imports aren't repeated")
        self.assertLess(code.index("import"), code.index("print(\"Let's"), "imports go at the top")

    def test_never_after_code_that_runs_forever_or_inside_a_block(self):
        code = "from signal import pause\nfor i in range(3):\n    print(i)\npause()\n"
        new, _t, _c = fp.add_part(code, PARTS["random"])
        self.assertLess(new.index("roll ="), new.index("pause()"), "goes before pause()")
        new, _t, _c = fp.add_part(code, PARTS["random"], position=code.index("print"))
        self.assertGreater(new.index("roll ="), new.index("print(i)"), "goes after the loop, not inside it")
        compile(new, "x", "exec")

    def test_insert_at_the_cursor(self):
        code, _tip, _c = fp.add_part("a = 1\nb = 2\n", PARTS["random"], position=len("a = 1\n"))
        self.assertLess(code.index("roll ="), code.index("b = 2"))


@unittest.skipUnless(HAVE_GPIOZERO, "gpiozero is not installed")
class TestIdeasRun(unittest.TestCase):
    def test_every_idea_runs(self):
        for idea in LIB["ideas"]:
            with self.subTest(idea=idea["id"]):
                stdin = "Will it rain?\nbye\n" if idea["id"] == "magic8" else "pineapple\n"
                r = run_shim(idea["code"], events=["1 tap 23", "2 tap 23"], seconds=4, stdin=stdin,
                             env={"PIPATH_DEMO": "1"}, timeout=20)
                self.assertNotIn("Traceback", r.stderr, r.stderr)
                self.assertEqual(gpio_lint(idea["code"]), [])


if __name__ == "__main__":
    unittest.main()

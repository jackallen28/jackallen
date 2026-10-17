"""The code review coach (pipath/review.py): tips on how code is written, for Year 9-10."""
import glob
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipath.review import review  # noqa: E402


def titles(code):
    return [t.title for t in review(code, max_tips=10)]


class TestReview(unittest.TestCase):
    def test_repeated_lines(self):
        code = "from gpiozero import LED\nled = LED(17)\n" + "led.on()\nled.off()\n" * 3
        self.assertIn("Don't repeat yourself", titles(code))

    def test_input_validation(self):
        self.assertIn("Validate the input", titles("age = int(input('Age? '))\nprint(age)\n"))
        safe = "try:\n    age = int(input('Age? '))\nexcept ValueError:\n    age = 0\n"
        self.assertNotIn("Validate the input", titles(safe))

    def test_magic_numbers_and_names(self):
        code = "from time import sleep\nsleep(0.3)\nsleep(0.3)\nsleep(0.3)\nq = 5\n"
        found = titles(code)
        self.assertIn("Name your numbers", found)
        self.assertIn("Choose clear names", found)

    def test_bare_except_global_and_tests(self):
        code = ("score = 0\ndef add(points):\n    global score\n    score += points\n    return score\n"
                "try:\n    add(1)\nexcept:\n    pass\n")
        found = titles(code)
        for t in ("Catch the error you expect", "Fewer globals"):
            self.assertIn(t, found)

    def test_clean_code_gets_no_tips(self):
        code = ('"""Greeting."""\ndef greet(name):\n    return f"Hi {name}"\n\nassert greet("Sam") == "Hi Sam"\n'
                'print(greet("Sam"))\n')
        self.assertEqual(review(code), [])

    def test_broken_code_is_left_to_the_coach(self):
        self.assertEqual(review("print('hi'"), [])

    def test_every_model_answer_can_be_reviewed(self):
        for f in sorted(glob.glob(str(ROOT / "data" / "lessons" / "*.toml"))):
            with open(f, "rb") as fh:
                lesson = tomllib.load(fh)
            for step in lesson["steps"]:
                tips = review(step["demo"])
                self.assertLessEqual(len(tips), 3)
                for t in tips:
                    self.assertNotIn("{", t.title)


if __name__ == "__main__":
    unittest.main()

"""Runs real broken programs and checks the Coach picks the right errors.toml entry.

    python3 -m unittest discover -s tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipath.content import Catalog  # noqa: E402
from pipath.hints import HintEngine, evaluate_checks, parse_traceback, precheck  # noqa: E402

ENGINE = HintEngine()

# (broken code, stdin, expected errors.toml id)
CASES = [
    ('print("hi)', "", "unterminated_string"),
    ('prnt("hi")', "", "name_did_you_mean"),
    ('print(hello)', "", "name_did_you_mean"),
    ('print(zebra_count)', "", "name_not_defined"),
    ('print "hi"', "", "print_no_brackets"),
    ('x = 3\nif x == 3\n    print(x)', "", "missing_colon"),
    ('x = 3\nif x = 3:\n    print(x)', "", "equals_in_condition"),
    ('print("hi"', "", "unclosed_bracket"),
    ('print("hi"))', "", "extra_bracket"),
    ('x = 3\nif x == 3:\nprint(x)', "", "indent_expected"),
    ('x = 3\n    print(x)', "", "unexpected_indent"),
    ('if True:\n        a = 1\n    b = 2', "", "unindent_mismatch"),
    ('age = input("Age? ")\nprint(age + 1)', "12\n", "concat_str_number"),
    ('age = input("Age? ")\nprint(1 + age)', "12\n", "input_maths_2"),
    ('age = input("Age? ")\nprint(age - 1)', "12\n", "input_maths"),
    ('g = input("G? ")\nif g < 5:\n    pass', "3\n", "compare_str_number"),
    ('n = input("N? ")\nfor i in range(n):\n    pass', "3\n", "str_as_int"),
    ('a = int(input("N? "))', "seven\n", "int_bad_text"),
    ('a = int(input("N? "))', "\n", "int_empty"),
    ('print(10 / 0)', "", "zero_division"),
    ('x = [1, 2]\nprint(x[5])', "", "index_range"),
    ('d = {"a": 1}\nprint(d["b"])', "", "key_missing"),
    ('import random\nprint(random.randInt(1, 3))', "", "attr_did_you_mean"),
    ('import randum', "", "module_not_found"),
    ('print(“hi”)', "", "fancy_quotes"),
    ('name = "Sam"\nprint("Hi" name)', "", "missing_comma"),
    ('x = 1\nelse:\n    pass', "", "else_without_if"),
    ('def f(a):\n    pass\nf()', "", "missing_argument"),
    ('print = 5\nprint("hi")', "", "not_callable"),
]


def run(code: str, stdin: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "student.py"
        p.write_text(code, encoding="utf-8")
        r = subprocess.run([sys.executable, p.name], cwd=d, input=stdin,
                           capture_output=True, text=True, timeout=10)
        return r.stderr, str(p)


class TestDiagnose(unittest.TestCase):
    def test_cases(self):
        for code, stdin, expected in CASES:
            with self.subTest(code=code):
                stderr, path = run(code, stdin)
                err = parse_traceback(stderr, path, code)
                self.assertIsNotNone(err, stderr)
                d = ENGINE.diagnose(err)
                self.assertEqual(d.entry_id, expected, f"{err.type}: {err.message}")
                self.assertNotIn("{", d.title + d.explain, "unfilled placeholder")
                self.assertTrue(d.line, "line number found")

    def test_blanks_precheck(self):
        starter = '# fill in the ___\nprint("Hello, ___!")'
        self.assertIsNotNone(precheck('print("Hello, ___!")', starter))
        self.assertIsNone(precheck('print("Hello, Sam!")', starter))
        self.assertIsNone(precheck('print(" /|___|\\ ")', ""), "student ASCII art is fine")


class TestLessonsSolvable(unittest.TestCase):
    """Model answers for every step must pass that step's checks."""

    ANSWERS = {
        "s1_hello": [
            ('print("Hello, Pi!")', ""),
            ('print("Hello, Sam!")', ""),
            ('print("Hello, Sam!")\nprint("My favourite food is dumplings")\nprint("I can juggle")', ""),
            ('print("I am learning Python")\nprint("Bugs are just clues")', ""),
            ('print(" /\\\\_/\\\\ ")\nprint("( o.o )")\nprint(" > ^ < ")\nprint("/     \\\\")', ""),
        ],
        "s2_pibot": [
            ('bot_name = "Sparky"\nprint("Beep boop! I am", bot_name)', ""),
            ('name = input("What is your name? ")\nprint(f"Nice to meet you, {name}!")', "Sam\n"),
            ('age = int(input("How old are you? "))\nprint(f"Next year you will be {age + 1}!")', "12\n"),
            ('a = input("a")\nb = input("b")\nfood = input("Food? ")\nprint(food.upper())', "x\ny\npizza\n"),
            ('a = input()\nb = input()\nc = input().upper()\nd = int(input())\nprint(d * 4)', "x\ny\nz\n2\n"),
        ],
        "s3_guess": [
            ('import random\nsecret = random.randint(1, 10)\nprint(secret)', ""),
            ('import random\nsecret = 5\nguess = int(input())\nif guess == secret:\n    print("You got it!")\nelse:\n    print("Nope")', "5\n"),
            ('import random\nsecret = 5\nguess = int(input())\nif guess == secret:\n    print("You got it!")\nelif guess < secret:\n    print("Too low!")\nelse:\n    print("Too high!")', "5\n"),
            ('import random\nsecret = random.randint(1, 1)\nguess = 0\nwhile guess != secret:\n    guess = int(input())\nprint("You got it!")', "1\n"),
            ('import random\nsecret = random.randint(1, 100)\nguess = 0\ntries = 0\nwhile guess != 50:\n    guess = int(input())\n    tries += 1\nprint(f"You got it! You took {tries} tries!")', "50\n"),
        ],
    }

    def test_model_answers(self):
        cat = Catalog()
        for lid, answers in self.ANSWERS.items():
            steps = cat.lesson(lid)["steps"]
            self.assertEqual(len(steps), len(answers), lid)
            for i, (code, stdin) in enumerate(answers):
                with self.subTest(lesson=lid, step=i + 1):
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "a.py"
                        p.write_text(code)
                        r = subprocess.run([sys.executable, "a.py"], cwd=d, input=stdin,
                                           capture_output=True, text=True, timeout=10)
                    res = evaluate_checks(steps[i]["checks"], code, r.stdout, r.returncode != 0,
                                          runs_this_step=3)
                    failed = [c.label for c in res if not c.passed]
                    self.assertEqual(failed, [], r.stderr)

    def test_starters_fail_until_edited(self):
        """Starter code with blanks should be caught by precheck, not crash oddly."""
        cat = Catalog()
        for lid in self.ANSWERS:
            for step in cat.lesson(lid)["steps"]:
                st = step.get("starter", "")
                if "___" in st:
                    self.assertIsNotNone(precheck(st, st))


if __name__ == "__main__":
    unittest.main()

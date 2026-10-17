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
from pipath.hints import HintEngine, parse_traceback, precheck  # noqa: E402

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
    ('score = 0\ndef add():\n    score += 1\nadd()', "", "unbound_local"),
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

    def test_names_and_messages_are_filled_in(self):
        stderr, path = run('score = 0\ndef add():\n    score += 1\nadd()', "")
        d = ENGINE.diagnose(parse_traceback(stderr, path, ""))
        self.assertIn("`score`", d.explain)

    def test_sys_exit_with_a_message_is_not_an_error(self):
        stderr, path = run('import sys\nsys.exit("Bye")', "")
        self.assertIsNone(parse_traceback(stderr, path, ""))
        stderr, path = run('raise ValueError("first line\\nsecond line")', "")
        self.assertEqual(parse_traceback(stderr, path, "").type, "ValueError")

    def test_blanks_precheck(self):
        starter = '# fill in the ___\nprint("Hello, ___!")'
        self.assertIsNotNone(precheck('print("Hello, ___!")', starter))
        self.assertIsNone(precheck('print("Hello, Sam!")', starter))
        self.assertIsNone(precheck('print(" /|___|\\ ")', ""), "student ASCII art is fine")


class TestLessonsSolvable(unittest.TestCase):
    """Starters with blanks are caught before they run."""

    def test_starters_fail_until_edited(self):
        """Starter code with blanks should be caught by precheck, not crash oddly.
        (Every step's model answer is its demo, tested in test_activities.py.)"""
        cat = Catalog()
        for p in cat.projects:
            if p.get("status") != "ready":
                continue
            for step in cat.lesson(p["id"])["steps"]:
                st = step.get("starter", "")
                if "___" in st:
                    self.assertIsNotNone(precheck(st, st))


if __name__ == "__main__":
    unittest.main()

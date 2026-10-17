"""The code editor: indenting, comments, paste fixes, undo, find and replace, brackets.

Needs Tk and a display (the Pi desktop, or xvfb-run on a PC); skipped otherwise.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
    HAVE_TK = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
except ImportError:          # python3 without python3-tk
    HAVE_TK = False


@unittest.skipUnless(HAVE_TK, "needs tkinter and a display")
class TestEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pipath.ui.editor import CodeEditor
        from pipath.ui.theme import setup_fonts
        cls.root = tk.Tk()
        setup_fonts(cls.root, 1.0)
        cls.ed = CodeEditor(cls.root)
        cls.ed.pack(fill="both", expand=True)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.ed.set_code("")
        self.t = self.ed.text

    def code(self):
        return self.ed.get_code()

    def put(self, code, cursor="end-1c"):
        self.ed.set_code(code)
        self.t.mark_set("insert", cursor)

    def select(self, a, b):
        self.t.tag_remove("sel", "1.0", "end")
        self.t.tag_add("sel", a, b)

    # ---- indenting
    def test_enter_indents_after_colon_and_keeps_indent(self):
        self.put("for i in range(3):")
        self.ed._newline()
        self.t.insert("insert", "print(i)")
        self.ed._newline()
        self.assertEqual(self.code(), "for i in range(3):\n    print(i)\n    ")

    def test_colon_in_a_string_or_comment(self):
        self.put('if x == "#":')
        self.ed._newline()
        self.assertTrue(self.code().endswith("\n    "), "a # inside a string isn't a comment")
        self.put("x = 1  # note:")
        self.ed._newline()
        self.assertTrue(self.code().endswith("\n"), "a colon in a comment doesn't indent")

    def test_enter_dedents_after_return(self):
        self.put("def f():\n    return 5")
        self.ed._newline()
        self.assertTrue(self.code().endswith("return 5\n"))

    def test_enter_replaces_selection(self):
        self.put("abcdef")
        self.select("1.2", "1.4")
        self.t.mark_set("insert", "1.4")
        self.ed._newline()
        self.assertEqual(self.code(), "ab\nef")

    def test_tab_indents_selected_lines_as_one_undo(self):
        self.put("a = 1\nb = 2\n\nc = 3")
        self.select("1.0", "4.0")            # stops at the start of line 4: line 4 isn't selected
        self.ed._tab()
        self.assertEqual(self.code(), "    a = 1\n    b = 2\n\nc = 3")
        self.ed.undo()
        self.assertEqual(self.code(), "a = 1\nb = 2\n\nc = 3")

    def test_tab_goes_to_next_indent_level(self):
        self.put("  x", cursor="1.2")
        self.ed._tab()
        self.assertEqual(self.code(), "    x")

    def test_shift_tab_and_backspace_unindent(self):
        self.put("        x = 1\n    y = 2")
        self.select("1.0", "2.end")
        self.ed._dedent()
        self.assertEqual(self.code(), "    x = 1\ny = 2")
        self.put("      z", cursor="1.6")
        self.ed._backspace()
        self.assertEqual(self.code(), "    z", "back to the last indent level")

    # ---- comments, paste, select all
    def test_comment_toggle_round_trip(self):
        self.put("a = 1\n    b = 2")
        self.select("1.0", "2.end")
        self.ed.toggle_comment()
        self.assertEqual(self.code(), "# a = 1\n    # b = 2")
        self.select("1.0", "2.end")
        self.ed.toggle_comment()
        self.assertEqual(self.code(), "a = 1\n    b = 2")
        self.ed.undo()
        self.assertEqual(self.code(), "# a = 1\n    # b = 2")

    def test_paste_fixes_web_characters(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("print(“hi”)\r\n\tx = 1​")
        self.put("")
        self.ed.paste()
        self.assertEqual(self.code(), 'print("hi")\n    x = 1')

    def test_select_all(self):
        self.put("one\ntwo")
        self.ed.select_all()
        self.assertEqual(self.t.get("sel.first", "sel.last"), "one\ntwo")

    # ---- find, replace, go to line
    def test_find_replace_and_undo(self):
        self.put("cat = 1\nCat = 2\ndog = cat")
        bar = self.ed.find_bar
        bar.open("replace")
        bar.entry.delete(0, "end")
        bar.entry.insert(0, "cat")
        bar.search()
        self.assertEqual(len(bar.matches), 3, "lower-case search ignores capitals")
        bar.entry.delete(0, "end")
        bar.entry.insert(0, "Cat")
        bar.search()
        self.assertEqual(len(bar.matches), 1, "a capital letter makes it exact")
        bar.entry.delete(0, "end")
        bar.entry.insert(0, "cat")
        bar.rep_entry.insert(0, "pet")
        bar.replace_all()
        self.assertEqual(self.code(), "pet = 1\npet = 2\ndog = pet")
        self.ed.undo()
        self.assertEqual(self.code(), "cat = 1\nCat = 2\ndog = cat")
        bar.close()
        self.assertFalse(self.t.tag_ranges("found"))

    def test_go_to_line(self):
        self.put("a\nb\nc\nd")
        self.ed.goto_line(3)
        self.assertEqual(self.t.index("insert"), "3.0")
        self.ed.goto_line(99)
        self.assertEqual(self.t.index("insert"), "4.0")

    # ---- brackets
    def test_bracket_partner_and_missing_partner(self):
        self.put('print("(", (1 + 2))', cursor="1.6")        # just after the first (
        self.ed._match_brackets()
        marked = [str(i) for i in self.t.tag_ranges("bracket")]
        self.assertEqual(marked, ["1.5", "1.6", "1.18", "1.19"], "the ( inside the string is ignored")
        self.put("x = (1 + 2", cursor="1.5")
        self.ed._match_brackets()
        self.assertTrue(self.t.tag_ranges("bracket_bad"))
        self.put("", cursor="1.0")
        self.ed._match_brackets()            # an empty file mustn't crash

    def test_smart_home(self):
        self.put("    x = 1", cursor="1.9")

        class E:
            state = 0
        self.ed._home(E())
        self.assertEqual(self.t.index("insert"), "1.4")
        self.ed._home(E())
        self.assertEqual(self.t.index("insert"), "1.0")


if __name__ == "__main__":
    unittest.main()

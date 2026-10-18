"""Profiles: first name + school only, duplicates spotted, older profiles still load."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PIPATH_HOME"] = self.tmp.name
        import pipath.storage
        self.storage = importlib.reload(pipath.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_and_school_only(self):
        st = self.storage
        self.assertEqual(st.validate_profile("Sam", "Bayside SC"), {})
        self.assertIn("school", st.validate_profile("Sam", ""))
        s = st.create_student("Sam", "Bayside SC")
        self.assertEqual(s.label, "Bayside SC")
        self.assertEqual(st.list_students()[0].first_name, "Sam")

    def test_duplicate_name_at_same_school(self):
        st = self.storage
        st.create_student("Sam", "Bayside SC")
        self.assertIsNotNone(st.find_student(" sam ", "bayside  sc"))
        self.assertIsNone(st.find_student("Sam", "Other College"))
        second = st.create_student("Sam B", "Bayside SC")
        self.assertNotEqual(second.slug, "sam")

    def test_old_profile_with_class_still_loads(self):
        st = self.storage
        folder = st.STUDENTS / "alex-8b"
        folder.mkdir(parents=True)
        (folder / "profile.json").write_text(json.dumps(
            {"first_name": "Alex", "school": "Bayside SC", "class_code": "8B", "tour_done": True}))
        s = st.list_students()[0]
        self.assertEqual(s.label, "8B · Bayside SC")
        self.assertEqual(s.lesson_status("s1_hello"), "new")
        self.assertEqual(s.help_level, "beginner")      # profiles from before help levels

    def test_help_level_is_saved(self):
        st = self.storage
        s = st.create_student("Sam", "Bayside SC")
        self.assertEqual(s.help_level, "beginner")
        s.set_help_level("advanced")
        self.assertEqual(st.list_students()[0].help_level, "advanced")
        s.set_help_level("expert")                       # unknown levels fall back to the default
        self.assertEqual(st.list_students()[0].help_level, "beginner")

    def test_several_names_on_one_profile(self):
        st = self.storage
        self.assertEqual(st.join_names(["Sam"]), "Sam")
        self.assertEqual(st.join_names(["Sam", "Alex"]), "Sam & Alex")
        self.assertEqual(st.join_names(["Sam", " ", "Alex", "Priya"]), "Sam, Alex & Priya")
        self.assertEqual(st.validate_names(["Sam", "Alex"], "Bayside SC"), {})
        self.assertIn("name0", st.validate_names(["", ""], "Bayside SC"))
        self.assertIn("school", st.validate_names(["Sam"], ""))
        s = st.create_student(["Sam", "Alex"], "Bayside SC", help_level="moderate", show="computer")
        again = st.list_students()[0]
        self.assertEqual(again.names, ["Sam", "Alex"])
        self.assertEqual(again.first_name, "Sam & Alex")
        self.assertEqual((again.help_level, again.show), ("moderate", "computer"))
        self.assertIsNotNone(st.find_student(["alex", "sam"], "bayside sc"))     # any order
        self.assertIsNone(st.find_student(["Sam"], "Bayside SC"))
        s.set_names(["Sam", "Alex", "Priya"])
        self.assertEqual(st.list_students()[0].first_name, "Sam, Alex & Priya")

    def test_show_choice(self):
        st = self.storage
        s = st.create_student("Sam", "Bayside SC")
        self.assertEqual(s.show, "all")
        s.set_show("lab")
        self.assertEqual(st.list_students()[0].show, "lab")
        s.set_show("../../etc")                          # not a tier id
        self.assertEqual(st.list_students()[0].show, "all")

    def test_names_in_any_language(self):
        st = self.storage
        for name in ("Thảo", "Ngāti", "Łukasz", "Zoë", "O'Brien", "Mary-Jane"):
            self.assertEqual(st.validate_names([name], "Bayside SC"), {}, name)
        for name in ("x×y", "R2D2", "Sam!"):
            self.assertIn("name0", st.validate_names([name], "Bayside SC"), name)

    def test_damaged_files_and_spreadsheet_safety(self):
        st = self.storage
        s = st.create_student("Sam", "=1+1")
        folder = st.STUDENTS / "broken"
        folder.mkdir()
        (folder / "profile.json").write_text("[]")              # valid JSON, but not a profile
        self.assertEqual(len(st.list_students()), 2)
        s.profile["school"] = None
        s.save_profile()
        self.assertIsNone(st.find_student("Nobody", "Bayside SC"))
        s.profile["school"] = "=1+1"
        s.save_profile()
        text = st.export_progress_csv([]).read_text(encoding="utf-8")
        self.assertIn("'=1+1", text)

    def test_progress_is_read_when_needed(self):
        st = self.storage
        s = st.create_student("Sam", "Bayside SC")
        s.mark_started("s1_hello")
        again = st.list_students()[0]
        self.assertIsNone(again._progress)
        self.assertEqual(again.lesson_status("s1_hello"), "in_progress")


class TestLevels(unittest.TestCase):
    def test_hint_rules(self):
        from pipath.levels import hint_rules
        self.assertEqual(hint_rules("beginner", "brief"), (0, 3))       # hints any time
        self.assertEqual(hint_rules("moderate", "guided"), (0, 3))      # the activity's own plan
        self.assertEqual(hint_rules("moderate", "scaffolded"), (1, 3))
        self.assertEqual(hint_rules("moderate", "brief"), (2, 2))
        self.assertEqual(hint_rules("advanced", "guided"), (2, 2))      # never the near-answer

    def test_goal_text(self):
        from pipath.levels import goal_text
        step = {"text": "Some background.\n\n**Your task:** make the LED blink."}
        self.assertEqual(goal_text(step), "**Your task:** make the LED blink.")
        self.assertIsNone(goal_text({"text": "**Goal:** already short."}))
        self.assertIsNone(goal_text({"text": "No marker here."}))
        self.assertEqual(goal_text({"text": "Long text", "goal": "Short goal"}), "Short goal")

    def test_only_advanced_skips_and_skips_the_tour(self):
        from pipath.levels import LEVELS, can_skip, offer_tour
        self.assertEqual([lv for lv in LEVELS if can_skip(lv)], ["advanced"])
        self.assertEqual([lv for lv in LEVELS if not offer_tour(lv)], ["advanced"])


class TestWipe(unittest.TestCase):
    """The teacher can wipe the Pi for the next school: every student goes, the Pi's settings stay."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PIPATH_HOME"] = self.tmp.name
        import pipath.storage
        self.st = importlib.reload(pipath.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def _fill(self):
        st = self.st
        a = st.create_student(["Sam", "Alex"], "Bayside SC")
        st.create_student("Jo", "Hilltop College")
        st.write_text(a.lesson_code_path("hello.py"), "print('hi')\n")
        st.write_text(a.project_path("game"), "print('game')\n")
        st.touch_student(a)
        st.set_app_state(gpio_mode="sim", camera="usb")
        st.export_progress_csv([{"id": "s1_hello"}])
        return a

    def test_summary(self):
        self._fill()
        info = self.st.wipe_summary()
        self.assertEqual(info["students"], 2)
        self.assertEqual(info["schools"], ["Bayside SC", "Hilltop College"])
        self.assertGreaterEqual(info["files"], 4)
        self.assertEqual(info["exports"], 1)

    def test_wipe_removes_every_student_and_keeps_pi_settings(self):
        self._fill()
        self.st.wipe_all()
        self.assertEqual(self.st.list_students(), [])
        home = Path(self.tmp.name)
        self.assertFalse((home / "students").exists())
        self.assertFalse((home / "exports").exists())
        self.assertEqual(list(home.glob(".wiping_*")), [])
        state = self.st.app_state()
        self.assertNotIn("last_student", state)
        self.assertEqual((state["gpio_mode"], state["camera"]), ("sim", "usb"))
        # a new group starts cleanly, even with the same name
        s = self.st.create_student("Sam", "Bayside SC")
        self.assertEqual(s.slug, "sam")
        self.assertEqual([x.first_name for x in self.st.list_students()], ["Sam"])

    def test_keep_exports(self):
        self._fill()
        self.st.wipe_all(keep_exports=True)
        self.assertEqual(self.st.list_students(), [])
        self.assertEqual(len(list((Path(self.tmp.name) / "exports").glob("*.csv"))), 1)

    def test_wipe_when_empty(self):
        self.assertEqual(self.st.wipe_summary()["students"], 0)
        self.st.wipe_all()
        self.assertEqual(self.st.list_students(), [])

    def test_backup_zip_has_everyones_work(self):
        import zipfile
        self._fill()
        with tempfile.TemporaryDirectory() as usb:
            out = self.st.backup_zip(Path(usb) / "PiPath-backups")
            names = zipfile.ZipFile(out).namelist()
            self.assertTrue(any(n.endswith("lessons/hello.py") for n in names))
            self.assertTrue(any(n.endswith("projects/game.py") for n in names))
            self.assertTrue(any(n.startswith("exports/") for n in names))
            self.assertTrue(any(n.endswith("profile.json") for n in names))
            self.st.wipe_all()
            self.assertTrue(out.exists())          # the backup lives outside PiPath's folder


if __name__ == "__main__":
    unittest.main()

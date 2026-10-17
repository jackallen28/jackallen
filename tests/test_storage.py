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


if __name__ == "__main__":
    unittest.main()

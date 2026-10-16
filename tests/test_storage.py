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


if __name__ == "__main__":
    unittest.main()

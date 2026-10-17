"""Every step of every activity must be solvable: its demo (the model answer that
"Watch the goal" plays) passes that step's checks, in the Simulator for GPIO / camera
activities, with the demo's simulated presses and typed answers. Starters must start cleanly.

    python3 -m unittest tests.test_activities
"""
import os
import re
import shutil
import sys
import tomllib
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipath.content import DATA_DIR, Catalog  # noqa: E402
from pipath.hints import gpio_lint, evaluate_checks, precheck  # noqa: E402
from pipath.levels import has_goal  # noqa: E402
from shimrun import HAVE_GPIOZERO, run_shim  # noqa: E402

LESSONS_DIR = DATA_DIR / "lessons"
WORKERS = max(2, min(8, (os.cpu_count() or 2) * 2))
SUPPORT = {"guided", "scaffolded", "brief"}


def all_lessons() -> list[str]:
    return [f.stem for f in sorted(LESSONS_DIR.glob("*.toml"))]


def hardware_lessons() -> list[str]:
    out = []
    for f in sorted(LESSONS_DIR.glob("*.toml")):
        with open(f, "rb") as fh:
            raw = tomllib.load(fh)
        if raw.get("requires_gpio") or raw.get("requires_camera"):
            out.append(f.stem)
    return out


def run_demo(step: dict):
    seconds = step.get("demo_seconds")
    files = [DATA_DIR / "demo_files" / rel for rel in step.get("demo_files", [])]
    r = run_shim(step["demo"], events=step.get("demo_events"), seconds=seconds,
                 stdin=step.get("demo_input", ""), timeout=(seconds or 25) + 20, keep_folder=True, files=files,
                 env={"PIPATH_DEMO": "1"})
    crashed = (r.rc != 0 and not r.stopped) or "Traceback" in r.stderr
    res = evaluate_checks(step["checks"], step["demo"], r.stdout, crashed, runs_this_step=3,
                          folder=r.folder, since=r.started)
    shutil.rmtree(r.folder, ignore_errors=True)
    return r, [c.label for c in res if not c.passed]


class TestLessonFiles(unittest.TestCase):
    """Quick 'lesson lint' for every lesson file."""

    def test_every_lesson_is_well_formed(self):
        cat = Catalog()
        for f in sorted(LESSONS_DIR.glob("*.toml")):
            lesson = cat.lesson(f.stem)
            with self.subTest(lesson=f.stem):
                self.assertEqual(lesson["id"], f.stem)
                self.assertTrue(lesson.get("intro") and lesson.get("outro") and lesson.get("file_name"))
                for i, step in enumerate(lesson["steps"]):
                    self.assertIn(step["support"], SUPPORT, f"step {i + 1}")
                    self.assertLessEqual(len(step["hints"]), 3, f"step {i + 1}")
                    self.assertTrue(step.get("text"), f"step {i + 1}")
                    self.assertTrue(has_goal(step), f"step {i + 1}: add a **Your task:** or **Goal:** "
                                                    "line (Advanced shows just the goal)")
                    self.assertTrue(step.get("checks"), f"step {i + 1} has no checklist")
                    for c in step["checks"]:
                        if c["type"] in ("output_regex", "code_regex", "file_contains"):
                            re.compile(c["value"])
                    if "demo" in step:
                        self.assertNotIn("___", step["demo"], f"step {i + 1} demo has blanks")
                        self.assertEqual(gpio_lint(step["demo"]), [], f"step {i + 1}: a model answer "
                                         "shouldn't get a Coach tip")
                    for rel in step.get("demo_files", []):
                        self.assertTrue((DATA_DIR / "demo_files" / rel).exists(), rel)
                for rel in lesson.get("files", []):
                    self.assertTrue((DATA_DIR / "demo_files" / rel).exists(), rel)
                for row in lesson.get("wiring", []):
                    if row.get("kind"):
                        self.assertTrue(row.get("pin") or row.get("pins"), row)

    def test_catalog_points_at_real_lessons(self):
        for p in Catalog().projects:
            if p.get("status") == "ready":
                self.assertTrue((LESSONS_DIR / f"{p['id']}.toml").exists(), p["id"])


@unittest.skipUnless(HAVE_GPIOZERO, "gpiozero is not installed")
class TestActivitiesSolvable(unittest.TestCase):
    def test_every_step_demo_passes_its_checks(self):
        cat = Catalog()
        jobs = []
        for lid in all_lessons():
            for i, step in enumerate(cat.lesson(lid)["steps"]):
                self.assertIn("demo", step, f"{lid} step {i + 1} needs a demo (model answer)")
                jobs.append((lid, i, step))
        with ThreadPoolExecutor(WORKERS) as pool:
            results = list(pool.map(lambda j: (j, run_demo(j[2])), jobs))
        for (lid, i, _step), (r, failed) in results:
            with self.subTest(lesson=lid, step=i + 1):
                self.assertEqual(failed, [], f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")

    def test_starters_start_cleanly(self):
        """A starter without blanks runs for a few seconds without crashing (planted bugs need presses)."""
        cat = Catalog()
        jobs = []
        for lid in hardware_lessons():
            for i, step in enumerate(cat.lesson(lid)["steps"]):
                st = step.get("starter", "")
                if not st or step.get("starter_mode") != "replace":
                    continue
                if "___" in st:
                    self.assertIsNotNone(precheck(st, st), f"{lid} step {i + 1}")
                    continue
                jobs.append((lid, i, st))
        with ThreadPoolExecutor(WORKERS) as pool:
            results = list(pool.map(lambda j: (j, run_shim(j[2], seconds=3, timeout=15)), jobs))
        for (lid, i, _st), r in results:
            with self.subTest(lesson=lid, step=i + 1):
                self.assertTrue(r.rc == 0 or r.stopped, r.stderr)
                self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()

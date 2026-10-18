"""Adaptive scaffolding (pipath/adapt.py): nudges when stuck, level suggestions when it's too easy
or too hard, and never nagging."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipath.adapt import EARLY_HINTS_SECONDS, IDLE_SECONDS, NO_RUN_SECONDS, Adapter  # noqa: E402


class TestNudges(unittest.TestCase):
    def test_same_error_twice_gets_a_nudge_once(self):
        a = Adapter("beginner")
        a.start_step(0)
        self.assertIsNone(a.after_run(1, False, "missing_colon"))
        offer = a.after_run(2, False, "missing_colon")
        self.assertEqual(offer.kind, "nudge")
        self.assertIn(("Show me a hint", "hint"), offer.actions)
        a.after_run(3, False, "other")
        self.assertIsNone(a.after_run(4, False, "other"), "each nudge once per step")

    def test_same_check_and_many_fails(self):
        a = Adapter("moderate")
        a.start_step(0)
        a.after_run(1, False, None, "It prints the seconds")
        offer = a.after_run(2, False, None, "It prints the seconds")
        self.assertIn("It prints the seconds", offer.text)
        a.after_run(3, False, None, "x")
        offer = a.after_run(4, False, None, "y")
        self.assertIn(("Watch the goal", "goal"), offer.actions)

    def test_quiet_and_no_run_nudges(self):
        a = Adapter("advanced")
        a.start_step(0)
        self.assertIsNone(a.tick(30))
        self.assertEqual(a.tick(NO_RUN_SECONDS).title, "Give it a run!")
        a.after_run(NO_RUN_SECONDS + 1, False, None, "x")
        self.assertIsNone(a.tick(NO_RUN_SECONDS + 10), "just ran: not idle")
        self.assertEqual(a.tick(NO_RUN_SECONDS + 1 + IDLE_SECONDS).title, "Need a hand?")

    def test_hints_unlock_early_when_stuck(self):
        a = Adapter("advanced")
        a.start_step(0)
        self.assertFalse(a.hints_early(10))
        self.assertTrue(a.hints_early(EARLY_HINTS_SECONDS))
        b = Adapter("advanced")
        b.start_step(0)
        for t in range(3):
            b.after_run(t, False, None, "x")
        self.assertTrue(b.hints_early(5))

    def test_switched_off(self):
        a = Adapter("beginner", enabled=False)
        a.start_step(0)
        a.after_run(1, False, "e")
        self.assertIsNone(a.after_run(2, False, "e"))
        self.assertIsNone(a.tick(10_000))


class TestLevelSuggestions(unittest.TestCase):
    def finish(self, a, fails=0, hints=0):
        a.start_step(0)
        for t in range(fails):
            a.after_run(t, False, None, f"check {t}")
        for _ in range(hints):
            a.on_hint()
        a.after_run(50, True)
        return a.step_done(60)

    def test_flying_suggests_harder_then_waits(self):
        a = Adapter("beginner")
        self.assertIsNone(self.finish(a))
        self.assertIsNone(self.finish(a))
        offer = self.finish(a)
        self.assertEqual(offer.kind, "harder")
        self.assertIn(("Try Moderate", "level:moderate"), offer.actions)
        for _ in range(3):
            self.assertIsNone(self.finish(a), "cool-down after a suggestion")

    def test_struggling_suggests_easier(self):
        a = Adapter("advanced")
        for _ in range(2):
            self.finish(a, fails=4)
        offer = self.finish(a, fails=4)
        self.assertEqual(offer.kind, "easier")
        self.assertIn(("Switch to Moderate", "level:moderate"), offer.actions)

    def test_no_harder_than_advanced_and_state_is_saved(self):
        a = Adapter("advanced")
        for _ in range(4):
            self.assertIsNone(self.finish(a))
        b = Adapter("moderate", a.state())
        self.assertEqual(self.finish(b).kind, "harder", "history carries over between activities")

    def test_a_finished_step_counts_once(self):
        a = Adapter("beginner")
        a.start_step(0, already_done=True)
        self.assertIsNone(a.step_done(5))
        self.assertEqual(a.history, [])


if __name__ == "__main__":
    unittest.main()

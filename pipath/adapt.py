"""Adaptive scaffolding: help that responds to how a student is going.

The student still chooses their help level. On top of it, PiPath watches a few simple signals and
*offers* (never forces) the right next thing:

- stuck on a step (the same clue twice, a check that keeps failing, a long quiet spell) ->
  a gentle nudge with a button for a hint, Watch the goal, or the full explanation, and hints
  unlock early even at the Moderate / Advanced levels
- flying through steps (first try, no hints, several in a row) -> "try a harder level?"
- finding it tough several steps running -> "want a bit more help?"

Each nudge shows at most once per step, and level suggestions wait a few steps after the last one,
so the Coach never nags. Plain logic (no Tk), so it can be tested; workspace.py shows the offers.
No AI: just counting.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .levels import LEVELS

IDLE_SECONDS = 150         # no edits or runs for this long, while stuck ...
STEP_SECONDS = 180         # ... and on the step at least this long -> a "need a hand?" nudge
NO_RUN_SECONDS = 240       # on a step this long without pressing Run once
EARLY_HINTS_FAILS = 3      # failed runs before hints unlock whatever the level
EARLY_HINTS_SECONDS = 300  # or this long on one step
HISTORY = 8                # step results remembered (in the profile)
COOLDOWN_STEPS = 4         # steps to wait after a level suggestion before another


@dataclass
class Offer:
    kind: str                      # "nudge" | "harder" | "easier"
    title: str
    text: str                      # markdown
    actions: list[tuple[str, str]] = field(default_factory=list)   # (button label, action)
    # actions: "hint", "goal", "full", "dismiss", "level:<beginner|moderate|advanced>"


@dataclass
class _Step:
    started: float
    last_progress: float
    runs: int = 0
    failed: int = 0
    hints: int = 0
    last_error: str | None = None
    last_failing: str | None = None
    same_fail: int = 0
    shown: set = field(default_factory=set)
    done: bool = False


class Adapter:
    def __init__(self, level: str, saved: dict | None = None, enabled: bool = True):
        self.level = level if level in LEVELS else LEVELS[0]
        self.enabled = enabled
        saved = saved or {}
        self.history: list[dict] = list(saved.get("history", []))[-HISTORY:]
        self.cooldown: int = int(saved.get("cooldown", 0))
        self.step: _Step | None = None

    def state(self) -> dict:
        """What to save in the profile, so suggestions carry on between activities."""
        return {"history": self.history[-HISTORY:], "cooldown": self.cooldown}

    # ---------------------------------------------------------------- events from the workspace
    def start_step(self, now: float, already_done: bool = False) -> None:
        self.step = _Step(started=now, last_progress=now, done=already_done)

    def on_edit(self, now: float) -> None:
        if self.step:
            self.step.last_progress = now

    def on_hint(self) -> None:
        if self.step:
            self.step.hints += 1

    def after_run(self, now: float, passed: bool, error_id: str | None = None,
                  failing: str | None = None) -> Offer | None:
        """After a Run is checked. error_id: the Coach entry if it crashed; failing: the first
        check not ticked yet (its label)."""
        s = self.step
        if s is None or s.done:
            return None
        s.runs += 1
        s.last_progress = now
        if passed:
            return None
        s.failed += 1
        repeat_error = error_id is not None and error_id == s.last_error
        s.last_error = error_id
        s.same_fail = s.same_fail + 1 if failing and failing == s.last_failing else (1 if failing else 0)
        s.last_failing = failing
        if not self.enabled:
            return None
        if repeat_error:
            return self._once("same_error", Offer(
                "nudge", "Same clue as last time",
                "That's the same error again, so let's slow down. Look at the line the Coach points to, "
                "and read it out loud, character by character. Brackets, quotes, colons and spelling "
                "are the usual suspects.",
                [("Show me a hint", "hint"), ("I've got it", "dismiss")]))
        if s.failed >= 4:
            return self._once("many_fails", Offer(
                "nudge", "Want to see it working?",
                "You've had a few goes. That's how programmers work! Watching the finished step can make "
                "the instructions click. Your code stays as it is.",
                [("Watch the goal", "goal"), ("Show me a hint", "hint"), ("Keep trying", "dismiss")]))
        if s.same_fail >= 2 and failing:
            return self._once("same_check", Offer(
                "nudge", "Nearly there",
                f"Everything else is working. The part still to do is: **{failing}**. Read the "
                "**Your task** line again and compare it with your code.",
                [("Show me a hint", "hint"), ("Show the full explanation", "full"), ("OK", "dismiss")]))
        return None

    def tick(self, now: float) -> Offer | None:
        """Called every so often while a step is on screen."""
        s = self.step
        if s is None or s.done or not self.enabled:
            return None
        on_step = now - s.started
        if s.runs == 0 and on_step >= NO_RUN_SECONDS:
            return self._once("no_run", Offer(
                "nudge", "Give it a run!",
                "Press **Run** even if you're not sure your code is right. It's not a test: running it "
                "is how you find out what to change, and I'll help with any errors.",
                [("Show me a hint", "hint"), ("OK", "dismiss")]))
        if s.runs and on_step >= STEP_SECONDS and now - s.last_progress >= IDLE_SECONDS:
            return self._once("idle", Offer(
                "nudge", "Need a hand?",
                "This step is a tricky one. You could watch the goal, open a hint, or ask the person "
                "next to you. Talking it through often helps!",
                [("Watch the goal", "goal"), ("Show me a hint", "hint"), ("I'm OK", "dismiss")]))
        return None

    def hints_early(self, now: float) -> bool:
        """Stuck for a while: hints unlock whatever the level (Advanced still never gets the answer)."""
        s = self.step
        return bool(self.enabled and s and not s.done and
                    (s.failed >= EARLY_HINTS_FAILS or now - s.started >= EARLY_HINTS_SECONDS))

    def step_done(self, now: float) -> Offer | None:
        """The step's checklist is complete. Remember how it went; maybe suggest a new level."""
        s = self.step
        if s is None or s.done:
            return None
        s.done = True
        self.history.append({"first_try": s.failed == 0, "failed": s.failed, "hints": s.hints,
                             "secs": round(now - s.started)})
        self.history = self.history[-HISTORY:]
        if self.cooldown > 0:
            self.cooldown -= 1
            return None
        if not self.enabled or len(self.history) < 3:
            return None
        last = self.history[-3:]
        i = LEVELS.index(self.level)
        if i < len(LEVELS) - 1 and all(r["first_try"] and r["hints"] == 0 for r in last):
            harder = LEVELS[i + 1]
            self.cooldown = COOLDOWN_STEPS
            return Offer("harder", "You're flying!",
                         "Three steps in a row, first try, with no hints. Want more of a challenge? At "
                         f"**{harder.title()}** you get {_LEVEL_PITCH[harder]}",
                         [(f"Try {harder.title()}", f"level:{harder}"), ("Stay here", "dismiss")])
        if i > 0 and (sum(r["failed"] for r in last) >= 9 or sum(r["hints"] for r in last) >= 5):
            easier = LEVELS[i - 1]
            self.cooldown = COOLDOWN_STEPS
            return Offer("easier", "Want a bit more help?",
                         "These steps have been tough, and you kept going. That's great! At "
                         f"**{easier.title()}** you get {_LEVEL_PITCH[easier]} You can switch back any time.",
                         [(f"Switch to {easier.title()}", f"level:{easier}"), ("I'll keep going", "dismiss")])
        return None

    # ---------------------------------------------------------------- helpers
    def _once(self, key: str, offer: Offer) -> Offer | None:
        if self.step is None or key in self.step.shown:
            return None
        self.step.shown.add(key)
        return offer


_LEVEL_PITCH = {
    "beginner": "full explanations, and hints whenever you want them.",
    "moderate": "a go first before hints, and a code review after each step.",
    "advanced": "just the goal, Python's real error messages, code reviews, and you can skip ahead.",
}

"""How much help a student wants: Beginner, Moderate or Advanced. Chosen by the student.

Beginner  new to Python: full explanations, hints any time (all three), tour offered.
Moderate  done some Python: the activity's own gradual release (guided -> scaffolded -> brief).
Advanced  confident (Year 9-10), "tutorial off": just the goal (explanation one click away),
          hints only after two tries and never the near-answer, no tour, and steps can be skipped.
"""
from __future__ import annotations

import re

LEVELS = ["beginner", "moderate", "advanced"]
DEFAULT = "beginner"

INFO = {
    "beginner": ("Beginner", "New to Python. Full explanations, and hints whenever you want them."),
    "moderate": ("Moderate", "You've done some Python. Help fades as you go: have a try, then hints unlock."),
    "advanced": ("Advanced", "Confident with Python (Year 9-10). Tutorial off: just the goal, fewer hints, "
                             "and you can skip steps you already know."),
}

# The activity's own support level -> (hints unlock after N tries, how many hint tiers you can see)
SUPPORT_RULES = {"guided": (0, 3), "scaffolded": (1, 3), "brief": (2, 2)}

_GOAL = re.compile(r"\*\*(Your task|Goal|Your goal)\b[^*]*\*\*")


def normalise(level: str | None) -> str:
    return level if level in LEVELS else DEFAULT


def hint_rules(level: str, support: str) -> tuple[int, int]:
    if level == "beginner":
        return 0, 3
    if level == "advanced":
        return 2, 2
    return SUPPORT_RULES.get(support, SUPPORT_RULES["scaffolded"])


def goal_text(step: dict) -> str | None:
    """The short version of a step for Advanced: its `goal`, or the text from 'Your task' / 'Goal' on."""
    if step.get("goal"):
        return step["goal"]
    m = _GOAL.search(step.get("text", ""))
    if m is None or m.start() == 0:
        return None          # no shorter version: show the whole text
    return step["text"][m.start():]


def can_skip(level: str) -> bool:
    return level == "advanced"


def offer_tour(level: str) -> bool:
    return level != "advanced"

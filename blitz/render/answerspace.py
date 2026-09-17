"""Ruled writing space.

A revision sheet you can't write on is a reading sheet. Every non-multiple-choice
question gets faint ruled lines sized to the marks available, which also gives
the student an honest signal about how much the examiner expects.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

LINE_GAP = 5.6 * mm
RULE_COLOUR = colors.HexColor("#c9cdd6")


class RuledSpace(Flowable):
    """N faint horizontal rules for handwriting."""

    def __init__(self, width: float, lines: int, gap: float = LINE_GAP):
        super().__init__()
        self.width = width
        self.lines = max(0, lines)
        self.gap = gap
        self.height = self.lines * gap

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(RULE_COLOUR)
        c.setLineWidth(0.35)
        for i in range(self.lines):
            y = self.height - (i + 1) * self.gap + 1.5
            c.line(0, y, self.width, y)
        c.restoreState()


def lines_for_marks(marks: int | None, question_type: str = "") -> int:
    """How many ruled lines a question of this size deserves.

    Roughly one line per mark for short answers, tapering for long responses
    where a student will write more compactly (and often continue on lined paper).
    """
    if question_type.endswith("-mc"):
        return 0
    m = marks or 2
    if m <= 1:
        return 1
    if m <= 4:
        return m
    if m <= 6:
        return m - 1
    return min(m, 8)

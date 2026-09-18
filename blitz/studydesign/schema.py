"""The study design is the spine of this tool.

Every question in the corpus hangs off a key-knowledge dot point, every sheet is
built from a set of dot points, and nothing can be printed that isn't traceable
back to one. The dataclasses here mirror the VCAA document structure:

    StudyDesign -> Unit -> AreaOfStudy -> KeyKnowledge

`verified` marks whether a dot point's wording was imported from the official
VCAA PDF (True) or typed in by hand and not yet checked (False). The UI surfaces
unverified content so you never revise against wording the tool invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# The stock openers VCAA uses on most dot points, which carry no topic.
_OPENER = re.compile(
    r"^(?:investigate|analyse|analyze|apply|explain|describe|identify|model|"
    r"calculate|compare|interpret|discuss|distinguish|evaluate)"
    r"(?:\s+and\s+(?:apply|analyse|analyze|explain|compare|evaluate))?"
    r"(?:\s+(?:theoretically|practically|qualitatively|quantitatively|and))*"
    r"\s+(?:(?:the|that|a|an)\b\s+)?",
    re.IGNORECASE,
)


def shorten(text: str, words: int = 7) -> str:
    """Trim a study design dot point to something that fits on one line."""
    trimmed = _OPENER.sub("", text.strip(), count=1).strip()
    trimmed = trimmed or text.strip()
    # Cut at the first list marker or clause break, which is usually where the
    # dot point stops naming its topic and starts enumerating.
    for marker in (":", ";", " - ", ", including"):
        head = trimmed.split(marker)[0]
        if len(head) >= 12:
            trimmed = head
    parts = trimmed.split()
    out = " ".join(parts[:words])
    if len(parts) > words:
        out += "\u2026"
    return out[:1].upper() + out[1:] if out else text[:40]


@dataclass(frozen=True)
class KeyKnowledge:
    """One key-knowledge dot point — the atom the whole tool indexes against."""

    id: str  # e.g. "bm-u3-aos2-kk04"
    text: str
    verified: bool = False
    # Optional shorthand the UI shows in tight spaces, e.g. "Motivation theories".
    label: str | None = None

    @property
    def display(self) -> str:
        """A short name for tight spaces: the checklist, warnings, the UI.

        VCAA writes dot points as whole sentences, most of them opening with the
        same stock phrase ("investigate and apply theoretically and practically
        the …"). Printed verbatim they overflow the sheet's masthead and read as
        near-identical. So the boilerplate opener is stripped and the first real
        clause kept.
        """
        if self.label:
            return self.label
        return shorten(self.text)


@dataclass(frozen=True)
class AreaOfStudy:
    id: str  # e.g. "bm-u3-aos2"
    number: int
    title: str
    outcome: str  # the VCAA outcome statement for this AOS
    key_knowledge: tuple[KeyKnowledge, ...] = ()
    key_skills: tuple[str, ...] = ()

    @property
    def display(self) -> str:
        return f"AOS {self.number}: {self.title}"

    @property
    def unit_number(self) -> int | None:
        """The unit this area belongs to, read off its positional id."""
        import re

        m = re.search(r"-u(\d+)-aos", self.id)
        return int(m.group(1)) if m else None

    @property
    def display_with_unit(self) -> str:
        """Unambiguous when areas from both units appear side by side.

        Every unit has an AOS 1, so a sheet drawing on Unit 3 and Unit 4 listed
        "AOS 1: ..., AOS 1: ..." and looked like a duplicate.
        """
        unit = self.unit_number
        return f"U{unit} AOS {self.number}: {self.title}" if unit else self.display


@dataclass(frozen=True)
class Unit:
    id: str  # e.g. "bm-u3"
    number: int  # 3 or 4
    title: str
    areas_of_study: tuple[AreaOfStudy, ...] = ()

    @property
    def display(self) -> str:
        return f"Unit {self.number}: {self.title}"


@dataclass(frozen=True)
class QuestionType:
    """A question format that makes sense for this subject.

    Physics and Business Management are assessed very differently, so the
    available formats are per-subject data rather than a global enum.
    """

    id: str  # e.g. "bm-extended-response"
    label: str  # e.g. "Extended response"
    description: str
    typical_marks: tuple[int, ...] = ()
    # Roughly how much of a page one question of this type consumes, used by the
    # layout planner to hit exactly two pages. Calibrated in render/layout.py.
    default_weight: float = 1.0


@dataclass(frozen=True)
class StudyDesign:
    subject_id: str  # e.g. "business-management"
    subject_name: str  # e.g. "VCE Business Management"
    accreditation: str  # e.g. "2023-2027"
    source: str  # where the wording came from
    units: tuple[Unit, ...] = ()
    question_types: tuple[QuestionType, ...] = ()
    command_terms: dict[str, str] = field(default_factory=dict)

    # -- lookups ---------------------------------------------------------

    def unit(self, number: int) -> Unit:
        for u in self.units:
            if u.number == number:
                return u
        raise KeyError(f"{self.subject_id} has no unit {number}")

    def area(self, aos_id: str) -> AreaOfStudy:
        for u in self.units:
            for a in u.areas_of_study:
                if a.id == aos_id:
                    return a
        raise KeyError(f"unknown area of study: {aos_id}")

    def key_knowledge(self, kk_id: str) -> KeyKnowledge:
        for kk in self.all_key_knowledge():
            if kk.id == kk_id:
                return kk
        raise KeyError(f"unknown key knowledge: {kk_id}")

    def all_areas(self) -> list[AreaOfStudy]:
        return [a for u in self.units for a in u.areas_of_study]

    def all_key_knowledge(self) -> list[KeyKnowledge]:
        return [kk for a in self.all_areas() for kk in a.key_knowledge]

    def area_of(self, kk_id: str) -> AreaOfStudy:
        for a in self.all_areas():
            if any(kk.id == kk_id for kk in a.key_knowledge):
                return a
        raise KeyError(f"unknown key knowledge: {kk_id}")

    def question_type(self, qt_id: str) -> QuestionType:
        for qt in self.question_types:
            if qt.id == qt_id:
                return qt
        raise KeyError(f"unknown question type: {qt_id}")

    @property
    def fully_verified(self) -> bool:
        return all(kk.verified for kk in self.all_key_knowledge())

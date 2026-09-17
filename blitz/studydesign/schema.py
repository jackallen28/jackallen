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

from dataclasses import dataclass, field


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
        return self.label or self.text


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

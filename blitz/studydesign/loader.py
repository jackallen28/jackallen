"""Load study designs from YAML into the frozen dataclasses."""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

from ..config import STUDY_DESIGN_DIR
from .schema import AreaOfStudy, KeyKnowledge, QuestionType, StudyDesign, Unit


def _key_knowledge(raw: dict, aos_id: str, index: int) -> KeyKnowledge:
    if isinstance(raw, str):
        raw = {"text": raw}
    return KeyKnowledge(
        id=raw.get("id") or f"{aos_id}-kk{index:02d}",
        text=raw["text"].strip(),
        verified=bool(raw.get("verified", False)),
        label=raw.get("label"),
    )


def _area(raw: dict, unit_id: str) -> AreaOfStudy:
    number = int(raw["number"])
    aos_id = raw.get("id") or f"{unit_id}-aos{number}"
    return AreaOfStudy(
        id=aos_id,
        number=number,
        title=raw["title"].strip(),
        outcome=raw.get("outcome", "").strip(),
        key_knowledge=tuple(
            _key_knowledge(kk, aos_id, i)
            for i, kk in enumerate(raw.get("key_knowledge", []), start=1)
        ),
        key_skills=tuple(s.strip() for s in raw.get("key_skills", [])),
    )


def _unit(raw: dict, subject_id: str) -> Unit:
    number = int(raw["number"])
    unit_id = raw.get("id") or f"{subject_id}-u{number}"
    return Unit(
        id=unit_id,
        number=number,
        title=raw["title"].strip(),
        areas_of_study=tuple(_area(a, unit_id) for a in raw.get("areas_of_study", [])),
    )


def _question_type(raw: dict) -> QuestionType:
    return QuestionType(
        id=raw["id"],
        label=raw["label"],
        description=raw.get("description", "").strip(),
        typical_marks=tuple(int(m) for m in raw.get("typical_marks", [])),
        default_weight=float(raw.get("default_weight", 1.0)),
    )


def parse_study_design(raw: dict) -> StudyDesign:
    subject_id = raw["subject_id"]
    return StudyDesign(
        subject_id=subject_id,
        subject_name=raw["subject_name"],
        accreditation=str(raw.get("accreditation", "")),
        source=raw.get("source", ""),
        units=tuple(_unit(u, subject_id) for u in raw.get("units", [])),
        question_types=tuple(_question_type(q) for q in raw.get("question_types", [])),
        command_terms=dict(raw.get("command_terms", {})),
    )


def load_study_design_file(path: Path) -> StudyDesign:
    with path.open(encoding="utf-8") as fh:
        return parse_study_design(yaml.safe_load(fh))


@functools.lru_cache(maxsize=None)
def load_study_design(subject_id: str) -> StudyDesign:
    path = STUDY_DESIGN_DIR / f"{subject_id}.yaml"
    if not path.exists():
        available = ", ".join(s.subject_id for s in list_subjects()) or "none"
        raise FileNotFoundError(
            f"No study design for {subject_id!r} (available: {available})"
        )
    return load_study_design_file(path)


def list_subjects() -> list[StudyDesign]:
    """Every study design shipped with the tool, in filename order."""
    designs = []
    for path in sorted(STUDY_DESIGN_DIR.glob("*.yaml")):
        try:
            designs.append(load_study_design_file(path))
        except Exception as exc:  # a malformed file shouldn't hide the good ones
            print(f"warning: skipping study design {path.name}: {exc}")
    return designs

"""The objects that travel between the UI, the picker and the renderer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class SheetSpec:
    """Everything the student chose on the form."""

    subject_id: str
    kk_ids: list[str] = field(default_factory=list)      # selected dot points
    question_type_ids: list[str] = field(default_factory=list)
    notes: str = ""                                       # free-text nudge
    title: str = ""
    difficulty: str = "mixed"                             # easy | mixed | hard
    include_solutions: bool = True
    prefer_figures: bool = True                           # favour diagram questions
    allow_generated: bool = True                          # fill gaps with generated Qs
    seed: int | None = None                               # reproducible sheets
    exclude_question_ids: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "SheetSpec":
        return cls(**json.loads(raw))


@dataclass
class Question:
    """A question as the renderer needs it."""

    id: str
    subject_id: str
    question_type: str
    body: str
    stem: str | None = None
    parts: list[str] = field(default_factory=list)
    options: list[str] | None = None
    answer: str | None = None
    answer_figure: str | None = None
    marks: int | None = None
    difficulty: int | None = None
    figure_path: str | None = None
    figure_caption: str | None = None
    citation: str = ""
    source_id: str = ""
    source_kind: str = ""
    generated: bool = False
    verified: bool = False
    render_mode: str = "text"      # 'text' or 'crop' — see db.py
    answer_mode: str = "text"
    provenance: str | None = None
    kk_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row, kk_ids: list[str] | None = None) -> "Question":
        d = dict(row)
        opts = d.get("options")
        return cls(
            id=d["id"],
            subject_id=d["subject_id"],
            question_type=d["question_type"],
            body=d["body"],
            stem=d.get("stem"),
            parts=json.loads(d["parts"]) if d.get("parts") else [],
            options=json.loads(opts) if opts else None,
            answer=d.get("answer"),
            answer_figure=d.get("answer_figure"),
            marks=d.get("marks"),
            difficulty=d.get("difficulty"),
            figure_path=d.get("figure_path"),
            figure_caption=d.get("figure_caption"),
            citation=d.get("citation") or "",
            source_id=d.get("source_id") or "",
            source_kind=d.get("source_kind") or "",
            generated=bool(d.get("generated")),
            verified=bool(d.get("verified")),
            render_mode=d.get("render_mode") or "text",
            answer_mode=d.get("answer_mode") or "text",
            provenance=d.get("provenance"),
            kk_ids=kk_ids or [],
        )

    @property
    def has_figure(self) -> bool:
        return bool(self.figure_path)

    @property
    def is_cropped(self) -> bool:
        """True when the sheet must show the page image rather than the text."""
        return self.render_mode == "crop" and bool(self.figure_path)


@dataclass
class SheetPlan:
    """The picked questions plus what the picker couldn't satisfy."""

    spec: SheetSpec
    questions: list[Question] = field(default_factory=list)
    uncovered_kk_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_pages: float = 0.0

    @property
    def total_marks(self) -> int:
        return sum(q.marks or 0 for q in self.questions)

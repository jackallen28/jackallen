"""Extract a draft question pack from a PDF, deterministically.

No model, no network. On a 1000-page Checkpoints this takes about 40 seconds on
a laptop, so there is nothing to schedule or resume — it finishes while you
watch.

The point is not that it is as good as a person reading the book. It is that it
is right about most questions and *honest about which ones it isn't*. Every
question carries a `review` block listing what is uncertain, so the expensive
pass — a person, or a model — only has to look at the minority that is flagged
rather than all 1300 questions.

Output is a pack (docs/question-pack-schema.md), so the draft, the reviewed
version and a hand-written pack are all the same kind of file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
import re
from datetime import date
from pathlib import Path

from ..studydesign import StudyDesign, load_study_design
from . import extract, segment
from .segment import RawQuestion
from .tag import KeywordTagger

# Below this, a tag is a guess rather than a finding.
LOW_CONFIDENCE = 0.55
# A question body far outside these bounds is usually a segmentation failure.
SHORT_BODY = 40
LONG_BODY = 2600


@dataclass
class DraftReport:
    pages: int = 0
    questions: int = 0
    flagged: int = 0
    counts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        clean = self.questions - self.flagged
        pct = (clean / self.questions * 100) if self.questions else 0
        lines = [
            f"{self.questions} questions from {self.pages} pages",
            f"  {clean} need no review ({pct:.0f}%)",
            f"  {self.flagged} flagged:",
        ]
        for reason, n in sorted(self.counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"      {n:5}  {reason}")
        return "\n".join(lines)


# An inline run of option letters in the body means _split_options did not fire.
INLINE_OPTIONS = re.compile(r"\bA\b.{4,220}?\bB\b.{4,220}?\bC\b.{4,220}?\bD\b",
                            re.DOTALL)


def _review_flags(q: RawQuestion, tags, body: str) -> list[str]:
    """What a human actually has to look at.

    Kept deliberately narrow. The first version flagged 73% of the book, which
    is no better than reviewing all of it: it counted "the source prints no
    worked solution" and "this question is a crop" as problems, when both are
    facts already recorded and handled. A flag earns its place only if a person
    looking at it would change something.
    """
    flags: list[str] = []
    if tags.rejected or not tags.kk_ids:
        flags.append("untagged: no dot point matched")
    elif tags.confidence < LOW_CONFIDENCE:
        flags.append(f"low-confidence tag ({tags.confidence:.2f})")
    if not q.options and INLINE_OPTIONS.search(body):
        flags.append("multiple-choice options look unsplit — check the boundary")
    if not q.marks and not q.options and not q.parts:
        flags.append("no marks and no options — may be a fragment")
    if len(body) < SHORT_BODY:
        flags.append("very short — may be a fragment")
    if len(body) > LONG_BODY:
        flags.append("very long — may be two questions run together")
    return flags


def _notes_for(q: RawQuestion) -> list[str]:
    """Facts worth recording that are not problems to fix."""
    notes: list[str] = []
    if not q.answer:
        notes.append("Source answer not supplied; no answer generated.")
    if q.needs_crop:
        notes.append(f"Question rendered as a page crop: {q.crop_reason}.")
    if q.answer_needs_crop:
        notes.append(f"Solution rendered as a page crop: {q.answer_crop_reason}.")
    return notes


def _union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _pad(doc, page_index: int, bbox, x: float = 8.0, y: float = 4.0) -> list[float]:
    """Widen a crop slightly so it doesn't look clipped on the sheet."""
    page = doc[page_index]
    x0, y0, x1, y1 = bbox
    return [round(max(0.0, x0 - x), 1), round(max(0.0, y0 - y), 1),
            round(min(page.rect.width, x1 + x), 1),
            round(min(page.rect.height, y1 + y), 1)]


def _figure_ref(text: str) -> bool:
    from .pipeline import FIGURE_REF

    return bool(FIGURE_REF.search(text))


def build_draft(
    pdf_path: str | Path,
    *,
    subject_id: str,
    source_id: str,
    title: str | None = None,
    kind: str = "checkpoints",
    edition: str | None = None,
    pages: tuple[int, int] | None = None,
    design: StudyDesign | None = None,
    progress=print,
) -> tuple[dict, DraftReport]:
    """Return a pack dict plus a report on what needs reviewing."""
    from ..corpus.sample import fingerprint
    from .pipeline import _figure_for

    design = design or load_study_design(subject_id)
    pdf_path = Path(pdf_path).resolve()
    title = title or pdf_path.stem.replace("-", " ").title()

    doc = extract.open_pdf(pdf_path)
    first, last = pages or (0, doc.page_count)
    last = min(last, doc.page_count)

    report = DraftReport(pages=last - first)
    progress(f"  reading {report.pages} pages…")
    questions = segment.segment_document(doc, first, last)
    report.questions = len(questions)
    progress(f"  found {len(questions)} questions; tagging…")

    tagger = KeywordTagger(design)
    entries = []

    for n, q in enumerate(questions, start=1):
        body = q.full_text
        tags = tagger.tag(body, q.options, q.marks)

        figures = []
        rect, page_index = _figure_for(doc, q)

        if q.needs_crop and q.bbox:
            # The text can't be trusted, so the crop has to cover the whole
            # question, not just a diagram it happens to contain. Without this
            # the draft silently downgraded every unreflowable question back to
            # its mangled text.
            span = _union(q.bbox, rect if page_index == q.page_index else None)
            figures.append({
                "role": "question",
                "page": q.page_index,
                "bbox": _pad(doc, q.page_index, span),
                "caption": None,
            })
        elif rect:
            figures.append({
                "role": "question",
                "page": page_index,
                "bbox": [round(v, 1) for v in rect],
            })

        if q.answer_needs_crop and q.answer_bbox:
            figures.append({
                "role": "answer",
                "page": q.end_page_index,
                "bbox": _pad(doc, q.end_page_index, q.answer_bbox),
            })

        entry: dict = {
            "id": f"{source_id.upper()}-{n:04d}",
            "kk_ids": tags.kk_ids,
            "question_type": tags.question_type or design.question_types[0].id,
            "stem": q.text or body,
        }
        if q.printed_page:
            entry["printed_page"] = q.printed_page
        if q.number:
            entry["source_number"] = q.number
        if q.provenance:
            entry["provenance"] = q.provenance
        if q.marks:
            entry["marks"] = q.marks
        if tags.difficulty:
            entry["difficulty"] = tags.difficulty
        if q.parts:
            entry["parts"] = [{"text": p} for p in q.parts]
        if q.options:
            entry["options"] = q.options
        if q.answer:
            entry["answer"] = {"text": q.answer}
        if figures:
            entry["figures"] = figures
        if q.needs_crop and any(f["role"] == "question" for f in figures):
            entry["render_mode"] = "crop"
        if q.answer_needs_crop and any(f["role"] == "answer" for f in figures):
            entry["answer_mode"] = "crop"
        notes = _notes_for(q)
        if notes:
            entry["notes"] = " ".join(notes)

        flags = _review_flags(q, tags, body)
        if _figure_ref(body) and not figures:
            flags.append("text mentions a figure but none was found")
        if flags:
            entry["review"] = flags
            report.flagged += 1
            for f in flags:
                key = f.split(":")[0].split("(")[0].strip()
                report.counts[key] = report.counts.get(key, 0) + 1

        entries.append(entry)

        if n % 200 == 0:
            progress(f"    {n}/{len(questions)}…")

    doc.close()

    pack = {
        "pack_version": "1.0",
        "subject_id": subject_id,
        "study_design_fingerprint": fingerprint(design),
        "_generated": {
            "by": "blitz extract-pack",
            "on": date.today().isoformat(),
            "note": "Draft. Every entry with a 'review' key needs a human or a "
                    "model to check it; the rest are mechanical extractions. "
                    "Delete the 'review' keys as you clear them.",
        },
        "source": {
            "id": source_id,
            "kind": kind,
            "title": title,
            "edition": edition,
            "pdf": str(pdf_path),
        },
        "questions": entries,
    }
    return pack, report


def write_draft(pack: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def review_queue(pack: dict) -> list[dict]:
    """Just the entries that need attention, smallest useful payload.

    Handing a model 1300 questions to re-check is most of the cost of indexing
    the book in the first place. Handing it only the flagged ones is the point.
    """
    return [
        {
            "id": q["id"],
            "review": q["review"],
            "printed_page": q.get("printed_page"),
            "source_number": q.get("source_number"),
            "stem": q.get("stem", "")[:600],
            "options": q.get("options"),
            "kk_ids": q.get("kk_ids"),
        }
        for q in pack["questions"] if q.get("review")
    ]

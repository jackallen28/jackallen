"""Turn a source PDF into rows in the question index.

    PDF -> line reconstruction -> question segmentation -> crops -> tags -> sqlite

Run it once per book. It is idempotent: question ids are derived from the source,
page and text, so re-ingesting updates rows in place rather than duplicating them.

Where a question or its solution cannot be faithfully turned back into text —
stacked fractions, equation-editor glyphs — the pipeline crops the real page
region and marks the row to be rendered as an image. The text is still stored so
search and dot-point tagging keep working; it just never reaches the sheet.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..db import insert_question, upsert_source
from ..studydesign import StudyDesign, load_study_design
from . import extract, segment
from .segment import RawQuestion
from .tag import get_tagger


@dataclass
class IngestReport:
    source_id: str
    pages_read: int = 0
    candidates: int = 0
    kept: int = 0
    rejected: int = 0
    with_figures: int = 0
    with_solutions: int = 0
    cropped_questions: int = 0
    cropped_solutions: int = 0
    multi_part: int = 0
    untagged_samples: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.source_id}: {self.pages_read} pages, {self.candidates} questions "
            f"found, {self.kept} indexed, {self.rejected} untagged\n"
            f"    {self.with_figures} with figures, {self.with_solutions} with "
            f"solutions, {self.multi_part} multi-part\n"
            f"    {self.cropped_questions} questions and {self.cropped_solutions} "
            f"solutions rendered as page crops (maths that won't reflow)"
        )


def _question_id(source_id: str, page: int, number: str | None, text: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{page}|{number}|{text[:200]}".encode())
    return f"{source_id}-p{page:04d}-{digest.hexdigest()[:10]}"


def _citation(title: str, printed_page: str | None, number: str | None,
              provenance: str | None) -> str:
    bits = [title]
    if printed_page:
        bits.append(f"p. {printed_page}")
    if number:
        bits.append(f"Q{number}")
    out = ", ".join(bits)
    if provenance:
        out += f" [{provenance}]"
    return out


def _union(
    a: tuple[float, float, float, float] | None,
    b: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float] | None:
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _figure_for(page, q: RawQuestion) -> tuple[float, float, float, float] | None:
    """The diagram belonging to this question, if any.

    Checkpoints fences each question between full-width rules, and the figure
    usually sits above its question rather than below. Using the rules as the
    boundary is far more reliable than a fixed distance threshold.
    """
    if not q.bbox:
        return None
    from .textflow import horizontal_rules

    rules = horizontal_rules(page)
    _, qy0, _, qy1 = q.bbox
    top = max([y for y in rules if y < qy0 + 2], default=0.0)
    bottom = min([y for y in rules if y > qy1 - 2], default=page.rect.height)

    regions = [
        r for r in _page_figures(page)
        if r[1] >= top - 4 and r[3] <= bottom + 4
    ]
    if not regions:
        return None
    return max(regions, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))


def _page_figures(page) -> list[tuple[float, float, float, float]]:
    content = extract.read_page_content(page)
    return content.figure_regions


def _crop_span(page, bbox, pad_x: float = 8.0):
    """Widen a crop to the full text column so it doesn't look clipped."""
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return (max(0.0, x0 - pad_x), y0, min(page.rect.width, x1 + pad_x), y1)


def ingest_pdf(
    conn: sqlite3.Connection,
    pdf_path: str | Path,
    *,
    source_id: str,
    subject_id: str,
    kind: str = "checkpoints",
    title: str | None = None,
    edition: str | None = None,
    page_offset: int = 0,
    pages: tuple[int, int] | None = None,
    design: StudyDesign | None = None,
    use_model: bool = True,
    progress=print,
) -> IngestReport:
    """Index one PDF.

    `page_offset` only matters when the book does not print its own page numbers
    next to each question; Checkpoints does ("Question 12/ 11"), and that number
    is preferred when present.
    """
    design = design or load_study_design(subject_id)
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    title = title or pdf_path.stem.replace("-", " ").title()
    upsert_source(
        conn, id=source_id, subject_id=subject_id, kind=kind, title=title,
        path=str(pdf_path), edition=edition, page_offset=page_offset,
        ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    doc = extract.open_pdf(pdf_path)
    first, last = pages or (0, doc.page_count)
    last = min(last, doc.page_count)

    report = IngestReport(source_id=source_id)
    report.pages_read = last - first

    progress(f"  reading {report.pages_read} pages…")
    questions = segment.segment_document(doc, first, last)
    report.candidates = len(questions)
    progress(f"  found {len(questions)} questions")

    staged: list[dict] = []
    for q in questions:
        page = doc[q.page_index]

        figure_path = None
        render_mode = "text"
        if q.needs_crop:
            # The text can't be trusted, so show the page itself.
            rect = _crop_span(page, _union(q.bbox, _figure_for(page, q)))
            figure_path = extract.crop(doc, q.page_index, rect, tag=source_id) if rect else None
            render_mode = "crop" if figure_path else "text"
        else:
            rect = _figure_for(page, q)
            if rect:
                figure_path = extract.crop(doc, q.page_index, rect, tag=source_id)

        answer_figure = None
        answer_mode = "text"
        if q.answer_needs_crop and q.answer_bbox:
            a_page_index = next(
                (i for i in range(q.page_index, q.end_page_index + 1)), q.page_index
            )
            rect = _crop_span(doc[a_page_index], q.answer_bbox)
            answer_figure = extract.crop(doc, a_page_index, rect, tag=f"{source_id}-a")
            answer_mode = "crop" if answer_figure else "text"

        staged.append({
            "raw": q,
            "text": q.full_text,
            "stem": q.text,
            "parts": q.parts,
            "options": q.options,
            "marks": q.marks,
            "answer": q.answer,
            "figure_path": figure_path,
            "render_mode": render_mode,
            "answer_figure": answer_figure,
            "answer_mode": answer_mode,
        })

    progress(f"  tagging {len(staged)} questions against the study design…")
    tagger = get_tagger(design, prefer_model=use_model)
    if hasattr(tagger, "tag_all"):
        results = tagger.tag_all(staged)
    else:
        results = [tagger.tag(s["text"], s["options"], s["marks"]) for s in staged]

    for item, tags in zip(staged, results):
        if tags.rejected or not tags.kk_ids:
            report.rejected += 1
            if len(report.untagged_samples) < 5:
                report.untagged_samples.append(item["text"][:110])
            continue

        q: RawQuestion = item["raw"]
        qid = _question_id(source_id, q.page_index, q.number, item["text"])
        printed = q.printed_page or (
            str(q.page_index + 1 + page_offset) if page_offset else None
        )
        insert_question(conn, {
            "id": qid,
            "subject_id": subject_id,
            "source_id": source_id,
            "question_type": tags.question_type or design.question_types[0].id,
            "body": item["text"],
            "stem": item["stem"] or None,
            "parts": json.dumps(item["parts"]) if item["parts"] else None,
            "options": item["options"] or None,
            "answer": item["answer"],
            "answer_figure": item["answer_figure"],
            "marks": item["marks"],
            "difficulty": tags.difficulty,
            "figure_path": item["figure_path"],
            "render_mode": item["render_mode"],
            "answer_mode": item["answer_mode"],
            "provenance": q.provenance,
            "pdf_page": q.page_index,
            "printed_page": printed,
            "citation": _citation(title, printed, q.number, q.provenance),
            "generated": 0,
            "verified": 0,
        }, tags.kk_ids)

        report.kept += 1
        report.with_figures += 1 if item["figure_path"] else 0
        report.with_solutions += 1 if item["answer"] else 0
        report.cropped_questions += 1 if item["render_mode"] == "crop" else 0
        report.cropped_solutions += 1 if item["answer_mode"] == "crop" else 0
        report.multi_part += 1 if q.parts else 0

    conn.commit()
    doc.close()
    progress("  " + report.summary())
    return report


def coverage_report(conn: sqlite3.Connection, design: StudyDesign) -> list[dict]:
    """Per-dot-point counts, so you can see where the index is thin."""
    from ..db import coverage

    counts = coverage(conn, design.subject_id)
    rows = []
    for area in design.all_areas():
        for kk in area.key_knowledge:
            rows.append({
                "aos": area.display,
                "kk_id": kk.id,
                "label": kk.display,
                "count": counts.get(kk.id, 0),
                "verified": kk.verified,
            })
    return rows

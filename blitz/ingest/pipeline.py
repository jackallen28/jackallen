"""Turn a source PDF into rows in the question index.

    PDF -> pages -> raw questions -> figure crops -> tags -> sqlite

Run it once per book. It is idempotent: question ids are derived from the source
and page, so re-ingesting updates rows in place rather than duplicating them.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..db import insert_question, upsert_source
from ..studydesign import StudyDesign, load_study_design
from . import extract, segment
from .tag import KeywordTagger, TagResult, get_tagger

# Text that follows a question in Checkpoints-style books and is really the
# worked solution for it.
SOLUTION_CUE = re.compile(
    r"^\s*(solution|answer|worked solution|explanation)\s*[:.]?\s*",
    re.IGNORECASE,
)


@dataclass
class IngestReport:
    source_id: str
    pages_read: int = 0
    candidates: int = 0
    kept: int = 0
    rejected: int = 0
    with_figures: int = 0
    with_solutions: int = 0
    untagged_samples: list[str] = None

    def __post_init__(self):
        if self.untagged_samples is None:
            self.untagged_samples = []

    def summary(self) -> str:
        return (
            f"{self.source_id}: {self.pages_read} pages, {self.candidates} candidates, "
            f"{self.kept} indexed ({self.with_figures} with figures, "
            f"{self.with_solutions} with solutions), {self.rejected} rejected"
        )


def _question_id(source_id: str, page_index: int, number: str | None, text: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{page_index}|{number}|{text[:200]}".encode())
    return f"{source_id}-p{page_index:04d}-{digest.hexdigest()[:10]}"


def _citation(source_title: str, printed_page: str | None, number: str | None) -> str:
    bits = [source_title]
    if printed_page:
        bits.append(f"p. {printed_page}")
    if number:
        bits.append(f"Q{number}")
    return ", ".join(bits)


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
    solutions_from: str | None = None,
    progress=print,
) -> IngestReport:
    """Index one PDF.

    `page_offset` is (printed page number - pdf page index), so citations show
    the number a student will actually find in the book.
    `solutions_from` names another already-ingested source whose answers should
    be matched to these questions (for books that ship a separate answer PDF).
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

    staged: list[dict] = []
    for index in range(first, last):
        page = extract.read_page(doc, index, page_offset=page_offset)
        report.pages_read += 1
        regions = page.figure_regions

        for rq in segment.segment_page(page):
            report.candidates += 1
            body, answer = _split_solution(rq.text)
            figure_rect = segment.nearest_figure(rq, regions)
            figure_path = None
            if figure_rect:
                figure_path = extract.crop(doc, index, figure_rect, tag=source_id)

            staged.append({
                "raw": rq,
                "text": body,
                "options": rq.options,
                "marks": rq.marks,
                "answer": answer,
                "figure_path": figure_path,
                "page_index": index,
                "printed_page": rq.printed_page,
            })

        if report.pages_read % 25 == 0:
            progress(f"  read {report.pages_read} pages, {len(staged)} candidates")

    progress(f"  tagging {len(staged)} candidates against the study design…")
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

        rq = item["raw"]
        qid = _question_id(source_id, item["page_index"], rq.number, item["text"])
        insert_question(conn, {
            "id": qid,
            "subject_id": subject_id,
            "source_id": source_id,
            "question_type": tags.question_type or design.question_types[0].id,
            "body": item["text"],
            "options": item["options"] or None,
            "answer": item["answer"],
            "marks": item["marks"],
            "difficulty": tags.difficulty,
            "figure_path": item["figure_path"],
            "pdf_page": item["page_index"],
            "printed_page": item["printed_page"],
            "citation": _citation(title, item["printed_page"], rq.number),
            "generated": 0,
            "verified": 0,
        }, tags.kk_ids)

        report.kept += 1
        report.with_figures += 1 if item["figure_path"] else 0
        report.with_solutions += 1 if item["answer"] else 0

    conn.commit()
    doc.close()
    progress("  " + report.summary())
    return report


def _split_solution(text: str) -> tuple[str, str | None]:
    """Separate an inline worked solution from the question stem."""
    for line_break in ("\n", ". "):
        parts = text.split(line_break)
        for i, part in enumerate(parts):
            if SOLUTION_CUE.match(part):
                body = line_break.join(parts[:i]).strip()
                answer = SOLUTION_CUE.sub("", line_break.join(parts[i:])).strip()
                if body and answer:
                    return body, answer
    m = SOLUTION_CUE.search(text)
    if m and m.start() > 30:
        return text[:m.start()].strip(), text[m.end():].strip()
    return text, None


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

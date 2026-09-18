"""One command: a study design and a book in, an index out.

    blitz index book.pdf --subject physics [--study-design sd.pdf]

Decides what kind of book it is, runs the right question extractor, indexes the
teaching content as well, tags everything to the study design, writes it all to
the database, and says what it found and what it is unsure about. No model, no
network; a 1000-page book takes about a minute.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..db import insert_passage, insert_question, upsert_source
from ..studydesign import StudyDesign, load_study_design
from . import extract
from .detect import Detection, detect_kind
from .docx import docx_to_pdf, is_docx
from .passages import extract_passages, tag_passages
from .segment import RawQuestion, segment_document
from .tag import KeywordTagger
from .textbook import segment_textbook


@dataclass
class IndexReport:
    source_id: str
    kind: str = "unknown"
    detection: str = ""
    pages: int = 0
    questions_found: int = 0
    questions_indexed: int = 0
    questions_untagged: int = 0
    with_figures: int = 0
    with_solutions: int = 0
    cropped: int = 0
    passages_found: int = 0
    passages_indexed: int = 0
    passages_untagged: int = 0
    review: list[str] = field(default_factory=list)
    study_design: str | None = None

    def summary(self) -> str:
        lines = [f"{self.source_id}: {self.pages} pages, detected as {self.detection}"]
        if self.study_design:
            lines.append(f"  study design: {self.study_design}")
        lines.append(
            f"  questions: {self.questions_found} found, {self.questions_indexed} "
            f"indexed, {self.questions_untagged} untagged")
        lines.append(
            f"             {self.with_figures} with figures, {self.with_solutions} "
            f"with solutions, {self.cropped} as page crops")
        lines.append(
            f"  content  : {self.passages_found} sections found, "
            f"{self.passages_indexed} indexed, {self.passages_untagged} untagged")
        if self.review:
            lines.append(f"  {len(self.review)} item(s) to review:")
            lines += [f"      · {r}" for r in self.review[:8]]
            if len(self.review) > 8:
                lines.append(f"      … and {len(self.review) - 8} more")
        return "\n".join(lines)


def _qid(source_id: str, q: RawQuestion) -> str:
    digest = hashlib.sha1(
        f"{source_id}|{q.page_index}|{q.number}|{q.full_text[:200]}".encode())
    return f"{source_id}-p{q.page_index:04d}-{digest.hexdigest()[:10]}"


def _pid(source_id: str, title: str, page: int) -> str:
    digest = hashlib.sha1(f"{source_id}|{page}|{title}".encode())
    return f"{source_id}-s{page:04d}-{digest.hexdigest()[:10]}"


def _citation(title: str, printed: str | None, number: str | None,
              provenance: str | None) -> str:
    bits = [title]
    if printed:
        bits.append(f"p. {printed}")
    if number:
        bits.append(f"Q{number}")
    out = ", ".join(bits)
    if provenance:
        out += f" [{provenance}]"
    return out


def index_book(
    conn: sqlite3.Connection,
    pdf_path: str | Path,
    *,
    subject_id: str,
    source_id: str,
    title: str | None = None,
    kind: str = "auto",
    edition: str | None = None,
    page_offset: int = 0,
    pages: tuple[int, int] | None = None,
    study_design_pdf: str | Path | None = None,
    design: StudyDesign | None = None,
    include_content: bool = True,
    progress=print,
) -> IndexReport:
    """Index one book against one study design."""
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    title = title or pdf_path.stem.replace("-", " ").replace("_", " ").title()
    report = IndexReport(source_id=source_id)

    converted_from = None
    if is_docx(pdf_path):
        # A Word file is rendered to a PDF with the typography the extractors
        # read (headings larger than body, list numbers visible, images
        # inline) and then treated as any other book.
        progress(f"  rendering {pdf_path.name} to PDF…")
        converted_from = pdf_path
        pdf_path = docx_to_pdf(pdf_path)
        report.review.append(
            f"converted from Word ({converted_from.name}); page numbers in "
            "citations are the rendered PDF's, not Word's")

    # 1. Study design, if one was handed over with the book.
    if study_design_pdf:
        from ..studydesign.importer import import_study_design
        from ..studydesign.loader import load_study_design as _load

        progress(f"  importing study design from {Path(study_design_pdf).name}…")
        out = import_study_design(study_design_pdf, subject_id)
        _load.cache_clear()
        report.study_design = f"imported from {Path(study_design_pdf).name} → {out.name}"
        design = None
    design = design or load_study_design(subject_id)
    if not report.study_design:
        report.study_design = (
            f"{design.subject_name} ({'verified' if design.fully_verified else 'DRAFT'})")

    doc = extract.open_pdf(pdf_path)
    first, last = pages or (0, doc.page_count)
    last = min(last, doc.page_count)
    report.pages = last - first

    # 2. What kind of book is this?
    detection: Detection = detect_kind(doc)
    resolved = kind if kind != "auto" else detection.kind
    if resolved == "unknown":
        resolved = "textbook"          # the more forgiving extractor
        report.review.append(
            "could not tell what kind of book this is; treated as a textbook — "
            "pass --kind to override")
    report.kind = resolved
    report.detection = (f"{resolved} (auto: {detection.summary()})"
                        if kind == "auto" else f"{resolved} (forced)")
    progress(f"  {report.detection}")

    upsert_source(
        conn, id=source_id, subject_id=subject_id, kind=resolved, title=title,
        path=str(pdf_path), edition=edition, page_offset=page_offset,
        ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

    tagger = KeywordTagger(design)

    # 3. Questions, with the extractor that matches the book.
    progress("  extracting questions…")
    if resolved == "checkpoints":
        questions = segment_document(doc, first, last)
    else:
        questions = segment_textbook(doc, first, last, printed_offset=page_offset)
    report.questions_found = len(questions)

    from .pipeline import _figure_for, _crop_span, _union

    for q in questions:
        tags = tagger.tag(q.full_text, q.options, q.marks)
        page = doc[q.page_index]
        figure_rect, figure_page = _figure_for(doc, q)

        figure_path, render_mode, pt_width = None, "text", None
        if q.needs_crop and q.bbox:
            same = figure_rect if figure_page == q.page_index else None
            rect = _crop_span(page, _union(q.bbox, same))
            figure_path = extract.crop(doc, q.page_index, rect, tag=source_id) if rect else None
            if figure_path:
                render_mode, pt_width = "crop", rect[2] - rect[0]
        elif figure_rect:
            figure_path = extract.crop(doc, figure_page, figure_rect, tag=source_id)
            pt_width = figure_rect[2] - figure_rect[0]

        answer_figure, answer_mode = None, "text"
        if q.answer_needs_crop and q.answer_bbox:
            rect = _crop_span(doc[q.end_page_index], q.answer_bbox)
            answer_figure = extract.crop(doc, q.end_page_index, rect, tag=f"{source_id}-a")
            if answer_figure:
                answer_mode = "crop"

        if tags.rejected or not tags.kk_ids:
            report.questions_untagged += 1
            if len(report.review) < 40:
                report.review.append(f"untagged question p.{q.page_index + 1}: "
                                     f"{q.full_text[:70]}…")
            continue

        printed = q.printed_page or (str(q.page_index + 1 + page_offset) if page_offset else None)
        insert_question(conn, {
            "id": _qid(source_id, q),
            "subject_id": subject_id, "source_id": source_id,
            "question_type": tags.question_type or design.question_types[0].id,
            "body": q.full_text, "stem": q.text or None,
            "parts": json.dumps(q.parts) if q.parts else None,
            "options": q.options or None,
            "answer": q.answer, "answer_figure": answer_figure,
            "marks": q.marks, "difficulty": tags.difficulty,
            "figure_path": figure_path, "figure_pt_width": pt_width,
            "render_mode": render_mode, "answer_mode": answer_mode,
            "provenance": q.provenance,
            "pdf_page": q.page_index, "printed_page": printed,
            "citation": _citation(title, printed, q.number, q.provenance),
            "context": q.stimulus or None,
            "generated": 0, "verified": 0,
        }, tags.kk_ids)
        report.questions_indexed += 1
        report.with_figures += 1 if figure_path and render_mode == "text" else 0
        report.with_solutions += 1 if q.answer else 0
        report.cropped += 1 if "crop" in (render_mode, answer_mode) else 0

    # 4. The teaching content. A Checkpoints book has none worth indexing —
    #    it is questions and solutions — and looking anyway turned option
    #    lines into "headings" and swept whole questions in as prose.
    if include_content and resolved == "checkpoints":
        progress("  skipping content: Checkpoints is a question book")
        include_content = False
    if include_content:
        progress("  indexing content…")
        passages = extract_passages(doc, first, last)
        tag_passages(passages, tagger)
        report.passages_found = len(passages)
        for p in passages:
            if not p.kk_ids:
                report.passages_untagged += 1
                continue
            insert_passage(conn, {
                "id": _pid(source_id, p.title, p.page_start),
                "subject_id": subject_id, "source_id": source_id,
                "title": p.title, "section": p.section_number, "level": p.level,
                "body": p.body,
                "page_start": p.page_start, "page_end": p.page_end,
                "printed_page": str(p.page_start + 1 + page_offset) if page_offset else None,
                "confidence": p.confidence,
            }, p.kk_ids)
            report.passages_indexed += 1

    conn.commit()
    doc.close()
    progress(report.summary())
    return report

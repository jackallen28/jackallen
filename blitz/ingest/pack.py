"""Import a curated question pack.

A pack is the structured index of one book — see docs/question-pack-schema.md.
It is the preferred way in. The heuristic extractor in this package exists for
when no pack is available; where one is, it wins, because a person (or a model
with the book in front of it) has already decided where each question starts and
ends, what it assesses, and whether its text can be trusted.

The import is all-or-nothing: the pack is validated in full first, and nothing
is written unless it is clean. A half-loaded pack is worse than none, because
the gaps are invisible once sheets start being generated from it.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import CROPS_DIR
from ..db import insert_question, upsert_source
from ..studydesign import StudyDesign, load_study_design

PACK_VERSION = "1.0"


@dataclass
class PackReport:
    path: str
    subject_id: str = ""
    source_id: str = ""
    questions: int = 0
    imported: int = 0
    with_figures: int = 0
    with_answers: int = 0
    cropped: int = 0
    untagged: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        head = f"{Path(self.path).name}: {self.questions} questions"
        if self.errors:
            return f"{head} — NOT IMPORTED, {len(self.errors)} error(s)"
        return (
            f"{head}, {self.imported} imported\n"
            f"    {self.with_figures} with figures, {self.with_answers} with "
            f"answers, {self.cropped} rendered as crops, {self.untagged} untagged"
        )


def _text_of(q: dict) -> str:
    """Stem plus parts, which is what gets searched and tagged."""
    bits = [q.get("stem", "")]
    for part in q.get("parts") or []:
        label = part.get("label")
        text = part.get("text", "")
        bits.append(f"{label}. {text}" if label else text)
    return " ".join(b for b in bits if b).strip()


def _answer_text(q: dict) -> str | None:
    answer = q.get("answer")
    if not answer:
        return None
    if isinstance(answer, str):
        return answer.strip() or None
    bits = [answer.get("text", "")]
    for part in answer.get("parts") or []:
        label = part.get("label")
        text = part.get("text", "")
        bits.append(f"{label}. {text}" if label else text)
    out = " ".join(b for b in bits if b).strip()
    return out or None


def _marks(q: dict) -> int | None:
    if q.get("marks") is not None:
        return int(q["marks"])
    parts = q.get("parts") or []
    total = sum(int(p["marks"]) for p in parts if p.get("marks") is not None)
    return total or None


def validate(pack: dict, design: StudyDesign, pack_dir: Path) -> PackReport:
    """Check a pack against the study design and the filesystem.

    Everything that could go wrong is collected and reported together — finding
    one bad dot point id per run would make a 1000-page pack unusable.
    """
    report = PackReport(path=str(pack_dir), subject_id=design.subject_id)
    err, warn = report.errors.append, report.warnings.append

    version = str(pack.get("pack_version", ""))
    if version and version.split(".")[0] != PACK_VERSION.split(".")[0]:
        err(f"pack_version {version} is not compatible with {PACK_VERSION}")

    source = pack.get("source") or {}
    if not source.get("id"):
        err("source.id is required and must be stable across re-imports")
    report.source_id = source.get("id", "")

    from ..corpus.sample import fingerprint

    stated = pack.get("study_design_fingerprint")
    actual = fingerprint(design)
    if stated and stated != actual:
        err(
            f"pack was built against a different {design.subject_id} study "
            f"design (fingerprint {stated}, now {actual}). Dot point ids are "
            "positional, so its kk_ids may point at the wrong dot points. "
            "Re-run `blitz dot-points` and rebuild the pack."
        )
    elif not stated:
        warn("pack states no study_design_fingerprint; dot point ids unverified")

    valid_kk = {kk.id for kk in design.all_key_knowledge()}
    valid_qt = {qt.id for qt in design.question_types}

    questions = pack.get("questions") or []
    report.questions = len(questions)
    if not questions:
        err("pack contains no questions")

    seen: set[str] = set()
    source_pdf = source.get("pdf")
    pdf_pages = _page_count(pack_dir, source_pdf) if source_pdf else None

    for i, q in enumerate(questions):
        where = f"question[{i}]" + (f" ({q.get('id')})" if q.get("id") else "")
        qid = q.get("id")
        if not qid:
            err(f"{where}: id is required")
        elif qid in seen:
            err(f"{where}: duplicate id")
        else:
            seen.add(qid)

        if not _text_of(q):
            err(f"{where}: has neither stem nor parts")

        unknown = [k for k in (q.get("kk_ids") or []) if k not in valid_kk]
        if unknown:
            err(f"{where}: unknown dot point id(s) {unknown}")
        elif not q.get("kk_ids"):
            report.untagged += 1

        qt = q.get("question_type")
        if qt and qt not in valid_qt:
            err(f"{where}: unknown question_type {qt!r} "
                f"(expected one of {sorted(valid_qt)})")

        for mode_key in ("render_mode", "answer_mode"):
            mode = q.get(mode_key, "text")
            if mode not in ("text", "crop"):
                err(f"{where}: {mode_key} must be 'text' or 'crop', got {mode!r}")

        for j, fig in enumerate(q.get("figures") or []):
            _validate_figure(fig, f"{where}.figures[{j}]", pack_dir,
                             source_pdf, pdf_pages, err)

        if q.get("render_mode") == "crop" and not _figures_for(q, "question"):
            err(f"{where}: render_mode is 'crop' but no question figure was given")
        if q.get("answer_mode") == "crop" and not _figures_for(q, "answer"):
            err(f"{where}: answer_mode is 'crop' but no answer figure was given")

    return report


def _validate_figure(fig: dict, where: str, pack_dir: Path, source_pdf,
                     pdf_pages: int | None, err) -> None:
    role = fig.get("role", "question")
    if role not in ("question", "answer"):
        err(f"{where}: role must be 'question' or 'answer', got {role!r}")

    has_file, has_box = bool(fig.get("file")), fig.get("page") is not None
    if has_file == has_box:
        err(f"{where}: give either 'file' or 'page'+'bbox', not both or neither")
        return

    if has_file:
        if not (pack_dir / fig["file"]).exists():
            err(f"{where}: file not found: {fig['file']}")
        return

    if not source_pdf:
        err(f"{where}: uses page/bbox but source.pdf is not set")
        return
    if pdf_pages is None:
        err(f"{where}: source.pdf could not be opened")
        return
    page = fig["page"]
    if not isinstance(page, int) or not 0 <= page < pdf_pages:
        err(f"{where}: page {page} is outside the PDF (0..{pdf_pages - 1})")
    bbox = fig.get("bbox")
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        err(f"{where}: bbox must be [x0, y0, x1, y1]")
    elif bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        err(f"{where}: bbox is empty or inverted: {bbox}")


def _figures_for(q: dict, role: str) -> list[dict]:
    return [f for f in (q.get("figures") or [])
            if f.get("role", "question") == role]


def _page_count(pack_dir: Path, pdf: str) -> int | None:
    path = _resolve(pack_dir, pdf)
    if not path.exists():
        return None
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    try:
        with pymupdf.open(str(path)) as doc:
            return doc.page_count
    except Exception:
        return None


def _resolve(pack_dir: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else (pack_dir / path)


def _materialise(fig: dict, pack_dir: Path, doc, tag: str) -> str | None:
    """Turn a figure reference into a PNG on disk, and return its path."""
    from . import extract

    if fig.get("file"):
        src = _resolve(pack_dir, fig["file"])
        CROPS_DIR.mkdir(parents=True, exist_ok=True)
        dest = CROPS_DIR / f"{tag}-{src.name}"
        if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
            shutil.copyfile(src, dest)
        return str(dest)

    if doc is None:
        return None
    return extract.crop(doc, int(fig["page"]), tuple(fig["bbox"]), tag=tag)


def import_pack(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    design: StudyDesign | None = None,
    dry_run: bool = False,
    progress=print,
) -> PackReport:
    """Validate a pack and, if it is clean, load it into the index."""
    path = Path(path).resolve()
    pack_dir = path.parent
    with path.open(encoding="utf-8") as fh:
        pack = json.load(fh)

    subject_id = pack.get("subject_id")
    if not subject_id:
        report = PackReport(path=str(path))
        report.errors.append("subject_id is required")
        return report

    design = design or load_study_design(subject_id)
    report = validate(pack, design, pack_dir)
    report.path = str(path)

    for warning in report.warnings:
        progress(f"  ! {warning}")
    if not report.ok:
        for error in report.errors[:20]:
            progress(f"  ERROR {error}")
        if len(report.errors) > 20:
            progress(f"  ... and {len(report.errors) - 20} more")
        progress("  " + report.summary())
        return report
    if dry_run:
        progress("  " + report.summary() + "  (dry run — nothing written)")
        return report

    source = pack["source"]
    upsert_source(
        conn, id=source["id"], subject_id=subject_id,
        kind=source.get("kind", "other"),
        title=source.get("title", source["id"]),
        path=str(_resolve(pack_dir, source["pdf"])) if source.get("pdf") else None,
        edition=source.get("edition"),
        page_offset=int(source.get("page_offset", 0)),
        ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    doc = None
    if source.get("pdf"):
        from . import extract
        pdf_path = _resolve(pack_dir, source["pdf"])
        if pdf_path.exists():
            doc = extract.open_pdf(pdf_path)

    try:
        for q in pack["questions"]:
            _import_one(conn, q, pack, source, design, pack_dir, doc, report)
    finally:
        if doc is not None:
            doc.close()

    conn.commit()
    progress("  " + report.summary())
    return report


def _import_one(conn, q, pack, source, design, pack_dir, doc, report) -> None:
    qid = f"{source['id']}-{q['id']}"
    text = _text_of(q)
    answer = _answer_text(q)

    question_fig = next(iter(_figures_for(q, "question")), None)
    answer_fig = next(iter(_figures_for(q, "answer")), None)
    figure_path = _materialise(question_fig, pack_dir, doc, qid) if question_fig else None
    answer_figure = _materialise(answer_fig, pack_dir, doc, f"{qid}-a") if answer_fig else None

    render_mode = q.get("render_mode", "text")
    if render_mode == "crop" and not figure_path:
        render_mode = "text"          # validation passed, but the crop failed
    answer_mode = q.get("answer_mode", "text")
    if answer_mode == "crop" and not answer_figure:
        answer_mode = "text"

    parts = [
        (f"{p['label']}. {p['text']}" if p.get("label") else p.get("text", ""))
        for p in (q.get("parts") or [])
    ]

    insert_question(conn, {
        "id": qid,
        "subject_id": pack["subject_id"],
        "source_id": source["id"],
        "question_type": q.get("question_type") or design.question_types[0].id,
        "body": text,
        "stem": q.get("stem") or None,
        "parts": json.dumps(parts) if parts else None,
        "options": q.get("options") or None,
        "answer": answer,
        "answer_figure": answer_figure,
        "marks": _marks(q),
        "difficulty": q.get("difficulty"),
        "figure_path": figure_path,
        "figure_caption": (question_fig or {}).get("caption"),
        "render_mode": render_mode,
        "answer_mode": answer_mode,
        "provenance": q.get("provenance"),
        "pdf_page": (question_fig or {}).get("page"),
        "printed_page": q.get("printed_page"),
        "citation": _citation(source, q),
        "generated": 0,
        # A pack is curated, so its rows start verified — unlike the extractor's.
        "verified": 1,
        "extra": json.dumps({k: v for k, v in (
            ("title", q.get("title")), ("notes", q.get("notes")),
            ("pack_id", q.get("id")),
        ) if v}),
    }, q.get("kk_ids") or [])

    report.imported += 1
    report.with_figures += 1 if figure_path else 0
    report.with_answers += 1 if answer else 0
    report.cropped += 1 if "crop" in (render_mode, answer_mode) else 0


def _citation(source: dict, q: dict) -> str:
    bits = [source.get("title", source["id"])]
    if q.get("printed_page"):
        bits.append(f"p. {q['printed_page']}")
    if q.get("source_number"):
        bits.append(f"Q{q['source_number']}")
    out = ", ".join(bits)
    if q.get("provenance"):
        out += f" [{q['provenance']}]"
    return out

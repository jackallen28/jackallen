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
import re
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
    drafts: int = 0
    flagged: int = 0
    narrowed: int = 0          # pack tags narrowed to the dot point the text names
    extended: int = 0          # a dot point the pack never used, added on evidence
    covered_before: int = 0    # dot points with at least one question, pack as given
    covered_after: int = 0     # ... after refinement
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        head = f"{Path(self.path).name}: {self.questions} questions"
        if self.errors:
            return f"{head} — NOT IMPORTED, {len(self.errors)} error(s)"
        lines = [
            f"{head}, {self.imported} imported",
            f"    {self.with_figures} with figures, {self.with_answers} with "
            f"answers, {self.cropped} rendered as crops, {self.untagged} untagged",
            f"    {self.drafts} marked draft, {self.flagged} flagged for review",
        ]
        if self.narrowed or self.extended:
            lines.append(
                f"    tags refined: {self.narrowed} narrowed to the dot point "
                f"the text names, {self.extended} extended to a dot point the "
                f"pack left empty; {self.covered_before} -> {self.covered_after} "
                f"dot points covered")
        return "\n".join(lines)


def _text_of(q: dict) -> str:
    """Stem plus parts, which is what gets searched, tagged and, for a question
    without parts, printed."""
    bits = [_split_marks(q.get("stem", ""))[0]]
    for part in q.get("parts") or []:
        label = part.get("label")
        text, _ = _split_marks(part.get("text", ""))
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


# "(3 marks)" on the end of a stem, as the book prints it. The sheet prints the
# marks itself, so a stem that keeps them shows them twice.
_TRAILING_MARKS = re.compile(r"\s*\(\s*(\d+)\s*marks?\s*\)\s*$", re.I)


def _split_marks(text: str | None) -> tuple[str | None, int | None]:
    """Strip a trailing "(N marks)" from text, returning the text and N."""
    if not text:
        return text, None
    m = _TRAILING_MARKS.search(text)
    if not m:
        return text, None
    return text[:m.start()].rstrip(), int(m.group(1))


def _marks(q: dict) -> int | None:
    if q.get("marks") is not None:
        return int(q["marks"])
    parts = q.get("parts") or []
    total = sum(int(p["marks"]) for p in parts if p.get("marks") is not None)
    if total:
        return total
    _, from_stem = _split_marks(q.get("stem"))
    return from_stem


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

    zoom = source.get("figure_zoom")
    if zoom is not None and not (isinstance(zoom, (int, float)) and 0.5 <= zoom <= 8):
        err(f"source.figure_zoom must be a number of pixels per PDF point "
            f"(typically 1–4), got {zoom!r}")
    uses_files = any(f.get("file") for q in (pack.get("questions") or [])
                     for f in (q.get("figures") or []))
    if uses_files and zoom is None and not any(
            f.get("pt_width") for q in (pack.get("questions") or [])
            for f in (q.get("figures") or []) if f.get("file")):
        warn("figures are image files with no source.figure_zoom and no "
             "pt_width; pixels will be taken as points, which overstates crop "
             "width for any render above 72 dpi and can force single-column "
             "sheets needlessly")

    questions = pack.get("questions") or []
    report.questions = len(questions)
    if not questions:
        err("pack contains no questions")

    seen: set[str] = set()
    source_pdf = source.get("pdf")
    pdf_pages = _page_count(pack_dir, source_pdf) if source_pdf else None

    # A missing source PDF is one problem, not one per figure. Reporting it per
    # figure buried the real message under 287 copies of itself.
    uses_bbox = any(f.get("page") is not None
                    for q in questions for f in (q.get("figures") or []))
    if uses_bbox and not source_pdf:
        err("figures use page/bbox but source.pdf is not set")
    elif uses_bbox and pdf_pages is None:
        err(f"source.pdf could not be opened: {source_pdf}\n"
            "         Every page/bbox figure needs it. Check the path is right "
            "on this machine,\n"
            "         or re-export the pack with figures as files.")
    pdf_missing = uses_bbox and (not source_pdf or pdf_pages is None)

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

        status = q.get("status", pack.get("status", "approved"))
        if status not in ("approved", "draft", "needs-review"):
            err(f"{where}: status must be approved, draft or needs-review, "
                f"got {status!r}")

        deps = q.get("depends_on") or []
        if not isinstance(deps, list):
            err(f"{where}: depends_on must be a list of question ids")

        for mode_key in ("render_mode", "answer_mode"):
            mode = q.get(mode_key, "text")
            if mode not in ("text", "crop"):
                err(f"{where}: {mode_key} must be 'text' or 'crop', got {mode!r}")

        for j, fig in enumerate(q.get("figures") or []):
            _validate_figure(fig, f"{where}.figures[{j}]", pack_dir,
                             source_pdf, pdf_pages, err,
                             skip_pdf_checks=pdf_missing)

        if q.get("render_mode") == "crop" and not _figures_for(q, "question"):
            err(f"{where}: render_mode is 'crop' but no question figure was given")
        if q.get("answer_mode") == "crop" and not _figures_for(q, "answer"):
            err(f"{where}: answer_mode is 'crop' but no answer figure was given")

    for i, q in enumerate(questions):
        for dep in (q.get("depends_on") or []):
            if dep not in seen:
                err(f"question[{i}] ({q.get('id')}): depends_on {dep!r}, which "
                    "is not in this pack — a question whose prerequisite is "
                    "missing cannot be put on a sheet")

    return report


def _validate_figure(fig: dict, where: str, pack_dir: Path, source_pdf,
                     pdf_pages: int | None, err,
                     skip_pdf_checks: bool = False) -> None:
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

    if skip_pdf_checks:
        return                        # already reported once, for the whole pack
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
    refine: bool = True,
    progress=print,
) -> PackReport:
    """Validate a pack and, if it is clean, load it into the index.

    With `refine` (the default) each question's dot points are narrowed to
    the ones its own text names — see refine_tags for why a pack needs it.
    """
    path = Path(path).expanduser().resolve()
    pack_dir = path.parent
    report = PackReport(path=str(path))

    def fail(message: str) -> PackReport:
        report.errors.append(message)
        progress(f"  ERROR {message}")
        return report

    # These are the things that go wrong before a pack is even read, and a raw
    # traceback is a poor way to learn that a path has a typo in it.
    if not path.exists():
        return fail(f"no such pack file: {path}")
    if path.is_dir():
        return fail(f"{path} is a directory, not a pack file")
    try:
        with path.open(encoding="utf-8") as fh:
            pack = json.load(fh)
    except json.JSONDecodeError as exc:
        return fail(f"{path.name} is not valid JSON: {exc.msg} at line "
                    f"{exc.lineno}, column {exc.colno}")
    except UnicodeDecodeError as exc:
        return fail(f"{path.name} is not UTF-8 text: {exc}")

    if not isinstance(pack, dict):
        return fail(f"{path.name} should hold a JSON object, found "
                    f"{type(pack).__name__}")

    subject_id = pack.get("subject_id")
    if not subject_id:
        return fail("subject_id is required at the top level of the pack "
                    "(see docs/question-pack-schema.md)")

    if design is None:
        try:
            design = load_study_design(subject_id)
        except FileNotFoundError as exc:
            return fail(str(exc))
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

    refiner = None
    if refine:
        try:
            refiner = TagRefiner(design, pack["questions"])
        except ValueError as exc:      # a stale lexicon; import without it
            progress(f"  ! tags not refined: {exc}")
    if refiner is not None:
        report.covered_before = len(refiner.mapped)

    try:
        for q in pack["questions"]:
            _import_one(conn, q, pack, source, design, pack_dir, doc, report,
                        refiner)
    finally:
        if doc is not None:
            doc.close()

    conn.commit()
    progress("  " + report.summary())
    return report


class TagRefiner:
    """Turns a pack's chapter-level dot points into question-level ones.

    A model indexing a book tags by chapter: every question in "Chapter 6
    Circular motion" gets the same two or three dot points, and dot points no
    chapter is named after get nothing at all. That was the whole Physics
    book — 841 questions, 21 distinct tag sets, 31 of 71 dot points empty.
    A sheet on "proper time" then has nothing to draw on while a sheet on
    "Newton's laws" draws every question in two chapters.

    The pack's tags stay authoritative for *where* a question belongs: its
    chapter fixes the area of study, and nothing here moves a question
    outside it. Within that, the lexicon does two things:

    * narrow — where the question's own text names one of the pack's dot
      points (a spring launcher names energy transformation, not work), keep
      the named one(s) and drop the rest of the chapter's set;
    * extend — where the text strongly names a dot point in the same area
      that the pack never used at all (muons name "examples of special
      relativity", a slip-ring generator names "DC generators"), add it.

    Extension is deliberately limited to dot points the pack left empty:
    letting it add any dot point piled a third of the book onto "Newton's
    three laws", whose vocabulary is every mechanics question's vocabulary.
    Where the lexicon says nothing, the pack's tags are kept as given.
    """

    STRONG = 2.0        # a multi-word trigger, or two triggers, to extend

    def __init__(self, design: StudyDesign, questions: list[dict]):
        from .tag import KeywordTagger

        self.design = design
        self.tagger = KeywordTagger(design)
        self.mapped = {k for q in questions for k in (q.get("kk_ids") or [])}
        self.unmapped = {kk.id for kk in design.all_key_knowledge()
                         if kk.id not in self.mapped}
        self.covered: set[str] = set()

    def refine(self, q: dict, text: str) -> tuple[list[str], str]:
        """The dot points to file this question under, and what changed."""
        orig = list(q.get("kk_ids") or [])
        if not orig:
            return orig, "kept"
        areas = set()
        for k in orig:
            try:
                areas.add(self.design.area_of(k).id)
            except KeyError:
                pass
        cands = {kk.id for a in areas for kk in self.design.area(a).key_knowledge}
        hay = " ".join([q.get("context") or "", text, *(q.get("options") or [])])
        lex = {k: v for k, v in self.tagger.lexicon.score_all(hay).items()
               if k in cands}
        inside = {k: v for k, v in lex.items() if k in orig}
        outside = {k: v for k, v in lex.items()
                   if k not in orig and k in self.unmapped}
        what = []
        if inside:
            best = max(inside.values())
            new = [k for k, v in sorted(inside.items(), key=lambda kv: -kv[1])
                   if v >= best * 0.6][:2]
            if len(new) < len(orig):
                what.append("narrowed")
        else:
            new, best = list(orig), 0.0
        if outside:
            k, v = max(outside.items(), key=lambda kv: kv[1])
            if v >= self.STRONG and v >= best:
                new.append(k)
                what.append("extended")
        self.covered.update(new)
        return new, "+".join(what) or "kept"


def _import_one(conn, q, pack, source, design, pack_dir, doc, report,
                refiner: TagRefiner | None = None) -> None:
    qid = f"{source['id']}-{q['id']}"
    text = _text_of(q)
    answer = _answer_text(q)
    kk_ids = q.get("kk_ids") or []
    if refiner is not None:
        kk_ids, what = refiner.refine(q, text)
        report.narrowed += "narrowed" in what
        report.extended += "extended" in what
        report.covered_after = len(refiner.covered)

    # Every figure, in order. A question routinely needs more than one: a page
    # continuation, the shared scenario printed above it, or an earlier question
    # it depends on. Importing only the first silently truncated 60% of the
    # content in the pilot pack.
    figures: list[dict] = []
    zoom = float(source.get("figure_zoom") or 1.0)
    for n, fig in enumerate(q.get("figures") or []):
        role = fig.get("role", "question")
        tag = f"{qid}-{role[0]}{n}"
        path = _materialise(fig, pack_dir, doc, tag)
        if not path:
            continue
        figures.append({
            "role": role,
            "path": path,
            "pt_width": _pt_width(fig, path, zoom),
            "zoom": zoom if not fig.get("bbox") else None,
            "caption": fig.get("caption"),
        })

    question_figs = [f for f in figures if f["role"] == "question"]
    answer_figs = [f for f in figures if f["role"] == "answer"]
    first_q = question_figs[0] if question_figs else None
    figure_path = first_q["path"] if first_q else None
    figure_pt_width = first_q["pt_width"] if first_q else None
    answer_figure = answer_figs[0]["path"] if answer_figs else None

    render_mode = q.get("render_mode", "text")
    if render_mode == "crop" and not question_figs:
        render_mode = "text"          # validation passed, but the crop failed
    answer_mode = q.get("answer_mode", "text")
    if answer_mode == "crop" and not answer_figs:
        answer_mode = "text"

    parts = []
    for p in (q.get("parts") or []):
        ptext, _ = _split_marks(p.get("text", ""))
        parts.append(f"{p['label']}. {ptext}" if p.get("label") else (ptext or ""))
    stem, _ = _split_marks(q.get("stem"))

    insert_question(conn, {
        "id": qid,
        "subject_id": pack["subject_id"],
        "source_id": source["id"],
        "question_type": q.get("question_type") or design.question_types[0].id,
        "body": text,
        "stem": stem or None,
        "parts": json.dumps(parts) if parts else None,
        "options": q.get("options") or None,
        "answer": answer,
        "answer_figure": answer_figure,
        "marks": _marks(q),
        "difficulty": q.get("difficulty"),
        "figure_path": figure_path,
        "figure_pt_width": figure_pt_width,
        "figure_caption": (first_q or {}).get("caption"),
        "figures": json.dumps(figures) if figures else None,
        "render_mode": render_mode,
        "answer_mode": answer_mode,
        "provenance": q.get("provenance"),
        "pdf_page": next(
            (f.get("page") for f in (q.get("figures") or [])
             if f.get("role", "question") == "question" and f.get("page") is not None),
            None),
        "printed_page": q.get("printed_page"),
        "citation": _citation(source, q),
        "context": q.get("context") or None,
        # Namespaced like the question ids themselves, or the lookup finds
        # nothing and the prerequisite is silently never pulled in.
        "depends_on": json.dumps(
            [f"{source['id']}-{d}" for d in q["depends_on"]]
        ) if q.get("depends_on") else None,
        "review": json.dumps(q["review"]) if q.get("review") else None,
        "generated": 0,
        # A pack is curated, but curated is not the same as checked. A pack that
        # says its rows are drafts — or that flags a row for review — is taken
        # at its word; marking unreviewed curriculum tags "verified" would put a
        # confidence on the sheet that nobody has earned.
        "verified": 0 if (
            q.get("status", pack.get("status", "approved")) != "approved"
            or q.get("review")
        ) else 1,
        "extra": json.dumps({k: v for k, v in (
            ("title", q.get("title")), ("notes", q.get("notes")),
            ("pack_id", q.get("id")),
        ) if v}),
    }, kk_ids)

    report.imported += 1
    report.drafts += 1 if q.get("status", "approved") != "approved" else 0
    report.flagged += 1 if q.get("review") else 0
    report.with_figures += 1 if figure_path else 0
    report.with_answers += 1 if answer else 0
    report.cropped += 1 if "crop" in (render_mode, answer_mode) else 0


def _pt_width(fig: dict | None, path: str | None, zoom: float = 1.0) -> float | None:
    """The crop's width in PDF points, which decides the sheet's layout.

    A bbox says so directly. An explicit `pt_width` on the figure is next best.
    Otherwise a supplied image file only has pixels, and PNGs from a renderer
    carry no DPI, so the pack's `source.figure_zoom` (pixels per point) converts
    them. Without any of those, one pixel is taken as one point — which for a
    3x render overstates the width threefold and forces the sheet into a
    single column it did not need.
    """
    if not fig or not path:
        return None
    bbox = fig.get("bbox")
    if bbox:
        return float(bbox[2]) - float(bbox[0])
    if fig.get("pt_width"):
        return float(fig["pt_width"])
    from ..render.layout import image_px_size

    size = image_px_size(path)
    if size is None:
        return None
    return float(size[0]) / max(float(zoom or 1.0), 1e-6)


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

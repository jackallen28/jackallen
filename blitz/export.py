"""Write everything indexed for a subject out as a folder people can look at.

The SQLite index is what the sheet generator reads, but nobody wants to open
SQLite to see what came out of their books. This writes the same content as
plain files: one JSON of questions in the question-pack format (so it can be
re-imported, edited, or handed to a model), one of teaching passages, the
coverage table, a list of sources, and copies of every figure crop. Then a
zip of the lot for the browser to hand over.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import OUT_DIR
from .corpus.sample import fingerprint
from .studydesign import StudyDesign, load_study_design


@dataclass
class ExportReport:
    folder: Path
    zip_path: Path | None = None
    questions: int = 0
    passages: int = 0
    figures: int = 0
    sources: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"{self.folder.name}: {self.questions} questions, {self.passages} "
                f"teaching sections, {self.figures} figures, from "
                f"{len(self.sources)} source(s)")


def coverage_text(conn: sqlite3.Connection, design: StudyDesign) -> str:
    """The coverage table as text, one line per dot point, per source."""
    from .db import coverage_by_source, passage_coverage
    from .ingest.pipeline import coverage_report

    rows = coverage_report(conn, design)
    content = passage_coverage(conn, design.subject_id)
    by_source = coverage_by_source(conn, design.subject_id)
    sources = sorted({src for _, src in by_source})
    out = [f"{design.subject_name} — questions held per dot point",
           f"study design fingerprint {fingerprint(design)}", ""]
    head = f"{'Qs':>4} {'text':>5}" + "".join(f"{s[-16:]:>17}" for s in sources)
    out.append(head + "   dot point")
    current = None
    for row in rows:
        if row["aos"] != current:
            current = row["aos"]
            out += ["", current]
        cols = "".join(f"{by_source.get((row['kk_id'], s), 0):>17}" for s in sources)
        out.append(f"  {row['count']:4} {content.get(row['kk_id'], 0):5}{cols}   "
                   f"{row['label']}  [{row['kk_id']}]")
    empty = sum(1 for r in rows if r["count"] == 0)
    out += ["", f"{empty} of {len(rows)} dot points have no question yet."]
    return "\n".join(out) + "\n"


def _copy_figure(path: str | None, figures_dir: Path, copied: dict[str, str]) -> str | None:
    if not path:
        return None
    if path in copied:
        return copied[path]
    src = Path(path)
    if not src.exists():
        return None
    figures_dir.mkdir(parents=True, exist_ok=True)
    dest = figures_dir / src.name
    if not dest.exists():
        shutil.copyfile(src, dest)
    copied[path] = f"figures/{src.name}"
    return copied[path]


def export_subject(conn: sqlite3.Connection, subject_id: str,
                   out_dir: Path | None = None, make_zip: bool = True,
                   design: StudyDesign | None = None) -> ExportReport:
    """Write the subject's index to a folder (and a zip of it)."""
    design = design or load_study_design(subject_id)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    folder = Path(out_dir or OUT_DIR) / f"index-{subject_id}-{stamp}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    figures_dir = folder / "figures"
    copied: dict[str, str] = {}
    report = ExportReport(folder=folder)

    sources = [dict(r) for r in conn.execute(
        "SELECT id, kind, title, path, edition, page_offset, ingested_at "
        "FROM source WHERE subject_id = ? ORDER BY id", (subject_id,))]
    report.sources = [s["id"] for s in sources]

    questions = []
    for row in conn.execute(
            "SELECT * FROM question WHERE subject_id = ? ORDER BY source_id, id",
            (subject_id,)):
        q = dict(row)
        kk = [r["kk_id"] for r in conn.execute(
            "SELECT kk_id FROM question_kk WHERE question_id = ? "
            "ORDER BY primary_kk DESC, confidence DESC", (q["id"],))]
        figs = []
        for spec in json.loads(q.get("figures") or "[]"):
            rel = _copy_figure(spec.get("path"), figures_dir, copied)
            if rel:
                figs.append({"role": spec.get("role", "question"), "file": rel,
                             "pt_width": spec.get("pt_width"),
                             "caption": spec.get("caption")})
        if not figs:
            for role, key in (("question", "figure_path"), ("answer", "answer_figure")):
                rel = _copy_figure(q.get(key), figures_dir, copied)
                if rel:
                    figs.append({"role": role, "file": rel,
                                 "pt_width": q.get("figure_pt_width") if role == "question" else None})
        questions.append({
            "id": q["id"],
            "source_id": q["source_id"],
            "kk_ids": kk,
            "question_type": q["question_type"],
            "marks": q.get("marks"),
            "difficulty": q.get("difficulty"),
            "stem": q.get("stem") or (q["body"] if not q.get("parts") else None),
            "parts": json.loads(q["parts"]) if q.get("parts") else [],
            "options": json.loads(q["options"]) if q.get("options") else None,
            "answer": q.get("answer"),
            "context": q.get("context"),
            "citation": q.get("citation"),
            "render_mode": q.get("render_mode") or "text",
            "answer_mode": q.get("answer_mode") or "text",
            "figures": figs,
            "verified": bool(q.get("verified")),
            "generated": bool(q.get("generated")),
        })
    report.questions = len(questions)

    passages = []
    for row in conn.execute(
            "SELECT * FROM passage WHERE subject_id = ? ORDER BY source_id, page_start",
            (subject_id,)):
        p = dict(row)
        kk = [r["kk_id"] for r in conn.execute(
            "SELECT kk_id FROM passage_kk WHERE passage_id = ?", (p["id"],))]
        passages.append({
            "id": p["id"], "source_id": p["source_id"], "kk_ids": kk,
            "title": p["title"], "section": p.get("section"), "level": p["level"],
            "page_start": p["page_start"], "page_end": p["page_end"],
            "printed_page": p.get("printed_page"), "text": p["body"],
        })
    report.passages = len(passages)
    report.figures = len(copied)

    dot_points = [
        {"id": kk.id, "area": area.display, "text": kk.text}
        for area in design.all_areas() for kk in area.key_knowledge
    ]
    meta = {
        "subject_id": subject_id,
        "subject_name": design.subject_name,
        "study_design_fingerprint": fingerprint(design),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
        "counts": {"questions": len(questions), "passages": len(passages),
                   "figures": len(copied)},
    }
    (folder / "index.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "questions.json").write_text(
        json.dumps({"subject_id": subject_id,
                    "study_design_fingerprint": meta["study_design_fingerprint"],
                    "dot_points": dot_points, "questions": questions},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "passages.json").write_text(
        json.dumps({"subject_id": subject_id, "passages": passages},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "coverage.txt").write_text(coverage_text(conn, design), encoding="utf-8")
    (folder / "README.txt").write_text(
        f"{design.subject_name} — index exported {meta['exported_at']}\n\n"
        f"questions.json   every question, in the question-pack format (re-importable)\n"
        f"passages.json    teaching sections from textbooks, tagged to dot points\n"
        f"coverage.txt     questions held per dot point, one column per source\n"
        f"figures/         every diagram and page crop the questions refer to\n"
        f"index.json       what was indexed, from where, and when\n\n"
        f"{report.summary()}\n", encoding="utf-8")

    if make_zip:
        base = str(folder)
        report.zip_path = Path(shutil.make_archive(base, "zip", root_dir=folder.parent,
                                                   base_dir=folder.name))
    return report

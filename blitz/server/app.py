"""Local web UI.

Runs on 127.0.0.1 only by default. Nothing is uploaded anywhere: your PDFs, the
index built from them and the sheets it produces all stay on this machine.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import db
from ..config import CROPS_DIR, OUT_DIR, STUDENTS_DIR, ensure_dirs
from ..models import SheetSpec
from ..picker import build_plan
from ..render import render_sheet
from ..studydesign import list_subjects, load_study_design
from .auth import auth_middleware, password

STATIC = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    yield


app = FastAPI(title="VCE Blitz", docs_url=None, redoc_url=None, lifespan=lifespan)

# Paths that work before the folder has been set up: the setup page itself,
# what it calls, the health probe, and the static files any page needs.
SETUP_PATHS = {"/setup", "/setup.js", "/api/status", "/api/setup", "/healthz"}
ASSET_SUFFIXES = (".css", ".js", ".png", ".svg", ".ico", ".woff", ".woff2")


@app.middleware("http")
async def setup_gate(request, call_next):
    """Until the Blitz folder is set up, only the setup page is reachable.

    A browser is redirected there; an API call is refused with a clear
    reason rather than acting on an index that does not exist yet.
    """
    from ..setup import is_set_up

    path = request.url.path
    if is_set_up() or path in SETUP_PATHS or path.endswith(ASSET_SUFFIXES):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse(
            {"detail": "This Blitz folder has not been set up yet. Open / to "
                       "restore a backup or start from scratch."},
            status_code=409)
    return RedirectResponse("/setup", status_code=307)


app.middleware("http")(auth_middleware)


@app.get("/healthz")
def healthz():
    """Liveness probe. Served without a password so the platform can reach it."""
    subjects = list_subjects()
    return {
        "ok": True,
        "subjects": [s.subject_id for s in subjects],
        "protected": bool(password()),
    }


class SheetRequest(BaseModel):
    subject_id: str
    kk_ids: list[str] = Field(default_factory=list)
    question_type_ids: list[str] = Field(default_factory=list)
    notes: str = ""
    title: str = ""
    difficulty: str = "mixed"
    include_solutions: bool = True
    prefer_figures: bool = True
    allow_generated: bool = True
    seed: int | None = None
    # Who it is for. An existing id, or a new name to create. With a student
    # named, questions they have already been given are skipped unless
    # allow_repeats is set.
    student_id: str | None = None
    student_name: str | None = None
    allow_repeats: bool = False

    def to_spec(self) -> SheetSpec:
        fields = self.model_dump(exclude={"student_id", "student_name", "allow_repeats"})
        return SheetSpec(**fields)


def _resolve_student(conn, req: SheetRequest) -> dict | None:
    """The student row for a request, creating one from a new name."""
    if req.student_name and req.student_name.strip():
        return db.get_or_create_student(conn, req.student_name)
    if req.student_id:
        row = conn.execute("SELECT * FROM student WHERE id = ?", (req.student_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "no such student")
        return dict(row)
    return None


def _apply_history(conn, spec: SheetSpec, student: dict | None, allow_repeats: bool
                   ) -> list[str]:
    """Exclude what the student has had; return the serials that were skipped
    among questions that would otherwise have been candidates."""
    if student is None or allow_repeats:
        return []
    had = db.student_history(conn, student["id"])
    if not had:
        return []
    spec.exclude_question_ids = sorted(set(spec.exclude_question_ids) | set(had))
    if not spec.kk_ids:
        return []
    marks = ", ".join("?" for _ in had)
    kk_marks = ", ".join("?" for _ in spec.kk_ids)
    rows = conn.execute(
        f"SELECT DISTINCT q.serial FROM question q JOIN question_kk kk ON kk.question_id = q.id "
        f"WHERE q.id IN ({marks}) AND kk.kk_id IN ({kk_marks}) ORDER BY q.serial",
        [*had, *spec.kk_ids]).fetchall()
    return [r["serial"] for r in rows if r["serial"]]


# --- First run ----------------------------------------------------------------

@app.get("/setup")
def setup_page():
    """Shown until the folder is set up; afterwards it redirects home."""
    from ..setup import is_set_up

    if is_set_up():
        return RedirectResponse("/", status_code=307)
    return FileResponse(STATIC / "setup.html")


@app.get("/api/status")
def api_status():
    """What this Blitz folder holds, for the setup page."""
    from ..setup import status

    return status()


@app.post("/api/setup")
async def api_setup(
    mode: str = Form(...),
    subjects: list[str] = Form(default=[]),
    samples: str = Form(""),
    erase: str = Form(""),
    replace: str = Form(""),
    backup: UploadFile | None = File(None),
    designs: list[UploadFile] = File(default=[]),
    design_names: list[str] = Form(default=[]),
):
    """Set the folder up one of three ways: restore, scratch, or keep."""
    from .. import setup as setup_mod
    from ..config import ROOT

    if setup_mod.is_set_up():
        raise HTTPException(409, "this folder is already set up")
    try:
        if mode == "restore":
            if backup is None or not backup.filename:
                raise HTTPException(400, "choose the backup zip to restore")
            staged = ROOT / "backups" / f"restoring-{backup.filename}"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(await backup.read())
            try:
                result = setup_mod.setup_restore(staged, replace=bool(replace),
                                                 name=Path(backup.filename).name)
            finally:
                staged.unlink(missing_ok=True)
        elif mode == "scratch":
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                uploaded = []
                for i, upload in enumerate(designs or []):
                    if not upload.filename:
                        continue
                    staged = Path(tmp) / Path(upload.filename).name
                    staged.write_bytes(await upload.read())
                    # An empty name means "guess it from the filename", which
                    # add_study_design does; passing the filename through as
                    # the name would make the subject "2024ChemistrySD".
                    name = design_names[i] if i < len(design_names) else ""
                    uploaded.append((name, staged))
                result = setup_mod.setup_scratch(
                    [s for s in subjects if s], samples=bool(samples),
                    erase=bool(erase), designs=uploaded)
        elif mode == "adopt":
            result = setup_mod.setup_adopt()
        else:
            raise HTTPException(400, f"unknown setup mode {mode!r}")
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return result


@app.get("/api/root")
def api_root():
    from ..config import ROOT

    return {"root": str(ROOT)}


# --- Backup: one zip with everything worth keeping ----------------------------

class BackupIn(BaseModel):
    include_sources: bool = False


@app.post("/api/backup")
def api_backup(body: BackupIn):
    from .. import backup
    from ..config import ROOT

    report = backup.create_backup(root=ROOT, include_sources=body.include_sources)
    return {"name": report.path.name, "path": str(report.path),
            "files": report.files, "bytes": report.bytes,
            "counts": report.counts, "summary": report.summary()}


@app.get("/backups/{name}")
def get_backup(name: str):
    from ..config import ROOT

    folder = (ROOT / "backups").resolve()
    path = (folder / name).resolve()
    if not re.fullmatch(r"blitz-backup-[\d-]+\.zip", name) or not path.is_file() \
            or folder not in path.parents:
        raise HTTPException(404, "no such backup")
    return FileResponse(path, media_type="application/zip", filename=name)


@app.get("/api/subjects")
def api_subjects():
    """The full study design tree plus how many questions back each dot point."""
    out = []
    with db.session() as conn:
        for design in list_subjects():
            held = db.coverage(conn, design.subject_id)
            by_type = db.coverage_by_type(conn, design.subject_id)
            out.append({
                "id": design.subject_id,
                "name": design.subject_name,
                "accreditation": design.accreditation,
                "verified": design.fully_verified,
                "source": design.source,
                "question_types": [
                    {
                        "id": qt.id,
                        "label": qt.label,
                        "description": qt.description,
                        "available": sum(
                            n for (kk, t), n in by_type.items() if t == qt.id
                        ),
                    }
                    for qt in design.question_types
                ],
                "units": [
                    {
                        "id": u.id,
                        "number": u.number,
                        "title": u.title,
                        "areas": [
                            {
                                "id": a.id,
                                "number": a.number,
                                "title": a.title,
                                "outcome": a.outcome,
                                "key_knowledge": [
                                    {
                                        "id": kk.id,
                                        "text": kk.text,
                                        "label": kk.display,
                                        "verified": kk.verified,
                                        "available": held.get(kk.id, 0),
                                    }
                                    for kk in a.key_knowledge
                                ],
                            }
                            for a in u.areas_of_study
                        ],
                    }
                    for u in design.units
                ],
            })
    return {"subjects": out}


@app.post("/api/preview")
def api_preview(req: SheetRequest):
    """What would go on the sheet, without rendering it."""
    design = _design_or_404(req.subject_id)
    with db.session() as conn:
        student = _resolve_student(conn, req)
        spec = req.to_spec()
        skipped = _apply_history(conn, spec, student, req.allow_repeats)
        plan = build_plan(conn, spec, design)
    if skipped:
        plan.warnings.append(
            f"Skipped {len(skipped)} question(s) {student['name']} has already had "
            f"on these dot points ({', '.join(skipped[:8])}{'…' if len(skipped) > 8 else ''}). "
            "Tick 'allow repeats' to let them back in.")
    return {
        "student": student,
        "skipped": skipped,
        "questions": [
            {
                "id": q.id,
                "serial": q.serial,
                "type": q.question_type,
                "marks": q.marks,
                "generated": q.generated,
                "has_figure": q.has_figure,
                "citation": q.citation,
                "preview": q.body[:150],
            }
            for q in plan.questions
        ],
        "count": len(plan.questions),
        "total_marks": plan.total_marks,
        "estimated_pages": plan.estimated_pages,
        "uncovered": [
            {"id": kk, "label": _label(design, kk)} for kk in plan.uncovered_kk_ids
        ],
        "warnings": plan.warnings,
    }


@app.post("/api/generate")
def api_generate(req: SheetRequest):
    design = _design_or_404(req.subject_id)
    with db.session() as conn:
        student = _resolve_student(conn, req)
        spec = req.to_spec()
        skipped = _apply_history(conn, spec, student, req.allow_repeats)
        plan = build_plan(conn, spec, design)
        if not plan.questions:
            raise HTTPException(
                422,
                "Nothing to put on the sheet. "
                + (plan.warnings[0] if plan.warnings else "Select some dot points."),
            )
        stem = f"blitz-{req.subject_id}-{uuid.uuid4().hex[:8]}"
        if student:
            from ..students import safe_name

            who = safe_name(student["name"]).replace(" ", "-").lower()
            stem = f"blitz-{who}-{req.subject_id}-{uuid.uuid4().hex[:6]}"
        name = f"{stem}.pdf"
        result = render_sheet(plan, OUT_DIR / name, design)
        db.record_sheet(
            conn, sheet_id=stem, subject_id=req.subject_id,
            title=req.title or f"{design.subject_name} Blitz",
            spec_json=spec.to_json(), pdf_path=str(OUT_DIR / name),
            question_ids=[q.id for q in plan.questions],
            student_id=student["id"] if student else None)
        conn.commit()
        if student:
            from ..students import write_workbooks

            write_workbooks(conn)
    if skipped:
        plan.warnings.append(
            f"Skipped {len(skipped)} question(s) {student['name']} has already had "
            f"({', '.join(skipped[:8])}{'…' if len(skipped) > 8 else ''}).")

    return {
        **result,
        "url": f"/sheets/{name}",
        "filename": name,
        "student": student,
        "skipped": skipped,
        "serials": [q.serial for q in plan.questions],
        "warnings": plan.warnings,
        "uncovered": [
            {"id": kk, "label": _label(design, kk)} for kk in plan.uncovered_kk_ids
        ],
    }


@app.api_route("/sheets/{name}", methods=["GET", "HEAD"])
def get_sheet(name: str, download: bool = False):
    """Serve a generated sheet.

    Inline by default, so the page can show the sheet in a viewer as soon as it
    is generated — `attachment` made the browser download it and left the
    preview blank. `?download=1` is the save button.

    HEAD is registered alongside GET because some viewers probe with it first,
    and without it the request fell through to the static mount and 404'd.
    """
    # Resolve and confirm the file really sits inside OUT_DIR before serving it.
    path = (OUT_DIR / name).resolve()
    if not path.is_file() or OUT_DIR.resolve() not in path.parents:
        raise HTTPException(404, "no such sheet")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{name}"'},
    )


def _design_or_404(subject_id: str):
    try:
        return load_study_design(subject_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


def _label(design, kk_id: str) -> str:
    try:
        return design.key_knowledge(kk_id).display
    except KeyError:
        return kk_id


# --- Index materials: upload, run, hand back a folder -------------------------

@app.get("/")
def home_page():
    """Three doors: make a Blitz, index materials, students."""
    return FileResponse(STATIC / "home.html")


@app.get("/blitz")
def blitz_page():
    return FileResponse(STATIC / "index.html")


@app.get("/students")
def students_page():
    return FileResponse(STATIC / "students.html")


@app.get("/questions")
def questions_page():
    return FileResponse(STATIC / "questions.html")


# --- Students ----------------------------------------------------------------

class StudentIn(BaseModel):
    name: str


@app.get("/api/students")
def api_students():
    with db.session() as conn:
        rows = conn.execute(
            "SELECT st.id, st.name, COUNT(DISTINCT s.id) AS sheets, "
            "COUNT(sq.question_id) AS questions, MAX(s.created_at) AS last "
            "FROM student st LEFT JOIN sheet s ON s.student_id = st.id "
            "LEFT JOIN sheet_question sq ON sq.sheet_id = s.id "
            "GROUP BY st.id ORDER BY st.name").fetchall()
    return {"folder": str(STUDENTS_DIR), "students": [dict(r) for r in rows]}


@app.post("/api/students")
def api_student_create(body: StudentIn):
    from ..students import write_workbooks

    with db.session() as conn:
        try:
            student = db.get_or_create_student(conn, body.name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        conn.commit()
        write_workbooks(conn)
    return student


@app.get("/api/students/{student_id}")
def api_student(student_id: str):
    from ..students import safe_name

    with db.session() as conn:
        st = conn.execute("SELECT * FROM student WHERE id = ?", (student_id,)).fetchone()
        if st is None:
            raise HTTPException(404, "no such student")
        sheets = []
        for sh in conn.execute(
                "SELECT * FROM sheet WHERE student_id = ? ORDER BY created_at DESC",
                (student_id,)):
            design = _design_or_404(sh["subject_id"])
            qs = []
            for r in conn.execute(
                    "SELECT q.id, q.serial, q.citation FROM sheet_question sq "
                    "JOIN question q ON q.id = sq.question_id "
                    "WHERE sq.sheet_id = ? ORDER BY sq.position", (sh["id"],)):
                kk = [x["kk_id"] for x in conn.execute(
                    "SELECT kk_id FROM question_kk WHERE question_id = ? "
                    "ORDER BY primary_kk DESC", (r["id"],))]
                qs.append({"id": r["id"], "serial": r["serial"],
                           "citation": r["citation"],
                           "kk": [_label(design, k) for k in kk]})
            pdf = Path(sh["pdf_path"]).name if sh["pdf_path"] else None
            sheets.append({"id": sh["id"], "title": sh["title"],
                           "subject_id": sh["subject_id"],
                           "created_at": sh["created_at"],
                           "url": f"/sheets/{pdf}" if pdf and (OUT_DIR / pdf).exists() else None,
                           "questions": qs})
    return {**dict(st), "workbook": f"{safe_name(st['name'])}.xlsx", "sheets": sheets}


@app.get("/students/files/{name}")
def get_student_file(name: str):
    path = (STUDENTS_DIR / name).resolve()
    if path.suffix != ".xlsx" or not path.is_file() or STUDENTS_DIR.resolve() not in path.parents:
        raise HTTPException(404, "no such workbook")
    return FileResponse(
        path, filename=name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- Questions: look up, inspect, flag ----------------------------------------

_SERIAL = re.compile(r"^[A-Za-z]{2,4}-\d{1,6}$")


def _fts_query(text: str) -> str:
    """A safe FTS5 query: every word quoted, all required, prefix on the last."""
    words = [w.replace('"', "") for w in text.split() if w.strip('"')]
    if not words:
        return ""
    quoted = [f'"{w}"' for w in words]
    quoted[-1] = quoted[-1] + "*"
    return " ".join(quoted)


def _crop_url(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    return f"/crops/{p.name}" if p.exists() else None


@app.get("/api/questions")
def api_questions(subject: str, q: str = "", flagged: str = "", limit: int = 40):
    """Search by serial (exact) or words (full text), optionally flagged only."""
    q = q.strip()
    with db.session() as conn:
        design = _design_or_404(subject)
        params: list = [subject]
        if _SERIAL.match(q):
            where = "q.subject_id = ? AND upper(q.serial) = upper(?)"
            params.append(q)
        elif q:
            where = ("q.subject_id = ? AND q.rowid IN (SELECT rowid FROM question_fts "
                     "WHERE question_fts MATCH ?)")
            params.append(_fts_query(q))
        else:
            where = "q.subject_id = ?"
        if flagged:
            where += " AND q.flag IS NOT NULL"
        total = conn.execute(f"SELECT COUNT(*) AS n FROM question q WHERE {where}",
                             params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT q.* FROM question q WHERE {where} ORDER BY q.flag IS NULL, q.serial LIMIT ?",
            [*params, max(1, min(limit, 200))]).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            kk = [x["kk_id"] for x in conn.execute(
                "SELECT kk_id FROM question_kk WHERE question_id = ? ORDER BY primary_kk DESC",
                (d["id"],))]
            given = conn.execute(
                "SELECT COUNT(*) AS n FROM sheet_question sq JOIN sheet s ON s.id = sq.sheet_id "
                "WHERE sq.question_id = ? AND s.student_id IS NOT NULL", (d["id"],)).fetchone()["n"]
            figs = []
            for spec in json.loads(d.get("figures") or "[]"):
                url = _crop_url(spec.get("path"))
                if url:
                    figs.append({"role": spec.get("role", "question"), "url": url})
            if not figs:
                for role, key in (("question", "figure_path"), ("answer", "answer_figure")):
                    url = _crop_url(d.get(key))
                    if url:
                        figs.append({"role": role, "url": url})
            try:
                type_label = design.question_type(d["question_type"]).label
            except KeyError:
                type_label = d["question_type"]
            out.append({
                "id": d["id"], "serial": d.get("serial"), "citation": d.get("citation"),
                "source_id": d["source_id"], "type_label": type_label,
                "marks": d.get("marks"), "kk": [_label(design, k) for k in kk],
                "context": d.get("context"), "body": d["body"],
                "options": json.loads(d["options"]) if d.get("options") else None,
                "answer": d.get("answer"), "render_mode": d.get("render_mode") or "text",
                "answer_mode": d.get("answer_mode") or "text", "figures": figs,
                "flag": d.get("flag"), "flag_note": d.get("flag_note"),
                "flagged_at": d.get("flagged_at"), "given": given,
            })
    return {"total": total, "questions": out}


class FlagIn(BaseModel):
    flag: str | None = None
    note: str = ""


@app.post("/api/questions/{question_id}/flag")
def api_flag(question_id: str, body: FlagIn):
    with db.session() as conn:
        if conn.execute("SELECT 1 FROM question WHERE id = ?", (question_id,)).fetchone() is None:
            raise HTTPException(404, "no such question")
        try:
            db.set_flag(conn, question_id, body.flag or None, body.note.strip() or None)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        conn.commit()
        row = conn.execute("SELECT id, serial, flag, flag_note, flagged_at FROM question "
                           "WHERE id = ?", (question_id,)).fetchone()
    return dict(row)


@app.get("/crops/{name}")
def get_crop(name: str):
    path = (CROPS_DIR / name).resolve()
    if not path.is_file() or CROPS_DIR.resolve() not in path.parents:
        raise HTTPException(404, "no such figure")
    return FileResponse(path)


@app.get("/index")
def indexer_page():
    """The plain page for indexing files: pick a subject, drop files, press Index."""
    return FileResponse(STATIC / "indexer.html")


@app.post("/api/index")
async def api_index_start(
    subject_id: str | None = Form(None),
    subject_name: str | None = Form(None),
    study_design: UploadFile | None = File(None),
    files: list[UploadFile] = File(default=[]),
):
    """Stage the upload under sources/<subject>/uploads/ and start the job."""
    from . import indexjob

    if subject_name and not subject_id:
        subject_id = indexjob.slug(subject_name)
        if study_design is None:
            raise HTTPException(400, "a new subject needs its VCAA study design")
    if not subject_id:
        raise HTTPException(400, "pick a subject or name a new one")
    if not files and study_design is None:
        raise HTTPException(400, "nothing was uploaded")
    known = {d.subject_id for d in list_subjects()}
    if subject_id not in known and study_design is None:
        raise HTTPException(400, f"no subject '{subject_id}'; upload its study design")

    uploads = []
    for f in files:
        if f.filename:
            uploads.append((f.filename, await f.read()))
    folder = indexjob.stage_uploads(subject_id, uploads)
    design_path = None
    if study_design is not None and study_design.filename:
        design_path = folder / ("study-design" + Path(study_design.filename).suffix.lower())
        design_path.write_bytes(await study_design.read())
    job = indexjob.start(subject_id, folder, study_design=design_path,
                         subject_name=subject_name)
    return {"id": job.id, "subject_id": subject_id, "folder": str(folder)}


@app.get("/api/index/{job_id}")
def api_index_status(job_id: str):
    from . import indexjob

    job = indexjob.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    return job.snapshot()


@app.get("/exports/{name}")
def get_export(name: str):
    """A zip of an export folder, by name."""
    from . import indexjob

    path = indexjob.export_path(name)
    if path is None:
        raise HTTPException(404, "no such export")
    return FileResponse(path, media_type="application/zip", filename=name)


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")

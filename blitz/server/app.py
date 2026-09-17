"""Local web UI.

Runs on 127.0.0.1 only by default. Nothing is uploaded anywhere: your PDFs, the
index built from them and the sheets it produces all stay on this machine.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import db
from ..config import OUT_DIR, ensure_dirs
from ..models import SheetSpec
from ..picker import build_plan
from ..render import render_sheet
from ..studydesign import list_subjects, load_study_design

STATIC = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    yield


app = FastAPI(title="VCE Blitz", docs_url=None, redoc_url=None, lifespan=lifespan)


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

    def to_spec(self) -> SheetSpec:
        return SheetSpec(**self.model_dump())


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
        plan = build_plan(conn, req.to_spec(), design)
    return {
        "questions": [
            {
                "id": q.id,
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
    spec = req.to_spec()
    with db.session() as conn:
        plan = build_plan(conn, spec, design)
        if not plan.questions:
            raise HTTPException(
                422,
                "Nothing to put on the sheet. "
                + (plan.warnings[0] if plan.warnings else "Select some dot points."),
            )
        name = f"blitz-{req.subject_id}-{uuid.uuid4().hex[:8]}.pdf"
        result = render_sheet(plan, OUT_DIR / name, design)

    return {
        **result,
        "url": f"/sheets/{name}",
        "filename": name,
        "warnings": plan.warnings,
        "uncovered": [
            {"id": kk, "label": _label(design, kk)} for kk in plan.uncovered_kk_ids
        ],
    }


@app.get("/sheets/{name}")
def get_sheet(name: str):
    # Resolve and confirm the file really sits inside OUT_DIR before serving it.
    path = (OUT_DIR / name).resolve()
    if not path.is_file() or OUT_DIR.resolve() not in path.parents:
        raise HTTPException(404, "no such sheet")
    return FileResponse(path, media_type="application/pdf", filename=name)


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


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")

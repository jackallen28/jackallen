import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "..", "projects")
ALLOWED_EXTENSIONS = {".ino", ".h", ".cpp", ".c"}


def _safe_path(project: str, filename: str) -> str:
    base = os.path.realpath(os.path.join(PROJECTS_DIR, project))
    full = os.path.realpath(os.path.join(base, filename))
    if not full.startswith(base):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if os.path.splitext(filename)[1] not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    return full


@router.get("/api/files")
async def list_files(project: str = "default"):
    project_dir = os.path.join(PROJECTS_DIR, project)
    if not os.path.isdir(project_dir):
        return {"files": []}
    files = [
        f for f in os.listdir(project_dir)
        if os.path.splitext(f)[1] in ALLOWED_EXTENSIONS
    ]
    return {"project": project, "files": sorted(files)}


@router.get("/api/files/{filename}")
async def read_file(filename: str, project: str = "default"):
    path = _safe_path(project, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path) as f:
        return {"filename": filename, "content": f.read()}


class SaveRequest(BaseModel):
    filename: str
    content: str
    project: str = "default"


@router.post("/api/files")
async def save_file(body: SaveRequest):
    project_dir = os.path.join(PROJECTS_DIR, body.project)
    os.makedirs(project_dir, exist_ok=True)
    path = _safe_path(body.project, body.filename)
    with open(path, "w") as f:
        f.write(body.content)
    return {"saved": body.filename}


@router.delete("/api/files/{filename}")
async def delete_file(filename: str, project: str = "default"):
    path = _safe_path(project, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(path)
    return {"deleted": filename}

# TODO: GET /api/files  — return project file tree
# TODO: POST /api/files — create or update a file in the active project
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/files")
async def list_files():
    return {"status": "stub"}

@router.post("/api/files")
async def save_file():
    return {"status": "stub"}

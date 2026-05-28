# TODO: /api/compile — invoke arduino-cli compile with the submitted sketch
# TODO: /api/upload  — invoke arduino-cli upload to the selected serial port
from fastapi import APIRouter

router = APIRouter()

@router.post("/api/compile")
async def compile():
    return {"status": "stub"}

@router.post("/api/upload")
async def upload():
    return {"status": "stub"}

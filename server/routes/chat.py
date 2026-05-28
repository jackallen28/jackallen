# TODO: call Anthropic API with message history; stream tokens back to client
from fastapi import APIRouter

router = APIRouter()

@router.post("/api/chat")
async def chat():
    return {"status": "stub"}

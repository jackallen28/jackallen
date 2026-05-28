import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic

router = APIRouter()

def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=key)

SYSTEM_PROMPT = (
    "You are an expert Arduino and ESP32 embedded systems assistant embedded in the "
    "Allentronics VibeDuino IDE. Help the user write, debug, and understand Arduino/C++ "
    "sketches. When providing code, use Arduino-style C++ and keep explanations concise. "
    "If asked about wiring, describe pin connections clearly."
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]

@router.post("/api/chat")
async def chat(body: ChatRequest):
    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[m.model_dump() for m in body.messages],
    )

    return {"reply": response.content[0].text}

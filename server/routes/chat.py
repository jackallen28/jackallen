import os
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic

router = APIRouter()

def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=key)

SYSTEM_PROMPT = """You are an expert Arduino and ESP32 embedded systems assistant inside the
Allentronics VibeDuino IDE. Help users write, debug, and understand Arduino/C++ sketches.

WIRING DIAGRAM INSTRUCTIONS
When the user asks about wiring, connecting, or hooking up components, you MUST append a
[WIRING] JSON block at the very end of your reply (after all explanatory text). Use this exact format:

[WIRING]
{
  "connections": [
    { "from": "arduino-uno-r3:D2", "to": "hc-sr501:OUT" },
    { "from": "arduino-uno-r3:5V",  "to": "hc-sr501:VCC" },
    { "from": "arduino-uno-r3:GND", "to": "hc-sr501:GND" }
  ]
}
[/WIRING]

Available component IDs: arduino-uno-r3, hc-sr501
Arduino pin names: D0-D13, A0-A5, 5V, 3V3, GND
HC-SR501 pin names: VCC, OUT, GND

Only include [WIRING] when the user is asking about physical connections. Do not include it
for code-only questions. Keep explanations concise."""


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]

def _extract_wiring(text: str):
    """Pull [WIRING]...[/WIRING] JSON out of the reply, return (clean_text, wiring_dict|None)."""
    match = re.search(r"\[WIRING\]\s*([\s\S]*?)\[/WIRING\]", text)
    if not match:
        return text, None
    try:
        wiring = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return text, None
    clean = text[:match.start()].rstrip() + text[match.end():]
    return clean.strip(), wiring

@router.post("/api/chat")
async def chat(body: ChatRequest):
    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[m.model_dump() for m in body.messages],
    )
    raw = response.content[0].text
    clean, wiring = _extract_wiring(raw)
    return {"reply": clean, "wiring": wiring}

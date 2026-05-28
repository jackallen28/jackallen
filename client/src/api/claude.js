const BASE = "http://localhost:8000"

// Each message: { role: "user" | "assistant", content: string }
// Returns the assistant reply string, or throws on error.
export async function sendMessage(messages) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }

  const data = await res.json()
  return data.reply
}

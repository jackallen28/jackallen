const BASE = "http://localhost:8000"

export async function compile(code, fqbn = "arduino:avr:uno") {
  const res = await fetch(`${BASE}/api/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, fqbn }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json() // { success, stdout, stderr }
}

export async function upload(code, port, fqbn = "arduino:avr:uno") {
  const res = await fetch(`${BASE}/api/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, fqbn, port }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json() // { success, stdout, stderr }
}

export async function listPorts() {
  const res = await fetch(`${BASE}/api/ports`)
  if (!res.ok) return { ports: [] }
  return res.json() // { ports: [{ port }] }
}

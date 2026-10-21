// Talks to the CircuitPath server. Every write carries the X-CircuitPath
// header, which the server requires (it stops other websites sending
// requests as a logged-in student).

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || "Something went wrong. Try again.");
    this.status = status;
    this.code = body?.error || "unknown";
    this.retryAfter = body?.retry_after || 0;
  }

  /** True when the server couldn't be reached (network blip, Pi off). */
  get offline() {
    return this.status === 0;
  }
}

const listeners = new Set();

/** Called with no arguments when the server says the student is logged out. */
export function onLoggedOut(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function request(method, path, body, { raw = false, keepalive = false } = {}) {
  const headers = {};
  let payload;
  if (method !== "GET") headers["X-CircuitPath"] = "1";
  if (body instanceof Blob || body instanceof ArrayBuffer) {
    headers["Content-Type"] = "application/octet-stream";
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, { method, headers, body: payload, credentials: "same-origin", keepalive });
  } catch {
    throw new ApiError(0, { error: "offline", message: "Can't reach CircuitPath. Check your network." });
  }
  if (raw && res.ok) return res;
  let data = null;
  if (res.status !== 204) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  }
  if (!res.ok) {
    const err = new ApiError(res.status, data);
    if (res.status >= 502 && res.status <= 504) err.status = 0; // the Pi is restarting
    if (err.code === "logged_out" && !path.startsWith("/api/login")) listeners.forEach((fn) => fn());
    throw err;
  }
  return data;
}

export const api = {
  info: () => request("GET", "/api/info"),
  catalogue: () => request("GET", "/api/catalogue"),
  project: (id) => request("GET", `/api/projects/${encodeURIComponent(id)}`),
  classes: () => request("GET", "/api/classes"),
  students: (classId) => request("GET", `/api/classes/${classId}/students`),
  createStudent: (profile) => request("POST", "/api/students", profile),
  login: (studentId, pictures) => request("POST", "/api/login", { student_id: studentId, pictures }),
  logout: () => request("POST", "/api/logout"),
  me: () => request("GET", "/api/me"),
  saveSettings: (settings) => request("PUT", "/api/me/settings", settings),
  progress: () => request("GET", "/api/me/progress"),
  saveProgress: (project, data) => request("PUT", `/api/me/progress/${encodeURIComponent(project)}`, data),
  sketch: (project) => request("GET", `/api/me/sketches/${encodeURIComponent(project)}`),
  saveSketch: (project, code, opts) => request("PUT", `/api/me/sketches/${encodeURIComponent(project)}`, { code }, opts),
  previewImport: (file) => request("POST", "/api/me/import?mode=preview", file),
  applyImport: (file, replace) => request("POST", `/api/me/import?mode=apply&replace=${replace ? "true" : "false"}`, file),
  exportUrl: "/api/me/export",
};

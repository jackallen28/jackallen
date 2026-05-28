import { useState, useEffect } from "react"

const BASE = "http://localhost:8000"

const FILE_ICONS = { ".ino": "⚡", ".h": "📄", ".cpp": "📄", ".c": "📄" }
function icon(name) {
  const ext = name.slice(name.lastIndexOf("."))
  return FILE_ICONS[ext] ?? "📄"
}

export default function Sidebar({ activeFile, onFileSelect, onFileCreated }) {
  const [files, setFiles] = useState([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")
  const [error, setError] = useState(null)

  async function fetchFiles() {
    try {
      const res = await fetch(`${BASE}/api/files`)
      const data = await res.json()
      setFiles(data.files ?? [])
    } catch {
      setError("Backend offline")
    }
  }

  useEffect(() => { fetchFiles() }, [])

  async function handleCreate() {
    const name = newName.trim()
    if (!name) return
    const filename = name.includes(".") ? name : `${name}.ino`
    try {
      await fetch(`${BASE}/api/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, content: "", project: "default" }),
      })
      setNewName("")
      setCreating(false)
      await fetchFiles()
      onFileCreated?.(filename)
    } catch {
      setError("Could not create file")
    }
  }

  async function handleDelete(e, filename) {
    e.stopPropagation()
    if (!confirm(`Delete ${filename}?`)) return
    await fetch(`${BASE}/api/files/${filename}?project=default`, { method: "DELETE" })
    await fetchFiles()
    if (activeFile === filename) onFileSelect?.(null)
  }

  return (
    <div className="h-full flex flex-col bg-[#16213e] border-r border-[#0f3460] text-xs">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#0f3460] shrink-0">
        <span className="font-bold text-[#e94560] tracking-widest">FILES</span>
        <button
          onClick={() => { setCreating(true); setNewName("") }}
          className="text-gray-400 hover:text-white text-base leading-none"
          title="New file"
        >+</button>
      </div>

      {/* New-file input */}
      {creating && (
        <div className="px-2 py-1 border-b border-[#0f3460] flex gap-1 shrink-0">
          <input
            autoFocus
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setCreating(false) }}
            placeholder="name.ino"
            className="flex-1 bg-[#0d0d1a] border border-[#0f3460] rounded px-1 py-0.5 text-gray-200 focus:outline-none focus:border-[#e94560]"
          />
          <button onClick={handleCreate} className="text-[#e94560] px-1">✓</button>
          <button onClick={() => setCreating(false)} className="text-gray-500 px-1">✕</button>
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto">
        {error && <p className="px-3 py-2 text-red-400">{error}</p>}
        {files.length === 0 && !error && (
          <p className="px-3 py-3 text-gray-600">No files yet</p>
        )}
        {files.map(f => (
          <div
            key={f}
            onClick={() => onFileSelect?.(f)}
            className={`flex items-center justify-between px-3 py-1.5 cursor-pointer group ${
              activeFile === f
                ? "bg-[#0f3460] text-white"
                : "text-gray-400 hover:bg-[#0f3460]/50 hover:text-gray-200"
            }`}
          >
            <span>{icon(f)} {f}</span>
            <button
              onClick={e => handleDelete(e, f)}
              className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 ml-1"
            >✕</button>
          </div>
        ))}
      </div>
    </div>
  )
}

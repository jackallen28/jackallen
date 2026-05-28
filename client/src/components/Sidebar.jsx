import { useState, useEffect } from "react"
import { FolderOpen, FilePlus, Trash2, FileCode, FileType, File } from "lucide-react"

const BASE = "http://localhost:8000"

function FileIcon({ name }) {
  const ext = name.slice(name.lastIndexOf("."))
  if (ext === ".ino") return <FileCode size={12} className="text-[#e94560] shrink-0" />
  if (ext === ".h")   return <FileType size={12} className="text-[#4a9eff] shrink-0" />
  if (ext === ".cpp" || ext === ".c") return <File size={12} className="text-[#c084fc] shrink-0" />
  return <File size={12} className="text-gray-500 shrink-0" />
}

export default function Sidebar({ activeFile, onFileSelect, onFileCreated }) {
  const [files, setFiles]     = useState([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName]   = useState("")
  const [error, setError]       = useState(null)

  async function fetchFiles() {
    try {
      const res = await fetch(`${BASE}/api/files`)
      const data = await res.json()
      setFiles(data.files ?? [])
      setError(null)
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
    <div className="h-full flex flex-col bg-[#080e1c] panel-border-r text-xs">

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 panel-border-b shrink-0">
        <div className="flex items-center gap-1.5">
          <FolderOpen size={12} className="text-[#4a9eff]" />
          <span className="font-bold tracking-widest text-[10px] text-gray-400 uppercase">Project</span>
        </div>
        <button
          onClick={() => { setCreating(true); setNewName("") }}
          title="New file"
          className="text-gray-500 hover:text-[#e94560] transition-colors p-0.5 rounded"
        >
          <FilePlus size={13} />
        </button>
      </div>

      {/* New-file input */}
      {creating && (
        <div className="px-2 py-1.5 panel-border-b flex gap-1 shrink-0 bg-[#0d1526]">
          <input
            autoFocus
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter") handleCreate()
              if (e.key === "Escape") setCreating(false)
            }}
            placeholder="filename.ino"
            className="flex-1 bg-[#080b14] border border-[#e94560]/40 rounded px-2 py-0.5 text-gray-200 focus:outline-none focus:border-[#e94560] placeholder-gray-600"
          />
          <button onClick={handleCreate} className="text-green-400 hover:text-green-300 px-1">✓</button>
          <button onClick={() => setCreating(false)} className="text-gray-600 hover:text-gray-400 px-1">✕</button>
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto py-1">
        {error && (
          <p className="px-3 py-2 text-yellow-500/70 text-[10px]">⚠ {error}</p>
        )}
        {!error && files.length === 0 && (
          <p className="px-3 py-3 text-gray-700">No files yet</p>
        )}
        {files.map(f => (
          <div
            key={f}
            onClick={() => onFileSelect?.(f)}
            className={`flex items-center justify-between px-3 py-1.5 cursor-pointer group transition-colors ${
              activeFile === f
                ? "bg-[#e94560]/10 border-l-2 border-[#e94560] text-white"
                : "text-gray-500 hover:bg-[#0d1526] hover:text-gray-300 border-l-2 border-transparent"
            }`}
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <FileIcon name={f} />
              <span className="truncate">{f}</span>
            </div>
            <button
              onClick={e => handleDelete(e, f)}
              className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 ml-1 transition-opacity shrink-0"
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="panel-border-t px-3 py-1.5 shrink-0">
        <span className="text-[10px] text-gray-700">default project</span>
      </div>
    </div>
  )
}

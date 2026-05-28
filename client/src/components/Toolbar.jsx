import { useState, useEffect } from "react"
import { compile, upload, listPorts } from "../api/compiler"

const BOARDS = [
  { label: "Arduino Uno",    fqbn: "arduino:avr:uno" },
  { label: "Arduino Mega",   fqbn: "arduino:avr:mega" },
  { label: "Arduino Nano",   fqbn: "arduino:avr:nano" },
  { label: "ESP32",          fqbn: "esp32:esp32:esp32" },
  { label: "ESP8266",        fqbn: "esp8266:esp8266:generic" },
]

export default function Toolbar({ code }) {
  const [fqbn, setFqbn] = useState(BOARDS[0].fqbn)
  const [ports, setPorts] = useState([])
  const [port, setPort] = useState("")
  const [status, setStatus] = useState({ msg: "", ok: null }) // ok: true/false/null
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listPorts().then(({ ports: p }) => {
      setPorts(p)
      if (p.length) setPort(p[0].port)
    })
  }, [])

  async function handleCompile() {
    if (busy) return
    setBusy(true)
    setStatus({ msg: "Compiling…", ok: null })
    try {
      const res = await compile(code ?? "", fqbn)
      setStatus({ msg: res.success ? "Compiled OK" : res.stderr.split("\n")[0] || "Error", ok: res.success })
    } catch (e) {
      setStatus({ msg: e.message, ok: false })
    } finally {
      setBusy(false)
    }
  }

  async function handleUpload() {
    if (busy || !port) return
    setBusy(true)
    setStatus({ msg: "Uploading…", ok: null })
    try {
      const res = await upload(code ?? "", port, fqbn)
      setStatus({ msg: res.success ? "Upload OK" : res.stderr.split("\n")[0] || "Error", ok: res.success })
    } catch (e) {
      setStatus({ msg: e.message, ok: false })
    } finally {
      setBusy(false)
    }
  }

  const statusColor = status.ok === null ? "text-gray-400" : status.ok ? "text-green-400" : "text-red-400"

  return (
    <div className="flex items-center gap-3 px-4 h-full bg-[#16213e] border-b border-[#0f3460]">
      {/* Brand */}
      <span className="text-[#e94560] font-bold text-xs tracking-widest shrink-0">VIBEDUINO</span>

      <div className="w-px h-5 bg-[#0f3460]" />

      {/* Board selector */}
      <select
        value={fqbn}
        onChange={e => setFqbn(e.target.value)}
        className="bg-[#0d0d1a] border border-[#0f3460] text-gray-300 text-xs rounded px-2 py-1 focus:outline-none focus:border-[#e94560]"
      >
        {BOARDS.map(b => (
          <option key={b.fqbn} value={b.fqbn}>{b.label}</option>
        ))}
      </select>

      {/* Port selector */}
      <select
        value={port}
        onChange={e => setPort(e.target.value)}
        className="bg-[#0d0d1a] border border-[#0f3460] text-gray-300 text-xs rounded px-2 py-1 focus:outline-none focus:border-[#e94560]"
      >
        {ports.length === 0
          ? <option value="">No ports found</option>
          : ports.map(p => <option key={p.port} value={p.port}>{p.port}</option>)
        }
      </select>

      {/* Compile */}
      <button
        onClick={handleCompile}
        disabled={busy}
        className="px-3 py-1 text-xs bg-[#0f3460] border border-[#e94560] text-[#e94560] rounded hover:bg-[#e94560] hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ▶ Compile
      </button>

      {/* Upload */}
      <button
        onClick={handleUpload}
        disabled={busy || !port}
        className="px-3 py-1 text-xs bg-[#e94560] text-white rounded hover:bg-[#c73652] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ⬆ Upload
      </button>

      {/* Status */}
      {status.msg && (
        <span className={`text-xs truncate max-w-xs ${statusColor}`}>
          {status.msg}
        </span>
      )}
    </div>
  )
}

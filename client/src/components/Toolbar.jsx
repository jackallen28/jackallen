import { useState, useEffect } from "react"
import { Play, Upload, Cpu, RefreshCw, Circle, ChevronDown, Zap } from "lucide-react"
import { compile, upload, listPorts } from "../api/compiler"

const BOARDS = [
  { label: "Arduino Uno",   fqbn: "arduino:avr:uno" },
  { label: "Arduino Mega",  fqbn: "arduino:avr:mega" },
  { label: "Arduino Nano",  fqbn: "arduino:avr:nano" },
  { label: "ESP32",         fqbn: "esp32:esp32:esp32" },
  { label: "ESP8266",       fqbn: "esp8266:esp8266:generic" },
]

const STATUS_STYLE = {
  idle:    "text-gray-500",
  busy:    "text-yellow-400",
  ok:      "text-green-400",
  error:   "text-red-400",
}

export default function Toolbar({ code }) {
  const [fqbn, setFqbn]     = useState(BOARDS[0].fqbn)
  const [ports, setPorts]   = useState([])
  const [port, setPort]     = useState("")
  const [status, setStatus] = useState({ msg: "", type: "idle" })
  const [busy, setBusy]     = useState(false)

  useEffect(() => {
    listPorts().then(({ ports: p }) => {
      setPorts(p)
      if (p.length) setPort(p[0].port)
    })
  }, [])

  async function run(label, action) {
    if (busy) return
    setBusy(true)
    setStatus({ msg: `${label}…`, type: "busy" })
    try {
      const res = await action()
      setStatus({
        msg: res.success ? `${label} OK` : (res.stderr?.split("\n").find(l => l.includes("error:")) ?? "Failed"),
        type: res.success ? "ok" : "error",
      })
    } catch (e) {
      setStatus({ msg: e.message, type: "error" })
    } finally {
      setBusy(false)
    }
  }

  const boardLabel = BOARDS.find(b => b.fqbn === fqbn)?.label ?? fqbn

  return (
    <div className="flex items-center gap-3 px-4 h-full bg-[#080e1c] panel-border-b select-none">

      {/* Brand */}
      <div className="flex items-center gap-1.5 shrink-0 mr-1">
        <Zap size={15} className="text-[#e94560]" fill="#e94560" />
        <span className="text-xs font-bold tracking-[0.18em]"
          style={{ background: "linear-gradient(90deg,#e94560,#ff6b9d)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          VIBEDUINO
        </span>
      </div>

      <div className="w-px h-5 bg-[#1a2744]" />

      {/* Board selector */}
      <div className="relative flex items-center gap-1 text-xs text-gray-400">
        <Cpu size={11} className="text-[#4a7fc1] shrink-0" />
        <div className="relative">
          <select
            value={fqbn}
            onChange={e => setFqbn(e.target.value)}
            className="appearance-none bg-[#0d1526] border border-[#1a2744] hover:border-[#2a3f6f] text-gray-300 text-xs rounded pl-2 pr-6 py-1 focus:outline-none focus:border-[#e94560] cursor-pointer transition-colors"
          >
            {BOARDS.map(b => <option key={b.fqbn} value={b.fqbn}>{b.label}</option>)}
          </select>
          <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
        </div>
      </div>

      {/* Port selector */}
      <div className="relative flex items-center gap-1 text-xs text-gray-400">
        <Circle size={8} className={ports.length ? "text-green-400 fill-green-400" : "text-gray-600 fill-gray-600"} />
        <div className="relative">
          <select
            value={port}
            onChange={e => setPort(e.target.value)}
            className="appearance-none bg-[#0d1526] border border-[#1a2744] hover:border-[#2a3f6f] text-gray-300 text-xs rounded pl-2 pr-6 py-1 focus:outline-none focus:border-[#e94560] cursor-pointer transition-colors"
          >
            {ports.length === 0
              ? <option value="">No ports</option>
              : ports.map(p => <option key={p.port} value={p.port}>{p.port}</option>)
            }
          </select>
          <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
        </div>
      </div>

      <div className="w-px h-5 bg-[#1a2744]" />

      {/* Compile */}
      <button
        onClick={() => run("Compile", () => compile(code ?? "", fqbn))}
        disabled={busy}
        className="flex items-center gap-1.5 px-3 py-1 text-xs border border-[#e94560]/40 text-[#e94560] rounded hover:bg-[#e94560]/10 hover:border-[#e94560] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        {busy ? <RefreshCw size={11} className="animate-spin" /> : <Play size={11} fill="currentColor" />}
        Compile
      </button>

      {/* Upload */}
      <button
        onClick={() => run("Upload", () => upload(code ?? "", port, fqbn))}
        disabled={busy || !port}
        className="flex items-center gap-1.5 px-3 py-1 text-xs bg-[#e94560] text-white rounded hover:bg-[#c73652] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_8px_#e9456044]"
      >
        {busy ? <RefreshCw size={11} className="animate-spin" /> : <Upload size={11} />}
        Upload
      </button>

      {/* Status message */}
      {status.msg && (
        <span className={`text-xs truncate max-w-sm animate-status ${STATUS_STYLE[status.type]}`}>
          {status.type === "ok" && "✓ "}
          {status.type === "error" && "✗ "}
          {status.msg}
        </span>
      )}
    </div>
  )
}

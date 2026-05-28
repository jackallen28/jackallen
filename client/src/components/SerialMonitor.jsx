import { useState, useRef, useEffect } from "react"
import { Terminal, Plug, PlugZap, Trash2, ChevronsRight } from "lucide-react"
import { useSerial } from "../hooks/useSerial"

const BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400]

function LogLine({ entry }) {
  const styles = {
    in:   "text-green-300",
    out:  "text-[#e94560]",
    info: "text-[#4a9eff]",
    err:  "text-yellow-400",
  }
  const prefix = { in: "  ", out: ">>", info: "--", err: "!!" }
  return (
    <div className={`flex gap-2 leading-4 ${styles[entry.dir] ?? "text-gray-300"}`}>
      <span className="opacity-40 shrink-0 select-none">{prefix[entry.dir] ?? "  "}</span>
      <span className="break-all">{entry.text}</span>
    </div>
  )
}

export default function SerialMonitor() {
  const { connected, log, connect, disconnect, send, clearLog } = useSerial()
  const [input, setInput] = useState("")
  const [baud, setBaud]   = useState(115200)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [log])

  function handleSend() {
    const text = input.trim()
    if (!text || !connected) return
    send(text)
    setInput("")
  }

  return (
    <div className="h-full flex flex-col bg-[#040810] panel-border-t relative overflow-hidden crt crt-scan">

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#080e1c] panel-border-b shrink-0 z-10">
        <Terminal size={11} className="text-[#00ff88]" />
        <span className="text-[10px] font-bold tracking-widest text-gray-500 uppercase">Serial Monitor</span>

        {/* Connection indicator */}
        <div className="flex items-center gap-1.5 ml-1">
          <div className={`w-1.5 h-1.5 rounded-full transition-all ${
            connected
              ? "bg-green-400 shadow-[0_0_6px_#4ade80]"
              : "bg-gray-700"
          }`} />
          <span className={`text-[10px] ${connected ? "text-green-400" : "text-gray-600"}`}>
            {connected ? `${baud} baud` : "disconnected"}
          </span>
        </div>

        {/* Baud selector */}
        <select
          value={baud}
          onChange={e => setBaud(Number(e.target.value))}
          disabled={connected}
          className="ml-auto bg-transparent border border-[#1a2744] text-gray-500 text-[10px] rounded px-1 py-0.5 focus:outline-none disabled:opacity-50"
        >
          {BAUD_RATES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>

        <button
          onClick={connected ? disconnect : () => connect(baud)}
          className={`flex items-center gap-1 px-2 py-0.5 text-[10px] rounded transition-colors ${
            connected
              ? "bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-900/40"
              : "bg-[#0d1526] text-gray-400 hover:text-green-400 border border-[#1a2744] hover:border-green-800"
          }`}
        >
          {connected ? <><Plug size={9} /> Disconnect</> : <><PlugZap size={9} /> Connect</>}
        </button>

        <button onClick={clearLog} className="text-gray-700 hover:text-gray-400 transition-colors" title="Clear">
          <Trash2 size={11} />
        </button>
      </div>

      {/* Log */}
      <div className="flex-1 overflow-y-auto px-3 py-1 font-mono text-[11px] z-10">
        {log.length === 0 && (
          <p className="text-gray-700 mt-2 text-[11px]">
            {connected ? "Waiting for data…" : "Connect a board to start monitoring serial output."}
          </p>
        )}
        {log.map((entry, i) => <LogLine key={i} entry={entry} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 panel-border-t flex items-center z-10 bg-[#040810]">
        <ChevronsRight size={12} className={`ml-3 shrink-0 ${connected ? "text-[#e94560]" : "text-gray-700"}`} />
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          disabled={!connected}
          placeholder={connected ? "Send command…" : "Not connected"}
          className="flex-1 bg-transparent px-2 py-1.5 text-xs text-green-300 focus:outline-none disabled:text-gray-700 placeholder-gray-700 font-mono"
        />
        <button
          onClick={handleSend}
          disabled={!connected || !input.trim()}
          className="px-3 text-xs text-[#e94560] hover:text-white disabled:text-gray-700 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}

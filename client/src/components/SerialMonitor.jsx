import { useState, useRef, useEffect } from "react"
import { useSerial } from "../hooks/useSerial"

const BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400]

export default function SerialMonitor() {
  const { connected, log, connect, disconnect, send, clearLog } = useSerial()
  const [input, setInput] = useState("")
  const [baud, setBaud] = useState(115200)
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

  function lineColor(dir) {
    if (dir === "out") return "text-[#e94560]"
    if (dir === "err") return "text-yellow-400"
    if (dir === "info") return "text-blue-400"
    return "text-green-300"
  }

  return (
    <div className="h-full flex flex-col bg-[#0d0d1a] border-t border-[#0f3460]">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-1 border-b border-[#0f3460] shrink-0">
        <span className="text-[#e94560] font-bold text-xs tracking-widest">SERIAL MONITOR</span>
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-gray-600"}`} />

        <select
          value={baud}
          onChange={e => setBaud(Number(e.target.value))}
          disabled={connected}
          className="ml-auto bg-[#16213e] border border-[#0f3460] text-gray-300 text-xs rounded px-1 py-0.5 focus:outline-none"
        >
          {BAUD_RATES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>

        <button
          onClick={connected ? disconnect : () => connect(baud)}
          className={`px-2 py-0.5 text-xs rounded ${
            connected
              ? "bg-red-800 text-red-300 hover:bg-red-700"
              : "bg-[#0f3460] text-gray-300 hover:bg-[#1a4a80]"
          }`}
        >
          {connected ? "Disconnect" : "Connect"}
        </button>

        <button
          onClick={clearLog}
          className="px-2 py-0.5 text-xs text-gray-500 hover:text-gray-300"
        >
          Clear
        </button>
      </div>

      {/* Log */}
      <div className="flex-1 overflow-y-auto px-3 py-1 font-mono text-xs">
        {log.length === 0 && (
          <p className="text-gray-600 mt-2">Connect a board and click Connect to start monitoring.</p>
        )}
        {log.map((entry, i) => (
          <div key={i} className={lineColor(entry.dir)}>
            {entry.dir === "out" ? ">> " : entry.dir === "info" || entry.dir === "err" ? "-- " : ""}
            {entry.text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-[#0f3460] flex">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          disabled={!connected}
          placeholder={connected ? "Send command…" : "Not connected"}
          className="flex-1 bg-transparent px-3 py-1.5 text-xs text-gray-200 focus:outline-none disabled:text-gray-600"
        />
        <button
          onClick={handleSend}
          disabled={!connected || !input.trim()}
          className="px-3 text-xs text-[#e94560] hover:text-white disabled:opacity-30"
        >
          Send
        </button>
      </div>
    </div>
  )
}

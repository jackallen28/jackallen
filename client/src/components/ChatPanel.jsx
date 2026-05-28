import { useState, useRef, useEffect } from "react"
import { sendMessage } from "../api/claude"

export default function ChatPanel() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    const next = [...messages, { role: "user", content: text }]
    setMessages(next)
    setInput("")
    setError(null)
    setLoading(true)

    try {
      const reply = await sendMessage(next)
      setMessages([...next, { role: "assistant", content: reply }])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col bg-[#16213e] border-l border-[#0f3460]">
      {/* header */}
      <div className="px-3 py-2 border-b border-[#0f3460] text-xs font-bold text-[#e94560] tracking-widest shrink-0">
        AI ASSISTANT
      </div>

      {/* message list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3 text-sm">
        {messages.length === 0 && (
          <p className="text-gray-500 text-xs mt-4 text-center">
            Ask anything about your Arduino / ESP32 sketch.
          </p>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded px-3 py-2 whitespace-pre-wrap break-words ${
              m.role === "user"
                ? "bg-[#0f3460] text-gray-200 ml-4"
                : "bg-[#1a1a2e] border border-[#0f3460] text-gray-300 mr-4"
            }`}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div className="bg-[#1a1a2e] border border-[#0f3460] text-gray-500 text-xs rounded px-3 py-2 mr-4 animate-pulse">
            thinking...
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-400 text-xs rounded px-3 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* input */}
      <div className="shrink-0 border-t border-[#0f3460] p-2 flex gap-2">
        <textarea
          className="flex-1 bg-[#0d0d1a] border border-[#0f3460] rounded px-2 py-1 text-xs text-gray-200 resize-none focus:outline-none focus:border-[#e94560]"
          rows={2}
          placeholder="Ask about your sketch… (Enter to send)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="px-3 py-1 text-xs bg-[#e94560] text-white rounded hover:bg-[#c73652] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  )
}

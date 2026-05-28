import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Sparkles } from "lucide-react"
import { sendMessage } from "../api/claude"

// Renders text with ```code blocks``` highlighted
function MessageContent({ text }) {
  const parts = text.split(/(```[\s\S]*?```)/g)
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith("```")) {
          const lines = part.slice(3).split("\n")
          const lang = lines[0].trim()
          const code = lines.slice(1, -1).join("\n")
          return (
            <pre key={i} className="mt-2 mb-1 bg-[#080b14] border border-[#1a2744] rounded p-2 text-xs text-green-300 overflow-x-auto whitespace-pre-wrap">
              {lang && <span className="text-[#e94560]/70 text-[10px] block mb-1">{lang}</span>}
              {code}
            </pre>
          )
        }
        return <span key={i} className="whitespace-pre-wrap">{part}</span>
      })}
    </span>
  )
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-3 py-2">
      <Bot size={11} className="text-[#4a9eff] mr-1 shrink-0" />
      <span className="text-[10px] text-gray-500 mr-2">thinking</span>
      <span className="w-1.5 h-1.5 rounded-full bg-[#4a9eff] animate-dot-1 inline-block" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#4a9eff] animate-dot-2 inline-block" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#4a9eff] animate-dot-3 inline-block" />
    </div>
  )
}

export default function ChatPanel({ code, onWiring }) {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState("")
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    const userContent = code
      ? `${text}\n\n[Current sketch]\n\`\`\`cpp\n${code}\n\`\`\``
      : text

    const next = [...messages, { role: "user", content: userContent }]
    setMessages(next)
    setInput("")
    setError(null)
    setLoading(true)
    textareaRef.current?.focus()

    try {
      const { reply, wiring } = await sendMessage(next)
      setMessages([...next, { role: "assistant", content: reply }])
      if (wiring) onWiring?.(wiring)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  // Display text: strip the appended sketch from user messages
  function displayText(msg) {
    if (msg.role !== "user") return msg.content
    const idx = msg.content.indexOf("\n\n[Current sketch]")
    return idx !== -1 ? msg.content.slice(0, idx) : msg.content
  }

  return (
    <div className="h-full flex flex-col bg-[#080e1c] panel-border-l">

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 panel-border-b shrink-0">
        <Sparkles size={12} className="text-[#e94560]" />
        <span className="text-[10px] font-bold tracking-widest text-gray-400 uppercase">AI Assistant</span>
        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-green-400 shadow-[0_0_6px_#4ade80]" title="Claude connected" />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-xs">

        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-3 mt-6 text-center">
            <div className="w-10 h-10 rounded-full bg-[#e94560]/10 border border-[#e94560]/20 flex items-center justify-center animate-glow">
              <Bot size={18} className="text-[#e94560]" />
            </div>
            <p className="text-gray-600 text-[11px] leading-relaxed max-w-[200px]">
              Ask anything about your Arduino or ESP32 sketch. I can see your current code.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2 animate-slide-in ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
              m.role === "user"
                ? "bg-[#e94560]/20 border border-[#e94560]/30"
                : "bg-[#4a9eff]/10 border border-[#4a9eff]/20"
            }`}>
              {m.role === "user"
                ? <User size={9} className="text-[#e94560]" />
                : <Bot size={9} className="text-[#4a9eff]" />
              }
            </div>
            <div className={`rounded-lg px-3 py-2 max-w-[88%] leading-relaxed ${
              m.role === "user"
                ? "bg-[#1a1030] border border-[#e94560]/15 text-gray-300"
                : "bg-[#0d1526] border border-[#1a2744] text-gray-300"
            }`}>
              <MessageContent text={displayText(m)} />
            </div>
          </div>
        ))}

        {loading && <ThinkingDots />}

        {error && (
          <div className="bg-red-900/20 border border-red-800/40 text-red-400 text-[11px] rounded px-3 py-2">
            ✗ {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 panel-border-t p-2">
        <div className="flex gap-2 items-end bg-[#0d1526] border border-[#1a2744] rounded-lg px-3 py-2 focus-within:border-[#e94560]/40 transition-colors">
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Ask about your sketch… (Enter to send)"
            className="flex-1 bg-transparent text-xs text-gray-200 resize-none focus:outline-none placeholder-gray-700 leading-relaxed"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="shrink-0 w-6 h-6 rounded flex items-center justify-center bg-[#e94560] hover:bg-[#c73652] disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-[0_0_6px_#e9456055]"
          >
            <Send size={10} className="text-white" />
          </button>
        </div>
        <p className="text-[10px] text-gray-700 mt-1 text-right">⇧↵ newline · ↵ send</p>
      </div>
    </div>
  )
}

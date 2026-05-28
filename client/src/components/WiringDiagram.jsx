import { Cpu } from "lucide-react"

// Animated circuit trace component
function Trace({ d, delay = 0, color = "#1a2744" }) {
  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth="1.5"
      strokeDasharray="200"
      strokeDashoffset="0"
      strokeLinecap="round"
      style={{ animation: `circuit-trace 3s ease-in-out ${delay}s infinite` }}
    />
  )
}

function PlaceholderBoard() {
  return (
    <svg viewBox="0 0 360 200" className="w-full max-w-sm opacity-60" aria-hidden="true">
      {/* PCB base */}
      <rect x="40" y="10" width="280" height="180" rx="8"
        fill="#050d1a" stroke="#1a2744" strokeWidth="1.5" />

      {/* Animated traces */}
      <Trace d="M 80 50 L 160 50 L 160 100" delay={0} color="#0f3460" />
      <Trace d="M 280 60 L 200 60 L 200 100" delay={0.8} color="#0f3460" />
      <Trace d="M 80 150 L 160 150 L 160 100" delay={1.6} color="#0f3460" />
      <Trace d="M 280 140 L 200 140 L 200 100" delay={2.4} color="#0f3460" />

      {/* Left pin header */}
      {[0,1,2,3,4,5,6,7].map(i => (
        <g key={`lp${i}`}>
          <rect x="44" y={22 + i * 20} width="22" height="10" rx="2"
            fill="#0a1628" stroke="#1e3a5f" strokeWidth="1" />
          <circle cx="55" cy={27 + i * 20} r="2.5" fill="#4a7fc1" opacity="0.7" />
          <text x="72" y={31 + i * 20} fill="#1e3a5f" fontSize="7" fontFamily="monospace">
            D{i}
          </text>
        </g>
      ))}

      {/* Right pin header */}
      {[0,1,2,3,4,5].map(i => (
        <g key={`rp${i}`}>
          <rect x="294" y={22 + i * 20} width="22" height="10" rx="2"
            fill="#0a1628" stroke="#1e3a5f" strokeWidth="1" />
          <circle cx="305" cy={27 + i * 20} r="2.5" fill="#4a7fc1" opacity="0.7" />
          <text x="280" y={31 + i * 20} fill="#1e3a5f" fontSize="7" fontFamily="monospace" textAnchor="end">
            {i < 4 ? `A${i}` : i === 4 ? "3V3" : "GND"}
          </text>
        </g>
      ))}

      {/* MCU chip */}
      <rect x="120" y="72" width="120" height="56" rx="4"
        fill="#0a1628" stroke="#1e3a5f" strokeWidth="1.5" />
      {/* Chip pin marks */}
      {[0,1,2,3].map(i => (
        <g key={`cp${i}`}>
          <rect x={130 + i * 24} y="68" width="8" height="8" rx="1" fill="#1e3a5f" />
          <rect x={130 + i * 24} y="124" width="8" height="8" rx="1" fill="#1e3a5f" />
        </g>
      ))}
      <text x="180" y="97" fill="#2a4a7f" fontSize="9" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
        ATmega328P
      </text>
      <text x="180" y="112" fill="#1e3a5f" fontSize="7" textAnchor="middle" fontFamily="monospace">
        16 MHz
      </text>

      {/* Crystal */}
      <ellipse cx="260" cy="100" rx="12" ry="6" fill="#0a1628" stroke="#1e3a5f" strokeWidth="1" />
      <text x="260" y="103" fill="#1e3a5f" fontSize="6" textAnchor="middle" fontFamily="monospace">XTAL</text>

      {/* USB */}
      <rect x="143" y="172" width="38" height="14" rx="3"
        fill="#0a1628" stroke="#1e3a5f" strokeWidth="1" />
      <rect x="149" y="176" width="6" height="6" rx="1" fill="#1e3a5f" />
      <rect x="157" y="176" width="6" height="6" rx="1" fill="#1e3a5f" />
      <rect x="165" y="176" width="6" height="6" rx="1" fill="#1e3a5f" />
      <text x="162" y="171" fill="#1e3a5f" fontSize="6" textAnchor="middle" fontFamily="monospace">USB</text>

      {/* Power LED */}
      <circle cx="100" cy="165" r="5" fill="#0a1628" stroke="#e94560" strokeWidth="1" />
      <circle cx="100" cy="165" r="2" fill="#e94560" opacity="0.6"
        style={{ animation: "glow-pulse 2s ease-in-out infinite" }} />
      <text x="100" y="158" fill="#e94560" fontSize="5.5" textAnchor="middle" opacity="0.5">PWR</text>
    </svg>
  )
}

export default function WiringDiagram({ components = [] }) {
  return (
    <div className="h-full flex flex-col bg-[#050c18] panel-border-t">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 panel-border-b bg-[#080e1c] shrink-0">
        <Cpu size={11} className="text-[#4a9eff]" />
        <span className="text-[10px] font-bold tracking-widest text-gray-500 uppercase">Wiring Diagram</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-3 overflow-hidden px-4">
        {components.length === 0 ? (
          <>
            <PlaceholderBoard />
            <p className="text-[10px] text-gray-700 text-center max-w-xs">
              Ask the AI to &quot;wire an LED to pin 13&quot; and the diagram will update here
            </p>
          </>
        ) : (
          <div className="w-full overflow-auto p-4 text-xs text-gray-400 space-y-1">
            {components.map((c, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-[#e94560]">{c.name}</span>
                <span className="text-gray-600">→</span>
                <span className="text-[#4a9eff]">{c.pin}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

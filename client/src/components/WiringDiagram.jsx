// Renders a pin/component diagram driven by AI-parsed data from ChatPanel.
// Currently shows a placeholder; component data will be passed via props once
// the chat route extracts structured wiring info from AI responses.
export default function WiringDiagram({ components = [] }) {
  return (
    <div className="h-full flex flex-col bg-[#0b0b18] border-t border-[#0f3460]">
      {/* Header */}
      <div className="px-3 py-1 border-b border-[#0f3460] shrink-0">
        <span className="text-[#e94560] font-bold text-xs tracking-widest">WIRING DIAGRAM</span>
      </div>

      {components.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <svg viewBox="0 0 320 160" className="w-72 opacity-30" aria-hidden="true">
            {/* Board outline */}
            <rect x="20" y="20" width="280" height="120" rx="6" fill="none" stroke="#0f3460" strokeWidth="2" />
            {/* Left pin rail */}
            {[0,1,2,3,4,5,6].map(i => (
              <g key={`l${i}`}>
                <rect x="8" y={30 + i * 14} width="18" height="8" rx="2" fill="#0f3460" />
                <text x="30" y={37 + i * 14} fill="#1a4a80" fontSize="6">D{i}</text>
              </g>
            ))}
            {/* Right pin rail */}
            {[0,1,2,3].map(i => (
              <g key={`r${i}`}>
                <rect x="294" y={30 + i * 14} width="18" height="8" rx="2" fill="#0f3460" />
                <text x="280" y={37 + i * 14} fill="#1a4a80" fontSize="6" textAnchor="end">A{i}</text>
              </g>
            ))}
            {/* Chip */}
            <rect x="110" y="55" width="100" height="50" rx="4" fill="#0d0d1a" stroke="#1a4a80" strokeWidth="1.5" />
            <text x="160" y="84" fill="#1a4a80" fontSize="9" textAnchor="middle">MCU</text>
            {/* USB */}
            <rect x="130" y="125" width="40" height="12" rx="2" fill="#0f3460" />
            <text x="150" y="134" fill="#1a4a80" fontSize="6" textAnchor="middle">USB</text>
          </svg>
        </div>
      ) : (
        <div className="flex-1 overflow-auto p-4">
          {/* Future: render component nodes and wire connections */}
          {components.map((c, i) => (
            <div key={i} className="text-xs text-gray-400 mb-1">
              {c.name} → {c.pin}
            </div>
          ))}
        </div>
      )}

      {components.length === 0 && (
        <p className="text-center text-xs text-gray-700 pb-2">
          Ask the AI to wire a component and the diagram will appear here
        </p>
      )}
    </div>
  )
}

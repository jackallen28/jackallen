import { useState, useRef, useCallback } from "react"
import { Cpu, Plus, Trash2 } from "lucide-react"
import { COMPONENT_DEFS } from "./wiring/components.js"
import WireCanvas from "./wiring/WireCanvas.jsx"

const WIRE_COLORS = [
  "#e94560","#4a9eff","#00ff88","#ffcc00",
  "#ff6b9d","#c084fc","#fb923c","#34d399",
]

const DEFAULT_PLACEMENTS = {
  "arduino-uno-r3": { x: 40,  y: 40 },
  "hc-sr501":       { x: 320, y: 80 },
}

const CANVAS_W = 600
const CANVAS_H = 340

export default function WiringDiagram({ wiring = { connections: [] } }) {
  const [placements, setPlacements] = useState(DEFAULT_PLACEMENTS)
  const [canvasSize]  = useState({ w: CANVAS_W, h: CANVAS_H })
  const dragging = useRef(null)

  // ── drag-to-reposition components ──────────────────────────────────────────
  function onMouseDown(e, compId) {
    e.preventDefault()
    const start = { mx: e.clientX, my: e.clientY, ...placements[compId] }
    dragging.current = { compId, start }
    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
  }

  const onMouseMove = useCallback((e) => {
    if (!dragging.current) return
    const { compId, start } = dragging.current
    setPlacements(prev => ({
      ...prev,
      [compId]: {
        x: Math.max(0, start.x + e.clientX - start.mx),
        y: Math.max(0, start.y + e.clientY - start.my),
      }
    }))
  }, [])

  const onMouseUp = useCallback(() => {
    dragging.current = null
    window.removeEventListener("mousemove", onMouseMove)
    window.removeEventListener("mouseup", onMouseUp)
  }, [onMouseMove])

  const connections = wiring.connections ?? []
  const activeComponents = Object.keys(placements)

  return (
    <div className="h-full flex flex-col bg-[#050c18] panel-border-t">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 panel-border-b bg-[#080e1c] shrink-0">
        <Cpu size={11} className="text-[#4a9eff]" />
        <span className="text-[10px] font-bold tracking-widest text-gray-500 uppercase">Wiring Diagram</span>
        {connections.length > 0 && (
          <span className="ml-auto text-[10px] text-gray-600">{connections.length} connection{connections.length !== 1 ? "s" : ""}</span>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 overflow-auto">
        <div
          className="relative bg-[#040810]"
          style={{
            width: canvasSize.w,
            height: canvasSize.h,
            minWidth: "100%",
            backgroundImage: "radial-gradient(circle, #1a2744 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        >
          {/* Wire layer */}
          <WireCanvas
            connections={connections}
            placements={placements}
            componentDefs={COMPONENT_DEFS}
            width={canvasSize.w}
            height={canvasSize.h}
          />

          {/* Component layer */}
          {activeComponents.map(compId => {
            const def = COMPONENT_DEFS[compId]
            if (!def) return null
            const { x, y } = placements[compId]
            const SVGRenderer = def.render

            return (
              <div
                key={compId}
                onMouseDown={e => onMouseDown(e, compId)}
                style={{ position: "absolute", left: x, top: y, cursor: "grab", userSelect: "none" }}
                title={`${def.label} — drag to move`}
              >
                <div className="relative group">
                  {/* Hover ring */}
                  <div className="absolute inset-0 rounded border border-transparent group-hover:border-[#e94560]/30 pointer-events-none" />
                  <SVGRenderer width={def.width} height={def.height} pinMap={def.pinMap} />
                  {/* Label */}
                  <div className="absolute -top-4 left-0 text-[9px] text-gray-600 whitespace-nowrap font-mono">
                    {def.label}
                  </div>
                </div>
              </div>
            )
          })}

          {/* Empty state */}
          {connections.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <p className="text-[11px] text-gray-700 text-center">
                Ask the AI to wire a component<br/>
                <span className="text-gray-800">e.g. "wire the HC-SR501 to pin D2"</span>
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Connection table */}
      {connections.length > 0 && (
        <div className="shrink-0 panel-border-t overflow-x-auto">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="bg-[#080e1c]">
                <th className="px-3 py-1 text-left text-gray-600 font-normal">#</th>
                <th className="px-3 py-1 text-left text-gray-600 font-normal">From</th>
                <th className="px-3 py-1 text-left text-gray-600 font-normal">To</th>
                <th className="px-3 py-1 text-left text-gray-600 font-normal">Wire</th>
              </tr>
            </thead>
            <tbody>
              {connections.map((c, i) => (
                <tr key={i} className="border-t border-[#0d1526]">
                  <td className="px-3 py-0.5 text-gray-700">{i + 1}</td>
                  <td className="px-3 py-0.5 text-[#4a9eff]">{c.from}</td>
                  <td className="px-3 py-0.5 text-[#00ff88]">{c.to}</td>
                  <td className="px-3 py-0.5">
                    <span
                      className="inline-block w-8 h-1.5 rounded"
                      style={{ background: WIRE_COLORS[i % WIRE_COLORS.length] }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

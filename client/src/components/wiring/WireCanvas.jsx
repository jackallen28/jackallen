// Draws orthogonal SVG wire paths between two absolute canvas points.
// Routes: horizontal leg → vertical leg → horizontal leg (H-V-H)

const WIRE_COLORS = [
  "#e94560", "#4a9eff", "#00ff88", "#ffcc00",
  "#ff6b9d", "#c084fc", "#fb923c", "#34d399",
]

function orthogonalPath(x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2
  return `M ${x1} ${y1} H ${mx} V ${y2} H ${x2}`
}

export default function WireCanvas({ connections, placements, componentDefs, width, height }) {
  return (
    <svg
      width={width}
      height={height}
      style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
    >
      {connections.map((conn, i) => {
        const [fromComp, fromPin] = conn.from.split(":")
        const [toComp, toPin]     = conn.to.split(":")

        const fromPlacement = placements[fromComp]
        const toPlacement   = placements[toComp]
        if (!fromPlacement || !toPlacement) return null

        const fromDef = componentDefs[fromComp]
        const toDef   = componentDefs[toComp]
        if (!fromDef || !toDef) return null

        const fp = fromDef.pinMap[fromPin]
        const tp = toDef.pinMap[toPin]
        if (!fp || !tp) return null

        const x1 = fromPlacement.x + fp.x
        const y1 = fromPlacement.y + fp.y
        const x2 = toPlacement.x + tp.x
        const y2 = toPlacement.y + tp.y

        const color = WIRE_COLORS[i % WIRE_COLORS.length]

        return (
          <g key={i}>
            {/* Shadow for depth */}
            <path d={orthogonalPath(x1, y1, x2, y2)}
              stroke="#000" strokeWidth="3" fill="none" strokeOpacity="0.4"
              strokeLinecap="round" strokeLinejoin="round" />
            {/* Wire */}
            <path d={orthogonalPath(x1, y1, x2, y2)}
              stroke={color} strokeWidth="2" fill="none"
              strokeLinecap="round" strokeLinejoin="round" />
            {/* Pin dots */}
            <circle cx={x1} cy={y1} r="3" fill={color} />
            <circle cx={x2} cy={y2} r="3" fill={color} />
          </g>
        )
      })}
    </svg>
  )
}

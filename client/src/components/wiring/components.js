// Component library — SVG renderers + pin maps
// pinMap coords are relative to the component's top-left corner (pixels at 1x scale)

export const COMPONENT_DEFS = {
  "arduino-uno-r3": {
    label: "Arduino Uno R3",
    width: 180,
    height: 240,
    // Pin positions relative to component origin
    pinMap: {
      "D0":  { x: 162, y: 46 },
      "D1":  { x: 162, y: 59 },
      "D2":  { x: 162, y: 72 },
      "D3":  { x: 162, y: 85 },
      "D4":  { x: 162, y: 98 },
      "D5":  { x: 162, y: 111 },
      "D6":  { x: 162, y: 124 },
      "D7":  { x: 162, y: 137 },
      "D8":  { x: 162, y: 155 },
      "D9":  { x: 162, y: 168 },
      "D10": { x: 162, y: 181 },
      "D11": { x: 162, y: 194 },
      "D12": { x: 162, y: 207 },
      "D13": { x: 162, y: 220 },
      "5V":  { x: 18,  y: 46 },
      "3V3": { x: 18,  y: 59 },
      "GND": { x: 18,  y: 72 },
      "GND2":{ x: 18,  y: 85 },
      "A0":  { x: 18,  y: 168 },
      "A1":  { x: 18,  y: 181 },
      "A2":  { x: 18,  y: 194 },
      "A3":  { x: 18,  y: 207 },
      "A4":  { x: 18,  y: 220 },
      "A5":  { x: 18,  y: 233 },
    },
    render: ArduinoUnoSVG,
  },
  "hc-sr501": {
    label: "HC-SR501 PIR",
    width: 90,
    height: 100,
    pinMap: {
      "VCC": { x: 15, y: 90 },
      "OUT": { x: 45, y: 90 },
      "GND": { x: 75, y: 90 },
    },
    render: HcSr501SVG,
  },
}

// ── SVG component renderers ───────────────────────────────────────────────────

function ArduinoUnoSVG({ width, height, pinMap }) {
  const W = width, H = height
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} overflow="visible">
      {/* PCB body */}
      <rect x="10" y="10" width={W-20} height={H-20} rx="6"
        fill="#1a3a2a" stroke="#2d6a4f" strokeWidth="1.5" />

      {/* Brand strip */}
      <rect x="10" y="10" width={W-20} height="22" rx="6"
        fill="#153020" stroke="none" />
      <text x={W/2} y="25" textAnchor="middle" fill="#2d6a4f"
        fontSize="8" fontFamily="monospace" fontWeight="bold">
        ARDUINO UNO R3
      </text>

      {/* USB connector */}
      <rect x="60" y="0" width="36" height="14" rx="3"
        fill="#1a1a2e" stroke="#2d3a5f" strokeWidth="1" />
      <text x="78" y="10" textAnchor="middle" fill="#2d3a5f"
        fontSize="6" fontFamily="monospace">USB</text>

      {/* MCU chip */}
      <rect x="55" y="95" width="70" height="60" rx="3"
        fill="#111" stroke="#333" strokeWidth="1" />
      <text x="90" y="122" textAnchor="middle" fill="#333"
        fontSize="6" fontFamily="monospace">ATmega</text>
      <text x="90" y="132" textAnchor="middle" fill="#333"
        fontSize="6" fontFamily="monospace">328P</text>

      {/* Crystal */}
      <ellipse cx="44" cy="130" rx="8" ry="4"
        fill="#111" stroke="#2d3a5f" strokeWidth="1" />

      {/* Power LED */}
      <circle cx="30" cy="55" r="4"
        fill="#004400" stroke="#00aa00" strokeWidth="1" />

      {/* Right-side digital pins */}
      {["D0","D1","D2","D3","D4","D5","D6","D7"].map((pin, i) => {
        const { x, y } = pinMap[pin]
        return (
          <g key={pin}>
            <circle cx={x} cy={y} r="4" fill="#b8860b" stroke="#daa520" strokeWidth="0.5" />
            <text x={x-8} y={y+3} textAnchor="end" fill="#5a8a6a"
              fontSize="5.5" fontFamily="monospace">{pin}</text>
          </g>
        )
      })}
      {["D8","D9","D10","D11","D12","D13"].map((pin) => {
        const { x, y } = pinMap[pin]
        return (
          <g key={pin}>
            <circle cx={x} cy={y} r="4" fill="#b8860b" stroke="#daa520" strokeWidth="0.5" />
            <text x={x-8} y={y+3} textAnchor="end" fill="#5a8a6a"
              fontSize="5.5" fontFamily="monospace">{pin}</text>
          </g>
        )
      })}

      {/* Left-side power + analog pins */}
      {["5V","3V3","GND","GND2"].map((pin) => {
        const { x, y } = pinMap[pin]
        const colors = { "5V": "#cc3333", "3V3": "#cc7700", "GND": "#444", "GND2": "#444" }
        return (
          <g key={pin}>
            <circle cx={x} cy={y} r="4" fill={colors[pin] ?? "#b8860b"} stroke="#888" strokeWidth="0.5" />
            <text x={x+8} y={y+3} textAnchor="start" fill="#5a8a6a"
              fontSize="5.5" fontFamily="monospace">{pin === "GND2" ? "GND" : pin}</text>
          </g>
        )
      })}
      {["A0","A1","A2","A3","A4","A5"].map((pin) => {
        const { x, y } = pinMap[pin]
        return (
          <g key={pin}>
            <circle cx={x} cy={y} r="4" fill="#4a7fc1" stroke="#6a9fd1" strokeWidth="0.5" />
            <text x={x+8} y={y+3} textAnchor="start" fill="#5a8a6a"
              fontSize="5.5" fontFamily="monospace">{pin}</text>
          </g>
        )
      })}
    </svg>
  )
}

function HcSr501SVG({ width, height, pinMap }) {
  const W = width, H = height
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} overflow="visible">
      {/* PCB */}
      <rect x="5" y="5" width={W-10} height={H-25} rx="4"
        fill="#3a1a3a" stroke="#6a2a6a" strokeWidth="1.5" />

      {/* Dome lens */}
      <ellipse cx={W/2} cy={H/2 - 10} rx="28" ry="28"
        fill="none" stroke="#8a4a8a" strokeWidth="1.5" strokeDasharray="3 2" />
      <ellipse cx={W/2} cy={H/2 - 10} rx="18" ry="18"
        fill="#2a0a2a" stroke="#8a4a8a" strokeWidth="1" />
      <text x={W/2} y={H/2 - 6} textAnchor="middle" fill="#8a4a8a"
        fontSize="6" fontFamily="monospace">PIR</text>

      {/* Label */}
      <text x={W/2} y={H - 18} textAnchor="middle" fill="#6a2a6a"
        fontSize="6" fontFamily="monospace" fontWeight="bold">HC-SR501</text>

      {/* Pins */}
      {Object.entries(pinMap).map(([pin, { x, y }]) => {
        const colors = { VCC: "#cc3333", GND: "#444", OUT: "#4a9eff" }
        return (
          <g key={pin}>
            <rect x={x-4} y={y-6} width="8" height="12" rx="1"
              fill={colors[pin] ?? "#888"} stroke="#aaa" strokeWidth="0.5" />
            <text x={x} y={y+14} textAnchor="middle" fill="#8a5a8a"
              fontSize="6" fontFamily="monospace">{pin}</text>
          </g>
        )
      })}
    </svg>
  )
}

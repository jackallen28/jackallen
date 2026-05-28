// TODO: connects to compiler.js compile() and upload(), shows board/port selectors,
//       run/stop buttons, and project name. Receives serial port state from useSerial.
export default function Toolbar() {
  return (
    <div className="flex items-center gap-2 px-4 h-full bg-[#16213e] border-b border-[#0f3460]">
      <span className="text-[#e94560] font-bold text-sm tracking-widest">ALLENTRONICS VIBEDUINO</span>
    </div>
  )
}

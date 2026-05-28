import { useState, useEffect } from 'react'
import Toolbar from './components/Toolbar'
import Sidebar from './components/Sidebar'
import CodeEditor from './components/CodeEditor'
import ChatPanel from './components/ChatPanel'
import WiringDiagram from './components/WiringDiagram'
import SerialMonitor from './components/SerialMonitor'

const BASE = "http://localhost:8000"

export default function App() {
  const [code, setCode] = useState(undefined)
  const [activeFile, setActiveFile] = useState("sketch.ino")

  // Load file content when selection changes
  useEffect(() => {
    if (!activeFile) return
    fetch(`${BASE}/api/files/${activeFile}?project=default`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCode(d.content) })
      .catch(() => {})
  }, [activeFile])

  // Auto-save on code change (debounced)
  useEffect(() => {
    if (code === undefined || !activeFile) return
    const t = setTimeout(() => {
      fetch(`${BASE}/api/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: activeFile, content: code, project: "default" }),
      }).catch(() => {})
    }, 800)
    return () => clearTimeout(t)
  }, [code, activeFile])

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateRows: '48px 1fr 180px',
        gridTemplateColumns: '200px 1fr 300px',
        gridTemplateAreas: `
          "toolbar  toolbar  toolbar"
          "sidebar  main     chat"
          "serial   serial   serial"
        `,
        height: '100dvh',
        width: '100%',
      }}
    >
      <div style={{ gridArea: 'toolbar' }}>
        <Toolbar code={code} />
      </div>

      <div style={{ gridArea: 'sidebar', overflow: 'hidden' }}>
        <Sidebar
          activeFile={activeFile}
          onFileSelect={setActiveFile}
          onFileCreated={setActiveFile}
        />
      </div>

      <div style={{ gridArea: 'main', display: 'grid', gridTemplateRows: '1fr 1fr', overflow: 'hidden' }}>
        <CodeEditor value={code} onChange={setCode} filename={activeFile} />
        <WiringDiagram />
      </div>

      <div style={{ gridArea: 'chat', overflow: 'hidden' }}>
        <ChatPanel code={code} />
      </div>

      <div style={{ gridArea: 'serial', overflow: 'hidden' }}>
        <SerialMonitor />
      </div>
    </div>
  )
}

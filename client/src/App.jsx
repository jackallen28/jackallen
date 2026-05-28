import Toolbar from './components/Toolbar'
import Sidebar from './components/Sidebar'
import CodeEditor from './components/CodeEditor'
import ChatPanel from './components/ChatPanel'
import WiringDiagram from './components/WiringDiagram'
import SerialMonitor from './components/SerialMonitor'

export default function App() {
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
        <Toolbar />
      </div>

      <div style={{ gridArea: 'sidebar', overflow: 'hidden' }}>
        <Sidebar />
      </div>

      <div style={{ gridArea: 'main', display: 'grid', gridTemplateRows: '1fr 1fr', overflow: 'hidden' }}>
        <CodeEditor />
        <WiringDiagram />
      </div>

      <div style={{ gridArea: 'chat', overflow: 'hidden' }}>
        <ChatPanel />
      </div>

      <div style={{ gridArea: 'serial', overflow: 'hidden' }}>
        <SerialMonitor />
      </div>
    </div>
  )
}

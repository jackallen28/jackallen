import { useRef } from "react"
import Editor, { loader } from "@monaco-editor/react"
import * as monaco from "monaco-editor"
import { FileCode, Circle } from "lucide-react"

loader.config({ monaco })

const DEFAULT_SKETCH = `// Allentronics VibeDuino — new sketch
void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
`

export default function CodeEditor({ value = DEFAULT_SKETCH, onChange, filename = "sketch.ino", dirty = false }) {
  const editorRef = useRef(null)

  function handleMount(editor) {
    editorRef.current = editor
  }

  return (
    <div className="h-full flex flex-col bg-[#080b14]">
      {/* Tab bar */}
      <div className="flex items-center panel-border-b bg-[#080e1c] shrink-0">
        <div className="flex items-center gap-1.5 px-4 py-1.5 border-b-2 border-[#e94560] bg-[#080b14]">
          <FileCode size={11} className="text-[#e94560]" />
          <span className="text-xs text-gray-300">{filename}</span>
          {dirty && (
            <Circle size={6} className="text-yellow-400 fill-yellow-400 ml-0.5" />
          )}
        </div>
        <div className="ml-auto px-4">
          <span className="text-[10px] text-gray-700 uppercase tracking-wider">C++ / Arduino</span>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          language="cpp"
          theme="vs-dark"
          value={value}
          onChange={onChange}
          onMount={handleMount}
          options={{
            fontSize: 13,
            fontFamily: "ui-monospace, 'Cascadia Code', Consolas, monospace",
            fontLigatures: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            lineNumbers: "on",
            renderLineHighlight: "gutter",
            tabSize: 2,
            wordWrap: "on",
            automaticLayout: true,
            padding: { top: 10 },
            scrollbar: { verticalScrollbarSize: 4, horizontalScrollbarSize: 4 },
            overviewRulerLanes: 0,
            hideCursorInOverviewRuler: true,
            renderLineHighlightOnlyWhenFocus: false,
          }}
        />
      </div>
    </div>
  )
}

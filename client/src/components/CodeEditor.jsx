import { useRef } from "react"
import Editor, { loader } from "@monaco-editor/react"
import * as monaco from "monaco-editor"

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

export default function CodeEditor({ value = DEFAULT_SKETCH, onChange, filename = "sketch.ino" }) {
  const editorRef = useRef(null)

  function handleMount(editor) {
    editorRef.current = editor
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-1 bg-[#0d0d1a] border-b border-[#0f3460] text-xs text-gray-500 shrink-0 flex items-center gap-2">
        <span className="text-[#e94560]">■</span>
        <span>{filename}</span>
      </div>

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
            fontFamily: "ui-monospace, Consolas, monospace",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            lineNumbers: "on",
            renderLineHighlight: "line",
            tabSize: 2,
            wordWrap: "on",
            automaticLayout: true,
            padding: { top: 8 },
          }}
        />
      </div>
    </div>
  )
}

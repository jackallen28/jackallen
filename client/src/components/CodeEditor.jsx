// TODO: wraps @monaco-editor/react with Arduino/C++ syntax highlighting.
//       Receives file content from Sidebar selection; sends content to compiler.js.
export default function CodeEditor() {
  return (
    <div className="h-full bg-[#0d0d1a] flex items-center justify-center">
      <p className="text-xs text-gray-500">CodeEditor</p>
    </div>
  )
}

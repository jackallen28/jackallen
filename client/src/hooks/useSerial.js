import { useState, useRef, useCallback } from "react"

export function useSerial() {
  const [connected, setConnected] = useState(false)
  const [log, setLog] = useState([])     // [{ text, dir: "in"|"out" }]
  const portRef = useRef(null)
  const readerRef = useRef(null)

  function append(text, dir) {
    setLog(prev => [...prev, { text, dir, ts: Date.now() }])
  }

  const connect = useCallback(async (baudRate = 115200) => {
    if (!("serial" in navigator)) {
      append("Web Serial API not supported in this browser.", "err")
      return
    }
    try {
      const port = await navigator.serial.requestPort()
      await port.open({ baudRate })
      portRef.current = port
      setConnected(true)
      append(`Connected at ${baudRate} baud`, "info")

      // read loop
      const reader = port.readable.getReader()
      readerRef.current = reader
      const decoder = new TextDecoder()
      let buf = ""
      ;(async () => {
        try {
          while (true) {
            const { value, done } = await reader.read()
            if (done) break
            buf += decoder.decode(value, { stream: true })
            const lines = buf.split("\n")
            buf = lines.pop()
            lines.forEach(l => append(l, "in"))
          }
        } catch {
          // port closed
        } finally {
          setConnected(false)
          append("Disconnected", "info")
        }
      })()
    } catch (e) {
      append(`Connect failed: ${e.message}`, "err")
    }
  }, [])

  const disconnect = useCallback(async () => {
    try {
      await readerRef.current?.cancel()
      await portRef.current?.close()
    } catch { /* ignore */ }
    portRef.current = null
    readerRef.current = null
    setConnected(false)
  }, [])

  const send = useCallback(async (data) => {
    if (!portRef.current?.writable) return
    const writer = portRef.current.writable.getWriter()
    try {
      await writer.write(new TextEncoder().encode(data + "\n"))
      append(data, "out")
    } finally {
      writer.releaseLock()
    }
  }, [])

  const clearLog = useCallback(() => setLog([]), [])

  return { connected, log, connect, disconnect, send, clearLog }
}

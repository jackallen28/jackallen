# Allentronics VibeDuino

A browser-based Arduino/ESP32 vibe coding IDE with an AI chat panel.

## Architecture

```
jackallen/
├── client/          # React + Vite + Tailwind frontend (port 5173)
│   └── src/
│       ├── App.jsx                    — IDE grid layout (toolbar | sidebar+main+chat | serial)
│       ├── components/
│       │   ├── Toolbar.jsx            — TODO: compile/upload buttons, board/port selector
│       │   ├── Sidebar.jsx            — TODO: project file tree via GET /api/files
│       │   ├── CodeEditor.jsx         — TODO: Monaco editor with Arduino/C++ syntax
│       │   ├── ChatPanel.jsx          — TODO: AI chat, streams from POST /api/chat
│       │   ├── WiringDiagram.jsx      — TODO: interactive breadboard/pin diagram
│       │   └── SerialMonitor.jsx      — TODO: Web Serial API terminal
│       ├── api/
│       │   ├── claude.js              — TODO: sendMessage() → POST /api/chat
│       │   └── compiler.js            — TODO: compile() and upload() stubs
│       └── hooks/
│           └── useSerial.js           — TODO: Web Serial API connect/disconnect/send
└── server/          # Python FastAPI backend (port 8000)
    ├── main.py                        — app entry point, CORS, route registration
    └── routes/
        ├── chat.py                    — TODO: POST /api/chat → Anthropic API streaming
        ├── compiler.py                — TODO: POST /api/compile, POST /api/upload → arduino-cli
        └── files.py                   — TODO: GET/POST /api/files → project file management
```

## Running locally

**Frontend**
```bash
cd client
npm install
npm run dev
```

**Backend**
```bash
cd server
cp .env.example .env   # fill in ANTHROPIC_API_KEY
pip install fastapi uvicorn python-dotenv
uvicorn main:app --reload --port 8000
```

## TODO stubs (implementation order)

1. `server/routes/chat.py` — wire up Anthropic API to get the chat panel talking
2. `client/src/api/claude.js` — implement `sendMessage()` to POST to `/api/chat`
3. `client/src/components/ChatPanel.jsx` — render conversation and stream tokens
4. `client/src/components/CodeEditor.jsx` — mount Monaco with C++ language
5. `client/src/components/Sidebar.jsx` — file tree from `/api/files`
6. `server/routes/files.py` — project file persistence
7. `server/routes/compiler.py` — arduino-cli integration
8. `client/src/hooks/useSerial.js` — Web Serial API
9. `client/src/components/SerialMonitor.jsx` — terminal UI
10. `client/src/components/WiringDiagram.jsx` — breadboard renderer

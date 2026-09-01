import 'dotenv/config';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { Server as SocketServer } from 'socket.io';
import { Session, PHASES } from './state.js';
import { isLiveBotConfigured } from './bot.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(here, '..', 'public');

const PORT = Number(process.env.PORT || 3000);
const TEACHER_PASSCODE = process.env.TEACHER_PASSCODE || 'letmein';

if (!process.env.TEACHER_PASSCODE) {
  console.warn('[server] TEACHER_PASSCODE is not set. Using the default "letmein" — set one before class.');
}
if (!isLiveBotConfigured()) {
  console.warn('[server] ANTHROPIC_API_KEY is not set. The AI partner will use scripted replies.');
}

const app = express();
const server = http.createServer(app);
const io = new SocketServer(server);
const session = new Session();

app.use(express.static(publicDir));
app.get('/teacher', (_req, res) => res.sendFile(path.join(publicDir, 'teacher.html')));
app.get('/healthz', (_req, res) => res.json({ ok: true, phase: session.phase }));

// --------------------------------------------------------------- broadcasting

const teacherSockets = new Set();

function socketFor(code) {
  const student = session.getByCode(code);
  if (!student || !student.socketId) return null;
  return io.sockets.sockets.get(student.socketId) || null;
}

function pushTeachers() {
  const view = session.teacherView();
  for (const id of teacherSockets) {
    io.sockets.sockets.get(id)?.emit('teacher:state', view);
  }
}

function pushStudent(code) {
  socketFor(code)?.emit('student:state', session.studentView(code));
}

function pushAllStudents() {
  for (const code of session.students.keys()) pushStudent(code);
}

// Coalesce bursts (a whole class joining at once) into one update per tick.
let teacherPushQueued = false;
function queueTeacherPush() {
  if (teacherPushQueued) return;
  teacherPushQueued = true;
  setImmediate(() => {
    teacherPushQueued = false;
    pushTeachers();
  });
}

session.on('roster', queueTeacherPush);
session.on('phase', () => {
  pushAllStudents();
  queueTeacherPush();
});
session.on('message', (code, payload) => socketFor(code)?.emit('chat:message', payload));
session.on('typing', (code, isTyping) => socketFor(code)?.emit('chat:typing', isTyping));

// ------------------------------------------------------------------- sockets

io.on('connection', (socket) => {
  let role = null; // 'student' | 'teacher'

  // -- student ---------------------------------------------------------------

  socket.on('student:join', (payload, ack) => {
    const code = String(payload?.code ?? '').trim();
    const result = session.join(code, socket.id);
    if (!result.ok) return ack?.(result);

    role = 'student';
    socket.data.code = code;
    ack?.({ ok: true });
    pushStudent(code);
  });

  socket.on('chat:send', (payload, ack) => {
    if (role !== 'student') return ack?.({ ok: false, error: 'Not signed in.' });
    ack?.(session.sendMessage(socket.data.code, payload?.text));
  });

  socket.on('chat:typing', (isTyping) => {
    if (role === 'student') session.setTyping(socket.data.code, isTyping);
  });

  socket.on('guess:submit', (payload, ack) => {
    if (role !== 'student') return ack?.({ ok: false, error: 'Not signed in.' });
    const result = session.submitGuess(socket.data.code, payload?.guess);
    ack?.(result);
    pushStudent(socket.data.code);
  });

  socket.on('student:refresh', () => {
    if (role === 'student') pushStudent(socket.data.code);
  });

  // -- teacher ---------------------------------------------------------------

  socket.on('teacher:auth', (payload, ack) => {
    if (String(payload?.passcode ?? '') !== TEACHER_PASSCODE) {
      return ack?.({ ok: false, error: 'Wrong passcode.' });
    }
    role = 'teacher';
    teacherSockets.add(socket.id);
    ack?.({ ok: true, liveBot: isLiveBotConfigured() });
    socket.emit('teacher:state', session.teacherView());
  });

  function teacherOnly(handler) {
    return (payload, ack) => {
      if (role !== 'teacher') return ack?.({ ok: false, error: 'Not authorised.' });
      const result = handler(payload) || { ok: true };
      ack?.(result);
      pushTeachers();
    };
  }

  socket.on('teacher:start', teacherOnly((payload) =>
    session.start({
      durationSec: Number(payload?.durationSec) || 120,
      aiRatio: Number(payload?.aiRatio ?? 0.5),
    })
  ));

  socket.on('teacher:end', teacherOnly(() => session.endRound()));
  socket.on('teacher:results', teacherOnly(() => session.showResults()));
  socket.on('teacher:reset', teacherOnly((payload) =>
    session.reset({ keepStudents: payload?.keepStudents !== false })
  ));
  socket.on('teacher:remove', teacherOnly((payload) => {
    const code = String(payload?.code ?? '');
    socketFor(code)?.emit('student:kicked');
    return { ok: session.remove(code) };
  }));
  socket.on('teacher:transcripts', (_payload, ack) => {
    if (role !== 'teacher') return ack?.({ ok: false, error: 'Not authorised.' });
    ack?.({ ok: true, transcripts: session.transcripts() });
  });

  // -- teardown --------------------------------------------------------------

  socket.on('disconnect', () => {
    teacherSockets.delete(socket.id);
    if (role === 'student') session.disconnect(socket.id);
  });
});

// A ticking clock so late joiners and reconnects see an accurate countdown.
setInterval(() => {
  if (session.phase === PHASES.ACTIVE) queueTeacherPush();
}, 1000);

server.listen(PORT, () => {
  console.log(`[server] Human or Not — classroom edition on http://localhost:${PORT}`);
  console.log(`[server] Students: http://localhost:${PORT}/   Teacher: http://localhost:${PORT}/teacher`);
});

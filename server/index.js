import 'dotenv/config';
import http from 'node:http';
import os from 'node:os';
import dgram from 'node:dgram';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { Server as SocketServer } from 'socket.io';
import { Session, PHASES } from './state.js';
import { isLiveBotConfigured, defaultModel } from './bot.js';
import { MODEL_CATALOG } from './models.js';
import { buildCsvReport, buildHtmlReport, reportFilename } from './report.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(here, '..', 'public');

const PORT = Number(process.env.PORT || 3000);
const TEACHER_PASSCODE = process.env.TEACHER_PASSCODE || 'letmein';

if (!process.env.TEACHER_PASSCODE) {
  console.warn('[server] TEACHER_PASSCODE is not set. Using the default "letmein" — set one before class.');
}
if (!isLiveBotConfigured()) {
  console.warn('[server] ANTHROPIC_API_KEY is not set. The AI partner will use scripted replies.');
} else {
  console.log(`[server] Default AI partner model: ${defaultModel}`);
}

// Adapters that exist on a machine but are not how other devices reach it.
// Windows in particular ships several of these (WSL, Hyper-V, VirtualBox).
const VIRTUAL_ADAPTER = /wsl|hyper-?v|vethernet|virtualbox|vmware|docker|loopback|utun|awdl|llw|bridge|tailscale|zerotier/i;

/**
 * Every IPv4 address this machine can be reached on from the local network,
 * with its adapter name. `localhost` only works on the host itself, so one of
 * these is what students need.
 */
function lanAddresses() {
  const found = [];
  for (const [name, addresses] of Object.entries(os.networkInterfaces())) {
    for (const address of addresses || []) {
      if (address.family === 'IPv4' && !address.internal) {
        found.push({ name, address: address.address, virtual: VIRTUAL_ADAPTER.test(name) });
      }
    }
  }
  // Real adapters first, so the most useful address is the one they read.
  return found.sort((a, b) => Number(a.virtual) - Number(b.virtual));
}

/**
 * Ask the OS which local address it would use to reach the outside world.
 * Opening a UDP socket sends no packets — it just resolves the route — and it
 * reliably picks the real Wi-Fi or Ethernet adapter out of a crowded list.
 */
function primaryAddress() {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      try { socket.close(); } catch { /* already closed */ }
      resolve(value);
    };
    const socket = dgram.createSocket('udp4');
    socket.on('error', () => finish(null));
    setTimeout(() => finish(null), 500);
    try {
      socket.connect(53, '8.8.8.8', () => {
        try { finish(socket.address().address); } catch { finish(null); }
      });
    } catch { finish(null); }
  });
}

/** The addresses to advertise, best guess first. */
async function joinAddresses() {
  const all = lanAddresses();
  const primary = await primaryAddress();
  if (!primary) return all;
  const match = all.find((entry) => entry.address === primary);
  if (!match) return all;
  return [match, ...all.filter((entry) => entry !== match)];
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
    ack?.({
      ok: true,
      liveBot: isLiveBotConfigured(),
      models: MODEL_CATALOG,
      joinUrls: cachedJoinUrls,
    });
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
      // Validated against the server-side catalog inside start().
      modelMix: payload?.modelMix,
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
  socket.on('teacher:report', (_payload, ack) => {
    if (role !== 'teacher') return ack?.({ ok: false, error: 'Not authorised.' });
    if (session.roundNumber === 0) return ack?.({ ok: false, error: 'No round has run yet.' });
    const data = session.reportData();
    ack?.({
      ok: true,
      html: buildHtmlReport(data),
      csv: buildCsvReport(data),
      htmlName: reportFilename(data, 'html'),
      csvName: reportFilename(data, 'csv'),
    });
  });

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

let cachedJoinUrls = [];

server.listen(PORT, async () => {
  console.log('[server] Human or Not — classroom edition');
  console.log(`[server] Teacher console (this machine only) ... http://localhost:${PORT}/teacher`);

  const addresses = await joinAddresses();
  cachedJoinUrls = addresses.map((entry) => `http://${entry.address}:${PORT}`);

  if (addresses.length === 0) {
    console.log('[server] No network address found — other devices will not be able to connect.');
    return;
  }

  const [best, ...rest] = addresses;
  console.log('[server]');
  console.log(`[server] STUDENTS JOIN AT ...... http://${best.address}:${PORT}   (adapter: ${best.name})`);
  if (rest.length) {
    console.log('[server] If that one does not work, try:');
    for (const entry of rest) {
      const note = entry.virtual ? '  — virtual adapter, unlikely to work' : '';
      console.log(`[server]   http://${entry.address}:${PORT}   (${entry.name})${note}`);
    }
  }
  console.log('[server]');
});

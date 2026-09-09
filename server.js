/**
 * Mind Feud — server.
 *
 * One teacher device runs this. It serves:
 *   /       the host board (project this)
 *   /play   the team console (one per team computer)
 *
 * State lives here, not in the browsers, so a team refreshing their tab mid
 * round loses nothing.
 */

import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { WebSocketServer } from 'ws';

import { Game, TEAMS } from './src/game.js';
import { judgeBoardGuess, judgeRapidGuess, aiAvailable } from './src/judge.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3000);

/**
 * Public deployments (Render) versus the teacher's own laptop.
 *
 * On a laptop on the school network, anyone who can reach the server is
 * already in the room, so no passwords: the teacher opens the board and the
 * two team machines join. On a public URL that assumption is gone — an
 * unguarded host board hands out every answer on the internet — so both gates
 * below switch themselves on automatically when a public host is detected.
 */
const IS_PUBLIC = Boolean(process.env.RENDER || process.env.PUBLIC_DEPLOY);
const EXTERNAL_URL = (process.env.RENDER_EXTERNAL_URL || process.env.PUBLIC_URL || '')
  .replace(/\/$/, '');

// Guards the host board (the screen that shows unrevealed answers).
const HOST_TOKEN = process.env.HOST_TOKEN || (IS_PUBLIC ? randomToken(24) : '');

// A short code the class types to join, so a stray visitor cannot buzz in.
// Shown in huge type on the lobby screen — the teacher just reads it out.
const JOIN_CODE = (process.env.JOIN_CODE || (IS_PUBLIC ? randomCode(4) : '')).toUpperCase();

function randomToken(n) {
  const alphabet = 'abcdefghijkmnopqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: n }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join('');
}
// No O/0, I/1 or similar — this gets read off a projector and typed by teenagers.
function randomCode(n) {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: n }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join('');
}

const app = express();
app.set('trust proxy', 1); // Render terminates TLS in front of us
app.use(express.static(path.join(here, 'public')));
app.get('/', (_req, res) => res.sendFile(path.join(here, 'public', 'host.html')));
app.get('/play', (_req, res) => res.sendFile(path.join(here, 'public', 'play.html')));
app.get('/health', (_req, res) => res.json({ ok: true, ai: aiAvailable() }));

/**
 * What the two screens need before anyone has authenticated.
 * Deliberately does NOT include the join code or the host token.
 */
app.get('/api/config', (req, res) => {
  res.json({
    playUrls: playUrls(req),
    joinRequired: Boolean(JOIN_CODE),
    hostTokenRequired: Boolean(HOST_TOKEN),
    ai: aiAvailable(),
  });
});

/**
 * Where the class should point their browsers. On a laptop that is the LAN
 * address (location.hostname would be "localhost", which no student machine
 * can reach); on Render it is the public URL.
 */
function playUrls(req) {
  if (EXTERNAL_URL) return [`${EXTERNAL_URL}/play`];
  if (IS_PUBLIC && req) return [`${req.protocol}://${req.get('host')}/play`];
  return lanAddresses().map((a) => `http://${a}:${PORT}/play`);
}

const server = http.createServer(app);
const wss = new WebSocketServer({ server });
const game = new Game();

/** @type {Set<{ws:import('ws').WebSocket, role:string, team:string|null, name:string}>} */
const clients = new Set();

function send(ws, payload) {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(payload));
}

function broadcastState(fx = null) {
  for (const c of clients) {
    send(c.ws, {
      type: 'state',
      state: game.snapshot(c.role === 'host' ? 'host' : c.team),
      fx,
      you: { role: c.role, team: c.team, name: c.name },
      roster: roster(),
      // Only the authenticated host learns the code, so the lobby screen can
      // display it. It never travels to a player socket.
      joinCode: c.role === 'host' ? JOIN_CODE : undefined,
    });
  }
}

function roster() {
  const out = { host: 0, A: [], B: [] };
  for (const c of clients) {
    if (c.role === 'host') out.host += 1;
    else if (c.team) out[c.team].push(c.name);
  }
  return out;
}

function toast(ws, text, tone = 'info') {
  send(ws, { type: 'toast', text, tone });
}

wss.on('connection', (ws) => {
  // Nothing is granted until the join handshake succeeds.
  const client = { ws, role: 'pending', team: null, name: 'Player' };
  clients.add(client);

  ws.on('message', async (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    try {
      await handle(client, msg);
    } catch (err) {
      console.error('[ws] handler error:', err);
      toast(ws, 'Something went wrong — the host can override.', 'error');
    }
  });

  ws.on('close', () => {
    clients.delete(client);
    broadcastState();
  });
});

async function handle(client, msg) {
  const { ws } = client;

  switch (msg.type) {
    case 'join': {
      if (msg.role === 'host') {
        if (HOST_TOKEN && msg.token !== HOST_TOKEN) {
          return send(ws, { type: 'denied', as: 'host', reason: 'Wrong or missing host key.' });
        }
        client.role = 'host';
        client.team = null;
        client.name = 'Host';
      } else {
        if (JOIN_CODE && String(msg.code || '').trim().toUpperCase() !== JOIN_CODE) {
          return send(ws, { type: 'denied', as: 'player', reason: 'Wrong game code.' });
        }
        client.role = 'player';
        client.team = TEAMS.includes(msg.team) ? msg.team : 'A';
        client.name = String(msg.name || '').slice(0, 20) || `${client.team} player`;
      }
      send(ws, { type: 'accepted', role: client.role });
      return broadcastState();
    }

    case 'buzz': {
      if (client.role !== 'player' || !client.team) return;
      const res = game.buzz(client.team, client.name);
      if (res.error) return toast(ws, res.error, 'warn');
      return broadcastState(res.fx || 'buzz');
    }

    case 'answer': {
      if (client.role !== 'player' || !client.team) return;
      const text = String(msg.text || '').trim();
      if (!text) return;
      return submitAnswer(client, text);
    }

    case 'host': {
      if (client.role !== 'host') return toast(ws, 'Host only.', 'warn');
      return hostAction(ws, msg);
    }

    default:
      return;
  }
}

async function submitAnswer(client, text) {
  const { ws, team } = client;

  if (game.phase === 'final' || game.phase === 'spoiler') {
    const question = game.currentRapid();
    if (!question) return toast(ws, 'No question up.', 'warn');
    const verdict = await judgeRapidGuess(text, question);
    const res = game.applyRapidGuess(team, text, verdict.correct);
    if (res.error) return toast(ws, res.error, 'warn');
    return broadcastState(res.fx);
  }

  if (game.phase !== 'answering') return toast(ws, 'Wait for the buzz.', 'warn');
  if (team !== game.control) return toast(ws, 'Not your turn.', 'warn');

  const question = game.currentQuestion();
  if (!question) return toast(ws, 'No question on the board.', 'warn');

  // Freeze the board while judging so a fast second guess cannot jump the queue.
  const judging = game.phase;
  const verdict = await judgeBoardGuess(text, question.answers, question.nearMiss || []);
  if (game.phase !== judging || game.control !== team) {
    return toast(ws, 'Too slow — the board moved on.', 'warn');
  }

  const res = game.applyGuess(team, text, verdict);
  if (res.error) return toast(ws, res.error, 'warn');
  return broadcastState(res.fx);
}

function hostAction(ws, msg) {
  const a = msg.action;
  let res = { ok: true };
  let fx = null;

  switch (a) {
    case 'startRound':
      res = game.startRound(typeof msg.index === 'number' ? msg.index : undefined);
      fx = 'roundStart';
      break;
    case 'openQuestion':
      res = game.openQuestion(msg.questionId);
      fx = 'questionUp';
      break;
    case 'reopenBuzzers':
      if (game.board && (game.phase === 'answering' || game.phase === 'buzzing')) {
        game.phase = 'buzzing';
        game.control = null;
        game.buzzedBy = null;
        game.buzzLocked = false;
        game.note('buzzersReopened');
        game.touch();
        fx = 'questionUp';
      } else {
        res = { error: 'No live question.' };
      }
      break;
    case 'giveControl':
      if (game.board && TEAMS.includes(msg.team)) {
        game.control = msg.team;
        game.buzzedBy = msg.team;
        game.buzzLocked = true;
        game.phase = 'answering';
        game.note('buzz', { team: msg.team, player: 'host' });
        game.touch();
        fx = 'buzz';
      } else {
        res = { error: 'No live question.' };
      }
      break;
    case 'reveal':
      res = game.hostReveal(Number(msg.index), TEAMS.includes(msg.team) ? msg.team : null);
      fx = res.fx;
      break;
    case 'endRound':
      res = game.endRoundBoard('host');
      fx = 'roundEnd';
      break;
    case 'startFinal':
      res = game.startFinal(TEAMS.includes(msg.team) ? msg.team : undefined);
      break;
    case 'startFinalClock':
      res = game.startFinalClock();
      fx = 'go';
      break;
    case 'startSpoilerClock':
      res = game.startSpoilerClock();
      fx = 'go';
      break;
    case 'skipRapid':
      if (game.phase === 'final' || game.phase === 'spoiler') {
        const stage = game.phase === 'spoiler' ? game.spoiler : game.final;
        res = game.finalPass(stage.team);
        fx = 'pass';
      } else {
        res = { error: 'Not in the final.' };
      }
      break;
    case 'markRapid': // host overrules the judge on a rapid-fire answer
      if (game.phase === 'final' || game.phase === 'spoiler') {
        const stage = game.phase === 'spoiler' ? game.spoiler : game.final;
        res = game.applyRapidGuess(stage.team, '(host)', Boolean(msg.correct));
        fx = res.fx;
      } else {
        res = { error: 'Not in the final.' };
      }
      break;
    case 'endRapid':
      game.endRapid();
      fx = 'roundEnd';
      break;
    case 'adjust':
      res = game.adjustScore(msg.team, Number(msg.delta) || 0);
      break;
    case 'teamName':
      res = game.setTeamName(msg.team, msg.name);
      break;
    case 'setting':
      if (msg.key in game.settings) {
        game.settings[msg.key] = msg.value;
        game.touch();
      }
      break;
    case 'finish':
      game.finish();
      fx = 'gameOver';
      break;
    case 'reset':
      game.reset();
      fx = 'roundStart';
      break;
    default:
      res = { error: `Unknown action: ${a}` };
  }

  if (res && res.error) return toast(ws, res.error, 'warn');
  return broadcastState(fx);
}

/* The rapid-fire clock. One interval for the whole game; it only does work
 * while a final-round stage is actually running. */
setInterval(() => {
  if (game.tickClock()) broadcastState();
}, 1000);

/* ------------------------------------------------------------------ */

function lanAddresses() {
  const out = [];
  for (const entries of Object.values(os.networkInterfaces())) {
    for (const e of entries || []) {
      if (e.family === 'IPv4' && !e.internal) out.push(e.address);
    }
  }
  return out;
}

server.listen(PORT, '0.0.0.0', () => {
  const urls = playUrls(null);
  console.log('');
  console.log('  ┌─────────────────────────────────────────────┐');
  console.log('  │   MIND FEUD — "Where is My Mind?"           │');
  console.log('  └─────────────────────────────────────────────┘');
  console.log('');

  if (IS_PUBLIC) {
    const base = EXTERNAL_URL || `(this service's URL)`;
    console.log(`  Public deployment on port ${PORT}.`);
    console.log('');
    console.log(`  Host board (project this):  ${base}/?token=${HOST_TOKEN}`);
    console.log(`  Team computers:             ${base}/play`);
    console.log('');
    console.log(`  GAME CODE for the class:    ${JOIN_CODE}`);
    console.log('  (also shown in large type on the lobby screen)');
    if (!process.env.HOST_TOKEN) {
      console.log('');
      console.log('  NOTE: HOST_TOKEN was not set, so one was generated for this boot and');
      console.log('  will change on the next restart. Set HOST_TOKEN in the dashboard to');
      console.log('  keep a stable host link you can bookmark.');
    }
  } else {
    console.log(`  Host board (project this):  http://localhost:${PORT}/`);
    if (urls.length) {
      console.log('');
      console.log('  Team computers open ONE of these:');
      for (const u of urls) console.log(`      ${u}`);
    } else {
      console.log('\n  No network interface found — use single-device mode on the host screen.');
    }
    if (JOIN_CODE) console.log(`\n  Game code: ${JOIN_CODE}`);
  }

  console.log('');
  console.log(aiAvailable()
    ? '  Answer judging: local matcher + Claude for the odd phrasings.'
    : '  Answer judging: local matcher only (no ANTHROPIC_API_KEY set). Fine — the\n'
      + '  question bank has aliases for the expected wordings, and the host can\n'
      + '  override any call with one click.');
  console.log('');
});

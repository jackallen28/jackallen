/**
 * Mind Jeopardy — server.
 *
 * Three screens, three audiences:
 *   /        the host's laptop — step-by-step control, and every answer
 *   /board   the projector — the grid, the scores, the clue, the clock
 *   /play    a team computer — buzzer, answer box, wager box
 *
 * State lives here, not in the browsers, so a team refreshing mid-clue loses
 * nothing and the projector window can be closed and reopened at will.
 */

import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { WebSocketServer } from 'ws';

import { Game } from './src/game.js';
import { judgeAnswer, aiAvailable } from './src/judge.js';
import { CATEGORIES, FINAL, findClue } from './src/questions.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3000);

/**
 * A laptop on the school network versus a public URL.
 *
 * On a laptop, anyone who can reach the server is already in the room, so
 * there are no passwords. On a public URL that assumption is gone — an
 * unguarded host screen hands out every answer — so both gates below switch
 * themselves on when a public host is detected.
 */
const IS_PUBLIC = Boolean(process.env.RENDER || process.env.PUBLIC_DEPLOY);
const EXTERNAL_URL = (process.env.RENDER_EXTERNAL_URL || process.env.PUBLIC_URL || '')
  .replace(/\/$/, '');

// Guards the host laptop screen AND the projector, both of which the teacher
// opens themselves. Students only ever need /play.
const HOST_TOKEN = process.env.HOST_TOKEN || (IS_PUBLIC ? randomToken(24) : '');
// The short code the class types to join. Shown large on the projector.
const JOIN_CODE = (process.env.JOIN_CODE || (IS_PUBLIC ? randomCode(4) : '')).toUpperCase();

function randomToken(n) {
  const a = 'abcdefghijkmnopqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: n }, () => a[Math.floor(Math.random() * a.length)]).join('');
}
// No O/0 or I/1 — this gets read off a projector and typed by teenagers.
function randomCode(n) {
  const a = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: n }, () => a[Math.floor(Math.random() * a.length)]).join('');
}

const app = express();
app.set('trust proxy', 1); // Render terminates TLS in front of us
app.use(express.static(path.join(here, 'public')));
app.get('/', (_req, res) => res.sendFile(path.join(here, 'public', 'host.html')));
app.get('/board', (_req, res) => res.sendFile(path.join(here, 'public', 'board.html')));
app.get('/play', (_req, res) => res.sendFile(path.join(here, 'public', 'play.html')));
app.get('/health', (_req, res) => res.json({ ok: true, ai: aiAvailable() }));

/** What the screens need before anyone has authenticated. Leaks neither code. */
app.get('/api/config', (req, res) => {
  res.json({
    playUrls: playUrls(req),
    joinRequired: Boolean(JOIN_CODE),
    hostTokenRequired: Boolean(HOST_TOKEN),
    ai: aiAvailable(),
    // Team names are on the projector anyway, and the join screen needs them
    // before a student has entered the code.
    teams: game.teams.map((t) => ({ id: t.id, name: t.name })),
    phase: game.phase,
  });
});

function playUrls(req) {
  if (EXTERNAL_URL) return [`${EXTERNAL_URL}/play`];
  if (IS_PUBLIC && req) return [`${req.protocol}://${req.get('host')}/play`];
  return lanAddresses().map((a) => `http://${a}:${PORT}/play`);
}

const server = http.createServer(app);
const wss = new WebSocketServer({ server });
const game = new Game();

/** @type {Set<{ws:any, role:string, teamId:string|null}>} */
const clients = new Set();

function send(ws, payload) {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(payload));
}

function audienceFor(client) {
  if (client.role === 'host') return 'host';
  if (client.role === 'board') return 'board';
  return client.teamId || 'board';
}

function broadcast(fx = null) {
  for (const c of clients) {
    // A socket that has not passed the join handshake gets nothing at all —
    // otherwise any disconnect elsewhere would push state to it.
    if (c.role === 'pending') continue;
    send(c.ws, {
      type: 'state',
      state: game.snapshot(audienceFor(c)),
      fx,
      you: { role: c.role, teamId: c.teamId },
      roster: roster(),
      // Only the authenticated host learns the join code, so the projector can
      // display it. It never travels to a player socket.
      joinCode: c.role === 'host' || c.role === 'board' ? JOIN_CODE : undefined,
    });
  }
}

function roster() {
  const out = { host: 0, board: 0, teams: {} };
  for (const c of clients) {
    if (c.role === 'host') out.host += 1;
    else if (c.role === 'board') out.board += 1;
    else if (c.teamId) out.teams[c.teamId] = (out.teams[c.teamId] || 0) + 1;
  }
  return out;
}

function toast(ws, text, tone = 'info') {
  send(ws, { type: 'toast', text, tone });
}

wss.on('connection', (ws) => {
  // Nothing is granted until the join handshake succeeds.
  const client = { ws, role: 'pending', teamId: null };
  clients.add(client);

  ws.on('message', async (raw) => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return; }
    try {
      await handle(client, msg);
    } catch (err) {
      console.error('[ws] handler error:', err);
      toast(ws, 'Something went wrong — the host can override.', 'error');
    }
  });

  ws.on('close', () => { clients.delete(client); broadcast(); });
});

async function handle(client, msg) {
  const { ws } = client;

  switch (msg.type) {
    case 'join': {
      // The host laptop and the projector both show more than a student should
      // see, so they share the host key.
      if (msg.role === 'host' || msg.role === 'board') {
        if (HOST_TOKEN && msg.token !== HOST_TOKEN) {
          return send(ws, { type: 'denied', as: msg.role, reason: 'Wrong or missing host key.' });
        }
        client.role = msg.role;
        client.teamId = null;
      } else {
        if (JOIN_CODE && String(msg.code || '').trim().toUpperCase() !== JOIN_CODE) {
          return send(ws, { type: 'denied', as: 'player', reason: 'Wrong game code.' });
        }
        client.role = 'player';
        client.teamId = msg.teamId || null;
      }
      send(ws, { type: 'accepted', role: client.role, teamId: client.teamId });
      return broadcast();
    }

    case 'pickTeam': {
      if (client.role !== 'player') return;
      if (!game.team(msg.teamId)) return toast(ws, 'That team no longer exists.', 'warn');
      client.teamId = msg.teamId;
      send(ws, { type: 'accepted', role: 'player', teamId: client.teamId });
      return broadcast();
    }

    case 'buzz': {
      if (client.role !== 'player' || !client.teamId) return;
      const res = game.buzz(client.teamId);
      if (res.error) return toast(ws, res.error, 'warn');
      return broadcast(res.fx);
    }

    case 'answer': {
      if (client.role !== 'player' || !client.teamId) return;
      return submitAnswer(client, String(msg.text || '').trim());
    }

    case 'wager': {
      if (client.role !== 'player' || !client.teamId) return;
      const res = game.submitWager(client.teamId, msg.amount);
      if (res.error) return toast(ws, res.error, 'warn');
      return broadcast(res.fx);
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
  const { ws, teamId } = client;
  if (!text) return;

  /* Final Jeopardy: everyone writes at once, and the verdict is recorded but
   * not applied — the host reveals team by team afterwards. */
  if (game.phase === 'finalClue') {
    const res = game.submitFinalAnswer(teamId, text);
    if (res.error) return toast(ws, res.error, 'warn');
    broadcast(res.fx);
    const verdict = await judgeAnswer(text, FINAL);
    game.recordFinalVerdict(teamId, verdict);
    return broadcast();
  }

  if (game.phase !== 'answering') return toast(ws, 'Wait for the buzz.', 'warn');
  if (game.active?.buzzedBy !== teamId) return toast(ws, 'Not your clue.', 'warn');

  const found = findClue(game.active.categoryIndex, game.active.clueIndex);
  if (!found) return toast(ws, 'No clue in play.', 'warn');

  // Remember which clue we are judging, so a slow verdict cannot land on a
  // later one if the host moves the game on while Claude is thinking.
  const { categoryIndex, clueIndex } = game.active;
  const verdict = await judgeAnswer(text, found.clue);
  const stillOurs = game.phase === 'answering'
    && game.active?.buzzedBy === teamId
    && game.active.categoryIndex === categoryIndex
    && game.active.clueIndex === clueIndex;
  if (!stillOurs) return toast(ws, 'Too slow — the board moved on.', 'warn');

  const res = game.resolveAnswer(verdict.correct, text, verdict.source);
  if (res.error) return toast(ws, res.error, 'warn');
  return broadcast(res.fx);
}

function hostAction(ws, msg) {
  let res = { ok: true };
  let fx = null;

  switch (msg.action) {
    case 'addTeam': res = game.addTeam(msg.name); break;
    case 'removeTeam': res = game.removeTeam(msg.teamId); break;
    case 'renameTeam': res = game.renameTeam(msg.teamId, msg.name); break;
    case 'startGame': res = game.startGame(); fx = res.fx; break;

    case 'pickClue': res = game.pickClue(Number(msg.categoryIndex), Number(msg.clueIndex)); fx = res.fx; break;
    case 'openBuzzers': res = game.openBuzzers(); fx = res.fx; break;
    case 'giveClue': // host awards the buzz by hand, e.g. a team shouted first
      res = game.phase === 'open' ? game.buzz(msg.teamId) : { error: 'Buzzers are not live.' };
      fx = res.fx;
      break;
    case 'mark': res = game.resolveAnswer(Boolean(msg.correct), '(host)', 'host'); fx = res.fx; break;
    case 'reveal': res = game.revealAnswer('host'); fx = res.fx; break;
    case 'backToBoard': res = game.backToBoard(); break;

    case 'startFinal': res = game.startFinal(); fx = res.fx; break;
    case 'openWagers': res = game.openWagers(); fx = res.fx; break;
    case 'openFinalClue': res = game.openFinalClue(); fx = res.fx; break;
    case 'closeFinalWriting': res = game.closeFinalWriting(); fx = res.fx; break;
    case 'revealFinalTeam':
      res = game.revealFinalTeam(msg.teamId,
        msg.correct === undefined ? null : Boolean(msg.correct));
      fx = res.fx;
      break;
    case 'setWager': res = game.submitWager(msg.teamId, msg.amount); break;

    case 'adjust': res = game.adjustScore(msg.teamId, Number(msg.delta) || 0); break;
    case 'setPicker': res = game.setPicker(msg.teamId); break;
    case 'setting':
      if (msg.key in game.settings) { game.settings[msg.key] = msg.value; game.touch(); }
      break;
    case 'finish': game.finish(); fx = 'gameOver'; break;
    case 'reset': game.reset(); break;
    default: res = { error: `Unknown action: ${msg.action}` };
  }

  if (res && res.error) return toast(ws, res.error, 'warn');
  return broadcast(fx);
}

/* One clock for the whole game; it only does work while something is running. */
setInterval(() => { if (game.tick()) broadcast(); }, 1000);

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
  console.log('  │   MIND JEOPARDY — "Where is My Mind?"       │');
  console.log('  └─────────────────────────────────────────────┘');
  console.log('');
  console.log(`  ${CATEGORIES.length} categories · ${CATEGORIES.length * 5} clues · Final Jeopardy`);
  console.log('');

  if (IS_PUBLIC) {
    const base = EXTERNAL_URL || "(this service's URL)";
    console.log(`  Public deployment on port ${PORT}.`);
    console.log('');
    console.log(`  Host laptop:      ${base}/?token=${HOST_TOKEN}`);
    console.log(`  Projector:        open it with one click from the host screen`);
    console.log(`  Team computers:   ${base}/play`);
    console.log('');
    console.log(`  GAME CODE:        ${JOIN_CODE}`);
    if (!process.env.HOST_TOKEN) {
      console.log('');
      console.log('  NOTE: HOST_TOKEN was not set, so one was generated for this boot and');
      console.log('  will change on restart. Set it in the dashboard for a stable link.');
    }
  } else {
    console.log(`  Host laptop (your screen):   http://localhost:${PORT}/`);
    console.log(`  Projector (second window):   opened from the host screen`);
    if (urls.length) {
      console.log('');
      console.log('  Team computers open ONE of these:');
      for (const u of urls) console.log(`      ${u}`);
    }
    if (JOIN_CODE) console.log(`\n  Game code: ${JOIN_CODE}`);
  }

  console.log('');
  console.log(aiAvailable()
    ? '  Answer judging: local matcher + Claude for the odd phrasings.'
    : '  Answer judging: local matcher only (no ANTHROPIC_API_KEY set). Fine — the\n'
      + '  clue bank has aliases for the expected wordings, and every ruling has a\n'
      + '  one-click override on the host screen.');
  console.log('');
});

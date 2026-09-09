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
const HOST_TOKEN = process.env.HOST_TOKEN || ''; // optional, keeps students off the host view

const app = express();
app.use(express.static(path.join(here, 'public')));
app.get('/', (_req, res) => res.sendFile(path.join(here, 'public', 'host.html')));
app.get('/play', (_req, res) => res.sendFile(path.join(here, 'public', 'play.html')));
app.get('/health', (_req, res) => res.json({ ok: true, ai: aiAvailable() }));
// The host screen shows these to the class — location.hostname on the teacher's
// own machine is "localhost", which no student computer can reach.
app.get('/api/join-urls', (_req, res) =>
  res.json({ urls: lanAddresses().map((a) => `http://${a}:${PORT}/play`) }));

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
  const client = { ws, role: 'player', team: null, name: 'Player' };
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
          return toast(ws, 'Wrong host password.', 'error');
        }
        client.role = 'host';
        client.team = null;
        client.name = 'Host';
      } else {
        client.role = 'player';
        client.team = TEAMS.includes(msg.team) ? msg.team : 'A';
        client.name = String(msg.name || '').slice(0, 20) || `${client.team} player`;
      }
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

server.listen(PORT, () => {
  const addrs = lanAddresses();
  console.log('');
  console.log('  ┌─────────────────────────────────────────────┐');
  console.log('  │   MIND FEUD — "Where is My Mind?"           │');
  console.log('  └─────────────────────────────────────────────┘');
  console.log('');
  console.log(`  Host board (project this):  http://localhost:${PORT}/`);
  if (addrs.length) {
    console.log('');
    console.log('  Team computers open ONE of these:');
    for (const a of addrs) console.log(`      http://${a}:${PORT}/play`);
  } else {
    console.log('\n  No network interface found — use single-device mode on the host screen.');
  }
  console.log('');
  console.log(aiAvailable()
    ? '  Answer judging: local matcher + Claude for the odd phrasings.'
    : '  Answer judging: local matcher only (no ANTHROPIC_API_KEY set). Fine — the\n'
      + '  question bank has aliases for the expected wordings, and the host can\n'
      + '  override any call with one click.');
  console.log('');
});

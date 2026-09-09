/**
 * Public-deployment checks.
 *
 * Boots the server the way Render does — RENDER set, a host token and a join
 * code in the environment — and proves the two gates actually hold. These are
 * the checks that matter once the game is on a URL anyone can find.
 *
 * Run: node test/deploy.test.js
 */

import { spawn } from 'node:child_process';
import WebSocket from 'ws';

const PORT = 3198;
const HOST_TOKEN = 'secret-host-key';
const JOIN_CODE = 'MIND';
let pass = 0, fail = 0;
const failures = [];

function check(ok, label, detail = '') {
  if (ok) pass++; else { fail++; failures.push(`${label}${detail ? `  (${detail})` : ''}`); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn(process.execPath, ['server.js'], {
  env: {
    ...process.env,
    PORT: String(PORT),
    RENDER: 'true',
    RENDER_EXTERNAL_URL: 'https://mind-feud.onrender.com',
    HOST_TOKEN,
    JOIN_CODE,
    ANTHROPIC_API_KEY: '',
  },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let banner = '';
server.stdout.on('data', (d) => { banner += d.toString(); });
server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));

for (let i = 0; i < 100; i++) {
  try { if ((await fetch(`http://127.0.0.1:${PORT}/health`)).ok) break; } catch {}
  await sleep(100);
}

/* ---- the public config endpoint leaks nothing ---- */
const cfg = await (await fetch(`http://127.0.0.1:${PORT}/api/config`)).json();
check(cfg.joinRequired === true, 'config says a join code is required');
check(cfg.hostTokenRequired === true, 'config says a host token is required');
const raw = JSON.stringify(cfg);
check(!raw.includes(JOIN_CODE), 'the join code is NOT in the public config', raw);
check(!raw.includes(HOST_TOKEN), 'the host token is NOT in the public config', raw);
check(cfg.playUrls[0] === 'https://mind-feud.onrender.com/play',
  'the public URL is advertised, not a LAN address', cfg.playUrls[0]);

/* ---- a client that tries each gate ---- */
function open(joinMsg) {
  return new Promise((resolve) => {
    const ws = new WebSocket(`ws://127.0.0.1:${PORT}`);
    const got = { messages: [], state: null, joinCode: undefined };
    ws.on('open', () => ws.send(JSON.stringify(joinMsg)));
    ws.on('message', (raw) => {
      const m = JSON.parse(raw.toString());
      got.messages.push(m.type);
      if (m.type === 'state') { got.state = m.state; got.joinCode = m.joinCode; }
    });
    setTimeout(() => resolve({ ...got, ws }), 350);
  });
}

/* Host with no token — refused, and told nothing. */
const noToken = await open({ type: 'join', role: 'host' });
check(noToken.messages.includes('denied'), 'host with no token is denied');
check(!noToken.messages.includes('accepted'), 'host with no token is not accepted');
check(noToken.state === null, 'a denied host receives no game state');

/* Host with the wrong token — same. */
const badToken = await open({ type: 'join', role: 'host', token: 'guess' });
check(badToken.messages.includes('denied'), 'host with a wrong token is denied');

/* Host with the right token — in, and told the code for the lobby screen. */
const goodHost = await open({ type: 'join', role: 'host', token: HOST_TOKEN });
check(goodHost.messages.includes('accepted'), 'host with the right token is accepted');
check(goodHost.joinCode === JOIN_CODE, 'the authenticated host learns the game code', String(goodHost.joinCode));

/* Player with no code — refused. */
const noCode = await open({ type: 'join', role: 'player', team: 'A', name: 'Sneak' });
check(noCode.messages.includes('denied'), 'player with no code is denied');
check(noCode.joinCode === undefined, 'a denied player is never sent the code');

/* Player with the wrong code — refused. */
const badCode = await open({ type: 'join', role: 'player', team: 'A', name: 'Sneak', code: 'XXXX' });
check(badCode.messages.includes('denied'), 'player with a wrong code is denied');

/* Player with the right code, lowercase — in (students will type it lowercase). */
const goodPlayer = await open({ type: 'join', role: 'player', team: 'A', name: 'Ana', code: 'mind' });
check(goodPlayer.messages.includes('accepted'), 'player with the code is accepted, case-insensitively');
check(goodPlayer.joinCode === undefined, 'an accepted PLAYER is still never sent the code');

/* ---- a refused socket cannot drive the game ---- */
const host = new WebSocket(`ws://127.0.0.1:${PORT}`);
await new Promise((r) => host.on('open', r));
let hostState = null;
host.on('message', (raw) => {
  const m = JSON.parse(raw.toString());
  if (m.type === 'state') hostState = m.state;
});
host.send(JSON.stringify({ type: 'join', role: 'host', token: HOST_TOKEN }));
await sleep(200);
host.send(JSON.stringify({ type: 'host', action: 'startRound', index: 0 }));
host.send(JSON.stringify({ type: 'host', action: 'openQuestion', questionId: 'r1q2' }));
await sleep(250);
check(hostState?.phase === 'buzzing', 'the real host can start a question', hostState?.phase);

// The denied sockets are still open. They must be inert.
noToken.ws.send(JSON.stringify({ type: 'host', action: 'reset' }));
noCode.ws.send(JSON.stringify({ type: 'buzz' }));
badCode.ws.send(JSON.stringify({ type: 'answer', text: 'closure' }));
await sleep(300);
check(hostState.phase === 'buzzing', 'a denied socket cannot reset the game or buzz', hostState.phase);
check(hostState.scores.A === 0 && hostState.scores.B === 0, 'a denied socket cannot score');

/* ---- an accepted player still never sees unrevealed answers ---- */
const spy = new WebSocket(`ws://127.0.0.1:${PORT}`);
await new Promise((r) => spy.on('open', r));
let spyState = null;
spy.on('message', (raw) => {
  const m = JSON.parse(raw.toString());
  if (m.type === 'state') spyState = m.state;
});
spy.send(JSON.stringify({ type: 'join', role: 'player', team: 'B', name: 'Ben', code: JOIN_CODE }));
await sleep(300);
check(spyState?.board?.slots.every((x) => x.revealed || x.text === null),
  'an accepted player still cannot see unrevealed answers');

/* ---- the banner tells the teacher what they need ---- */
check(banner.includes(JOIN_CODE), 'the startup log prints the game code');
check(banner.includes(`?token=${HOST_TOKEN}`), 'the startup log prints the host board link');
check(banner.includes('https://mind-feud.onrender.com'), 'the startup log prints the public URL');

for (const c of [noToken.ws, badToken.ws, goodHost.ws, noCode.ws, badCode.ws, goodPlayer.ws, host, spy]) c.close();
server.kill();

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('Public-deployment checks passed.\n');

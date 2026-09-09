/**
 * Public-deployment checks.
 *
 * Boots the server the way Render does and then attacks it. On a public URL
 * the host laptop AND the projector both show more than a student should see,
 * so both sit behind the host key; /play sits behind the short game code.
 *
 * Run: node test/deploy.test.js
 */

import { spawn } from 'node:child_process';
import WebSocket from 'ws';

const PORT = 3298;
const HOST_TOKEN = 'secret-host-key';
const JOIN_CODE = 'MIND';
let pass = 0, fail = 0;
const failures = [];
const check = (ok, label, detail = '') => {
  if (ok) pass++; else { fail++; failures.push(`${label}${detail ? `  (${detail})` : ''}`); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn(process.execPath, ['server.js'], {
  env: {
    ...process.env,
    PORT: String(PORT),
    RENDER: 'true',
    RENDER_EXTERNAL_URL: 'https://mind-jeopardy.onrender.com',
    HOST_TOKEN,
    JOIN_CODE,
    ANTHROPIC_API_KEY: '',
    ANTHROPIC_AUTH_TOKEN: '',
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

/* ---- the public config endpoint leaks neither code ---- */
const cfg = await (await fetch(`http://127.0.0.1:${PORT}/api/config`)).json();
const raw = JSON.stringify(cfg);
check(cfg.joinRequired === true, 'config says a game code is required');
check(cfg.hostTokenRequired === true, 'config says a host key is required');
check(!raw.includes(JOIN_CODE), 'the game code is NOT in the public config', raw);
check(!raw.includes(HOST_TOKEN), 'the host key is NOT in the public config', raw);
check(cfg.playUrls[0] === 'https://mind-jeopardy.onrender.com/play',
  'the public URL is advertised, not a LAN address', cfg.playUrls[0]);

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

/* ---- the host key guards BOTH privileged screens ---- */
for (const role of ['host', 'board']) {
  const none = await open({ type: 'join', role });
  check(none.messages.includes('denied'), `${role} with no key is denied`);
  check(none.state === null, `a denied ${role} receives no game state`);
  const bad = await open({ type: 'join', role, token: 'guess' });
  check(bad.messages.includes('denied'), `${role} with a wrong key is denied`);
  const good = await open({ type: 'join', role, token: HOST_TOKEN });
  check(good.messages.includes('accepted'), `${role} with the right key is accepted`);
  check(good.joinCode === JOIN_CODE, `an authenticated ${role} learns the game code`);
  good.ws.close(); none.ws.close(); bad.ws.close();
}

/* ---- the game code guards the team console ---- */
const noCode = await open({ type: 'join', role: 'player', teamId: 't1' });
check(noCode.messages.includes('denied'), 'player with no code is denied');
check(noCode.joinCode === undefined, 'a denied player is never sent the code');

const badCode = await open({ type: 'join', role: 'player', teamId: 't1', code: 'XXXX' });
check(badCode.messages.includes('denied'), 'player with a wrong code is denied');

const goodPlayer = await open({ type: 'join', role: 'player', teamId: 't1', code: 'mind' });
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
host.send(JSON.stringify({ type: 'host', action: 'addTeam', name: 'Alpha' }));
host.send(JSON.stringify({ type: 'host', action: 'addTeam', name: 'Beta' }));
host.send(JSON.stringify({ type: 'host', action: 'startGame' }));
host.send(JSON.stringify({ type: 'host', action: 'pickClue', categoryIndex: 0, clueIndex: 0 }));
await sleep(300);
check(hostState?.phase === 'clue', 'the real host can start a game', hostState?.phase);

noCode.ws.send(JSON.stringify({ type: 'host', action: 'reset' }));
badCode.ws.send(JSON.stringify({ type: 'buzz' }));
noCode.ws.send(JSON.stringify({ type: 'answer', text: 'sensation' }));
await sleep(300);
check(hostState.phase === 'clue', 'a denied socket cannot reset the game or buzz', hostState.phase);
check(hostState.teams.every((t) => t.score === 0), 'a denied socket cannot score');

/* ---- an accepted player still cannot see unrevealed answers ---- */
const spy = new WebSocket(`ws://127.0.0.1:${PORT}`);
await new Promise((r) => spy.on('open', r));
let spyState = null;
spy.on('message', (raw) => {
  const m = JSON.parse(raw.toString());
  if (m.type === 'state') spyState = m.state;
});
spy.send(JSON.stringify({
  type: 'join', role: 'player', teamId: hostState.teams[0].id, code: JOIN_CODE,
}));
await sleep(300);
check(spyState?.clue?.answer === null, 'an accepted player cannot see the live clue answer');
check(spyState.categories.every((c) => c.clues.every((x) => x.answer === null)),
  'an accepted player cannot see any answer on the board');
check(spyState.clue?.note === null, 'an accepted player never sees a teaching note');

/* ---- the banner tells the teacher what they need ---- */
check(banner.includes(JOIN_CODE), 'the startup log prints the game code');
check(banner.includes(`?token=${HOST_TOKEN}`), 'the startup log prints the host link');
check(banner.includes('https://mind-jeopardy.onrender.com'), 'the startup log prints the public URL');

for (const c of [noCode.ws, badCode.ws, goodPlayer.ws, host, spy]) c.close();
server.kill();

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('Public-deployment checks passed.\n');

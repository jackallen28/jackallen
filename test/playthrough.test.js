/**
 * End-to-end playthrough against a real server on a real socket.
 *
 * Boots the server, connects a host and both team consoles, then plays a round
 * and the final. Catches the things unit tests miss: buzzer race handling,
 * turn passing, whether a team screen can see unrevealed answers, and whether
 * the clock actually runs down.
 *
 * Run: node test/playthrough.test.js
 */

import { spawn } from 'node:child_process';
import WebSocket from 'ws';

const PORT = 3199;
let pass = 0, fail = 0;
const failures = [];

function check(ok, label, detail = '') {
  if (ok) pass++;
  else { fail++; failures.push(`${label}${detail ? `  (${detail})` : ''}`); }
}

const server = spawn(process.execPath, ['server.js'], {
  env: { ...process.env, PORT: String(PORT), ANTHROPIC_API_KEY: '' },
  stdio: ['ignore', 'pipe', 'pipe'],
});
server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await waitForServer();

class Client {
  constructor(label) {
    this.label = label;
    this.state = null;
    this.toasts = [];
    this.ws = new WebSocket(`ws://127.0.0.1:${PORT}`);
    this.ready = new Promise((res) => { this.ws.on('open', res); });
    this.ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'state') this.state = msg.state;
      else if (msg.type === 'toast') this.toasts.push(msg.text);
    });
  }
  send(o) { this.ws.send(JSON.stringify(o)); }
  host(action, extra = {}) { this.send({ type: 'host', action, ...extra }); }
  close() { this.ws.close(); }
  /** Wait until the server state satisfies `fn`, or give up. */
  async until(fn, ms = 2500) {
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      if (this.state && fn(this.state)) return true;
      await sleep(20);
    }
    return false;
  }
}

const host = new Client('host');
const teamA = new Client('A');
const teamB = new Client('B');
await Promise.all([host.ready, teamA.ready, teamB.ready]);

host.send({ type: 'join', role: 'host' });
teamA.send({ type: 'join', role: 'player', team: 'A', name: 'Ana' });
teamB.send({ type: 'join', role: 'player', team: 'B', name: 'Ben' });
await sleep(150);

check(host.state?.phase === 'lobby', 'starts in the lobby', host.state?.phase);

/* ---- round 1 ---- */
host.host('startRound', { index: 0 });
await host.until((s) => s.phase === 'intro');
check(host.state.round.index === 0, 'round 1 selected');

host.host('openQuestion', { questionId: 'r1q2' }); // the Gestalt board
await host.until((s) => s.phase === 'buzzing');
check(teamA.state.board?.prompt.includes('Gestalt'), 'teams see the prompt');

/* A team screen must never receive an unrevealed answer. */
const leaked = teamA.state.board.slots.some((x) => !x.revealed && x.text !== null);
check(!leaked, 'unrevealed answers are NOT sent to team screens');
check(host.state.board.slots.every((x) => x.text !== null), 'host screen sees every answer');

/* ---- buzzer race: both teams hit space, only one wins ---- */
teamA.send({ type: 'buzz' });
teamB.send({ type: 'buzz' });
await host.until((s) => s.phase === 'answering');
const winner = host.state.control;
check(winner === 'A' || winner === 'B', 'exactly one team takes control', String(winner));
const loser = winner === 'A' ? teamB : teamA;
const winnerClient = winner === 'A' ? teamA : teamB;
check(host.state.buzzLocked, 'buzzers lock after the first buzz');

/* The team that lost the race cannot answer. */
loser.send({ type: 'answer', text: 'closure' });
await sleep(120);
check(loser.toasts.some((t) => /not your turn|too late/i.test(t)),
  'the team without control is refused', JSON.stringify(loser.toasts));

/* ---- correct answers keep the board ---- */
winnerClient.send({ type: 'answer', text: 'closure' });
await host.until((s) => s.board.slots[0].revealed);
check(host.state.board.slots[0].by === winner, 'correct answer credited to the buzzing team');
check(host.state.scores[winner] === 26, 'points awarded at ×1', String(host.state.scores[winner]));
check(host.state.control === winner, 'the team keeps control after a correct answer');

winnerClient.send({ type: 'answer', text: 'proximty' }); // typo on purpose
await host.until((s) => s.board.slots[1].revealed);
check(host.state.scores[winner] === 49, 'a typo still scores', String(host.state.scores[winner]));

/* A repeat of something already up costs the turn but not the board. */
winnerClient.send({ type: 'answer', text: 'closure' });
await sleep(150);
check(host.state.control === winner, 'a duplicate does not pass control');
check(host.state.board.misses === 0, 'a duplicate is not a miss');

/* ---- ONE wrong answer passes control ---- */
winnerClient.send({ type: 'answer', text: 'the turing test' });
await host.until((s) => s.control !== winner);
check(host.state.control === (winner === 'A' ? 'B' : 'A'), 'one miss passes control to the other team');
check(host.state.board.misses === 1, 'the miss is recorded');

/* ---- host overrides ---- */
const other = host.state.control;
host.host('reveal', { index: 2, team: other });
await host.until((s) => s.board.slots[2].revealed);
check(host.state.scores[other] === 20, 'host can reveal and credit a slot', String(host.state.scores[other]));

host.host('endRound');
await host.until((s) => s.phase === 'roundOver');
check(host.state.board.slots.every((x) => x.revealed), 'ending the round reveals the whole board');
check(host.state.board.slots.filter((x) => x.missed).length === 3, 'unclaimed slots are marked missed');

/* ---- the final round goes to the leaders ---- */
host.host('startFinal');
await host.until((s) => s.phase === 'finalIntro');
const leader = host.state.scores.A > host.state.scores.B ? 'A' : 'B';
check(host.state.final.team === leader, 'the leading team is called up', host.state.final?.team);

const onClock = leader === 'A' ? teamA : teamB;
const offClock = leader === 'A' ? teamB : teamA;
check(onClock.state.rapidPrompt !== null, 'the team on the clock sees the rapid-fire question');
check(offClock.state.rapidPrompt === null, 'the other team does NOT see it');

host.host('startFinalClock');
await host.until((s) => s.phase === 'final' && s.final.running);
const startSecs = host.state.final.secondsLeft;
await sleep(2200);
check(host.state.final.secondsLeft < startSecs, 'the clock actually runs down',
  `${startSecs} -> ${host.state.final.secondsLeft}`);

/* Answer the question that is actually up, whatever it happens to be. */
const { RAPID_FIRE } = await import('../src/questions.js');
const current = RAPID_FIRE.find((x) => x.prompt === host.state.rapidPrompt);
const before = host.state.final.points;
onClock.send({ type: 'answer', text: current.accept[0] });
await host.until((s) => s.final.points > before);
check(host.state.final.points === before + 10, 'a rapid-fire hit scores 10', String(host.state.final.points));

/* SPACE passes, and the pass falls into the spoiler pile. */
const askedBefore = host.state.final.asked;
onClock.send({ type: 'buzz' });
await host.until((s) => s.final.asked > askedBefore);
check(host.state.final.missedCount === 1, 'a pass lands in the spoiler pile');

host.host('endRapid');
await host.until((s) => s.phase === 'spoilerIntro' || s.phase === 'gameOver');
check(host.state.phase === 'spoilerIntro', 'the trailing team gets a spoiler round', host.state.phase);
check(host.state.spoiler.team !== leader, 'the spoiler round goes to the trailing team');

host.host('startSpoilerClock');
await host.until((s) => s.phase === 'spoiler' && s.spoiler.running);
const spoilerQ = RAPID_FIRE.find((x) => x.prompt === host.state.rapidPrompt);
const spBefore = host.state.scores[host.state.spoiler.team];
offClock.send({ type: 'answer', text: spoilerQ.accept[0] });
await host.until((s) => s.scores[s.spoiler.team] > spBefore);
check(host.state.scores[host.state.spoiler.team] === spBefore + 15,
  'spoiler answers are worth 15');

host.host('endRapid');
await host.until((s) => s.phase === 'gameOver');
check(['A', 'B', 'tie'].includes(host.state.winner), 'the game declares a winner', host.state.winner);

/* ---- reset ---- */
host.host('reset');
await host.until((s) => s.phase === 'lobby');
check(host.state.scores.A === 0 && host.state.scores.B === 0, 'reset clears the scores');

for (const c of [host, teamA, teamB]) c.close();
server.kill();

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('Full playthrough passed.\n');

async function waitForServer() {
  for (let i = 0; i < 100; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/health`);
      if (res.ok) return;
    } catch { /* not up yet */ }
    await sleep(100);
  }
  throw new Error('server did not start');
}

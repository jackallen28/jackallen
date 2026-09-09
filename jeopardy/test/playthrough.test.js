/**
 * End-to-end playthrough against a real server on real sockets.
 *
 * Boots the server, connects a host, a projector and three team consoles, then
 * plays clues and the whole of Final Jeopardy. Catches what unit tests miss:
 * the buzzer race, lockout after a wrong answer, whether the projector can see
 * an unrevealed answer, the clocks, and the wager arithmetic.
 *
 * Run: node test/playthrough.test.js
 */

import { spawn } from 'node:child_process';
import WebSocket from 'ws';
import { CATEGORIES, FINAL } from '../src/questions.js';

const PORT = 3297;
let pass = 0, fail = 0;
const failures = [];
const check = (ok, label, detail = '') => {
  if (ok) pass++; else { fail++; failures.push(`${label}${detail ? `  (${detail})` : ''}`); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn(process.execPath, ['server.js'], {
  env: { ...process.env, PORT: String(PORT), ANTHROPIC_API_KEY: '', ANTHROPIC_AUTH_TOKEN: '' },
  stdio: ['ignore', 'pipe', 'pipe'],
});
server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));
for (let i = 0; i < 100; i++) {
  try { if ((await fetch(`http://127.0.0.1:${PORT}/health`)).ok) break; } catch {}
  await sleep(100);
}

class Client {
  constructor() {
    this.state = null;
    this.toasts = [];
    this.ws = new WebSocket(`ws://127.0.0.1:${PORT}`);
    this.ready = new Promise((res) => this.ws.on('open', res));
    this.ws.on('message', (raw) => {
      const m = JSON.parse(raw.toString());
      if (m.type === 'state') this.state = m.state;
      else if (m.type === 'toast') this.toasts.push(m.text);
    });
  }
  send(o) { this.ws.send(JSON.stringify(o)); }
  host(action, extra = {}) { this.send({ type: 'host', action, ...extra }); }
  close() { this.ws.close(); }
  async until(fn, ms = 3000) {
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      if (this.state && fn(this.state)) return true;
      await sleep(20);
    }
    return false;
  }
}

const host = new Client();
const board = new Client();
const p1 = new Client();
const p2 = new Client();
const p3 = new Client();
await Promise.all([host.ready, board.ready, p1.ready, p2.ready, p3.ready]);

host.send({ type: 'join', role: 'host' });
board.send({ type: 'join', role: 'board' });
await sleep(150);
check(host.state?.phase === 'setup', 'starts in setup', host.state?.phase);

/* ---- teams are created by the host, any number ---- */
host.host('addTeam', { name: 'The Cartesians' });
host.host('addTeam', { name: 'Team Anatta' });
host.host('addTeam', { name: 'The Gestaltists' });
await host.until((s) => s.teams.length === 3);
check(host.state.teams.length === 3, 'three teams created');

const cfg = await (await fetch(`http://127.0.0.1:${PORT}/api/config`)).json();
check(cfg.teams.length === 3, 'the join screen can list teams before joining');

const ids = host.state.teams.map((t) => t.id);
p1.send({ type: 'join', role: 'player', teamId: ids[0] });
p2.send({ type: 'join', role: 'player', teamId: ids[1] });
p3.send({ type: 'join', role: 'player', teamId: ids[2] });
await sleep(200);

host.host('startGame');
await host.until((s) => s.phase === 'board');
check(host.state.picker === ids[0], 'the first team picks first');

/* ---- putting a clue up ---- */
host.host('pickClue', { categoryIndex: 0, clueIndex: 0 });
await host.until((s) => s.phase === 'clue');
const firstClue = CATEGORIES[0].clues[0];
check(board.state.clue?.text === firstClue.text, 'the projector shows the clue text');
check(board.state.clue.answer === null, 'the projector does NOT get the answer yet');
check(host.state.clue.answer === firstClue.answer, 'the host laptop DOES get the answer');
check(host.state.clue.note === firstClue.note, 'the host laptop gets the teaching note');
check(p1.state.clue.answer === null, 'a team screen does NOT get the answer');
check(board.state.categories[1].clues[0].answer === null, 'the projector never gets the unplayed answers');
check(host.state.categories[1].clues[0].answer !== null, 'the host laptop lists every answer');

/* ---- buzzers are shut until the host has read the clue ---- */
p1.send({ type: 'buzz' });
await sleep(120);
check(host.state.phase === 'clue', 'buzzing before the buzzers open does nothing');
check(p1.toasts.some((t) => /not live/i.test(t)), 'and the team is told why');

host.host('openBuzzers');
await host.until((s) => s.phase === 'open');

/* ---- the race: three teams, one winner ---- */
p2.send({ type: 'buzz' });
p3.send({ type: 'buzz' });
p1.send({ type: 'buzz' });
await host.until((s) => s.phase === 'answering');
const holder = host.state.clue.buzzedBy;
check(ids.includes(holder), 'exactly one team takes the clue', String(holder));
const holderClient = [p1, p2, p3][ids.indexOf(holder)];
const otherClient = [p1, p2, p3][(ids.indexOf(holder) + 1) % 3];
check(host.state.clue.secondsLeft > 0, 'the answer clock starts on the buzz');

otherClient.send({ type: 'answer', text: firstClue.answer });
await sleep(150);
check(host.state.clue.buzzedBy === holder, 'a team without the clue cannot answer');

/* ---- a wrong answer costs the clue, not points ---- */
const scoreBefore = host.state.teams.find((t) => t.id === holder).score;
holderClient.send({ type: 'answer', text: 'the turing test' });
await host.until((s) => s.phase === 'open');
check(host.state.teams.find((t) => t.id === holder).score === scoreBefore,
  'a wrong answer does NOT subtract points');
check(host.state.clue.lockedOut.includes(holder), 'the wrong team is locked out of this clue');
check(host.state.phase === 'open', 'the buzzers reopen for everyone else');

holderClient.send({ type: 'buzz' });
await sleep(120);
check(host.state.clue.buzzedBy === null, 'a locked-out team cannot buzz again on this clue');

/* ---- a correct answer scores and takes the pick ---- */
otherClient.send({ type: 'buzz' });
await host.until((s) => s.phase === 'answering');
const winner = host.state.clue.buzzedBy;
otherClient.send({ type: 'answer', text: firstClue.accept[0] });
await host.until((s) => s.phase === 'revealed');
check(host.state.teams.find((t) => t.id === winner).score === firstClue.value,
  'a correct answer scores the clue value',
  String(host.state.teams.find((t) => t.id === winner).score));
check(host.state.picker === winner, 'the correct team picks next');
check(board.state.clue.answer === firstClue.answer, 'the answer now goes up on the projector');
check(board.state.clue.note === null, 'the teaching note NEVER goes to the projector');

host.host('backToBoard');
await host.until((s) => s.phase === 'board');
check(host.state.categories[0].clues[0].used, 'the clue is struck off the board');
check(host.state.cluesLeft === 29, 'clue count drops', String(host.state.cluesLeft));

/* ---- a clue nobody gets ---- */
host.host('pickClue', { categoryIndex: 1, clueIndex: 0 });
host.host('openBuzzers');
await host.until((s) => s.phase === 'open');
for (const [i, c] of [p1, p2, p3].entries()) {
  c.send({ type: 'buzz' });
  await host.until((s) => s.phase === 'answering');
  c.send({ type: 'answer', text: 'definitely not the answer' });
  await host.until((s) => s.phase === 'open' || s.phase === 'revealed');
}
check(host.state.phase === 'revealed', 'once every team has missed, the answer is revealed',
  host.state.phase);
check(board.state.clue.answer !== null, 'and the projector shows it');
host.host('backToBoard');
await host.until((s) => s.phase === 'board');

/* ---- the answer clock expiring counts as a miss ---- */
host.host('setting', { key: 'answerSeconds', value: 1 });
host.host('pickClue', { categoryIndex: 2, clueIndex: 0 });
host.host('openBuzzers');
await host.until((s) => s.phase === 'open');
p1.send({ type: 'buzz' });
await host.until((s) => s.phase === 'answering');
await host.until((s) => s.clue.lockedOut.includes(ids[0]), 4000);
check(host.state.clue.lockedOut.includes(ids[0]), 'running out of time locks the team out');
host.host('setting', { key: 'answerSeconds', value: 15 });
host.host('reveal');
await host.until((s) => s.phase === 'revealed');
host.host('backToBoard');

/* ---- Final Jeopardy ---- */
host.host('adjust', { teamId: ids[0], delta: 800 });
host.host('adjust', { teamId: ids[1], delta: 400 });
await sleep(150);
host.host('startFinal');
await host.until((s) => s.phase === 'finalIntro');
check(board.state.final.text === null, 'the projector does NOT see the final clue during the intro');
check(host.state.final.text === FINAL.text, 'the host laptop sees it from the start');

host.host('openWagers');
await host.until((s) => s.phase === 'finalWager');

// A wager above your score is refused — this is what keeps scores non-negative.
const p1Score = host.state.teams.find((t) => t.id === ids[0]).score;
p1.send({ type: 'wager', amount: p1Score + 1 });
await sleep(150);
check(p1.toasts.some((t) => /cannot wager more/i.test(t)), 'over-wagering is refused');

p1.send({ type: 'wager', amount: p1Score });      // all in
p2.send({ type: 'wager', amount: 100 });
p3.send({ type: 'wager', amount: 0 });
await host.until((s) => s.final.submitted.every((x) => x.wagered));
check(board.state.final.submitted.every((x) => x.wagered), 'the projector sees WHO has wagered');
const boardJson = JSON.stringify(board.state.final.detail);
check(!boardJson.includes(String(p1Score)) || Object.keys(board.state.final.detail).length === 0,
  'the projector never sees the wager amounts', boardJson);
check(p2.state.final.detail[ids[0]] === undefined, 'a team cannot see another team\'s wager');
check(p1.state.final.detail[ids[0]]?.wager === p1Score, 'a team can see its own wager');

host.host('openFinalClue');
await host.until((s) => s.phase === 'finalClue');
check(p1.state.final.text === FINAL.text, 'every team now sees the final clue');

p1.send({ type: 'answer', text: 'substance dualism' });
p2.send({ type: 'answer', text: 'materialism' });
p3.send({ type: 'answer', text: 'cartesian dualism' });
await host.until((s) => s.final.submitted.every((x) => x.answered));
await sleep(250); // let the judge record its verdicts
check(host.state.final.results[ids[0]]?.correct === true, 'a correct final answer is recorded');
check(host.state.final.results[ids[1]]?.correct === false, 'a wrong final answer is recorded');
check(p2.state.final.detail[ids[0]] === undefined, 'a team still cannot see another team\'s answer');

host.host('closeFinalWriting');
await host.until((s) => s.phase === 'finalReveal');
check(host.state.final.revealOrder.length === 3, 'a reveal order is offered');
const order = host.state.final.revealOrder;
const scores = host.state.teams;
check(
  scores.find((t) => t.id === order[0]).score <= scores.find((t) => t.id === order[2]).score,
  'the reveal order runs poorest first',
);

const before = Object.fromEntries(host.state.teams.map((t) => [t.id, t.score]));
for (const id of [...order]) {
  host.host('revealFinalTeam', { teamId: id });
  await host.until((s) => s.final.revealed.includes(id));
}
await host.until((s) => s.phase === 'gameOver');

check(host.state.teams.find((t) => t.id === ids[0]).score === before[ids[0]] + p1Score,
  'a correct final answer adds the wager');
check(host.state.teams.find((t) => t.id === ids[1]).score === before[ids[1]] - 100,
  'a wrong final answer subtracts the wager');
check(host.state.teams.every((t) => t.score >= 0), 'no score ever goes negative');
check(ids.includes(host.state.winner) || host.state.winner === 'tie',
  'a winner is declared', String(host.state.winner));

/* ---- reset ---- */
host.host('reset');
await host.until((s) => s.phase === 'setup');
check(host.state.teams.length === 0 && host.state.cluesLeft === 30, 'reset clears everything');

for (const c of [host, board, p1, p2, p3]) c.close();
server.kill();

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('Full playthrough passed.\n');

/* Mind Feud — team console. One of these per team computer. */

import { play, unlock } from '/sfx.js';

const $ = (id) => document.getElementById(id);
let ws;
let state = null;
let me = { team: null, name: '' };
let lastVersion = -1;
let joined = false;
let joinRequired = false;

// A public deployment asks the class for the code on the projector.
fetch('/api/config')
  .then((r) => r.json())
  .then((d) => {
    joinRequired = Boolean(d.joinRequired);
    $('codeInput').classList.toggle('hidden', !joinRequired);
  })
  .catch(() => {});

/* ---------------- join ---------------- */

const saved = JSON.parse(localStorage.getItem('mindfeud.me') || 'null');
if (saved) {
  me.team = saved.team;
  me.code = saved.code || '';
  $('nameInput').value = saved.name || '';
  $('codeInput').value = me.code;
  selectTeam(saved.team);
}

function selectTeam(team) {
  me.team = team;
  $('pickA').classList.toggle('sel', team === 'A');
  $('pickB').classList.toggle('sel', team === 'B');
}

$('pickA').onclick = () => { unlock(); selectTeam('A'); };
$('pickB').onclick = () => { unlock(); selectTeam('B'); };
$('joinBtn').onclick = doJoin;
for (const id of ['nameInput', 'codeInput']) {
  $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') doJoin(); });
}

function doJoin() {
  unlock();
  $('joinErr').textContent = '';
  if (!me.team) { $('joinErr').textContent = 'Pick a team first.'; return; }
  if (joinRequired && !$('codeInput').value.trim()) {
    $('joinErr').textContent = 'Enter the game code from the board.';
    return;
  }
  me.code = $('codeInput').value.trim().toUpperCase();
  me.name = $('nameInput').value.trim() || `Team ${me.team}`;
  localStorage.setItem('mindfeud.me', JSON.stringify(me));
  joined = true;
  connect();
}

/** Only swap to the game screen once the server has actually let us in. */
function showGame() {
  $('join').classList.add('hidden');
  $('game').classList.remove('hidden');
}

/* ---------------- connection ---------------- */

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);
  ws.onopen = () => ws.send(JSON.stringify({
    type: 'join', role: 'player', team: me.team, name: me.name, code: me.code || '',
  }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') onState(msg.state, msg.fx);
    else if (msg.type === 'accepted') showGame();
    else if (msg.type === 'denied') {
      joined = false;
      ws.close();
      $('game').classList.add('hidden');
      $('join').classList.remove('hidden');
      $('joinErr').textContent = msg.reason;
    } else if (msg.type === 'toast') bump(msg.text, msg.tone === 'error' ? 'bad' : 'warn');
  };
  // Reconnect quietly — a team should never have to think about the network.
  ws.onclose = () => { if (joined) setTimeout(connect, 1000); };
}

/* ---------------- state ---------------- */

function onState(next, fx) {
  const isNew = next.version !== lastVersion;
  lastVersion = next.version;
  const prev = state;
  state = next;
  render();

  if (!isNew || !fx) return;
  const ev = state.lastEvent || {};
  const mine = ev.team === me.team;

  // Only play the payoff sounds for your own team, so the two team computers
  // do not turn into a wall of noise. The host screen carries the show.
  if (fx === 'ding' && mine) { play('ding'); bump(ev.answer ? `+${ev.value} — ${ev.answer}` : `+${ev.value}`, 'good'); }
  else if (fx === 'sweep' && mine) { play('sweep'); bump('BOARD CLEARED!', 'good'); }
  else if (fx === 'strike' && mine) { play('strike'); bump('Not on the board — over to them.', 'bad'); }
  else if (fx === 'nearmiss' && mine) { play('nearmiss'); bump(`Correct — but NOT on the board! ${ev.detail || ''}`, 'warn'); }
  else if (fx === 'duplicate' && mine) { play('duplicate'); bump('Already up there — look at the board!', 'warn'); }
  else if (fx === 'buzz') { play('buzz'); if (mine) bump('You got in! Say it, then type it.', 'good'); }
  else if (fx === 'questionUp' || fx === 'roundStart') { play('questionUp'); bump(''); }
  else if (fx === 'go') play('go');

  // Grab the keyboard the moment control lands on us.
  if (prev?.control !== state.control && state.control === me.team) focusAnswer();
}

function render() {
  if (!state) return;
  const s = state;
  const isFinal = s.phase === 'final' || s.phase === 'spoiler';
  const stage = s.phase === 'spoiler' ? s.spoiler : s.final;

  $('nameA').textContent = s.teamNames.A;
  $('nameB').textContent = s.teamNames.B;
  $('valA').textContent = s.scores.A;
  $('valB').textContent = s.scores.B;
  $('scoreA').classList.toggle('control', s.control === 'A');
  $('scoreB').classList.toggle('control', s.control === 'B');
  $('multiplier').textContent = s.board ? `×${s.board.multiplier}` : (s.round ? `×${s.round.multiplier}` : '—');

  // Status line
  const ours = s.control === me.team;
  let status = 'Waiting for the host…';
  if (s.phase === 'lobby') status = `You are on ${s.teamNames[me.team]}. Waiting to start…`;
  else if (s.phase === 'intro') status = s.round ? s.round.name : 'Get ready…';
  else if (s.phase === 'buzzing') status = 'BUZZERS ARE LIVE — hit SPACE!';
  else if (s.phase === 'answering') status = ours ? 'YOUR BOARD — say it out loud, then type it' : `${s.teamNames[s.control]} are answering…`;
  else if (s.phase === 'roundOver') status = 'Round over.';
  else if (s.phase === 'finalIntro') status = stage && stage.team === me.team ? 'FINAL ROUND — you are up!' : 'Final round — they are up.';
  else if (s.phase === 'spoilerIntro') status = stage && stage.team === me.team ? 'SPOILER ROUND — your comeback!' : 'Spoiler round — their turn.';
  else if (isFinal) status = stage.team === me.team ? 'GO! SPACE to pass.' : `${s.teamNames[stage.team]} are on the clock.`;
  else if (s.phase === 'gameOver') {
    status = s.winner === 'tie' ? 'A TIE!'
      : s.winner === me.team ? 'YOU WIN! 🎉' : `${s.teamNames[s.winner]} win.`;
  }
  $('status').textContent = status;

  // Clock
  const showClock = Boolean(stage) && ['finalIntro', 'final', 'spoilerIntro', 'spoiler'].includes(s.phase);
  $('clockRow').classList.toggle('hidden', !showClock);
  if (showClock) {
    const secs = stage.secondsLeft;
    $('miniClock').textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
    $('miniClock').style.color = secs <= 10 && stage.running ? 'var(--red)' : 'var(--gold)';
  }

  // Question — the board prompt for everyone; the rapid-fire prompt only for
  // the team actually on the clock (the server enforces this too).
  const qText = isFinal || s.phase === 'finalIntro' || s.phase === 'spoilerIntro'
    ? s.rapidPrompt
    : (s.board ? s.board.prompt : null);
  $('questionBox').classList.toggle('hidden', !qText);
  $('questionBox').textContent = qText || '';

  renderMiniBoard(s);
  renderBuzzer(s, ours, isFinal, stage);
  renderInput(s, ours, isFinal, stage);
}

function renderMiniBoard(s) {
  const el = $('miniBoard');
  if (!s.board) { el.innerHTML = ''; return; }
  const sig = JSON.stringify(s.board.slots);
  if (el.dataset.sig === sig) return;
  el.dataset.sig = sig;
  el.innerHTML = '';
  for (const slot of s.board.slots) {
    const d = document.createElement('div');
    const open = slot.revealed && !slot.missed;
    d.className = `mini ${open ? 'open' : slot.missed ? 'open missed' : 'closed'}`;
    if (slot.by) d.dataset.by = slot.by;
    d.innerHTML = `<div class="n">${slot.index + 1}</div><div class="t"></div><div class="p">${slot.points ?? ''}</div>`;
    d.querySelector('.t').textContent = slot.text || '';
    el.appendChild(d);
  }
}

function renderBuzzer(s, ours, isFinal, stage) {
  const b = $('buzzer');
  b.className = '';
  if (isFinal && stage && stage.team === me.team && stage.running) {
    b.classList.add('ours');
    b.innerHTML = 'PASS<small>SPACE skips — it goes to the other team</small>';
  } else if (s.phase === 'buzzing' && !s.buzzLocked) {
    b.classList.add('live');
    b.innerHTML = 'BUZZ!<small>PRESS SPACE</small>';
  } else if (s.phase === 'answering' && ours) {
    b.classList.add('ours', 'typing');
    b.innerHTML = 'YOU HAVE THE BOARD<small>keep going until you get one wrong</small>';
  } else if (s.phase === 'answering') {
    b.classList.add('locked');
    b.innerHTML = `${escapeHtml(s.teamNames[s.control])} HAVE IT<small>listen up — you are next</small>`;
  } else {
    b.classList.add('locked');
    b.innerHTML = 'BUZZERS LOCKED<small>press SPACE when they open</small>';
  }
}

function renderInput(s, ours, isFinal, stage) {
  const canType = (s.phase === 'answering' && ours)
    || (isFinal && stage && stage.team === me.team && stage.running);
  $('answerInput').disabled = !canType;
  $('sendBtn').disabled = !canType;
  $('answerInput').placeholder = canType
    ? 'Type your answer, then Enter'
    : 'Wait for your turn…';
  if (!canType) $('answerInput').value = '';
}

function focusAnswer() {
  const input = $('answerInput');
  if (!input.disabled) setTimeout(() => input.focus(), 30);
}

/* ---------------- input ---------------- */

$('buzzer').onclick = () => { unlock(); doBuzz(); };
$('sendBtn').onclick = () => sendAnswer();
$('answerInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); sendAnswer(); }
});

document.addEventListener('keydown', (e) => {
  if (e.code !== 'Space') return;
  unlock();
  // Space is the buzzer everywhere EXCEPT inside the answer box, where people
  // need it to type "chinese room".
  if (e.target === $('answerInput')) return;
  e.preventDefault();
  doBuzz();
});

function doBuzz() {
  if (!joined || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'buzz' }));
}

function sendAnswer() {
  const input = $('answerInput');
  const text = input.value.trim();
  if (!text || input.disabled) return;
  ws.send(JSON.stringify({ type: 'answer', text }));
  input.value = '';
  bump('Judging…', 'warn');
}

function bump(text, tone = '') {
  const el = $('feedback');
  el.className = tone;
  el.textContent = text;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

document.addEventListener('click', unlock, { once: true });

/* Mind Jeopardy — a team computer.
 *
 * Deliberately small: a buzzer, one text box, and a wager box that appears
 * only in Final Jeopardy. This screen never receives an unrevealed answer,
 * another team's wager, or another team's written answer. */

import { play, unlock } from '/sfx.js';

const $ = (id) => document.getElementById(id);
let ws, state = null, joined = false, joinRequired = false, lobbyTeams = [];
let me = { teamId: null, code: '' };
let lastVersion = -1, lastTick = null;

const saved = JSON.parse(localStorage.getItem('mindjeopardy.me') || 'null');
if (saved) { me = { ...me, ...saved }; $('codeInput').value = me.code || ''; }

/* The team list is created by the host, so the join screen polls for it. It
 * comes from /api/config rather than a socket because on a public deployment a
 * socket cannot join without the code the student has not typed yet. */
async function refreshConfig() {
  try {
    const d = await (await fetch('/api/config')).json();
    joinRequired = Boolean(d.joinRequired);
    $('codeInput').classList.toggle('hidden', !joinRequired);
    lobbyTeams = d.teams || [];
    renderTeamPick();
  } catch { /* the host will be along shortly */ }
}
refreshConfig();
const lobbyPoll = setInterval(() => { if (!joined) refreshConfig(); }, 2000);

function renderTeamPick() {
  const wrap = $('teamPick');
  if (!lobbyTeams.length) {
    wrap.dataset.sig = '';
    wrap.innerHTML = '<p class="muted">The host has not set up the teams yet — hold on.</p>';
    return;
  }
  const sig = JSON.stringify(lobbyTeams.map((t) => [t.id, t.name])) + me.teamId;
  if (wrap.dataset.sig === sig) return;
  wrap.dataset.sig = sig;
  wrap.innerHTML = '';
  for (const t of lobbyTeams) {
    const b = document.createElement('button');
    b.className = me.teamId === t.id ? 'sel' : '';
    b.dataset.team = t.id;
    b.textContent = t.name;
    wrap.appendChild(b);
  }
}

$('teamPick').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  unlock();
  me.teamId = b.dataset.team;
  renderTeamPick();
});

$('joinBtn').onclick = doJoin;
$('codeInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') doJoin(); });

function doJoin() {
  unlock();
  $('joinErr').textContent = '';
  if (!me.teamId) { $('joinErr').textContent = 'Pick your team first.'; return; }
  if (joinRequired && !$('codeInput').value.trim()) {
    $('joinErr').textContent = 'Enter the game code from the board.';
    return;
  }
  me.code = $('codeInput').value.trim().toUpperCase();
  localStorage.setItem('mindjeopardy.me', JSON.stringify(me));
  joined = true;
  clearInterval(lobbyPoll);
  connect();
}

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);
  ws.onopen = () => ws.send(JSON.stringify({
    type: 'join', role: 'player', teamId: me.teamId, code: me.code,
  }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') onState(msg.state, msg.fx);
    else if (msg.type === 'accepted') {
      $('join').classList.add('hidden');
      $('game').classList.remove('hidden');
    } else if (msg.type === 'denied') {
      joined = false;
      ws.close();
      $('game').classList.add('hidden');
      $('join').classList.remove('hidden');
      $('joinErr').textContent = msg.reason;
      refreshConfig();
    } else if (msg.type === 'toast') hint(msg.text, 'warn');
  };
  ws.onclose = () => { if (joined) setTimeout(connect, 1000); };
}

function onState(next, fx) {
  const isNew = next.version !== lastVersion;
  lastVersion = next.version;
  const prev = state;
  state = next;
  render();

  if (isNew && fx) {
    const ev = state.lastEvent || {};
    const mine = ev.team === me.teamId;
    // Only our own outcomes make noise here — the projector carries the show.
    if (fx === 'correct' && mine) { play('correct'); hint(`Correct! +${ev.value ?? ''}`, 'good'); }
    else if (fx === 'wrong' && mine) { play('wrong'); hint('No — the others can buzz now.', 'bad'); }
    else if (fx === 'timeup' && mine) { play('timeup'); hint('Out of time.', 'bad'); }
    else if (fx === 'buzz') { play('buzz'); if (mine) hint('You got in! Say it, then type it.', 'good'); }
    else if (fx === 'open') { play('open'); hint(''); }
    else if (fx === 'lock' && mine) play('lock');
    else if (fx === 'select' || fx === 'final') play(fx);
  }

  // Grab the keyboard the moment the clue becomes ours.
  if (prev?.clue?.buzzedBy !== state.clue?.buzzedBy && state.clue?.buzzedBy === me.teamId) {
    setTimeout(() => { if (!$('answerInput').disabled) $('answerInput').focus(); }, 30);
  }
  tickSound();
}

function render() {
  if (!state) return;
  const s = state;
  const mine = s.teams.find((t) => t.id === me.teamId);
  if (!mine) {
    // The host removed or reset the teams — back to the picker.
    $('game').classList.add('hidden');
    $('join').classList.remove('hidden');
    renderTeamPick();
    return;
  }

  $('myTeamName').textContent = mine.name;
  $('myScoreVal').textContent = mine.score;

  const holding = s.clue?.buzzedBy === me.teamId;
  const lockedOut = s.clue?.lockedOut?.includes(me.teamId);

  let status = 'Waiting for the host…';
  if (s.phase === 'setup') status = 'Waiting for the game to start…';
  else if (s.phase === 'board') status = s.picker === me.teamId ? 'YOUR PICK — call out a category and value' : 'Another team is choosing…';
  else if (s.phase === 'clue') status = 'Listen to the clue — buzzers open in a moment';
  else if (s.phase === 'open') status = lockedOut ? 'You have had your go on this one' : 'BUZZ IN — hit SPACE!';
  else if (s.phase === 'answering') status = holding ? 'YOU HAVE IT — say it, then type it' : `${nameOf(s.clue.buzzedBy)} is answering…`;
  else if (s.phase === 'revealed') status = 'Answer is on the board';
  else if (s.phase === 'boardCleared') status = 'Board cleared — Final Jeopardy next';
  else if (s.phase === 'finalIntro') status = 'FINAL JEOPARDY — get ready to wager';
  else if (s.phase === 'finalWager') status = s.final.detail[me.teamId]?.wager !== null && s.final.detail[me.teamId]?.wager !== undefined
    ? 'Wager locked in — wait for the clue' : `WAGER NOW — up to ${mine.score}`;
  else if (s.phase === 'finalClue') status = s.final.detail[me.teamId]?.answer ? 'Answer submitted' : 'WRITE YOUR ANSWER';
  else if (s.phase === 'finalReveal') status = 'The reveal…';
  else if (s.phase === 'gameOver') {
    status = s.winner === 'tie' ? "It's a tie!" : s.winner === me.teamId ? 'YOU WIN! 🎉' : `${nameOf(s.winner)} win.`;
  }
  $('status').textContent = status;

  // Clue text: the board clue for everyone, the Final clue once it is open.
  const text = ['finalClue', 'finalReveal', 'gameOver'].includes(s.phase)
    ? s.final?.text
    : s.clue?.text;
  $('clueBox').classList.toggle('hidden', !text);
  $('clueBox').textContent = text || '';

  renderClock(s);
  renderBuzzer(s, holding, lockedOut);
  renderInputs(s, holding, mine);
}

const nameOf = (id) => state.teams.find((t) => t.id === id)?.name || '';

function renderClock(s) {
  const stage = s.phase === 'answering' ? s.clue
    : ['finalWager', 'finalClue'].includes(s.phase) ? s.final : null;
  const show = stage?.running;
  $('clock').classList.toggle('hidden', !show);
  if (show) {
    $('clock').textContent = stage.secondsLeft >= 60
      ? `${Math.floor(stage.secondsLeft / 60)}:${String(stage.secondsLeft % 60).padStart(2, '0')}`
      : stage.secondsLeft;
    $('clock').classList.toggle('low', stage.secondsLeft <= 5);
  }
}

function renderBuzzer(s, holding, lockedOut) {
  const b = $('buzzer');
  b.className = '';
  if (s.phase === 'open' && !lockedOut) {
    b.classList.add('live');
    b.innerHTML = 'BUZZ!<small>PRESS SPACE</small>';
  } else if (holding) {
    b.classList.add('ours', 'typing');
    b.innerHTML = 'YOU HAVE IT<small>say it out loud, then type it</small>';
  } else if (s.phase === 'answering') {
    b.classList.add('locked');
    b.innerHTML = `${escapeHtml(nameOf(s.clue.buzzedBy))} HAS IT<small>if they miss, you can buzz again</small>`;
  } else if (lockedOut && s.phase === 'open') {
    b.classList.add('locked');
    b.innerHTML = 'ALREADY HAD YOUR GO<small>on this clue</small>';
  } else if (['finalWager', 'finalClue'].includes(s.phase)) {
    b.classList.add('ours', 'typing');
    b.innerHTML = s.phase === 'finalWager'
      ? 'FINAL JEOPARDY<small>lock in your wager below</small>'
      : 'FINAL JEOPARDY<small>write your answer below</small>';
  } else {
    b.classList.add('locked');
    b.innerHTML = 'BUZZERS LOCKED<small>press SPACE when they open</small>';
  }
}

function renderInputs(s, holding, mine) {
  const canAnswer = holding
    || (s.phase === 'finalClue' && !s.final.detail[me.teamId]?.answer);
  $('answerRow').classList.toggle('hidden', s.phase === 'finalWager');
  $('answerInput').disabled = !canAnswer;
  $('sendBtn').disabled = !canAnswer;
  $('answerInput').placeholder = canAnswer ? 'Type your answer, then Enter' : 'Wait for your turn…';
  if (!canAnswer && s.phase !== 'finalClue') $('answerInput').value = '';

  const wagering = s.phase === 'finalWager'
    && (s.final.detail[me.teamId]?.wager === null || s.final.detail[me.teamId]?.wager === undefined);
  $('wagerRow').classList.toggle('hidden', !wagering);
  if (wagering) {
    $('wagerInput').max = mine.score;
    $('wagerInput').placeholder = `0 to ${mine.score}`;
  }
}

/* ---------------- input ---------------- */

$('buzzer').onclick = () => { unlock(); doBuzz(); };
$('sendBtn').onclick = sendAnswer;
$('wagerBtn').onclick = sendWager;
$('answerInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); sendAnswer(); }
});
$('wagerInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); sendWager(); }
});

document.addEventListener('keydown', (e) => {
  if (e.code !== 'Space') return;
  unlock();
  // Space is the buzzer everywhere except in a text box, where people need it
  // to type "chinese room".
  if (e.target.matches('input, textarea')) return;
  e.preventDefault();
  doBuzz();
});

function doBuzz() {
  if (!joined || ws?.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'buzz' }));
}

function sendAnswer() {
  const input = $('answerInput');
  const text = input.value.trim();
  if (!text || input.disabled) return;
  ws.send(JSON.stringify({ type: 'answer', text }));
  input.value = '';
  hint(state?.phase === 'finalClue' ? 'Answer locked in.' : 'Judging…', 'warn');
}

function sendWager() {
  const value = $('wagerInput').value.trim();
  if (value === '') return;
  ws.send(JSON.stringify({ type: 'wager', amount: Number(value) }));
}

function hint(text, tone = '') {
  $('hint').className = tone;
  $('hint').textContent = text;
}

function tickSound() {
  const stage = state.phase === 'answering' ? state.clue
    : ['finalWager', 'finalClue'].includes(state.phase) ? state.final : null;
  if (!stage?.running) { lastTick = null; return; }
  if (stage.secondsLeft !== lastTick) {
    lastTick = stage.secondsLeft;
    if (stage.secondsLeft <= 5 && stage.secondsLeft > 0) play('tick');
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

document.addEventListener('click', unlock, { once: true });

/* Mind Jeopardy — the projector window.
 *
 * Read-only by design: no clicks, no keyboard, no controls. It is opened by
 * the host screen (which passes the key), dragged onto the projector and left
 * there for the lesson. The server never sends this window an answer that has
 * not already been revealed to the room. */

import { play, unlock } from '/sfx.js';

const $ = (id) => document.getElementById(id);
let ws, state = null, roster = null, joinCode = '', joinUrls = [];
let lastVersion = -1, lastTick = null;
const token = new URLSearchParams(location.search).get('token') || '';

fetch('/api/config').then((r) => r.json()).then((d) => {
  joinUrls = d.playUrls || [];
  if (state) render();
}).catch(() => {});

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);
  ws.onopen = () => ws.send(JSON.stringify({ type: 'join', role: 'board', token }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      if (msg.joinCode !== undefined) joinCode = msg.joinCode || '';
      roster = msg.roster;
      onState(msg.state, msg.fx);
    } else if (msg.type === 'denied') {
      document.body.innerHTML =
        '<div style="display:grid;place-items:center;height:100vh;text-align:center;padding:2rem">'
        + '<div><h1 style="color:var(--gold)">Board locked</h1>'
        + '<p>Open this window from the host screen so it carries the key.</p></div></div>';
    }
  };
  ws.onclose = () => setTimeout(connect, 1200);
}

function onState(next, fx) {
  const isNew = next.version !== lastVersion;
  lastVersion = next.version;
  state = next;
  render();
  if (fx && isNew) { play(fx); announce(fx); }
  tickSound();
}

function announce(fx) {
  const ev = state.lastEvent || {};
  if (fx === 'buzz') flash(`${ev.name || ''}`, 'warn');
  else if (fx === 'correct') flash('CORRECT', 'good');
  else if (fx === 'wrong') flash('NO', 'bad');
  else if (fx === 'timeup') flash("TIME'S UP", 'bad');
  else if (fx === 'gameOver') {
    flash(state.winner === 'tie' ? 'A TIE!' : `${nameOf(state.winner)} WINS`, 'good');
  }
}

function flash(text, tone) {
  const el = $('flash');
  el.querySelector('.inner').textContent = text;
  el.className = '';
  void el.offsetWidth;
  el.classList.add('show', tone);
}

const nameOf = (id) => state.teams.find((t) => t.id === id)?.name || '';

function render() {
  if (!state) return;
  const s = state;
  const inFinal = ['finalIntro', 'finalWager', 'finalClue', 'finalReveal'].includes(s.phase);
  const onClue = ['clue', 'open', 'answering', 'revealed'].includes(s.phase);
  const onGrid = ['board', 'boardCleared'].includes(s.phase);
  const over = s.phase === 'gameOver';

  $('lobby').classList.toggle('hidden', s.phase !== 'setup');
  $('gridview').classList.toggle('hidden', !onGrid);
  $('clueview').classList.toggle('hidden', !onClue);
  $('finalview').classList.toggle('hidden', !inFinal);
  $('gameover').classList.toggle('hidden', !over);
  $('scores').classList.toggle('hidden', s.phase === 'setup');

  if (s.phase === 'setup') renderLobby(s);
  if (onGrid) renderGrid(s);
  if (onClue) renderClue(s);
  if (inFinal) renderFinal(s);
  if (over) renderOver(s);
  renderScores(s);
}

function renderLobby(s) {
  $('joinUrl').textContent = joinUrls[0] || `${location.origin}/play`;
  $('code').textContent = joinCode;
  $('code').classList.toggle('hidden', !joinCode);
  $('codeLabel').classList.toggle('hidden', !joinCode);
  const joined = roster ? Object.values(roster.teams || {}).reduce((a, b) => a + b, 0) : 0;
  $('rosterLine').textContent = s.teams.length
    ? `${s.teams.map((t) => t.name).join(' · ')}   —   ${joined} device${joined === 1 ? '' : 's'} connected`
    : 'Waiting for the host to set up the teams…';
}

function renderGrid(s) {
  const grid = $('grid');
  const rows = s.categories[0].clues.length;
  grid.style.gridTemplateColumns = `repeat(${s.categories.length}, 1fr)`;
  grid.style.gridTemplateRows = `auto repeat(${rows}, 1fr)`;

  const sig = JSON.stringify(s.categories.map((c) => c.clues.map((x) => x.used)));
  if (grid.dataset.sig === sig) return;
  grid.dataset.sig = sig;

  grid.innerHTML = '';
  for (const c of s.categories) {
    const h = document.createElement('div');
    h.className = 'cat';
    h.textContent = c.name;
    grid.appendChild(h);
  }
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < s.categories.length; col++) {
      const cl = s.categories[col].clues[row];
      const d = document.createElement('div');
      d.className = `cell ${cl.used ? 'used' : ''}`;
      d.textContent = cl.value;
      d.style.gridColumn = col + 1;
      d.style.gridRow = row + 2;
      grid.appendChild(d);
    }
  }
}

function renderClue(s) {
  const c = s.clue;
  if (!c) return;
  $('clueMeta').textContent = `${c.category} — ${c.value}`;
  $('clueText').textContent = c.text;

  $('buzzWho').textContent = s.phase === 'open' ? 'BUZZ IN'
    : c.buzzedBy ? nameOf(c.buzzedBy)
      : s.phase === 'clue' ? '' : '';

  const showClock = s.phase === 'answering' && c.running;
  $('clock').classList.toggle('hidden', !showClock);
  $('clock').textContent = showClock ? c.secondsLeft : '';
  $('clock').classList.toggle('low', c.secondsLeft <= 5);

  const ans = $('clueAnswer');
  ans.classList.toggle('hidden', !c.answer);
  if (c.answer) ans.textContent = c.answer;

  setBar(showClock ? c.secondsLeft / (s.settings.answerSeconds || 1) : null, c.secondsLeft <= 5);
}

function renderFinal(s) {
  const f = s.final;
  if (!f) return;
  $('finalMeta').textContent = `FINAL JEOPARDY — ${f.category}`;

  if (s.phase === 'finalIntro') {
    $('finalText').textContent = 'Decide your wager. You may bet anything up to your score.';
  } else if (s.phase === 'finalWager') {
    $('finalText').textContent = 'LOCK IN YOUR WAGER';
  } else {
    $('finalText').textContent = f.text || '';
  }

  const showClock = f.running;
  $('finalClock').classList.toggle('hidden', !showClock);
  $('finalClock').textContent = showClock
    ? `${Math.floor(f.secondsLeft / 60)}:${String(f.secondsLeft % 60).padStart(2, '0')}` : '';
  $('finalClock').classList.toggle('low', f.secondsLeft <= 10);
  setBar(showClock ? f.secondsLeft / ((s.phase === 'finalWager' ? s.settings.wagerSeconds : s.settings.finalSeconds) || 1) : null,
    f.secondsLeft <= 10);

  // Who has committed — never how much, and never what they wrote.
  const wait = $('finalWait');
  const showWait = ['finalWager', 'finalClue'].includes(s.phase);
  wait.classList.toggle('hidden', !showWait);
  if (showWait) {
    const key = s.phase === 'finalWager' ? 'wagered' : 'answered';
    wait.innerHTML = '';
    for (const t of s.teams) {
      const done = f.submitted.find((x) => x.id === t.id)?.[key];
      const row = document.createElement('div');
      row.className = `waitrow ${done ? 'done' : ''}`;
      row.innerHTML = `<span class="dot"></span><span>${escapeHtml(t.name)}</span>`;
      wait.appendChild(row);
    }
  }

  const ans = $('finalAnswer');
  ans.classList.toggle('hidden', !f.answer);
  if (f.answer) ans.textContent = f.answer;

  // Revealed teams, one at a time, in the order the host works through them.
  const res = $('finalResults');
  res.innerHTML = '';
  if (s.phase === 'finalReveal' || s.phase === 'gameOver') {
    for (const id of f.revealed) {
      const detail = f.detail[id] || {};
      const ok = f.results[id]?.correct;
      const row = document.createElement('div');
      row.style.cssText = 'margin-top:.7rem;font-size:clamp(.85rem,2vw,1.5rem)';
      row.innerHTML = `<b>${escapeHtml(nameOf(id))}</b> wrote “${escapeHtml(detail.answer || '—')}” `
        + `<span style="color:${ok ? 'var(--green)' : 'var(--red)'}">${ok ? '✓' : '✗'}</span> `
        + `<span style="color:var(--gold)">${ok ? '+' : '−'}${detail.wager ?? 0}</span>`;
      res.appendChild(row);
    }
  }
}

function renderOver(s) {
  $('winLine').textContent = s.winner === 'tie' ? 'A TIE!' : `${nameOf(s.winner)} WINS`;
  $('finalScores').innerHTML = [...s.teams]
    .sort((a, b) => b.score - a.score)
    .map((t) => `<div>${escapeHtml(t.name)} — <b style="color:var(--gold)">${t.score}</b></div>`)
    .join('');
}

function renderScores(s) {
  const el = $('scores');
  el.innerHTML = '';
  for (const t of s.teams) {
    const d = document.createElement('div');
    const buzzed = s.clue?.buzzedBy === t.id;
    const locked = s.clue?.lockedOut?.includes(t.id);
    d.className = `score ${buzzed ? 'buzzed' : ''} ${s.picker === t.id && !buzzed ? 'picker' : ''} ${locked && !buzzed ? 'locked' : ''}`;
    d.innerHTML = `<div class="nm"></div><div class="sc">${t.score}</div>`;
    d.querySelector('.nm').textContent = t.name;
    el.appendChild(d);
  }
}

function setBar(fraction, low) {
  const bar = $('bar');
  bar.classList.toggle('hidden', fraction === null);
  bar.classList.toggle('low', Boolean(low));
  if (fraction !== null) {
    bar.querySelector('i').style.width = `${Math.max(0, Math.min(1, fraction)) * 100}%`;
  }
}

function tickSound() {
  const stage = state.phase === 'answering' ? state.clue
    : ['finalWager', 'finalClue'].includes(state.phase) ? state.final : null;
  if (!stage || !stage.running) { lastTick = null; return; }
  if (stage.secondsLeft !== lastTick) {
    lastTick = stage.secondsLeft;
    if (stage.secondsLeft <= 5 && stage.secondsLeft > 0) play('tick');
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// The host screen opens this window with a click, which is enough to let audio
// through; this is a belt-and-braces second chance.
document.addEventListener('click', unlock, { once: true });
document.addEventListener('keydown', unlock, { once: true });
unlock();
connect();

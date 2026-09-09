/* Mind Feud — host board. This is the screen the class watches. */

import { play, unlock, setEnabled } from '/sfx.js';

const $ = (id) => document.getElementById(id);
let ws;
let state = null;
let roster = { host: 0, A: [], B: [] };
let lastVersion = -1;
let lastClock = null;
let joinUrls = [];
let gameCode = '';
let hostToken = new URLSearchParams(location.search).get('token')
  || sessionStorage.getItem('mindfeud.hostToken') || '';

// The teacher opens the board on localhost; the class needs a reachable address
// (the LAN IP on a laptop, the public URL on Render).
fetch('/api/config')
  .then((r) => r.json())
  .then((d) => { joinUrls = d.playUrls || []; if (state) render(); })
  .catch(() => {});

/* ---------------- connection ---------------- */

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);
  ws.onopen = () => ws.send(JSON.stringify({ type: 'join', role: 'host', token: hostToken }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      if (msg.joinCode !== undefined) gameCode = msg.joinCode || '';
      roster = msg.roster || roster;
      onState(msg.state, msg.fx);
    } else if (msg.type === 'accepted') {
      sessionStorage.setItem('mindfeud.hostToken', hostToken);
      $('gate').classList.add('hidden');
    } else if (msg.type === 'denied') {
      // A public deployment guards this screen — it shows every answer.
      $('gate').classList.remove('hidden');
      $('gateErr').textContent = hostToken ? msg.reason : '';
      $('gateInput').focus();
    } else if (msg.type === 'toast') {
      flash(msg.text, msg.tone === 'error' ? 'bad' : 'warn');
    }
  };
  // A dropped socket mid-lesson should heal itself without anyone noticing.
  ws.onclose = () => setTimeout(connect, 1200);
}

function act(action, extra = {}) {
  ws?.send(JSON.stringify({ type: 'host', action, ...extra }));
}

/* ---------------- rendering ---------------- */

function onState(next, fx) {
  const isNew = next.version !== lastVersion;
  lastVersion = next.version;
  state = next;
  render();
  if (fx && isNew) {
    play(fx);
    announce(fx);
  }
  tickSound();
}

function announce(fx) {
  const ev = state.lastEvent || {};
  const teamName = ev.team ? state.teamNames[ev.team] : '';
  switch (fx) {
    case 'ding':
      flash(`${teamName}  +${ev.value ?? ''}`, 'good');
      break;
    case 'sweep':
      flash('BOARD CLEARED!', 'good');
      break;
    case 'strike':
      flash('✗', 'bad');
      break;
    case 'nearmiss':
      flash('NOT ON THE BOARD!', 'warn');
      break;
    case 'duplicate':
      flash('ALREADY UP THERE', 'warn');
      break;
    case 'buzz':
      flash(`${teamName} BUZZED IN`, 'warn');
      break;
    case 'gameOver':
      flash(state.winner === 'tie' ? 'A TIE!' : `${state.teamNames[state.winner]} WINS!`, 'good');
      break;
    default:
      break;
  }
}

function flash(text, tone) {
  const el = $('flash');
  el.querySelector('.inner').textContent = text;
  el.className = '';
  void el.offsetWidth; // restart the animation
  el.classList.add('show', tone);
}

function render() {
  if (!state) return;
  const s = state;

  $('nameA').textContent = s.teamNames.A;
  $('nameB').textContent = s.teamNames.B;
  $('valA').textContent = s.scores.A;
  $('valB').textContent = s.scores.B;
  $('scoreA').classList.toggle('control', s.control === 'A');
  $('scoreB').classList.toggle('control', s.control === 'B');

  const inFinal = ['finalIntro', 'final', 'spoilerIntro', 'spoiler'].includes(s.phase);
  const onBoard = ['buzzing', 'answering', 'roundOver'].includes(s.phase) && s.board;

  if (s.phase === 'final' || s.phase === 'finalIntro') {
    $('multiplier').textContent = '★';
    $('roundLabel').textContent = 'Final Round';
  } else if (s.phase === 'spoiler' || s.phase === 'spoilerIntro') {
    $('multiplier').textContent = '↺';
    $('roundLabel').textContent = 'Spoiler Round';
  } else if (s.phase === 'gameOver') {
    $('multiplier').textContent = '🏆';
    $('roundLabel').textContent = 'Final Score';
  } else {
    $('multiplier').textContent = onBoard ? `×${s.board.multiplier}` : (s.round ? `×${s.round.multiplier}` : '—');
    $('roundLabel').textContent = s.round ? `Round ${s.round.index + 1} of ${s.round.total}` : 'Lobby';
  }

  $('gameview').classList.toggle('hidden', !onBoard);
  $('finalview').classList.toggle('hidden', !inFinal && s.phase !== 'gameOver');
  $('titlecard').classList.toggle('hidden', onBoard || inFinal || s.phase === 'gameOver');

  if (onBoard) renderBoard(s);
  if (inFinal || s.phase === 'gameOver') renderFinal(s);
  if (!onBoard && !inFinal && s.phase !== 'gameOver') renderTitle(s);

  renderPanel(s);
}

function renderTitle(s) {
  const url = joinUrls[0] || `${location.origin}/play`;
  if (s.phase === 'lobby') {
    $('cardBig').textContent = 'MIND FEUD';
    $('cardSub').innerHTML = 'Where is My Mind? — Perception, Consciousness &amp; AI<br>'
      + 'Two teams. Six answers. One wrong and you lose the board.';
    $('joinUrl').textContent = url;
    $('joinUrl').title = joinUrls.join('  ·  ');
    $('joinUrl').classList.remove('hidden');
    $('gameCode').textContent = gameCode;
    $('gameCode').classList.toggle('hidden', !gameCode);
    $('gameCodeLabel').classList.toggle('hidden', !gameCode);
  } else {
    $('gameCode').classList.add('hidden');
    $('gameCodeLabel').classList.add('hidden');
    $('cardBig').textContent = s.round ? s.round.name.replace(/^Round \d+ — /, '') : '';
    $('cardSub').innerHTML = s.round
      ? `<b>Round ${s.round.index + 1}</b> · ${s.round.weeks} · <b>×${s.round.multiplier} points</b>`
      : '';
    $('joinUrl').classList.add('hidden');
  }
  const names = [...roster.A, ...roster.B];
  $('rosterLine').textContent = names.length
    ? `Connected — ${s.teamNames.A}: ${roster.A.join(', ') || '(nobody yet)'}   |   ${s.teamNames.B}: ${roster.B.join(', ') || '(nobody yet)'}`
    : 'Waiting for the team computers to join…';
}

function renderBoard(s) {
  $('prompt').textContent = s.board.prompt;

  const board = $('board');
  board.innerHTML = '';
  for (const slot of s.board.slots) {
    const el = document.createElement('div');
    const open = slot.revealed && !slot.missed;
    el.className = `slot ${open ? 'open' : slot.missed ? 'open missed' : 'closed'}`;
    if (slot.by) el.dataset.by = slot.by;
    el.innerHTML = `
      <div class="num">${slot.index + 1}</div>
      <div class="text"></div>
      <div class="pts">${slot.points ?? ''}</div>
      <div class="peek"></div>`;
    // The host screen always knows the answer; unrevealed slots get a faint
    // peek so the teacher can steer without breaking character.
    el.querySelector('.text').textContent = slot.text || '';
    el.querySelector('.peek').textContent = slot.revealed ? '' : (slot.text || '');
    board.appendChild(el);
  }

  const strikes = $('strikes');
  strikes.innerHTML = '';
  for (let i = 0; i < s.board.missLimit; i++) {
    const x = document.createElement('div');
    x.className = `strike-x ${i < s.board.misses ? 'on' : ''}`;
    x.textContent = '✗';
    strikes.appendChild(x);
  }

  const nm = $('nearmisses');
  if (s.board.nearMissesHit.length) {
    nm.classList.remove('hidden');
    nm.innerHTML = s.board.nearMissesHit
      .map((t) => `<div><b>Correct — but not on the board:</b> ${escapeHtml(t)}</div>`)
      .join('');
  } else {
    nm.classList.add('hidden');
  }
}

function renderFinal(s) {
  const stage = s.phase === 'spoiler' || s.phase === 'spoilerIntro' ? s.spoiler : s.final;
  if (!stage) return;
  const secs = stage.secondsLeft ?? 0;
  const clock = $('clock');
  clock.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
  clock.classList.toggle('low', secs <= 10 && stage.running);

  $('rapidPrompt').textContent = s.rapidPrompt || '';
  $('rapidPrompt').classList.toggle('hidden', !s.rapidPrompt);

  const name = s.teamNames[stage.team];
  if (s.phase === 'finalIntro') {
    $('finalStats').innerHTML =
      `<span style="color:var(--gold)">FINAL ROUND — RAPID FIRE</span><br>`
      + `${escapeHtml(name)} are up. Beat <b>${s.final.target}</b> points in ${secs} seconds for a <b>+${s.final.bonus}</b> bonus.<br>`
      + `<span class="muted" style="font-size:.7em">SPACE passes — and every pass falls to the other team in the spoiler round.</span>`;
  } else if (s.phase === 'spoilerIntro') {
    $('finalStats').innerHTML =
      `<span style="color:var(--gold)">SPOILER ROUND</span><br>`
      + `${escapeHtml(name)} get every question the leaders left behind — worth <b>15</b> each.`;
  } else if (s.phase === 'gameOver') {
    $('finalStats').innerHTML = s.winner === 'tie'
      ? '<span style="color:var(--gold);font-size:1.6em">A DEAD TIE</span>'
      : `<span style="color:var(--gold);font-size:1.6em">${escapeHtml(s.teamNames[s.winner])} WIN</span><br>`
        + `${escapeHtml(s.teamNames.A)} ${s.scores.A} — ${s.scores.B} ${escapeHtml(s.teamNames.B)}`;
    $('rapidPrompt').classList.add('hidden');
  } else {
    $('finalStats').innerHTML =
      `${escapeHtml(name)} — <b>${stage.points}</b> pts · ${stage.correct} correct`
      + (s.phase === 'final'
        ? ` · <span style="color:${stage.points >= s.final.target ? 'var(--green)' : 'var(--gold)'}">target ${s.final.target}</span>`
        : ` · ${stage.total - stage.asked} left in the pile`);
  }
}

function tickSound() {
  const stage = state.phase === 'spoiler' ? state.spoiler : state.phase === 'final' ? state.final : null;
  if (!stage || !stage.running) { lastClock = null; return; }
  if (stage.secondsLeft !== lastClock) {
    lastClock = stage.secondsLeft;
    if (stage.secondsLeft <= 10 && stage.secondsLeft > 0) play('tick');
  }
}

/* ---------------- control panel ---------------- */

function renderPanel(s) {
  const grid = $('revealGrid');
  const slots = s.board ? s.board.slots : [];
  if (grid.dataset.sig !== JSON.stringify(slots.map((x) => [x.revealed, x.text]))) {
    grid.dataset.sig = JSON.stringify(slots.map((x) => [x.revealed, x.text]));
    grid.innerHTML = '';
    slots.forEach((slot) => {
      const row = document.createElement('div');
      row.className = 'row';
      row.innerHTML = `
        <button class="btn small a" data-reveal="${slot.index}" data-team="A" ${slot.revealed ? 'disabled' : ''}>A</button>
        <button class="btn small b" data-reveal="${slot.index}" data-team="B" ${slot.revealed ? 'disabled' : ''}>B</button>
        <button class="btn small" data-reveal="${slot.index}" style="flex:5;text-align:left" ${slot.revealed ? 'disabled' : ''}>${slot.index + 1}. ${escapeHtml(truncate(slot.text || '', 34))}</button>`;
      grid.appendChild(row);
    });
  }

  const list = $('questionList');
  const sig = JSON.stringify(s.roundList.map((r) => r.questions.map((q) => q.used)));
  if (list.dataset.sig !== sig) {
    list.dataset.sig = sig;
    list.innerHTML = '';
    s.roundList.forEach((round) => {
      const h = document.createElement('div');
      h.className = 'muted';
      h.style.cssText = 'margin:.5rem 0 .2rem;font-weight:700';
      h.textContent = `${round.name} (×${round.multiplier})`;
      list.appendChild(h);
      round.questions.forEach((q) => {
        const b = document.createElement('button');
        b.className = `btn qbtn small ${q.used ? 'used' : ''}`;
        b.style.width = '100%';
        b.style.marginBottom = '.2rem';
        b.dataset.question = q.id;
        b.dataset.round = round.index;
        b.textContent = truncate(q.prompt, 90);
        list.appendChild(b);
      });
    });
  }

  $('missLimit').value = s.settings.missLimit;
  $('buzzToReclaim').checked = s.settings.buzzToReclaim;
  $('enableSpoiler').checked = s.settings.enableSpoiler;

  const log = $('log');
  log.innerHTML = '';
  for (const ev of s.log || []) {
    const li = document.createElement('li');
    li.className = ev.kind;
    const who = ev.team ? `<span class="who" style="color:var(--team${ev.team})">${escapeHtml(s.teamNames[ev.team])}</span> ` : '';
    let body = '';
    switch (ev.kind) {
      case 'correct': body = `typed “${escapeHtml(ev.text)}” → <b>${escapeHtml(ev.answer)}</b> +${ev.value}`; break;
      case 'wrong': body = `typed “${escapeHtml(ev.text)}” — not on the board`; break;
      case 'nearMiss': body = `typed “${escapeHtml(ev.text)}” — correct, off the board`; break;
      case 'duplicate': body = `typed “${escapeHtml(ev.text)}” — already up`; break;
      case 'buzz': body = `buzzed in (${escapeHtml(ev.player || '')})`; break;
      case 'rapidCorrect': body = `“${escapeHtml(ev.text)}” ✓ +${ev.value}`; break;
      case 'rapidWrong': body = `“${escapeHtml(ev.text)}” ✗`; break;
      case 'rapidPass': body = 'passed'; break;
      case 'hostReveal': body = `host revealed #${ev.index + 1}`; break;
      case 'roundOver': body = `round over (${escapeHtml(ev.reason || '')})`; break;
      case 'roundIntro': body = escapeHtml(ev.round || ''); break;
      default: body = escapeHtml(ev.kind);
    }
    const why = ev.source && ev.source !== 'local'
      ? `<div class="why">judged by ${ev.source}</div>` : '';
    li.innerHTML = who + body + why;
    log.appendChild(li);
  }
}

/* ---------------- input ---------------- */

document.addEventListener('click', (e) => {
  unlock();
  const btn = e.target.closest('button');
  if (!btn) return;

  if (btn.id === 'gateBtn') return submitToken();
  if (btn.id === 'toggle') return $('panel').classList.toggle('collapsed');
  if (btn.id === 'setA') return act('teamName', { team: 'A', name: $('teamAName').value });
  if (btn.id === 'setB') return act('teamName', { team: 'B', name: $('teamBName').value });
  if (btn.id === 'resetBtn') {
    if (confirm('Reset scores, rounds and the question pool?')) act('reset');
    return;
  }

  if (btn.dataset.reveal !== undefined) {
    return act('reveal', { index: Number(btn.dataset.reveal), team: btn.dataset.team || null });
  }
  if (btn.dataset.question) {
    // Jump straight to that question, switching round if needed.
    const roundIndex = Number(btn.dataset.round);
    if (!state.round || state.round.index !== roundIndex) act('startRound', { index: roundIndex });
    return act('openQuestion', { questionId: btn.dataset.question });
  }
  if (btn.dataset.act) {
    const extra = {};
    if (btn.dataset.team) extra.team = btn.dataset.team;
    if (btn.dataset.delta) extra.delta = Number(btn.dataset.delta);
    if (btn.dataset.correct) extra.correct = true;
    return act(btn.dataset.act, extra);
  }
});

$('missLimit').addEventListener('change', (e) =>
  act('setting', { key: 'missLimit', value: Math.max(1, Number(e.target.value) || 4) }));
$('buzzToReclaim').addEventListener('change', (e) =>
  act('setting', { key: 'buzzToReclaim', value: e.target.checked }));
$('enableSpoiler').addEventListener('change', (e) =>
  act('setting', { key: 'enableSpoiler', value: e.target.checked }));
$('soundOn').addEventListener('change', (e) => setEnabled(e.target.checked));

$('gateInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); submitToken(); }
});

document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, select, textarea')) return;
  if (!$('gate').classList.contains('hidden')) return;
  unlock();
  const k = e.key.toLowerCase();

  // No-network mode: the teacher runs both buzzers from this keyboard.
  if (k === 'a') { e.preventDefault(); return act('giveControl', { team: 'A' }); }
  if (k === 'l') { e.preventDefault(); return act('giveControl', { team: 'B' }); }

  if (k === 'h') { e.preventDefault(); return $('panel').classList.toggle('collapsed'); }
  if (k === 'n') { e.preventDefault(); return act('openQuestion'); }
  if (k === 'b') { e.preventDefault(); return act('reopenBuzzers'); }
  if (k === 'e') { e.preventDefault(); return act('endRound'); }
  if (e.key >= '1' && e.key <= '6') {
    e.preventDefault();
    return act('reveal', { index: Number(e.key) - 1, team: state?.control || null });
  }
});

function submitToken() {
  const value = $('gateInput').value.trim();
  if (!value) return;
  hostToken = value;
  // Put it in the URL so a refresh — or a bookmark — just works.
  const url = new URL(location.href);
  url.searchParams.set('token', value);
  history.replaceState(null, '', url);
  $('gateErr').textContent = '';
  ws.send(JSON.stringify({ type: 'join', role: 'host', token: hostToken }));
}

/* ---------------- helpers ---------------- */

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function truncate(str, n) {
  return str.length > n ? `${str.slice(0, n - 1)}…` : str;
}

connect();

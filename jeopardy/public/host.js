/* Mind Jeopardy — the host's laptop.
 *
 * The whole screen is organised around one question: what should the teacher
 * do right now? The step panel at the top answers it in a sentence and gives
 * the one or two buttons that make sense at this moment. Everything else on
 * the page is reference material. */

import { play, unlock, setEnabled } from '/sfx.js';

const $ = (id) => document.getElementById(id);
let ws, state = null, roster = null, joinCode = '';
let lastVersion = -1, boardWindow = null;
let hostToken = new URLSearchParams(location.search).get('token')
  || sessionStorage.getItem('mindjeopardy.hostToken') || '';

fetch('/api/config').then((r) => r.json()).then((d) => {
  $('aiPill').textContent = d.ai ? 'AI judging on' : 'local judging';
}).catch(() => {});

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);
  ws.onopen = () => ws.send(JSON.stringify({ type: 'join', role: 'host', token: hostToken }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      if (msg.joinCode !== undefined) joinCode = msg.joinCode || '';
      roster = msg.roster;
      onState(msg.state, msg.fx);
    } else if (msg.type === 'accepted') {
      sessionStorage.setItem('mindjeopardy.hostToken', hostToken);
      $('gate').classList.add('hidden');
    } else if (msg.type === 'denied') {
      $('gate').classList.remove('hidden');
      $('gateErr').textContent = hostToken ? msg.reason : '';
      $('gateInput').focus();
    } else if (msg.type === 'toast') {
      flash(msg.text, msg.tone === 'error' ? 'bad' : 'warn');
    }
  };
  ws.onclose = () => setTimeout(connect, 1200);
}

const act = (action, extra = {}) => ws?.send(JSON.stringify({ type: 'host', action, ...extra }));

function onState(next, fx) {
  const isNew = next.version !== lastVersion;
  lastVersion = next.version;
  state = next;
  render();
  if (fx && isNew) play(fx);
}

function flash(text, tone) {
  const el = $('flash');
  el.querySelector('.inner').textContent = text;
  el.className = '';
  void el.offsetWidth;
  el.classList.add('show', tone);
}

const nameOf = (id) => state.teams.find((t) => t.id === id)?.name || '—';

/* ---------------- the step-by-step panel ---------------- */

/**
 * Everything the teacher needs at this instant: a heading, a sentence of
 * detail, and the buttons that are actually valid right now. Anything not
 * valid is simply not rendered, so there is nothing to get wrong live.
 */
function stepFor(s) {
  const btn = (label, action, extra = {}, cls = 'btn big') => ({ label, action, extra, cls });

  switch (s.phase) {
    case 'setup':
      return {
        now: 'Setting up',
        title: s.teams.length < 2 ? 'Add your teams' : `${s.teams.length} teams ready`,
        detail: s.teams.length < 2
          ? 'One team per computer in the room. Add at least two below.'
          : 'Open the projector window and drag it onto the second screen, then start.',
        actions: s.teams.length >= 2 ? [btn('▶ Start the game', 'startGame', {}, 'btn big primary')] : [],
      };

    case 'board':
      return {
        now: 'On the board',
        title: `${nameOf(s.picker)} choose`,
        detail: `Ask them for a category and a value, then click it on the board below. ${s.cluesLeft} clue${s.cluesLeft === 1 ? '' : 's'} left.`,
        actions: [],
      };

    case 'clue':
      return {
        now: 'Clue is up',
        title: 'Read it out loud',
        detail: 'The class can see it on the projector. When you have finished reading, open the buzzers.',
        actions: [btn('🔔 Open the buzzers', 'openBuzzers', {}, 'btn big primary')],
      };

    case 'open':
      return {
        now: 'Buzzers live',
        title: 'Waiting for a buzz',
        detail: 'First team in gets it. If someone clearly shouted first, hand it to them below.',
        actions: s.teams
          .filter((t) => !s.clue.lockedOut.includes(t.id))
          .map((t) => btn(`Give it to ${t.name}`, 'giveClue', { teamId: t.id }, 'btn'))
          .concat([btn('Nobody — show the answer', 'reveal', {}, 'btn')]),
      };

    case 'answering':
      return {
        now: 'Answering',
        title: `${nameOf(s.clue.buzzedBy)} has it`,
        detail: 'They type it on their computer and it is judged automatically — or rule on it yourself.',
        actions: [
          btn('✓ Correct', 'mark', { correct: true }, 'btn big good'),
          btn('✗ Wrong', 'mark', { correct: false }, 'btn big bad'),
        ],
      };

    case 'revealed': {
      const got = s.clue.correctBy;
      return {
        now: 'Answer revealed',
        title: got ? `${nameOf(got)} got it — +${s.clue.value}` : 'Nobody got it',
        detail: 'Read the note below out loud, then go back to the board.',
        actions: [btn('◀ Back to the board', 'backToBoard', {}, 'btn big primary')],
      };
    }

    case 'boardCleared':
      return {
        now: 'Board cleared',
        title: 'Every clue is gone',
        detail: 'Time for Final Jeopardy. Every team wagers, so anyone can still win.',
        actions: [btn('★ Start Final Jeopardy', 'startFinal', {}, 'btn big primary')],
      };

    case 'finalIntro':
      return {
        now: 'Final Jeopardy',
        title: `Announce the category: ${s.final.category}`,
        detail: 'Say the category out loud and let them think. Do not read the clue yet — they wager first.',
        actions: [btn('Open the wagers', 'openWagers', {}, 'btn big primary')],
      };

    case 'finalWager': {
      const waiting = s.final.submitted.filter((x) => !x.wagered);
      return {
        now: 'Final Jeopardy',
        title: waiting.length ? `Waiting on ${waiting.length} team${waiting.length === 1 ? '' : 's'}` : 'All wagers in',
        detail: waiting.length
          ? `Still to wager: ${waiting.map((x) => nameOf(x.id)).join(', ')}. Anyone who does not wager is treated as wagering nothing.`
          : 'Everyone has committed. Show them the clue.',
        actions: [btn('Show the clue', 'openFinalClue', {}, 'btn big primary')],
      };
    }

    case 'finalClue': {
      const waiting = s.final.submitted.filter((x) => !x.answered);
      return {
        now: 'Final Jeopardy',
        title: waiting.length ? `Writing — waiting on ${waiting.length}` : 'All answers in',
        detail: waiting.length
          ? `Still writing: ${waiting.map((x) => nameOf(x.id)).join(', ')}.`
          : 'Everyone has answered. Close it and start the reveal.',
        actions: [btn('Stop writing & reveal', 'closeFinalWriting', {}, 'btn big primary')],
      };
    }

    case 'finalReveal': {
      const next = s.final.revealOrder[0];
      return {
        now: 'The reveal',
        title: next ? `Reveal ${nameOf(next)}` : 'All revealed',
        detail: next
          ? 'Lowest score first. Read out what they wrote, pause, then reveal their wager.'
          : '',
        actions: next ? [btn(`Reveal ${nameOf(next)}`, 'revealFinalTeam', { teamId: next }, 'btn big primary')] : [],
      };
    }

    case 'gameOver':
      return {
        now: 'Finished',
        title: s.winner === 'tie' ? "It's a tie!" : `${nameOf(s.winner)} win`,
        detail: 'Final scores are on the projector. Read the Final Jeopardy note below for the debrief.',
        actions: [],
      };

    default:
      return { now: 'Right now', title: 'Connecting…', detail: '', actions: [] };
  }
}

/* ---------------- render ---------------- */

function render() {
  if (!state) return;
  const s = state;

  $('phasePill').textContent = s.phase;
  $('cluesPill').textContent = s.phase === 'setup' ? '' : `${s.cluesLeft} clues left`;

  const step = stepFor(s);
  $('stepNow').textContent = step.now;
  $('stepTitle').textContent = step.title;
  $('stepDetail').textContent = step.detail;
  const actions = $('stepActions');
  actions.innerHTML = '';
  for (const a of step.actions) {
    const b = document.createElement('button');
    b.className = a.cls;
    b.textContent = a.label;
    b.dataset.act = a.action;
    b.dataset.extra = JSON.stringify(a.extra);
    actions.appendChild(b);
  }

  renderClueCard(s);
  $('setupCard').classList.toggle('hidden', s.phase !== 'setup');
  if (s.phase === 'setup') renderSetupTeams(s);
  $('gridCard').classList.toggle('hidden', !['board', 'boardCleared'].includes(s.phase));
  if (['board', 'boardCleared'].includes(s.phase)) renderHostGrid(s);

  renderScoreTable(s);
  renderFinalPanel(s);

  $('answerSeconds').value = s.settings.answerSeconds;
  $('finalSeconds').value = s.settings.finalSeconds;

  renderLog(s);
}

function renderClueCard(s) {
  const show = s.clue && ['clue', 'open', 'answering', 'revealed'].includes(s.phase);
  const showFinal = s.final && ['finalClue', 'finalReveal', 'gameOver'].includes(s.phase);
  $('clueCard').classList.toggle('hidden', !show && !showFinal);
  if (!show && !showFinal) return;

  if (show) {
    $('clueHead').textContent = `${s.clue.category} — ${s.clue.value}`;
    $('clueTextH').textContent = s.clue.text;
    $('clueAnsH').textContent = s.clue.answer || '';
    const note = $('clueNoteH');
    // The note only appears once the answer is out, so it is never a spoiler
    // sitting in the teacher's eyeline while they are still reading the clue.
    const showNote = s.phase === 'revealed' && s.clue.note;
    note.classList.toggle('hidden', !showNote);
    if (showNote) note.innerHTML = `<b>Say this:</b> ${escapeHtml(s.clue.note)}`;
  } else {
    $('clueHead').textContent = `FINAL JEOPARDY — ${s.final.category}`;
    $('clueTextH').textContent = s.final.text || '';
    $('clueAnsH').textContent = s.final.answer || '';
    const note = $('clueNoteH');
    const showNote = s.phase !== 'finalClue' && s.final.note;
    note.classList.toggle('hidden', !showNote);
    if (showNote) note.innerHTML = `<b>Say this:</b> ${escapeHtml(s.final.note)}`;
  }
}

function renderSetupTeams(s) {
  const t = $('setupTeams');
  t.innerHTML = '';
  for (const team of s.teams) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="nm"></td>
      <td style="width:5rem;text-align:right">
        <button class="btn sm bad" data-act="removeTeam" data-extra='${JSON.stringify({ teamId: team.id })}'>Remove</button>
      </td>`;
    tr.querySelector('.nm').textContent = team.name;
    t.appendChild(tr);
  }
}

function renderHostGrid(s) {
  const g = $('hostGrid');
  const sig = JSON.stringify(s.categories.map((c) => c.clues.map((x) => x.used)));
  if (g.dataset.sig === sig) return;
  g.dataset.sig = sig;
  g.style.gridTemplateColumns = `repeat(${s.categories.length}, 1fr)`;
  g.innerHTML = '';
  for (const c of s.categories) {
    const h = document.createElement('div');
    h.className = 'hcat';
    h.textContent = c.name;
    g.appendChild(h);
  }
  const rows = s.categories[0].clues.length;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < s.categories.length; col++) {
      const cl = s.categories[col].clues[row];
      const b = document.createElement('button');
      b.className = 'hcell';
      b.disabled = cl.used;
      b.dataset.act = 'pickClue';
      b.dataset.extra = JSON.stringify({ categoryIndex: col, clueIndex: row });
      b.innerHTML = `<b>${cl.value}</b><br>`;
      b.appendChild(document.createTextNode(cl.answer || ''));
      g.appendChild(b);
    }
  }
}

function renderScoreTable(s) {
  const t = $('scoreTable');
  t.innerHTML = '';
  for (const team of [...s.teams].sort((a, b) => b.score - a.score)) {
    const connected = roster?.teams?.[team.id] || 0;
    const tr = document.createElement('tr');
    if (s.picker === team.id) tr.className = 'picker';
    tr.innerHTML = `
      <td class="nm"></td>
      <td style="width:2.5rem" class="muted">${connected ? '●' : '○'}</td>
      <td class="sc">${team.score}</td>
      <td style="width:4.5rem;text-align:right">
        <button class="btn sm" data-act="adjust" data-extra='${JSON.stringify({ teamId: team.id, delta: -100 })}'>−</button>
        <button class="btn sm" data-act="adjust" data-extra='${JSON.stringify({ teamId: team.id, delta: 100 })}'>+</button>
      </td>`;
    tr.querySelector('.nm').textContent = team.name;
    tr.querySelector('.nm').title = connected ? `${connected} device(s)` : 'no device connected';
    t.appendChild(tr);
  }
}

function renderFinalPanel(s) {
  const show = Boolean(s.final);
  $('finalCard').classList.toggle('hidden', !show);
  if (!show) return;

  const p = $('finalPanel');
  p.innerHTML = '';
  for (const team of s.teams) {
    const d = s.final.detail[team.id] || {};
    const res = s.final.results[team.id];
    const revealed = s.final.revealed.includes(team.id);
    const row = document.createElement('div');
    row.style.cssText = 'padding:.35rem 0;border-bottom:1px solid var(--edge)';
    row.innerHTML = `
      <div style="display:flex;gap:.4rem;align-items:baseline">
        <b style="flex:1"></b>
        <span class="muted" style="font-size:.75rem">wager</span>
        <span style="color:var(--gold);font-weight:700">${d.wager ?? '—'}</span>
      </div>
      <div style="font-size:.82rem;opacity:.85;margin-top:.15rem">
        ${d.answer !== null && d.answer !== undefined ? `“${escapeHtml(d.answer || '(blank)')}”` : '<span class="muted">not written yet</span>'}
        ${res ? `<b style="color:${res.correct ? 'var(--green)' : 'var(--red)'}"> ${res.correct ? '✓' : '✗'}</b>` : ''}
      </div>`;
    row.querySelector('b').textContent = team.name;

    // Before a team is revealed the host can overrule the automatic ruling.
    if (s.phase === 'finalReveal' && !revealed) {
      const controls = document.createElement('div');
      controls.className = 'row';
      controls.style.marginTop = '.3rem';
      controls.innerHTML = `
        <button class="btn sm good" data-act="revealFinalTeam" data-extra='${JSON.stringify({ teamId: team.id, correct: true })}'>Reveal as ✓</button>
        <button class="btn sm bad" data-act="revealFinalTeam" data-extra='${JSON.stringify({ teamId: team.id, correct: false })}'>Reveal as ✗</button>`;
      row.appendChild(controls);
    }
    p.appendChild(row);
  }
}

function renderLog(s) {
  const log = $('log');
  log.innerHTML = '';
  for (const ev of s.log || []) {
    const li = document.createElement('li');
    li.className = ev.kind;
    let body = '';
    switch (ev.kind) {
      case 'correct': body = `${ev.name}: “${ev.text}” ✓ +${ev.value}`; break;
      case 'wrong': body = `${ev.name}: “${ev.text}” ✗`; break;
      case 'timeUp': body = `${ev.name} ran out of time`; break;
      case 'buzz': body = `${ev.name} buzzed in`; break;
      case 'clueUp': body = `${ev.category} — ${ev.value}`; break;
      case 'finalCorrect': body = `${ev.name} ✓ +${ev.wager}`; break;
      case 'finalWrong': body = `${ev.name} ✗ −${ev.wager}`; break;
      case 'wager': body = `${ev.name} locked a wager`; break;
      case 'finalAnswer': body = `${ev.name} submitted`; break;
      case 'adjust': body = `${ev.name} ${ev.delta > 0 ? '+' : ''}${ev.delta} by hand`; break;
      default: body = ev.kind;
    }
    li.textContent = body;
    if (ev.source && ev.source !== 'local') {
      const why = document.createElement('div');
      why.className = 'why';
      why.textContent = `judged by ${ev.source}`;
      li.appendChild(why);
    }
    log.appendChild(li);
  }
}

/* ---------------- input ---------------- */

document.addEventListener('click', (e) => {
  unlock();
  const btn = e.target.closest('button');
  if (!btn) return;

  if (btn.id === 'gateBtn') return submitToken();
  if (btn.id === 'openBoard') return openProjector();
  if (btn.id === 'addTeamBtn') return addTeam();
  if (btn.id === 'resetBtn') {
    if (confirm('Reset teams, scores and the whole board?')) act('reset');
    return;
  }
  if (btn.dataset.act) {
    const extra = btn.dataset.extra ? JSON.parse(btn.dataset.extra) : {};
    return act(btn.dataset.act, extra);
  }
});

/** Opens the projector window carrying the host key, so it is never gated. */
function openProjector() {
  const url = `/board${hostToken ? `?token=${encodeURIComponent(hostToken)}` : ''}`;
  boardWindow = window.open(url, 'mindjeopardy-board', 'width=1280,height=800');
  if (!boardWindow) {
    alert('Your browser blocked the pop-up. Allow pop-ups for this site, or open '
      + `${location.origin}${url} in a new window yourself.`);
  }
}

function addTeam() {
  const input = $('teamNameInput');
  const name = input.value.trim();
  if (!name) return input.focus();
  act('addTeam', { name });
  input.value = '';
  input.focus();
}

$('teamNameInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); addTeam(); }
});
$('gateInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); submitToken(); }
});
$('answerSeconds').addEventListener('change', (e) =>
  act('setting', { key: 'answerSeconds', value: Math.max(0, Number(e.target.value) || 0) }));
$('finalSeconds').addEventListener('change', (e) =>
  act('setting', { key: 'finalSeconds', value: Math.max(10, Number(e.target.value) || 60) }));
$('soundOn').addEventListener('change', (e) => setEnabled(e.target.checked));

// The primary action is always on the space bar, so the teacher can drive the
// whole game without hunting for a button.
document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, select, textarea')) return;
  if (!$('gate').classList.contains('hidden')) return;
  if (e.code === 'Space') {
    const primary = $('stepActions').querySelector('.primary') || $('stepActions').querySelector('button');
    if (primary) { e.preventDefault(); primary.click(); }
    return;
  }
  if (state?.phase === 'answering') {
    if (e.key === 'y' || e.key === 'Y') { e.preventDefault(); act('mark', { correct: true }); }
    if (e.key === 'n' || e.key === 'N') { e.preventDefault(); act('mark', { correct: false }); }
  }
});

function submitToken() {
  const value = $('gateInput').value.trim();
  if (!value) return;
  hostToken = value;
  const url = new URL(location.href);
  url.searchParams.set('token', value);
  history.replaceState(null, '', url);
  $('gateErr').textContent = '';
  ws.send(JSON.stringify({ type: 'join', role: 'host', token: hostToken }));
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

connect();

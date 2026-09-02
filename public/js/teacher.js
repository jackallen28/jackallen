(() => {
  const socket = io();
  const $ = (id) => document.getElementById(id);

  let catalog = [];
  let personaCatalog = [];
  const mixState = new Map();     // model id -> { on, weight }
  const personaState = new Map(); // persona id -> on

  let latest = null;              // last teacher:state
  let postStage = 'reveal';       // which post-round screen we are on
  let downloaded = false;
  let clockTimer = null;
  let endsAt = null;

  const STAGES = ['setup', 'lobby', 'running', 'answering', 'reveal', 'scores', 'report', 'startover'];
  // Which dot in the progress bar each stage lights up.
  const STEP_OF = {
    setup: 'setup', lobby: 'lobby', running: 'running', answering: 'reveal',
    reveal: 'reveal', scores: 'scores', report: 'report', startover: 'report',
  };

  // -------------------------------------------------------------------- auth

  function unlock() {
    const passcode = $('passcode').value;
    socket.emit('teacher:auth', { passcode }, (res) => {
      if (!res?.ok) {
        $('auth-error').textContent = res?.error || 'Could not unlock.';
        return;
      }
      sessionStorage.setItem('hon-teacher', passcode);
      $('screen-auth').classList.add('hidden');
      $('screen-dash').classList.remove('hidden');
      $('bot-warning').classList.toggle('hidden', Boolean(res.liveBot));

      catalog = res.models || [];
      personaCatalog = res.personas || [];
      $('persona-block').classList.toggle('hidden', !res.classroomPack);
      $('voice-note').textContent = res.voiceSamples
        ? `Voice: bots also copy ${res.voiceSamples} of your writing samples.`
        : '';
      showJoinUrls(res.joinUrls);
      buildMixer();
      buildPersonaPicker();
    });
  }

  $('auth-btn').addEventListener('click', unlock);
  $('passcode').addEventListener('keydown', (e) => { if (e.key === 'Enter') unlock(); });
  socket.on('connect', () => {
    const saved = sessionStorage.getItem('hon-teacher');
    if (saved) { $('passcode').value = saved; unlock(); }
  });

  function showJoinUrls(urls) {
    const text = urls && urls.length ? urls[0] : `${location.host}/`;
    $('join-url').textContent = text;
    $('join-url-2').textContent = text;
    if (urls && urls.length > 1) $('join-url').title = `Also: ${urls.slice(1).join(', ')}`;
  }

  // ------------------------------------------------------------------ roster

  $('roster-btn').addEventListener('click', () => $('roster-file').click());

  $('roster-file').addEventListener('change', (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      socket.emit('teacher:roster', { csv: String(reader.result || '') }, (res) => {
        if (!res?.ok) {
          $('roster-issues').innerHTML = `<span style="color:var(--danger)">${res?.error || 'Could not read that file.'}</span>`;
          return;
        }
        renderRosterIssues(res);
      });
      $('roster-file').value = '';
    };
    reader.readAsText(file);
  });

  $('roster-clear').addEventListener('click', () => {
    socket.emit('teacher:clearRoster', {}, () => { $('roster-issues').innerHTML = ''; });
  });

  function renderRosterIssues(res) {
    const bits = [];
    if (res.duplicates?.length) {
      bits.push(`<div style="color:var(--ai)">${res.duplicates.length} duplicate login(s) ignored: ${res.duplicates.slice(0, 5).join(', ')}</div>`);
    }
    if (res.errors?.length) {
      bits.push(`<div style="color:var(--danger)">${res.errors.length} row(s) skipped:</div>` +
        res.errors.slice(0, 5).map((e) => `<div class="muted">${e}</div>`).join(''));
    }
    $('roster-issues').innerHTML = bits.join('');
  }

  // ------------------------------------------------------------- model mixer

  $('ratio').addEventListener('input', (e) => { $('ratio-label').textContent = `${e.target.value}%`; });

  function buildMixer() {
    const host = $('model-mix');
    host.innerHTML = '';
    for (const model of catalog) {
      if (!mixState.has(model.id)) mixState.set(model.id, { on: true, weight: 1 });
      const state = mixState.get(model.id);

      const row = document.createElement('div');
      row.className = 'mix-row';
      row.dataset.model = model.id;

      const toggle = document.createElement('input');
      toggle.type = 'checkbox';
      toggle.checked = state.on;
      toggle.id = `mix-${model.id}`;
      toggle.setAttribute('aria-label', `Use ${model.label}`);

      const name = document.createElement('div');
      name.innerHTML = `<div class="name">${model.label}</div><div class="blurb">${model.blurb}</div>`;

      const weight = document.createElement('input');
      weight.type = 'range';
      weight.min = '1'; weight.max = '5'; weight.step = '1';
      weight.value = String(state.weight);
      weight.setAttribute('aria-label', `${model.label} share`);

      const share = document.createElement('div');
      share.className = 'share';

      toggle.addEventListener('change', () => { state.on = toggle.checked; refreshMixer(); });
      weight.addEventListener('input', () => { state.weight = Number(weight.value); refreshMixer(); });

      row.append(toggle, name, weight, share);
      host.appendChild(row);
    }
    refreshMixer();
  }

  function currentMix() {
    const mix = {};
    for (const [id, state] of mixState) if (state.on) mix[id] = state.weight;
    return mix;
  }

  function refreshMixer() {
    const mix = currentMix();
    const total = Object.values(mix).reduce((sum, w) => sum + w, 0);
    const active = Object.keys(mix).length;
    for (const row of document.querySelectorAll('#model-mix .mix-row')) {
      const state = mixState.get(row.dataset.model);
      row.classList.toggle('off', !state.on);
      row.querySelector('.share').textContent =
        state.on && total ? `${Math.round((state.weight / total) * 100)}%` : '—';
    }
    $('mix-summary').textContent = active === 0 ? 'none selected'
      : active === 1 ? '1 model' : `${active} models, split by share`;
    $('mix-warning').textContent = active === 0 ? 'Pick at least one model.' : '';
    $('mix-warning').style.color = active === 0 ? 'var(--danger)' : '';
    refreshOpenButton();
  }

  // ----------------------------------------------------------- persona picker

  function buildPersonaPicker() {
    const host = $('persona-pick');
    host.innerHTML = '';
    for (const persona of personaCatalog) {
      if (!personaState.has(persona.id)) personaState.set(persona.id, true);

      const row = document.createElement('div');
      row.className = 'mix-row';
      row.style.gridTemplateColumns = '22px 1fr';
      row.dataset.persona = persona.id;

      const toggle = document.createElement('input');
      toggle.type = 'checkbox';
      toggle.checked = personaState.get(persona.id);
      toggle.id = `persona-${persona.id}`;
      toggle.setAttribute('aria-label', `Use persona ${persona.id}`);
      toggle.addEventListener('change', () => {
        personaState.set(persona.id, toggle.checked);
        refreshPersonaPicker();
      });

      const name = document.createElement('div');
      name.innerHTML = `<div class="name">${persona.id} — ${persona.label}</div>`;
      row.append(toggle, name);
      host.appendChild(row);
    }
    refreshPersonaPicker();
  }

  function currentPersonaMix() {
    const mix = {};
    for (const [id, on] of personaState) if (on) mix[id] = 1;
    return mix;
  }

  function refreshPersonaPicker() {
    const active = Object.keys(currentPersonaMix()).length;
    for (const row of document.querySelectorAll('#persona-pick .mix-row')) {
      row.classList.toggle('off', !personaState.get(row.dataset.persona));
    }
    $('persona-summary').textContent = active === 0
      ? 'none selected' : `${active} of ${personaCatalog.length} in play`;
    $('persona-warning').textContent = active === 0 ? 'Pick at least one, or all will be used.' : '';
  }

  function refreshOpenButton() {
    $('open-btn').disabled = Object.keys(currentMix()).length === 0;
  }

  // ---------------------------------------------------------------- commands

  function command(event, payload) {
    $('dash-error').textContent = '';
    socket.emit(event, payload || {}, (res) => {
      if (res && res.ok === false) $('dash-error').textContent = res.error || 'That did not work.';
    });
  }

  $('open-btn').addEventListener('click', () => command('teacher:openLobby'));
  $('begin-btn').addEventListener('click', () => command('teacher:start', {
    durationSec: Number($('duration').value),
    aiRatio: Number($('ratio').value) / 100,
    modelMix: currentMix(),
    personaMix: currentPersonaMix(),
  }));
  $('end-btn').addEventListener('click', () => command('teacher:end'));
  $('reveal-btn').addEventListener('click', () => {
    postStage = 'reveal';
    command('teacher:results');
  });
  $('to-scores-btn').addEventListener('click', () => { postStage = 'scores'; render(); });
  $('to-report-btn').addEventListener('click', () => { postStage = 'report'; render(); });
  $('to-startover-btn').addEventListener('click', () => { postStage = 'startover'; render(); });
  $('back-report-btn').addEventListener('click', () => { postStage = 'report'; render(); });

  $('startover-btn').addEventListener('click', () => {
    const warning = downloaded
      ? 'Wipe every login, student number, message and result?'
      : 'You have NOT downloaded the report yet, and nothing is saved on the server.\n\nWipe everything anyway?';
    if (!confirm(warning)) return;
    postStage = 'reveal';
    downloaded = false;
    $('zip-note').textContent = '';
    command('teacher:startOver');
  });

  // ------------------------------------------------------------------ report

  $('zip-btn').addEventListener('click', () => {
    $('zip-note').textContent = 'Building…';
    socket.emit('teacher:report', {}, (res) => {
      if (!res?.ok) {
        $('zip-note').textContent = res?.error || 'Could not build the report.';
        return;
      }
      const bytes = Uint8Array.from(atob(res.zipBase64), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = res.zipName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      downloaded = true;
      $('zip-note').textContent = `Saved ${res.zipName} — report, spreadsheet and transcripts inside.`;
    });
  });

  // ------------------------------------------------------------------- clock

  function startClock() { stopClock(); tick(); clockTimer = setInterval(tick, 250); }
  function stopClock() { if (clockTimer) clearInterval(clockTimer); clockTimer = null; }

  function tick() {
    const el = $('big-clock');
    if (!endsAt) { el.textContent = '—'; return; }
    const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
    el.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
    el.classList.toggle('warn', left <= 30 && left > 10);
    el.classList.toggle('critical', left <= 10);
    if (left <= 0) stopClock();
  }

  // ------------------------------------------------------------------ render

  socket.on('teacher:state', (state) => {
    const wasResults = latest?.phase === 'results';
    latest = state;
    // Entering the post-round screens always starts at the reveal.
    if (state.phase === 'results' && !wasResults) postStage = 'reveal';
    render();
  });

  function currentStage() {
    if (!latest) return 'setup';
    if (latest.phase === 'setup') return 'setup';
    if (latest.phase === 'lobby') return 'lobby';
    if (latest.phase === 'active') return 'running';
    if (latest.phase === 'guess') return 'answering';
    return postStage;
  }

  function render() {
    if (!latest) return;
    const stage = currentStage();

    for (const name of STAGES) {
      const el = $(`stage-${name}`);
      if (el) el.classList.toggle('hidden', name !== stage);
    }
    for (const li of $('steps').children) {
      li.classList.toggle('on', li.dataset.step === STEP_OF[stage]);
    }
    $('join-line').classList.toggle('hidden', !['setup', 'lobby'].includes(stage));

    endsAt = latest.endsAt;
    if (stage === 'running') startClock(); else stopClock();

    renderRosterStatus();
    renderLobby();
    renderRunning();
    if (stage === 'answering') {
      $('answered-count').textContent = `${latest.stats.answered}/${latest.stats.paired}`;
    }
    if (stage === 'reveal') renderPairs();
    if (stage === 'scores') renderScores();
    if (stage === 'startover') {
      $('download-warning').textContent = downloaded
        ? '' : 'You have not downloaded the report for this round yet.';
    }
  }

  function renderRosterStatus() {
    const roster = latest.roster || { size: 0 };
    $('roster-status').innerHTML = roster.size
      ? `<strong>${roster.size}</strong> logins loaded. Only these will be accepted.`
      : 'No list uploaded — any correctly formatted login will work.';
    $('roster-clear').classList.toggle('hidden', !roster.size);
  }

  function renderLobby() {
    const grid = $('code-grid');
    const students = latest.students || [];
    $('lobby-count').textContent = students.length;
    $('lobby-of').textContent = latest.roster?.size ? `of ${latest.roster.size} on the list` : '';
    $('lobby-empty').classList.toggle('hidden', students.length > 0);
    $('begin-btn').disabled = students.length === 0;

    const shown = new Set([...grid.children].map((el) => el.dataset.code));
    for (const student of students) {
      if (shown.has(student.code)) {
        grid.querySelector(`[data-code="${student.code}"]`)
          ?.classList.toggle('offline', !student.connected);
        continue;
      }
      const chip = document.createElement('div');
      chip.className = `code-chip${student.connected ? '' : ' offline'}`;
      chip.dataset.code = student.code;
      chip.innerHTML = `<div class="who">${student.student}</div><div class="sub">${student.code}</div><span class="dot"></span>`;
      grid.appendChild(chip);
    }
    for (const el of [...grid.children]) {
      if (!students.some((s) => s.code === el.dataset.code)) el.remove();
    }
  }

  function renderRunning() {
    $('run-students').textContent = latest.stats.paired;
    $('run-messages').textContent = (latest.students || [])
      .reduce((sum, s) => sum + (s.messagesSent || 0), 0);
  }

  function renderPairs() {
    const host = $('pairs');
    host.innerHTML = '';
    for (const [index, pair] of (latest.pairs || []).entries()) {
      const card = document.createElement('div');
      card.className = `pair ${pair.type}`;
      card.style.animationDelay = `${Math.min(index * 90, 1200)}ms`;

      if (pair.type === 'ai') {
        card.innerHTML = `
          <div class="side"><div class="face">🧑</div><div class="who">${pair.members[0].student}</div></div>
          <div class="link">talked to</div>
          <div class="side"><div class="face">🤖</div><div class="who">${pair.modelLabel || 'AI'}</div>
            <div class="sub">${pair.personaLabel || ''}</div></div>`;
      } else {
        card.innerHTML = `
          <div class="side"><div class="face">🧑</div><div class="who">${pair.members[0]?.student || '—'}</div></div>
          <div class="link">talked to</div>
          <div class="side"><div class="face">🧑</div><div class="who">${pair.members[1]?.student || '—'}</div></div>`;
      }
      host.appendChild(card);
    }
  }

  function renderScores() {
    const s = latest.stats;
    $('sc-correct').textContent = s.correct;
    $('sc-wrong').textContent = Math.max(0, s.answered - s.correct);
    $('sc-accuracy').textContent = s.accuracy === null ? '—' : `${s.accuracy}%`;
    $('sc-human').textContent = s.humanAccuracy === null ? '—' : `${s.humanAccuracy}%`;
    $('sc-ai').textContent = s.aiAccuracy === null ? '—' : `${s.aiAccuracy}%`;

    const grid = $('scoregrid');
    grid.innerHTML = '';
    for (const student of (latest.students || []).filter((x) => x.inRound)) {
      const cell = document.createElement('div');
      const status = student.correct === null ? 'none' : student.correct ? 'right' : 'wrong';
      cell.className = `scorecell ${status}`;
      cell.innerHTML = `
        <div class="mark">${status === 'right' ? '✓' : status === 'wrong' ? '✕' : '–'}</div>
        <div class="who">${student.student}</div>
        <div class="sub">${student.partnerType === 'ai'
          ? `${student.modelLabel}${student.persona ? ' · ' + student.persona : ''}`
          : 'peer'}</div>`;
      grid.appendChild(cell);
    }

    fillTable('model-body', latest.byModel || [], (row) => [
      `<strong>${row.label}</strong>`, row.students, row.fooled, row.caught,
      row.foolRate === null ? '—' : `<strong>${row.foolRate}%</strong>`,
      `$${row.costUsd.toFixed(4)}`,
    ]);
    fillTable('persona-body', latest.byPersona || [], (row) => [
      `<strong>${row.id}</strong> <span class="small muted">${row.label}</span>`,
      row.students, row.fooled, row.caught,
      row.foolRate === null ? '—' : `<strong>${row.foolRate}%</strong>`,
    ]);
  }

  function fillTable(id, rows, cellsFor) {
    const body = $(id);
    body.innerHTML = '';
    for (const row of [...rows].sort((a, b) => (b.foolRate ?? -1) - (a.foolRate ?? -1))) {
      const tr = document.createElement('tr');
      for (const html of cellsFor(row)) {
        const td = document.createElement('td');
        td.innerHTML = String(html);
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  }
})();

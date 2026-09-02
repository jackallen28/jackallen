(() => {
  const socket = io();
  const $ = (id) => document.getElementById(id);

  let clockTimer = null;
  let endsAt = null;
  let spoilersShown = false;
  let catalog = [];
  const mixState = new Map(); // model id -> { on, weight }

  const PHASE_LABELS = {
    lobby: 'Lobby',
    active: 'Round running',
    guess: 'Students answering',
    results: 'Results',
  };

  // -------------------------------------------------------------------- auth

  // Replaced with the server's real network address once we unlock — `localhost`
  // is right only on the machine running the server, never for students.
  $('join-url').textContent = `${location.host}/`;

  function showJoinUrls(urls) {
    if (!urls || !urls.length) return;
    const host = $('join-url');
    host.textContent = urls[0];
    if (urls.length > 1) host.title = `Also reachable at: ${urls.slice(1).join(', ')}`;
  }

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
      $('voice-note').textContent = res.voiceSamples
        ? `Voice: bots are copying ${res.voiceSamples} of your own student writing samples.`
        : 'Voice: no writing samples loaded — bots use a generic teenager voice.';
      showJoinUrls(res.joinUrls);
      buildMixer();
    });
  }

  $('auth-btn').addEventListener('click', unlock);
  $('passcode').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') unlock();
  });

  socket.on('connect', () => {
    const saved = sessionStorage.getItem('hon-teacher');
    if (saved) {
      $('passcode').value = saved;
      unlock();
    }
  });

  // ---------------------------------------------------------------- controls

  $('ratio').addEventListener('input', (e) => {
    $('ratio-label').textContent = `${e.target.value}%`;
  });

  // ------------------------------------------------------------- model mixer

  /**
   * One row per model the server offers. Weights are relative, so the server
   * splits the AI-paired students between the ticked models in proportion.
   */
  function buildMixer() {
    const host = $('model-mix');
    host.innerHTML = '';

    for (const model of catalog) {
      if (!mixState.has(model.id)) mixState.set(model.id, { on: true, weight: 1 });
      const state = mixState.get(model.id);

      const row = document.createElement('div');
      row.className = 'mix-row';

      const toggle = document.createElement('input');
      toggle.type = 'checkbox';
      toggle.checked = state.on;
      toggle.id = `mix-${model.id}`;
      toggle.setAttribute('aria-label', `Use ${model.label}`);

      const name = document.createElement('div');
      name.innerHTML = `<div class="name">${model.label}</div><div class="blurb">${model.blurb}</div>`;

      const weight = document.createElement('input');
      weight.type = 'range';
      weight.min = '1';
      weight.max = '5';
      weight.step = '1';
      weight.value = String(state.weight);
      weight.setAttribute('aria-label', `${model.label} share`);

      const share = document.createElement('div');
      share.className = 'share';

      toggle.addEventListener('change', () => {
        state.on = toggle.checked;
        refreshMixer();
      });
      weight.addEventListener('input', () => {
        state.weight = Number(weight.value);
        refreshMixer();
      });

      row.append(toggle, name, weight, share);
      row.dataset.model = model.id;
      host.appendChild(row);
    }
    refreshMixer();
  }

  /** Enabled models and their weights, as the server expects them. */
  function currentMix() {
    const mix = {};
    for (const [id, state] of mixState) if (state.on) mix[id] = state.weight;
    return mix;
  }

  /** Repaint the share percentages and the enabled/disabled styling. */
  function refreshMixer() {
    const mix = currentMix();
    const total = Object.values(mix).reduce((sum, w) => sum + w, 0);
    const active = Object.keys(mix).length;

    for (const row of document.querySelectorAll('.mix-row')) {
      const id = row.dataset.model;
      const state = mixState.get(id);
      row.classList.toggle('off', !state.on);
      row.querySelector('.share').textContent = state.on && total
        ? `${Math.round((state.weight / total) * 100)}%`
        : '—';
    }

    $('mix-summary').textContent = active === 0
      ? 'none selected'
      : active === 1
        ? `1 model`
        : `${active} models, split by share`;

    $('mix-warning').textContent = active === 0
      ? 'Pick at least one model — AI partners cannot run without one.'
      : '';
    $('mix-warning').style.color = active === 0 ? 'var(--danger)' : '';
    updateStartButton();
  }

  let lastJoined = 0;
  let lastPhase = 'lobby';
  function updateStartButton() {
    $('start-btn').disabled =
      lastPhase === 'active' || lastJoined === 0 || Object.keys(currentMix()).length === 0;
  }

  function command(event, payload) {
    $('dash-error').textContent = '';
    socket.emit(event, payload || {}, (res) => {
      if (res && res.ok === false) $('dash-error').textContent = res.error || 'That did not work.';
    });
  }

  $('start-btn').addEventListener('click', () => {
    spoilersShown = false;
    command('teacher:start', {
      durationSec: Number($('duration').value),
      aiRatio: Number($('ratio').value) / 100,
      modelMix: currentMix(),
    });
  });

  $('end-btn').addEventListener('click', () => command('teacher:end'));
  $('results-btn').addEventListener('click', () => command('teacher:results'));

  $('reset-btn').addEventListener('click', () => {
    const keepStudents = confirm(
      'Start a fresh round?\n\nOK = keep the current students signed in.\nCancel = also clear the whole roster.'
    );
    spoilersShown = false;
    $('transcripts').innerHTML = '';
    command('teacher:reset', { keepStudents });
  });

  $('spoiler-btn').addEventListener('click', () => {
    spoilersShown = !spoilersShown;
    applySpoilers();
  });

  function applySpoilers() {
    document.querySelectorAll('.spoiler').forEach((el) => el.classList.toggle('shown', spoilersShown));
    $('spoiler-btn').textContent = spoilersShown ? '🙈 Hide pairings' : '👁 Reveal pairings';
    $('spoiler-note').classList.toggle('hidden', spoilersShown);
  }

  $('transcript-btn').addEventListener('click', () => {
    socket.emit('teacher:transcripts', {}, (res) => {
      if (!res?.ok) return;
      const host = $('transcripts');
      host.innerHTML = '';
      if (!res.transcripts.length) {
        host.innerHTML = '<p class="muted small">No conversations to show yet.</p>';
        return;
      }
      for (const conv of res.transcripts) {
        const box = document.createElement('div');
        box.className = 'transcript';
        const who = conv.type === 'ai'
          ? `${conv.members[0]} ↔ ${conv.modelLabel || 'AI'}`
          : conv.members.join(' ↔ ');
        const head = document.createElement('div');
        head.innerHTML =
          `<strong>${who}</strong> <span class="pill ${conv.type}">${conv.type === 'ai' ? conv.modelLabel || 'AI' : 'Human'}</span>`;
        head.style.marginBottom = '8px';
        box.appendChild(head);

        if (!conv.messages.length) {
          const empty = document.createElement('div');
          empty.className = 'line muted';
          empty.textContent = 'No messages were sent.';
          box.appendChild(empty);
        }
        for (const message of conv.messages) {
          const line = document.createElement('div');
          line.className = 'line';
          const who = document.createElement('span');
          who.className = 'who';
          who.textContent = `${message.sender}: `;
          line.appendChild(who);
          line.appendChild(document.createTextNode(message.text));
          box.appendChild(line);
        }
        host.appendChild(box);
      }
    });
  });

  // ------------------------------------------------------------------- clock

  function startClock() {
    stopClock();
    tick();
    clockTimer = setInterval(tick, 250);
  }

  function stopClock() {
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
  }

  function tick() {
    const el = $('dash-clock');
    if (!endsAt) {
      el.textContent = '—';
      el.className = 'clock';
      return;
    }
    const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
    el.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
    el.classList.toggle('warn', left <= 30 && left > 10);
    el.classList.toggle('critical', left <= 10);
    if (left <= 0) stopClock();
  }

  // -------------------------------------------------------------------- render

  socket.on('teacher:state', (state) => {
    $('phase-pill').textContent = PHASE_LABELS[state.phase] || state.phase;
    $('phase-pill').className = `pill ${state.phase === 'active' ? 'human' : ''}`;

    endsAt = state.endsAt;
    if (state.phase === 'active') startClock();
    else {
      stopClock();
      tick();
    }

    lastPhase = state.phase;
    lastJoined = state.stats.joined;
    updateStartButton();
    $('end-btn').disabled = state.phase !== 'active';
    $('results-btn').disabled = state.phase !== 'guess';

    const s = state.stats;
    $('stat-joined').textContent = s.joined;
    $('stat-paired').textContent = s.paired;
    $('stat-human').textContent = s.withHuman;
    $('stat-ai').textContent = s.withAi;
    $('stat-answered').textContent = `${s.answered}/${s.paired}`;
    $('stat-accuracy').textContent = s.accuracy === null ? '—' : `${s.accuracy}%`;
    $('acc-human').textContent = s.humanAccuracy === null ? '—' : `${s.humanAccuracy}%`;
    $('acc-ai').textContent = s.aiAccuracy === null ? '—' : `${s.aiAccuracy}%`;

    const inLobby = state.phase === 'lobby';
    $('lobby-panel').classList.toggle('hidden', !inLobby);
    $('round-panel').classList.toggle('hidden', inLobby);
    $('model-panel').classList.toggle('hidden', inLobby || !(state.byModel || []).length);
    renderModels(state.byModel || []);
    $('transcript-panel').classList.toggle('hidden', state.phase === 'lobby' || state.phase === 'active');

    if (inLobby) renderLobby(state.students);
    else renderRound(state.students);
  });

  function renderLobby(students) {
    const grid = $('code-grid');
    $('lobby-empty').classList.toggle('hidden', students.length > 0);
    grid.innerHTML = '';
    for (const student of students) {
      const chip = document.createElement('div');
      chip.className = `code-chip${student.connected ? '' : ' offline'}`;
      chip.title = student.connected ? 'Connected' : 'Disconnected';
      chip.textContent = student.code;
      const dot = document.createElement('span');
      dot.className = 'dot';
      chip.appendChild(dot);
      chip.addEventListener('dblclick', () => {
        if (confirm(`Remove student ${student.code}?`)) {
          socket.emit('teacher:remove', { code: student.code }, () => {});
        }
      });
      grid.appendChild(chip);
    }
  }

  function renderRound(students) {
    const body = $('round-body');
    body.innerHTML = '';

    for (const student of students) {
      const tr = document.createElement('tr');

      const code = document.createElement('td');
      code.innerHTML = `<strong>${student.code}</strong>`;
      tr.appendChild(code);

      const status = document.createElement('td');
      status.innerHTML = student.inRound
        ? student.connected
          ? '<span class="small">Online</span>'
          : '<span class="small" style="color:var(--danger)">Dropped</span>'
        : '<span class="small muted">Not in round</span>';
      tr.appendChild(status);

      const partner = document.createElement('td');
      partner.className = 'spoiler';
      partner.innerHTML = student.inRound
        ? student.partnerType === 'ai'
          ? '<span class="pill ai">AI bot</span>'
          : `<span class="pill human">Peer</span> <span class="small muted">${student.partner}</span>`
        : '<span class="muted">—</span>';
      tr.appendChild(partner);

      const model = document.createElement('td');
      model.className = 'spoiler';
      model.innerHTML = student.modelLabel
        ? `<span class="small">${student.modelLabel}</span>`
        : '<span class="muted">—</span>';
      tr.appendChild(model);

      const sent = document.createElement('td');
      sent.textContent = student.inRound ? student.messagesSent : '—';
      tr.appendChild(sent);

      const guess = document.createElement('td');
      guess.innerHTML = student.guess
        ? student.guess === 'ai'
          ? '<span class="pill ai">Said AI</span>'
          : '<span class="pill human">Said peer</span>'
        : '<span class="small muted">waiting…</span>';
      tr.appendChild(guess);

      const result = document.createElement('td');
      result.className = 'spoiler';
      result.innerHTML =
        student.correct === null
          ? '<span class="muted">—</span>'
          : student.correct
            ? '<span class="pill good">✓ Correct</span>'
            : '<span class="pill bad">✕ Wrong</span>';
      tr.appendChild(result);

      body.appendChild(tr);
    }

    applySpoilers();
  }

  function renderModels(rows) {
    const body = $('model-body');
    body.innerHTML = '';

    for (const row of [...rows].sort((a, b) => (b.foolRate ?? -1) - (a.foolRate ?? -1))) {
      const tr = document.createElement('tr');
      const cells = [
        `<strong>${row.label}</strong>`,
        row.students,
        row.answered,
        row.fooled,
        row.caught,
        row.foolRate === null ? '<span class="muted">—</span>' : `<strong>${row.foolRate}%</strong>`,
        `<span class="small muted">${row.tokensIn.toLocaleString()} / ${row.tokensOut.toLocaleString()}</span>`,
        `<span class="small">$${row.costUsd.toFixed(4)}</span>`,
      ];
      for (const html of cells) {
        const td = document.createElement('td');
        td.innerHTML = String(html);
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  }

  // ----------------------------------------------------------------- reports

  function download(filename, text, mime) {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Revoke on the next tick so the download has already started.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function requestReport(format) {
    $('dash-error').textContent = '';
    socket.emit('teacher:report', {}, (res) => {
      if (!res?.ok) {
        $('dash-error').textContent = res?.error || 'Could not build the report.';
        return;
      }
      if (format === 'csv') download(res.csvName, res.csv, 'text/csv;charset=utf-8');
      else download(res.htmlName, res.html, 'text/html;charset=utf-8');
    });
  }

  $('report-html-btn').addEventListener('click', () => requestReport('html'));
  $('report-csv-btn').addEventListener('click', () => requestReport('csv'));
})();

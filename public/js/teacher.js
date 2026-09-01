(() => {
  const socket = io();
  const $ = (id) => document.getElementById(id);

  let clockTimer = null;
  let endsAt = null;
  let spoilersShown = false;

  const PHASE_LABELS = {
    lobby: 'Lobby',
    active: 'Round running',
    guess: 'Students answering',
    results: 'Results',
  };

  // -------------------------------------------------------------------- auth

  $('join-url').textContent = `${location.host}/`;

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
        const who = conv.type === 'ai' ? `${conv.members[0]} ↔ AI bot` : conv.members.join(' ↔ ');
        const head = document.createElement('div');
        head.innerHTML =
          `<strong>${who}</strong> <span class="pill ${conv.type}">${conv.type === 'ai' ? 'AI' : 'Human'}</span>`;
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

    $('start-btn').disabled = state.phase === 'active' || state.stats.joined === 0;
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
        ? `<span class="pill ${student.partnerType}">${student.partnerType === 'ai' ? 'AI bot' : 'Peer'}</span> <span class="small muted">${student.partner}</span>`
        : '<span class="muted">—</span>';
      tr.appendChild(partner);

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
})();

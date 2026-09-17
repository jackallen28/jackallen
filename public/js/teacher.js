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

  // ----------------------------------------------------------------- helpers

  /** Wire a hidden file input to a button, and read the chosen file as text. */
  function fileButton(buttonId, inputId, onText) {
    $(buttonId).addEventListener('click', () => $(inputId).click());
    $(inputId).addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => onText(String(reader.result || ''), file.name);
      reader.readAsText(file);
      $(inputId).value = '';
    });
  }

  /** Hand a file to the browser to save. */
  function saveFile(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const escapeHtml = (value) => String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // ----------------------------------------------------- class context & save

  fileButton('context-btn', 'context-file', (markdown) => {
    socket.emit('teacher:context', { markdown }, (res) => {
      if (!res?.ok) {
        $('context-status').innerHTML = `<span style="color:var(--danger)">${escapeHtml(res?.error || 'Could not read that file.')}</span>`;
        return;
      }
      // The state push that follows renders the loaded context; the response is
      // only needed to surface headings the file had that the app did not use.
      if (res.context?.unknownHeadings?.length) {
        $('load-status').innerHTML = `<span style="color:var(--warn)">Heading(s) not recognised and ignored: ${escapeHtml(res.context.unknownHeadings.join(', '))}. Keep the template's headings.</span>`;
      } else {
        $('load-status').textContent = '';
      }
    });
  });

  $('context-clear').addEventListener('click', () => command('teacher:clearContext'));

  fileButton('load-btn', 'load-file', (json, filename) => {
    socket.emit('teacher:load', { json }, (res) => {
      if (!res?.ok) {
        $('load-status').innerHTML = `<span style="color:var(--danger)">${escapeHtml(res?.error || 'Could not load that file.')}</span>`;
        return;
      }
      const when = res.savedAt ? new Date(res.savedAt).toLocaleString() : 'unknown time';
      const bits = [
        `<strong>Loaded ${escapeHtml(res.title || filename)}</strong> (saved ${escapeHtml(when)}):`,
        res.context ? 'class context' : null,
        res.voice ? `${res.voice} learned lines` : null,
        res.roster ? `${res.roster} logins` : null,
        res.rounds ? `${res.rounds} previous round(s)` : null,
        'settings',
      ].filter(Boolean);
      const notes = (res.notes || []).map((n) => `<div style="color:var(--warn)">${escapeHtml(n)}</div>`).join('');
      $('load-status').innerHTML = `<span style="color:var(--human)">${bits.join(' · ')}</span>${notes}`;
      if (res.settings) applySettings(res.settings);
    });
  });

  $('savefile-btn').addEventListener('click', () => {
    socket.emit('teacher:save', {}, (res) => {
      if (!res?.ok) { $('load-status').textContent = res?.error || 'Could not build the save file.'; return; }
      saveFile(new Blob([res.json], { type: 'application/json' }), res.name);
      $('load-status').textContent = `Saved ${res.name}. Load it on this screen next time.`;
    });
  });

  /** Push loaded settings into the controls, so a saved class looks the way it was left. */
  function applySettings(settings) {
    if (settings.durationSec) {
      const select = $('duration');
      if ([...select.options].some((o) => Number(o.value) === settings.durationSec)) {
        select.value = String(settings.durationSec);
      }
    }
    if (typeof settings.aiRatio === 'number') {
      $('ratio').value = String(Math.round(settings.aiRatio * 10) * 10);
      $('ratio-label').textContent = `${$('ratio').value}%`;
    }
    if (settings.modelMix && typeof settings.modelMix === 'object') {
      const total = Object.values(settings.modelMix).reduce((n, w) => n + Number(w || 0), 0);
      for (const [id, state] of mixState) {
        const weight = Number(settings.modelMix[id] || 0);
        state.on = weight > 0;
        // Saved weights are normalised shares; map back onto the 1–5 slider.
        state.weight = weight > 0 && total ? Math.max(1, Math.min(5, Math.round((weight / total) * 5))) : 1;
      }
      buildMixer();
    }
    if (settings.personaMix && typeof settings.personaMix === 'object') {
      for (const [id] of personaState) personaState.set(id, Boolean(settings.personaMix[id]));
      buildPersonaPicker();
    }
  }

  function renderClassStatus() {
    const ctx = latest.classContext;
    if (ctx) {
      $('context-status').innerHTML =
        `<span style="color:var(--human)"><strong>${escapeHtml(ctx.title)}</strong> loaded</span> — ` +
        `${ctx.sections} section${ctx.sections === 1 ? '' : 's'}` +
        (ctx.samples ? `, ${ctx.samples} writing sample${ctx.samples === 1 ? '' : 's'}` : ', no writing samples (the built-in ones are used)') +
        (ctx.blocklist ? `, ${ctx.blocklist} name${ctx.blocklist === 1 ? '' : 's'} blocked` : ', <span style="color:var(--warn)">no names blocked</span>') +
        (ctx.hasSubject ? '' : ', <span style="color:var(--warn)">no subject boundary given</span>');
    } else {
      $('context-status').textContent = 'No class context loaded — using the built-in unit.';
    }
    $('context-clear').classList.toggle('hidden', !ctx);

    const voice = latest.voice || { count: 0 };
    $('voice-status').innerHTML = voice.count
      ? `Class voice: <strong>${voice.count}</strong> learned line${voice.count === 1 ? '' : 's'} from earlier rounds ` +
        `<button id="voice-clear" class="ghost small" style="margin-left:6px">Clear</button>`
      : '';
    $('voice-clear')?.addEventListener('click', () => command('teacher:clearVoice'));

    // A fresh result from the learn step outlives the next state push; the
    // standing summary only fills the gap when there is nothing newer to say.
    if (learnNote) { $('learn-status').textContent = learnNote; return; }
    const rounds = latest.rounds || [];
    $('learn-status').textContent = voice.count
      ? `The bot currently knows ${voice.count} of your class's lines${rounds.length ? ` across ${rounds.length} round(s)` : ''}.`
      : 'Nothing learned yet.';
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
      bits.push(`<div style="color:var(--warn)">${res.duplicates.length} duplicate login(s) ignored: ${res.duplicates.slice(0, 5).join(', ')}</div>`);
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

  // ------------------------------------------------------------------- modal

  let modalResolve = null;

  /**
   * In-page confirmation. Returns a promise for the answer.
   * Used for anything that destroys a round, so the click is always deliberate.
   */
  function askConfirm({ title, body, warn = '', confirmLabel = "Yes, I'm sure" }) {
    $('modal-title').textContent = title;
    $('modal-body').textContent = body;
    $('modal-confirm').textContent = confirmLabel;
    $('modal-warn').textContent = warn;
    $('modal-warn').classList.toggle('hidden', !warn);
    $('modal').classList.remove('hidden');
    $('modal-cancel').focus();
    return new Promise((resolve) => { modalResolve = resolve; });
  }

  function closeModal(answer) {
    $('modal').classList.add('hidden');
    const resolve = modalResolve;
    modalResolve = null;
    if (resolve) resolve(answer);
  }

  $('modal-cancel').addEventListener('click', () => closeModal(false));
  $('modal-confirm').addEventListener('click', () => closeModal(true));
  // Clicking the backdrop or pressing Escape cancels — never confirms.
  $('modal').addEventListener('click', (e) => { if (e.target === $('modal')) closeModal(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalResolve) closeModal(false);
  });

  /** The reset flow, reachable from the header at any point in the lesson. */
  async function confirmReset() {
    const roundStarted = latest && latest.roundNumber > 0;
    const midRound = latest && ['active', 'guess'].includes(latest.phase);

    const ok = await askConfirm({
      title: 'Are you sure?',
      body: midRound
        ? 'A round is running. Resetting ends it immediately and returns every student to the login screen.'
        : 'This wipes every login, student number, message and result, and goes back to the start.',
      warn: roundStarted && !downloaded
        ? 'You have not saved this round\'s files. Nothing is kept on the server — the transcripts, the class context and the learned voice will all be gone.'
        : (latest?.classContext || latest?.voice?.count)
          ? 'The class context and learned voice are wiped too. Save a file first if you want them back.'
          : '',
      confirmLabel: 'Yes, reset everything',
    });
    if (!ok) return;

    postStage = 'reveal';
    downloaded = false;
    $('zip-note').textContent = '';
    $('roster-issues').innerHTML = '';
    $('load-status').textContent = '';
    learnNote = '';
    command('teacher:startOver');
  }

  $('reset-btn').addEventListener('click', confirmReset);

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

  $('startover-btn').addEventListener('click', confirmReset);

  // ------------------------------------------------------------- learn voice

  let learnCandidates = [];
  let learnNote = '';          // the last learn result, shown until the next round

  $('learn-btn').addEventListener('click', () => {
    $('learn-status').textContent = 'Reading the transcripts…';
    socket.emit('teacher:voiceCandidates', {}, (res) => {
      if (!res?.ok) { $('learn-status').textContent = res?.error || 'Could not read the round.'; return; }
      learnCandidates = res.candidates || [];
      if (learnCandidates.length === 0) {
        $('learn-status').textContent = res.dropped
          ? `Nothing new to learn: ${res.dropped} line(s) were dropped for safety (${res.droppedReasons.map((r) => `${r.count} ${r.reason}`).join(', ')}).`
          : 'Nothing new to learn from this round.';
        return;
      }
      openLearnModal(res);
    });
  });

  function openLearnModal(res) {
    $('learn-intro').textContent =
      `${learnCandidates.length} line(s) your students typed this round, with anything identifying already removed. ` +
      `The bot already knows ${res.already} line(s); the limit is ${res.limit}, oldest dropped first.`;
    $('learn-dropped').textContent = res.dropped
      ? `${res.dropped} line(s) were removed automatically: ${res.droppedReasons.map((r) => `${r.count} ${r.reason}`).join(', ')}.`
      : '';
    const list = $('learn-list');
    list.innerHTML = '';
    for (const [index, line] of learnCandidates.entries()) {
      const row = document.createElement('label');
      row.className = 'learn-row';
      row.innerHTML = `<input type="checkbox" checked data-index="${index}"><span>${escapeHtml(line)}</span>`;
      row.querySelector('input').addEventListener('change', (e) => {
        row.classList.toggle('off', !e.target.checked);
        refreshLearnCount();
      });
      list.appendChild(row);
    }
    refreshLearnCount();
    $('learn-modal').classList.remove('hidden');
  }

  function selectedLearnLines() {
    return [...$('learn-list').querySelectorAll('input:checked')].map((el) => learnCandidates[Number(el.dataset.index)]);
  }

  function refreshLearnCount() {
    const n = selectedLearnLines().length;
    $('learn-count').textContent = `${n} of ${learnCandidates.length} selected`;
    $('learn-confirm').disabled = n === 0;
    $('learn-confirm').textContent = n === 0 ? 'Nothing selected' : `Use ${n} line${n === 1 ? '' : 's'}`;
  }

  $('learn-all').addEventListener('click', () => {
    for (const el of $('learn-list').querySelectorAll('input')) { el.checked = true; el.closest('.learn-row').classList.remove('off'); }
    refreshLearnCount();
  });
  $('learn-none').addEventListener('click', () => {
    for (const el of $('learn-list').querySelectorAll('input')) { el.checked = false; el.closest('.learn-row').classList.add('off'); }
    refreshLearnCount();
  });
  $('learn-cancel').addEventListener('click', () => $('learn-modal').classList.add('hidden'));
  $('learn-modal').addEventListener('click', (e) => { if (e.target === $('learn-modal')) $('learn-modal').classList.add('hidden'); });
  $('learn-confirm').addEventListener('click', () => {
    const lines = selectedLearnLines();
    $('learn-modal').classList.add('hidden');
    socket.emit('teacher:voiceCommit', { lines }, (res) => {
      learnNote = res?.ok
        ? `Learned ${res.added} new line(s). The bot now knows ${res.total}. Save all files to keep them.`
        : (res?.error || 'Could not save those lines.');
      $('learn-status').textContent = learnNote;
      downloaded = false;
    });
  });

  $('another-btn').addEventListener('click', async () => {
    if (!downloaded) {
      const ok = await askConfirm({
        title: 'Run another round?',
        body: 'The next round replaces this one\'s transcripts and results on screen. The class context, learned voice and logins are kept.',
        warn: 'You have not saved this round\'s files yet. Nothing is kept on the server.',
        confirmLabel: 'Run another round anyway',
      });
      if (!ok) return;
    }
    postStage = 'reveal';
    downloaded = false;
    learnNote = '';
    $('zip-note').textContent = '';
    command('teacher:anotherRound');
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
      saveFile(new Blob([bytes], { type: 'application/zip' }), res.zipName);
      downloaded = true;
      $('zip-note').textContent = `Saved ${res.zipName} — report, spreadsheet, transcripts and the save file inside.`;
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
    renderClassStatus();
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

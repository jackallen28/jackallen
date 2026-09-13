(() => {
  const socket = io();
  const $ = (id) => document.getElementById(id);
  const { t, applyLanguage } = window.HON_I18N;

  const screens = {
    language: $('screen-language'),
    signin: $('screen-signin'),
    waiting: $('screen-waiting'),
    late: $('screen-late'),
    chat: $('screen-chat'),
    guess: $('screen-guess'),
    reveal: $('screen-reveal'),
    summary: $('screen-summary'),
  };

  let myCode = null;
  let myLang = null;
  let endsAt = null;
  let clockTimer = null;
  let typingTimeout = null;
  let typingSent = false;
  let renderedCount = 0;
  // 'code' = logins issued on cards, 'name' = participants type their own name.
  let joinMode = 'code';

  function show(name) {
    for (const [key, el] of Object.entries(screens)) el.classList.toggle('hidden', key !== name);
  }

  socket.on('session:config', (config) => {
    joinMode = config?.joinMode === 'name' ? 'name' : 'code';
    refreshSignin();
  });

  /** Point the one sign-in field at whichever identity the facilitator chose. */
  function refreshSignin() {
    const byName = joinMode === 'name';
    $('signin-lead').textContent = t(byName ? 'nameLead' : 'signinLead');
    $('code-label').textContent = t(byName ? 'nameLabel' : 'loginLabel');
    $('name-hint').textContent = byName ? t('nameHint') : '';
    codeInput.placeholder = byName ? t('namePlaceholder') : 'WXYZ1234';
    codeInput.maxLength = byName ? 24 : 8;
    codeInput.style.textTransform = byName ? 'none' : 'uppercase';
    codeInput.style.letterSpacing = byName ? 'normal' : '.28em';
    codeInput.style.fontSize = byName ? '1.2rem' : '1.6rem';
  }

  // ----------------------------------------------------------- language gate

  for (const button of document.querySelectorAll('.langbtn')) {
    button.addEventListener('click', () => chooseLanguage(button.dataset.lang));
  }

  function chooseLanguage(lang) {
    myLang = applyLanguage(lang);
    sessionStorage.setItem('hon-lang', myLang);
    refreshSignin();
    show('signin');
    $('code').focus();
  }

  $('back-to-lang').addEventListener('click', () => show('language'));

  // ------------------------------------------------------------------- sign in

  const codeInput = $('code');

  codeInput.addEventListener('input', () => {
    if (joinMode === 'name') return;
    const cleaned = codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    const letters = cleaned.slice(0, 4).replace(/[^A-Z]/g, '');
    const digits = cleaned.slice(letters.length).replace(/\D/g, '').slice(0, 4);
    codeInput.value = letters + digits;
  });
  codeInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') join(); });
  $('join-btn').addEventListener('click', () => join());

  function join(code = codeInput.value.trim()) {
    if (joinMode === 'name') {
      if (!code) { $('signin-error').textContent = t('errNameFormat'); return; }
    } else if (!/^[A-Z]{4}\d{4}$/.test(code.toUpperCase())) {
      $('signin-error').textContent = t('errFormat');
      return;
    }
    $('signin-error').textContent = '';
    socket.emit('student:join', { code, lang: myLang }, (res) => {
      if (!res?.ok) {
        // The server sends a code so the message can be shown in the participant's
        // own language; its English text is the fallback.
        const key = res?.code && `err${res.code.charAt(0).toUpperCase()}${res.code.slice(1)}`;
        const translated = key && t(key) !== key ? t(key) : null;
        $('signin-error').textContent = translated || res?.error || t('errFormat');
        return;
      }
      myCode = res.code || code.toUpperCase();
      sessionStorage.setItem('hon-code', myCode);
    });
  }

  // --------------------------------------------------------------------- chat

  const log = $('log');
  const typingEl = document.createElement('div');
  typingEl.className = 'typing hidden';
  typingEl.innerHTML = '<span></span><span></span><span></span>';
  log.appendChild(typingEl);

  function addBubble({ mine, text }) {
    const el = document.createElement('div');
    el.className = `bubble ${mine ? 'mine' : 'them'}`;
    el.textContent = text;
    log.insertBefore(el, typingEl);
    log.scrollTop = log.scrollHeight;
    renderedCount += 1;
  }

  function renderTranscript(transcript) {
    log.querySelectorAll('.bubble').forEach((b) => b.remove());
    renderedCount = 0;
    for (const message of transcript) addBubble(message);
  }

  $('composer').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('msg');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    stopTyping();
    socket.emit('chat:send', { text }, (res) => {
      if (!res?.ok && res?.error) console.warn(res.error);
    });
  });

  $('msg').addEventListener('input', () => {
    if (!typingSent) { socket.emit('chat:typing', true); typingSent = true; }
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(stopTyping, 1600);
  });

  function stopTyping() {
    clearTimeout(typingTimeout);
    if (typingSent) { socket.emit('chat:typing', false); typingSent = false; }
  }

  socket.on('chat:message', (message) => {
    addBubble(message);
    if (!message.mine) typingEl.classList.add('hidden');
  });

  socket.on('chat:typing', (isTyping) => {
    typingEl.classList.toggle('hidden', !isTyping);
    if (isTyping) log.scrollTop = log.scrollHeight;
  });

  // -------------------------------------------------------------------- clock

  function startClock() { stopClock(); tick(); clockTimer = setInterval(tick, 250); }
  function stopClock() { if (clockTimer) clearInterval(clockTimer); clockTimer = null; }

  function tick() {
    const el = $('chat-clock');
    const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
    el.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
    el.classList.toggle('warn', left <= 30 && left > 10);
    el.classList.toggle('critical', left <= 10);
    if (left <= 0) stopClock();
  }

  // ------------------------------------------------------------------- guess

  $('guess-human').addEventListener('click', () => submitGuess('human'));
  $('guess-ai').addEventListener('click', () => submitGuess('ai'));

  function submitGuess(guess) {
    $('guess-human').disabled = true;
    $('guess-ai').disabled = true;
    socket.emit('guess:submit', { guess }, (res) => {
      if (!res?.ok) {
        $('guess-error').textContent = res?.error || '';
        $('guess-human').disabled = false;
        $('guess-ai').disabled = false;
      }
    });
  }

  function renderReveal(reveal, guess) {
    $('reveal-icon').textContent = reveal.correct ? '🎉' : '😅';
    $('reveal-title').textContent = reveal.correct ? t('revealRight') : t('revealWrong');
    $('reveal-body').innerHTML =
      (reveal.partnerType === 'ai' ? t('wasAi') : t('wasHuman')) +
      `<br><span class="small">${t('youGuessed')} ` +
      `${guess === 'ai' ? t('guessedAi') : t('guessedHuman')}.</span>`;
  }

  function renderSummary(summary) {
    const show = (id, value) => { $(id).textContent = value === null ? '—' : `${value}%`; };
    $('sum-participants').textContent = summary.participants;
    show('sum-accuracy', summary.overall.accuracy);
    show('sum-ai', summary.vsAi.accuracy);
    show('sum-peer', summary.vsPeer.accuracy);
    $('sum-answered').textContent =
      `${summary.overall.correct}/${summary.overall.answered} ${t('ofAnswered')}`;
  }

  // ------------------------------------------------------------- state router

  socket.on('student:state', (state) => {
    if (state.phase === 'signin' || state.phase === 'setup') {
      show(myLang ? 'signin' : 'language');
      return;
    }

    myCode = state.code;
    $('waiting-code').textContent = state.student || state.code;
    $('waiting-count').textContent = state.waitingCount;

    switch (state.phase) {
      case 'lobby':
        stopClock();
        show('waiting');
        break;

      case 'active':
        if (!state.inRound) { show('late'); break; }
        endsAt = state.endsAt;
        if (state.transcript.length !== renderedCount) renderTranscript(state.transcript);
        startClock();
        show('chat');
        $('msg').focus();
        break;

      case 'guess':
      case 'results':
        stopClock();
        if (!state.inRound) { show('late'); break; }
        if (state.classSummary && state.reveal) {
          renderReveal(state.reveal, state.guess);
          renderSummary(state.classSummary);
          show('summary');
        } else if (state.reveal) {
          renderReveal(state.reveal, state.guess);
          show('reveal');
        } else {
          $('guess-human').disabled = false;
          $('guess-ai').disabled = false;
          $('guess-error').textContent = '';
          show('guess');
        }
        break;

      default:
        show(myLang ? 'signin' : 'language');
    }
  });

  socket.on('session:reset', () => {
    sessionStorage.removeItem('hon-code');
    myCode = null;
    stopClock();
    renderTranscript([]);
    codeInput.value = '';
    show(myLang ? 'signin' : 'language');
    $('signin-error').textContent = t('errReset');
  });

  socket.on('student:kicked', () => {
    sessionStorage.removeItem('hon-code');
    myCode = null;
    show(myLang ? 'signin' : 'language');
    $('signin-error').textContent = t('errRemoved');
  });

  // Rejoin automatically after a refresh, keeping the language already chosen.
  socket.on('connect', () => {
    const savedLang = myLang || sessionStorage.getItem('hon-lang');
    if (savedLang) {
      myLang = applyLanguage(savedLang);
      refreshSignin();
      show('signin');
    }
    const saved = myCode || sessionStorage.getItem('hon-code');
    if (saved && myLang) join(saved);
  });

  socket.on('disconnect', () => stopClock());

  // First paint: the language gate, unless this browser already chose one.
  const remembered = sessionStorage.getItem('hon-lang');
  if (remembered) { myLang = applyLanguage(remembered); refreshSignin(); show('signin'); }
  else show('language');
})();

(() => {
  const socket = io();
  const $ = (id) => document.getElementById(id);

  const screens = {
    signin: $('screen-signin'),
    waiting: $('screen-waiting'),
    late: $('screen-late'),
    chat: $('screen-chat'),
    guess: $('screen-guess'),
    reveal: $('screen-reveal'),
  };

  let myCode = null;
  let endsAt = null;
  let clockTimer = null;
  let typingTimeout = null;
  let typingSent = false;
  let renderedCount = 0;

  function show(name) {
    for (const [key, el] of Object.entries(screens)) el.classList.toggle('hidden', key !== name);
  }

  // ------------------------------------------------------------------- sign in

  const codeInput = $('code');

  codeInput.addEventListener('input', () => {
    codeInput.value = codeInput.value.replace(/\D/g, '').slice(0, 6);
  });
  codeInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') join();
  });
  // Wrapped so the click event is not passed in as the `code` argument.
  $('join-btn').addEventListener('click', () => join());

  function join(code = codeInput.value.trim()) {
    if (!/^\d{6}$/.test(code)) {
      $('signin-error').textContent = 'Enter exactly 6 digits.';
      return;
    }
    $('signin-error').textContent = '';
    socket.emit('student:join', { code }, (res) => {
      if (!res?.ok) {
        $('signin-error').textContent = res?.error || 'Could not join.';
        return;
      }
      myCode = code;
      sessionStorage.setItem('hon-code', code);
    });
  }

  // --------------------------------------------------------------------- chat

  const log = $('log');

  function addBubble({ mine, text }) {
    const el = document.createElement('div');
    el.className = `bubble ${mine ? 'mine' : 'them'}`;
    el.textContent = text;
    log.insertBefore(el, typingEl);
    log.scrollTop = log.scrollHeight;
    renderedCount += 1;
  }

  const typingEl = document.createElement('div');
  typingEl.className = 'typing hidden';
  typingEl.innerHTML = '<span></span><span></span><span></span>';
  log.appendChild(typingEl);

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
    if (!typingSent) {
      socket.emit('chat:typing', true);
      typingSent = true;
    }
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(stopTyping, 1600);
  });

  function stopTyping() {
    clearTimeout(typingTimeout);
    if (typingSent) {
      socket.emit('chat:typing', false);
      typingSent = false;
    }
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
    const el = $('chat-clock');
    const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
    const mins = Math.floor(left / 60);
    const secs = String(left % 60).padStart(2, '0');
    el.textContent = `${mins}:${secs}`;
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
        $('guess-error').textContent = res?.error || 'Could not save your answer.';
        $('guess-human').disabled = false;
        $('guess-ai').disabled = false;
      }
    });
  }

  function renderReveal(reveal, guess) {
    const wasAi = reveal.partnerType === 'ai';
    $('reveal-icon').textContent = reveal.correct ? '🎉' : '😅';
    $('reveal-title').textContent = reveal.correct ? 'You got it right' : 'Not this time';
    $('reveal-body').innerHTML = wasAi
      ? 'You were chatting with an <strong>AI bot</strong>.'
      : 'You were chatting with a <strong>real classmate</strong>.';
    $('reveal-body').innerHTML += `<br><span class="small">You guessed ${
      guess === 'ai' ? 'AI bot' : 'classmate'
    }.</span>`;
  }

  // ------------------------------------------------------------- state router

  socket.on('student:state', (state) => {
    if (state.phase === 'signin') {
      show('signin');
      return;
    }

    myCode = state.code;
    $('waiting-code').textContent = state.code;
    $('waiting-count').textContent = state.waitingCount;

    switch (state.phase) {
      case 'lobby':
        stopClock();
        show('waiting');
        break;

      case 'active':
        if (!state.inRound) {
          show('late');
          break;
        }
        endsAt = state.endsAt;
        if (state.transcript.length !== renderedCount) renderTranscript(state.transcript);
        startClock();
        show('chat');
        $('msg').focus();
        break;

      case 'guess':
      case 'results':
        stopClock();
        if (!state.inRound) {
          show('late');
          break;
        }
        if (state.reveal) {
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
        show('signin');
    }
  });

  socket.on('student:kicked', () => {
    sessionStorage.removeItem('hon-code');
    myCode = null;
    show('signin');
    $('signin-error').textContent = 'You were removed from the room.';
  });

  // Rejoin automatically after a refresh or a dropped connection.
  socket.on('connect', () => {
    const saved = myCode || sessionStorage.getItem('hon-code');
    if (saved) join(saved);
  });

  socket.on('disconnect', () => stopClock());
})();

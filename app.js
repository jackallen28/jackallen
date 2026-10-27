'use strict';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { path: 'pi', step: 0, level: 'beginner', view: 'blocks', connections: [false, false, false], hint: 0, running: false, light: 0, timer: null, peek: 'pi' };
const paths = {
  pi: {
    title: 'PiPath · Traffic lights', project: '🚦 Traffic lights', word: 'glow.',
    description: 'Three lights. A few lines of Python. One very satisfying first “I did that.”',
    controller: 'Raspberry Pi', pins: '17 · 27 · 22 · GND',
    connections: ['Red → GPIO 17', 'Amber → GPIO 27', 'Green → GPIO 22'],
    connected: 'Three LEDs, three GPIO pins. Ready for a little Python?',
    filename: 'traffic_lights.py',
    annotations: [
      'The Wiring Wizard breaks a circuit into small connections. You meet each part before you start coding.',
      'Different starting points, the same destination. Beginner support explains each step; Advanced puts the goal first.',
      'A simulator makes the invisible visible. Students can test an idea, see what changed and try again before using real hardware.'
    ],
    levels: {
      beginner: ['Let’s take it one light at a time.', 'First, import LED and create your red light on GPIO 17. Turn it on, wait a moment, then turn it off.'],
      moderate: ['A plan, with room to figure things out.', 'Create your LEDs, then sequence red → green → amber. Use a pause between changes. Try your idea before asking for a hint.'],
      advanced: ['Your challenge: run a traffic-light sequence.', 'Goal: red, green, amber, repeat. Choose your timing. Open a hint if you want one.']
    },
    hints: ['An LED is an output. LED(17) tells Python which GPIO pin your red light uses.', 'red.on() turns the light on. sleep(1.5) gives you time to see it.', 'Try this pattern for each light: light.on(), sleep(1.5), light.off(). Then repeat.'],
    code: '<span class="kw">from</span> gpiozero <span class="kw">import</span> LED\n<span class="kw">from</span> time <span class="kw">import</span> sleep\n\nred = LED(17)\nred.on()  <span class="comment"># a little light!</span>\nsleep(1.5)\nred.off()'
  },
  arduino: {
    title: 'ArduinoPath · Distance sensor', project: '◉ Distance sensor', word: 'sense.',
    description: 'An ultrasonic sensor. A curious coder. Discover how a circuit can notice the world around it.',
    controller: 'Arduino Uno', pins: '5V · GND · TRIG · ECHO',
    connections: ['Power → 5V', 'Signal → pins 6 / 7', 'Ground → GND'],
    connected: 'Power, signal and ground. Your sensor is ready to say hello.',
    filename: 'distance_sensor.ino',
    annotations: [
      'Connect with confidence. The real Wiring Wizard introduces each component, shows the connections and checks the circuit.',
      'Start with blocks, then see the text they represent. Support levels offer different ways into the same project.',
      'Move an object and watch the reading change. This one simple idea can become something bigger, like a Smart Bin.'
    ],
    levels: {
      beginner: ['Let’s help your sensor find its voice.', 'The sensor sends a sound pulse and listens for its echo. Start with a distance block, then print the result.'],
      moderate: ['Measure, notice, respond.', 'Read the distance and show it in the serial monitor. What should happen when an object gets close?'],
      advanced: ['Your challenge: detect something nearby.', 'Goal: read distance, compare it with 20 cm and respond. Choose blocks or text.']
    },
    hints: ['The ultrasonic sensor measures distance by timing the echo of a sound pulse.', 'Use the distance reading in a comparison. A smaller number means the object is closer.', 'Try: if (distance < 20) { /* object nearby */ }. Move the slider and watch the result.'],
    code: '<span class="comment">// Simplified distance-reading idea</span>\n<span class="kw">void</span> loop() {\n  <span class="kw">float</span> distance = readDistanceCm();\n  Serial.println(distance);\n  <span class="kw">if</span> (distance &lt; 20) {\n    <span class="comment">// Something is close. Your move!</span>\n  }\n}'
  }
};
const peekData = {
  pi: {
    title: 'A helpful next step.\nAlways within reach.',
    copy: 'A clear goal, bite-sized steps and a simulator bring Python into the real world.',
    label: 'Inside PiPath', image: 'assets/pipath-screen.webp',
    alt: 'Actual PiPath traffic lights lesson with a step checklist, Python editor and simulated LEDs',
    notes: ['See the traffic-light goal and work through one manageable step at a time.', 'The checklist and Coach help students notice what worked and what to try next.', 'Run Python and watch the simulated lights respond before trying real GPIO hardware.'],
    positions: [[6, 20], [9, 67], [86, 79]],
    video: 'assets/pipath-walkthrough.mp4', videoTitle: 'PiPath · Traffic lights walkthrough'
  },
  blocks: {
    title: 'Big ideas.\nOne block at a time.',
    copy: 'The Smart Bin walkthrough shows how blocks, a circuit view and a simulator work together.',
    label: 'Inside ArduinoPath · Blocks', image: 'assets/arduino-blocks-screen.webp',
    alt: 'Actual ArduinoPath Smart Bin project with visual blocks, guided steps and ultrasonic sensor simulator',
    notes: ['A project is broken into a series of small goals, with a checklist for each step.', 'Visual blocks build a program while the app shows the corresponding C++ underneath.', 'Move the simulated object closer and watch the distance reading change.'],
    positions: [[6, 25], [41, 49], [86, 26]],
    video: 'assets/arduinopath-blocks-walkthrough.mp4', videoTitle: 'ArduinoPath · Smart Bin in blocks'
  },
  text: {
    title: 'Same curiosity.\nA new language.',
    copy: 'See the Smart Bin take shape in text, with scaffolding and the same hands-on feedback.',
    label: 'Inside ArduinoPath · Text', image: 'assets/arduino-text-screen.webp',
    alt: 'Actual ArduinoPath Smart Bin text coding view with lesson instructions, code and simulator',
    notes: ['Clear step goals keep the bigger project from feeling overwhelming.', 'Text coding gives students room to edit, experiment and grow their independence.', 'Code, circuit and feedback stay together, so students can connect cause and effect.'],
    positions: [[6, 23], [44, 38], [85, 28]],
    video: 'assets/arduinopath-text-walkthrough.mp4', videoTitle: 'ArduinoPath · Smart Bin in text'
  }
};

function pressed(selector, attribute, value) {
  $$(selector).forEach(button => button.setAttribute('aria-pressed', String(button.dataset[attribute] === value)));
}
function clearRun() {
  clearTimeout(state.timer);
  state.timer = null;
  state.running = false;
  $$('#traffic-housing i').forEach(light => light.classList.remove('on'));
  $('#toy-car').classList.remove('moving');
  $('#run-button').innerHTML = '<span aria-hidden="true">▶</span> Run my circuit';
}
function resetDemo() {
  clearRun();
  state.connections = [false, false, false];
  state.hint = 0;
  state.level = 'beginner';
  state.view = 'blocks';
  $('#success-message').hidden = true;
  $('#live-readout').textContent = 'Your circuit is ready.';
  renderConnections();
  renderLevel();
  renderView();
  setStage(0);
}
function choosePath(path, shouldScroll = false) {
  state.path = path;
  const data = paths[path];
  pressed('[data-demo]', 'demo', path);
  $('#play-word').textContent = data.word;
  $('#play-description').textContent = data.description;
  $('#demo-app-name').textContent = data.title;
  $('#demo-project').textContent = data.project;
  $('#controller-name').textContent = data.controller;
  $('#connect-description').textContent = path === 'pi' ? 'Tap the connections. Real LEDs also need resistors and a shared ground.' : 'Tap the connections. This taster uses a 5V Arduino Uno.';
  $('#controller-pins-text').textContent = data.pins;
  $('#controller').classList.toggle('arduino', path === 'arduino');
  $('#scene-leds').hidden = path !== 'pi';
  $('#scene-sensor').hidden = path === 'pi';
  $('#traffic-housing').hidden = path !== 'pi';
  $('#road').hidden = path !== 'pi';
  $('#distance-demo').hidden = path === 'pi';
  $('#code-view-switch').hidden = path === 'pi';
  $('#demo-code').innerHTML = data.code;
  $('#code-filename').firstChild.textContent = data.filename + ' ';
  $('#run-title').textContent = path === 'pi' ? 'You’re in the driving seat.' : 'How close is too close?';
  $('#run-description').textContent = path === 'pi' ? 'Press Run and watch your traffic lights cycle.' : 'Press Run, then move the slider to bring the object closer.';
  const range = $('#demo-range');
  range.min = path === 'pi' ? '5' : '2';
  range.max = path === 'pi' ? '30' : '100';
  range.value = path === 'pi' ? '15' : '60';
  $('#range-label').firstChild.textContent = path === 'pi' ? 'Light timing ' : 'Object distance ';
  $('#range-min').textContent = path === 'pi' ? 'QUICK CHANGE' : 'RIGHT UP CLOSE';
  $('#range-max').textContent = path === 'pi' ? 'TAKE YOUR TIME' : 'FAR, FAR AWAY';
  resetDemo();
  updateRange();
  choosePeek(path === 'pi' ? 'pi' : 'blocks');
  if (shouldScroll) $('#playground').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
}
function renderConnections() {
  const data = paths[state.path];
  $('#connection-buttons').replaceChildren();
  data.connections.forEach((label, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = (state.connections[index] ? '✓ ' : '+ ') + label;
    button.setAttribute('aria-pressed', String(state.connections[index]));
    button.addEventListener('click', () => {
      state.connections[index] = !state.connections[index];
      renderConnections();
      $('#connection-buttons').children[index].focus({ preventScroll: true });
    });
    $('#connection-buttons').append(button);
    $(`.wire-${index}`).classList.toggle('connected', state.connections[index]);
  });
  const count = state.connections.filter(Boolean).length;
  $('#connection-status').textContent = count === 3 ? '✓ ' + data.connected : `${count} of 3 connections made. You’ve got this.`;
  $('#connect-next').disabled = count !== 3;
}
function setStage(step, focus = false) {
  if (step !== 2) clearRun();
  state.step = step;
  ['connect', 'code', 'run'].forEach((name, index) => { $(`#stage-${name}`).hidden = index !== step; });
  $$('[data-step]').forEach(button => {
    const active = Number(button.dataset.step) === step;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  $('#annotation-text').textContent = paths[state.path].annotations[step];
  if (focus) {
    const title = $(`#stage-${['connect', 'code', 'run'][step]} h3`);
    title.tabIndex = -1;
    title.focus({ preventScroll: true });
  }
}
function renderLevel() {
  pressed('[data-level]', 'level', state.level);
  const [title, text] = paths[state.path].levels[state.level];
  const heading = document.createElement('strong'); heading.textContent = title;
  const copy = document.createElement('span'); copy.textContent = text;
  $('#level-message').replaceChildren(heading, copy);
  $('#coach-message').textContent = 'Stuck is just a step on the way. Ask for a nudge.';
  $('#hint-button').innerHTML = 'Give me a hint <span>↗</span>';
  state.hint = 0;
}
function renderView() {
  pressed('[data-view]', 'view', state.view);
  const blocks = state.path === 'arduino' && state.view === 'blocks';
  $('#block-code').hidden = !blocks;
  $('.code-editor pre').hidden = blocks;
  $('#block-code').innerHTML = '<div class="code-block">repeat forever</div><div class="code-block indent">set distance to <b>read distance (cm)</b></div><div class="code-block indent">print <b>distance</b> to serial monitor</div><div class="code-block condition indent">if distance &lt; 20</div><div class="code-block indent">something is close ✦</div>';
}
function tick() {
  if (!state.running || state.path !== 'pi') return;
  const sequence = ['red', 'green', 'amber'];
  const light = sequence[state.light % sequence.length];
  $$('#traffic-housing i').forEach(node => node.classList.toggle('on', node.dataset.light === light));
  $('#toy-car').classList.toggle('moving', light === 'green');
  $('#live-readout').textContent = {red: 'Red says stop. Your code made that happen.', green: 'Green means go. Look at you making things move!', amber: 'Amber: get ready for another little loop.'}[light];
  state.light++;
  state.timer = setTimeout(tick, Number($('#demo-range').value) * 100);
}
function updateRange() {
  const value = Number($('#demo-range').value);
  $('#range-output').value = state.path === 'pi' ? `${(value / 10).toFixed(1)} seconds` : `${value} cm`;
  if (state.path === 'arduino') {
    $('#distance-value').textContent = `${value} cm`;
    $('.distance-object').style.left = `${52 - value * .43}%`;
    const close = value < 20;
    $('#sensor-indicator').classList.toggle('near', close && state.running);
    $('#sensor-indicator').textContent = !state.running ? 'READY TO SENSE' : close ? 'OBJECT DETECTED!' : 'ALL CLEAR';
    if (state.running) $('#live-readout').textContent = close ? `distance < 20 → true. Hello, nearby object! (${value} cm)` : `distance < 20 → false. Room to explore. (${value} cm)`;
  } else if (state.running) {
    clearTimeout(state.timer);
    state.timer = setTimeout(tick, value * 100);
  }
}
function toggleRun() {
  if (state.running) { clearRun(); $('#live-readout').textContent = 'Paused. Change something and try again.'; updateRange(); return; }
  state.running = true;
  state.light = 0;
  $('#run-button').innerHTML = '<span aria-hidden="true">■</span> Stop my circuit';
  $('#success-message').hidden = false;
  if (state.path === 'pi') tick(); else updateRange();
}

$$('[data-path]').forEach(button => button.addEventListener('click', () => choosePath(button.dataset.path, true)));
$$('[data-demo]').forEach(button => button.addEventListener('click', () => choosePath(button.dataset.demo)));
$$('[data-step]').forEach(button => button.addEventListener('click', () => setStage(Number(button.dataset.step))));
$('#connect-next').addEventListener('click', () => setStage(1, true));
$('#code-next').addEventListener('click', () => setStage(2, true));
$('#reset-demo').addEventListener('click', resetDemo);
$$('[data-level]').forEach(button => button.addEventListener('click', () => { state.level = button.dataset.level; renderLevel(); }));
$$('[data-view]').forEach(button => button.addEventListener('click', () => { state.view = button.dataset.view; renderView(); }));
$('#hint-button').addEventListener('click', () => {
  const hints = paths[state.path].hints;
  $('#coach-message').textContent = hints[state.hint % hints.length];
  state.hint++;
  $('#hint-button').innerHTML = (state.hint % hints.length === 0 ? 'Read the first hint again' : 'One more nudge') + ' <span>↗</span>';
});
$('#demo-range').addEventListener('input', updateRange);
$('#run-button').addEventListener('click', toggleRun);
document.addEventListener('visibilitychange', () => { if (document.hidden && state.running) { clearRun(); $('#live-readout').textContent = 'Paused while you were away. Ready when you are.'; } });

function choosePeek(key) {
  state.peek = key;
  const data = peekData[key];
  pressed('[data-peek]', 'peek', key);
  $('#peek-title').replaceChildren(...data.title.split('\n').flatMap((line, index) => index ? [document.createElement('br'), document.createTextNode(line)] : [document.createTextNode(line)]));
  $('#peek-copy').textContent = data.copy;
  $('#peek-window-label').textContent = data.label;
  $('#app-screenshot').src = data.image;
  $('#app-screenshot').alt = data.alt;
  data.notes.forEach((note, index) => {
    $(`#peek-note-${index + 1}`).textContent = note;
    const hotspot = $$('[data-hotspot]')[index];
    hotspot.style.left = `${data.positions[index][0]}%`;
    hotspot.style.top = `${data.positions[index][1]}%`;
    hotspot.style.right = 'auto';
    hotspot.style.bottom = 'auto';
    hotspot.setAttribute('aria-expanded', 'false');
  });
  $('#hotspot-tooltip').hidden = true;
}
$$('[data-peek]').forEach(button => button.addEventListener('click', () => choosePeek(button.dataset.peek)));
$$('[data-hotspot]').forEach(button => button.addEventListener('click', () => {
  const wasOpen = button.getAttribute('aria-expanded') === 'true';
  $$('[data-hotspot]').forEach(node => node.setAttribute('aria-expanded', 'false'));
  button.setAttribute('aria-expanded', String(!wasOpen));
  $('#hotspot-tooltip').hidden = wasOpen;
  $('#hotspot-tooltip').textContent = peekData[state.peek].notes[Number(button.dataset.hotspot)];
}));
const dialog = $('#video-dialog');
const video = $('#walkthrough-video');
$('#watch-walkthrough').addEventListener('click', () => {
  const data = peekData[state.peek];
  $('#video-dialog-title').textContent = data.videoTitle;
  video.src = data.video;
  video.poster = data.image;
  video.load();
  dialog.showModal();
});
$('#close-video').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) { const bounds = dialog.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close(); } });
dialog.addEventListener('close', () => { video.pause(); video.removeAttribute('src'); video.load(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') { $('#hotspot-tooltip').hidden = true; $$('[data-hotspot]').forEach(button => button.setAttribute('aria-expanded', 'false')); } });
choosePath('pi');
choosePeek('pi');

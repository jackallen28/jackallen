/**
 * Mind Jeopardy sound effects, synthesised in the browser.
 *
 * No audio files to ship, nothing to go missing on a school machine, and no
 * licensing question about using the real show's stings. Everything below is an
 * oscillator and an envelope.
 *
 * Browsers block audio until the page has been clicked, so `unlock()` is wired
 * to the first interaction on both screens.
 */

let ctx = null;
let master = null;
let enabled = true;

export function unlock() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = 0.32;
    master.connect(ctx.destination);
  }
  if (ctx.state === 'suspended') ctx.resume();
}

export function setEnabled(on) { enabled = on; }
export function isEnabled() { return enabled; }

function tone({ freq, start = 0, dur = 0.2, type = 'sine', gain = 0.5, sweepTo = null }) {
  if (!ctx || !enabled) return;
  const t0 = ctx.currentTime + start;
  const osc = ctx.createOscillator();
  const env = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (sweepTo) osc.frequency.exponentialRampToValueAtTime(sweepTo, t0 + dur);
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(gain, t0 + 0.012);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(env).connect(master);
  osc.start(t0);
  osc.stop(t0 + dur + 0.05);
}

function noise({ start = 0, dur = 0.3, gain = 0.35, freq = 900, q = 1 }) {
  if (!ctx || !enabled) return;
  const t0 = ctx.currentTime + start;
  const frames = Math.floor(ctx.sampleRate * dur);
  const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  const filter = ctx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.value = freq;
  filter.Q.value = q;
  const env = ctx.createGain();
  env.gain.setValueAtTime(gain, t0);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  src.connect(filter).connect(env).connect(master);
  src.start(t0);
}

const SOUNDS = {
  /** A clue is selected from the grid. */
  select() {
    tone({ freq: 523, dur: 0.1, type: 'sine', gain: 0.3 });
    tone({ freq: 784, start: 0.06, dur: 0.18, type: 'sine', gain: 0.3 });
  },

  /** Buzzers go live. */
  open() {
    tone({ freq: 660, dur: 0.12, type: 'triangle', gain: 0.3 });
    tone({ freq: 990, start: 0.09, dur: 0.2, type: 'triangle', gain: 0.28 });
  },

  /** A team beat the others to it. */
  buzz() {
    tone({ freq: 880, dur: 0.1, type: 'square', gain: 0.35 });
    tone({ freq: 1320, start: 0.07, dur: 0.16, type: 'square', gain: 0.32 });
  },

  /** Correct — the bright rising chime. */
  correct() {
    tone({ freq: 1046, dur: 0.14, type: 'sine', gain: 0.45 });
    tone({ freq: 1568, start: 0.08, dur: 0.45, type: 'sine', gain: 0.42 });
    tone({ freq: 2093, start: 0.08, dur: 0.4, type: 'triangle', gain: 0.16 });
  },

  /** Wrong — the flat double buzz. Costs the clue, not points. */
  wrong() {
    tone({ freq: 180, dur: 0.26, type: 'square', gain: 0.3 });
    tone({ freq: 120, dur: 0.26, type: 'square', gain: 0.28 });
    tone({ freq: 180, start: 0.3, dur: 0.3, type: 'square', gain: 0.3 });
    tone({ freq: 120, start: 0.3, dur: 0.3, type: 'square', gain: 0.28 });
  },

  /** The answer clock ran out with a team holding the clue. */
  timeup() {
    tone({ freq: 400, dur: 0.6, type: 'sawtooth', gain: 0.26, sweepTo: 130 });
    noise({ dur: 0.5, gain: 0.12, freq: 400 });
  },

  /** The answer goes up on the projector. */
  reveal() {
    tone({ freq: 392, dur: 0.2, type: 'triangle', gain: 0.3 });
    tone({ freq: 587, start: 0.14, dur: 0.35, type: 'triangle', gain: 0.3 });
  },

  /** A wager or a written answer is locked in. */
  lock() {
    tone({ freq: 700, dur: 0.07, type: 'square', gain: 0.22 });
    tone({ freq: 500, start: 0.07, dur: 0.1, type: 'square', gain: 0.2 });
  },

  /** Game opening, and the Final Jeopardy sting. */
  themeIn() {
    [392, 523, 659, 784].forEach((f, i) =>
      tone({ freq: f, start: i * 0.11, dur: 0.55, type: 'triangle', gain: 0.4 }));
  },

  final() {
    [523, 494, 440, 392, 349].forEach((f, i) =>
      tone({ freq: f, start: i * 0.14, dur: 0.7, type: 'triangle', gain: 0.36 }));
    noise({ start: 0.6, dur: 0.9, gain: 0.09, freq: 2200, q: 0.7 });
  },

  gameOver() {
    const notes = [523, 659, 784, 1046, 784, 1046, 1318];
    notes.forEach((f, i) => tone({ freq: f, start: i * 0.13, dur: 0.6, type: 'triangle', gain: 0.4 }));
    noise({ start: 0.5, dur: 1.4, gain: 0.13, freq: 3500, q: 0.5 });
  },

  /** Last few seconds of any clock. */
  tick() {
    tone({ freq: 1200, dur: 0.05, type: 'square', gain: 0.18 });
  },
};

export function play(name) {
  const fn = SOUNDS[name];
  if (!fn || !ctx || !enabled) return;
  try { fn(); } catch { /* an unsupported browser should never break the game */ }
}

/**
 * Game-show sound effects, synthesised in the browser.
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
  /** Correct answer — the bright two-note bell. */
  ding() {
    tone({ freq: 1318.5, dur: 0.16, type: 'sine', gain: 0.5 });
    tone({ freq: 1975.5, start: 0.09, dur: 0.5, type: 'sine', gain: 0.45 });
    tone({ freq: 2637, start: 0.09, dur: 0.45, type: 'triangle', gain: 0.18 });
  },

  /** Wrong answer — the flat double buzz. */
  strike() {
    tone({ freq: 175, dur: 0.28, type: 'square', gain: 0.32 });
    tone({ freq: 116, dur: 0.28, type: 'square', gain: 0.3 });
    tone({ freq: 175, start: 0.34, dur: 0.34, type: 'square', gain: 0.32 });
    tone({ freq: 116, start: 0.34, dur: 0.34, type: 'square', gain: 0.3 });
  },

  /** Somebody hit the buzzer. */
  buzz() {
    tone({ freq: 880, dur: 0.1, type: 'square', gain: 0.35 });
    tone({ freq: 1320, start: 0.07, dur: 0.14, type: 'square', gain: 0.32 });
  },

  /** Correct, but not on the board — that "ohhhh" moment. */
  nearmiss() {
    tone({ freq: 660, dur: 0.5, type: 'sawtooth', gain: 0.22, sweepTo: 210 });
    noise({ dur: 0.4, gain: 0.12, freq: 500 });
  },

  /** Already on the board. */
  duplicate() {
    tone({ freq: 420, dur: 0.14, type: 'triangle', gain: 0.25 });
    tone({ freq: 420, start: 0.16, dur: 0.14, type: 'triangle', gain: 0.25 });
  },

  /** Board cleared — full fanfare. */
  sweep() {
    const notes = [523, 659, 784, 1047, 1319];
    notes.forEach((f, i) => tone({ freq: f, start: i * 0.075, dur: 0.5, type: 'triangle', gain: 0.42 }));
    noise({ start: 0.3, dur: 0.7, gain: 0.1, freq: 4000, q: 0.6 });
  },

  roundStart() {
    [392, 523, 659].forEach((f, i) => tone({ freq: f, start: i * 0.1, dur: 0.35, type: 'triangle', gain: 0.4 }));
  },

  questionUp() {
    tone({ freq: 523, dur: 0.18, type: 'triangle', gain: 0.35 });
    tone({ freq: 784, start: 0.12, dur: 0.28, type: 'triangle', gain: 0.35 });
  },

  roundEnd() {
    [659, 523, 392].forEach((f, i) => tone({ freq: f, start: i * 0.1, dur: 0.35, type: 'triangle', gain: 0.35 }));
  },

  /** Rapid-fire clock starts. */
  go() {
    tone({ freq: 440, dur: 0.15, type: 'square', gain: 0.3 });
    tone({ freq: 440, start: 0.35, dur: 0.15, type: 'square', gain: 0.3 });
    tone({ freq: 880, start: 0.7, dur: 0.4, type: 'square', gain: 0.4 });
  },

  pass() {
    tone({ freq: 500, dur: 0.1, type: 'triangle', gain: 0.22, sweepTo: 300 });
  },

  gameOver() {
    const notes = [523, 659, 784, 1047, 784, 1047, 1319];
    notes.forEach((f, i) => tone({ freq: f, start: i * 0.13, dur: 0.6, type: 'triangle', gain: 0.4 }));
    noise({ start: 0.5, dur: 1.4, gain: 0.13, freq: 3500, q: 0.5 });
  },

  /** Last ten seconds of the rapid-fire clock. */
  tick() {
    tone({ freq: 1200, dur: 0.05, type: 'square', gain: 0.18 });
  },
};

export function play(name) {
  const fn = SOUNDS[name];
  if (!fn || !ctx || !enabled) return;
  try { fn(); } catch { /* an unsupported browser should never break the game */ }
}

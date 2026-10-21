import { test } from "node:test";
import assert from "node:assert/strict";
import { Autosaver, Status, statusText } from "../../ui/js/autosave.js";

// Fake timers we can step through by hand.
function fakeClock() {
  let now = 1_000_000;
  let next = 1;
  const timers = new Map();
  return {
    setTimeout(fn, ms) { const id = next++; timers.set(id, { fn, at: now + ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
    now: () => now,
    async advance(ms) {
      now += ms;
      for (const [id, t] of [...timers].sort((a, b) => a[1].at - b[1].at)) {
        if (t.at <= now && timers.has(id)) {
          timers.delete(id);
          t.fn();
          await settle();
        }
      }
      await settle();
    },
    pending: () => timers.size,
  };
}

const settle = () => new Promise((r) => setImmediate(r));

function memStore() {
  const m = new Map();
  return { m, get: async (k) => m.get(k), set: async (k, v) => void m.set(k, v), del: async (k) => void m.delete(k) };
}

function setup({ failWith } = {}) {
  const clock = fakeClock();
  const store = memStore();
  const sent = [];
  const statuses = [];
  const server = { fail: failWith ?? null };
  const saver = new Autosaver({
    key: "7:blink",
    store,
    timers: clock,
    delay: 1000,
    retryDelay: 5000,
    onStatus: (s) => statuses.push(s),
    send: async (code) => {
      if (server.fail) throw server.fail;
      sent.push(code);
    },
  });
  return { clock, store, sent, statuses, saver, server };
}

test("saves once, a second after typing stops", async () => {
  const { clock, sent, saver } = setup();
  saver.load("");
  saver.change("v");
  await clock.advance(500);
  saver.change("vo");
  await clock.advance(500);
  saver.change("voi");
  await clock.advance(999);
  assert.deepEqual(sent, []);
  assert.equal(saver.status, Status.PENDING);
  await clock.advance(1);
  assert.deepEqual(sent, ["voi"]);
  assert.equal(saver.status, Status.SAVED);
});

test("typing back to the saved code needs no save", async () => {
  const { clock, sent, saver } = setup();
  saver.load("abc");
  saver.change("abcd");
  saver.change("abc");
  assert.equal(saver.status, Status.SAVED);
  await clock.advance(2000);
  assert.deepEqual(sent, []);
});

test("offline: keeps the code in the browser and retries", async () => {
  const { clock, store, sent, saver, server } = setup({ failWith: { offline: true } });
  saver.load("");
  saver.change("void setup()");
  await clock.advance(1000);
  assert.equal(saver.status, Status.OFFLINE);
  assert.equal(store.m.get("7:blink").code, "void setup()");

  saver.change("void setup() {}");
  assert.equal(saver.status, Status.OFFLINE, "still says offline while typing");
  await settle();
  assert.equal(store.m.get("7:blink").code, "void setup() {}");

  server.fail = null; // network back
  await clock.advance(5000);
  assert.deepEqual(sent, ["void setup() {}"]);
  assert.equal(saver.status, Status.SAVED);
  assert.equal(store.m.has("7:blink"), false, "offline copy cleared once saved");
});

test("a refusal shows the server's message and keeps the code", async () => {
  const { clock, store, saver } = setup({ failWith: { message: "This sketch is too long to save." } });
  const seen = [];
  saver.onStatus = (s, d) => seen.push([s, d]);
  saver.load("");
  saver.change("x".repeat(10));
  await clock.advance(1000);
  assert.equal(saver.status, Status.ERROR);
  assert.deepEqual(seen.at(-1), [Status.ERROR, "This sketch is too long to save."]);
  assert.ok(store.m.has("7:blink"));
});

test("flush saves straight away, including typing during a save", async () => {
  const { sent, saver } = setup();
  saver.load("");
  let release;
  const slow = new Promise((r) => (release = r));
  const fast = saver.send;
  saver.send = async (code) => {
    await slow;
    return fast(code);
  };
  saver.change("one");
  const flushing = saver.flush();
  await settle();
  saver.change("two"); // typed while "one" is being sent
  release();
  assert.equal(await flushing, true);
  assert.deepEqual(sent, ["one", "two"]);
  assert.equal(saver.status, Status.SAVED);
});

test("recover: newer unsaved code from the browser wins and is sent", async () => {
  const { store, sent, saver } = setup();
  store.m.set("7:blink", { code: "offline edit", at: 2000 });
  const code = await saver.recover("server copy", 1000);
  assert.equal(code, "offline edit");
  assert.deepEqual(sent, ["offline edit"]);
  assert.equal(store.m.has("7:blink"), false);
});

test("recover: an older browser copy loses to newer work on the server", async () => {
  const { store, sent, saver } = setup();
  store.m.set("7:blink", { code: "stale", at: 500 });
  const code = await saver.recover("saved on another laptop", 1000);
  assert.equal(code, "saved on another laptop");
  assert.deepEqual(sent, []);
  assert.equal(store.m.has("7:blink"), false);
});

test("status words", () => {
  assert.equal(statusText(Status.SAVED), "Saved ✓");
  assert.equal(statusText(Status.SAVING), "Saving...");
  assert.equal(statusText(Status.OFFLINE), "Offline, will save when you're back");
});

// Autosave: code is saved about a second after typing stops. If the network
// blips, the unsaved code waits in the browser (an offline store such as
// IndexedDB) and is sent when the server is back.
//
// The saver doesn't know about fetch or IndexedDB: it is given a `send`
// function and a `store`, so it can be tested in Node.

export const Status = Object.freeze({
  SAVED: "saved",      // everything is on the server
  PENDING: "pending",  // typed, waiting for the pause before saving
  SAVING: "saving",
  OFFLINE: "offline",  // couldn't reach the server; kept in the browser
  ERROR: "error",      // the server refused it (too big, logged out...)
});

export class Autosaver {
  /**
   * @param {object} opts
   * @param {(code: string) => Promise<any>} opts.send  saves to the server; throws an error with offline: true when unreachable
   * @param {{get(k), set(k, v), del(k)}} opts.store     the browser's offline store
   * @param {string} opts.key                            what this sketch is called in the store
   * @param {(status: string, detail?: string) => void} [opts.onStatus]
   * @param {number} [opts.delay]       ms of quiet before saving (default 1000)
   * @param {number} [opts.retryDelay]  ms between retries while offline (default 5000)
   * @param {object} [opts.timers]      { setTimeout, clearTimeout, now } for tests
   */
  constructor({ send, store, key, onStatus = () => {}, delay = 1000, retryDelay = 5000, timers = globalThis }) {
    Object.assign(this, { send, store, key, onStatus, delay, retryDelay });
    this.timers = {
      setTimeout: (fn, ms) => timers.setTimeout(fn, ms),
      clearTimeout: (t) => timers.clearTimeout(t),
      now: timers.now ? () => timers.now() : () => Date.now(),
    };
    this.code = "";       // the latest code
    this.savedCode = "";  // the code the server has
    this.timer = null;
    this.inflight = null;
    this.status = Status.SAVED;
    this.stopped = false;
  }

  get dirty() {
    return this.code !== this.savedCode;
  }

  setStatus(status, detail) {
    if (this.status === status && !detail) return;
    this.status = status;
    this.onStatus(status, detail);
  }

  /** Starts from the server's copy. */
  load(code) {
    this.code = this.savedCode = code;
    this.setStatus(Status.SAVED);
  }

  /**
   * Starts from the server's copy, unless the offline store has code that
   * never reached the server and is newer than the server's copy
   * (serverUpdatedAt, ms). Returns the code to show.
   */
  async recover(serverCode, serverUpdatedAt = 0) {
    this.load(serverCode);
    let pending = null;
    try {
      pending = await this.store.get(this.key);
    } catch {
      pending = null;
    }
    if (pending && typeof pending.code === "string" && pending.at > serverUpdatedAt && pending.code !== serverCode) {
      this.code = pending.code;
      await this.flush();
      return pending.code;
    }
    if (pending) await this.forget();
    return serverCode;
  }

  /** Call on every edit. */
  change(code) {
    if (this.stopped) return;
    this.code = code;
    if (!this.dirty && !this.inflight) {
      this.cancelTimer();
      this.setStatus(Status.SAVED);
      return;
    }
    if (this.status === Status.OFFLINE) {
      this.keep(code); // keep showing "Offline", and keep the newest code safe
    } else if (!this.inflight) {
      this.setStatus(Status.PENDING);
    }
    this.schedule(this.status === Status.OFFLINE ? this.retryDelay : this.delay);
  }

  schedule(ms) {
    this.cancelTimer();
    this.timer = this.timers.setTimeout(() => {
      this.timer = null;
      this.sendCurrent();
    }, ms);
  }

  cancelTimer() {
    if (this.timer != null) this.timers.clearTimeout(this.timer);
    this.timer = null;
  }

  /** Sends the current code once. Resolves true if the server has it. */
  async sendCurrent() {
    while (this.inflight) await this.inflight;
    if (!this.dirty) {
      this.setStatus(Status.SAVED);
      return true;
    }
    const code = this.code;
    this.setStatus(Status.SAVING);
    const attempt = (async () => {
      try {
        await this.send(code);
        this.savedCode = code;
        if (this.dirty) {
          this.setStatus(Status.PENDING); // more typing arrived; its timer will save it
        } else {
          await this.forget();
          this.setStatus(Status.SAVED);
        }
        return true;
      } catch (err) {
        await this.keep(this.code);
        if (err && err.offline) {
          this.setStatus(Status.OFFLINE);
          if (!this.stopped) this.schedule(this.retryDelay);
        } else {
          this.setStatus(Status.ERROR, err && err.message);
        }
        return false;
      }
    })();
    this.inflight = attempt;
    try {
      return await attempt;
    } finally {
      if (this.inflight === attempt) this.inflight = null;
    }
  }

  /** Saves everything now (Run, Upload, leaving the project). Resolves true if saved. */
  async flush() {
    this.cancelTimer();
    for (let tries = 0; tries < 5; tries++) {
      if (!(await this.sendCurrent())) return false;
      if (!this.dirty) return true;
    }
    return !this.dirty;
  }

  /** The network is back: try again now. */
  retry() {
    if (this.dirty && !this.stopped) this.flush();
  }

  async keep(code) {
    try {
      await this.store.set(this.key, { code, at: this.timers.now() });
    } catch {
      // No offline store (a private window, say): nothing more we can do.
    }
  }

  async forget() {
    try {
      await this.store.del(this.key);
    } catch {
      // ignore
    }
  }

  /** Stops timers when leaving the project. Call flush() first. */
  stop() {
    this.stopped = true;
    this.cancelTimer();
  }
}

/** The words students see for each status. */
export function statusText(status, detail) {
  switch (status) {
    case Status.SAVED: return "Saved ✓";
    case Status.PENDING: return "Not saved yet";
    case Status.SAVING: return "Saving...";
    case Status.OFFLINE: return "Offline, will save when you're back";
    case Status.ERROR: return detail || "Couldn't save. Your code is kept in this browser for now.";
    default: return "";
  }
}

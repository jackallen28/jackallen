// Demo mode for web/preview.html: a pretend controller behind a pretend Wi-Fi board, so the
// dashboard can be tried in any browser. It is not part of the firmware.
(function () {
  const t0 = Date.now();
  const cfg = { t: "cfg", l1: 25, l2: 50, l3: 100, ap: 4, am: 500, ah: 0, cc: 2, cm: 250, rs: 0, rl: 1, rh: 2000, ch: 20, bk: 70, vn: 0, va: 0, ra: 0, ppl: 6600, cal: 1, fw: 2 };
  const DEF = Object.assign({}, cfg);
  const n = { pulses: 0, c: 0, s: 0, cp: 0, m: 0, st: 0, v: 1, ppl: 66, cal: 1, hz: 0, ack: 0, ok: 1, ev: 0, ec: 1, es: 3, ex: 2, alertEnd: 0 };
  const ev = [], hist = [], cmds = [];
  let nextId = 1, frac = 0, lastTick = Date.now(), lastHist = 0, tapOn = true, tapChange = Date.now() + 25000;
  const log = (code, src, extra) => ev.push([Date.now(), code, src, extra]);
  log(100, 9, 1); log(101, 9, 0); log(1, 3, 2);
  // Start part-way through a 25 L limit so the gauge has something to show.
  n.c = n.s = n.pulses = Math.round(17.3 * 66);

  function tick() {
    const now = Date.now(), dt = (now - lastTick) / 1000;
    lastTick = now;
    if (now > tapChange) { tapOn = !tapOn; tapChange = now + (tapOn ? 30000 : 8000); }
    const target = tapOn && n.v ? 11.5 + Math.sin(now / 4000) * 1.2 : 0;   // Hz
    n.hz = n.hz + (target - n.hz) * Math.min(1, dt * 2);
    if (n.hz < 0.05) n.hz = 0;
    frac += n.hz * dt;
    const p = Math.floor(frac); frac -= p;
    n.pulses += p; n.c += p; n.s += p; if (n.st == 3) n.cp += p;
    if (n.st == 1 && now > n.alertEnd) {
      n.c = 0;
      if (cfg.ah) { n.st = 4; n.v = 0; log(12, 3, cfg["l" + (n.m + 1)]); } else { n.st = 0; n.v = 1; }
    }
    if (n.st == 2 && now > n.alertEnd) { n.st = 0; n.v = 1; }
    if (n.st == 1) n.v = Math.floor((now - n.alertStart) / cfg.am) % 2;
    if (n.st == 0 && n.m < 3 && n.c >= cfg["l" + (n.m + 1)] * n.ppl) {
      n.c = 0; log(2, 3, cfg["l" + (n.m + 1)]);
      if (cfg.ap) { n.st = 1; n.alertStart = now; n.alertEnd = now + cfg.ap * 2 * cfg.am; }
      else if (cfg.ah) { n.st = 4; n.v = 0; }
    }
    if (now - lastHist > 2000) { lastHist = now; hist.push(Math.round(n.hz * 60 / n.ppl * 100)); if (hist.length > 150) hist.shift(); }
  }
  setInterval(tick, 100);

  function run(body) {
    const [c, ...a] = body.split(",");
    const v = parseInt(a[0], 10);
    switch (c) {
      case "M": if (n.st == 3) return 4; n.m = v; log(4, 2, v); return 2;
      case "R": if (n.st == 3) return 4; n.c = n.s = 0; n.st = 0; n.v = 1; log(3, 2, 0); return 2;
      case "CS": n.st = 3; n.cp = 0; log(5, 2, 0); return 2;
      case "CX": if (n.st != 3) return 4; n.st = 0; n.c = n.s = 0; log(8, 2, n.cp); return 2;
      case "CF": {
        if (n.st != 3) return 4;
        const ppl = n.cp / (v / 100);
        n.st = 0; n.c = n.s = 0;
        if (ppl >= 5 && ppl <= 1000) { n.ppl = ppl; n.cal = 1; log(6, 2, Math.round(ppl * 100)); return 2; }
        log(7, 2, n.cp); return 3;
      }
      case "P": if (!(v >= 500 && v <= 100000)) return 3; n.ppl = v / 100; n.cal = 1; log(13, 2, v); return 2;
      case "S": for (const kv of a) { const [k, x] = kv.split("="); if (!(k in DEF)) return 3; cfg[k] = +x; } log(9, 2, 0); return 2;
      case "D": Object.assign(cfg, DEF); if (v == 1) { n.ppl = 64.8; n.cal = 0; n.m = 3; } n.c = n.s = 0; n.st = 0; n.v = 1; log(10, 2, v); return 2;
      case "T": if (n.st != 0) return 4; n.st = 2; n.v = 0; n.alertEnd = Date.now() + 1000; log(11, 2, 0); return 2;
      case "Q": return 2;
    }
    return 5;
  }

  function status() {
    const now = Date.now();
    const s = { t: "s", n: n.pulses, c: n.c, s: n.s, hz: Math.round(n.hz * 100), m: n.m, st: n.st, v: n.v, cp: n.cp, in: 0,
      ppl: Math.round(n.ppl * 100), cal: n.cal, ack: 0, ok: 1, ev: ev.length, ec: 0, es: 0, ex: 0, g: 3, bad: 0, up: Math.round((now - t0) / 1000) + 3600 };
    return {
      now: now - t0 + 3605000, ap: "VAT_Aqua_Tracka", esp: "1.0 demo", clients: 1,
      link: { state: "ok", age: 400, byteAge: 100, good: Math.round((now - t0) / 900) + 4000, bad: 2, bytes: 812345, sent: nextId - 1, retries: 0, failed: 0, queued: 0 },
      s, cfg: Object.assign({}, cfg, { ppl: Math.round(n.ppl * 100), cal: n.cal }), cfgAge: 3000,
      ev: ev.slice(-40).map(e => [now - e[0], e[1], e[2], e[3]]), hist: hist.slice(), cmds: cmds.slice(-16),
    };
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async function (url, opts) {
    const u = String(url);
    const reply = (code, obj) => new Response(JSON.stringify(obj), { status: code, headers: { "Content-Type": "application/json" } });
    if (u.endsWith("/api/status")) return reply(200, status());
    if (u.endsWith("/api/cmd")) {
      const body = decodeURIComponent(String(opts.body).replace(/^c=/, ""));
      const id = nextId++;
      cmds.push([id, 1]);
      setTimeout(() => { const st = run(body); const c = cmds.find(x => x[0] == id); if (c) c[1] = st; }, 500 + Math.random() * 600);
      return reply(200, { id });
    }
    return realFetch(url, opts);
  };
})();

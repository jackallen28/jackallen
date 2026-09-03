/*!
 * CAD Quote Bot — embeddable chat widget
 *
 * Usage (inline, fills the container):
 *   <div id="cad-quote-bot"></div>
 *   <script src="https://your-api.example.com/embed/cad-quote-widget.js"
 *           data-api="https://your-api.example.com"
 *           data-target="#cad-quote-bot"></script>
 *
 * Usage (floating bubble, bottom-right of every page):
 *   <script src="https://your-api.example.com/embed/cad-quote-widget.js"
 *           data-api="https://your-api.example.com"
 *           data-mode="popup"></script>
 *
 * Optional attributes: data-accent, data-height, data-title, data-subtitle.
 * Everything renders inside a shadow root, so the host page's CSS cannot
 * leak in and this stylesheet cannot leak out.
 */
(function () {
  'use strict';

  var script = document.currentScript || (function () {
    var all = document.getElementsByTagName('script');
    return all[all.length - 1];
  })();

  var opts = {
    api: (script.getAttribute('data-api') || '').replace(/\/$/, ''),
    target: script.getAttribute('data-target') || '#cad-quote-bot',
    mode: script.getAttribute('data-mode') || 'inline',
    accent: script.getAttribute('data-accent') || '#FF6A1A',
    height: script.getAttribute('data-height') || '640px',
    title: script.getAttribute('data-title') || 'Design & quote assistant',
    subtitle: script.getAttribute('data-subtitle') || 'Describe your part — get a 3D model and a quote'
  };
  if (!opts.api) {
    console.error('[cad-quote-bot] data-api is required on the script tag.');
    return;
  }

  /* ------------------------------------------------------------------ */
  /* styles                                                              */
  /* ------------------------------------------------------------------ */

  var CSS = `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }
.root {
  --accent: ACCENT;
  --accent-soft: ACCENT14;
  --ink: #14161a;
  --muted: #6b7280;
  --line: #eceef1;
  --line-strong: #dfe2e7;
  --bg: #ffffff;
  --bubble: #f6f7f9;
  font: 400 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
  color: var(--ink);
  background: var(--bg);
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}
.head {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 18px; border-bottom: 1px solid var(--line); background: #fff; flex: none;
}
.mark { width: 9px; height: 20px; border-radius: 2px; background: var(--accent); flex: none; }
.head h2 { margin: 0; font-size: 15px; font-weight: 650; letter-spacing: -.01em; }
.head p { margin: 1px 0 0; font-size: 12.5px; color: var(--muted); }
.head .close {
  margin-left: auto; border: 0; background: none; cursor: pointer; color: var(--muted);
  font-size: 20px; line-height: 1; padding: 4px 6px; border-radius: 6px;
}
.head .close:hover { background: var(--bubble); color: var(--ink); }

.log { flex: 1 1 auto; overflow-y: auto; padding: 20px 18px 8px; scroll-behavior: smooth; }
.msg { display: flex; margin-bottom: 14px; }
.msg.user { justify-content: flex-end; }
.bubble {
  max-width: 86%; padding: 11px 14px; border-radius: 14px; font-size: 14.5px;
  white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere;
}
.msg.bot .bubble { background: var(--bubble); border-top-left-radius: 5px; }
.msg.user .bubble { background: var(--accent); color: #fff; border-top-right-radius: 5px; }
.bubble strong { font-weight: 650; }
.bubble em { font-style: normal; color: var(--muted); font-size: 13.5px; }
.msg.user .bubble em { color: rgba(255,255,255,.85); }

.typing { display: inline-flex; gap: 4px; padding: 14px; }
.typing i { width: 6px; height: 6px; border-radius: 50%; background: var(--line-strong); animation: blink 1.2s infinite; }
.typing i:nth-child(2) { animation-delay: .18s; }
.typing i:nth-child(3) { animation-delay: .36s; }
@keyframes blink { 0%, 60%, 100% { opacity: .35; } 30% { opacity: 1; } }

.card {
  margin-top: 10px; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff;
  max-width: 86%;
}
.card img { display: block; width: 100%; background: #fafbfc; }
.card .body { padding: 12px 14px; }
.card h3 { margin: 0 0 8px; font-size: 14px; font-weight: 650; }
.stats { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.stat { font-size: 11.5px; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; }
.card .row { display: flex; gap: 8px; flex-wrap: wrap; }

.foot { flex: none; border-top: 1px solid var(--line); padding: 12px 14px 14px; background: #fff; }
.chips { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--line-strong); background: #fff; color: var(--ink); transition: .15s;
}
.chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }

.composer { display: flex; gap: 8px; align-items: flex-end; }
textarea.input {
  flex: 1 1 auto; font: inherit; font-size: 14.5px; resize: none; padding: 11px 13px; max-height: 140px;
  border: 1px solid var(--line-strong); border-radius: 10px; background: #fff; color: var(--ink); outline: none;
}
textarea.input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
button.btn {
  font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; border-radius: 10px;
  padding: 11px 16px; border: 1px solid var(--line-strong); background: #fff; color: var(--ink); transition: .15s;
  white-space: nowrap;
}
button.btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
button.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.btn.primary:hover:not(:disabled) { filter: brightness(.94); color: #fff; }
button.btn:disabled { opacity: .5; cursor: default; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }

.busy { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 13.5px; padding: 4px 2px; }
.spinner {
  width: 15px; height: 15px; border: 2px solid var(--line-strong); border-top-color: var(--accent);
  border-radius: 50%; animation: spin .8s linear infinite; flex: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

form.lead { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
form.lead .field { display: flex; flex-direction: column; gap: 4px; }
form.lead .field.wide { grid-column: 1 / -1; }
form.lead label { font-size: 12px; font-weight: 600; color: var(--muted); }
form.lead input, form.lead select, form.lead textarea {
  font: inherit; font-size: 14px; padding: 10px 12px; border: 1px solid var(--line-strong);
  border-radius: 9px; background: #fff; color: var(--ink); outline: none; width: 100%;
}
form.lead textarea { resize: vertical; min-height: 62px; }
form.lead input:focus, form.lead select:focus, form.lead textarea:focus {
  border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft);
}
form.lead .err { font-size: 11.5px; color: #d64545; }
form.lead .hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.legal { grid-column: 1 / -1; font-size: 11.5px; color: var(--muted); margin: 2px 0 0; }
.done { text-align: center; color: var(--muted); font-size: 13.5px; padding: 6px; }
.error { color: #d64545; font-size: 13px; padding: 6px 2px; }

@media (max-width: 520px) {
  form.lead { grid-template-columns: 1fr; }
  .bubble, .card { max-width: 94%; }
}

/* popup mode */
:host(.popup-host) { position: fixed; right: 20px; bottom: 20px; z-index: 2147483000; }
.launcher {
  border: 0; cursor: pointer; border-radius: 999px; background: var(--accent); color: #fff;
  font: 600 14.5px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
  padding: 15px 22px; box-shadow: 0 8px 26px rgba(20,22,26,.18); display: flex; align-items: center; gap: 9px;
}
.launcher:hover { filter: brightness(.95); }
.panel {
  width: min(420px, calc(100vw - 32px));
  height: min(660px, calc(100vh - 120px));
  box-shadow: 0 18px 48px rgba(20,22,26,.16);
  border-radius: 16px;
}
.hidden { display: none !important; }
`;

  /* ------------------------------------------------------------------ */
  /* helpers                                                             */
  /* ------------------------------------------------------------------ */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Tiny markdown subset: **bold**, _italic_, and blank-line paragraphs.
  // Input is escaped first, so nothing from the server can inject markup.
  function formatText(s) {
    return escapeHtml(s)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|\s)_([^_\n]+)_/g, '$1<em>$2</em>');
  }

  function hexWithAlpha(hex, alpha) {
    var h = String(hex).replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
  }

  /* ------------------------------------------------------------------ */
  /* widget                                                              */
  /* ------------------------------------------------------------------ */

  function Widget(host) {
    this.host = host;
    this.shadow = host.attachShadow({ mode: 'open' });
    this.sessionId = null;
    this.messageCount = 0;
    this.state = null;
    this.polling = null;
    this.busy = false;
    this.build();
  }

  Widget.prototype.build = function () {
    var style = document.createElement('style');
    style.textContent = CSS
      .replace(/ACCENT14/g, hexWithAlpha(opts.accent, 0.13))
      .replace(/ACCENT/g, opts.accent);
    this.shadow.appendChild(style);

    this.root = el('div', 'root');
    if (opts.mode === 'popup') this.root.classList.add('panel');

    var head = el('div', 'head');
    head.appendChild(el('span', 'mark'));
    var titles = el('div');
    var h2 = el('h2', null, opts.title);
    var p = el('p', null, opts.subtitle);
    titles.appendChild(h2);
    titles.appendChild(p);
    head.appendChild(titles);
    if (opts.mode === 'popup') {
      var close = el('button', 'close', '×');
      close.setAttribute('aria-label', 'Close chat');
      close.addEventListener('click', function () { this.toggle(false); }.bind(this));
      head.appendChild(close);
    }
    this.root.appendChild(head);

    this.log = el('div', 'log');
    this.log.setAttribute('role', 'log');
    this.log.setAttribute('aria-live', 'polite');
    this.root.appendChild(this.log);

    this.foot = el('div', 'foot');
    this.root.appendChild(this.foot);

    this.shadow.appendChild(this.root);
  };

  Widget.prototype.mount = function () {
    var self = this;
    window.addEventListener('message', function (event) {
      // Sent by the 3D viewer tab when the customer taps "Return to chat".
      if (event.data && event.data.type === 'cadbot:viewer-return') {
        try { window.focus(); } catch (e) {}
        self.scrollDown();
      }
    });
    this.start();
  };

  /* ----------------------------- transport ------------------------- */

  Widget.prototype.call = function (path, body, method) {
    return fetch(opts.api + path, {
      method: method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          var err = new Error(data.message || 'Request failed');
          err.payload = data;
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  };

  Widget.prototype.start = function () {
    var self = this;
    this.setFooter(this.busyFooter('Starting…'));
    this.call('/api/session', {})
      .then(function (snap) {
        self.sessionId = snap.sessionId;
        self.apply(snap);
      })
      .catch(function (err) { self.showError(err); });
  };

  Widget.prototype.send = function (text) {
    if (this.busy || !text || !this.sessionId) return;
    var self = this;
    this.busy = true;
    this.appendMessage({ role: 'user', text: text });
    this.messageCount += 1;
    this.setFooter(this.typingFooter());
    this.call('/api/message', { sessionId: this.sessionId, text: text })
      .then(function (snap) { self.busy = false; self.apply(snap); })
      .catch(function (err) { self.busy = false; self.showError(err); });
  };

  Widget.prototype.action = function (id) {
    if (this.busy || !this.sessionId) return;
    var self = this;
    this.busy = true;
    this.setFooter(this.typingFooter());
    this.call('/api/action', { sessionId: this.sessionId, action: id })
      .then(function (snap) { self.busy = false; self.apply(snap); })
      .catch(function (err) { self.busy = false; self.showError(err); });
  };

  Widget.prototype.poll = function () {
    if (this.polling) return;
    var self = this;
    this.polling = setInterval(function () {
      self.call('/api/session/' + self.sessionId + '?since=' + self.messageCount, null, 'GET')
        .then(function (snap) { self.apply(snap); })
        .catch(function () { /* transient — the next tick retries */ });
    }, 2500);
  };

  Widget.prototype.stopPoll = function () {
    if (this.polling) { clearInterval(this.polling); this.polling = null; }
  };

  /* ------------------------------ render --------------------------- */

  Widget.prototype.apply = function (snap) {
    if (!snap || !snap.messages) return;
    for (var i = 0; i < snap.messages.length; i++) this.appendMessage(snap.messages[i]);
    this.messageCount = snap.messageCount != null ? snap.messageCount : this.messageCount + snap.messages.length;
    this.state = snap.state;
    if (snap.state === 'generating') this.poll(); else this.stopPoll();
    this.renderFooter(snap.ui);
    this.scrollDown();
  };

  Widget.prototype.appendMessage = function (msg) {
    var wrap = el('div', 'msg ' + (msg.role === 'user' ? 'user' : 'bot'));
    var col = el('div');
    col.style.maxWidth = '100%';
    var bubble = el('div', 'bubble');
    bubble.innerHTML = formatText(msg.text);
    col.appendChild(bubble);
    if (msg.card && msg.card.type === 'preview') col.appendChild(this.previewCard(msg.card));
    wrap.appendChild(col);
    this.log.appendChild(wrap);
    this.scrollDown();
  };

  Widget.prototype.previewCard = function (card) {
    var self = this;
    var box = el('div', 'card');
    if (card.imageUrl) {
      var img = el('img');
      img.src = card.imageUrl;
      img.alt = 'Render of ' + (card.title || 'your part');
      img.loading = 'lazy';
      box.appendChild(img);
    }
    var body = el('div', 'body');
    body.appendChild(el('h3', null, card.title || 'Your model'));
    if (card.stats) {
      var stats = el('div', 'stats');
      stats.appendChild(el('span', 'stat', card.stats.bboxMm.x + ' × ' + card.stats.bboxMm.y + ' × ' + card.stats.bboxMm.z + ' mm'));
      stats.appendChild(el('span', 'stat', card.stats.volumeCm3 + ' cm³ of material'));
      body.appendChild(stats);
    }
    var row = el('div', 'row');
    var view = el('button', 'btn primary', 'Open 3D viewer');
    view.addEventListener('click', function () {
      // Opened by script, so the viewer's "Return to chat" button can close it.
      var tab = window.open(card.viewerUrl, '_blank', 'noopener=no');
      if (!tab) window.location.href = card.viewerUrl;
      self.scrollDown();
    });
    row.appendChild(view);
    var dl = el('button', 'btn', 'Download STL');
    dl.addEventListener('click', function () { window.open(card.stlUrl, '_blank'); });
    row.appendChild(dl);
    body.appendChild(row);
    box.appendChild(body);
    return box;
  };

  Widget.prototype.setFooter = function (node) {
    this.foot.innerHTML = '';
    if (node) this.foot.appendChild(node);
  };

  Widget.prototype.typingFooter = function () {
    var wrap = el('div', 'busy');
    var dots = el('div', 'typing');
    dots.appendChild(el('i')); dots.appendChild(el('i')); dots.appendChild(el('i'));
    wrap.appendChild(dots);
    return wrap;
  };

  Widget.prototype.busyFooter = function (label) {
    var wrap = el('div', 'busy');
    wrap.appendChild(el('span', 'spinner'));
    wrap.appendChild(el('span', null, label));
    return wrap;
  };

  Widget.prototype.renderFooter = function (ui) {
    if (!ui) return;
    var self = this;

    if (ui.mode === 'busy') { this.setFooter(this.busyFooter(ui.label || 'Working…')); return; }

    if (ui.mode === 'done') {
      var done = el('div', 'done', 'Conversation complete — thanks!');
      this.setFooter(done);
      return;
    }

    if (ui.mode === 'confirm') {
      var actions = el('div', 'actions');
      (ui.actions || []).forEach(function (a) {
        var b = el('button', 'btn' + (a.style === 'primary' ? ' primary' : ''), a.label);
        b.addEventListener('click', function () { self.action(a.id); });
        actions.appendChild(b);
      });
      this.setFooter(actions);
      return;
    }

    if (ui.mode === 'form') { this.setFooter(this.leadForm(ui.fields)); return; }

    // Default: free-text composer, optionally with tappable suggestions.
    var wrap = el('div');
    if (ui.chips && ui.chips.length) {
      var chips = el('div', 'chips');
      ui.chips.forEach(function (label) {
        var c = el('button', 'chip', label);
        c.addEventListener('click', function () { self.send(label); });
        chips.appendChild(c);
      });
      wrap.appendChild(chips);
    }
    var composer = el('div', 'composer');
    var input = el('textarea', 'input');
    input.rows = 1;
    input.placeholder = ui.placeholder || 'Type a message…';
    input.setAttribute('aria-label', 'Message');
    input.addEventListener('input', function () {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 140) + 'px';
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
    });
    var send = el('button', 'btn primary', 'Send');
    function submit() {
      var text = input.value.trim();
      if (!text) return;
      input.value = '';
      self.send(text);
    }
    send.addEventListener('click', submit);
    composer.appendChild(input);
    composer.appendChild(send);
    wrap.appendChild(composer);
    this.setFooter(wrap);
    if (opts.mode !== 'popup' || this.opened) { try { input.focus({ preventScroll: true }); } catch (e) {} }
  };

  Widget.prototype.leadForm = function (fields) {
    var self = this;
    var form = el('form', 'lead');
    var inputs = {};

    (fields || []).forEach(function (f) {
      var wide = f.type === 'textarea' || f.name === 'name' || f.name === 'email';
      var field = el('div', 'field' + (wide ? ' wide' : ''));
      var id = 'f_' + f.name;
      var label = el('label', null, f.label);
      label.setAttribute('for', id);
      field.appendChild(label);

      var input;
      if (f.type === 'select') {
        input = document.createElement('select');
        (f.options || []).forEach(function (o) {
          var opt = document.createElement('option');
          opt.value = o; opt.textContent = o;
          input.appendChild(opt);
        });
      } else if (f.type === 'textarea') {
        input = document.createElement('textarea');
      } else {
        input = document.createElement('input');
        input.type = f.type || 'text';
        if (f.min != null) input.min = f.min;
        if (f.max != null) input.max = f.max;
        if (f.name === 'quantity') input.value = '1';
      }
      input.id = id;
      input.name = f.name;
      if (f.autocomplete) input.setAttribute('autocomplete', f.autocomplete);
      if (f.required) input.required = true;
      field.appendChild(input);
      var err = el('div', 'err');
      err.hidden = true;
      field.appendChild(err);
      inputs[f.name] = { input: input, err: err };
      form.appendChild(field);
    });

    // Honeypot — hidden from people, irresistible to bots.
    var hp = el('div', 'hp');
    var hpInput = document.createElement('input');
    hpInput.type = 'text'; hpInput.name = 'company'; hpInput.tabIndex = -1;
    hpInput.setAttribute('autocomplete', 'off');
    hp.appendChild(hpInput);
    form.appendChild(hp);

    var legal = el('p', 'legal', 'We use these details only to quote your job and contact you about it.');
    form.appendChild(legal);

    var submitWrap = el('div', 'field wide');
    var submit = el('button', 'btn primary', 'Request my quote');
    submit.type = 'submit';
    submitWrap.appendChild(submit);
    var formErr = el('div', 'error');
    formErr.hidden = true;
    submitWrap.appendChild(formErr);
    form.appendChild(submitWrap);

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (self.busy) return;
      var payload = { sessionId: self.sessionId };
      Object.keys(inputs).forEach(function (k) {
        payload[k] = inputs[k].input.value;
        inputs[k].err.hidden = true;
      });
      payload.company = hpInput.value;
      formErr.hidden = true;
      self.busy = true;
      submit.disabled = true;
      submit.textContent = 'Sending…';

      self.call('/api/lead', payload)
        .then(function (snap) { self.busy = false; self.apply(snap); })
        .catch(function (err) {
          self.busy = false;
          submit.disabled = false;
          submit.textContent = 'Request my quote';
          var errors = err.payload && err.payload.errors;
          if (errors) {
            Object.keys(errors).forEach(function (k) {
              if (!inputs[k]) return;
              inputs[k].err.textContent = errors[k];
              inputs[k].err.hidden = false;
            });
          } else {
            formErr.textContent = err.message || 'Could not send — please try again.';
            formErr.hidden = false;
          }
        });
    });

    return form;
  };

  Widget.prototype.showError = function (err) {
    var self = this;
    var wrap = el('div');
    var msg = el('div', 'error', (err && err.message) || 'Connection problem.');
    var retry = el('button', 'btn', 'Try again');
    retry.addEventListener('click', function () {
      if (self.sessionId) self.call('/api/session/' + self.sessionId + '?since=' + self.messageCount, null, 'GET')
        .then(function (snap) { self.apply(snap); })
        .catch(function (e) { self.showError(e); });
      else self.start();
    });
    wrap.appendChild(msg);
    wrap.appendChild(retry);
    this.setFooter(wrap);
    console.error('[cad-quote-bot]', err);
  };

  Widget.prototype.scrollDown = function () {
    var log = this.log;
    requestAnimationFrame(function () { log.scrollTop = log.scrollHeight; });
  };

  /* ------------------------------------------------------------------ */
  /* mounting                                                            */
  /* ------------------------------------------------------------------ */

  function mountInline() {
    var target = document.querySelector(opts.target);
    if (!target) {
      console.error('[cad-quote-bot] target not found:', opts.target);
      return;
    }
    if (!target.style.height) target.style.height = opts.height;
    var widget = new Widget(target);
    widget.mount();
    window.CADQuoteBot = widget;
  }

  function mountPopup() {
    var hostEl = document.createElement('div');
    document.body.appendChild(hostEl);

    var launcherHost = document.createElement('div');
    launcherHost.className = 'popup-host';
    document.body.appendChild(launcherHost);
    var lShadow = launcherHost.attachShadow({ mode: 'open' });
    var lStyle = document.createElement('style');
    lStyle.textContent = CSS.replace(/ACCENT14/g, hexWithAlpha(opts.accent, 0.13)).replace(/ACCENT/g, opts.accent) +
      ':host{position:fixed;right:20px;bottom:20px;z-index:2147483000}';
    lShadow.appendChild(lStyle);
    var launcher = el('button', 'launcher');
    launcher.innerHTML = '<span aria-hidden="true">◆</span> Design & quote';
    lShadow.appendChild(launcher);

    hostEl.className = 'popup-host';
    hostEl.style.cssText = 'position:fixed;right:20px;bottom:88px;z-index:2147483000;display:none';
    var widget = new Widget(hostEl);
    var started = false;
    widget.toggle = function (open) {
      hostEl.style.display = open ? 'block' : 'none';
      launcher.style.display = open ? 'none' : 'flex';
      widget.opened = open;
      if (open && !started) { started = true; widget.mount(); }
    };
    launcher.addEventListener('click', function () { widget.toggle(true); });
    window.CADQuoteBot = widget;
  }

  function boot() {
    if (opts.mode === 'popup') mountPopup(); else mountInline();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

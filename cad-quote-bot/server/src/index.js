import express from 'express';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config, assertConfig } from './config.js';
import { initStore, getSession, getLead, listLeads, pruneSessions, paths } from './store.js';
import * as flow from './flow.js';
import { checkModel, checkStructuredOutput } from './llm.js';
import { checkOpenscad } from './openscad.js';
import { rateLimit } from './ratelimit.js';
import { readLocalFile, contentTypeFor } from './storage.js';
import { renderViewerPage } from './viewer.js';
import { renderQuotePreview, renderRequestList } from './notify.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const app = express();
app.set('trust proxy', true);
app.use(express.json({ limit: '64kb' }));

/* ------------------------------- CORS ------------------------------- */
const allowAll = config.allowedOrigins.includes('*');
app.use((req, res, next) => {
  const origin = req.get('origin');
  if (origin && (allowAll || config.allowedOrigins.includes(origin))) {
    res.set('Access-Control-Allow-Origin', origin);
    res.set('Vary', 'Origin');
  } else if (!origin && allowAll) {
    res.set('Access-Control-Allow-Origin', '*');
  }
  res.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type');
  res.set('Access-Control-Max-Age', '86400');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  return next();
});

const ip = (req) => (req.headers['x-forwarded-for']?.split(',')[0] || req.ip || 'unknown').trim();

/** Everything the widget needs to render, and nothing it shouldn't see. */
function snapshot(session, since = 0) {
  return {
    sessionId: session.id,
    state: session.state,
    ui: flow.uiFor(session),
    messages: session.messages.slice(since).map((m) => ({ id: m.id, role: m.role, text: m.text, card: m.card })),
    messageCount: session.messages.length,
    generating: session.state === 'generating',
  };
}

async function loadSession(req, res) {
  const session = await getSession(req.body?.sessionId || req.params?.sessionId || req.query?.sessionId);
  if (!session) {
    // The widget starts a fresh chat when it sees this code — sessions do not
    // survive a restart on a host without persistent storage.
    res.status(404).json({ error: 'session_not_found', message: 'That chat has expired. Starting a new one.' });
    return null;
  }
  return session;
}

/* ------------------------------ routes ------------------------------ */

app.get('/healthz', (req, res) => res.json({
  ok: true,
  notifyMode: config.notify.mode,
  publicUrl: config.publicUrl,
  warnings: assertConfig(),
}));

// Deep check for a fresh deploy: does the disk work, is OpenSCAD installed, is
// the API key accepted? Answers the "why did the chat say it failed" question
// without needing the logs. The Claude call costs a fraction of a cent.
app.get('/diag', async (req, res) => {
  if (!rateLimit(`d:${ip(req)}`, 20).ok) return res.status(429).json({ error: 'rate_limited' });

  const checks = {};

  checks.config = {
    publicUrl: config.publicUrl,
    dataDir: paths.dataDir,
    storageDriver: config.storage.driver,
    notifyMode: config.notify.mode,
    allowedOrigins: config.allowedOrigins,
    model: config.anthropic.model,
    anthropicKeyPresent: Boolean(config.anthropic.apiKey),
    adminPageEnabled: Boolean(config.adminKey),
    warnings: assertConfig(),
  };

  try {
    const probe = path.join(paths.dataDir, `.diag-${Date.now()}`);
    await fs.writeFile(probe, 'ok');
    await fs.rm(probe, { force: true });
    checks.storage = { ok: true, writable: paths.dataDir };
  } catch (err) {
    checks.storage = { ok: false, error: `${err.code || ''} ${err.message}`.trim() };
  }

  checks.openscad = await checkOpenscad();
  checks.claude = await checkModel();

  // ?full=1 also runs the first real call of a conversation. Slower and a few
  // cents, but it is the check that catches a rejected request shape.
  if (req.query.full) checks.structuredOutput = await checkStructuredOutput();

  const ok = Object.values(checks).every((c) => c.ok !== false);
  return res.status(ok ? 200 : 503).json({ ok, checks });
});

app.post('/api/session', async (req, res, next) => {
  try {
    if (!rateLimit(`s:${ip(req)}`, config.limits.maxSessionsPerIpPerHour).ok) {
      return res.status(429).json({ error: 'rate_limited', message: 'Too many chats started from this connection. Try again later.' });
    }
    const session = await flow.start({
      ip: ip(req),
      origin: req.get('origin') || null,
      referer: req.get('referer') || null,
      userAgent: (req.get('user-agent') || '').slice(0, 300),
      startedAt: new Date().toISOString(),
    });
    return res.json(snapshot(session));
  } catch (err) { return next(err); }
});

app.post('/api/message', async (req, res, next) => {
  try {
    if (!rateLimit(`m:${ip(req)}`, config.limits.maxMessagesPerIpPerHour).ok) {
      return res.status(429).json({ error: 'rate_limited', message: 'Too many messages. Try again later.' });
    }
    const session = await loadSession(req, res);
    if (!session) return undefined;
    const since = session.messages.length;
    await flow.handleMessage(session, req.body.text);
    return res.json(snapshot(session, since));
  } catch (err) { return next(err); }
});

app.post('/api/action', async (req, res, next) => {
  try {
    const session = await loadSession(req, res);
    if (!session) return undefined;
    const since = session.messages.length;
    await flow.handleAction(session, String(req.body.action || ''));
    return res.json(snapshot(session, since));
  } catch (err) { return next(err); }
});

// Polled while a model is generating (and after any reconnect).
app.get('/api/session/:sessionId', async (req, res, next) => {
  try {
    const session = await loadSession(req, res);
    if (!session) return undefined;
    const since = Math.max(0, Number(req.query.since) || 0);
    return res.json(snapshot(session, since));
  } catch (err) { return next(err); }
});

app.post('/api/lead', async (req, res, next) => {
  try {
    const session = await loadSession(req, res);
    if (!session) return undefined;
    if (session.state !== 'details') {
      return res.status(409).json({ error: 'wrong_state', message: 'This chat is not at the contact-details step.' });
    }
    // Honeypot: real customers never fill a hidden field.
    if (String(req.body.company || '').trim()) return res.status(202).json(snapshot(session, session.messages.length));
    const since = session.messages.length;
    const result = await flow.submitLead(session, req.body);
    if (!result.ok) return res.status(400).json({ error: 'validation', message: 'Please check the highlighted fields.', errors: result.errors });
    return res.json(snapshot(session, since));
  } catch (err) { return next(err); }
});

/* --------------------- quote previews (no email) --------------------- */

// The notification as it would arrive, rendered in the browser. Addressed by an
// unguessable id so the customer can be handed the link in chat.
// No scripts, so lock the page down.
const PREVIEW_CSP = "default-src 'none'; img-src * data:; style-src 'unsafe-inline'; frame-ancestors 'none'";

app.get('/quote/:leadId', async (req, res) => {
  const lead = await getLead(req.params.leadId);
  if (!lead) return res.status(404).send('Quote request not found.');
  res.set('Content-Type', 'text/html; charset=utf-8');
  res.set('Content-Security-Policy', PREVIEW_CSP);
  res.set('X-Robots-Tag', 'noindex');
  return res.send(renderQuotePreview(lead, req.query.view === 'customer' ? 'customer' : 'owner'));
});

// Every request received. Off unless ADMIN_KEY is set, because it lists
// customers' contact details.
app.get('/requests', async (req, res) => {
  if (!config.adminKey) return res.status(404).send('Set ADMIN_KEY to enable this page.');
  if (req.query.key !== config.adminKey) return res.status(401).send('Add ?key=<ADMIN_KEY> to this URL.');
  res.set('Content-Type', 'text/html; charset=utf-8');
  res.set('Content-Security-Policy', PREVIEW_CSP);
  res.set('X-Robots-Tag', 'noindex');
  return res.send(renderRequestList(await listLeads(200), config.adminKey));
});

/* ------------------------- files and viewer ------------------------- */

app.get('/files/*', async (req, res) => {
  if (config.storage.driver !== 'local') return res.status(404).end();
  const key = decodeURIComponent(req.params[0] || '');
  const file = await readLocalFile(key);
  if (!file) return res.status(404).end();
  res.set('Content-Type', contentTypeFor(key));
  res.set('Cache-Control', 'private, max-age=86400');
  if (key.endsWith('.stl')) res.set('Content-Disposition', `attachment; filename="${path.basename(key)}"`);
  return res.send(file);
});

app.get('/viewer/:sessionId/:jobId', async (req, res) => {
  const session = await getSession(req.params.sessionId);
  const job = session?.job;
  if (!job || job.id !== req.params.jobId || job.status !== 'done') return res.status(404).send('Model not found or expired.');
  res.set('Content-Type', 'text/html; charset=utf-8');
  return res.send(renderViewerPage({
    title: session.spec?.title || 'Your part',
    stlUrl: job.stlUrl,
    stats: job.stats,
  }));
});

// The demo page, served from this host so a fresh deploy is testable at its own
// URL with nothing else to set up. The API and widget URLs are rewritten to
// wherever this server is actually running.
app.get('/', async (req, res, next) => {
  try {
    const html = await fs.readFile(path.join(here, '..', '..', 'embed', 'demo.html'), 'utf8');
    res.set('Content-Type', 'text/html; charset=utf-8');
    return res.send(html
      .replaceAll('http://localhost:8080', config.publicUrl)
      .replace('./cad-quote-widget.js', '/embed/cad-quote-widget.js'));
  } catch (err) { return next(err); }
});

// three.js is served from here rather than a CDN: one less third party, and it
// keeps working behind strict Content-Security-Policy headers.
app.use('/vendor', express.static(path.join(here, '..', 'node_modules', 'three', 'build'), {
  maxAge: '30d',
  immutable: true,
}));

// Convenience: serve the embed script from the API host so a site only needs one tag.
app.use('/embed', express.static(path.join(here, '..', '..', 'embed'), {
  setHeaders: (res) => res.set('Access-Control-Allow-Origin', '*'),
}));

/* ------------------------------ errors ------------------------------ */

app.use((err, req, res, next) => { // eslint-disable-line no-unused-vars
  console.error('[error]', err);
  const status = err.code === 'refusal' ? 400 : 500;
  res.status(status).json({
    error: err.code || 'server_error',
    message: err.code === 'refusal'
      ? 'I can\'t help with that particular request. Try describing a different part.'
      : 'Something went wrong on our side. Please try again.',
    // Not shown in the chat, but visible in the network tab and the logs — the
    // difference between "it broke" and knowing why.
    detail: String(err?.error?.error?.message || err?.message || '').slice(0, 300) || undefined,
    upstreamStatus: err?.status ?? undefined,
  });
});

/* ------------------------------ startup ----------------------------- */

await initStore();
for (const warning of assertConfig()) console.warn(`[config] ${warning}`);

setInterval(() => {
  pruneSessions().then((n) => n && console.log(`[store] pruned ${n} expired sessions`));
}, 3600_000).unref();

app.listen(config.port, () => {
  console.log(`${config.brand.name} listening on :${config.port} (public: ${config.publicUrl})`);
  console.log(`[notify] mode: ${config.notify.mode}${config.notify.mode === 'preview' ? ' — quote requests are viewable in the browser, not emailed' : ` -> ${config.notify.to.join(', ')}`}`);
  if (config.adminKey) console.log(`[admin] quote requests: ${config.publicUrl}/requests?key=${config.adminKey}`);
  else console.log('[admin] set ADMIN_KEY to enable the /requests list');
});

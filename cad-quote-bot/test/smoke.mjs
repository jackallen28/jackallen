/**
 * End-to-end smoke test — no API key, no OpenSCAD install, no email sent.
 *
 *   npm run test:smoke        (from cad-quote-bot/server)
 *
 * It boots the real server against a stub Claude API and a stub OpenSCAD
 * binary, then drives one complete conversation: brief -> questions -> spec ->
 * generate -> viewer -> quote request, asserting the state machine at each step.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const API = 'http://127.0.0.1:8099';
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cadbot-test-'));
const children = [];
let failures = 0;

function check(label, condition, detail = '') {
  const mark = condition ? '  ok  ' : ' FAIL ';
  if (!condition) failures += 1;
  console.log(`${mark} ${label}${detail && !condition ? ` — ${detail}` : ''}`);
}

function spawnChild(label, cmd, args, env) {
  const child = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  children.push(child);
  const log = [];
  child.stdout.on('data', (d) => log.push(String(d)));
  child.stderr.on('data', (d) => log.push(String(d)));
  child.on('exit', (code) => { if (code) console.error(`[${label}] exited ${code}\n${log.join('')}`); });
  return { child, log };
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForHealth(tries = 40) {
  for (let i = 0; i < tries; i += 1) {
    try {
      const res = await fetch(`${API}/healthz`);
      if (res.ok) return true;
    } catch { /* not up yet */ }
    await wait(250);
  }
  return false;
}

const post = async (p, body) => {
  const res = await fetch(API + p, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
};

try {
  spawnChild('stub-api', process.execPath, [path.join(here, 'fake-anthropic.mjs')], {});
  const server = spawnChild('server', process.execPath, [path.join(here, '..', 'server', 'src', 'index.js')], {
    ANTHROPIC_BASE_URL: 'http://127.0.0.1:9333',
    ANTHROPIC_API_KEY: 'sk-test',
    QUOTE_NOTIFY_EMAIL: 'owner@example.com',
    // Stub renderer by default so the suite is hermetic and instant. Set
    // OPENSCAD_BIN=openscad to run it against the real thing.
    OPENSCAD_BIN: process.env.OPENSCAD_BIN || path.join(here, 'bin', 'openscad'),
    OPENSCAD_XVFB: process.env.OPENSCAD_XVFB || 'false',
    DATA_DIR: dataDir,
    PORT: '8099',
    PUBLIC_URL: API,
    RESEND_API_KEY: '',
    SMTP_HOST: '',
    ADMIN_KEY: 'test-key',
  });

  check('server starts and answers /healthz', await waitForHealth());

  let snap = (await post('/api/session', {})).body;
  const id = snap.sessionId;
  check('session starts in the brief state', snap.state === 'brief', snap.state);

  snap = (await post('/api/message', { sessionId: id, text: 'a wall bracket to hold a 90 mm diameter torch' })).body;
  check('a brief produces intake questions', snap.state === 'questions' && snap.ui.chips.length > 0);

  for (const answer of ['250 mm', 'Timber stud', 'Horizontal']) {
    snap = (await post('/api/message', { sessionId: id, text: answer })).body;
  }
  check('answering every question produces a spec to confirm', snap.state === 'summary', snap.state);

  snap = (await post('/api/action', { sessionId: id, action: 'spec_change' })).body;
  check('"change something" reopens the spec', snap.state === 'change', snap.state);
  snap = (await post('/api/message', { sessionId: id, text: 'make the back plate 8 mm thick' })).body;
  check('a change request rebuilds the spec', snap.state === 'summary', snap.state);

  snap = (await post('/api/action', { sessionId: id, action: 'spec_ok' })).body;
  check('approving the spec starts generation', snap.state === 'generating', snap.state);

  let since = snap.messageCount;
  for (let i = 0; i < 40 && snap.state === 'generating'; i += 1) {
    await wait(500);
    snap = await (await fetch(`${API}/api/session/${id}?since=${since}`)).json();
    if (snap.messages.length) since = snap.messageCount;
  }
  check('generation finishes and asks for review', snap.state === 'review', snap.state);

  const preview = snap.messages.map((m) => m.card).find((c) => c && c.type === 'preview')
    || JSON.parse(fs.readFileSync(path.join(dataDir, 'sessions', `${id}.json`), 'utf8')).messages
      .map((m) => m.card).find((c) => c && c.type === 'preview');
  check('a preview card with a viewer link is returned', Boolean(preview?.viewerUrl && preview?.stlUrl));
  // The stub binary emits a 20 mm cube; real OpenSCAD builds the stub API's
  // 40 mm one.
  const expectedVolume = process.env.OPENSCAD_BIN ? 64 : 8;
  check(`the STL is measured (${expectedVolume} cm³)`, preview?.stats?.volumeCm3 === expectedVolume, JSON.stringify(preview?.stats));

  const viewer = await fetch(preview.viewerUrl);
  const viewerHtml = await viewer.text();
  check('the viewer page renders', viewer.ok && viewerHtml.includes('Return to chat'));
  check('the viewer self-hosts three.js', viewerHtml.includes('/vendor/three.min.js'));
  check('three.js is actually served', (await fetch(`${API}/vendor/three.min.js`)).ok);
  check('the STL downloads', (await fetch(preview.stlUrl)).ok);

  check('unknown models 404', (await fetch(`${API}/viewer/s_deadbeefdeadbeefdeadbeef/j_x`)).status === 404);
  check('path traversal on /files is refused', (await fetch(`${API}/files/../../../etc/passwd`)).status === 404);

  snap = (await post('/api/action', { sessionId: id, action: 'design_ok' })).body;
  check('approving the design asks for contact details', snap.state === 'details' && snap.ui.mode === 'form');

  const bad = await post('/api/lead', { sessionId: id, name: 'A', email: 'nope', phone: '1', postcode: '', quantity: 0, leadtime: 'x' });
  check('invalid contact details are rejected field by field',
    bad.status === 400 && Object.keys(bad.body.errors).length === 6, JSON.stringify(bad.body));

  const hp = await post('/api/lead', { sessionId: id, company: 'spam-bot', name: 'Bot', email: 'b@b.co', phone: '0400000000', postcode: '3000', quantity: 1, leadtime: 'Flexible / no rush' });
  check('the honeypot silently drops bot submissions', hp.status === 202);

  const good = await post('/api/lead', {
    sessionId: id, name: 'Jack Allen', email: 'jack@example.com', phone: '0412 345 678',
    postcode: '3000', quantity: 25, leadtime: 'Within 2 weeks', notes: 'Matte black if possible',
  });
  check('a valid quote request completes the chat', good.status === 200 && good.body.state === 'done', JSON.stringify(good.body).slice(0, 120));

  const leads = fs.readFileSync(path.join(dataDir, 'leads.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  check('the lead is persisted with its spec and files', leads.length === 1 && Boolean(leads[0].files.stl) && leads[0].quantity === 25);

  const leadId = leads[0].id;
  const linkCard = good.body.messages.map((m) => m.card).find((c) => c && c.type === 'link');
  check('the chat offers a preview link instead of emailing', linkCard?.url?.endsWith(`/quote/${leadId}`), JSON.stringify(linkCard));

  const ownerView = await (await fetch(`${API}/quote/${leadId}`)).text();
  check('the preview shows the request as you would receive it',
    ownerView.includes('PREVIEW') && ownerView.includes('Jack Allen') && ownerView.includes('0412 345 678') && ownerView.includes('Open 3D viewer'));
  const customerView = await (await fetch(`${API}/quote/${leadId}?view=customer`)).text();
  check('the customer copy is previewable too', customerView.includes('got your design request'));
  check('an unknown quote id 404s', (await fetch(`${API}/quote/q_${'0'.repeat(24)}`)).status === 404);

  check('/requests needs the admin key', (await fetch(`${API}/requests`)).status === 401);
  const list = await fetch(`${API}/requests?key=test-key`);
  check('/requests lists the request with the key', list.ok && (await list.text()).includes('Jack Allen'));

  // Diagnostics: the endpoint a fresh deploy is debugged with.
  const diag = await (await fetch(`${API}/diag`)).json();
  check('/diag reports the config, storage and OpenSCAD',
    diag.checks.config.anthropicKeyPresent && diag.checks.storage.ok === true && 'ok' in diag.checks.openscad,
    JSON.stringify(diag.checks).slice(0, 200));
  check('/diag reaches the model', diag.checks.claude.ok === true, JSON.stringify(diag.checks.claude));

  // An expired session must be reported in a way the widget can recover from.
  const expired = await post('/api/message', { sessionId: `s_${'a'.repeat(24)}`, text: 'hello' });
  check('an expired session returns a recoverable error',
    expired.status === 404 && expired.body.error === 'session_not_found' && Boolean(expired.body.message),
    JSON.stringify(expired.body));

  const home = await fetch(`${API}/`);
  const homeHtml = await home.text();
  check('the hosted demo page points the widget at this server',
    home.ok && homeHtml.includes(`data-api="${API}"`) && homeHtml.includes('/embed/cad-quote-widget.js'));
} finally {
  for (const child of children) child.kill();
  fs.rmSync(dataDir, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} check(s) failed` : '\nAll checks passed');
process.exit(failures ? 1 : 0);

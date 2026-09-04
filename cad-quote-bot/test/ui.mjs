/**
 * Browser test — drives the real widget in headless Chromium against the same
 * stubs the smoke test uses, and writes screenshots to test/screenshots/.
 *
 *   npm i -D playwright && npx playwright install chromium
 *   npm run test:ui        (from cad-quote-bot/server)
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const API = 'http://127.0.0.1:8099';
const SITE = 'http://127.0.0.1:8100';
const shots = path.join(here, 'screenshots');

let chromium;
for (const specifier of ['playwright', '/opt/node22/lib/node_modules/playwright/index.mjs']) {
  try { ({ chromium } = await import(specifier)); break; } catch { /* try the next one */ }
}
if (!chromium) {
  console.error('Playwright is not installed. Run:  npm i -D playwright && npx playwright install chromium');
  process.exit(2);
}

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cadbot-ui-'));
const children = [];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const check = (label, ok, detail = '') => {
  if (!ok) failures += 1;
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${!ok && detail ? ` — ${detail}` : ''}`);
};

// Serve the embed folder on a second origin, so the run exercises CORS the way
// a real customer's website does.
const site = http.createServer((req, res) => {
  const file = path.join(here, '..', 'embed', req.url === '/' ? 'demo.html' : req.url.split('?')[0]);
  try {
    let body = fs.readFileSync(file, 'utf8');
    if (file.endsWith('.html')) body = body.replaceAll('http://localhost:8080', API);
    res.writeHead(200, { 'Content-Type': file.endsWith('.js') ? 'text/javascript' : 'text/html' });
    res.end(body);
  } catch { res.writeHead(404).end(); }
}).listen(8100);

function spawnChild(cmd, args, env) {
  const child = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  children.push(child);
  return child;
}

let browser;
try {
  spawnChild(process.execPath, [path.join(here, 'fake-anthropic.mjs')], {});
  spawnChild(process.execPath, [path.join(here, '..', 'server', 'src', 'index.js')], {
    ANTHROPIC_BASE_URL: 'http://127.0.0.1:9333',
    ANTHROPIC_API_KEY: 'sk-test',
    QUOTE_NOTIFY_EMAIL: 'owner@example.com',
    ADMIN_KEY: 'test-key',
    ALLOWED_ORIGINS: SITE,
    // Stub renderer by default so the suite is hermetic and instant. Set
    // OPENSCAD_BIN=openscad to run it against the real thing.
    OPENSCAD_BIN: process.env.OPENSCAD_BIN || path.join(here, 'bin', 'openscad'),
    OPENSCAD_XVFB: process.env.OPENSCAD_XVFB || 'false',
    DATA_DIR: dataDir,
    PORT: '8099',
    PUBLIC_URL: API,
    RESEND_API_KEY: '',
    SMTP_HOST: '',
  });
  for (let i = 0; i < 40; i += 1) {
    try { if ((await fetch(`${API}/healthz`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }

  fs.mkdirSync(shots, { recursive: true });
  browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });

  await page.goto(`${SITE}/demo.html`);
  const bot = page.locator('#cad-quote-bot'); // Playwright pierces the shadow root

  await bot.locator('textarea.input').waitFor({ timeout: 15000 });
  check('the widget mounts and greets the visitor', await bot.locator('.msg.bot').first().isVisible());

  // An expired session (every restart on a host without a disk) must recover
  // silently rather than dead-ending on an error.
  await page.evaluate(() => { window.CADQuoteBot.sessionId = 's_' + 'a'.repeat(24); });
  await bot.locator('textarea.input').fill('hello');
  await bot.locator('button.btn.primary').click();
  await page.waitForTimeout(2000);
  const recovered = await page.evaluate(() => window.CADQuoteBot.sessionId);
  check('an expired session silently starts a new chat',
    recovered && recovered !== 's_' + 'a'.repeat(24) && (await bot.locator('.error').count()) === 0,
    String(recovered));
  errors.length = 0; // the deliberate 404 above is expected

  await bot.locator('textarea.input').fill('a wall bracket to hold a 90 mm diameter torch');
  await bot.locator('button.btn.primary').click();
  await bot.locator('.chip').first().waitFor({ timeout: 20000 });
  check('intake questions arrive with tappable options', (await bot.locator('.chip').count()) > 0);

  for (let i = 0; i < 3; i += 1) {
    await bot.locator('.chip').first().click();
    await page.waitForTimeout(1200);
  }
  await bot.locator('button', { hasText: 'Looks right' }).waitFor({ timeout: 20000 });
  await page.screenshot({ path: path.join(shots, '1-spec.png') });
  check('the spec is shown with confirm/change buttons', true);

  await bot.locator('button', { hasText: 'Looks right' }).click();
  await bot.locator('button', { hasText: 'Open 3D viewer' }).waitFor({ timeout: 60000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(shots, '2-preview.png') });
  check('the render preview card appears', await bot.locator('.card img').isVisible());

  const [viewer] = await Promise.all([
    page.context().waitForEvent('page'),
    bot.locator('button', { hasText: 'Open 3D viewer' }).click(),
  ]);
  await viewer.waitForLoadState('domcontentloaded');
  await viewer.waitForFunction(() => document.getElementById('status')?.classList.contains('hidden'), null, { timeout: 30000 });
  await viewer.screenshot({ path: path.join(shots, '3-viewer.png') });
  check('the 3D viewer opens in a new tab and loads the mesh', true);

  await viewer.click('#back');
  await page.waitForTimeout(800);
  check('"Return to chat" closes the viewer tab', viewer.isClosed());

  await bot.locator('button', { hasText: 'Approve this design' }).click();
  await bot.locator('form.lead').waitFor({ timeout: 15000 });
  await bot.locator('#f_name').fill('Jack Allen');
  await bot.locator('#f_email').fill('jack@example.com');
  await bot.locator('#f_phone').fill('0412 345 678');
  await bot.locator('#f_postcode').fill('3000');
  await bot.locator('#f_quantity').fill('25');
  await bot.locator('#f_leadtime').selectOption('Within 2 weeks');
  await page.screenshot({ path: path.join(shots, '4-details.png') });
  check('the contact form renders every field', (await bot.locator('form.lead input, form.lead select, form.lead textarea').count()) >= 7);

  await bot.locator('button', { hasText: 'Request my quote' }).click();
  await page.waitForSelector('#cad-quote-bot >> text=that\'s with us', { timeout: 20000 });
  await page.screenshot({ path: path.join(shots, '5-done.png') });
  check('the request is submitted and confirmed in-chat', true);

  // Preview mode: the request is opened in a tab instead of emailed.
  const [preview] = await Promise.all([
    page.context().waitForEvent('page'),
    bot.locator('button', { hasText: 'Preview the quote request' }).click(),
  ]);
  await preview.waitForLoadState('domcontentloaded');
  await preview.screenshot({ path: path.join(shots, '6-quote-preview.png'), fullPage: true });
  check('the quote request preview opens with the customer\'s details',
    (await preview.content()).includes('Jack Allen') && (await preview.content()).includes('PREVIEW'));

  await preview.goto(`${API}/requests?key=test-key`);
  await preview.screenshot({ path: path.join(shots, '7-requests.png'), fullPage: true });
  check('the /requests list shows the submitted request', (await preview.content()).includes('Jack Allen'));
  await preview.close();

  check('no JavaScript errors on the page', errors.length === 0, errors.join(' | '));
  console.log(`\nScreenshots: ${shots}`);
} finally {
  if (browser) await browser.close();
  site.close();
  for (const child of children) child.kill();
  fs.rmSync(dataDir, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} check(s) failed` : '\nAll checks passed');
process.exit(failures ? 1 : 0);

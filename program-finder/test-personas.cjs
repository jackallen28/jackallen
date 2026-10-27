// Acceptance tests for program-finder.html (dev-only tooling; nothing here ships).
// Run: node program-finder/test-personas.cjs
const { chromium } = require('playwright');
const path = require('path');
const assert = require('assert');

const FILE = 'file://' + path.join(__dirname, 'program-finder.html');
const base = { year: null, coding: 1, spread: 50, electronics: 0, tools: [], goals: { quick: 2, build: 1, code: 1, data: 1 }, subjects: {}, project: 'either', time: 'full' };
const mk = (o) => Object.assign({}, base, o, { goals: Object.assign({}, base.goals, o.goals || {}) });

// expect: start ids (any of), stretch ids (any of, or null = not checked)
const personas = [
  ['A Year 7 beginners', mk({ year: '7', coding: 0, electronics: 0, goals: { quick: 3 }, time: 'half' }), ['bin-mb-buttons', 'car-mb-timing'], null],
  ['B Year 8 Scratch class (micro:bit)', mk({ year: '8', coding: 1, electronics: 1, tools: ['microbit'], project: 'car' }), ['car-mb-timing'], ['car-ard-sensor']],
  ['B2 Year 8 Scratch class (micro:bit + MakeCode)', mk({ year: '8', coding: 1, electronics: 1, tools: ['microbit', 'makecode'], project: 'car' }), ['car-mb-timing'], ['car-ard-sensor']],
  ['C Year 9 engineering-keen', mk({ year: '9', coding: 2, electronics: 2, goals: { build: 3 }, subjects: { syseng: 3 }, project: 'bin' }), ['bin-ard-ultra'], ['bin-esp-fill']],
  ['D Year 10 physics and maths', mk({ year: '10', coding: 2, electronics: 2, subjects: { physics: 3, maths: 2 }, project: 'car' }), ['car-ard-speed'], null],
  ['E Year 10 coders', mk({ year: '10', coding: 4, electronics: 1, goals: { data: 3 }, subjects: { acsd: 3, algo: 2 } }), ['bin-pi-ml', 'car-pi-ml'], null],
  ['F Year 10 mixed, many pathways', mk({ year: 'mixed', coding: 2, spread: 90, subjects: { syseng: 2, acsd: 2, physics: 1 } }), ['bin-ard-ultra', 'car-ard-sensor'], ['bin-esp-fill', 'bin-pi-ml', 'car-esp-web', 'car-pi-ml']],
  ['G Short visit, keen coders', mk({ year: '10', coding: 4, time: 'half' }), ['bin-ard-ultra', 'car-ard-sensor', 'bin-esp-fill', 'car-esp-web'], null],
  ['H Own ideas', mk({ year: '9', coding: 2, project: 'own' }), ['own-guided'], null]
];

(async () => {
  const browser = await chromium.launch();
  let failed = 0;
  const check = (name, fn) => { try { fn(); console.log('ok   ' + name); } catch (e) { failed++; console.log('FAIL ' + name + ': ' + e.message); } };

  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const requests = [];
  ctx.on('request', (r) => requests.push(r.url()));
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(FILE);

  for (const [name, st, startIds, stretchIds] of personas) {
    const res = await page.evaluate((s) => {
      const r = buildResult(s);
      return { start: r.start.id, suggested: r.suggested.id, platform: r.suggested.platformKey, stretch: r.stretch && r.stretch.v.id, reasons: r.reasons, ranked: r.ranked.slice(0, 3).map(x => x.v.id + ':' + x.p.total.toFixed(2)) };
    }, st);
    check(name, () => {
      const got = res.start === 'own-guided' ? 'own-guided' : res.start;
      assert(startIds.includes(got), 'start ' + got + ' not in ' + startIds + ' (top: ' + res.ranked + ')');
      if (stretchIds) assert(res.stretch && stretchIds.includes(res.stretch), 'stretch ' + res.stretch + ' not in ' + stretchIds);
      assert(res.reasons.length >= 2 && res.reasons.length <= 3, 'reasons: ' + res.reasons.length);
    });
    if (name.startsWith('G')) check('G is not a Pi ML version', () => assert(!/-pi-ml$/.test(res.start)));
    if (name.startsWith('H')) check('H suggests a platform', () => assert(['arduino', 'arduino-wifi', 'microbit', 'pi'].includes(res.platform)));
  }

  // Curriculum links come from the workbook rows (see import-curriculum.py).
  const cur = (o, id) => page.evaluate(([s, vid]) => { const v = CFG.variants.find(x => x.id === vid); const c = buildCurriculum(s, v); return { codes: c.items.concat(c.topUp).map(x => x.code), pathways: c.pathways.map(x => x.study), n: c.items.length + c.topUp.length, links: c.items.concat(c.topUp).concat(c.pathways).every(x => x.link) }; }, [mk(o), id]);
  for (const year of ['7', '8', '9', '10', 'mixed']) {
    for (const vid of ['bin-mb-buttons', 'bin-mb-radio', 'bin-ard-ultra', 'bin-esp-fill', 'bin-pi-ml', 'car-mb-timing', 'car-ard-sensor', 'car-ard-speed', 'car-esp-web', 'car-pi-ml']) {
      const c = await cur({ year }, vid);
      check('curriculum ' + year + ' ' + vid + ' (' + c.codes.length + ' codes)', () => { assert(c.n >= 3 && c.n <= 5, 'got ' + c.n); assert(new Set(c.codes).size === c.codes.length); assert(c.codes.every(x => /^VC2/.test(x))); assert(c.links); });
    }
  }
  const has = async (o, id, code) => (await cur(o, id)).codes.includes(code);
  assert(await has({ year: '8' }, 'car-ard-speed', 'VC2M8M07') && !(await has({ year: '8' }, 'car-ard-sensor', 'VC2M8M07')));
  assert(await has({ year: '9' }, 'bin-esp-fill', 'VC2TDI10S01'));
  assert(await has({ year: '10' }, 'bin-pi-ml', 'VC2S10I06'));
  const pw = async (o, id) => (await cur(o, id)).pathways;
  const sePw = await pw({ year: '10', subjects: { syseng: 3 } }, 'bin-ard-ultra');
  assert(sePw.length >= 1 && sePw.every(x => x === 'Systems Engineering'), 'SE: ' + sePw);
  const acPw = await pw({ year: '10', subjects: { acsd: 3, algo: 2 } }, 'bin-pi-ml');
  assert(acPw.includes('Applied Computing') && acPw.includes('Algorithmics') && !acPw.includes('Systems Engineering'), 'AC: ' + acPw);
  const vce = await pw({ year: '11-12' }, 'bin-pi-ml');
  assert(['Systems Engineering', 'Applied Computing', 'Algorithmics'].every(x => vce.includes(x)), 'VCE: ' + vce);
  assert((await pw({ year: '7' }, 'bin-mb-buttons')).length === 0);
  console.log('ok   curriculum selection rules');

  // Flow: Years 7-8 never see the pathway screen; defaults tap through quickly.
  const flow = async (year) => {
    const p = await ctx.newPage();
    await p.goto(FILE);
    await p.click('[data-id="' + year + '"]');
    const titles = [];
    for (let i = 0; i < 8; i++) {
      titles.push(await p.textContent('h1'));
      if (await p.$('#result-title')) break;
      await p.click('#next');
    }
    const result = await p.textContent('#result-title');
    return { p, titles, result };
  };
  const t0 = Date.now();
  const y8 = await flow('8');
  const ms = Date.now() - t0;
  check('Year 8 flow has 6 question screens and no pathway screen', () => {
    assert(!y8.titles.includes('Where are they heading?'), y8.titles.join(' | '));
    assert(/recommendation/i.test(y8.result), y8.result);
  });
  check('tapping defaults takes well under 60 seconds (' + ms + ' ms)', () => assert(ms < 10000));
  const y9 = await flow('9');
  check('Year 9 flow includes the pathway screen (7 screens)', () => assert(y9.titles.includes('Where are they heading?')));


  // Result layout: the recommendation is its own box, then what students do; curriculum is collapsed.
  {
    const p = y9.p;
    const boxes = await p.$$eval('.result > .panel, .result > .cols, .result > details', els => els.map(e => e.className.replace(/\s+/g, ' ').trim()));
    check('result order: recommendation, what students do, why/other, curriculum, next steps', () => {
      assert(/^panel hero/.test(boxes[0]) && /^panel does/.test(boxes[1]) && /^cols/.test(boxes[2]) && /curr/.test(boxes[3]) && /next/.test(boxes[4]), boxes.join(' | '));
    });
    const facts = await p.$$eval('.hero dt', e => e.map(x => x.textContent));
    check('recommendation box has Project, Platform and Version', () => assert.deepStrictEqual(facts, ['Project', 'Platform', 'Version']));
      assert.strictEqual(await p.$eval('details.curr', d => d.open), false);
    const words = await p.evaluate(() => document.querySelector('.result').innerText.split(/\s+/).filter(Boolean).length);
    check('result text is succinct (' + words + ' words with curriculum collapsed)', () => assert(words < 260, String(words)));
  }

  // Copy summary: no identifying data; nothing stored; no network.
  const summary = await y9.p.inputValue('textarea.sumtext');
  check('summary has the expected sections and no contact details', () => {
    assert(/RECOMMENDATION/.test(summary) && /CLASS PROFILE/.test(summary));
    assert(!/@|https?:|\b\d{8,}\b/.test(summary), 'summary contains an email, link or phone-like number');
  });
  const stored = await y9.p.evaluate(() => ({ ls: localStorage.length, ss: sessionStorage.length, ck: document.cookie.length }));
  check('storage is empty', () => assert.deepStrictEqual(stored, { ls: 0, ss: 0, ck: 0 }));
  check('no network requests beyond the file itself', () => assert(requests.every(u => u.startsWith('file://')), requests.filter(u => !u.startsWith('file://')).join(',')));
  const html = require('fs').readFileSync(path.join(__dirname, 'program-finder.html'), 'utf8');
  check('no emoji characters in the source', () => assert(!/\p{Extended_Pictographic}/u.test(html), 'found: ' + (html.match(/\p{Extended_Pictographic}/u) || [])[0]));
  check('no external URLs in the source', () => assert(!/(src|href)=["']https?:/i.test(html)));
  check('no page errors', () => assert.deepStrictEqual(errors, []));

  // Screenshots (light and dark, laptop and phone).
  const shots = path.join(process.env.SHOTS || '/tmp', 'finder-shots');
  require('fs').mkdirSync(shots, { recursive: true });
  for (const [scheme, vp] of [['light', { width: 1366, height: 768 }], ['dark', { width: 1366, height: 768 }], ['light', { width: 390, height: 844 }]]) {
    const c = await browser.newContext({ viewport: vp, colorScheme: scheme });
    const p = await c.newPage();
    await p.goto(FILE + '?debug=0');
    await p.click('[data-id="9"]');
    const tag = scheme + '-' + vp.width;
    await p.screenshot({ path: path.join(shots, tag + '-1-year.png') });
    await p.click('#next');
    await p.screenshot({ path: path.join(shots, tag + '-2-coding.png') });
    await p.click('#next'); await p.click('#next');
    await p.screenshot({ path: path.join(shots, tag + '-4-tools.png') });
    await p.click('#next'); await p.click('#next');
    await p.click('.subj .opt >> nth=0'); await p.click('.subj .opt >> nth=3');
    await p.screenshot({ path: path.join(shots, tag + '-6-pathway.png') });
    await p.click('#next');
    await p.screenshot({ path: path.join(shots, tag + '-7-project.png') });
    await p.click('#next');
    await p.waitForTimeout(1600);
    await p.screenshot({ path: path.join(shots, tag + '-8-result.png'), fullPage: true });
    await c.close();
  }

  // No scrolling on a laptop for each question screen.
  {
    const p = await ctx.newPage();
    await p.goto(FILE);
    await p.click('[data-id="9"]');
    for (let i = 0; i < 7; i++) {
      const title = await p.textContent('h1');
      if (i === 5) { await p.click('.subj .opt >> nth=0'); await p.click('.subj .opt >> nth=1'); }
      const over = await p.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
      check('no scroll needed at 1366x768: ' + title + ' (overflow ' + over + 'px)', () => assert(over <= 0));
      await p.click('#next');
    }
  }

  await browser.close();
  console.log(failed ? '\n' + failed + ' check(s) failed' : '\nAll checks passed');
  process.exit(failed ? 1 : 0);
})();

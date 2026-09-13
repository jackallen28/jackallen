import { io } from 'socket.io-client';

const URL = 'http://localhost:3299';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const emit = (sock, ev, payload) => new Promise((res) => sock.emit(ev, payload, res));
let failures = 0;
function check(label, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${extra ? '  ' + extra : ''}`);
  if (!cond) failures++;
}

const teacher = io(URL);
await new Promise((r) => teacher.on('connect', r));
let tState = null;
teacher.on('teacher:state', (s) => { tState = s; });
const auth = await emit(teacher, 'teacher:auth', { passcode: 'test' });

check('console is offered both languages',
  auth.languages?.map((l) => l.code).join(',') === 'en,zh',
  JSON.stringify(auth.languages?.map((l) => l.native)));
check('report can be produced in both languages',
  auth.reportLanguages?.includes('en') && auth.reportLanguages?.includes('zh'));
check('translation reported as available', auth.translation === true);

// --- roster and room
const CODES = ['AAAA0001', 'BBBB0002', 'CCCC0003', 'DDDD0004'];
const csv = 'login,student\n' + CODES.map((c, i) => `${c},Participant 0${i + 1}`).join('\n');
check('roster uploads', (await emit(teacher, 'teacher:roster', { csv })).ok);
check('room opens', (await emit(teacher, 'teacher:openLobby', {})).ok);
await sleep(150);

// Three English, one Chinese. However the shuffle falls, the Chinese participant
// must land in a mixed pair and the remaining pair must share a language — so both
// branches below are exercised on every run rather than whenever the shuffle obliges.
const LANGS = { AAAA0001: 'en', BBBB0002: 'zh', CCCC0003: 'en', DDDD0004: 'en' };
const people = {};
for (const code of CODES) {
  const sock = io(URL);
  await new Promise((r) => sock.on('connect', r));
  const rec = { sock, code, state: null, msgs: [] };
  sock.on('student:state', (s) => { rec.state = s; });
  sock.on('chat:message', (m) => rec.msgs.push(m));
  people[code] = rec;
  check(`join ${code} as ${LANGS[code]}`, (await emit(sock, 'student:join', { code, lang: LANGS[code] })).ok);
}
await sleep(250);

check('each participant language reaches the console',
  tState.students.every((s) => LANGS[s.code] === s.lang),
  tState.students.map((s) => `${s.code}=${s.lang}`).join(' '));

// An unknown language must not be stored verbatim.
const stray = io(URL);
await new Promise((r) => stray.on('connect', r));
await emit(stray, 'student:join', { code: 'AAAA0001', lang: 'klingon' });
await sleep(200);
check('unknown language falls back to English',
  tState.students.find((s) => s.code === 'AAAA0001')?.lang === 'en');
stray.close();
await sleep(150);
await emit(people.AAAA0001.sock, 'student:join', { code: 'AAAA0001', lang: 'en' });
await sleep(150);

// --- a round with only human pairs, so translation is what is under test
check('round starts', (await emit(teacher, 'teacher:start', { durationSec: 20, aiRatio: 0 })).ok);
await sleep(400);

const pairs = tState.pairs.filter((p) => p.type === 'human');
check('everyone is in a human pair', pairs.length === 2, `${pairs.length} pairs`);

for (const code of CODES) await emit(people[code].sock, 'chat:send', { text: `hello from ${code}` });
await sleep(1800);

// Find one mixed-language pair and one same-language pair, whichever way they fell.
let mixedChecked = false;
let sameChecked = false;
for (const pair of pairs) {
  const [a, b] = pair.members.map((m) => m.login);
  const mixed = LANGS[a] !== LANGS[b];
  const received = people[a].msgs.filter((m) => !m.mine);
  if (received.length === 0) continue;

  if (mixed && !mixedChecked) {
    check('across languages, the recipient gets a translation',
      received.some((m) => m.text.startsWith('TRANSLATED(')), received[0]?.text);
    mixedChecked = true;
  }
  if (!mixed && !sameChecked) {
    check('same language, the text is untouched',
      received.every((m) => !m.text.startsWith('TRANSLATED(')), received[0]?.text);
    sameChecked = true;
  }
}
check('a mixed-language pair was exercised', mixedChecked);
check('a same-language pair was exercised', sameChecked);

check('senders always see their own words',
  CODES.every((c) => people[c].msgs.filter((m) => m.mine)
    .every((m) => m.text === `hello from ${c}`)));

// --- summary is aggregate-only and appears only after the reveal
await emit(teacher, 'teacher:end', {});
await sleep(300);
for (const code of CODES) await emit(people[code].sock, 'guess:submit', { guess: 'human' });
await sleep(300);
check('no class summary while answers are still open',
  CODES.every((c) => !people[c].state?.classSummary));

check('teacher reveals', (await emit(teacher, 'teacher:results', {})).ok);
await sleep(400);
const summary = people[CODES[0]].state?.classSummary;
check('participants now see the class summary', Boolean(summary));
check('summary has only aggregates',
  summary && ['participants', 'overall', 'vsAi', 'vsPeer'].every((k) => k in summary) &&
    !JSON.stringify(summary).includes('AAAA0001'),
  JSON.stringify(summary));
check('everyone was right about their peer', summary?.overall.accuracy === 100,
  String(summary?.overall.accuracy));

// --- the report, in both languages
const en = await emit(teacher, 'teacher:report', { lang: 'en' });
const zh = await emit(teacher, 'teacher:report', { lang: 'zh' });
check('english report builds', en.ok && en.html.includes('By model'));
check('chinese report builds', zh.ok && zh.html.includes('按模型统计'));
check('chinese report declares its language', zh.html.includes('lang="zh-CN"'));
check('chinese report loads a CJK font stack', zh.html.includes('PingFang SC'));
check('the two reports differ', en.html !== zh.html);
check('csv keeps english headers in both',
  en.csv.split('\n')[0] === zh.csv.split('\n')[0] &&
  en.csv.split('\n')[0].startsWith('participant,login,language,'),
  en.csv.split('\n')[0].slice(0, 46));
check('csv records each chosen language',
  en.csv.includes(',zh,') && en.csv.includes(',en,'));
check('transcripts follow the report language',
  zh.zipBase64 && Buffer.from(zh.zipBase64, 'base64').toString('utf8').includes('对话记录'));

// --- free-entry names instead of assigned logins
check('join mode defaults to codes', tState?.joinMode === 'code', tState?.joinMode);
check('mode is locked once the room is open',
  !(await emit(teacher, 'teacher:joinMode', { mode: 'name' })).ok);

check('start over', (await emit(teacher, 'teacher:startOver', {})).ok);
await sleep(250);
check('unknown mode rejected', !(await emit(teacher, 'teacher:joinMode', { mode: 'telepathy' })).ok);
check('switch to name entry', (await emit(teacher, 'teacher:joinMode', { mode: 'name' })).ok);
await sleep(150);
check('console reports the new mode', tState?.joinMode === 'name', tState?.joinMode);

// An un-joined page is told which sign-in to render.
const watcher = io(URL);
const config = await new Promise((r) => watcher.on('session:config', r));
check('sign-in pages are told the mode', config?.joinMode === 'name', JSON.stringify(config));

check('room opens', (await emit(teacher, 'teacher:openLobby', {})).ok);
await sleep(150);

const named = {};
for (const [name, lang] of [['Li Wei', 'zh'], ['Sam', 'en'], ['张老师', 'zh']]) {
  const sock = io(URL);
  await new Promise((r) => sock.on('connect', r));
  const res = await emit(sock, 'student:join', { code: name, lang });
  check(`join as "${name}"`, res.ok === true, res.error || '');
  named[name] = sock;
}
await sleep(250);
check('names are what the console shows',
  ['Li Wei', 'Sam', '张老师'].every((n) => tState.students.some((s) => s.student === n)),
  tState.students.map((s) => s.student).join(' | '));

// A second person cannot take a name that is in use.
const clash = io(URL);
await new Promise((r) => clash.on('connect', r));
const taken = await emit(clash, 'student:join', { code: 'li  WEI', lang: 'en' });
check('a name in use is refused', taken.ok === false && taken.code === 'nameTaken', taken.error || '');
check('refusals carry a code the app can translate', typeof taken.code === 'string');
// Still open on purpose: closing it first would leave this ack unanswered forever.
check('an empty name is refused',
  !(await emit(clash, 'student:join', { code: '   ', lang: 'en' })).ok);
clash.close();
check('three participants, not four', tState.students.length === 3, String(tState.students.length));

// Same name, different spacing and case, after dropping off — that is a reconnect.
named['Li Wei'].close();
await sleep(300);
const again = io(URL);
await new Promise((r) => again.on('connect', r));
const rejoin = await emit(again, 'student:join', { code: '  li wei  ', lang: 'zh' });
check('the same person can come back', rejoin.ok === true, rejoin.error || '');
await sleep(200);
check('coming back does not create a duplicate',
  tState.students.length === 3, String(tState.students.length));
check('the name keeps its original spelling',
  tState.students.some((s) => s.student === 'Li Wei'),
  tState.students.map((s) => s.student).join(' | '));

// Names carry through to the report.
check('name round starts',
  (await emit(teacher, 'teacher:start', { durationSec: 15, aiRatio: 1 })).ok);
await sleep(400);
await emit(teacher, 'teacher:end', {});
await sleep(200);
await emit(teacher, 'teacher:results', {});
await sleep(300);
const namedReport = await emit(teacher, 'teacher:report', { lang: 'en' });
check('the report names the participants',
  namedReport.ok && namedReport.html.includes('张老师') && namedReport.csv.includes('Li Wei'));

again.close();
for (const sock of Object.values(named)) sock.close();
watcher.close();

console.log(`\n${failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED'}`);
teacher.close();
for (const code of CODES) people[code].sock.close();
process.exit(failures === 0 ? 0 : 1);

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

// Two pick English, two pick Chinese.
const LANGS = { AAAA0001: 'en', BBBB0002: 'zh', CCCC0003: 'en', DDDD0004: 'zh' };
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

console.log(`\n${failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED'}`);
teacher.close();
for (const code of CODES) people[code].sock.close();
process.exit(failures === 0 ? 0 : 1);

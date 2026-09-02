import { io } from 'socket.io-client';

const URL = 'http://localhost:3199';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
function check(label, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${extra ? '  ' + extra : ''}`);
  if (!cond) failures++;
}
const emit = (sock, ev, payload) =>
  new Promise((res) => sock.emit(ev, payload, res));

// ---- teacher
const teacher = io(URL);
await new Promise((r) => teacher.on('connect', r));
let tState = null;
teacher.on('teacher:state', (s) => { tState = s; });

check('wrong passcode rejected', !(await emit(teacher, 'teacher:auth', { passcode: 'nope' })).ok);
check('teacher auth', (await emit(teacher, 'teacher:auth', { passcode: 'test' })).ok);
check('start blocked with no students', !(await emit(teacher, 'teacher:start', {})).ok);

// ---- students
const codes = ['100001', '100002', '100003', '100004', '100005'];
const students = {};
for (const code of codes) {
  const sock = io(URL);
  await new Promise((r) => sock.on('connect', r));
  const rec = { sock, code, state: null, msgs: [], typing: 0 };
  sock.on('student:state', (s) => { rec.state = s; });
  sock.on('chat:message', (m) => rec.msgs.push(m));
  sock.on('chat:typing', (t) => { if (t) rec.typing++; });
  students[code] = rec;
  check(`join ${code}`, (await emit(sock, 'student:join', { code })).ok);
}
check('bad code rejected', !(await emit(students['100001'].sock, 'student:join', { code: '12' })).ok);
await sleep(200);
check('teacher sees 5 joined', tState?.stats.joined === 5, `got ${tState?.stats.joined}`);
check('all in lobby', Object.values(students).every((s) => s.state?.phase === 'lobby'));
check('no chat before start', !(await emit(students['100001'].sock, 'chat:send', { text: 'hi' })).ok);

// ---- start
check('start round', (await emit(teacher, 'teacher:start', { durationSec: 15, aiRatio: 0.5 })).ok);
await sleep(300);
check('phase active', tState?.phase === 'active');
check('all 5 paired', tState?.stats.paired === 5, `paired=${tState?.stats.paired}`);
check('mix of ai + human', tState?.stats.withAi > 0 && tState?.stats.withHuman > 0,
  `ai=${tState?.stats.withAi} human=${tState?.stats.withHuman}`);
check('every student in round', Object.values(students).every((s) => s.state?.inRound));
check('endsAt set', typeof tState?.endsAt === 'number');

// late joiner
const late = io(URL);
await new Promise((r) => late.on('connect', r));
let lateState = null;
late.on('student:state', (s) => { lateState = s; });
await emit(late, 'student:join', { code: '999999' });
await sleep(200);
check('late joiner not in round', lateState?.phase === 'active' && lateState?.inRound === false);

// ---- chatting
for (const code of codes) await emit(students[code].sock, 'chat:send', { text: `hey from ${code}` });
await sleep(300);
check('own message echoed', Object.values(students).every((s) => s.msgs.some((m) => m.mine)));
check('rate limit works', !(await emit(students['100001'].sock, 'chat:send', { text: 'spam' })).ok);
check('empty message rejected', !(await emit(students['100002'].sock, 'chat:send', { text: '   ' })).ok);

// human pairs relay
const humanCodes = tState.students.filter((s) => s.partnerType === 'human').map((s) => s.code);
const aiCodes = tState.students.filter((s) => s.partnerType === 'ai').map((s) => s.code);
check('human pair received partner msg',
  humanCodes.every((c) => students[c].msgs.some((m) => !m.mine)),
  `humans=${humanCodes.join(',')}`);

// bot replies (scripted fallback, no API key in this run)
await sleep(5000);
check('AI-paired students got bot replies',
  aiCodes.every((c) => students[c].msgs.some((m) => !m.mine)),
  `ai=${aiCodes.join(',')}`);
check('bot showed typing indicator', aiCodes.every((c) => students[c].typing > 0));

// reconnect mid-round
const rejoin = io(URL);
await new Promise((r) => rejoin.on('connect', r));
let rejoinState = null;
rejoin.on('student:state', (s) => { rejoinState = s; });
await emit(rejoin, 'student:join', { code: codes[0] });
await sleep(250);
check('reconnect restores transcript',
  rejoinState?.inRound === true && rejoinState.transcript.length > 0,
  `${rejoinState?.transcript.length} msgs`);
rejoin.close();
// The reconnect above made `rejoin` the live socket for this student; closing it
// leaves them with none. Hand control back to their original socket.
await emit(students[codes[0]].sock, 'student:join', { code: codes[0] });
await sleep(250);
check('original socket resumes after the extra tab closes',
  students[codes[0]].state?.inRound === true);

// ---- natural round expiry
console.log('  … waiting for the 15s clock to run out');
await sleep(12000);
check('phase auto-advanced to guess', tState?.phase === 'guess', `phase=${tState?.phase}`);
check('students on guess screen',
  codes.every((c) => students[c].state?.phase === 'guess' && !students[c].state.reveal));
check('chat closed after time', !(await emit(students['100003'].sock, 'chat:send', { text: 'late' })).ok);

// ---- guesses
check('bad guess value rejected', !(await emit(students['100001'].sock, 'guess:submit', { guess: 'maybe' })).ok);
for (const code of codes) {
  const partnerType = tState.students.find((s) => s.code === code).partnerType;
  // 100001 deliberately guesses wrong so we can verify scoring both ways.
  const guess = code === '100001' ? (partnerType === 'ai' ? 'human' : 'ai') : partnerType;
  await emit(students[code].sock, 'guess:submit', { guess });
}
await sleep(300);
check('double guess rejected', !(await emit(students['100002'].sock, 'guess:submit', { guess: 'ai' })).ok);
check('all answered', tState?.stats.answered === 5, `answered=${tState?.stats.answered}`);
check('scoring: 4 of 5 correct', tState?.stats.correct === 4, `correct=${tState?.stats.correct}`);
check('accuracy = 80%', tState?.stats.accuracy === 80, `acc=${tState?.stats.accuracy}`);
check('reveal only after guessing',
  codes.every((c) => students[c].state?.reveal),
  'each student has reveal');
check('reveal correctness matches',
  students['100001'].state.reveal.correct === false &&
  codes.slice(1).every((c) => students[c].state.reveal.correct === true));

// ---- results + transcripts
check('show results', (await emit(teacher, 'teacher:results', {})).ok);
await sleep(200);
check('phase results', tState?.phase === 'results');
const tr = await emit(teacher, 'teacher:transcripts', {});
check('transcripts returned', tr.ok && tr.transcripts.length > 0, `${tr.transcripts?.length} convs`);
check('transcripts name the model that replied',
  tr.transcripts.filter((c) => c.type === 'ai')
    .every((c) => c.messages.some((m) => m.isBot && m.sender === c.modelLabel)),
  tr.transcripts.filter((c) => c.type === 'ai').map((c) => c.modelLabel).join(','));

// ---- report on the finished round
const rep = await emit(teacher, 'teacher:report', {});
check('report builds', rep.ok === true, rep.error || '');
check('report is a standalone html page',
  rep.html?.startsWith('<!doctype html>') && rep.html.includes('</html>'));
check('report names every student in the round',
  codes.every((c) => rep.html.includes(c)));
check('report includes transcript text', rep.html.includes('hey from 100001'));
const csvLines = rep.csv.trim().split('\n');
check('report csv is one physical line per student',
  csvLines.length === 6, `${csvLines.length} lines`);
check('report csv embeds the transcript in the row',
  csvLines.slice(1).every((line) => line.includes('hey from ')));
check('report csv header carries the persona',
  rep.csv.split('\n')[0].startsWith('student,partner_type,model,persona,'));
check('report filenames are dated', /^human-or-not_round-\d+_\d{4}-\d{2}-\d{2}_\d{4}\.html$/.test(rep.htmlName),
  rep.htmlName);

// ---- a second round using several models at once
check('reset for multi-model round', (await emit(teacher, 'teacher:reset', { keepStudents: true })).ok);
await sleep(200);
const mix = { 'claude-opus-5': 1, 'claude-sonnet-5': 1, 'claude-haiku-4-5': 1 };
check('start multi-model round',
  (await emit(teacher, 'teacher:start', { durationSec: 15, aiRatio: 1, modelMix: mix })).ok);
await sleep(400);
const aiRows = tState.students.filter((s) => s.partnerType === 'ai');
check('every AI student has a model', aiRows.length > 0 && aiRows.every((s) => s.model),
  aiRows.map((s) => s.modelLabel).join(','));
check('models come from the requested mix',
  aiRows.every((s) => Object.keys(mix).includes(s.model)));
check('more than one model in play', new Set(aiRows.map((s) => s.model)).size > 1,
  `${new Set(aiRows.map((s) => s.model)).size} distinct`);
check('breakdown rows sum to the AI students',
  tState.byModel.reduce((n, r) => n + r.students, 0) === aiRows.length);

// --- classroom personas
check('every AI student is assigned a persona', aiRows.every((s) => s.persona),
  aiRows.map((s) => s.persona).join(','));
check('personas come from the pack (A-D)',
  aiRows.every((s) => ['A', 'B', 'C', 'D'].includes(s.persona)));
check('persona labels are readable',
  aiRows.every((s) => /^[A-D] — .+/.test(s.personaLabel)), aiRows[0]?.personaLabel);
check('persona breakdown sums to the AI students',
  tState.byPersona.reduce((n, r) => n + r.students, 0) === aiRows.length);
check('persona breakdown reports a fooled rate',
  tState.byPersona.every((r) => 'foolRate' in r));

// only the requested personas are used
check('reset before restricting personas', (await emit(teacher, 'teacher:reset', { keepStudents: true })).ok);
await sleep(150);
await emit(teacher, 'teacher:start', {
  durationSec: 15, aiRatio: 1, modelMix: mix, personaMix: { B: 1 },
});
await sleep(300);
check('persona selection is honoured',
  tState.students.filter((s) => s.partnerType === 'ai').every((s) => s.persona === 'B'),
  JSON.stringify(tState.personaMix));

// an unknown persona must not reach the prompt
check('reset before bad persona', (await emit(teacher, 'teacher:reset', { keepStudents: true })).ok);
await sleep(150);
await emit(teacher, 'teacher:start', {
  durationSec: 15, aiRatio: 1, modelMix: mix, personaMix: { Z: 9 },
});
await sleep(300);
check('unknown persona rejected and replaced',
  tState.students.filter((s) => s.partnerType === 'ai').every((s) => s.persona !== 'Z'),
  JSON.stringify(tState.personaMix));
await emit(teacher, 'teacher:end', {});
await sleep(200);

// an unknown model id from the browser must never reach the API
check('reset before rejecting bad model', (await emit(teacher, 'teacher:reset', { keepStudents: true })).ok);
await sleep(150);
await emit(teacher, 'teacher:start', {
  durationSec: 15, aiRatio: 1, modelMix: { 'evil-model-9000': 5 },
});
await sleep(300);
check('unknown model id is rejected and replaced',
  tState.students.filter((s) => s.partnerType === 'ai').every((s) => s.model !== 'evil-model-9000'),
  JSON.stringify(tState.modelMix));

check('breakdown reports fooled vs caught',
  tState.byModel.every((r) => 'foolRate' in r && 'costUsd' in r));

await emit(teacher, 'teacher:end', {});
await sleep(200);

// ---- reset
check('reset keeps roster', (await emit(teacher, 'teacher:reset', { keepStudents: true })).ok);
await sleep(250);
check('back to lobby', tState?.phase === 'lobby' && tState?.stats.joined === 6, `joined=${tState?.stats.joined}`);
check('guesses cleared', tState?.students.every((s) => s.guess === null));
check('students see waiting room', codes.every((c) => students[c].state?.phase === 'lobby'));

// unauthorised control attempt
check('student cannot start a round', !(await emit(students['100001'].sock, 'teacher:start', {})).ok);

console.log(`\n${failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED'}`);
teacher.close();
late.close();
for (const s of Object.values(students)) s.sock.close();
process.exit(failures === 0 ? 0 : 1);

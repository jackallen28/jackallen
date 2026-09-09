/**
 * Offline checks on the local matcher.
 *
 * These run with no API key: they prove that the answers students actually
 * type — typos, partial phrases, their own words — land on the right slot
 * without the game ever needing the network.
 *
 * Run: node test/matcher.test.js
 */

import { ROUNDS, RAPID_FIRE } from '../src/questions.js';
import { judgeBoardGuess, judgeRapidGuess } from '../src/judge.js';

const q = (id) => {
  for (const r of ROUNDS) {
    const found = r.questions.find((x) => x.id === id);
    if (found) return found;
  }
  throw new Error(`no question ${id}`);
};

let pass = 0;
let fail = 0;
const failures = [];

async function expectBoard(questionId, guess, expectedIndex) {
  const question = q(questionId);
  const v = await judgeBoardGuess(guess, question.answers, question.nearMiss || []);
  const ok = v.kind === 'board' && v.index === expectedIndex;
  record(ok, `${questionId} "${guess}" -> answer ${expectedIndex + 1}`,
    `got ${v.kind}:${v.index}`);
}

async function expectNearMiss(questionId, guess, expectedIndex = 0) {
  const question = q(questionId);
  const v = await judgeBoardGuess(guess, question.answers, question.nearMiss || []);
  const ok = v.kind === 'nearmiss' && v.index === expectedIndex;
  record(ok, `${questionId} "${guess}" -> near miss ${expectedIndex + 1}`, `got ${v.kind}:${v.index}`);
}

async function expectNone(questionId, guess) {
  const question = q(questionId);
  const v = await judgeBoardGuess(guess, question.answers, question.nearMiss || []);
  record(v.kind === 'none', `${questionId} "${guess}" -> no match`, `got ${v.kind}:${v.index}`);
}

function record(ok, label, detail) {
  if (ok) { pass++; }
  else { fail++; failures.push(`${label}  (${detail})`); }
}

/* --- exact and near-exact --- */
await expectBoard('r1q2', 'closure', 0);
await expectBoard('r1q2', 'proximity', 1);
await expectBoard('r1q2', 'figure ground', 3);
await expectBoard('r1q2', 'the law of pragnanz', 4);

/* --- typos and phonetic spelling --- */
await expectBoard('r2q2', 'ockhams razer', 2);
await expectBoard('r2q2', 'occams razor', 2);
await expectBoard('r1q1', 'muller lyer illusion', 0);
await expectBoard('r4q2', 'the chinese room', 0);
await expectBoard('r4q2', 'chinees room', 0);
await expectBoard('r2q3', 'avicenas floating man', 5);

/* --- students' own words --- */
await expectBoard('r2q2', 'the interaction problem', 0);
await expectBoard('r2q2', 'how does the mind move the body', 0);
await expectBoard('r4q1', 'his personality changed', 0);
await expectBoard('r4q3', 'general anaesthetic', 2);
await expectBoard('r1q1', 'change blindness', 3);

/* --- word order and filler words --- */
await expectBoard('r3q1', 'is it primary or secondary', 3);
await expectBoard('r2q1', 'i think therefore i am', 3);
await expectBoard('r2q1', 'the evil demon', 2);

/* --- plurals and stems --- */
await expectBoard('r4q3', 'lobotomies', 4);
await expectBoard('r1q1', 'visual illusions', 0);

/* --- the near-miss trap: the 7th letter of PCASTLE --- */
await expectNearMiss('r3q1', 'evidence');
await expectNearMiss('r3q1', 'e for evidence');
await expectNearMiss('r1q1', 'synaesthesia');

/* --- a correct-sounding guess must NOT be swallowed by a looser slot --- */
await expectNearMiss('r1q1', 'the rubber hand illusion', 1);

/* --- genuinely wrong answers stay wrong --- */
await expectNone('r2q2', 'the turing test');
await expectNone('r1q2', 'bottom up processing');
await expectNone('r4q3', 'the soul is immortal');
await expectNone('r3q1', 'banana');

/* --- rapid fire --- */
const rf = (needle) => RAPID_FIRE.find((x) => x.prompt.includes(needle));
for (const [needle, guess] of [
  ['Two Latin words', 'cogito ergo sum'],
  ['rulebook thought experiment', 'the chinese room'],
  ['1848 railroad foreman', 'phineas gage'],
  ['original name for the Turing Test', 'the imitation game'],
  ['fewest assumptions', 'occams razor'],
]) {
  const question = rf(needle);
  const v = await judgeRapidGuess(guess, question);
  record(v.correct, `rapid "${guess}"`, `got ${JSON.stringify(v)}`);
}
const wrongRapid = await judgeRapidGuess('dualism', rf('everything mental is physical'));
record(!wrongRapid.correct, 'rapid rejects "dualism" for the materialism question', 'accepted it');

/* --- structural checks on the bank --- */
for (const round of ROUNDS) {
  for (const question of round.questions) {
    record(question.answers.length === 6, `${question.id} has 6 answers`, `${question.answers.length}`);
    const total = question.answers.reduce((a, b) => a + b.points, 0);
    record(total === 100, `${question.id} totals 100`, `${total}`);
    // Every answer must be reachable by its own aliases.
    for (let i = 0; i < question.answers.length; i++) {
      const alias = question.answers[i].accept[0];
      const v = await judgeBoardGuess(alias, question.answers, question.nearMiss || []);
      record(v.kind === 'board' && v.index === i,
        `${question.id} answer ${i + 1} reachable via "${alias}"`,
        `got ${v.kind}:${v.index}`);
    }
  }
}

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('All local matcher checks passed.\n');

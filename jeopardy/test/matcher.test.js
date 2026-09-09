/**
 * Offline checks on the clue bank and the local matcher.
 *
 * These run with no API key: they prove that what students actually type —
 * typos, surnames alone, their own words, Jeopardy phrasing — lands correctly
 * without the game ever needing the network.
 *
 * Run: node test/matcher.test.js
 */

import { CATEGORIES, FINAL } from '../src/questions.js';
import { judgeAnswer } from '../src/judge.js';

let pass = 0, fail = 0;
const failures = [];
function record(ok, label, detail = '') {
  if (ok) pass++; else { fail++; failures.push(`${label}${detail ? `  (${detail})` : ''}`); }
}

const clueIn = (categoryId, value) => {
  const c = CATEGORIES.find((x) => x.id === categoryId);
  if (!c) throw new Error(`no category ${categoryId}`);
  const cl = c.clues.find((x) => x.value === value);
  if (!cl) throw new Error(`no ${categoryId} ${value}`);
  return cl;
};

async function yes(categoryId, value, guess) {
  const v = await judgeAnswer(guess, clueIn(categoryId, value));
  record(v.correct, `${categoryId}/${value} accepts "${guess}"`, v.reason);
}
async function no(categoryId, value, guess) {
  const v = await judgeAnswer(guess, clueIn(categoryId, value));
  record(!v.correct, `${categoryId}/${value} rejects "${guess}"`, v.reason);
}

/* --- exact --- */
await yes('perception', 100, 'sensation');
await yes('descartes', 300, 'the pineal gland');
await yes('machines', 200, 'functionalism');

/* --- typos and phonetic spelling --- */
await yes('descartes', 500, 'occums razor');
await yes('descartes', 500, 'ockhams razer');
await yes('perception', 400, 'the mcgerk effect');
await yes('machines', 300, 'chinees room');
await yes('soul', 500, 'avicena');

/* --- surname alone, and the full name --- */
await yes('brain', 100, 'gage');
await yes('brain', 100, 'phineas gage');
await yes('descartes', 400, 'elisabeth of bohemia');
await yes('brain', 500, 'armstrong');

/* --- Jeopardy phrasing is accepted but never required --- */
await yes('machines', 100, 'what is the imitation game');
await yes('machines', 100, 'the imitation game');
await yes('descartes', 400, 'who is elisabeth of bohemia');
await yes('brain', 300, 'what is materialism');

/* --- students' own words --- */
await yes('brain', 200, 'his personality changed');
await yes('perception', 500, 'the rubber hand');
await yes('machines', 400, 'syntax isnt semantics');
await yes('source', 300, 'how long it lasted');

/* --- plurals, articles and word order --- */
await yes('perception', 300, 'gestalt principles');
await yes('descartes', 100, 'i think therefore i am');
await yes('soul', 100, 'the charioteer');

/* --- closely related but genuinely different answers must be rejected --- */
await no('brain', 300, 'dualism');
await no('perception', 100, 'perception');
await no('soul', 400, 'anatta');
await no('soul', 300, 'atman');
await no('machines', 300, 'the turing test');
await no('source', 500, 'durability');
await no('descartes', 300, 'the pituitary gland');
await no('perception', 200, 'the mcgurk effect');
await no('machines', 100, 'banana');

/* --- Final Jeopardy --- */
for (const guess of ['substance dualism', 'cartesian dualism', 'dualism', 'descartes dualism']) {
  const v = await judgeAnswer(guess, FINAL);
  record(v.correct, `final accepts "${guess}"`, v.reason);
}
for (const guess of ['materialism', 'functionalism', 'the chinese room']) {
  const v = await judgeAnswer(guess, FINAL);
  record(!v.correct, `final rejects "${guess}"`, v.reason);
}

/* --- structural checks on the bank --- */
record(CATEGORIES.length === 6, 'six categories', String(CATEGORIES.length));
for (const c of CATEGORIES) {
  record(c.clues.length === 5, `${c.id} has 5 clues`, String(c.clues.length));
  record(
    JSON.stringify(c.clues.map((x) => x.value)) === JSON.stringify([100, 200, 300, 400, 500]),
    `${c.id} runs 100-500 in order`,
  );
  for (const cl of c.clues) {
    record(Boolean(cl.text && cl.answer), `${c.id}/${cl.value} has text and an answer`);
    record(Array.isArray(cl.accept) && cl.accept.length > 0, `${c.id}/${cl.value} has aliases`);
    record(Boolean(cl.note), `${c.id}/${cl.value} has a teaching note`);
    // Every clue must be reachable by its own canonical answer and by each of
    // its own aliases — this is what catches a typo'd alias before a lesson.
    const byAnswer = await judgeAnswer(cl.answer, cl);
    record(byAnswer.correct, `${c.id}/${cl.value} reachable by its own answer "${cl.answer}"`);
    for (const alias of cl.accept) {
      const v = await judgeAnswer(alias, cl);
      record(v.correct, `${c.id}/${cl.value} reachable by alias "${alias}"`);
    }
  }
}

/* No clue's answer should be accepted by a different clue — that would mean two
 * cells on the board are effectively the same question. */
const all = CATEGORIES.flatMap((c) => c.clues.map((cl) => ({ id: `${c.id}/${cl.value}`, cl })));
for (const a of all) {
  for (const b of all) {
    if (a.id === b.id) continue;
    const v = await judgeAnswer(a.cl.answer, b.cl);
    record(!v.correct, `"${a.cl.answer}" is not also the answer to ${b.id}`);
  }
}

console.log(`\n${pass} passed, ${fail} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const f of failures) console.log('  ✗ ' + f);
  process.exit(1);
}
console.log('All clue bank and matcher checks passed.\n');

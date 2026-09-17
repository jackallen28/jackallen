/**
 * The teacher-loaded class: context upload, learned voice, save file.
 * Unit checks — no server, no model.
 */
import { parseClassContext, renderContextBlock } from '../server/context.js';
import { buildSharedPrompt, classContextTemplate } from '../server/classroom.js';
import { buildAllowlist, extractVoice, mergeVoice, rejectionReason } from '../server/learn.js';
import { buildSave, parseSave, SAVE_FORMAT } from '../server/save.js';

let failures = 0;
function check(label, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${extra ? '  ' + extra : ''}`);
  if (!cond) failures++;
}

const FILLED = `# Class Context — Year 8 Ecosystems

## About this class
- Subject: Science
- Year level: 8
- Unit or topic: Ecosystems and food webs
- Class size: 24

## What has been taught so far
Food chains and food webs. Producers, consumers, decomposers. The rock pool excursion
where the class found the sea star. Energy pyramids and the ten percent rule. Keystone
species, with the sea otter and kelp forest example everyone remembers.

## Shared reference points
- the sea otter thing
- "ten percent" said in a spooky voice
- the rock pool excursion, and who fell in

## What the bot must not know
Biomagnification. The nitrogen cycle. Anything about climate modelling.

## What to talk about
Ecosystems, food webs, energy flow, keystone species and the examples this class has covered.

## How students in this class write
- idk the otter one makes sense
- yeah nah thats not how food chains work
- wait so decomposers eat everything??
- 

## Names never to use
Jayden, Mia, Liam, Chloe
`;

console.log('--- the template itself ---');
check('the template ships with the pack', classContextTemplate.length > 1000);
const blank = parseClassContext(classContextTemplate);
check('an unfilled template is rejected, not silently loaded', blank.ok === false, blank.error);
check('the rejection names the missing section', /taught/i.test(blank.error || ''));

console.log('\n--- a filled-in context ---');
const parsed = parseClassContext(FILLED);
check('parses', parsed.ok === true, parsed.error);
const ctx = parsed.context;
check('title comes from the H1', ctx.title === 'Year 8 Ecosystems', ctx.title);
check('taught section captured', /keystone/i.test(ctx.taught));
check('samples parsed, empty bullet dropped', ctx.samples.length === 3, JSON.stringify(ctx.samples));
check('blocklist parsed', ctx.blocklist.join(',') === 'Jayden,Mia,Liam,Chloe', ctx.blocklist.join(','));
check('subject captured', /food webs/i.test(ctx.subject), ctx.subject);
check('forbidden captured', /nitrogen/i.test(ctx.forbidden));

console.log('\n--- headings matched loosely ---');
const reworded = FILLED
  .replace('## What has been taught so far', '## Content covered to date')
  .replace('## How students in this class write', '## Writing samples')
  .replace('## Names never to use', '## Blocklist');
const loose = parseClassContext(reworded);
check('reworded headings still land', loose.ok && loose.context.samples.length === 3 && loose.context.blocklist.length === 4,
  loose.ok ? '' : loose.error);
check('an unrecognised heading is reported, not lost silently',
  parseClassContext(FILLED + '\n## Homework\nstuff\n').context.unknownHeadings.includes('Homework'));
check('empty file rejected', parseClassContext('').ok === false);
check('a file with no headings is rejected with advice',
  /template/i.test(parseClassContext('just some text').error));

console.log('\n--- the prompt is rebuilt around it ---');
const prompt = buildSharedPrompt({ context: ctx });
check('class context replaces the built-in one', prompt.includes('sea otter') && !prompt.includes('Phineas'));
check('the subject boundary is the uploaded one', prompt.includes('keystone species and the examples'));
check('uploaded samples replace the pack corpus', prompt.includes('idk the otter one') && !prompt.includes('anaesthetic question'));
check('the blocklist reaches the scope', prompt.includes('Jayden, Mia, Liam, Chloe'));
check('forbidden content is framed as unknown, not as a list to use', /never heard of it/i.test(prompt) && prompt.includes('nitrogen'));
check('safeguards still last', prompt.lastIndexOf('OVERRIDING RULES') > prompt.lastIndexOf('CLASS CONTEXT'));
const withoutSamples = parseClassContext(FILLED.replace(/## How students[\s\S]*?## Names/, '## Names')).context;
check('a context without samples keeps the pack corpus',
  buildSharedPrompt({ context: withoutSamples }).includes('anaesthetic question'));
check('rendered block carries the title', renderContextBlock(ctx).startsWith('# Class context — Year 8 Ecosystems'));

console.log('\n--- learned voice: deidentification ---');
const guard = { allow: buildAllowlist(FILLED), names: ['Jayden', 'Student 03', 'ABCD1234', 'Mia'] };
const reason = (t) => rejectionReason(t, guard);
check('a plain chat line passes', reason('idk the otter one is kinda dumb') === null);
check('a class-vocabulary capital passes', reason('the Keystone species thing') === null, reason('the Keystone species thing'));
check('a roster name is caught', reason('mia thinks its the sun') === 'names someone in the class');
check('a login code is caught', reason('im ABCD1234 lol') === 'login code');
check('an email is caught', /email/.test(reason('msg me at kid@example.com')));
check('a web address is caught', /web/.test(reason('look at www.example.com')));
check('a phone number is caught', /phone/.test(reason('call 0412 345 678')));
check('an unfamiliar mid-line capital is treated as a name', /name-like/.test(reason('ask Priya she knows')), reason('ask Priya she knows'));
check('a sentence-initial capital in lower-case chat is allowed', reason('Nah thats wrong') === null, reason('Nah thats wrong'));
check('a long paragraph is not a chat line', /too long/.test(reason('x'.repeat(200))));

const transcripts = [{
  messages: [
    { isBot: false, text: 'idk the otter one is kinda dumb' },
    { isBot: true, text: 'lol why' },
    { isBot: false, text: 'ask Priya she knows' },
    { isBot: false, text: 'IDK THE OTTER ONE IS KINDA DUMB' },
    { isBot: false, text: 'yeah nah' },
  ],
}];
const out = extractVoice(transcripts, guard, ['yeah nah']);
check('bot lines are never learned', !out.kept.some((l) => l === 'lol why'));
check('duplicates collapse case-insensitively', out.kept.filter((l) => /otter/i.test(l)).length === 1);
check('already-learned lines are not offered again', !out.kept.includes('yeah nah'));
check('dropped lines are counted with reasons', out.dropped.length === 1 && /name-like/.test(out.dropped[0].reason));
const merged = mergeVoice(['yeah nah'], ['idk the otter one is kinda dumb', 'ask Priya she knows', 'yeah nah'], guard);
check('merge re-checks and dedupes', merged.length === 2 && !merged.some((l) => /Priya/.test(l)), JSON.stringify(merged));

console.log('\n--- the save file round-trips ---');
const save = buildSave({
  context: ctx, learnedVoice: merged,
  settings: { durationSec: 180, aiRatio: 0.7, modelMix: { 'claude-haiku-4-5': 1 }, personaMix: { A: 1 } },
  roster: [{ login: 'ABCD1234', student: 'Student 01' }, { login: 'WXYZ0002', student: 'Student 02' }],
  rounds: [{ round: 1, accuracy: 60 }],
});
check('format and version stamped', save.format === SAVE_FORMAT && save.version === 1);
check('title falls back to the context title', save.title === 'Year 8 Ecosystems');
const back = parseSave(JSON.stringify(save));
check('loads back', back.ok === true, back.error);
check('context survives the trip', back.parts.context?.title === 'Year 8 Ecosystems');
check('voice survives the trip', back.parts.learnedVoice.length === 2);
check('settings survive the trip', back.parts.settings.durationSec === 180 && back.parts.settings.aiRatio === 0.7);
check('roster survives the trip', back.parts.roster.length === 2);
check('rounds survive the trip', back.parts.rounds.length === 1);
check('garbage is refused', parseSave('not json').ok === false);
check('the wrong format is refused', /not a Human or Not/.test(parseSave('{"format":"other"}').error));
check('a bad login in the file is skipped and noted',
  parseSave(JSON.stringify({ ...save, roster: [...save.roster, { login: 'bad', student: 'x' }] })).notes.length === 1);

console.log(`\n${failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED'}`);
process.exit(failures === 0 ? 0 : 1);

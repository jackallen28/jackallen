/**
 * Answer judging, in two layers.
 *
 * Layer 1 (local, instant, always runs): normalise the typed answer and test it
 * against the alias list the clue carries, tolerating typos, plurals, word
 * order and filler words. In a live classroom this settles the overwhelming
 * majority of answers in well under a millisecond, which is what keeps a
 * buzzer game feeling like a buzzer game.
 *
 * Layer 2 (Claude, only when layer 1 says no): the phrasings nobody wrote an
 * alias for — "the lady who asked him how the mind pushes stuff", "the fake
 * hand one". Claude sees the clue and the official answer and rules on it.
 *
 * With no API key, or if the call fails or times out, the local verdict stands
 * and the host overrules it with one click. The game never blocks on the
 * network, because a lesson cannot wait for a retry.
 */

import Anthropic from '@anthropic-ai/sdk';

const MODEL = process.env.ANTHROPIC_MODEL || 'claude-opus-5';
const API_TIMEOUT_MS = Number(process.env.JUDGE_TIMEOUT_MS || 6000);

let client = null;
let betaSupported = true;

function getClient() {
  if (client) return client;
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) return null;
  client = new Anthropic({ timeout: API_TIMEOUT_MS, maxRetries: 1 });
  return client;
}

export function aiAvailable() {
  return Boolean(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN);
}

/* ------------------------------------------------------------------ */
/* Layer 1: local matching                                             */
/* ------------------------------------------------------------------ */

const FILLER = new Set([
  'the', 'a', 'an', 'of', 'is', 'it', 'its', 'that', 'this', 'and', 'or', 'to',
  'in', 'for', 'his', 'her', 'their', 'they', 'was', 'were', 'be', 'been',
  'about', 'with', 'on', 'at', 'as', 'by', 'from', 'you', 'your', 'im', 'i',
  'we', 'thing', 'stuff', 'like', 'um', 'uh', 'said', 'says', 'say', 'called',
  'he', 'she', 'him', 'do', 'does', 'did', 'doe', 'have', 'has', 'had',
  'can', 'could', 'will', 'would', 'just', 'really', 'also', 'very', 'so',
  'but', 'if', 'which', 'who', 'than', 'thi', 'wa', 'hi', 'ha',
  // Jeopardy phrasing is accepted but never required, so it is simply ignored.
  'what', 'whats', 'whos', 'where', 'when', 'why',
]);

function normalise(text) {
  return String(text || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip accents: Muller -> Muller
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')    // punctuation and hyphens become spaces
    .replace(/\s+/g, ' ')
    .trim();
}

function tokenise(text) {
  return normalise(text)
    .split(' ')
    .filter((w) => w.length > 0 && !FILLER.has(w))
    .map(stem)
    .filter((w) => w.length > 0 && !FILLER.has(w));
}

// Deliberately crude — enough to join "illusions"/"illusion",
// "principles"/"principle", "processing"/"process".
function stem(word) {
  if (word.length > 5 && word.endsWith('ing')) return word.slice(0, -3);
  if (word.length > 4 && word.endsWith('es')) return word.slice(0, -2);
  if (word.length > 3 && word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
  return word;
}

function levenshtein(a, b) {
  if (a === b) return 0;
  const m = a.length;
  const n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  let prev = Array.from({ length: n + 1 }, (_, i) => i);
  const curr = new Array(n + 1);
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    prev = curr.slice();
  }
  return prev[n];
}

/**
 * How far off a typo may be before we stop calling it the same word.
 *
 * Short words get no allowance at all: at two edits "gage" matches "game" and
 * "pineal" matches "phineas", which would credit a team for naming a different
 * clue's answer. Longer words can afford the latitude because there is more
 * signal left over to be wrong about.
 */
function typoBudget(word) {
  if (word.length <= 4) return 0;
  if (word.length <= 6) return 1;
  if (word.length <= 9) return 2;
  return 3;
}

function tokenPresent(needle, haystackTokens) {
  const budget = typoBudget(needle);
  for (const token of haystackTokens) {
    if (token === needle) return true;
    if (budget === 0) continue;
    if (Math.abs(token.length - needle.length) > budget) continue; // cheap gate
    if (levenshtein(needle, token) <= budget) return true;
  }
  return false;
}

/** An alias matches when every significant word of it appears in the guess. */
function aliasMatches(alias, guessTokens) {
  const needles = tokenise(alias);
  if (needles.length === 0) return false;
  return needles.every((n) => tokenPresent(n, guessTokens));
}

function localScan(guess, clue) {
  const guessTokens = tokenise(guess);
  if (guessTokens.length === 0) return null;
  for (const alias of [...(clue.accept || []), clue.answer]) {
    if (aliasMatches(alias, guessTokens)) return alias;
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Layer 2: Claude                                                     */
/* ------------------------------------------------------------------ */

const JUDGE_SYSTEM = `You are the judge for a fast-paced Jeopardy-style quiz in a Year 9/10 Humanities classroom. The unit is "Where is My Mind?" — perception, consciousness, dualism, materialism and artificial intelligence.

A student has buzzed in and typed an answer. You rule on whether it is the answer to the clue.

Judge generously on FORM and strictly on SUBSTANCE:
- Accept misspellings, phonetic spellings, missing accents, plurals and text-speak. "decarts", "occums razor", "mcgerk" are all fine.
- Accept the student's own words for the right idea. "the lady who asked how the mind pushes the body" is Elisabeth of Bohemia. "the fake hand one" is the rubber hand illusion.
- Accept an answer with or without Jeopardy phrasing. "What is materialism" and "materialism" are equally correct.
- Accept a surname alone when the answer is a person, and a first name alone only when it is unambiguous in this unit.
- REJECT an answer naming a genuinely different concept, however close. Materialism is not dualism. Sensation is not perception. The Turing Test is not the Chinese Room. Ātman is not anattā.
- REJECT vague gestures that could fit several clues, such as "something about the brain".

Return correct: true only if the student has clearly given the official answer.`;

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    correct: { type: 'boolean', description: 'Whether the student gave the official answer.' },
    reason: { type: 'string', description: 'At most 12 words, for the host screen.' },
  },
  required: ['correct', 'reason'],
  additionalProperties: false,
};

async function askClaude(guess, clue) {
  const anthropic = getClient();
  if (!anthropic) return null;

  const request = {
    model: MODEL,
    max_tokens: 1000,
    system: JUDGE_SYSTEM,
    messages: [{
      role: 'user',
      content: `CLUE: ${clue.text}\n\nOFFICIAL ANSWER: ${clue.answer}\n\nALSO ACCEPTABLE: ${(clue.accept || []).join('; ') || '(none listed)'}\n\nSTUDENT'S TYPED ANSWER: "${guess}"`,
    }],
    output_config: {
      effort: 'low', // a one-line ruling; low effort keeps the buzzer snappy
      format: { type: 'json_schema', schema: JUDGE_SCHEMA },
    },
  };

  let response;
  if (betaSupported) {
    try {
      response = await anthropic.beta.messages.create({
        ...request,
        betas: ['server-side-fallback-2026-07-01'],
        fallbacks: 'default',
      });
    } catch {
      // Older API surface, or the beta is unavailable here — drop it for the
      // rest of the lesson rather than paying a failed call on every answer.
      betaSupported = false;
      response = await anthropic.messages.create(request);
    }
  } else {
    response = await anthropic.messages.create(request);
  }

  if (response.stop_reason === 'refusal') return null;

  const text = (response.content || [])
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('');
  if (!text.trim()) return null;

  try {
    const parsed = JSON.parse(text);
    return { correct: Boolean(parsed.correct), reason: parsed.reason || '' };
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ */

/**
 * @returns {Promise<{correct:boolean, source:'local'|'ai'|'offline', reason:string}>}
 */
export async function judgeAnswer(guess, clue) {
  const alias = localScan(guess, clue);
  if (alias) return { correct: true, source: 'local', reason: `matched "${alias}"` };

  if (!aiAvailable()) return { correct: false, source: 'offline', reason: 'no match found' };

  try {
    const verdict = await askClaude(guess, clue);
    if (verdict) return { ...verdict, source: 'ai' };
  } catch (err) {
    console.warn('[judge] Claude call failed, using local verdict:', err.message);
  }
  return { correct: false, source: 'offline', reason: 'no match found' };
}

// Exported for the test script.
export const _internals = { normalise, tokenise, localScan, aliasMatches };

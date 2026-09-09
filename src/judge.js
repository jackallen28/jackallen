/**
 * Answer judging, in two layers.
 *
 * Layer 1 (local, instant, always runs): normalise the guess and test it
 * against every alias in the question bank, tolerating typos, plurals, word
 * order and filler words. In a live classroom this catches the overwhelming
 * majority of guesses in under a millisecond, which is what keeps the game
 * feeling like a buzzer game rather than a web form.
 *
 * Layer 2 (Claude, only when layer 1 says no): the phrasings nobody wrote an
 * alias for — "the thing where the hand isn't yours", "that lady who wrote to
 * him about how the mind pushes stuff". Claude sees the whole board and returns
 * which slot the guess belongs in, or none.
 *
 * If there is no API key, or the API call fails or times out, the local verdict
 * stands and the host can override with one click. The game never blocks on the
 * network.
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
]);

function normalise(text) {
  return String(text || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip accents: Muller -> Muller
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')      // punctuation and hyphens become spaces
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
// "aggregates"/"aggregate", "processing"/"process".
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

// How far off a typo may be before we stop calling it the same word.
function typoBudget(word) {
  if (word.length <= 3) return 0;
  if (word.length <= 5) return 1;
  if (word.length <= 9) return 2;
  return 3;
}

function tokenPresent(needle, haystackTokens) {
  const budget = typoBudget(needle);
  for (const token of haystackTokens) {
    if (token === needle) return true;
    if (budget === 0) continue;
    // A cheap length gate before paying for the edit distance.
    if (Math.abs(token.length - needle.length) > budget) continue;
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

/**
 * @returns {{index:number, alias:string}|null} index into `entries`
 */
function localScan(guess, entries) {
  const guessTokens = tokenise(guess);
  if (guessTokens.length === 0) return null;

  let best = null;
  entries.forEach((entry, index) => {
    const aliases = [entry.text, ...(entry.accept || [])];
    for (const alias of aliases) {
      if (!aliasMatches(alias, guessTokens)) continue;
      const specificity = tokenise(alias).length;
      // Prefer the most specific alias that matched, so "rubber hand illusion"
      // beats a looser "illusion" on a board that contains both.
      if (!best || specificity > best.specificity) {
        best = { index, alias, specificity };
      }
    }
  });
  return best ? { index: best.index, alias: best.alias } : null;
}

/* ------------------------------------------------------------------ */
/* Layer 2: Claude                                                     */
/* ------------------------------------------------------------------ */

const JUDGE_SYSTEM = `You are the adjudicator for a fast-paced Family Feud style quiz in a Year 9/10 Humanities classroom. The unit is "Where is My Mind?" — perception, consciousness, dualism, materialism and artificial intelligence.

A student has shouted an answer and typed it in. You decide which board answer they meant, if any.

Judge generously on FORM and strictly on SUBSTANCE:
- Accept misspellings, phonetic spellings, missing accents, plurals, abbreviations and text-speak. "decarts", "muller lyre", "occums razor", "the chinese room thingy" are all fine.
- Accept a student's own words for the right idea. "you cant touch something that isnt physical" is Elisabeth of Bohemia's interaction problem. "the fake hand one" is the rubber hand illusion.
- Accept a correct part standing for the whole, e.g. naming one Gestalt principle when the board answer names that principle.
- REJECT a guess that names a genuinely different concept, even a closely related one. Materialism is not dualism. Sensation is not perception. Top-down is not bottom-up. The Turing Test is not the Chinese Room.
- REJECT vague gestures that could point at three answers at once, e.g. "something about the brain".

If the guess clearly names a board answer, return that answer's number.
If it clearly names one of the near-miss answers instead, return that near-miss number.
Otherwise return matched: "none".`;

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    matched: {
      type: 'string',
      description: 'Either "board", "nearmiss", or "none".',
      enum: ['board', 'nearmiss', 'none'],
    },
    number: {
      type: 'integer',
      description: 'The 1-based number of the matched answer, or 0 when matched is "none".',
    },
    reason: {
      type: 'string',
      description: 'At most 12 words, for the teacher screen.',
    },
  },
  required: ['matched', 'number', 'reason'],
  additionalProperties: false,
};

function buildJudgePrompt(guess, answers, nearMiss) {
  const board = answers
    .map((a, i) => `${i + 1}. ${a.text}`)
    .join('\n');
  const near = (nearMiss || []).length
    ? (nearMiss || []).map((a, i) => `${i + 1}. ${a.text}`).join('\n')
    : '(none)';
  return `BOARD ANSWERS:\n${board}\n\nNEAR-MISS ANSWERS (correct, but not on the board):\n${near}\n\nSTUDENT'S TYPED GUESS: "${guess}"`;
}

async function askClaude(guess, answers, nearMiss) {
  const anthropic = getClient();
  if (!anthropic) return null;

  const request = {
    model: MODEL,
    max_tokens: 1000,
    system: JUDGE_SYSTEM,
    messages: [{ role: 'user', content: buildJudgePrompt(guess, answers, nearMiss) }],
    output_config: {
      effort: 'low', // a one-line classification; low effort keeps the buzzer snappy
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
    } catch (err) {
      // Older API surface, or the beta is unavailable here — drop it for the
      // rest of the lesson rather than paying the failed call every guess.
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

  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    return null;
  }

  const n = Number(parsed.number);
  if (parsed.matched === 'board' && n >= 1 && n <= answers.length) {
    return { kind: 'board', index: n - 1, reason: parsed.reason || '' };
  }
  if (parsed.matched === 'nearmiss' && nearMiss && n >= 1 && n <= nearMiss.length) {
    return { kind: 'nearmiss', index: n - 1, reason: parsed.reason || '' };
  }
  return { kind: 'none', index: -1, reason: parsed.reason || '' };
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

/**
 * Judge a board-round guess.
 *
 * @returns {Promise<{kind:'board'|'nearmiss'|'none', index:number,
 *                    source:'local'|'ai'|'offline', reason:string}>}
 */
export async function judgeBoardGuess(guess, answers, nearMiss = []) {
  // Scanned as one pool so the most specific alias wins across both lists.
  const pool = [
    ...answers.map((a) => ({ ...a, _kind: 'board' })),
    ...nearMiss.map((a) => ({ ...a, _kind: 'nearmiss' })),
  ];
  const hit = localScan(guess, pool);
  if (hit) {
    const kind = pool[hit.index]._kind;
    const index = kind === 'board' ? hit.index : hit.index - answers.length;
    return { kind, index, source: 'local', reason: `matched "${hit.alias}"` };
  }

  if (!aiAvailable()) {
    return { kind: 'none', index: -1, source: 'offline', reason: 'no match found' };
  }

  try {
    const verdict = await askClaude(guess, answers, nearMiss);
    if (verdict) return { ...verdict, source: 'ai' };
  } catch (err) {
    console.warn('[judge] Claude call failed, using local verdict:', err.message);
  }
  return { kind: 'none', index: -1, source: 'offline', reason: 'no match found' };
}

/**
 * Judge a rapid-fire guess against a single question's accepted answers.
 * @returns {Promise<{correct:boolean, source:string, reason:string}>}
 */
export async function judgeRapidGuess(guess, question) {
  const entries = [{ text: question.accept[0], accept: question.accept }];
  const hit = localScan(guess, entries);
  if (hit) return { correct: true, source: 'local', reason: `matched "${hit.alias}"` };

  if (!aiAvailable()) return { correct: false, source: 'offline', reason: 'no match found' };

  try {
    const verdict = await askClaude(guess, entries, []);
    if (verdict && verdict.kind === 'board') {
      return { correct: true, source: 'ai', reason: verdict.reason };
    }
  } catch (err) {
    console.warn('[judge] Claude call failed, using local verdict:', err.message);
  }
  return { correct: false, source: 'offline', reason: 'no match found' };
}

// Exported for the test script.
export const _internals = { normalise, tokenise, localScan, aliasMatches };

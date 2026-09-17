/**
 * Turn a round's transcripts into writing samples the bot can learn from.
 *
 * The bot's hardest job is sounding like *this* room, and nothing describes
 * that as well as what the room actually typed. After a round, the teacher can
 * take the human-written messages, have anything identifying stripped, review
 * every surviving line, and add them to the bot's briefing as examples of how
 * this class writes.
 *
 * This is examples in a prompt, not model training. Nothing here changes the
 * model; it changes what the model is shown before it writes.
 *
 * Deidentification is conservative and mechanical. A line is dropped, not
 * masked, when it carries anything that looks like it could name or locate a
 * person — a dropped line costs nothing, a leaked one costs a lot. The teacher's
 * review is the last line of defence and the console never commits a line the
 * teacher has not seen.
 */

const MAX_LINE = 160;
const MAX_VOICE = 120;

const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]+/;
const URL = /https?:\/\/|www\.|\.(?:com|net|org|edu|au|io)\b/i;
const HANDLE = /(?:^|\s)@\w+/;
const LONG_NUMBER = /\d{6,}/;
const PHONE = /\b0\d[\d\s-]{7,}\b/;
const LOGIN = /\b[A-Z]{4}\d{4}\b/;

// Capitalised words a chat line can carry without naming anyone. Everything
// else that is capitalised and not in the class context is treated as a name.
const SAFE_CAPS = new Set([
  'I', 'AI', 'OK', 'LOL', 'IDK', 'TBH', 'OMG', 'WTF', 'BTW', 'NGL', 'IMO', 'FR',
  'AI\'S', 'AIS', 'A', 'YES', 'NO', 'NAH', 'YEAH', 'THE', 'IT', 'ITS', 'IM', 'IF', 'SO',
  'BUT', 'AND', 'OR', 'NOT', 'WHY', 'WHAT', 'HOW', 'WHO', 'WHEN', 'WHERE',
]);

const wordsOf = (text) => String(text || '').match(/[A-Za-z][A-Za-z'’-]*/g) || [];

/**
 * Every capitalised word that appears in trusted text — the class context, the
 * pack — is vocabulary the class shares (Descartes, Gage, the Floating Man) and
 * safe to keep. A capitalised word that appears nowhere in it is probably a name.
 */
export function buildAllowlist(...texts) {
  const allow = new Set(SAFE_CAPS);
  for (const text of texts) {
    for (const word of wordsOf(text)) {
      if (/^[A-Z]/.test(word)) allow.add(word.toUpperCase().replace(/[’']/g, '\''));
    }
  }
  return allow;
}

/**
 * Why a line cannot be used, or null if it can.
 *
 * @param {string} text
 * @param {object} guard
 * @param {Set<string>} guard.allow   capitalised words that are not names
 * @param {string[]} guard.names      roster labels, logins and the blocklist
 */
export function rejectionReason(text, { allow, names }) {
  const line = String(text || '').trim();
  if (!line) return 'empty';
  if (line.length > MAX_LINE) return 'too long to be a chat line';
  if (EMAIL.test(line)) return 'email address';
  if (URL.test(line)) return 'web address';
  if (HANDLE.test(line)) return 'username';
  if (LONG_NUMBER.test(line) || PHONE.test(line)) return 'phone number or id';
  if (LOGIN.test(line)) return 'login code';

  const lower = line.toLowerCase();
  for (const name of names) {
    const needle = String(name || '').trim().toLowerCase();
    if (!needle) continue;
    const pattern = new RegExp(`(^|[^a-z0-9])${needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9]|$)`);
    if (pattern.test(lower)) return 'names someone in the class';
  }

  const words = wordsOf(line);
  // A line with no lower-case letters at all is shouting, not a list of names.
  // Known names were already caught above; the capital-word heuristic below
  // would reject every word of it.
  if (!/[a-z]/.test(line)) return null;
  for (const [index, word] of words.entries()) {
    if (!/^[A-Z]/.test(word)) continue;
    const key = word.toUpperCase().replace(/[’']/g, '\'');
    if (allow.has(key)) continue;
    // A sentence-initial capital is ordinary; a capitalised word mid-line that
    // the class has never been taught is somebody's name until proven otherwise.
    if (index === 0 && word.length > 1 && /^[A-Z][a-z]+$/.test(word) && words.length > 1) {
      // Allow it only when the rest of the line is plainly lower-case chat.
      continue;
    }
    return `unfamiliar name-like word "${word}"`;
  }
  return null;
}

/**
 * Candidate samples from a set of transcripts.
 *
 * @param {Array<{messages: Array<{isBot: boolean, text: string}>}>} transcripts
 * @param {object} guard  see rejectionReason
 * @param {string[]} [existing]  lines already learned, so nothing is offered twice
 * @returns {{kept: string[], dropped: Array<{text: string, reason: string}>}}
 */
export function extractVoice(transcripts, guard, existing = []) {
  const seen = new Set(existing.map((line) => line.toLowerCase()));
  const kept = [];
  const dropped = [];

  for (const conv of transcripts) {
    for (const message of conv.messages || []) {
      if (message.isBot) continue;
      const text = String(message.text || '').replace(/\s+/g, ' ').trim();
      const reason = rejectionReason(text, guard);
      if (reason) { dropped.push({ text, reason }); continue; }
      const key = text.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      kept.push(text);
    }
  }
  return { kept, dropped };
}

/**
 * Merge newly approved lines into the learned voice, newest last, capped.
 * Lines are re-checked here: the console is trusted to show what it was given,
 * not to invent lines, so anything that fails the guard is dropped again.
 */
export function mergeVoice(existing, approved, guard) {
  const seen = new Set(existing.map((line) => line.toLowerCase()));
  const merged = [...existing];
  for (const raw of approved) {
    const text = String(raw || '').replace(/\s+/g, ' ').trim();
    if (!text || seen.has(text.toLowerCase())) continue;
    if (rejectionReason(text, guard)) continue;
    seen.add(text.toLowerCase());
    merged.push(text);
  }
  return merged.slice(-MAX_VOICE);
}

export const VOICE_LIMIT = MAX_VOICE;

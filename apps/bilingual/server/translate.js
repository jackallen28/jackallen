import Anthropic from '@anthropic-ai/sdk';
import { modelCapabilities } from './models.js';

/**
 * Message translation between the two activity languages.
 *
 * Used only when two participants have chosen different languages. The AI partner
 * writes directly in its partner's language instead of being translated, because
 * generating in the target language reads better than translating into it.
 *
 * If translation fails for any reason the original text is delivered unchanged —
 * a message getting through in the wrong language beats a message vanishing.
 */

export const LANGUAGES = {
  en: { code: 'en', label: 'English', native: 'English', name: 'English' },
  zh: { code: 'zh', label: 'Chinese', native: '中文', name: 'Simplified Chinese' },
};

export const DEFAULT_LANGUAGE = 'en';

export function isLanguage(code) {
  return Object.prototype.hasOwnProperty.call(LANGUAGES, code);
}

export function languageName(code) {
  return LANGUAGES[code]?.name || LANGUAGES[DEFAULT_LANGUAGE].name;
}

// Translation is on the critical path of a live chat, so speed matters more than
// depth here. Override with TRANSLATE_MODEL if the output is not good enough.
const MODEL = process.env.TRANSLATE_MODEL || 'claude-haiku-4-5';

const SYSTEM = [
  'You translate short instant-messenger messages between English and Simplified Chinese',
  'for a live chat activity. Output only the translation. Never explain, never comment,',
  'never add quotation marks that were not there, never answer the message.',
  '',
  'Translate faithfully in register, not just in meaning. These are casual messages typed',
  'quickly by adults:',
  '- Keep it as short as the original. A three word message stays about three words.',
  '- Keep the tone: blunt stays blunt, friendly stays friendly, uncertain stays uncertain.',
  '- Keep informality. Do not raise the register, do not make it polite or literary, and',
  '  do not turn fragments into full sentences.',
  '- If the original has a typo, missing punctuation or no capital letter, produce',
  '  something equally casual rather than correcting it.',
  '- Keep any question a question.',
  '',
  'If the text is already in the target language, return it unchanged.',
  'If it cannot be translated at all, return it unchanged.',
].join('\n');

let client = null;
let clientFailed = false;

function getClient() {
  if (clientFailed) return null;
  if (client) return client;
  try {
    client = new Anthropic();
    return client;
  } catch (err) {
    console.warn('[translate] client unavailable, messages will pass through untranslated:', err.message);
    clientFailed = true;
    return null;
  }
}

export function isTranslationConfigured() {
  return Boolean(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN);
}

/** Strip anything the model wrapped around the translation. */
function clean(text, original) {
  const out = String(text || '')
    .replace(/^["'“”「」]+|["'“”「」]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return out || original;
}

/**
 * @param {string} text        the message as typed
 * @param {string} fromLang    sender's language code
 * @param {string} toLang      recipient's language code
 * @returns {Promise<{text: string, translated: boolean}>}
 */
export async function translate(text, fromLang, toLang) {
  const original = String(text || '');
  if (!original.trim() || fromLang === toLang) return { text: original, translated: false };

  const api = getClient();
  if (!api) return { text: original, translated: false };

  try {
    const request = {
      model: MODEL,
      max_tokens: 400,
      system: [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }],
      messages: [{
        role: 'user',
        content: `Translate from ${languageName(fromLang)} to ${languageName(toLang)}:\n\n${original}`,
      }],
    };
    // Same per-model gating as the chat bot: Haiku rejects an effort setting.
    if (modelCapabilities(MODEL).effort) request.output_config = { effort: 'low' };

    const response = await api.messages.create(request);
    if (response.stop_reason === 'refusal') {
      console.warn('[translate] refusal:', response.stop_details?.category);
      return { text: original, translated: false };
    }

    const text = clean(
      response.content.filter((b) => b.type === 'text').map((b) => b.text).join(' '),
      original
    );
    return { text, translated: text !== original };
  } catch (err) {
    console.warn('[translate] failed, delivering the original:', err.message);
    return { text: original, translated: false };
  }
}

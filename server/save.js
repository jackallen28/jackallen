/**
 * The save file: everything a teacher needs to pick a class up where they left
 * it, in one JSON file they keep themselves.
 *
 * Nothing is stored on the server, by design. The save file is the teacher's
 * copy of the parts that are expensive to recreate — the class context they
 * wrote, the voice the bot learned from their students, the settings they
 * settled on, the login list they printed — plus a log of the rounds run so
 * far. Transcripts and results live in the report, not here: the save file is
 * for carrying a class forward, not for keeping what was said.
 */
import { parseClassContext } from './context.js';
import { isValidLogin, normaliseLogin } from './roster.js';

export const SAVE_FORMAT = 'human-or-not-save';
export const SAVE_VERSION = 1;
export const SAVE_FILENAME = 'human-or-not-save.json';

const MAX_SAVE_CHARS = 400000;

/**
 * @param {object} parts
 * @param {import('./context.js').ParsedContext|null} parts.context
 * @param {string[]} parts.learnedVoice
 * @param {object} parts.settings
 * @param {Array<{login: string, student: string}>} parts.roster
 * @param {object[]} parts.rounds
 */
export function buildSave({ context, learnedVoice, settings, roster, rounds, title }) {
  return {
    format: SAVE_FORMAT,
    version: SAVE_VERSION,
    savedAt: new Date().toISOString(),
    title: title || context?.title || 'Human or Not? class',
    classContext: context ? context.raw : null,
    learnedVoice: [...learnedVoice],
    settings: {
      durationSec: settings.durationSec,
      aiRatio: settings.aiRatio,
      modelMix: settings.modelMix,
      personaMix: settings.personaMix,
    },
    roster: roster.map(({ login, student }) => ({ login, student })),
    rounds: [...rounds],
  };
}

/**
 * Validate an uploaded save and turn it back into session parts.
 *
 * Lenient about what it accepts — an older or hand-edited file with some parts
 * missing still loads what it can — and strict about what it lets through: the
 * context is re-parsed, logins are re-validated, and anything else is dropped.
 *
 * @returns {{ok: true, parts: object, notes: string[]} | {ok: false, error: string}}
 */
export function parseSave(rawText) {
  const text = String(rawText || '');
  if (text.length > MAX_SAVE_CHARS) return { ok: false, error: 'That file is too large to be a save file.' };

  let data;
  try {
    data = JSON.parse(text.replace(/^﻿/, ''));
  } catch {
    return { ok: false, error: 'That is not a save file — it is not valid JSON.' };
  }
  if (!data || typeof data !== 'object' || data.format !== SAVE_FORMAT) {
    return { ok: false, error: `That is not a Human or Not? save file (expected format "${SAVE_FORMAT}").` };
  }
  if (Number(data.version) > SAVE_VERSION) {
    return { ok: false, error: `That save file is from a newer version of the app (v${data.version}); this one reads v${SAVE_VERSION}.` };
  }

  const notes = [];
  const parts = { context: null, learnedVoice: [], settings: null, roster: [], rounds: [] };

  if (typeof data.classContext === 'string' && data.classContext.trim()) {
    const parsed = parseClassContext(data.classContext);
    if (parsed.ok) parts.context = parsed.context;
    else notes.push(`The class context in the file could not be read: ${parsed.error}`);
  }

  if (Array.isArray(data.learnedVoice)) {
    parts.learnedVoice = data.learnedVoice
      .filter((line) => typeof line === 'string')
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter((line) => line && line.length <= 160)
      .slice(-120);
  }

  if (data.settings && typeof data.settings === 'object') {
    const s = data.settings;
    parts.settings = {
      durationSec: Number.isFinite(Number(s.durationSec)) ? Number(s.durationSec) : undefined,
      aiRatio: Number.isFinite(Number(s.aiRatio)) ? Number(s.aiRatio) : undefined,
      modelMix: s.modelMix && typeof s.modelMix === 'object' ? s.modelMix : undefined,
      personaMix: s.personaMix && typeof s.personaMix === 'object' ? s.personaMix : undefined,
    };
  }

  if (Array.isArray(data.roster)) {
    const seen = new Set();
    for (const entry of data.roster) {
      const login = normaliseLogin(entry?.login);
      if (!isValidLogin(login) || seen.has(login)) continue;
      seen.add(login);
      parts.roster.push({ login, student: String(entry?.student || login).slice(0, 40) });
    }
    if (parts.roster.length < data.roster.length) {
      notes.push(`${data.roster.length - parts.roster.length} login(s) in the file were not valid and were skipped.`);
    }
  }

  if (Array.isArray(data.rounds)) {
    parts.rounds = data.rounds.filter((r) => r && typeof r === 'object').slice(-50);
  }

  parts.title = typeof data.title === 'string' ? data.title.slice(0, 120) : null;
  parts.savedAt = typeof data.savedAt === 'string' ? data.savedAt : null;
  return { ok: true, parts, notes };
}

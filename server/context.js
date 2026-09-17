/**
 * A class context the teacher uploads at runtime.
 *
 * The built-in pack in `classroom/` describes one specific unit. This lets a
 * teacher describe their own: they download the template, have any AI fill it
 * in from their unit plan, and upload the result before opening the room. The
 * file is read by its `## ` headings, matched loosely so a heading an AI has
 * reworded slightly still lands in the right place.
 */

/**
 * Which section each heading feeds. Matched against the lower-cased heading
 * text with every keyword in the list required, so "What has been taught so
 * far" and "Content taught to date" both resolve to `taught`.
 */
const SECTIONS = [
  // Order matters: "What to talk about" contains "about" too, so the subject
  // boundary is matched before the about-this-class section.
  { key: 'subject', keywords: [['talk about'], ['topics'], ['boundary']], required: false },
  { key: 'about', keywords: [['about']], required: false },
  { key: 'taught', keywords: [['taught'], ['covered'], ['content']], required: true },
  { key: 'references', keywords: [['reference'], ['in-joke'], ['shared']], required: false },
  { key: 'forbidden', keywords: [['not know'], ['must not'], ['avoid']], required: false },
  { key: 'samples', keywords: [['write'], ['writing'], ['samples'], ['voice']], required: false },
  { key: 'blocklist', keywords: [['names'], ['blocklist']], required: false },
];

const MAX_CONTEXT_CHARS = 60000;
const MAX_SAMPLES = 60;
const MAX_SAMPLE_CHARS = 200;

/** Strip the HTML comments the template uses for instructions. */
function stripNotes(text) {
  return String(text || '').replace(/<!--[\s\S]*?-->/g, '');
}

function sectionFor(heading) {
  const lower = heading.toLowerCase();
  for (const section of SECTIONS) {
    if (section.keywords.some((group) => group.every((word) => lower.includes(word)))) {
      return section.key;
    }
  }
  return null;
}

/**
 * Lines of a samples section: bullet points, blockquotes, or bare lines.
 * Empty bullets — the template ships three — are dropped.
 */
function parseSamples(body) {
  return body
    .split(/\r?\n/)
    .map((line) => line.replace(/^\s*(?:[-*]|>|\d+[.)])\s*/, '').trim())
    .filter((line) => line.length > 0 && line.length <= MAX_SAMPLE_CHARS)
    .slice(0, MAX_SAMPLES);
}

/** Comma- or line-separated first names. */
function parseBlocklist(body) {
  return [...new Set(
    body
      .split(/[,\n;]/)
      .map((name) => name.replace(/^\s*[-*]\s*/, '').trim())
      .filter((name) => name && name.length <= 40 && !/^[-\s]*$/.test(name))
  )];
}

/**
 * Parse an uploaded context file.
 *
 * @returns {{ok: true, context: ParsedContext} | {ok: false, error: string}}
 */
export function parseClassContext(raw) {
  const text = stripNotes(raw).replace(/^﻿/, '');
  if (!text.trim()) return { ok: false, error: 'That file is empty.' };
  if (text.length > MAX_CONTEXT_CHARS) {
    return { ok: false, error: `That file is too long (${text.length} characters; the limit is ${MAX_CONTEXT_CHARS}).` };
  }

  const title = (/^#\s+(.+)$/m.exec(text)?.[1] || '').replace(/^Class Context\s*[—-]\s*/i, '').trim();

  const parts = {};
  const unknownHeadings = [];
  const pattern = /^##\s+(.+)$/gm;
  const heads = [...text.matchAll(pattern)];
  for (const [index, head] of heads.entries()) {
    const start = head.index + head[0].length;
    const end = index + 1 < heads.length ? heads[index + 1].index : text.length;
    const body = text.slice(start, end).trim();
    const key = sectionFor(head[1].trim());
    if (!key) { unknownHeadings.push(head[1].trim()); continue; }
    parts[key] = parts[key] ? `${parts[key]}\n\n${body}` : body;
  }

  if (heads.length === 0) {
    return { ok: false, error: 'No "## " headings found. Start from the template — the app reads the file by its headings.' };
  }

  const missing = SECTIONS.filter((s) => s.required && !(parts[s.key] || '').replace(/^[\s-]*$/, '').trim());
  if (missing.length) {
    return { ok: false, error: 'The "What has been taught so far" section is empty. That is the one section the bot cannot do without.' };
  }

  const samples = parseSamples(parts.samples || '');
  const blocklist = parseBlocklist(parts.blocklist || '');
  const isBlank = (value) => !(value || '').replace(/^[\s-]*$/gm, '').trim();

  return {
    ok: true,
    context: {
      title: title || 'Uploaded class context',
      raw: String(raw),
      about: isBlank(parts.about) ? '' : parts.about,
      taught: parts.taught,
      references: isBlank(parts.references) ? '' : parts.references,
      forbidden: isBlank(parts.forbidden) ? '' : parts.forbidden,
      subject: isBlank(parts.subject) ? '' : parts.subject.replace(/\s+/g, ' ').trim(),
      samples,
      blocklist,
      unknownHeadings,
      sectionCount: Object.keys(parts).filter((k) => !isBlank(parts[k])).length,
    },
  };
}

/**
 * The context as the prompt's CLASS CONTEXT block. Only the sections that carry
 * something are rendered, under headings the bot can navigate by.
 */
export function renderContextBlock(context) {
  const out = [`# Class context — ${context.title}`, ''];
  if (context.about) out.push('## About this class', '', context.about, '');
  out.push('## What has been taught so far', '', context.taught, '');
  if (context.references) out.push('## Shared reference points', '', context.references, '');
  if (context.forbidden) {
    out.push(
      '## What you must not know',
      '',
      'None of the following has been taught yet. You have never heard of it. If it comes',
      'up, you do not recognise it.',
      '',
      context.forbidden,
      ''
    );
  }
  return out.join('\n').trim();
}

/** What the console shows about a loaded context. */
export function describeContext(context) {
  if (!context) return null;
  return {
    title: context.title,
    sections: context.sectionCount,
    samples: context.samples.length,
    blocklist: context.blocklist.length,
    hasSubject: Boolean(context.subject),
    unknownHeadings: context.unknownHeadings,
    chars: context.raw.length,
  };
}

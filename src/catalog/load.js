// Loads config/catalog.yaml, checks it thoroughly and returns a ready-to-use catalog object.
// If anything is wrong the error message lists every problem in plain English, so the
// owner can fix the YAML without reading code.

import fs from 'node:fs';
import path from 'node:path';
import YAML from 'yaml';
import { z } from 'zod';

const ID = z.string().regex(/^[a-z0-9][a-z0-9-]*$/, 'ids use lowercase letters, numbers and dashes only');
const DATE = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'dates are written YYYY-MM-DD');
const TIME = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'times are written HH:MM (24-hour)');

const dateRange = z.strictObject({ from: DATE, to: DATE });

const schema = z.strictObject({
  settings: z.strictObject({
    class_size: z.number().int().positive(),
    slots: z
      .array(z.strictObject({ id: ID, label: z.string().min(1), start: TIME, end: TIME }))
      .min(1),
    staff_pool: z.strictObject({ name: z.string().min(1), size: z.number().int().positive() }),
    allowed_pairs_share_rooms: z.boolean().default(true),
    // A semester can be one { from, to } range or a list of ranges (e.g. one per year).
    semesters: z.record(z.string(), z.union([dateRange, z.array(dateRange).min(1)])),
    blackouts: z
      .array(z.strictObject({ date: DATE, reason: z.string().default('Closed') }))
      .nullable()
      .default([]),
  }),
  resources: z
    .array(
      z.strictObject({
        id: ID,
        name: z.string().min(1),
        type: z.enum(['room', 'equipment']),
      }),
    )
    .min(1),
  categories: z.array(z.union([ID, z.strictObject({ id: ID, name: z.string().min(1) })])).min(1),
  programs: z
    .array(
      z.strictObject({
        id: ID,
        name: z.string().min(1),
        category: ID,
        active: z.boolean().default(true),
        semesters: z.array(z.string()).min(1),
        max_classes: z.number().int().positive(),
        staff_required: z.number().int().min(0),
        requires: z.array(z.array(ID).min(1)).default([]),
        cannot_run_with: z.array(ID).nullable().default([]),
        only_runs_with: z.array(ID).nullable().default(null),
        rotation: z.enum(['flexible', 'fixed-order']).nullable().default(null),
        equipment: z.array(z.string()).nullable().default([]),
        software: z.array(z.string()).nullable().default([]),
        notes: z.array(z.string()).nullable().default([]),
        bookings_service_id: z.string().nullable().default(null),
      }),
    )
    .min(1),
});

export class CatalogError extends Error {
  constructor(file, problems) {
    super(
      `The catalog file ${file} has ${problems.length} problem(s):\n` +
        problems.map((p) => `  - ${p}`).join('\n'),
    );
    this.name = 'CatalogError';
    this.problems = problems;
  }
}

// Turns a zod path like ['programs', 3, 'requires', 1] into "programs[3] (hype-machine) → requires[1]".
function describePath(issuePath, raw) {
  let label = '';
  let node = raw;
  for (const part of issuePath) {
    node = node?.[part];
    if (typeof part === 'number') {
      label += `[${part}]`;
      if (node && typeof node === 'object' && typeof node.id === 'string') label += ` (${node.id})`;
    } else {
      label += label ? ` → ${part}` : part;
    }
  }
  return label || '(top level)';
}

function findDuplicates(ids) {
  const seen = new Set();
  const dupes = new Set();
  for (const id of ids) (seen.has(id) ? dupes : seen).add(id);
  return [...dupes];
}

/**
 * Checks raw (already parsed) catalog data and returns the normalised catalog.
 * Throws CatalogError listing every problem found.
 */
export function buildCatalog(raw, file = 'catalog.yaml') {
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    throw new CatalogError(
      file,
      parsed.error.issues.map((i) => `${describePath(i.path, raw)}: ${i.message}`),
    );
  }
  const data = parsed.data;
  const problems = [];

  // --- settings -------------------------------------------------------------
  const semesters = {};
  for (const [key, value] of Object.entries(data.settings.semesters)) {
    semesters[key] = Array.isArray(value) ? value : [value];
    for (const range of semesters[key]) {
      if (range.from > range.to) problems.push(`settings → semesters → ${key}: "from" ${range.from} is after "to" ${range.to}`);
    }
  }
  for (const slot of data.settings.slots) {
    if (slot.start >= slot.end) problems.push(`settings → slots (${slot.id}): start ${slot.start} must be before end ${slot.end}`);
  }

  const categories = data.categories.map((c) =>
    typeof c === 'string' ? { id: c, name: c } : c,
  );

  // --- unique ids -----------------------------------------------------------
  for (const [what, list] of [
    ['resource', data.resources],
    ['program', data.programs],
    ['category', categories],
    ['slot', data.settings.slots],
  ]) {
    for (const id of findDuplicates(list.map((x) => x.id))) problems.push(`Duplicate ${what} id "${id}"`);
  }

  const resourceIds = new Set(data.resources.map((r) => r.id));
  const programIds = new Set(data.programs.map((p) => p.id));
  const categoryIds = new Set(categories.map((c) => c.id));
  const semesterIds = new Set(Object.keys(semesters));

  // --- program references ---------------------------------------------------
  for (const p of data.programs) {
    const where = `Program "${p.id}"`;
    if (!categoryIds.has(p.category)) problems.push(`${where}: unknown category "${p.category}"`);
    for (const s of p.semesters) {
      if (!semesterIds.has(s)) problems.push(`${where}: unknown semester "${s}" (known: ${[...semesterIds].join(', ')})`);
    }
    p.requires.forEach((alternatives, i) => {
      for (const r of alternatives) {
        if (!resourceIds.has(r)) problems.push(`${where} → requires line ${i + 1}: unknown room/equipment "${r}"`);
      }
    });
    for (const field of ['cannot_run_with', 'only_runs_with']) {
      for (const other of p[field] || []) {
        if (!programIds.has(other)) problems.push(`${where} → ${field}: unknown program "${other}"`);
        if (other === p.id) problems.push(`${where} → ${field}: a program can't list itself`);
      }
    }
    if (p.staff_required > data.settings.staff_pool.size) {
      problems.push(
        `${where}: needs ${p.staff_required} staff but the staff pool only has ${data.settings.staff_pool.size}, so it could never be booked`,
      );
    }
  }

  if (problems.length) throw new CatalogError(file, problems);

  // --- normalise --------------------------------------------------------------
  const programs = data.programs.map((p) => ({
    ...p,
    cannot_run_with: p.cannot_run_with || [],
    equipment: p.equipment || [],
    software: p.software || [],
    notes: p.notes || [],
  }));

  // cannot_run_with applies both ways: if A can't run with B, B can't run with A.
  const byId = Object.fromEntries(programs.map((p) => [p.id, p]));
  for (const p of programs) {
    for (const other of p.cannot_run_with) {
      if (!byId[other].cannot_run_with.includes(p.id)) byId[other].cannot_run_with.push(p.id);
    }
  }

  return {
    file,
    settings: {
      ...data.settings,
      semesters,
      blackouts: data.settings.blackouts || [],
    },
    resources: data.resources,
    categories,
    programs,
    index: {
      programs: byId,
      resources: Object.fromEntries(data.resources.map((r) => [r.id, r])),
      categories: Object.fromEntries(categories.map((c) => [c.id, c])),
      slots: Object.fromEntries(data.settings.slots.map((s) => [s.id, s])),
    },
  };
}

/** Reads and validates the catalog file. */
export function loadCatalog(filePath) {
  const shortName = path.relative(process.cwd(), filePath) || filePath;
  let text;
  try {
    text = fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    throw new CatalogError(shortName, [`could not read the file (${err.code || err.message})`]);
  }
  let raw;
  try {
    raw = YAML.parse(text);
  } catch (err) {
    throw new CatalogError(shortName, [`YAML syntax error: ${err.message.split('\n')[0]}`]);
  }
  return buildCatalog(raw, shortName);
}

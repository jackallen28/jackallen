// =====================================================================================
//  THE CLASH ENGINE
//
//  Pure functions: they only look at the catalog and the lists passed in. No database,
//  no web requests — which makes every rule easy to test.
//
//  checkBooking()  → can this one booking go ahead? If not, every reason why.
//  availability()  → checkBooking() for every day/slot in a date range.
//
//  A booking passed in `existingBookings` looks like:
//    { id, programId, date, slotId, classes, status, assignedResources: [...], school }
//  An external busy block (imported from Microsoft Bookings) looks like:
//    { id, date, start: "HH:MM", end: "HH:MM", resourceIds: [...], staff, programId?, label }
// =====================================================================================

import {
  isValidDate,
  isWeekend,
  eachDate,
  toMinutes,
  overlaps,
  semestersOn,
  blackoutOn,
  slotWindow,
} from './dates.js';
import { resourceName } from '../catalog/describe.js';

// Short, generic wording shown on the public website (it never reveals other schools).
const PUBLIC_TEXT = {
  program: 'This program is not available',
  slot: 'Unknown time slot',
  date: 'Closed',
  semester: 'Not offered this semester',
  size: 'Too many classes',
  combination: 'Unavailable — clashes with another program that day',
  resource: 'Unavailable — rooms or equipment already booked',
  staff: 'Unavailable — no staff available',
};

function reason(type, message, { publicMessage, causedBy = [] } = {}) {
  return { type, message, public: publicMessage || PUBLIC_TEXT[type], causedBy };
}

function listNames(names) {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/** Human description of whatever is causing a block, e.g. "booking #12, Riverbend PS". */
function describeOther(other) {
  if (other.kind === 'external') return `Microsoft Bookings: ${other.label || 'appointment'}`;
  return `booking #${other.id}${other.label ? `, ${other.label}` : ''}`;
}

function causedBy(other) {
  return {
    kind: other.kind,
    id: other.id,
    programId: other.programId || null,
    programName: other.program?.name || null,
    label: other.label || null,
  };
}

/** Collects everything else happening at the same time as the request. */
function overlappingActivity({ catalog, existingBookings, externalBusy, date, window, ignoreBookingId }) {
  const others = [];
  for (const b of existingBookings) {
    if (b.status === 'cancelled') continue;
    if (ignoreBookingId != null && b.id === ignoreBookingId) continue;
    if (b.date !== date) continue;
    const w = slotWindow(catalog, b.slotId);
    if (!overlaps(w, window)) continue;
    const program = catalog.index.programs[b.programId] || null;
    others.push({
      kind: 'booking',
      id: b.id,
      programId: b.programId,
      program,
      label: b.school || '',
      resources: b.assignedResources || [],
      staff: program ? program.staff_required : 0,
      ...w,
    });
  }
  for (const x of externalBusy) {
    if (x.date !== date) continue;
    const w = { start: toMinutes(x.start), end: toMinutes(x.end) };
    if (!overlaps(w, window)) continue;
    const program = (x.programId && catalog.index.programs[x.programId]) || null;
    others.push({
      kind: 'external',
      id: x.id,
      programId: x.programId || null,
      program,
      label: x.label || '',
      resources: x.resourceIds || [],
      staff: x.staff || 0,
      ...w,
    });
  }
  return others;
}

/**
 * Combination rules between the requested program and one other program.
 * Returns { blocked: reason | null, allowedPair: boolean }.
 */
function combinationCheck(catalog, program, other) {
  const them = other.program;
  if (!them) return { blocked: null, allowedPair: false };
  const who = describeOther(other);

  if (program.cannot_run_with.includes(them.id) || them.cannot_run_with.includes(program.id)) {
    return {
      blocked: reason('combination', `Can't run alongside ${them.name} (${who})`, { causedBy: [causedBy(other)] }),
      allowedPair: false,
    };
  }
  const names = (ids) => ids.map((id) => catalog.index.programs[id]?.name || id).join(' or ');
  if (program.only_runs_with && !program.only_runs_with.includes(them.id)) {
    const only = program.only_runs_with.length ? ` (only with ${names(program.only_runs_with)})` : '';
    return {
      blocked: reason(
        'combination',
        `${program.name} runs exclusively${only} — ${them.name} is already booked (${who})`,
        { causedBy: [causedBy(other)] },
      ),
      allowedPair: false,
    };
  }
  if (them.only_runs_with && !them.only_runs_with.includes(program.id)) {
    const only = them.only_runs_with.length ? ` (only with ${names(them.only_runs_with)})` : '';
    return {
      blocked: reason(
        'combination',
        `${them.name} is already booked and runs exclusively${only} (${who})`,
        { causedBy: [causedBy(other)] },
      ),
      allowedPair: false,
    };
  }
  const allowedPair =
    Boolean(program.only_runs_with?.includes(them.id)) || Boolean(them.only_runs_with?.includes(program.id));
  return { blocked: null, allowedPair };
}

/**
 * Can this booking go ahead?
 *
 * @param {object}   args
 * @param {object}   args.catalog           loaded catalog
 * @param {object[]} args.existingBookings  bookings already made (any dates; cancelled ones are ignored)
 * @param {object[]} [args.externalBusy]    busy blocks imported from Microsoft Bookings
 * @param {object}   args.request           { programId, date, slotId, classes }
 * @param {string}   [args.today]           "YYYY-MM-DD" — if given, earlier dates are refused
 * @param {*}        [args.ignoreBookingId] skip this booking (when re-checking an existing one)
 * @returns {{ ok: boolean, assignedResources: string[], reasons: object[], staff: object }}
 */
export function checkBooking({
  catalog,
  existingBookings = [],
  externalBusy = [],
  request,
  today = null,
  ignoreBookingId = null,
}) {
  const reasons = [];
  const { programId, date, slotId } = request;
  const classes = Number(request.classes);
  const result = (assignedResources = [], staff = null) => ({
    ok: reasons.length === 0,
    assignedResources,
    reasons,
    staff,
  });

  // ---- 1. program, date and slot -------------------------------------------------
  const program = catalog.index.programs[programId];
  if (!program) {
    reasons.push(reason('program', `Unknown program "${programId}"`));
    return result();
  }
  if (!program.active) reasons.push(reason('program', `${program.name} is not currently offered`));

  if (!isValidDate(date)) {
    reasons.push(reason('date', `"${date}" is not a valid date`, { publicMessage: 'Invalid date' }));
    return result();
  }
  const slot = catalog.index.slots[slotId];
  if (!slot) {
    reasons.push(reason('slot', `Unknown time slot "${slotId}"`));
    return result();
  }

  if (today && date < today) {
    reasons.push(reason('date', 'This date has passed', { publicMessage: 'This date has passed' }));
  }
  if (isWeekend(date)) {
    reasons.push(reason('date', 'Closed on weekends', { publicMessage: 'Closed on weekends' }));
  }
  const blackout = blackoutOn(catalog, date);
  if (blackout) {
    reasons.push(reason('date', `Closed: ${blackout.reason}`, { publicMessage: `Closed: ${blackout.reason}` }));
  }
  const semesters = semestersOn(catalog, date);
  if (semesters.length === 0) {
    reasons.push(reason('date', 'Outside semester dates', { publicMessage: 'Outside semester dates' }));
  } else if (!program.semesters.some((s) => semesters.includes(s))) {
    const offered = program.semesters.map((s) => s.replace(/^S(\d)$/, 'Semester $1')).join(' and ');
    reasons.push(
      reason('semester', `${program.name} is only offered in ${offered}`, {
        publicMessage: `Only offered in ${offered}`,
      }),
    );
  }

  // ---- 2. size --------------------------------------------------------------------
  const classSize = catalog.settings.class_size;
  if (!Number.isInteger(classes) || classes < 1) {
    reasons.push(reason('size', 'Number of classes must be at least 1', { publicMessage: 'At least 1 class' }));
  } else if (classes > program.max_classes) {
    const max = `${program.max_classes} class${program.max_classes > 1 ? 'es' : ''}`;
    reasons.push(
      reason('size', `${program.name} takes at most ${max} (${program.max_classes * classSize} students)`, {
        publicMessage: `Maximum ${max}`,
      }),
    );
  }

  // ---- 3. combination rules with everything else in the same slot -----------------
  const window = { start: toMinutes(slot.start), end: toMinutes(slot.end) };
  const others = overlappingActivity({
    catalog,
    existingBookings,
    externalBusy,
    date,
    window,
    ignoreBookingId,
  });
  const sharesWith = new Set(); // others whose rooms we may share (explicitly allowed pairs)
  for (const other of others) {
    const { blocked, allowedPair } = combinationCheck(catalog, program, other);
    if (blocked) reasons.push(blocked);
    if (allowedPair && catalog.settings.allowed_pairs_share_rooms) sharesWith.add(other);
  }

  // ---- 4. rooms and equipment -------------------------------------------------------
  const heldBy = new Map(); // resourceId → [others holding it]
  for (const other of others) {
    if (sharesWith.has(other)) continue;
    for (const r of other.resources) {
      if (!heldBy.has(r)) heldBy.set(r, []);
      heldBy.get(r).push(other);
    }
  }
  // Fill requirements with a single option first, so "Pink Room" isn't taken by a
  // "Pink or Blue Room" requirement that could have used Blue.
  const order = program.requires
    .map((alternatives, index) => ({ alternatives, index }))
    .sort((a, b) => a.alternatives.length - b.alternatives.length);
  const chosen = new Array(program.requires.length).fill(null);
  for (const { alternatives, index } of order) {
    const free = alternatives.find((r) => !heldBy.has(r) && !chosen.includes(r));
    if (free) {
      chosen[index] = free;
      continue;
    }
    const blockers = [...new Set(alternatives.flatMap((r) => heldBy.get(r) || []))];
    const names = alternatives.map((r) => resourceName(catalog, r));
    const verb = alternatives.length === 1 ? 'in use' : alternatives.length === 2 ? 'both in use' : 'all in use';
    const by = blockers.map((o) => `${o.program?.name || o.label || 'another booking'} – ${describeOther(o)}`);
    if (alternatives.some((r) => chosen.includes(r))) by.push(`another part of ${program.name}`);
    reasons.push(
      reason('resource', `${listNames(names)} ${verb} (${by.join('; ')})`, {
        causedBy: blockers.map(causedBy),
      }),
    );
  }

  // ---- 5 & 6. staff (bookings + imported external blocks) ---------------------------
  const pool = catalog.settings.staff_pool;
  // Find the busiest moment inside our slot (matters when slots of different lengths overlap).
  const checkpoints = [window.start, ...others.map((o) => o.start).filter((s) => s > window.start && s < window.end)];
  let peak = 0;
  let peakOthers = [];
  for (const t of checkpoints) {
    const active = others.filter((o) => o.start <= t && o.end > t);
    const used = active.reduce((sum, o) => sum + o.staff, 0);
    if (used > peak) {
      peak = used;
      peakOthers = active;
    }
  }
  const staff = { used: peak, needed: program.staff_required, pool: pool.size, name: pool.name };
  if (peak + program.staff_required > pool.size) {
    const busy = peakOthers.filter((o) => o.staff > 0);
    reasons.push(
      reason(
        'staff',
        `Not enough ${pool.name}: ${peak} of ${pool.size} already booked ` +
          `(${busy.map((o) => `${o.program?.name || o.label} – ${describeOther(o)}`).join('; ')}) ` +
          `and ${program.name} needs ${program.staff_required}`,
        { causedBy: busy.map(causedBy) },
      ),
    );
  }

  return result(chosen.filter(Boolean), staff);
}

/**
 * Runs checkBooking for every date and slot between `from` and `to` (inclusive).
 * @returns {{ date, slotId, ok, reasons }[]}
 */
export function availability({
  catalog,
  existingBookings = [],
  externalBusy = [],
  programId,
  from,
  to,
  classes = 1,
  today = null,
}) {
  // Group by date once so each day only looks at its own bookings.
  const bookingsByDate = groupByDate(existingBookings);
  const busyByDate = groupByDate(externalBusy);
  const results = [];
  for (const date of eachDate(from, to)) {
    for (const slot of catalog.settings.slots) {
      const check = checkBooking({
        catalog,
        existingBookings: bookingsByDate.get(date) || [],
        externalBusy: busyByDate.get(date) || [],
        request: { programId, date, slotId: slot.id, classes },
        today,
      });
      results.push({ date, slotId: slot.id, ok: check.ok, reasons: check.reasons, staff: check.staff });
    }
  }
  return results;
}

function groupByDate(items) {
  const map = new Map();
  for (const item of items) {
    if (!map.has(item.date)) map.set(item.date, []);
    map.get(item.date).push(item);
  }
  return map;
}

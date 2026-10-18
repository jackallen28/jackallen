// Clash engine tests (spec §10, tests 1–12), using the real config/catalog.yaml.
// Settings that the owner is likely to change (semester dates, staff pool, blackouts) are
// pinned here so the tests keep checking the *rules*, not today's calendar.

import { describe, it, expect } from 'vitest';
import path from 'node:path';
import { loadCatalog } from '../src/catalog/load.js';
import { checkBooking, availability } from '../src/engine/index.js';

const realCatalog = loadCatalog(path.resolve('config/catalog.yaml'));

function testCatalog({ staffPool = 20, blackouts = [] } = {}) {
  const catalog = structuredClone(realCatalog);
  catalog.settings.semesters = {
    S1: [{ from: '2027-01-28', to: '2027-06-25' }],
    S2: [{ from: '2027-07-13', to: '2027-12-17' }],
  };
  catalog.settings.staff_pool.size = staffPool;
  catalog.settings.blackouts = blackouts;
  return catalog;
}

const S2_TUESDAY = '2027-08-03';
const S2_SATURDAY = '2027-08-07';
const S1_TUESDAY = '2027-03-02';

let nextId = 1;
/** Books a program through the engine (so it gets real assigned rooms) and returns the booking. */
function book(catalog, existing, programId, { date = S2_TUESDAY, classes = 1, status = 'confirmed' } = {}) {
  const check = checkBooking({ catalog, existingBookings: existing, request: { programId, date, slotId: 'full', classes } });
  if (!check.ok) throw new Error(`Setup booking ${programId} failed: ${check.reasons.map((r) => r.message).join('; ')}`);
  const booking = { id: nextId++, programId, date, slotId: 'full', classes, status, assignedResources: check.assignedResources, school: 'Test School' };
  existing.push(booking);
  return booking;
}

function attempt(catalog, existing, programId, { date = S2_TUESDAY, classes = 1, externalBusy = [] } = {}) {
  return checkBooking({ catalog, existingBookings: existing, externalBusy, request: { programId, date, slotId: 'full', classes } });
}

describe('clash engine', () => {
  it('1. two programs needing Fibre Hub in the same slot → second is blocked, naming Fibre Hub', () => {
    const catalog = testCatalog();
    const existing = [];
    book(catalog, existing, 'mff-circular-fashion');
    const result = attempt(catalog, existing, '2d-merch-lab');
    expect(result.ok).toBe(false);
    const resource = result.reasons.find((r) => r.type === 'resource');
    expect(resource.message).toMatch(/Fibre Hub in use/);
    expect(resource.message).toMatch(/MFF: Circular Fashion/);
    expect(resource.causedBy[0].id).toBe(existing[0].id);
    expect(resource.public).toBe('Unavailable — rooms or equipment already booked');
  });

  it('2. Medical Emergency + Clean Energy in the same slot → blocked (both orders)', () => {
    const catalog = testCatalog();
    const a = [];
    book(catalog, a, 'medical-emergency');
    const r1 = attempt(catalog, a, 'clean-energy');
    expect(r1.ok).toBe(false);
    expect(r1.reasons.find((r) => r.type === 'combination').message).toMatch(/Can't run alongside Medical Emergency/);

    const b = [];
    book(catalog, b, 'clean-energy');
    const r2 = attempt(catalog, b, 'medical-emergency');
    expect(r2.ok).toBe(false);
    expect(r2.reasons.find((r) => r.type === 'combination').message).toMatch(/Can't run alongside Clean Energy/);
  });

  it('3. Creative TechStyles + Medical Emergency → allowed (allowed pair shares the Pink Room)', () => {
    const catalog = testCatalog();
    const existing = [];
    const me = book(catalog, existing, 'medical-emergency', { classes: 2 });
    expect(me.assignedResources).toContain('pink-room');
    const result = attempt(catalog, existing, 'creative-techstyles');
    expect(result.reasons).toEqual([]);
    expect(result.ok).toBe(true);
    expect(result.assignedResources).toContain('pink-room');

    // ...and the other way round
    const other = [];
    book(catalog, other, 'creative-techstyles');
    expect(attempt(catalog, other, 'medical-emergency').ok).toBe(true);
  });

  it('4. Creative TechStyles + Merch Lab → blocked by the "only runs with" whitelist (both orders)', () => {
    const catalog = testCatalog();
    const a = [];
    book(catalog, a, '2d-merch-lab');
    const r1 = attempt(catalog, a, 'creative-techstyles');
    expect(r1.ok).toBe(false);
    expect(r1.reasons.find((r) => r.type === 'combination').message).toMatch(
      /Creative TechStyles runs exclusively \(only with Medical Emergency or Clean Energy\)/,
    );

    const b = [];
    book(catalog, b, 'creative-techstyles');
    const r2 = attempt(catalog, b, '2d-merch-lab');
    expect(r2.ok).toBe(false);
    expect(r2.reasons.find((r) => r.type === 'combination').message).toMatch(
      /Creative TechStyles is already booked and runs exclusively/,
    );
  });

  it('5. Robot Lab + Smart Spaces → allowed in different rooms; a third Pink/Blue program → blocked', () => {
    const catalog = testCatalog();
    const existing = [];
    const robot = book(catalog, existing, 'ra-robot-lab');
    const spaces = book(catalog, existing, 'ra-smart-spaces');
    expect(robot.assignedResources).toContain('pink-room');
    expect(spaces.assignedResources).toEqual(['blue-room']);

    const third = attempt(catalog, existing, 'intro-entrepreneurship');
    expect(third.ok).toBe(false);
    const resource = third.reasons.find((r) => r.type === 'resource');
    expect(resource.message).toMatch(/Pink Room and Blue Room both in use/);
    expect(resource.message).toMatch(/R&A: Robot Lab/);
    expect(resource.message).toMatch(/R&A: Smart Spaces/);
  });

  it('6. two programs needing VR Headsets in different rooms → second blocked', () => {
    const catalog = testCatalog();
    const existing = [];
    book(catalog, existing, 'media-virtual-worlds'); // Design Hub + VR Headsets
    const result = attempt(catalog, existing, 'ce-gridlock'); // CE Simulation Lab + VR Headsets
    expect(result.ok).toBe(false);
    expect(result.reasons).toHaveLength(1);
    expect(result.reasons[0].type).toBe('resource');
    expect(result.reasons[0].message).toMatch(/VR Headsets in use/);
  });

  it('7. a Semester 2-only program on a Semester 1 date → unavailable', () => {
    const catalog = testCatalog();
    const result = attempt(catalog, [], 'clean-energy', { date: S1_TUESDAY });
    expect(result.ok).toBe(false);
    expect(result.reasons[0].type).toBe('semester');
    expect(result.reasons[0].message).toMatch(/only offered in Semester 2/);
    // ...but fine in Semester 2
    expect(attempt(catalog, [], 'clean-energy', { date: S2_TUESDAY }).ok).toBe(true);
  });

  it('8. classes > max → rejected; classes = max → allowed', () => {
    const catalog = testCatalog();
    const max = catalog.index.programs['medical-emergency'].max_classes;
    expect(attempt(catalog, [], 'medical-emergency', { classes: max }).ok).toBe(true);
    const tooMany = attempt(catalog, [], 'medical-emergency', { classes: max + 1 });
    expect(tooMany.ok).toBe(false);
    expect(tooMany.reasons[0].type).toBe('size');
    expect(attempt(catalog, [], 'medical-emergency', { classes: 0 }).ok).toBe(false);
  });

  it('9. staff pool exceeded → blocked', () => {
    const catalog = testCatalog({ staffPool: 4 });
    const existing = [];
    book(catalog, existing, 'media-exquisite-animation'); // DS Igloo, 2 staff
    book(catalog, existing, '3d-smart-tags'); // Systems Lab + Blue Room, 2 staff → 4 of 4
    const result = attempt(catalog, existing, 'media-hollywood-effects'); // rooms free, no staff left
    expect(result.ok).toBe(false);
    expect(result.reasons).toHaveLength(1);
    expect(result.reasons[0].type).toBe('staff');
    expect(result.reasons[0].message).toMatch(/4 of 4 already booked/);
    expect(result.staff).toMatchObject({ used: 4, needed: 2, pool: 4 });
  });

  it('10. cancelled bookings never block', () => {
    const catalog = testCatalog({ staffPool: 2 });
    const existing = [];
    const me = book(catalog, existing, 'medical-emergency');
    me.status = 'cancelled';
    const result = attempt(catalog, existing, 'clean-energy'); // would clash on combination, rooms, equipment and staff
    expect(result.reasons).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it('11. blackout dates and weekends are unavailable', () => {
    const catalog = testCatalog({ blackouts: [{ date: S2_TUESDAY, reason: 'Staff PD day' }] });
    const blackout = attempt(catalog, [], '3d-smart-tags', { date: S2_TUESDAY });
    expect(blackout.ok).toBe(false);
    expect(blackout.reasons[0].message).toBe('Closed: Staff PD day');

    const weekend = attempt(catalog, [], '3d-smart-tags', { date: S2_SATURDAY });
    expect(weekend.ok).toBe(false);
    expect(weekend.reasons[0].message).toBe('Closed on weekends');
  });

  it('12. an external busy block (imported from Microsoft Bookings) blocks its resource', () => {
    const catalog = testCatalog();
    const externalBusy = [
      { id: 'ext-1', date: S2_TUESDAY, start: '10:00', end: '12:00', resourceIds: ['fibre-hub'], staff: 0, label: 'Staff training' },
    ];
    const result = attempt(catalog, [], '2d-merch-lab', { externalBusy });
    expect(result.ok).toBe(false);
    expect(result.reasons[0].type).toBe('resource');
    expect(result.reasons[0].message).toMatch(/Fibre Hub in use .*Microsoft Bookings: Staff training/);

    // A block mapped to a program also brings that program's combination rules and staff.
    const meBlock = [
      { id: 'ext-2', date: S2_TUESDAY, start: '09:15', end: '14:45', resourceIds: ['drone-room', 'pink-room'], staff: 2, programId: 'medical-emergency', label: 'ME (booked in Bookings)' },
    ];
    const ce = attempt(catalog, [], 'clean-energy', { externalBusy: meBlock });
    expect(ce.ok).toBe(false);
    expect(ce.reasons.map((r) => r.type)).toContain('combination');

    // A block on another day doesn't matter.
    expect(attempt(catalog, [], '2d-merch-lab', { externalBusy: [{ ...externalBusy[0], date: '2027-08-04' }] }).ok).toBe(true);
  });
});

describe('availability()', () => {
  it('returns one result per day and slot with reasons', () => {
    const catalog = testCatalog();
    const existing = [];
    book(catalog, existing, 'medical-emergency');
    const days = availability({ catalog, existingBookings: existing, programId: 'clean-energy', from: '2027-08-02', to: '2027-08-08', classes: 1 });
    expect(days).toHaveLength(7);
    const byDate = Object.fromEntries(days.map((d) => [d.date, d]));
    expect(byDate['2027-08-02'].ok).toBe(true); // Monday
    expect(byDate[S2_TUESDAY].ok).toBe(false); // ME booked
    expect(byDate[S2_TUESDAY].reasons[0].type).toBe('combination');
    expect(byDate[S2_SATURDAY].ok).toBe(false);
  });

  it('refuses dates before "today" when given', () => {
    const catalog = testCatalog();
    const result = checkBooking({ catalog, request: { programId: '3d-smart-tags', date: S2_TUESDAY, slotId: 'full', classes: 1 }, today: '2027-08-04' });
    expect(result.ok).toBe(false);
    expect(result.reasons[0].message).toBe('This date has passed');
  });
});

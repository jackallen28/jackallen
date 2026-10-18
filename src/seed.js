// Demo data: example bookings over the next four weeks that show off the clash rules.
// Seed bookings go through the same rule checks as real ones, and are NEVER sent to
// Outlook or Microsoft Bookings.

import { addDays, weekday } from './engine/dates.js';

// week: 0 = the week starting next Monday. day: 0 = Monday … 4 = Friday.
const SCENARIOS = [
  // Tuesday: Medical Emergency → Clean Energy blocked; Creative TechStyles still allowed (allowed pair)
  { week: 0, day: 1, programId: 'medical-emergency', classes: 2, school: 'Riverbend Primary School', yearLevel: 'Year 6' },
  // Wednesday: Fibre Hub taken → Merch Lab, Wearable Tech, Hype Machine… blocked
  { week: 0, day: 2, programId: 'mff-circular-fashion', classes: 1, school: 'Hillcrest Secondary College', yearLevel: 'Year 9' },
  // Thursday: Pink and Blue rooms both used → a third Pink/Blue program is blocked
  { week: 0, day: 3, programId: 'ra-robot-lab', classes: 2, school: 'Wattle Grove Primary School', yearLevel: 'Year 5' },
  { week: 0, day: 3, programId: 'ra-smart-spaces', classes: 3, school: 'Bluegum College', yearLevel: 'Year 7' },
  // Friday: two bookings use all 4 STEAM Communicators → nothing else fits
  { week: 0, day: 4, programId: '3d-smart-tags', classes: 2, school: 'Ironbark Secondary College', yearLevel: 'Year 8' },
  { week: 0, day: 4, programId: 'media-exquisite-animation', classes: 1, school: 'Saltbush Primary School', yearLevel: 'Year 6' },
  // Next Monday: Creative TechStyles runs exclusively → e.g. Merch Lab blocked by the whitelist
  { week: 1, day: 0, programId: 'creative-techstyles', classes: 1, school: 'Banksia Heights College', yearLevel: 'Year 8' },
  { week: 1, day: 2, programId: 'media-virtual-worlds', classes: 1, school: 'Stringybark Primary School', yearLevel: 'Year 6' },
  { week: 1, day: 3, programId: 'media-podcast-production', classes: 2, school: 'Hillcrest Secondary College', yearLevel: 'Year 10' },
  { week: 2, day: 1, programId: '3d-hot-cup-challenge', classes: 2, school: 'Riverbend Primary School', yearLevel: 'Year 5' },
  { week: 2, day: 2, programId: 'hype-machine', classes: 1, school: 'Bluegum College', yearLevel: 'Year 9' },
  { week: 2, day: 4, programId: '2d-flat-pack-furniture', classes: 1, school: 'Ironbark Secondary College', yearLevel: 'Year 10' },
  { week: 3, day: 0, programId: 'clean-energy', classes: 2, school: 'Wattle Grove Primary School', yearLevel: 'Year 6' },
  { week: 3, day: 3, programId: '2d-glow-up', classes: 2, school: 'Saltbush Primary School', yearLevel: 'Year 7' },
];

const CONTACTS = ['Alex Chen', 'Priya Nair', 'Jordan Smith', 'Mia Rossi', 'Tom Nguyen', 'Grace Wilson', 'Sam Patel'];

/** Monday of the week after `today`. */
function nextMonday(today) {
  const days = (8 - weekday(today)) % 7 || 7;
  return addDays(today, days);
}

/**
 * Deletes ALL bookings and loads the demo bookings.
 * @returns {{ created: object[], skipped: string[] }}
 */
export function seedDemo(ctx) {
  const { store, bookings, catalog } = ctx;
  store.resetAll();
  const monday = nextMonday(ctx.today());
  const created = [];
  const skipped = [];

  SCENARIOS.forEach((s, i) => {
    if (!catalog.index.programs[s.programId]) {
      skipped.push(`${s.programId}: not in the catalog`);
      return;
    }
    const contactName = CONTACTS[i % CONTACTS.length];
    const form = {
      programId: s.programId,
      slotId: catalog.settings.slots[0].id,
      classes: Math.min(s.classes, catalog.index.programs[s.programId].max_classes),
      school: s.school,
      contactName,
      email: `${contactName.toLowerCase().replace(/[^a-z]+/g, '.')}@example.com`,
      phone: `03 9${String(4000000 + i * 1234).slice(0, 3)} ${String(1000 + i * 77).slice(0, 4)}`,
      yearLevel: s.yearLevel,
      notes: '',
    };
    // If the date is closed (holiday, outside the semester…) try the same weekday a week later.
    let last;
    for (let shift = 0; shift < 8; shift++) {
      const date = addDays(monday, (s.week + shift) * 7 + s.day);
      last = bookings.create({ ...form, date }, { source: 'demo', skipSync: true });
      if (last.ok) break;
      const onlyDateProblems = last.reasons?.every((r) => ['date', 'semester'].includes(r.type));
      if (!onlyDateProblems) break;
    }
    if (last.ok) created.push(last.booking);
    else skipped.push(`${s.programId}: ${(last.reasons || []).map((r) => r.message).join('; ') || JSON.stringify(last.errors)}`);
  });

  store.audit('demo.reset', null, { created: created.length, skipped });
  return { created, skipped };
}

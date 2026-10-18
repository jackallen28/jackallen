// Public JSON API used by the booking website (public/js/*.js).

import express from 'express';
import { publicBookingView } from '../bookings.js';
import { isValidDate, addDays } from '../engine/dates.js';
import {
  programRooms,
  programTrackedEquipment,
  describeCombinationRules,
  semesterLabel,
} from '../catalog/describe.js';
import { bookingIcs } from '../ics.js';

const MAX_RANGE_DAYS = 120;

/** What the public website is allowed to know about a program (no staff notes). */
export function publicProgram(catalog, p) {
  return {
    id: p.id,
    name: p.name,
    category: p.category,
    categoryName: catalog.index.categories[p.category]?.name || p.category,
    semesters: p.semesters,
    semesterLabel: semesterLabel(p.semesters),
    maxClasses: p.max_classes,
    maxStudents: p.max_classes * catalog.settings.class_size,
    rooms: programRooms(catalog, p),
    trackedEquipment: programTrackedEquipment(catalog, p),
    equipment: p.equipment,
    software: p.software,
    rotation: p.rotation,
    combinationRules: describeCombinationRules(catalog, p),
  };
}

export function apiRoutes(ctx) {
  const { catalog, bookings, store, config } = ctx;
  const router = express.Router();

  router.get('/catalog', (req, res) => {
    res.json({
      demoMode: config.demoMode,
      classSize: catalog.settings.class_size,
      slots: catalog.settings.slots,
      semesters: catalog.settings.semesters,
      today: ctx.today(),
      categories: catalog.categories,
      programs: catalog.programs.filter((p) => p.active).map((p) => publicProgram(catalog, p)),
    });
  });

  router.get('/programs/:id', (req, res) => {
    const program = catalog.index.programs[req.params.id];
    if (!program || !program.active) return res.status(404).json({ error: 'Program not found' });
    res.json(publicProgram(catalog, program));
  });

  // Availability for each day in a range, e.g. /api/programs/medical-emergency/availability?from=2027-03-01&to=2027-03-31&classes=2
  router.get('/programs/:id/availability', (req, res) => {
    const program = catalog.index.programs[req.params.id];
    if (!program || !program.active) return res.status(404).json({ error: 'Program not found' });
    const from = String(req.query.from || ctx.today());
    const to = String(req.query.to || addDays(from, 41));
    if (!isValidDate(from) || !isValidDate(to) || to < from) {
      return res.status(400).json({ error: 'Use ?from=YYYY-MM-DD&to=YYYY-MM-DD' });
    }
    if (to > addDays(from, MAX_RANGE_DAYS)) {
      return res.status(400).json({ error: `Ask for at most ${MAX_RANGE_DAYS} days at a time` });
    }
    const classes = Number(req.query.classes || 1);
    const results = bookings.availability({ programId: program.id, from, to, classes });
    res.json({
      programId: program.id,
      classes,
      from,
      to,
      days: results.map((r) => ({
        date: r.date,
        slotId: r.slotId,
        ok: r.ok,
        // Public view: the generic wording and rule type only — never other schools' details.
        reasons: dedupe(r.reasons.map((x) => ({ type: x.type, message: x.public }))),
      })),
    });
  });

  router.post('/bookings', (req, res) => {
    const outcome = bookings.create(req.body);
    if (!outcome.ok) {
      if (outcome.status === 409) {
        return res.status(409).json({
          error: 'Sorry — that slot is no longer available. Please choose another date.',
          reasons: dedupe(outcome.reasons.map((x) => ({ type: x.type, message: x.public }))),
        });
      }
      return res.status(outcome.status).json({ error: 'Please check the form', fields: outcome.errors });
    }
    const b = outcome.booking;
    res.status(201).json({ booking: publicBookingView(catalog, b), manageToken: b.manageToken, manageUrl: `/manage/${b.manageToken}` });
  });

  router.get('/manage/:token', (req, res) => {
    const booking = store.getBookingByToken(req.params.token);
    if (!booking) return res.status(404).json({ error: 'Booking not found' });
    res.json({ booking: publicBookingView(catalog, booking) });
  });

  router.post('/manage/:token/cancel', (req, res) => {
    const booking = store.getBookingByToken(req.params.token);
    if (!booking) return res.status(404).json({ error: 'Booking not found' });
    const outcome = bookings.cancel(booking.id, { by: 'school' });
    res.json({ booking: publicBookingView(catalog, outcome.booking) });
  });

  router.get('/manage/:token/booking.ics', (req, res) => {
    const booking = store.getBookingByToken(req.params.token);
    if (!booking) return res.status(404).json({ error: 'Booking not found' });
    res
      .type('text/calendar; charset=utf-8')
      .set('Content-Disposition', `attachment; filename="booking-${booking.id}.ics"`)
      .send(bookingIcs(ctx, booking));
  });

  return router;
}

function dedupe(reasons) {
  const seen = new Set();
  return reasons.filter((r) => {
    const key = `${r.type}|${r.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

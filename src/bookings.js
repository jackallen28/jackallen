// Booking actions used by the website and admin: check availability, create, cancel.
// Creating a booking re-checks every rule inside one locked database transaction, so two
// people clicking "Book" at the same moment can never both get a clashing slot.

import crypto from 'node:crypto';
import { z } from 'zod';
import { checkBooking, availability } from './engine/index.js';
import { addDays, isValidDate } from './engine/dates.js';
import { resourceName } from './catalog/describe.js';

const bookingInput = z.object({
  programId: z.string().min(1),
  date: z.string().refine(isValidDate, 'Choose a valid date'),
  slotId: z.string().min(1),
  classes: z.coerce.number().int('Whole classes only').min(1, 'At least 1 class'),
  school: z.string().trim().min(2, 'Enter the school name').max(200),
  contactName: z.string().trim().min(2, 'Enter a contact name').max(200),
  email: z.string().trim().max(200).pipe(z.email('Enter a valid email address')),
  phone: z.string().trim().min(6, 'Enter a phone number').max(50),
  yearLevel: z.string().trim().min(1, 'Enter the year level').max(50),
  notes: z.string().trim().max(2000).optional().default(''),
  // Hidden "honeypot" field: real people leave it empty, spam bots tend to fill it in.
  website: z.string().max(0, 'Leave this field empty').optional(),
});

export function bookingReference(id) {
  return `PB-${String(id).padStart(5, '0')}`;
}

export function createBookingService({ store, catalog, sync, today }) {
  /** Engine check against what's in the database right now. */
  function check(request, { ignoreBookingId = null, enforceToday = true } = {}) {
    return checkBooking({
      catalog,
      existingBookings: store.activeBookingsOn(request.date),
      externalBusy: store.externalBusyOn(request.date),
      request,
      today: enforceToday ? today() : null,
      ignoreBookingId,
    });
  }

  function programAvailability({ programId, from, to, classes }) {
    return availability({
      catalog,
      existingBookings: store.activeBookingsBetween(from, to),
      externalBusy: store.externalBusyBetween(from, to),
      programId,
      from,
      to,
      classes,
      today: today(),
    });
  }

  /**
   * Validates the form, re-checks the rules and saves the booking — all-or-nothing.
   * @returns {{ ok: true, booking } | { ok: false, status: 400|409, errors?, reasons? }}
   */
  function create(rawInput, { source = 'web', skipSync = false, enforceToday = true } = {}) {
    const parsed = bookingInput.safeParse(rawInput || {});
    if (!parsed.success) {
      const errors = {};
      for (const issue of parsed.error.issues) errors[issue.path[0] || 'form'] ??= issue.message;
      return { ok: false, status: 400, errors };
    }
    const input = parsed.data;
    const program = catalog.index.programs[input.programId];
    if (!program) return { ok: false, status: 400, errors: { programId: 'Unknown program' } };

    const outcome = store.immediate(() => {
      // Reload and check inside the lock: nobody else can write until we finish.
      const result = check(input, { enforceToday });
      if (!result.ok) return { ok: false, status: 409, reasons: result.reasons };
      const booking = store.insertBooking({
        uid: `${crypto.randomUUID()}@program-bookings`,
        programId: input.programId,
        date: input.date,
        slotId: input.slotId,
        classes: input.classes,
        students: input.classes * catalog.settings.class_size,
        assignedResources: result.assignedResources,
        school: input.school,
        contactName: input.contactName,
        email: input.email,
        phone: input.phone,
        yearLevel: input.yearLevel,
        notes: input.notes,
        manageToken: crypto.randomBytes(24).toString('base64url'),
        source,
        syncStatus: !skipSync && sync?.enabled ? 'pending' : 'none',
      });
      store.audit('booking.created', booking.id, {
        program: program.name,
        date: booking.date,
        classes: booking.classes,
        rooms: booking.assignedResources,
        source,
      }, source === 'web' ? `school: ${booking.email}` : source);
      return { ok: true, booking };
    });

    // Tell Outlook / Microsoft Bookings — after saving, and without making the school wait.
    if (outcome.ok && !skipSync && sync?.enabled) sync.bookingCreated(outcome.booking.id);
    return outcome;
  }

  function cancel(id, { by = 'school', skipSync = false } = {}) {
    const existing = store.getBooking(id);
    if (!existing) return { ok: false, status: 404 };
    if (existing.status === 'cancelled') return { ok: true, booking: existing, alreadyCancelled: true };
    const booking = store.immediate(() => {
      const b = store.cancelBooking(id);
      if (!skipSync && sync?.enabled) store.updateSync(id, { status: 'pending' });
      store.audit('booking.cancelled', id, { by }, by);
      return store.getBooking(b.id);
    });
    if (!skipSync && sync?.enabled) sync.bookingCancelled(id);
    return { ok: true, booking };
  }

  return { check, availability: programAvailability, create, cancel };
}

/** The booking as shown to the school (no internal sync details). */
export function publicBookingView(catalog, booking) {
  const program = catalog.index.programs[booking.programId];
  const slot = catalog.index.slots[booking.slotId];
  return {
    reference: bookingReference(booking.id),
    programId: booking.programId,
    programName: program?.name || booking.programId,
    date: booking.date,
    slotId: booking.slotId,
    slotLabel: slot ? `${slot.label} (${slot.start}–${slot.end})` : booking.slotId,
    classes: booking.classes,
    students: booking.students,
    rooms: booking.assignedResources.map((id) => resourceName(catalog, id)),
    school: booking.school,
    contactName: booking.contactName,
    email: booking.email,
    phone: booking.phone,
    yearLevel: booking.yearLevel,
    notes: booking.notes,
    status: booking.status,
    createdAt: booking.createdAt,
  };
}

export function defaultRange(today) {
  return { from: today, to: addDays(today, 41) };
}

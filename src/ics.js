// Builds iCalendar (.ics) text: the "Add to calendar" download, the Outlook subscription
// feeds and the email invites. Times are written in UTC so every calendar app agrees.

import { zonedToUtc } from './time.js';
import { bookingReference } from './bookings.js';
import { resourceName } from './catalog/describe.js';

const PRODID = '-//Program Booking System//EN';

export function escapeText(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

/** Lines longer than 75 bytes must be folded (RFC 5545 §3.1), without splitting a character. */
export function foldLine(line) {
  const bytes = Buffer.from(line, 'utf8');
  if (bytes.length <= 75) return line;
  const parts = [];
  let current = '';
  let currentBytes = 0;
  let limit = 75;
  for (const char of line) {
    const size = Buffer.byteLength(char, 'utf8');
    if (currentBytes + size > limit) {
      parts.push(current);
      current = '';
      currentBytes = 0;
      limit = 74; // continuation lines start with a space
    }
    current += char;
    currentBytes += size;
  }
  parts.push(current);
  return parts.join('\r\n ');
}

function utcStamp(date) {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

function line(name, value) {
  return foldLine(`${name}:${value}`);
}

/** Turns a list of events into a complete calendar file. */
export function buildCalendar({ method = 'PUBLISH', name = null, events = [] }) {
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', `PRODID:${PRODID}`, 'CALSCALE:GREGORIAN', `METHOD:${method}`];
  if (name) {
    lines.push(line('X-WR-CALNAME', escapeText(name)));
    lines.push('REFRESH-INTERVAL;VALUE=DURATION:PT1H', 'X-PUBLISHED-TTL:PT1H');
  }
  for (const e of events) {
    lines.push('BEGIN:VEVENT');
    lines.push(line('UID', e.uid));
    lines.push(`SEQUENCE:${e.sequence || 0}`);
    lines.push(`DTSTAMP:${utcStamp(e.stamp || new Date())}`);
    lines.push(`DTSTART:${utcStamp(e.start)}`);
    lines.push(`DTEND:${utcStamp(e.end)}`);
    lines.push(line('SUMMARY', escapeText(e.summary)));
    if (e.location) lines.push(line('LOCATION', escapeText(e.location)));
    if (e.description) lines.push(line('DESCRIPTION', escapeText(e.description)));
    if (e.url) lines.push(line('URL', e.url));
    if (e.organizer) lines.push(line(`ORGANIZER;CN=${quoteParam(e.organizer.name)}`, `mailto:${e.organizer.email}`));
    for (const a of e.attendees || []) {
      lines.push(line(`ATTENDEE;CN=${quoteParam(a.name || a.email)};ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=FALSE`, `mailto:${a.email}`));
    }
    lines.push(`STATUS:${e.status || 'CONFIRMED'}`);
    lines.push('TRANSP:OPAQUE'); // show as busy
    lines.push('END:VEVENT');
  }
  lines.push('END:VCALENDAR');
  return lines.join('\r\n') + '\r\n';
}

function quoteParam(value) {
  return `"${String(value).replace(/"/g, "'")}"`;
}

/** Start/end instants of a booking (local slot times converted to UTC). */
export function bookingTimes(ctx, booking) {
  const slot = ctx.catalog.index.slots[booking.slotId] || { start: '00:00', end: '23:59' };
  return {
    start: zonedToUtc(booking.date, slot.start, ctx.config.timezone),
    end: zonedToUtc(booking.date, slot.end, ctx.config.timezone),
  };
}

/** Everything a staff calendar entry needs; `audience` = 'staff' or 'school'. */
export function bookingEvent(ctx, booking, { audience = 'staff' } = {}) {
  const { catalog, config } = ctx;
  const program = catalog.index.programs[booking.programId];
  const programName = program?.name || booking.programId;
  const rooms = booking.assignedResources.map((id) => resourceName(catalog, id));
  const ref = bookingReference(booking.id);
  const classes = `${booking.classes} class${booking.classes > 1 ? 'es' : ''}`;
  const manageUrl = config.publicUrl ? `${config.publicUrl}/manage/${booking.manageToken}` : null;

  const description =
    audience === 'school'
      ? [
          `Booking reference: ${ref}`,
          `Program: ${programName}`,
          `School: ${booking.school}`,
          `${classes} (${booking.students} students), ${booking.yearLevel}`,
          manageUrl ? `View or cancel: ${manageUrl}` : null,
        ]
      : [
          `Booking reference: ${ref}`,
          `Program: ${programName}`,
          `School: ${booking.school}`,
          `Contact: ${booking.contactName}, ${booking.email}, ${booking.phone}`,
          `Year level: ${booking.yearLevel}`,
          `Classes: ${classes} (${booking.students} students)`,
          `Rooms/equipment: ${rooms.join(', ') || '—'}`,
          program ? `Staff needed: ${program.staff_required}` : null,
          booking.notes ? `School's notes: ${booking.notes}` : null,
          program?.notes?.length ? `Staff notes: ${program.notes.join(' · ')}` : null,
        ];

  return {
    uid: booking.uid,
    sequence: booking.sequence,
    ...bookingTimes(ctx, booking),
    summary:
      audience === 'school' ? `${programName} (${ref})` : `${programName} – ${booking.school} (${classes})`,
    location: rooms.join(', '),
    description: description.filter(Boolean).join('\n'),
    url: manageUrl,
    status: booking.status === 'cancelled' ? 'CANCELLED' : 'CONFIRMED',
  };
}

/** The "Add to calendar" file a school downloads. */
export function bookingIcs(ctx, booking) {
  return buildCalendar({ method: 'PUBLISH', events: [bookingEvent(ctx, booking, { audience: 'school' })] });
}

/** Subscription feed for Outlook. Cancelled bookings are left out. */
export function feedIcs(ctx, bookings, name) {
  return buildCalendar({
    method: 'PUBLISH',
    name,
    events: bookings.filter((b) => b.status !== 'cancelled').map((b) => bookingEvent(ctx, b)),
  });
}

/** Meeting invite (REQUEST) or cancellation (CANCEL) sent to the Bookings/staff mailboxes. */
export function inviteIcs(ctx, booking, method, { organizer, attendees }) {
  const event = bookingEvent(ctx, booking);
  return buildCalendar({
    method,
    events: [
      {
        ...event,
        organizer,
        attendees,
        status: method === 'CANCEL' ? 'CANCELLED' : 'CONFIRMED',
      },
    ],
  });
}

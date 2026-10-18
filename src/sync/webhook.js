// SYNC_MODE=webhook — sends every booking and cancellation as JSON to a Power Automate flow
// (trigger: "When an HTTP request is received"). The flow decides what to do with it, e.g.
// create a busy event on the staff / Bookings calendars, post in Teams, or email someone.
// No IT app registration is needed. See docs/POWER-AUTOMATE-SETUP.md.
//
// The event subject always ends with the booking reference, e.g. "[PB-00012]", so a flow can
// find and delete the calendar event again when the booking is cancelled.

import { bookingEvent } from '../ics.js';
import { bookingReference } from '../bookings.js';
import { resourceName } from '../catalog/describe.js';
import { windowsZone } from '../time.js';

const TIMEOUT_MS = 20000;

/** The JSON a flow receives. Keep field names stable — flows depend on them. */
export function webhookPayload({ catalog, config }, booking, event) {
  const program = catalog.index.programs[booking.programId];
  const slot = catalog.index.slots[booking.slotId] || { start: '00:00', end: '23:59' };
  const ics = bookingEvent({ catalog, config }, booking);
  const reference = bookingReference(booking.id);
  return {
    event, // booking.created | booking.cancelled | booking.test
    reference,
    bookingId: booking.id,
    uid: booking.uid,
    status: booking.status,
    // On booking.cancelled: whatever the flow returned as {"externalId"} when the booking was created
    // (e.g. the Outlook event id), so the flow can delete exactly that event.
    externalId: booking.externalId || null,
    programId: booking.programId,
    programName: program?.name || booking.programId,
    category: program?.category || null,
    bookingsServiceId: program?.bookings_service_id || null,
    date: booking.date,
    startTime: slot.start,
    endTime: slot.end,
    startLocal: `${booking.date}T${slot.start}:00`,
    endLocal: `${booking.date}T${slot.end}:00`,
    startUtc: ics.start.toISOString(),
    endUtc: ics.end.toISOString(),
    timeZone: config.timezone,
    windowsTimeZone: windowsZone(config.timezone),
    classes: booking.classes,
    students: booking.students,
    yearLevel: booking.yearLevel,
    school: booking.school,
    contactName: booking.contactName,
    email: booking.email,
    phone: booking.phone,
    notes: booking.notes,
    rooms: booking.assignedResources.map((id) => resourceName(catalog, id)),
    roomsText: booking.assignedResources.map((id) => resourceName(catalog, id)).join(', '),
    staffRequired: program?.staff_required ?? null,
    subject: `${ics.summary} [${reference}]`,
    description: ics.description,
    manageUrl: config.publicUrl ? `${config.publicUrl}/manage/${booking.manageToken}` : null,
  };
}

export function createWebhookAdapter({ config, catalog, fetchImpl = fetch }) {
  async function post(booking, event) {
    const url = config.webhook.url;
    if (!url) throw new Error('POWER_AUTOMATE_WEBHOOK_URL is not set — paste the HTTP POST URL of your flow');
    const res = await fetchImpl(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(webhookPayload({ catalog, config }, booking, event)),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await res.text().catch(() => '');
    if (!res.ok) throw new Error(`Power Automate flow returned ${res.status}: ${text.slice(0, 200) || res.statusText}`);
    // If the flow ends with a "Response" action returning {"externalId": "..."} we keep it.
    try {
      const data = text ? JSON.parse(text) : null;
      return { externalId: data?.externalId ? String(data.externalId) : undefined };
    } catch {
      return {};
    }
  }

  return {
    name: 'webhook',
    onBookingCreated: (booking) => post(booking, 'booking.created'),
    async onBookingCancelled(booking) {
      await post(booking, 'booking.cancelled');
    },
    /** Sends a sample so the flow's trigger schema can be generated / tested. */
    sendTest: (booking) => post(booking, 'booking.test'),
  };
}

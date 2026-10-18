// Inbound endpoint for Power Automate: a flow triggered by Microsoft Bookings ("When an
// appointment is created / updated / cancelled") tells the site about the appointment, so it
// blocks the same rooms, equipment and staff — and the program's combination rules apply.
//
//   POST /api/integrations/power-automate
//   Header:  Authorization: Bearer <INBOUND_WEBHOOK_SECRET>     (or  x-webhook-secret: <secret>)
//   Body:    { "action": "created" | "updated" | "cancelled",
//              "appointmentId": "...",
//              "serviceName": "Medical Emergency",     (or "serviceId")
//              "start": "2026-11-10T22:15:00Z", "end": "2026-11-11T03:45:00Z",
//              "timeZone": "UTC",                         (optional — for times without Z/offset)
//              "customerName": "..." }                    (optional, shown to staff only)
//
// See docs/POWER-AUTOMATE-SETUP.md for how to build the flows.

import crypto from 'node:crypto';
import express from 'express';
import { localParts, zonedToUtc } from '../time.js';

export const SOURCE = 'power-automate';

const WINDOWS_TO_IANA = {
  'AUS Eastern Standard Time': 'Australia/Melbourne',
  'Tasmania Standard Time': 'Australia/Hobart',
  'E. Australia Standard Time': 'Australia/Brisbane',
  'Cen. Australia Standard Time': 'Australia/Adelaide',
  'AUS Central Standard Time': 'Australia/Darwin',
  'W. Australia Standard Time': 'Australia/Perth',
  'UTC': 'UTC',
  'Coordinated Universal Time': 'UTC',
};

function secretMatches(expected, given) {
  if (!expected || !given) return false;
  const a = crypto.createHash('sha256').update(String(given)).digest();
  const b = crypto.createHash('sha256').update(expected).digest();
  return crypto.timingSafeEqual(a, b);
}

/** First non-empty value among several possible field names (flows name things differently). */
function pick(body, ...names) {
  for (const n of names) if (body[n] !== undefined && body[n] !== null && body[n] !== '') return body[n];
  return undefined;
}

/**
 * Turns whatever time format the flow sends into local { date, time }.
 * Accepts "…Z", "…+10:00", a Graph-style { dateTime, timeZone } object, or a plain
 * "2026-11-10T09:15:00" (read in `timeZone` if given, otherwise in the site's timezone).
 */
export function toLocal(value, timeZoneHint, siteZone) {
  if (!value) return null;
  let raw = value;
  let zone = timeZoneHint;
  if (typeof value === 'object') {
    raw = value.dateTime;
    zone = value.timeZone || zone;
  }
  if (typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(raw)) return null;
  if (/(Z|[+-]\d{2}:?\d{2})$/.test(raw)) {
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : localParts(d, siteZone);
  }
  const iana = zone ? WINDOWS_TO_IANA[zone] || zone : siteZone;
  if (iana === siteZone) return { date: raw.slice(0, 10), time: raw.slice(11, 16) };
  try {
    return localParts(zonedToUtc(raw.slice(0, 10), raw.slice(11, 16), iana), siteZone);
  } catch {
    return null; // unknown timezone name
  }
}

export function integrationRoutes(ctx) {
  const { config, catalog, store } = ctx;
  const router = express.Router();

  router.post('/api/integrations/power-automate', (req, res) => {
    if (!config.webhook.inboundSecret) {
      return res.status(404).json({ error: 'Inbound webhook is off (set INBOUND_WEBHOOK_SECRET)' });
    }
    const auth = req.get('authorization') || '';
    const given = auth.replace(/^Bearer\s+/i, '') || req.get('x-webhook-secret') || req.query.key;
    if (!secretMatches(config.webhook.inboundSecret, given)) return res.status(401).json({ error: 'Wrong or missing secret' });

    const body = req.body || {};
    const action = String(pick(body, 'action', 'event', 'type') || 'created').toLowerCase();
    const appointmentId = pick(body, 'appointmentId', 'id', 'appointmentID', 'selfServiceAppointmentId');
    if (!appointmentId) return res.status(400).json({ error: 'appointmentId is required' });

    store.setMeta('powerAutomate.lastInbound', JSON.stringify({ at: new Date().toISOString(), action, body }));

    if (/cancel|delet/.test(action)) {
      const removed = store.deleteExternalBusy(SOURCE, appointmentId);
      store.audit('bookings.appointment_cancelled', null, { appointmentId, removed });
      return res.json({ ok: true, action: 'cancelled', removed });
    }

    const zoneHint = pick(body, 'timeZone', 'timezone', 'startTimeZone');
    const start = toLocal(pick(body, 'start', 'startTime', 'startDateTime', 'Start'), zoneHint, config.timezone);
    const end = toLocal(pick(body, 'end', 'endTime', 'endDateTime', 'End'), zoneHint, config.timezone);
    if (!start || !end) {
      return res.status(400).json({ error: 'start and end must be date-times, e.g. "2026-11-10T22:15:00Z"' });
    }

    // Which program is this? By Bookings service id first, then by exact service name.
    const serviceId = pick(body, 'serviceId', 'ServiceId');
    const serviceName = String(pick(body, 'serviceName', 'service', 'ServiceName') || '').trim();
    const program =
      (serviceId && catalog.programs.find((p) => p.bookings_service_id === serviceId)) ||
      catalog.programs.find((p) => p.name.trim().toLowerCase() === serviceName.toLowerCase()) ||
      null;

    const customer = pick(body, 'customerName', 'customer', 'CustomerName');
    const block = ctx.sync.placeBlock({
      externalId: String(appointmentId),
      date: start.date,
      start: start.time,
      end: end.date === start.date ? end.time : '23:59',
      programId: program?.id || null,
      label: [serviceName || program?.name || 'Bookings appointment', customer].filter(Boolean).join(' – '),
    });
    store.upsertExternalBusy(SOURCE, block);
    store.audit('bookings.appointment_received', null, {
      appointmentId,
      program: program?.name || null,
      date: block.date,
      time: `${block.start}–${block.end}`,
    });

    res.json({
      ok: true,
      action: 'saved',
      linkedProgram: program?.name || null,
      warning: program ? undefined : `No program matches service "${serviceName || serviceId}" — saved, but it blocks nothing`,
      date: block.date,
      start: block.start,
      end: block.end,
      holds: block.resourceIds,
    });
  });

  return router;
}

// A small fake of the Microsoft Graph Bookings API, so graph mode can be tested (and demoed)
// before real credentials exist. Used by the tests and by `npm run graph:mock`.
// It only implements the endpoints this app uses.

import express from 'express';
import { zonedToUtc } from '../time.js';

const WINDOWS_TO_IANA = { 'AUS Eastern Standard Time': 'Australia/Melbourne', UTC: 'UTC' };

function toUtc(value) {
  if (!value?.dateTime) return null;
  if (value.timeZone === 'UTC' || /Z$/.test(value.dateTime)) {
    return new Date(/Z$/.test(value.dateTime) ? value.dateTime : `${value.dateTime}Z`);
  }
  const zone = WINDOWS_TO_IANA[value.timeZone] || 'UTC';
  return zonedToUtc(value.dateTime.slice(0, 10), value.dateTime.slice(11, 16), zone);
}

function graphTime(date) {
  return { dateTime: date.toISOString().replace(/\.\d{3}Z$/, '.0000000Z'), timeZone: 'UTC' };
}

/**
 * @param {object} opts
 * @param {string} [opts.businessId]
 * @param {{id: string, displayName: string}[]} [opts.services]
 */
export function createMockGraph({ businessId = 'bnts@example.onmicrosoft.com', services = [] } = {}) {
  const state = { appointments: new Map(), services, requests: [], failNext: 0, nextId: 1 };
  const app = express();
  app.use(express.json());

  app.use((req, res, next) => {
    state.requests.push({ method: req.method, path: req.path, body: req.body });
    if (!/^Bearer .+/.test(req.headers.authorization || '')) {
      return res.status(401).json({ error: { code: 'InvalidAuthenticationToken', message: 'Access token is empty.' } });
    }
    if (state.failNext > 0) {
      state.failNext--;
      return res.status(503).json({ error: { code: 'ServiceUnavailable', message: 'Mock outage' } });
    }
    next();
  });

  const base = '/v1.0/solutions/bookingBusinesses';
  const checkBusiness = (req, res, next) =>
    req.params.biz === businessId
      ? next()
      : res.status(404).json({ error: { code: 'ErrorItemNotFound', message: 'Booking business not found' } });

  app.get(base, (req, res) => res.json({ value: [{ id: businessId, displayName: 'Banyule Nillumbik Tech School (mock)' }] }));

  app.get(`${base}/:biz/services`, checkBusiness, (req, res) => res.json({ value: state.services }));

  app.post(`${base}/:biz/appointments`, checkBusiness, (req, res) => {
    const service = state.services.find((s) => s.id === req.body.serviceId);
    if (!service) return res.status(400).json({ error: { code: 'ErrorInvalidRequest', message: 'serviceId is not valid' } });
    const id = `AAMkMock${state.nextId++}`;
    const appointment = {
      ...req.body,
      id,
      serviceName: service.displayName,
      startDateTime: graphTime(toUtc(req.body.startDateTime)),
      endDateTime: graphTime(toUtc(req.body.endDateTime)),
      isCancelled: false,
    };
    state.appointments.set(id, appointment);
    res.status(201).json(appointment);
  });

  app.post(`${base}/:biz/appointments/:id/cancel`, checkBusiness, (req, res) => {
    const appointment = state.appointments.get(req.params.id);
    if (!appointment) return res.status(404).json({ error: { code: 'ErrorItemNotFound', message: 'Not found' } });
    appointment.isCancelled = true;
    appointment.cancellationMessage = req.body?.cancellationMessage;
    res.status(204).end();
  });

  app.get(`${base}/:biz/calendarView`, checkBusiness, (req, res) => {
    const start = new Date(req.query.start);
    const end = new Date(req.query.end);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return res.status(400).json({ error: { code: 'ErrorInvalidRequest', message: 'start and end are required' } });
    }
    const value = [...state.appointments.values()].filter((a) => {
      if (a.isCancelled) return false;
      const s = new Date(a.startDateTime.dateTime);
      return s >= start && s < end;
    });
    res.json({ value });
  });

  /** Pretend someone booked directly in Microsoft Bookings. Times are local (Melbourne). */
  function addDirectAppointment({ serviceId, date, start, end, customerName = 'Booked in Bookings' }) {
    const service = state.services.find((s) => s.id === serviceId);
    const id = `AAMkDirect${state.nextId++}`;
    state.appointments.set(id, {
      id,
      serviceId,
      serviceName: service?.displayName || 'Service',
      startDateTime: graphTime(zonedToUtc(date, start, 'Australia/Melbourne')),
      endDateTime: graphTime(zonedToUtc(date, end, 'Australia/Melbourne')),
      customers: [{ name: customerName }],
      isCancelled: false,
    });
    return id;
  }

  return { app, state, businessId, addDirectAppointment };
}

/** Mock services named exactly like the catalog programs (so they link automatically by name). */
export function servicesFromCatalog(catalog) {
  return catalog.programs.map((p) => ({ id: `mock-service-${p.id}`, displayName: p.name }));
}

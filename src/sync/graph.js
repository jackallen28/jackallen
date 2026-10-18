// SYNC_MODE=graph — full Microsoft Bookings sync through the Microsoft Graph API.
// Needs an Entra ID (Azure AD) app registration from IT — see docs/M365-BOOKINGS-SETUP.md.
//
//  • New booking   → POST /solutions/bookingBusinesses/{id}/appointments
//  • Cancellation  → POST /solutions/bookingBusinesses/{id}/appointments/{appointmentId}/cancel
//  • Import        → GET  /solutions/bookingBusinesses/{id}/calendarView   (next 120 days)
//                    so bookings made directly in Microsoft Bookings block rooms/staff here.
//
// Each program is linked to a Bookings "service" by `bookings_service_id` in catalog.yaml.
// If that is empty, a Bookings service with exactly the same name as the program is used.

import { ConfidentialClientApplication } from '@azure/msal-node';
import { zonedToUtc, localParts, windowsZone } from '../time.js';
import { bookingEvent } from '../ics.js';
import { addDays } from '../engine/dates.js';

const SERVICES_CACHE_MS = 10 * 60 * 1000;

function isLocal(url) {
  return /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(url + '/');
}

/** Gets app-only access tokens with the client-credentials flow (MSAL caches them). */
function msalTokenProvider(graph) {
  let app;
  return async () => {
    if (!graph.tenantId || !graph.clientId || !graph.clientSecret) {
      throw new Error('GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET must all be set for SYNC_MODE=graph');
    }
    app ??= new ConfidentialClientApplication({
      auth: {
        clientId: graph.clientId,
        clientSecret: graph.clientSecret,
        authority: `https://login.microsoftonline.com/${graph.tenantId}`,
      },
    });
    const result = await app.acquireTokenByClientCredential({ scopes: ['https://graph.microsoft.com/.default'] });
    if (!result?.accessToken) throw new Error('Could not get an access token from Microsoft Entra ID');
    return result.accessToken;
  };
}

export function createGraphAdapter({ config, catalog, tokenProvider = null, fetchImpl = fetch }) {
  const graph = config.graph;
  // The local mock server (npm run graph:mock) doesn't need real credentials.
  const getToken = tokenProvider || (isLocal(graph.baseUrl) ? async () => 'mock-token' : msalTokenProvider(graph));
  const winZone = windowsZone(config.timezone);
  let servicesCache = null;

  function businessPath(suffix = '') {
    if (!graph.businessId) throw new Error('BOOKINGS_BUSINESS_ID is not set (run `npm run graph:check` to list your Bookings businesses)');
    return `/solutions/bookingBusinesses/${encodeURIComponent(graph.businessId)}${suffix}`;
  }

  async function request(method, pathOrUrl, body) {
    const url = pathOrUrl.startsWith('http') ? pathOrUrl : `${graph.baseUrl}${pathOrUrl}`;
    const res = await fetchImpl(url, {
      method,
      headers: {
        Authorization: `Bearer ${await getToken()}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 204) return null;
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const detail = data?.error?.message || data?.error?.code || text.slice(0, 200) || res.statusText;
      const err = new Error(`Microsoft Graph ${method} ${url.replace(graph.baseUrl, '')} failed (${res.status}): ${detail}`);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  async function listAll(path) {
    const items = [];
    let next = path;
    while (next) {
      const page = await request('GET', next);
      items.push(...(page?.value || []));
      next = page?.['@odata.nextLink'] || null;
    }
    return items;
  }

  async function listServices({ fresh = false } = {}) {
    if (!fresh && servicesCache && Date.now() - servicesCache.at < SERVICES_CACHE_MS) return servicesCache.list;
    const list = await listAll(businessPath('/services'));
    servicesCache = { at: Date.now(), list };
    return list;
  }

  /** The Bookings service for a program: explicit id first, otherwise a service with the same name. */
  async function serviceIdFor(program) {
    if (program.bookings_service_id) return program.bookings_service_id;
    const match = (await listServices()).find(
      (s) => (s.displayName || '').trim().toLowerCase() === program.name.trim().toLowerCase(),
    );
    return match?.id || null;
  }

  /** A local date+time in the format Bookings expects. */
  function dateTime(date, time) {
    if (winZone) return { '@odata.type': '#microsoft.graph.dateTimeTimeZone', dateTime: `${date}T${time}:00.0000000`, timeZone: winZone };
    return { '@odata.type': '#microsoft.graph.dateTimeTimeZone', dateTime: zonedToUtc(date, time, config.timezone).toISOString(), timeZone: 'UTC' };
  }

  /** Graph dateTimeTimeZone → local { date, time }. */
  function toLocal(value) {
    if (!value?.dateTime) return null;
    const zone = value.timeZone || 'UTC';
    if (winZone && zone === winZone) {
      return { date: value.dateTime.slice(0, 10), time: value.dateTime.slice(11, 16) };
    }
    const iso = /Z$|[+-]\d{2}:\d{2}$/.test(value.dateTime) ? value.dateTime : `${value.dateTime}Z`;
    return localParts(new Date(iso), config.timezone);
  }

  return {
    name: 'graph',

    async onBookingCreated(booking, program) {
      if (!program) throw new Error(`Program "${booking.programId}" is no longer in the catalog`);
      const serviceId = await serviceIdFor(program);
      if (!serviceId) {
        throw new Error(
          `"${program.name}" isn't linked to a Microsoft Bookings service yet — add its bookings_service_id ` +
            'to config/catalog.yaml (`npm run graph:check` lists the ids), or name the Bookings service exactly like the program',
        );
      }
      const slot = catalog.index.slots[booking.slotId] || { start: '09:00', end: '15:00' };
      const event = bookingEvent({ catalog, config }, booking);
      const appointment = await request('POST', businessPath('/appointments'), {
        '@odata.type': '#microsoft.graph.bookingAppointment',
        serviceId,
        startDateTime: dateTime(booking.date, slot.start),
        endDateTime: dateTime(booking.date, slot.end),
        customerTimeZone: winZone || 'UTC',
        isLocationOnline: false,
        // The school already gets our confirmation page; don't send a second email from Bookings.
        optOutOfCustomerEmail: true,
        serviceNotes: event.description,
        customers: [
          {
            '@odata.type': '#microsoft.graph.bookingCustomerInformation',
            name: `${booking.contactName} (${booking.school})`,
            emailAddress: booking.email,
            phone: booking.phone,
            notes: `${booking.school} · ${booking.yearLevel} · ${booking.classes} class(es)`,
            timeZone: winZone || 'UTC',
          },
        ],
      });
      return { externalId: appointment?.id };
    },

    async onBookingCancelled(booking) {
      if (!booking.externalId) return; // never reached Bookings, nothing to cancel
      try {
        await request('POST', businessPath(`/appointments/${encodeURIComponent(booking.externalId)}/cancel`), {
          cancellationMessage: 'Cancelled through the program booking website.',
        });
      } catch (err) {
        if (err.status === 404) return; // already gone in Bookings
        throw err;
      }
    },

    async importBusy(fromDate, toDate) {
      const start = zonedToUtc(fromDate, '00:00', config.timezone).toISOString();
      const end = zonedToUtc(addDays(toDate, 1), '00:00', config.timezone).toISOString();
      const appointments = await listAll(
        businessPath(`/calendarView?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
      );
      const services = await listServices().catch(() => []);
      const programByService = new Map();
      for (const p of catalog.programs) {
        const id =
          p.bookings_service_id ||
          services.find((s) => (s.displayName || '').trim().toLowerCase() === p.name.trim().toLowerCase())?.id;
        if (id) programByService.set(id, p.id);
      }
      const blocks = [];
      for (const a of appointments) {
        if (a.isCancelled) continue;
        const s = toLocal(a.startDateTime);
        const e = toLocal(a.endDateTime);
        if (!s || !e) continue;
        blocks.push({
          externalId: a.id,
          date: s.date,
          start: s.time,
          end: e.date === s.date ? e.time : '23:59',
          programId: programByService.get(a.serviceId) || null,
          label: [a.serviceName, a.customers?.[0]?.name || a.customerName].filter(Boolean).join(' – ') || 'Bookings appointment',
        });
      }
      return blocks;
    },

    // Used by `npm run graph:check`
    listBusinesses: () => listAll('/solutions/bookingBusinesses'),
    listServices: () => listServices({ fresh: true }),
    getToken,
  };
}

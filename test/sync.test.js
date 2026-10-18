import { describe, it, expect, afterEach } from 'vitest';
import request from 'supertest';
import fs from 'node:fs';
import path from 'node:path';
import { createApp } from '../src/app.js';
import { createMockGraph, servicesFromCatalog } from '../src/sync/graph-mock.js';
import { testContext, testCatalog, bookingForm, S2_TUESDAY, S2_WEDNESDAY } from './helpers.js';

const quiet = { warn() {}, log() {} };
const open = [];
afterEach(async () => {
  while (open.length) {
    const item = open.pop();
    await item.close();
  }
});

/** A strict-enough iCalendar check (RFC 5545 basics that Outlook cares about). */
function validateIcs(text) {
  const problems = [];
  if (!text.endsWith('\r\n')) problems.push('must end with CRLF');
  if (/[^\r]\n/.test(text)) problems.push('bare LF line ending');
  const lines = text.split('\r\n').slice(0, -1);
  if (lines[0] !== 'BEGIN:VCALENDAR' || lines[lines.length - 1] !== 'END:VCALENDAR') problems.push('not wrapped in VCALENDAR');
  for (const line of lines) if (Buffer.byteLength(line) > 75) problems.push(`line over 75 octets: ${line.slice(0, 30)}…`);
  const unfolded = text.replace(/\r\n /g, '').split('\r\n');
  for (const prop of ['VERSION:2.0', 'PRODID:']) if (!unfolded.some((l) => l.startsWith(prop))) problems.push(`missing ${prop}`);
  const events = text.replace(/\r\n /g, '').split('BEGIN:VEVENT').slice(1);
  const uids = new Set();
  for (const ev of events) {
    for (const prop of ['UID:', 'DTSTAMP:', 'DTSTART:', 'DTEND:', 'SUMMARY:']) if (!ev.includes(`\r\n${prop}`)) problems.push(`event missing ${prop}`);
    const uid = ev.match(/\r\nUID:(.*)\r\n/)?.[1];
    if (uids.has(uid)) problems.push(`duplicate UID ${uid}`);
    uids.add(uid);
    if (!ev.includes('END:VEVENT')) problems.push('unterminated VEVENT');
  }
  return { problems, events };
}

describe('calendar feeds', () => {
  it('all-bookings and room feeds are valid, use stable UIDs and drop cancelled bookings', async () => {
    const ctx = testContext();
    open.push(ctx);
    const app = createApp(ctx);
    const a = await request(app).post('/api/bookings').send(bookingForm({ notes: 'Long notes, with commas; semicolons and a very long sentence that needs folding across several lines in the calendar file ✓' })).expect(201);
    await request(app).post('/api/bookings').send(bookingForm({ programId: '3d-smart-tags', date: S2_WEDNESDAY, classes: 1 })).expect(201);

    await request(app).get('/calendar/wrong-token/all.ics').expect(404);
    const feed = await request(app).get('/calendar/test-feed-token/all.ics').expect(200);
    expect(feed.headers['content-type']).toMatch(/text\/calendar/);
    const { problems, events } = validateIcs(feed.text);
    expect(problems).toEqual([]);
    expect(events).toHaveLength(2);
    const uid = feed.text.match(/UID:(.*)\r\n/)[1];

    const pink = await request(app).get('/calendar/test-feed-token/room/pink-room.ics').expect(200);
    expect(validateIcs(pink.text).events).toHaveLength(1); // only Medical Emergency uses the Pink Room
    await request(app).get('/calendar/test-feed-token/room/nowhere.ics').expect(404);

    await request(app).post(`/api/manage/${a.body.manageToken}/cancel`).expect(200);
    const after = await request(app).get('/calendar/test-feed-token/all.ics');
    expect(validateIcs(after.text).events).toHaveLength(1);
    expect(after.text).not.toContain(uid);
  });

  it('feeds are off while CALENDAR_FEED_TOKEN is the placeholder', async () => {
    const ctx = testContext({ env: { CALENDAR_FEED_TOKEN: 'change-me-to-a-long-random-string' } });
    open.push(ctx);
    await request(createApp(ctx)).get('/calendar/change-me-to-a-long-random-string/all.ics').expect(404);
  });
});

describe('SYNC_MODE=email', () => {
  it('writes REQUEST and CANCEL invites to data/outbox as .eml files', async () => {
    const ctx = testContext({ env: { SYNC_MODE: 'email', INVITE_ADDRESSES: 'bookings-calendar@example.org, staff@example.org', SMTP_FROM: 'noreply@example.org' }, logger: quiet });
    open.push(ctx);
    const app = createApp(ctx);
    const created = await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();

    const outbox = path.join(ctx.config.dataDir, 'outbox');
    let files = fs.readdirSync(outbox);
    expect(files).toHaveLength(1);
    const invite = fs.readFileSync(path.join(outbox, files[0]), 'utf8');
    expect(invite).toMatch(/To: bookings-calendar@example.org, staff@example.org/);
    expect(invite).toMatch(/text\/calendar; charset=utf-8; method=REQUEST/i);
    expect(invite).toContain('METHOD:REQUEST');
    expect(ctx.store.getBooking(1).syncStatus).toBe('synced');

    await request(app).post(`/api/manage/${created.body.manageToken}/cancel`).expect(200);
    await ctx.sync.idle();
    files = fs.readdirSync(outbox).sort();
    expect(files).toHaveLength(2);
    const cancel = fs.readFileSync(path.join(outbox, files.find((f) => f.includes('_cancel_'))), 'utf8');
    expect(cancel).toContain('METHOD:CANCEL');
    expect(cancel).toContain('STATUS:CANCELLED');
    expect(cancel).toMatch(/Subject: (Cancelled:|=\?UTF-8\?[QB]\?Cancelled)/i);
    // same event UID in both, so Outlook removes the original
    const uid = (t) => t.replace(/=\r\n/g, '').match(/UID:([^\r\n]+)/)[1];
    expect(uid(cancel)).toBe(uid(invite));
  });

  it('a missing INVITE_ADDRESSES marks the booking as failed but keeps it', async () => {
    const ctx = testContext({ env: { SYNC_MODE: 'email' }, logger: quiet });
    open.push(ctx);
    await request(createApp(ctx)).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();
    const b = ctx.store.getBooking(1);
    expect(b.status).toBe('confirmed');
    expect(b.syncStatus).toBe('failed');
    expect(b.syncError).toMatch(/INVITE_ADDRESSES/);
  });
});

describe('SYNC_MODE=graph (against the mock Graph server)', () => {
  async function graphSetup() {
    const mock = createMockGraph({ services: servicesFromCatalog(testCatalog()) });
    const server = mock.app.listen(0);
    await new Promise((r) => server.once('listening', r));
    const port = server.address().port;
    open.push({ close: () => new Promise((r) => server.close(r)) });
    const ctx = testContext({
      env: { SYNC_MODE: 'graph', BOOKINGS_BUSINESS_ID: mock.businessId, GRAPH_BASE_URL: `http://127.0.0.1:${port}/v1.0` },
      logger: quiet,
    });
    open.push(ctx);
    return { mock, ctx, app: createApp(ctx) };
  }

  it('creates an appointment, stores its id, and cancels it', async () => {
    const { mock, ctx, app } = await graphSetup();
    const created = await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();

    const booking = ctx.store.getBooking(1);
    expect(booking.syncStatus).toBe('synced');
    expect(booking.externalId).toMatch(/^AAMkMock/);
    const appt = mock.state.appointments.get(booking.externalId);
    expect(appt.serviceId).toBe('mock-service-medical-emergency');
    expect(appt.startDateTime.dateTime).toBe('2027-08-02T23:15:00.0000000Z'); // 09:15 AEST
    expect(appt.customers[0].emailAddress).toBe('sam@example.com');
    expect(appt.serviceNotes).toContain('Riverbend Primary School');

    await request(app).post(`/api/manage/${created.body.manageToken}/cancel`).expect(200);
    await ctx.sync.idle();
    expect(mock.state.appointments.get(booking.externalId).isCancelled).toBe(true);
    expect(ctx.store.getBooking(1).syncStatus).toBe('synced');
  });

  it('imports appointments made directly in Bookings, and they block the clash engine', async () => {
    const { mock, ctx, app } = await graphSetup();
    // our own booking — must not be imported back as "external"
    await request(app).post('/api/bookings').send(bookingForm({ programId: '3d-smart-tags', date: S2_WEDNESDAY, classes: 1 })).expect(201);
    await ctx.sync.idle();
    // someone books Medical Emergency directly in Microsoft Bookings
    mock.addDirectAppointment({ serviceId: 'mock-service-medical-emergency', date: S2_TUESDAY, start: '09:15', end: '14:45', customerName: 'Phone booking' });

    const result = await ctx.sync.runOnce();
    expect(result.imported).toBe(1);
    const busy = ctx.store.externalBusyOn(S2_TUESDAY);
    expect(busy).toHaveLength(1);
    expect(busy[0]).toMatchObject({ programId: 'medical-emergency', start: '09:15', end: '14:45', staff: 2 });
    expect(busy[0].resourceIds).toEqual(expect.arrayContaining(['drone-room', 'pink-room']));

    // Clean Energy can't run alongside it; Merch Lab... still fine room-wise
    const avail = await request(app).get(`/api/programs/clean-energy/availability?from=${S2_TUESDAY}&to=${S2_TUESDAY}`);
    expect(avail.body.days[0].ok).toBe(false);
    const clash = await request(app).post('/api/bookings').send(bookingForm({ programId: 'clean-energy', classes: 1 }));
    expect(clash.status).toBe(409);
  });

  it('a Graph outage marks the booking failed, and the retry job fixes it', async () => {
    const { mock, ctx, app } = await graphSetup();
    mock.state.failNext = 10;
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();
    expect(ctx.store.getBooking(1).syncStatus).toBe('failed');
    expect(ctx.store.getBooking(1).syncError).toMatch(/503/);
    expect(ctx.store.getBooking(1).status).toBe('confirmed'); // the booking itself is never undone

    mock.state.failNext = 0;
    const result = await ctx.sync.runOnce();
    expect(result.synced).toBe(1);
    expect(ctx.store.getBooking(1).syncStatus).toBe('synced');
    expect(mock.state.appointments.size).toBe(1);
  });

  it('a program with no matching Bookings service fails with a helpful message', async () => {
    const mock = createMockGraph({ services: [] });
    const server = mock.app.listen(0);
    await new Promise((r) => server.once('listening', r));
    open.push({ close: () => new Promise((r) => server.close(r)) });
    const ctx = testContext({
      env: { SYNC_MODE: 'graph', BOOKINGS_BUSINESS_ID: mock.businessId, GRAPH_BASE_URL: `http://127.0.0.1:${server.address().port}/v1.0` },
      logger: quiet,
    });
    open.push(ctx);
    await request(createApp(ctx)).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();
    expect(ctx.store.getBooking(1).syncError).toMatch(/isn't linked to a Microsoft Bookings service.*graph:check/);
  });
});

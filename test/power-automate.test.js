import { describe, it, expect, afterEach } from 'vitest';
import request from 'supertest';
import express from 'express';
import { createApp } from '../src/app.js';
import { toLocal } from '../src/routes/integrations.js';
import { testContext, bookingForm, S2_TUESDAY } from './helpers.js';

const quiet = { warn() {}, log() {} };
const open = [];
afterEach(async () => {
  while (open.length) await open.pop().close();
});

/** A stand-in for a Power Automate "When an HTTP request is received" flow. */
async function fakeFlow({ status = 200, reply = null } = {}) {
  const received = [];
  const app = express();
  app.use(express.json());
  const state = { status, reply };
  app.post('/flow', (req, res) => {
    received.push(req.body);
    if (state.reply) res.status(state.status).json(state.reply);
    else res.status(state.status).end();
  });
  const server = app.listen(0);
  await new Promise((r) => server.once('listening', r));
  open.push({ close: () => new Promise((r) => server.close(r)) });
  return { url: `http://127.0.0.1:${server.address().port}/flow`, received, state };
}

describe('Power Automate: website → flow (SYNC_MODE=webhook)', () => {
  it('posts created and cancelled events with everything a flow needs', async () => {
    const flow = await fakeFlow({ reply: { externalId: 'outlook-event-123' } });
    const ctx = testContext({ env: { SYNC_MODE: 'webhook', POWER_AUTOMATE_WEBHOOK_URL: flow.url }, logger: quiet });
    open.push(ctx);
    const app = createApp(ctx);

    const created = await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();
    expect(flow.received).toHaveLength(1);
    const p = flow.received[0];
    expect(p).toMatchObject({
      event: 'booking.created',
      reference: 'PB-00001',
      programName: 'Medical Emergency',
      date: S2_TUESDAY,
      startLocal: `${S2_TUESDAY}T09:15:00`,
      endLocal: `${S2_TUESDAY}T14:45:00`,
      startUtc: '2027-08-02T23:15:00.000Z',
      windowsTimeZone: 'AUS Eastern Standard Time',
      school: 'Riverbend Primary School',
      classes: 2,
      roomsText: 'Drone Room, Pink Room, Drones, Dobots',
    });
    expect(p.subject).toMatch(/\[PB-00001\]$/);
    expect(p.manageUrl).toMatch(/^https:\/\/bookings\.example\.org\/manage\//);
    const booking = ctx.store.getBooking(1);
    expect(booking.syncStatus).toBe('synced');
    expect(booking.externalId).toBe('outlook-event-123');

    await request(app).post(`/api/manage/${created.body.manageToken}/cancel`).expect(200);
    await ctx.sync.idle();
    expect(flow.received[1]).toMatchObject({ event: 'booking.cancelled', reference: 'PB-00001', status: 'cancelled', externalId: 'outlook-event-123' });
  });

  it('a failing flow marks the booking failed; the retry job resends it', async () => {
    const flow = await fakeFlow({ status: 500 });
    const ctx = testContext({ env: { SYNC_MODE: 'webhook', POWER_AUTOMATE_WEBHOOK_URL: flow.url }, logger: quiet });
    open.push(ctx);
    await request(createApp(ctx)).post('/api/bookings').send(bookingForm()).expect(201);
    await ctx.sync.idle();
    expect(ctx.store.getBooking(1)).toMatchObject({ status: 'confirmed', syncStatus: 'failed' });
    expect(ctx.store.getBooking(1).syncError).toMatch(/returned 500/);

    flow.state.status = 202;
    const result = await ctx.sync.runOnce();
    expect(result.synced).toBe(1);
    expect(ctx.store.getBooking(1).syncStatus).toBe('synced');
  });

  it('admin can send a test event to the flow', async () => {
    const flow = await fakeFlow();
    const ctx = testContext({ env: { POWER_AUTOMATE_WEBHOOK_URL: flow.url } });
    open.push(ctx);
    const agent = request.agent(createApp(ctx));
    await agent.post('/admin/api/login').send({ password: 'test-password' }).expect(200);
    await agent.post('/admin/api/sync/test-webhook').send({}).expect(200);
    expect(flow.received[0].event).toBe('booking.test');
    const sample = await agent.get('/admin/api/sync/sample-payload').expect(200);
    expect(sample.body.subject).toBeTruthy();
  });
});

describe('Power Automate: Microsoft Bookings → website (inbound)', () => {
  function setup(env = { INBOUND_WEBHOOK_SECRET: 'flow-secret' }) {
    const ctx = testContext({ env });
    open.push(ctx);
    return { ctx, app: createApp(ctx) };
  }
  const appointment = {
    action: 'created',
    appointmentId: 'AAMk-bookings-1',
    serviceName: 'Medical Emergency',
    start: '2027-08-02T23:15:00Z', // 09:15 Melbourne on S2_TUESDAY
    end: '2027-08-03T04:45:00Z',
    customerName: 'Phone booking',
  };

  it('is off without INBOUND_WEBHOOK_SECRET and needs the right secret', async () => {
    const off = setup({});
    await request(off.app).post('/api/integrations/power-automate').send(appointment).expect(404);
    const { app } = setup();
    await request(app).post('/api/integrations/power-automate').send(appointment).expect(401);
    await request(app).post('/api/integrations/power-automate').set('Authorization', 'Bearer nope').send(appointment).expect(401);
  });

  it('an appointment made in Bookings blocks rooms and combination rules; cancelling frees them', async () => {
    const { ctx, app } = setup();
    const res = await request(app)
      .post('/api/integrations/power-automate')
      .set('Authorization', 'Bearer flow-secret')
      .send(appointment)
      .expect(200);
    expect(res.body).toMatchObject({ ok: true, linkedProgram: 'Medical Emergency', date: S2_TUESDAY, start: '09:15', end: '14:45' });
    expect(res.body.holds).toEqual(expect.arrayContaining(['drone-room', 'pink-room', 'drones', 'dobots']));

    // Clean Energy can't run alongside Medical Emergency → blocked on the website
    const blocked = await request(app).post('/api/bookings').send(bookingForm({ programId: 'clean-energy', classes: 1 }));
    expect(blocked.status).toBe(409);

    // the same appointment sent again (e.g. "updated") replaces, never duplicates
    await request(app).post('/api/integrations/power-automate').set('x-webhook-secret', 'flow-secret').send({ ...appointment, action: 'updated' }).expect(200);
    expect(ctx.store.externalBusyOn(S2_TUESDAY)).toHaveLength(1);

    await request(app)
      .post('/api/integrations/power-automate')
      .set('Authorization', 'Bearer flow-secret')
      .send({ action: 'cancelled', appointmentId: 'AAMk-bookings-1' })
      .expect(200);
    expect(ctx.store.externalBusyOn(S2_TUESDAY)).toHaveLength(0);
    await request(app).post('/api/bookings').send(bookingForm({ programId: 'clean-energy', classes: 1 })).expect(201);
  });

  it('unknown services are saved but block nothing, with a warning', async () => {
    const { app } = setup();
    const res = await request(app)
      .post('/api/integrations/power-automate')
      .set('Authorization', 'Bearer flow-secret')
      .send({ ...appointment, serviceName: 'Teacher PD session' })
      .expect(200);
    expect(res.body.linkedProgram).toBeNull();
    expect(res.body.warning).toMatch(/No program matches/);
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
  });

  it('rejects missing ids and unreadable times', async () => {
    const { app } = setup();
    const send = (body) => request(app).post('/api/integrations/power-automate').set('Authorization', 'Bearer flow-secret').send(body);
    await send({ ...appointment, appointmentId: undefined }).expect(400);
    await send({ ...appointment, start: 'next tuesday' }).expect(400);
  });

  it('understands the different time formats flows send', () => {
    const tz = 'Australia/Melbourne';
    expect(toLocal('2027-08-02T23:15:00Z', null, tz)).toEqual({ date: '2027-08-03', time: '09:15' });
    expect(toLocal('2027-08-03T09:15:00+10:00', null, tz)).toEqual({ date: '2027-08-03', time: '09:15' });
    expect(toLocal('2027-08-02T23:15:00.0000000', 'UTC', tz)).toEqual({ date: '2027-08-03', time: '09:15' });
    expect(toLocal({ dateTime: '2027-08-02T23:15:00.0000000', timeZone: 'UTC' }, null, tz)).toEqual({ date: '2027-08-03', time: '09:15' });
    expect(toLocal('2027-08-03T09:15:00', 'AUS Eastern Standard Time', tz)).toEqual({ date: '2027-08-03', time: '09:15' });
    expect(toLocal('2027-08-03T09:15:00', null, tz)).toEqual({ date: '2027-08-03', time: '09:15' });
  });
});

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { seedDemo } from '../src/seed.js';
import { testContext, bookingForm, loginAs, S2_TUESDAY } from './helpers.js';

let ctx;
let app;
beforeEach(() => {
  ctx = testContext({ env: { DEMO_MODE: 'true' } });
  app = createApp(ctx);
});
afterEach(() => ctx.close());

const login = (role = 'manager') => loginAs(app, ctx, role);

describe('admin', () => {
  it('admin API routes reject requests without login', async () => {
    for (const path of ['/admin/api/me', '/admin/api/board', '/admin/api/bookings', '/admin/api/bookings.csv', '/admin/api/catalog', '/admin/api/sync']) {
      const res = await request(app).get(path);
      expect(res.status, path).toBe(401);
    }
    await request(app).post('/admin/api/demo/reset').send({}).expect(401);
    await request(app).post('/admin/api/bookings/1/cancel').send({}).expect(401);
  });

  it('admin pages show the login form until logged in', async () => {
    const res = await request(app).get('/admin');
    expect(res.text).toContain('Staff login');
  });

  it('a forged session cookie is refused', async () => {
    await request(app).get('/admin/api/me').set('Cookie', 'admin_session=forged-token').expect(401);
  });

  it('logged-in admin sees the board, full reasons, CSV and can cancel', async () => {
    const agent = await login();
    const created = await request(app).post('/api/bookings').send(bookingForm()).expect(201);

    const board = await agent.get(`/admin/api/board?date=${S2_TUESDAY}`).expect(200);
    expect(board.body.bookings).toHaveLength(1);
    expect(board.body.columns[0]).toMatchObject({ staffUsed: 2, staffPool: 4 });

    const test = await agent.post('/admin/api/rule-test').send({ programId: 'clean-energy', date: S2_TUESDAY, classes: 1 }).expect(200);
    expect(test.body.ok).toBe(false);
    expect(test.body.reasons[0].message).toMatch(/Can't run alongside Medical Emergency \(booking #1, Riverbend Primary School\)/);

    const csv = await agent.get('/admin/api/bookings.csv').expect(200);
    expect(csv.text).toContain('Riverbend Primary School');
    expect(csv.headers['content-type']).toMatch(/text\/csv/);

    const list = await agent.get('/admin/api/bookings?q=medical').expect(200);
    expect(list.body.bookings).toHaveLength(1);
    const id = list.body.bookings[0].id;
    expect(list.body.bookings[0].manageToken).toBeUndefined();

    // state-changing admin calls must be JSON
    await agent.post(`/admin/api/bookings/${id}/cancel`).type('form').send('x=1').expect(415);
    const cancelled = await agent.post(`/admin/api/bookings/${id}/cancel`).send({}).expect(200);
    expect(cancelled.body.booking.status).toBe('cancelled');
    const view = await request(app).get(`/api/manage/${created.body.manageToken}`);
    expect(view.body.booking.status).toBe('cancelled');
  });

  it('demo seed loads clash scenarios that all pass the rules', () => {
    ctx = testContext({ today: '2027-07-30' }); // a Friday in Semester 2
    const { created, skipped } = seedDemo(ctx);
    expect(skipped).toEqual([]);
    expect(created.length).toBeGreaterThanOrEqual(12);
    const me = created.find((b) => b.programId === 'medical-emergency');
    // Clean Energy is blocked on the Medical Emergency day; Creative TechStyles is allowed
    expect(ctx.bookings.check({ programId: 'clean-energy', date: me.date, slotId: 'full', classes: 1 }).ok).toBe(false);
    expect(ctx.bookings.check({ programId: 'creative-techstyles', date: me.date, slotId: 'full', classes: 1 }).ok).toBe(true);
  });
});

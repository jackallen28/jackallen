import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import request from 'supertest';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createApp } from '../src/app.js';
import { testContext, bookingForm, tempDir, S2_TUESDAY } from './helpers.js';

let ctx;
let app;
beforeEach(() => {
  ctx = testContext();
  app = createApp(ctx);
});
afterEach(() => ctx.close());

describe('public booking API', () => {
  it('health check', async () => {
    const res = await request(app).get('/healthz');
    expect(res.body).toEqual({ ok: true });
  });

  it('lists programs without staff-only notes', async () => {
    const res = await request(app).get('/api/catalog');
    expect(res.status).toBe(200);
    const me = res.body.programs.find((p) => p.id === 'medical-emergency');
    expect(me).toMatchObject({ name: 'Medical Emergency', maxClasses: 2, maxStudents: 50 });
    expect(me.rooms).toEqual(['Drone Room', 'Pink Room']);
    expect(me.notes).toBeUndefined();
  });

  it('create → view → cancel flow, with availability updating', async () => {
    const created = await request(app).post('/api/bookings').send(bookingForm());
    expect(created.status).toBe(201);
    expect(created.body.booking).toMatchObject({ programName: 'Medical Emergency', classes: 2, students: 50, status: 'confirmed' });
    expect(created.body.booking.reference).toMatch(/^PB-\d{5}$/);
    const token = created.body.manageToken;
    expect(token.length).toBeGreaterThan(20);

    // Clean Energy is now unavailable that day, with the generic public wording only.
    const avail = await request(app).get(`/api/programs/clean-energy/availability?from=${S2_TUESDAY}&to=${S2_TUESDAY}`);
    expect(avail.body.days[0].ok).toBe(false);
    expect(avail.body.days[0].reasons.map((r) => r.type)).toContain('combination');
    expect(JSON.stringify(avail.body)).not.toMatch(/Riverbend/);

    const view = await request(app).get(`/api/manage/${token}`);
    expect(view.status).toBe(200);
    expect(view.body.booking.school).toBe('Riverbend Primary School');

    const cancelled = await request(app).post(`/api/manage/${token}/cancel`);
    expect(cancelled.body.booking.status).toBe('cancelled');

    const after = await request(app).get(`/api/programs/clean-energy/availability?from=${S2_TUESDAY}&to=${S2_TUESDAY}`);
    expect(after.body.days[0].ok).toBe(true);
  });

  it('rejects an invalid form with field messages', async () => {
    const res = await request(app).post('/api/bookings').send(bookingForm({ email: 'not-an-email', school: '' }));
    expect(res.status).toBe(400);
    expect(res.body.fields.email).toMatch(/valid email/);
    expect(res.body.fields.school).toBeTruthy();
  });

  it('rejects too many classes and clashing bookings with 409', async () => {
    const tooMany = await request(app).post('/api/bookings').send(bookingForm({ classes: 3 }));
    expect(tooMany.status).toBe(409);
    expect(tooMany.body.reasons[0]).toEqual({ type: 'size', message: 'Maximum 2 classes' });

    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    const clash = await request(app).post('/api/bookings').send(bookingForm({ programId: 'clean-energy' }));
    expect(clash.status).toBe(409);
    expect(clash.body.error).toMatch(/no longer available/);
  });

  it('refuses past dates', async () => {
    const res = await request(app).post('/api/bookings').send(bookingForm({ date: '2027-07-13' }));
    expect(res.status).toBe(409);
    expect(res.body.reasons[0].message).toBe('This date has passed');
  });

  it('20 simultaneous bookings for the same clashing slot → exactly 1 succeeds', async () => {
    const server = app.listen(0);
    try {
      const attempts = Array.from({ length: 20 }, (_, i) =>
        request(server)
          .post('/api/bookings')
          .send(bookingForm({ programId: 'mff-circular-fashion', classes: 1, school: `School ${i}` })),
      );
      const results = await Promise.all(attempts);
      const statuses = results.map((r) => r.status);
      expect(statuses.filter((s) => s === 201)).toHaveLength(1);
      expect(statuses.filter((s) => s === 409)).toHaveLength(19);
      expect(ctx.store.activeBookingsOn(S2_TUESDAY)).toHaveLength(1);
    } finally {
      server.close();
    }
  });

  it('manage links only work with the right token', async () => {
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    await request(app).get('/api/manage/wrong-token').expect(404);
    await request(app).post('/api/manage/wrong-token/cancel').expect(404);
  });

  it('booking .ics download is a valid calendar file', async () => {
    const created = await request(app).post('/api/bookings').send(bookingForm());
    const res = await request(app).get(`/api/manage/${created.body.manageToken}/booking.ics`);
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/text\/calendar/);
    expect(res.text).toMatch(/^BEGIN:VCALENDAR\r\n/);
    // 09:15 Melbourne time in August (AEST, UTC+10) = 23:15 UTC the day before
    expect(res.text).toContain('DTSTART:20270802T231500Z');
    expect(res.text).toContain('DTEND:20270803T044500Z');
  });
});

describe('startup', () => {
  it('a catalog with an unknown room stops the server with a clear message', () => {
    const dir = tempDir();
    const bad = fs.readFileSync('config/catalog.yaml', 'utf8').replace('- [igloo]', '- [igloo-typo]');
    const file = path.join(dir, 'catalog.yaml');
    fs.writeFileSync(file, bad);
    const result = spawnSync(process.execPath, ['src/server.js'], {
      env: { ...process.env, CATALOG_PATH: file, DATA_DIR: dir, PORT: '0' },
      encoding: 'utf8',
      timeout: 15000,
    });
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/Could not start/);
    expect(result.stderr).toMatch(/unknown room\/equipment "igloo-typo"/);
  });
});

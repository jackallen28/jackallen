import { describe, it, expect, afterEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { loadConfig } from '../src/config.js';
import { testContext, testUser, loginAs, bookingForm } from './helpers.js';
import { codeAt, currentCounter, verifyCode, base32Encode, base32Decode } from '../src/security/totp.js';
import { hashPassword, verifyPassword } from '../src/security/passwords.js';
import { resetTwoFactor, setDisabled, logoutAll } from '../src/security/users.js';
import { ipMatcher } from '../src/security/headers.js';

const open = [];
afterEach(() => {
  while (open.length) open.pop().close();
});
function setup(env = {}) {
  const ctx = testContext({ env });
  open.push(ctx);
  return { ctx, app: createApp(ctx) };
}
const login = (app, body) => request(app).post('/admin/api/login').send(body);

describe('building blocks', () => {
  it('authenticator codes match the RFC 6238 test vector', () => {
    // RFC 6238 appendix B: secret "12345678901234567890", T = 59s → 94287082 (8 digits) → last 6 = 287082
    const secret = base32Encode(Buffer.from('12345678901234567890'));
    expect(codeAt(secret, Math.floor(59 / 30))).toBe('287082');
    expect(base32Decode(secret).toString()).toBe('12345678901234567890');
  });

  it('codes are accepted once, with one step of clock drift, and never replayed', () => {
    const secret = base32Encode(Buffer.from('12345678901234567890'));
    const now = 1_700_000_000_000;
    const counter = currentCounter(now);
    expect(verifyCode(secret, codeAt(secret, counter), { now })).toBe(counter);
    expect(verifyCode(secret, codeAt(secret, counter - 1), { now })).toBe(counter - 1);
    expect(verifyCode(secret, codeAt(secret, counter - 3), { now })).toBeNull();
    expect(verifyCode(secret, codeAt(secret, counter), { now, lastCounter: counter })).toBeNull();
    expect(verifyCode(secret, 'abcdef', { now })).toBeNull();
  });

  it('passwords are stored as salted scrypt hashes', async () => {
    const hash = await hashPassword('a long enough password');
    expect(hash).toMatch(/^scrypt\$/);
    expect(hash).not.toContain('a long enough password');
    expect(await verifyPassword('a long enough password', hash)).toBe(true);
    expect(await verifyPassword('wrong', hash)).toBe(false);
    expect(await hashPassword('a long enough password')).not.toBe(hash); // different salt each time
  });

  it('IP allow-list matches single addresses and IPv4 ranges', () => {
    const allowed = ipMatcher(['203.0.113.10', '10.20.0.0/16', '2001:db8::1']);
    expect(allowed('203.0.113.10')).toBe(true);
    expect(allowed('::ffff:203.0.113.10')).toBe(true);
    expect(allowed('10.20.5.9')).toBe(true);
    expect(allowed('10.21.0.1')).toBe(false);
    expect(allowed('2001:db8::1')).toBe(true);
    expect(allowed('198.51.100.1')).toBe(false);
  });
});

describe('staff login (ADMIN_ACCESS=accounts)', () => {
  it('needs email, password AND the current authenticator code', async () => {
    const { ctx, app } = setup();
    const u = await testUser(ctx);
    await login(app, { email: u.email, password: u.password }).expect(401);
    await login(app, { email: u.email, password: u.password, code: '000000' }).expect(401);
    await login(app, { email: u.email, password: 'wrong password!!', code: u.code() }).expect(401);
    await login(app, { email: 'nobody@example.org', password: u.password, code: u.code() }).expect(401);
    const ok = await login(app, { email: u.email.toUpperCase(), password: u.password, code: u.code() }).expect(200);
    const cookie = ok.headers['set-cookie'][0];
    expect(cookie).toMatch(/HttpOnly/);
    expect(cookie).toMatch(/SameSite=Strict/);
    // the same code can't be used again (replay)
    await login(app, { email: u.email, password: u.password, code: u.code() }).expect(401);
  });

  it('the old shared password does nothing in accounts mode', async () => {
    const { app } = setup({ ADMIN_PASSWORD: 'shared-secret' });
    await login(app, { password: 'shared-secret' }).expect(401);
  });

  it('locks an account for 15 minutes after 5 wrong attempts', async () => {
    const { ctx, app } = setup();
    const u = await testUser(ctx);
    for (let i = 0; i < 4; i++) await login(app, { email: u.email, password: 'wrong password!!', code: '123456' }).expect(401);
    const fifth = await login(app, { email: u.email, password: 'wrong password!!', code: '123456' }).expect(401);
    expect(fifth.body.error).toMatch(/locked/);
    const correct = await login(app, { email: u.email, password: u.password, code: u.code() }).expect(401);
    expect(correct.body.error).toMatch(/locked/);
    expect(ctx.store.recentAudit(10).some((a) => a.action === 'admin.account_locked' && a.actor === u.email)).toBe(true);
  });

  it('limits login attempts per IP address', async () => {
    const { app } = setup();
    for (let i = 0; i < 10; i++) await login(app, { email: `x${i}@example.org`, password: 'nope', code: '1' });
    await login(app, { email: 'y@example.org', password: 'nope', code: '1' }).expect(429);
  });

  it('viewers can look but not change anything', async () => {
    const { ctx, app } = setup({ DEMO_MODE: 'true' });
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    const viewer = await loginAs(app, ctx, 'viewer');
    const me = await viewer.get('/admin/api/me').expect(200);
    expect(me.body.user.role).toBe('viewer');
    await viewer.get('/admin/api/bookings').expect(200);
    await viewer.post('/admin/api/rule-test').send({ programId: 'clean-energy', date: '2027-08-03' }).expect(200);
    await viewer.post('/admin/api/bookings/1/cancel').send({}).expect(403);
    await viewer.post('/admin/api/demo/reset').send({}).expect(403);
    await viewer.post('/admin/api/sync/run').send({}).expect(403);
    expect(ctx.store.getBooking(1).status).toBe('confirmed');
  });

  it('cancellations record which staff member did it', async () => {
    const { ctx, app } = setup();
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
    const agent = await loginAs(app, ctx, 'manager');
    const who = (await agent.get('/admin/api/me')).body.user.email;
    await agent.post('/admin/api/bookings/1/cancel').send({}).expect(200);
    const entry = ctx.store.recentAudit(5).find((a) => a.action === 'booking.cancelled');
    expect(entry.actor).toBe(who);
  });

  it('sessions end on logout, when disabled, after a 2FA reset, or when revoked from the command line', async () => {
    const { ctx, app } = setup();
    const check = (agent) => agent.get('/admin/api/me');

    const a = await loginAs(app, ctx);
    await check(a).expect(200);
    await a.post('/admin/api/logout').expect(200);
    await check(a).expect(401);

    const b = await loginAs(app, ctx);
    const bEmail = (await check(b)).body.user.email;
    setDisabled(ctx.store, bEmail, true);
    await check(b).expect(401);

    const c = await loginAs(app, ctx);
    resetTwoFactor(ctx.store, (await check(c)).body.user.email);
    await check(c).expect(401);

    const d = await loginAs(app, ctx);
    logoutAll(ctx.store);
    await check(d).expect(401);
  });

  it('the login page explains how to create the first account', async () => {
    const { app } = setup();
    const res = await request(app).get('/admin/api/login-options').expect(200);
    expect(res.body).toEqual({ mode: 'accounts', hasAccounts: false });
  });
});

describe('ADMIN_ACCESS=off and the IP allow-list', () => {
  it('off: every admin URL is a plain 404 — there is no login to attack', async () => {
    const { ctx, app } = setup({ ADMIN_ACCESS: 'off' });
    await testUser(ctx); // even with accounts in the database
    for (const path of ['/admin', '/admin/bookings', '/admin/api/me', '/admin/api/login-options']) {
      await request(app).get(path).expect(404);
    }
    await request(app).post('/admin/api/login').send({}).expect(404);
    // the public site still works
    await request(app).post('/api/bookings').send(bookingForm()).expect(201);
  });

  it('allow-list: other IP addresses get a 404 for /admin', async () => {
    const { ctx, app } = setup({ ADMIN_ALLOWED_IPS: '203.0.113.0/24' });
    const u = await testUser(ctx);
    await request(app).get('/admin').set('X-Forwarded-For', '198.51.100.7').expect(404);
    await login(app, { email: u.email, password: u.password, code: u.code() }).set('X-Forwarded-For', '198.51.100.7').expect(404);
    await request(app).get('/admin').set('X-Forwarded-For', '203.0.113.50').expect(200);
    await login(app, { email: u.email, password: u.password, code: u.code() }).set('X-Forwarded-For', '203.0.113.50').expect(200);
  });

  it('shared-password mode is refused unless DEMO_MODE=true', () => {
    expect(() => loadConfig({ ADMIN_ACCESS: 'password', DEMO_MODE: 'false' })).toThrow(/only allowed with DEMO_MODE=true/);
    expect(loadConfig({ ADMIN_ACCESS: 'password', DEMO_MODE: 'true' }).adminAccess).toBe('password');
  });
});

describe('web protections', () => {
  it('sends security headers', async () => {
    const { app } = setup();
    const res = await request(app).get('/');
    expect(res.headers['content-security-policy']).toMatch(/script-src 'self'/);
    expect(res.headers['content-security-policy']).toMatch(/frame-ancestors 'none'/);
    expect(res.headers['x-frame-options']).toBe('DENY');
    expect(res.headers['x-content-type-options']).toBe('nosniff');
  });

  it('rate-limits floods of booking attempts from one address', async () => {
    const { app } = setup();
    const results = [];
    for (let i = 0; i < 61; i++) {
      results.push((await request(app).post('/api/bookings').set('X-Forwarded-For', '198.51.100.9').send({})).status);
    }
    expect(results.slice(0, 60).every((s) => s === 400)).toBe(true);
    expect(results[60]).toBe(429);
  });
});

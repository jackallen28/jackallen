// Shared set-up for the API and sync tests.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import YAML from 'yaml';
import { loadConfig } from '../src/config.js';
import { buildCatalog } from '../src/catalog/load.js';
import { createContext } from '../src/context.js';
import request from 'supertest';
import { createUser } from '../src/security/users.js';
import { codeAt, currentCounter } from '../src/security/totp.js';

export const S2_TUESDAY = '2027-08-03';
export const S2_WEDNESDAY = '2027-08-04';
export const TEST_TODAY = '2027-07-20';

/** The real catalog, with semester dates / staff pool pinned so tests don't depend on them. */
export function testCatalog({ staffPool = 4 } = {}) {
  const raw = YAML.parse(fs.readFileSync(path.resolve('config/catalog.yaml'), 'utf8'));
  raw.settings.semesters = {
    S1: [{ from: '2027-01-28', to: '2027-06-25' }],
    S2: [{ from: '2027-07-13', to: '2027-12-17' }],
  };
  raw.settings.staff_pool.size = staffPool;
  raw.settings.blackouts = [];
  return buildCatalog(raw, 'test-catalog');
}

export function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'bookings-test-'));
}

export function testConfig(env = {}) {
  return loadConfig({
    DATA_DIR: tempDir(),
    ADMIN_PASSWORD: 'test-password',
    CALENDAR_FEED_TOKEN: 'test-feed-token',
    SYNC_MODE: 'none',
    DEMO_MODE: 'false',
    PUBLIC_URL: 'https://bookings.example.org',
    ...env,
  });
}

export function testContext({ env = {}, staffPool = 4, today = TEST_TODAY, ...overrides } = {}) {
  const config = testConfig(env);
  return createContext(config, {
    catalog: testCatalog({ staffPool }),
    dbFile: ':memory:',
    today: () => today,
    ...overrides,
  });
}

export function bookingForm(overrides = {}) {
  return {
    programId: 'medical-emergency',
    date: S2_TUESDAY,
    slotId: 'full',
    classes: 2,
    school: 'Riverbend Primary School',
    contactName: 'Sam Teacher',
    email: 'sam@example.com',
    phone: '03 9000 0000',
    yearLevel: 'Year 6',
    notes: 'Two Year 6 classes',
    ...overrides,
  };
}

// ---- staff accounts ----------------------------------------------------------------

let userCount = 0;
export const TEST_PASSWORD = 'correct horse battery staple';

/** Creates a staff account and returns its details (including the authenticator secret). */
export async function testUser(ctx, role = 'manager') {
  const email = `staff${++userCount}@example.org`;
  const { totpSecret } = await createUser(ctx.store, { email, name: `Staff ${userCount}`, role, password: TEST_PASSWORD });
  return { email, password: TEST_PASSWORD, secret: totpSecret, code: () => codeAt(totpSecret, currentCounter()) };
}

/** A supertest agent logged in as a new staff member. */
export async function loginAs(app, ctx, role = 'manager') {
  const user = await testUser(ctx, role);
  const agent = request.agent(app);
  await agent.post('/admin/api/login').send({ email: user.email, password: user.password, code: user.code() }).expect(200);
  return agent;
}

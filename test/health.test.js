import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';

describe('health check', () => {
  it('GET /healthz returns ok', async () => {
    const res = await request(createApp()).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ok: true });
  });
});

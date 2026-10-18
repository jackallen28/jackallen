// Outlook / Google / Apple calendar subscription feeds — always on, no IT admin access needed.
//   /calendar/<CALENDAR_FEED_TOKEN>/all.ics                 every booking
//   /calendar/<CALENDAR_FEED_TOKEN>/room/<resource-id>.ics  one room or kit
// In Outlook: Add calendar → Subscribe from web → paste the link.

import crypto from 'node:crypto';
import express from 'express';
import { feedIcs } from '../ics.js';
import { addDays } from '../engine/dates.js';

const PAST_DAYS = 60; // keep recent history visible in the subscribed calendar

function tokenMatches(config, token) {
  const expected = config.calendarFeedToken;
  if (!expected || expected.startsWith('change-me')) return false; // feeds off until a real token is set
  const a = crypto.createHash('sha256').update(String(token)).digest();
  const b = crypto.createHash('sha256').update(expected).digest();
  return crypto.timingSafeEqual(a, b);
}

export function calendarRoutes(ctx) {
  const { config, catalog, store } = ctx;
  const router = express.Router();

  function send(res, bookings, name) {
    res
      .type('text/calendar; charset=utf-8')
      .set('Cache-Control', 'no-cache')
      .send(feedIcs(ctx, bookings, name));
  }

  router.get('/calendar/:token/all.ics', (req, res) => {
    if (!tokenMatches(config, req.params.token)) return res.status(404).send('Not found');
    const bookings = store.listBookings({ from: addDays(ctx.today(), -PAST_DAYS), status: 'confirmed', limit: 5000 });
    send(res, bookings, 'Program bookings');
  });

  router.get('/calendar/:token/room/:file', (req, res) => {
    if (!tokenMatches(config, req.params.token)) return res.status(404).send('Not found');
    const resourceId = req.params.file.replace(/\.ics$/, '');
    const resource = catalog.index.resources[resourceId];
    if (!resource) return res.status(404).send('Unknown room or equipment');
    const bookings = store
      .listBookings({ from: addDays(ctx.today(), -PAST_DAYS), status: 'confirmed', limit: 5000 })
      .filter((b) => b.assignedResources.includes(resourceId));
    send(res, bookings, `Program bookings – ${resource.name}`);
  });

  return router;
}

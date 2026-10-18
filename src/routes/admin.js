// Admin area: /admin pages and the /admin/api JSON endpoints behind them.

import path from 'node:path';
import express from 'express';
import { ROOT_DIR } from '../config.js';
import { checkPassword, isLoggedIn, setLoginCookie, clearLoginCookie, requireAdmin } from '../auth.js';
import { bookingReference } from '../bookings.js';
import { addDays, isValidDate, weekday, slotWindow, overlaps, toMinutes } from '../engine/dates.js';
import {
  resourceName,
  describeRequirement,
  describeCombinationRules,
  semesterLabel,
  programRooms,
} from '../catalog/describe.js';
import { seedDemo } from '../seed.js';

const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const ADMIN_PAGES = ['', 'bookings', 'rules', 'catalog', 'sync'];

/** Full booking details for staff. */
export function adminBookingView(catalog, b) {
  const program = catalog.index.programs[b.programId];
  const slot = catalog.index.slots[b.slotId];
  return {
    ...b,
    manageToken: undefined,
    reference: bookingReference(b.id),
    programName: program?.name || `${b.programId} (no longer in catalog)`,
    category: program?.category || null,
    slotLabel: slot ? `${slot.label} ${slot.start}–${slot.end}` : b.slotId,
    resources: b.assignedResources.map((id) => resourceName(catalog, id)),
    staffRequired: program?.staff_required ?? null,
    manageUrl: `/manage/${b.manageToken}`,
  };
}

function csvCell(value) {
  const s = String(value ?? '');
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function adminRoutes(ctx) {
  const { config, catalog, store, bookings } = ctx;
  const router = express.Router();
  const api = express.Router();

  // ---- pages -----------------------------------------------------------------------
  for (const name of ADMIN_PAGES) {
    router.get(`/admin${name ? `/${name}` : ''}`, (req, res) => {
      res.set('Cache-Control', 'no-store');
      res.sendFile(path.join(PUBLIC_DIR, isLoggedIn(config, req) ? 'admin.html' : 'admin-login.html'));
    });
  }

  // ---- login (no session needed) ---------------------------------------------------
  router.post('/admin/api/login', express.json(), (req, res) => {
    if (!checkPassword(config, req.body?.password)) {
      store.audit('admin.login_failed', null, { ip: req.ip });
      return res.status(401).json({ error: 'Wrong password' });
    }
    setLoginCookie(config, req, res);
    res.json({ ok: true });
  });
  router.post('/admin/api/logout', (req, res) => {
    clearLoginCookie(res);
    res.json({ ok: true });
  });

  // Everything below needs a valid admin session.
  router.use('/admin/api', requireAdmin(config), api);

  api.get('/me', (req, res) => {
    res.json({
      demoMode: config.demoMode,
      syncMode: config.syncMode,
      today: ctx.today(),
      staffPool: catalog.settings.staff_pool,
    });
  });

  // ---- day / week board -------------------------------------------------------------
  api.get('/board', (req, res) => {
    const date = isValidDate(req.query.date) ? req.query.date : ctx.today();
    const view = req.query.view === 'week' ? 'week' : 'day';
    let dates = [date];
    if (view === 'week') {
      const monday = addDays(date, -((weekday(date) + 6) % 7));
      dates = [0, 1, 2, 3, 4].map((i) => addDays(monday, i));
    }
    const from = dates[0];
    const to = dates[dates.length - 1];
    const dayBookings = store.activeBookingsBetween(from, to);
    const busy = store.externalBusyBetween(from, to);

    const columns = [];
    for (const d of dates) {
      for (const slot of catalog.settings.slots) {
        const window = slotWindow(catalog, slot.id);
        const inCol = dayBookings.filter((b) => b.date === d && overlaps(slotWindow(catalog, b.slotId), window));
        const busyInCol = busy.filter((x) => x.date === d && overlaps({ start: toMinutes(x.start), end: toMinutes(x.end) }, window));
        const staffUsed =
          inCol.reduce((sum, b) => sum + (catalog.index.programs[b.programId]?.staff_required || 0), 0) +
          busyInCol.reduce((sum, x) => sum + (x.staff || 0), 0);
        columns.push({
          key: `${d}|${slot.id}`,
          date: d,
          slotId: slot.id,
          slotLabel: `${slot.label} ${slot.start}–${slot.end}`,
          staffUsed,
          staffPool: catalog.settings.staff_pool.size,
          bookingIds: inCol.map((b) => b.id),
          busyIds: busyInCol.map((x) => x.id),
        });
      }
    }

    res.json({
      view,
      date,
      dates,
      staffPoolName: catalog.settings.staff_pool.name,
      blackouts: catalog.settings.blackouts.filter((b) => dates.includes(b.date)),
      resources: catalog.resources,
      programs: catalog.programs.map((p) => ({ id: p.id, name: p.name, category: p.category })),
      columns,
      bookings: dayBookings.map((b) => adminBookingView(catalog, b)),
      busy: busy.map((x) => ({
        ...x,
        programName: x.programId ? catalog.index.programs[x.programId]?.name : null,
        resources: x.resourceIds.map((id) => resourceName(catalog, id)),
      })),
    });
  });

  // ---- bookings list -----------------------------------------------------------------
  function filteredBookings(query) {
    let programIds;
    if (query.programId) programIds = [String(query.programId)];
    else if (query.category) programIds = catalog.programs.filter((p) => p.category === query.category).map((p) => p.id);
    const q = String(query.q || '').trim();
    // Searching for a program name finds its bookings too.
    let list = store.listBookings({
      from: isValidDate(query.from) ? query.from : undefined,
      to: isValidDate(query.to) ? query.to : undefined,
      status: ['confirmed', 'cancelled'].includes(query.status) ? query.status : undefined,
      syncStatus: ['none', 'pending', 'synced', 'failed'].includes(query.syncStatus) ? query.syncStatus : undefined,
      programIds,
    });
    if (q) {
      const needle = q.toLowerCase().replace(/^#/, '');
      list = list.filter((b) => {
        const name = catalog.index.programs[b.programId]?.name || b.programId;
        return [b.school, b.contactName, b.email, b.phone, b.notes, b.yearLevel, name, bookingReference(b.id), String(b.id)]
          .some((v) => String(v).toLowerCase().includes(needle));
      });
    }
    return list.map((b) => adminBookingView(catalog, b));
  }

  api.get('/bookings', (req, res) => {
    res.json({ bookings: filteredBookings(req.query) });
  });

  api.get('/bookings.csv', (req, res) => {
    const columns = [
      ['Reference', (b) => b.reference],
      ['Status', (b) => b.status],
      ['Date', (b) => b.date],
      ['Time', (b) => b.slotLabel],
      ['Program', (b) => b.programName],
      ['Classes', (b) => b.classes],
      ['Students', (b) => b.students],
      ['Rooms/equipment', (b) => b.resources.join('; ')],
      ['School', (b) => b.school],
      ['Contact', (b) => b.contactName],
      ['Email', (b) => b.email],
      ['Phone', (b) => b.phone],
      ['Year level', (b) => b.yearLevel],
      ['Notes', (b) => b.notes],
      ['Created', (b) => b.createdAt],
      ['Sync status', (b) => b.syncStatus],
      ['Sync error', (b) => b.syncError],
    ];
    const rows = filteredBookings(req.query).map((b) => columns.map(([, get]) => csvCell(get(b))).join(','));
    res
      .type('text/csv; charset=utf-8')
      .set('Content-Disposition', `attachment; filename="bookings-${ctx.today()}.csv"`)
      .send('﻿' + [columns.map(([h]) => h).join(','), ...rows].join('\r\n'));
  });

  api.post('/bookings/:id/cancel', (req, res) => {
    const outcome = bookings.cancel(Number(req.params.id), { by: 'admin' });
    if (!outcome.ok) return res.status(404).json({ error: 'Booking not found' });
    res.json({ booking: adminBookingView(catalog, outcome.booking) });
  });

  api.post('/bookings/:id/retry-sync', async (req, res) => {
    const booking = store.getBooking(Number(req.params.id));
    if (!booking) return res.status(404).json({ error: 'Booking not found' });
    if (!ctx.sync?.enabled) return res.status(400).json({ error: 'Sync is turned off (SYNC_MODE=none)' });
    await ctx.sync.syncBooking(booking.id);
    res.json({ booking: adminBookingView(catalog, store.getBooking(booking.id)) });
  });

  // ---- rule tester -------------------------------------------------------------------
  api.post('/rule-test', (req, res) => {
    const { programId, date, classes = 1, slotId = catalog.settings.slots[0].id } = req.body || {};
    if (!isValidDate(date)) return res.status(400).json({ error: 'Choose a date' });
    const result = bookings.check({ programId, date, slotId, classes: Number(classes) }, { enforceToday: false });
    res.json({
      ...result,
      assignedResourceNames: result.assignedResources.map((id) => resourceName(catalog, id)),
      sameDay: store.activeBookingsOn(date).map((b) => adminBookingView(catalog, b)),
      externalBusy: store.externalBusyOn(date),
    });
  });

  // ---- catalog view --------------------------------------------------------------------
  api.get('/catalog', (req, res) => {
    res.json({
      file: catalog.file,
      settings: catalog.settings,
      resources: catalog.resources,
      categories: catalog.categories,
      programs: catalog.programs.map((p) => ({
        ...p,
        categoryName: catalog.index.categories[p.category]?.name,
        semesterLabel: semesterLabel(p.semesters),
        rooms: programRooms(catalog, p),
        requirementsText: p.requires.map((alts) => describeRequirement(catalog, alts)),
        rulesText: describeCombinationRules(catalog, p),
      })),
    });
  });

  // ---- sync status ---------------------------------------------------------------------
  api.get('/sync', (req, res) => {
    const base = config.publicUrl || `${req.protocol}://${req.get('host')}`;
    const feedOk = Boolean(config.calendarFeedToken) && !config.calendarFeedToken.startsWith('change-me');
    const token = encodeURIComponent(config.calendarFeedToken);
    res.json({
      mode: config.syncMode,
      status: ctx.sync ? ctx.sync.status() : null,
      feeds: feedOk
        ? {
            all: `${base}/calendar/${token}/all.ics`,
            rooms: catalog.resources.map((r) => ({ id: r.id, name: r.name, url: `${base}/calendar/${token}/room/${r.id}.ics` })),
          }
        : null,
      needingSync: store.bookingsNeedingSync().map((b) => adminBookingView(catalog, b)),
      unmappedPrograms: catalog.programs.filter((p) => !p.bookings_service_id).map((p) => p.name),
      email: { inviteAddresses: config.email.inviteAddresses, smtp: Boolean(config.email.host) },
      graph: { businessId: config.graph.businessId, configured: Boolean(config.graph.clientId && config.graph.tenantId) },
      audit: store.recentAudit(30),
    });
  });

  api.post('/sync/run', async (req, res) => {
    if (!ctx.sync?.enabled) return res.status(400).json({ error: 'Sync is turned off (SYNC_MODE=none)' });
    const result = await ctx.sync.runOnce();
    res.json(result);
  });

  // ---- demo controls -------------------------------------------------------------------
  api.post('/demo/reset', (req, res) => {
    if (!config.demoMode) return res.status(403).json({ error: 'Demo mode is off' });
    const result = seedDemo(ctx);
    res.json({ created: result.created.length, skipped: result.skipped });
  });

  api.use((req, res) => res.status(404).json({ error: 'Not found' }));
  return router;
}

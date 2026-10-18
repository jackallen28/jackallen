// =====================================================================================
//  SYNC LAYER — sends bookings to Microsoft 365 and (in graph mode) imports appointments
//  made directly in Microsoft Bookings.
//
//  Every adapter implements the same three functions:
//    onBookingCreated(booking, program)   → { externalId? }
//    onBookingCancelled(booking, program)
//    importBusy(fromDate, toDate)         → [{ externalId, date, start, end, programId?, label }]   (optional)
//
//  Sync never blocks or undoes a booking. If sending fails, the booking is marked
//  sync_status = failed and retried automatically every 15 minutes (and shown in admin).
// =====================================================================================

import path from 'node:path';
import { createEmailAdapter } from './email.js';
import { createGraphAdapter } from './graph.js';
import { createWebhookAdapter } from './webhook.js';
import { addDays, slotWindow, overlaps, toMinutes } from '../engine/dates.js';

export const RETRY_MINUTES = 15;
export const IMPORT_DAYS = 120;

const noneAdapter = {
  name: 'none',
  async onBookingCreated() {
    return {};
  },
  async onBookingCancelled() {},
};

/** Picks the adapter for SYNC_MODE. Tests can pass their own options (e.g. a mock Graph). */
export function createAdapter({ config, catalog }, options = {}) {
  if (config.syncMode === 'email') {
    return createEmailAdapter({ config, catalog, outboxDir: path.join(config.dataDir, 'outbox'), ...options });
  }
  if (config.syncMode === 'graph') return createGraphAdapter({ config, catalog, ...options });
  if (config.syncMode === 'webhook') return createWebhookAdapter({ config, catalog, ...options });
  return noneAdapter;
}

export function createSyncService({ config, catalog, store, adapter, today, logger = console }) {
  const enabled = adapter.name !== 'none';
  const state = {
    lastRunAt: null,
    lastImportAt: store.getMeta('sync.lastImportAt'),
    lastImportCount: null,
    lastError: null,
    intervalMinutes: RETRY_MINUTES,
  };
  const queues = new Map(); // booking id → promise chain, so a create and a cancel never overlap
  let timer = null;

  async function process(id) {
    const booking = store.getBooking(id);
    if (!booking) return;
    if (booking.syncStatus === 'synced' || booking.syncStatus === 'none') return;
    const program = catalog.index.programs[booking.programId] || null;
    try {
      if (booking.status === 'confirmed') {
        const result = (await adapter.onBookingCreated(booking, program)) || {};
        store.updateSync(id, { status: 'synced', externalId: result.externalId, attempted: true });
        store.audit('sync.created', id, { mode: adapter.name, externalId: result.externalId || null });
      } else {
        await adapter.onBookingCancelled(booking, program);
        store.updateSync(id, { status: 'synced', attempted: true });
        store.audit('sync.cancelled', id, { mode: adapter.name });
      }
    } catch (err) {
      const message = err?.message || String(err);
      store.updateSync(id, { status: 'failed', error: message, attempted: true });
      store.audit('sync.failed', id, message);
      state.lastError = message;
      logger.warn(`Sync failed for booking #${id}: ${message}`);
    }
  }

  /** Sends one booking now (queued behind any sync already running for it). */
  function syncBooking(id) {
    const next = (queues.get(id) || Promise.resolve()).then(() => process(id));
    queues.set(id, next);
    next.finally(() => {
      if (queues.get(id) === next) queues.delete(id);
    });
    return next;
  }

  /** Works out which rooms an imported appointment holds, the same way the engine would. */
  function placeBlock(block, placedSoFar) {
    const program = block.programId ? catalog.index.programs[block.programId] : null;
    if (!program) return { ...block, resourceIds: [], staff: 0 };
    const window = { start: toMinutes(block.start), end: toMinutes(block.end) };
    const held = new Set();
    for (const b of store.activeBookingsOn(block.date)) {
      if (overlaps(slotWindow(catalog, b.slotId), window)) b.assignedResources.forEach((r) => held.add(r));
    }
    for (const p of placedSoFar) {
      if (p.date === block.date && overlaps({ start: toMinutes(p.start), end: toMinutes(p.end) }, window)) {
        p.resourceIds.forEach((r) => held.add(r));
      }
    }
    const chosen = [];
    const ordered = [...program.requires].sort((a, b) => a.length - b.length);
    for (const alternatives of ordered) {
      // It's a real appointment, so it holds a room even if that means a visible clash.
      chosen.push(alternatives.find((r) => !held.has(r) && !chosen.includes(r)) || alternatives[0]);
    }
    return { ...block, resourceIds: chosen, staff: program.staff_required };
  }

  async function importBusy() {
    if (!adapter.importBusy) return null;
    const from = today();
    const to = addDays(from, IMPORT_DAYS);
    const own = store.ownExternalIds();
    const appointments = (await adapter.importBusy(from, to)).filter((a) => !own.has(a.externalId));
    const placed = [];
    for (const a of appointments) placed.push(placeBlock(a, placed));
    store.replaceExternalBusy('graph', from, to, placed);
    state.lastImportAt = new Date().toISOString();
    state.lastImportCount = placed.length;
    store.setMeta('sync.lastImportAt', state.lastImportAt);
    return placed.length;
  }

  /** Retries everything pending/failed, then imports from Microsoft Bookings. */
  async function runOnce() {
    let synced = 0;
    let failed = 0;
    let imported = null;
    for (const b of store.bookingsNeedingSync()) {
      await syncBooking(b.id);
      const after = store.getBooking(b.id);
      if (after.syncStatus === 'synced') synced++;
      else failed++;
    }
    try {
      imported = await importBusy();
    } catch (err) {
      state.lastError = `Import from Microsoft Bookings failed: ${err.message}`;
      logger.warn(state.lastError);
    }
    state.lastRunAt = new Date().toISOString();
    return { synced, failed, imported };
  }

  return {
    enabled,
    mode: adapter.name,
    adapter,
    bookingCreated: (id) => syncBooking(id).catch(() => {}),
    bookingCancelled: (id) => syncBooking(id).catch(() => {}),
    syncBooking,
    runOnce,
    importBusy,
    // Rooms an appointment reported by Power Automate holds (other imported blocks that day count too).
    placeBlock: (block) =>
      placeBlock(block, store.externalBusyOn(block.date).filter((x) => x.externalId !== String(block.externalId))),
    status: () => ({ ...state }),
    start() {
      if (!enabled || timer) return;
      setTimeout(() => runOnce().catch((e) => logger.warn(e.message)), 5000).unref();
      timer = setInterval(() => runOnce().catch((e) => logger.warn(e.message)), RETRY_MINUTES * 60 * 1000);
      timer.unref();
    },
    stop() {
      clearInterval(timer);
      timer = null;
    },
    /** Waits until every queued sync has finished (used by tests and on shutdown). */
    async idle() {
      while (queues.size) await Promise.allSettled([...queues.values()]);
    },
  };
}

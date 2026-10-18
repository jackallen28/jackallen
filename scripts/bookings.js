// `npm run bookings -- <command>` — staff tasks from the server's command line. Useful when the
// admin website is switched off (ADMIN_ACCESS=off), so nothing can be changed over the web.
//
//   npm run bookings -- list [--from 2026-11-01] [--to 2026-11-30] [--all]
//   npm run bookings -- show PB-00012
//   npm run bookings -- cancel PB-00012
//
// In Docker:  docker compose exec app npm run bookings -- list

import { loadConfig } from '../src/config.js';
import { createContext } from '../src/context.js';
import { bookingReference } from '../src/bookings.js';
import { resourceName } from '../src/catalog/describe.js';

const ctx = createContext(loadConfig());
const { store, catalog } = ctx;
const [command, ...rest] = process.argv.slice(2);
const option = (name) => {
  const i = rest.indexOf(`--${name}`);
  return i >= 0 ? rest[i + 1] : undefined;
};

function find(ref) {
  const id = Number(String(ref || '').replace(/^PB-?/i, ''));
  const booking = Number.isInteger(id) && id > 0 ? store.getBooking(id) : null;
  if (!booking) throw new Error(`No booking ${ref}`);
  return booking;
}

function line(b) {
  const program = catalog.index.programs[b.programId]?.name || b.programId;
  return `${bookingReference(b.id)}  ${b.date}  ${b.status.padEnd(9)}  ${program.padEnd(38)}  ${b.school}  (${b.classes} class${b.classes > 1 ? 'es' : ''})`;
}

try {
  switch (command) {
    case 'list': {
      const list = store.listBookings({
        from: option('from') || (rest.includes('--all') ? undefined : ctx.today()),
        to: option('to'),
      });
      console.log(list.length ? list.map(line).join('\n') : 'No bookings.');
      break;
    }
    case 'show': {
      const b = find(rest[0]);
      console.log(line(b));
      console.log(`  Contact: ${b.contactName}, ${b.email}, ${b.phone} · ${b.yearLevel}`);
      console.log(`  Rooms/kit: ${b.assignedResources.map((r) => resourceName(catalog, r)).join(', ')}`);
      if (b.notes) console.log(`  Notes: ${b.notes}`);
      console.log(`  Sync: ${b.syncStatus}${b.syncError ? ` — ${b.syncError}` : ''}`);
      break;
    }
    case 'cancel': {
      const b = find(rest[0]);
      const outcome = ctx.bookings.cancel(b.id, { by: `command line (${process.env.USER || 'server'})` });
      await ctx.sync.idle(); // let Outlook / Bookings know before exiting
      console.log(outcome.alreadyCancelled ? 'Already cancelled.' : `✔ Cancelled: ${line(outcome.booking)}`);
      break;
    }
    default:
      console.log(`Staff tasks from the command line.

  npm run bookings -- list [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--all]
  npm run bookings -- show PB-00012
  npm run bookings -- cancel PB-00012`);
  }
} catch (err) {
  console.error(`✖ ${err.message}`);
  process.exitCode = 1;
} finally {
  ctx.close();
}

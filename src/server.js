// Entry point: `npm start` runs this file.

import { loadConfig, configWarnings } from './config.js';
import { createContext } from './context.js';
import { createApp } from './app.js';
import { seedDemo } from './seed.js';

let ctx;
try {
  const config = loadConfig();
  ctx = createContext(config);
} catch (err) {
  // Most likely a mistake in config/catalog.yaml — print it clearly and stop.
  console.error(`\n✖ Could not start: ${err.message}\n`);
  process.exit(1);
}

const { config } = ctx;
for (const warning of configWarnings(config)) console.warn(`⚠  ${warning}`);
if (config.adminAccess === 'accounts' && ctx.store.countActiveUsers() === 0) {
  console.warn('⚠  No staff accounts yet. Create one with:  npm run users -- add you@school.vic.edu.au --role manager');
}

// First start in demo mode: load example bookings so there is something to look at.
if (config.demoMode && ctx.store.countBookings() === 0) {
  const { created } = seedDemo(ctx);
  console.log(`Demo mode: loaded ${created.length} example bookings (reset any time from /admin).`);
}

const app = createApp(ctx);
const server = app.listen(config.port, () => {
  console.log(`Program booking system running at http://localhost:${config.port}`);
  console.log(`  catalog: ${ctx.catalog.file} (${ctx.catalog.programs.length} programs)`);
  console.log(`  data:    ${config.dataDir}`);
  console.log(`  sync:    ${config.syncMode}${ctx.sync.enabled ? ` (retries every 15 minutes)` : ''}`);
  console.log(`  admin:   ${{ accounts: 'staff accounts + authenticator codes', off: 'switched off (use npm run bookings / npm run users)', password: 'shared password (demo only)' }[config.adminAccess]}${config.adminAllowedIps.length ? `, only from ${config.adminAllowedIps.join(', ')}` : ''}`);
});
ctx.sync.start();

function shutdown() {
  server.close(() => {
    ctx.close();
    process.exit(0);
  });
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

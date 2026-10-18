// Entry point: `npm start` runs this file.

import { loadConfig, configWarnings } from './config.js';
import { createContext } from './context.js';
import { createApp } from './app.js';

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

const app = createApp(ctx);
const server = app.listen(config.port, () => {
  console.log(`Program booking system running at http://localhost:${config.port}`);
  console.log(`  catalog: ${ctx.catalog.file} (${ctx.catalog.programs.length} programs)`);
  console.log(`  data:    ${config.dataDir}`);
});

function shutdown() {
  server.close(() => {
    ctx.close();
    process.exit(0);
  });
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

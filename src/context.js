// Wires the pieces together: config → catalog → database → booking service.
// server.js, the scripts and the tests all build the app through createContext().

import { loadCatalog } from './catalog/load.js';
import { openDatabase, databaseFile } from './db/index.js';
import { createStore } from './db/store.js';
import { createBookingService } from './bookings.js';
import { todayIn } from './time.js';
import { createAdapter, createSyncService } from './sync/index.js';

/**
 * @param {object} config            from loadConfig()
 * @param {object} [overrides]       for tests: { catalog, dbFile, today, syncOptions, logger }
 */
export function createContext(config, overrides = {}) {
  const catalog = overrides.catalog || loadCatalog(config.catalogPath);
  const db = openDatabase(overrides.dbFile || databaseFile(config.dataDir));
  const store = createStore(db);
  const today = overrides.today || (() => todayIn(config.timezone));
  // How bookings reach Microsoft 365 (SYNC_MODE). syncOptions lets tests plug in a mock Graph server.
  const adapter = createAdapter({ config, catalog }, overrides.syncOptions);
  const sync = createSyncService({ config, catalog, store, adapter, today, logger: overrides.logger });
  const bookings = createBookingService({ store, catalog, sync, today });

  return {
    config,
    catalog,
    db,
    store,
    today,
    sync,
    bookings,
    close() {
      sync.stop();
      db.close();
    },
  };
}

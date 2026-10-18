// Wires the pieces together: config → catalog → database → booking service.
// server.js, the scripts and the tests all build the app through createContext().

import { loadCatalog } from './catalog/load.js';
import { openDatabase, databaseFile } from './db/index.js';
import { createStore } from './db/store.js';
import { createBookingService } from './bookings.js';
import { todayIn } from './time.js';

/**
 * @param {object} config            from loadConfig()
 * @param {object} [overrides]       for tests: { catalog, dbFile, today }
 */
export function createContext(config, overrides = {}) {
  const catalog = overrides.catalog || loadCatalog(config.catalogPath);
  const db = openDatabase(overrides.dbFile || databaseFile(config.dataDir));
  const store = createStore(db);
  const today = overrides.today || (() => todayIn(config.timezone));
  const sync = null;
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
      db.close();
    },
  };
}

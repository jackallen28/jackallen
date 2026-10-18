// `npm run backup` — writes a dated copy of the database to data/backups/.
// Safe to run while the site is running (uses SQLite's online backup).

import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { loadConfig } from '../src/config.js';
import { databaseFile } from '../src/db/index.js';

const config = loadConfig();
const source = databaseFile(config.dataDir);
if (!fs.existsSync(source)) {
  console.error(`No database found at ${source}`);
  process.exit(1);
}
const dir = path.join(config.dataDir, 'backups');
fs.mkdirSync(dir, { recursive: true });
const stamp = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '');
const target = path.join(dir, `bookings-${stamp}.sqlite`);

const db = new Database(source, { readonly: true });
await db.backup(target);
db.close();
console.log(`Backup written: ${target}`);

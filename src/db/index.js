// Opens the SQLite database file and brings its tables up to date ("migrations").
// To change the database later, ADD a new entry to MIGRATIONS — never edit an old one.

import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';

const MIGRATIONS = [
  // 1 — first version
  `
  CREATE TABLE bookings (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    uid                TEXT NOT NULL UNIQUE,           -- stable calendar event id
    program_id         TEXT NOT NULL,
    date               TEXT NOT NULL,                  -- YYYY-MM-DD (local)
    slot_id            TEXT NOT NULL,
    classes            INTEGER NOT NULL,
    students           INTEGER NOT NULL,
    assigned_resources TEXT NOT NULL DEFAULT '[]',     -- JSON list of resource ids
    school             TEXT NOT NULL,
    contact_name       TEXT NOT NULL,
    email              TEXT NOT NULL,
    phone              TEXT NOT NULL DEFAULT '',
    year_level         TEXT NOT NULL DEFAULT '',
    notes              TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    manage_token       TEXT NOT NULL UNIQUE,
    created_at         TEXT NOT NULL,
    cancelled_at       TEXT,
    sequence           INTEGER NOT NULL DEFAULT 0,     -- calendar SEQUENCE, goes up on each change
    source             TEXT NOT NULL DEFAULT 'web',    -- web | demo
    external_id        TEXT,                           -- Microsoft Bookings appointment id
    sync_status        TEXT NOT NULL DEFAULT 'none' CHECK (sync_status IN ('none', 'pending', 'synced', 'failed')),
    sync_error         TEXT,
    sync_attempts      INTEGER NOT NULL DEFAULT 0,
    synced_at          TEXT
  );
  CREATE INDEX bookings_by_date ON bookings (date);

  CREATE TABLE external_busy (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,                        -- e.g. graph
    external_id  TEXT NOT NULL,
    date         TEXT NOT NULL,
    start_time   TEXT NOT NULL,                        -- HH:MM (local)
    end_time     TEXT NOT NULL,
    resource_ids TEXT NOT NULL DEFAULT '[]',
    program_id   TEXT,                                 -- set when the Bookings service maps to a program
    staff        INTEGER NOT NULL DEFAULT 0,
    label        TEXT NOT NULL DEFAULT '',
    imported_at  TEXT NOT NULL,
    UNIQUE (source, external_id)
  );
  CREATE INDEX external_busy_by_date ON external_busy (date);

  CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    action     TEXT NOT NULL,
    booking_id INTEGER,
    detail     TEXT
  );

  CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
  );
  `,
];

/**
 * Opens (or creates) the database. Pass ':memory:' for a throwaway database in tests.
 */
export function openDatabase(file) {
  if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new Database(file);
  if (file !== ':memory:') db.pragma('journal_mode = WAL'); // better for a web server
  db.pragma('busy_timeout = 5000'); // wait (rather than fail) if another process is writing
  db.pragma('foreign_keys = ON');
  migrate(db);
  return db;
}

export function databaseFile(dataDir) {
  return path.join(dataDir, 'bookings.sqlite');
}

function migrate(db) {
  const current = db.pragma('user_version', { simple: true });
  for (let version = current; version < MIGRATIONS.length; version++) {
    db.transaction(() => {
      db.exec(MIGRATIONS[version]);
      db.pragma(`user_version = ${version + 1}`);
    })();
  }
}

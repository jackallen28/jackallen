// Every SQL query used by the app lives here. The rest of the code calls these functions
// and works with plain JavaScript objects (camelCase), never with raw rows.

function toBooking(row) {
  if (!row) return null;
  return {
    id: row.id,
    uid: row.uid,
    programId: row.program_id,
    date: row.date,
    slotId: row.slot_id,
    classes: row.classes,
    students: row.students,
    assignedResources: JSON.parse(row.assigned_resources || '[]'),
    school: row.school,
    contactName: row.contact_name,
    email: row.email,
    phone: row.phone,
    yearLevel: row.year_level,
    notes: row.notes,
    status: row.status,
    manageToken: row.manage_token,
    createdAt: row.created_at,
    cancelledAt: row.cancelled_at,
    sequence: row.sequence,
    source: row.source,
    externalId: row.external_id,
    syncStatus: row.sync_status,
    syncError: row.sync_error,
    syncAttempts: row.sync_attempts,
    syncedAt: row.synced_at,
  };
}

function toBusy(row) {
  return {
    id: `ext-${row.id}`,
    rowId: row.id,
    source: row.source,
    externalId: row.external_id,
    date: row.date,
    start: row.start_time,
    end: row.end_time,
    resourceIds: JSON.parse(row.resource_ids || '[]'),
    programId: row.program_id,
    staff: row.staff,
    label: row.label,
    importedAt: row.imported_at,
  };
}

export function createStore(db) {
  const now = () => new Date().toISOString();

  const store = {
    db,

    /** Wraps fn in a write transaction that other writers must wait for (BEGIN IMMEDIATE). */
    immediate(fn) {
      return db.transaction(fn).immediate();
    },

    // ---- bookings -----------------------------------------------------------------
    insertBooking(b) {
      const info = db
        .prepare(
          `INSERT INTO bookings (uid, program_id, date, slot_id, classes, students, assigned_resources,
             school, contact_name, email, phone, year_level, notes, status, manage_token, created_at,
             source, sync_status)
           VALUES (@uid, @programId, @date, @slotId, @classes, @students, @assignedResources,
             @school, @contactName, @email, @phone, @yearLevel, @notes, 'confirmed', @manageToken, @createdAt,
             @source, @syncStatus)`,
        )
        .run({
          ...b,
          assignedResources: JSON.stringify(b.assignedResources || []),
          createdAt: b.createdAt || now(),
          source: b.source || 'web',
          syncStatus: b.syncStatus || 'none',
        });
      return store.getBooking(Number(info.lastInsertRowid));
    },

    getBooking(id) {
      return toBooking(db.prepare('SELECT * FROM bookings WHERE id = ?').get(id));
    },

    getBookingByToken(token) {
      return toBooking(db.prepare('SELECT * FROM bookings WHERE manage_token = ?').get(String(token)));
    },

    /** Confirmed bookings on one date (what the clash engine needs). */
    activeBookingsOn(date) {
      return db
        .prepare(`SELECT * FROM bookings WHERE date = ? AND status = 'confirmed' ORDER BY id`)
        .all(date)
        .map(toBooking);
    },

    activeBookingsBetween(from, to) {
      return db
        .prepare(`SELECT * FROM bookings WHERE date BETWEEN ? AND ? AND status = 'confirmed' ORDER BY date, id`)
        .all(from, to)
        .map(toBooking);
    },

    /** All bookings (including cancelled), for calendar feeds and the admin list. */
    listBookings({ from, to, status, programIds, syncStatus, q, limit = 1000 } = {}) {
      const where = [];
      const params = {};
      if (from) (where.push('date >= @from'), (params.from = from));
      if (to) (where.push('date <= @to'), (params.to = to));
      if (status) (where.push('status = @status'), (params.status = status));
      if (syncStatus) (where.push('sync_status = @syncStatus'), (params.syncStatus = syncStatus));
      if (programIds) {
        if (!programIds.length) return [];
        where.push(`program_id IN (${programIds.map((_, i) => `@p${i}`).join(', ')})`);
        programIds.forEach((id, i) => (params[`p${i}`] = id));
      }
      if (q) {
        where.push(
          `(school LIKE @q OR contact_name LIKE @q OR email LIKE @q OR phone LIKE @q OR notes LIKE @q OR year_level LIKE @q OR CAST(id AS TEXT) = @qExact)`,
        );
        params.q = `%${q}%`;
        params.qExact = String(q).replace(/^#/, '');
      }
      const sql = `SELECT * FROM bookings ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
                   ORDER BY date, id LIMIT ${Number(limit) || 1000}`;
      return db.prepare(sql).all(params).map(toBooking);
    },

    cancelBooking(id) {
      db.prepare(
        `UPDATE bookings SET status = 'cancelled', cancelled_at = ?, sequence = sequence + 1
         WHERE id = ? AND status = 'confirmed'`,
      ).run(now(), id);
      return store.getBooking(id);
    },

    /** Records the result of sending a booking to Outlook / Microsoft Bookings. */
    updateSync(id, { status, externalId, error = null, attempted = false }) {
      db.prepare(
        `UPDATE bookings SET
           sync_status = @status,
           sync_error = @error,
           external_id = COALESCE(@externalId, external_id),
           sync_attempts = sync_attempts + @attempted,
           synced_at = CASE WHEN @status = 'synced' THEN @now ELSE synced_at END
         WHERE id = @id`,
      ).run({ id, status, error, externalId: externalId ?? null, attempted: attempted ? 1 : 0, now: now() });
      return store.getBooking(id);
    },

    bookingsNeedingSync() {
      return db
        .prepare(`SELECT * FROM bookings WHERE sync_status IN ('pending', 'failed') ORDER BY id`)
        .all()
        .map(toBooking);
    },

    /** Microsoft Bookings ids of appointments this app created (so imports can skip them). */
    ownExternalIds() {
      return new Set(
        db.prepare('SELECT external_id FROM bookings WHERE external_id IS NOT NULL').pluck().all(),
      );
    },

    countBookings() {
      return db.prepare('SELECT COUNT(*) FROM bookings').pluck().get();
    },

    // ---- busy blocks imported from Microsoft Bookings ------------------------------
    externalBusyOn(date) {
      return db.prepare('SELECT * FROM external_busy WHERE date = ? ORDER BY start_time').all(date).map(toBusy);
    },

    externalBusyBetween(from, to) {
      return db
        .prepare('SELECT * FROM external_busy WHERE date BETWEEN ? AND ? ORDER BY date, start_time')
        .all(from, to)
        .map(toBusy);
    },

    /** Replaces everything imported from `source` between two dates with a fresh list. */
    replaceExternalBusy(source, from, to, blocks) {
      db.transaction(() => {
        db.prepare('DELETE FROM external_busy WHERE source = ? AND date BETWEEN ? AND ?').run(source, from, to);
        const insert = db.prepare(
          `INSERT OR REPLACE INTO external_busy
             (source, external_id, date, start_time, end_time, resource_ids, program_id, staff, label, imported_at)
           VALUES (@source, @externalId, @date, @start, @end, @resourceIds, @programId, @staff, @label, @importedAt)`,
        );
        const importedAt = now();
        for (const b of blocks) {
          insert.run({
            source,
            externalId: b.externalId,
            date: b.date,
            start: b.start,
            end: b.end,
            resourceIds: JSON.stringify(b.resourceIds || []),
            programId: b.programId || null,
            staff: b.staff || 0,
            label: b.label || '',
            importedAt,
          });
        }
      })();
    },

    /** Adds or updates one imported block (used when a Power Automate flow reports an appointment). */
    upsertExternalBusy(source, b) {
      db.prepare(
        `INSERT INTO external_busy
           (source, external_id, date, start_time, end_time, resource_ids, program_id, staff, label, imported_at)
         VALUES (@source, @externalId, @date, @start, @end, @resourceIds, @programId, @staff, @label, @importedAt)
         ON CONFLICT(source, external_id) DO UPDATE SET
           date = excluded.date, start_time = excluded.start_time, end_time = excluded.end_time,
           resource_ids = excluded.resource_ids, program_id = excluded.program_id, staff = excluded.staff,
           label = excluded.label, imported_at = excluded.imported_at`,
      ).run({
        source,
        externalId: String(b.externalId),
        date: b.date,
        start: b.start,
        end: b.end,
        resourceIds: JSON.stringify(b.resourceIds || []),
        programId: b.programId || null,
        staff: b.staff || 0,
        label: b.label || '',
        importedAt: now(),
      });
    },

    deleteExternalBusy(source, externalId) {
      return db.prepare('DELETE FROM external_busy WHERE source = ? AND external_id = ?').run(source, String(externalId)).changes;
    },

    // ---- staff accounts and sessions -----------------------------------------------
    insertUser({ email, name, role, passwordHash, totpSecret }) {
      const info = db
        .prepare(
          `INSERT INTO users (email, name, role, password_hash, totp_secret, created_at)
           VALUES (?, ?, ?, ?, ?, ?)`,
        )
        .run(email.trim().toLowerCase(), name || '', role, passwordHash, totpSecret, now());
      return store.getUserById(Number(info.lastInsertRowid));
    },
    getUserById(id) {
      return db.prepare('SELECT * FROM users WHERE id = ?').get(id) || null;
    },
    getUserByEmail(email) {
      return db.prepare('SELECT * FROM users WHERE email = ?').get(String(email || '').trim().toLowerCase()) || null;
    },
    listUsers() {
      return db.prepare('SELECT id, email, name, role, disabled, locked_until, created_at, last_login_at FROM users ORDER BY email').all();
    },
    countActiveUsers() {
      return db.prepare('SELECT COUNT(*) FROM users WHERE disabled = 0').pluck().get();
    },
    updateUser(id, fields) {
      const columns = Object.keys(fields);
      if (!columns.length) return;
      db.prepare(`UPDATE users SET ${columns.map((c) => `${c} = @${c}`).join(', ')} WHERE id = @id`).run({ ...fields, id });
    },
    deleteUser(id) {
      db.prepare('DELETE FROM users WHERE id = ?').run(id);
    },

    insertSession(s) {
      db.prepare(
        `INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, ip, user_agent)
         VALUES (@tokenHash, @userId, @createdAt, @createdAt, @expiresAt, @ip, @userAgent)`,
      ).run({ ...s, createdAt: now() });
    },
    getSession(tokenHash) {
      return db.prepare('SELECT * FROM sessions WHERE token_hash = ?').get(tokenHash) || null;
    },
    touchSession(tokenHash) {
      db.prepare('UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?').run(now(), tokenHash);
    },
    deleteSession(tokenHash) {
      db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(tokenHash);
    },
    deleteSessionsForUser(userId) {
      return db.prepare('DELETE FROM sessions WHERE user_id = ?').run(userId).changes;
    },
    deleteAllSessions() {
      return db.prepare('DELETE FROM sessions').run().changes;
    },
    deleteExpiredSessions() {
      db.prepare('DELETE FROM sessions WHERE expires_at < ?').run(now());
    },

    // ---- audit log and settings ------------------------------------------------------
    /** Records an action. `actor` = who did it (staff email, "school", "system"…). */
    audit(action, bookingId = null, detail = null, actor = null) {
      db.prepare('INSERT INTO audit_log (at, action, booking_id, detail, actor) VALUES (?, ?, ?, ?, ?)').run(
        now(),
        action,
        bookingId,
        detail == null ? null : typeof detail === 'string' ? detail : JSON.stringify(detail),
        actor,
      );
    },

    recentAudit(limit = 50) {
      return db.prepare('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?').all(limit);
    },

    getMeta(key) {
      return db.prepare('SELECT value FROM meta WHERE key = ?').pluck().get(key) ?? null;
    },

    setMeta(key, value) {
      db.prepare('INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value').run(
        key,
        value == null ? null : String(value),
      );
    },

    /** Deletes all bookings and imported blocks (used by the demo reset). Staff accounts and the audit log are kept. */
    resetAll() {
      db.transaction(() => {
        db.exec(`DELETE FROM bookings; DELETE FROM external_busy;
                 DELETE FROM sqlite_sequence WHERE name IN ('bookings', 'external_busy');`);
      })();
    },
  };
  return store;
}

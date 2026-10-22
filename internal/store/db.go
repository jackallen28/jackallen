// Package store keeps everything in Postgres (Neon's free plan in
// production): classes, students (a class, a number and a hash of their code:
// never a name), sessions, sketches, progress, staff accounts and the audit log.
//
// The schema has a version (the schema_version table) and a list of
// migrations. Never edit a migration that has shipped: add a new one.
package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// ErrNotFound is returned when a row doesn't exist.
var ErrNotFound = errors.New("not found")

// ErrExists is returned when a unique row already exists.
var ErrExists = errors.New("already exists")

// migrations[i] takes the database from version i to version i+1.
// Times are Unix milliseconds (BIGINT).
var migrations = []string{
	// 1: the first schema.
	`
	CREATE TABLE classes (
		id         BIGSERIAL PRIMARY KEY,
		name       TEXT NOT NULL,
		created_at BIGINT NOT NULL,
		created_by BIGINT
	);
	CREATE UNIQUE INDEX classes_name ON classes (lower(name));

	-- A student is a class, a number in it and a keyed hash of their code.
	CREATE TABLE students (
		id         BIGSERIAL PRIMARY KEY,
		class_id   BIGINT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
		number     INT NOT NULL,
		code_hash  TEXT NOT NULL UNIQUE,
		settings   TEXT NOT NULL DEFAULT '{}',
		created_at BIGINT NOT NULL,
		last_seen  BIGINT NOT NULL DEFAULT 0,
		UNIQUE (class_id, number)
	);
	CREATE TABLE student_sessions (
		token_hash TEXT PRIMARY KEY,
		student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
		created_at BIGINT NOT NULL,
		expires_at BIGINT NOT NULL
	);
	CREATE INDEX student_sessions_student ON student_sessions (student_id);
	CREATE TABLE sketches (
		student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
		project_id TEXT NOT NULL,
		code       TEXT NOT NULL,
		updated_at BIGINT NOT NULL,
		PRIMARY KEY (student_id, project_id)
	);
	CREATE TABLE progress (
		student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
		project_id TEXT NOT NULL,
		data       TEXT NOT NULL,
		updated_at BIGINT NOT NULL,
		PRIMARY KEY (student_id, project_id)
	);

	CREATE TABLE staff (
		id                  BIGSERIAL PRIMARY KEY,
		email               TEXT NOT NULL,
		password_hash       TEXT NOT NULL,
		totp_secret         TEXT NOT NULL DEFAULT '', -- encrypted with the server secret
		totp_enabled        BOOLEAN NOT NULL DEFAULT FALSE,
		totp_last_step      BIGINT NOT NULL DEFAULT 0, -- stops a code being used twice
		is_admin            BOOLEAN NOT NULL DEFAULT FALSE,
		failed_logins       INT NOT NULL DEFAULT 0,
		locked_until        BIGINT NOT NULL DEFAULT 0,
		created_at          BIGINT NOT NULL,
		last_login          BIGINT NOT NULL DEFAULT 0,
		password_changed_at BIGINT NOT NULL
	);
	CREATE UNIQUE INDEX staff_email ON staff (lower(email));
	CREATE TABLE staff_recovery_codes (
		staff_id  BIGINT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
		code_hash TEXT NOT NULL,
		used_at   BIGINT NOT NULL DEFAULT 0,
		PRIMARY KEY (staff_id, code_hash)
	);
	CREATE TABLE staff_sessions (
		token_hash TEXT PRIMARY KEY,
		staff_id   BIGINT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
		created_at BIGINT NOT NULL,
		expires_at BIGINT NOT NULL,
		last_seen  BIGINT NOT NULL,
		mfa_at     BIGINT NOT NULL DEFAULT 0, -- 0 until the authenticator code is given
		ip         TEXT NOT NULL DEFAULT ''
	);
	CREATE INDEX staff_sessions_staff ON staff_sessions (staff_id);
	CREATE TABLE staff_invites (
		token_hash TEXT PRIMARY KEY,
		email      TEXT NOT NULL,
		is_admin   BOOLEAN NOT NULL DEFAULT FALSE,
		created_by BIGINT,
		created_at BIGINT NOT NULL,
		expires_at BIGINT NOT NULL,
		used_at    BIGINT NOT NULL DEFAULT 0
	);
	CREATE TABLE audit_log (
		id       BIGSERIAL PRIMARY KEY,
		at       BIGINT NOT NULL,
		staff_id BIGINT,
		action   TEXT NOT NULL,
		detail   TEXT NOT NULL DEFAULT '',
		ip       TEXT NOT NULL DEFAULT ''
	);
	CREATE INDEX audit_log_at ON audit_log (at DESC);
	CREATE TABLE server_settings (
		key   TEXT PRIMARY KEY,
		value TEXT NOT NULL
	);
	`,
}

// SchemaVersion is the version this build of the server writes.
var SchemaVersion = len(migrations)

// Store is the database.
type Store struct {
	db  *sql.DB
	now func() time.Time
}

// Open connects to Postgres (a postgres:// URL) and brings the schema up to date.
func Open(ctx context.Context, url string) (*Store, error) {
	db, err := sql.Open("pgx", url)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(10)
	db.SetConnMaxIdleTime(4 * time.Minute) // Neon suspends idle databases
	pctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()
	if err := db.PingContext(pctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("can't reach the database: %w", err)
	}
	s := &Store{db: db, now: time.Now}
	if err := s.migrate(ctx); err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
}

// Close closes the database.
func (s *Store) Close() error { return s.db.Close() }

// Ping checks the database is reachable (for the health check).
func (s *Store) Ping(ctx context.Context) error { return s.db.PingContext(ctx) }

// Version returns the schema version in the database.
func (s *Store) Version(ctx context.Context) (int, error) {
	var v int
	err := s.db.QueryRowContext(ctx, "SELECT COALESCE(MAX(version), 0) FROM schema_version").Scan(&v)
	return v, err
}

func (s *Store) migrate(ctx context.Context) error {
	conn, err := s.db.Conn(ctx)
	if err != nil {
		return err
	}
	defer conn.Close()
	// One server migrates at a time.
	if _, err := conn.ExecContext(ctx, "SELECT pg_advisory_lock(7428361)"); err != nil {
		return err
	}
	defer conn.ExecContext(context.Background(), "SELECT pg_advisory_unlock(7428361)")
	if _, err := conn.ExecContext(ctx, "CREATE TABLE IF NOT EXISTS schema_version (version INT NOT NULL)"); err != nil {
		return err
	}
	var v int
	if err := conn.QueryRowContext(ctx, "SELECT COALESCE(MAX(version), 0) FROM schema_version").Scan(&v); err != nil {
		return err
	}
	if v > SchemaVersion {
		return fmt.Errorf("the database is from a newer CircuitPath (schema %d, this server knows %d); update the server", v, SchemaVersion)
	}
	for ; v < SchemaVersion; v++ {
		tx, err := conn.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, migrations[v]); err != nil {
			tx.Rollback()
			return fmt.Errorf("migration %d: %w", v+1, err)
		}
		if _, err := tx.ExecContext(ctx, "INSERT INTO schema_version (version) VALUES ($1)", v+1); err != nil {
			tx.Rollback()
			return err
		}
		if err := tx.Commit(); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) millis() int64 { return s.now().UnixMilli() }

// isUnique reports whether err is a unique-constraint violation.
func isUnique(err error) bool {
	type sqlState interface{ SQLState() string }
	var e sqlState
	return errors.As(err, &e) && e.SQLState() == "23505"
}

func (s *Store) execOne(ctx context.Context, q string, args ...any) error {
	res, err := s.db.ExecContext(ctx, q, args...)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

// Setting reads a server setting, returning def if it isn't set.
func (s *Store) Setting(ctx context.Context, key, def string) (string, error) {
	var v string
	err := s.db.QueryRowContext(ctx, "SELECT value FROM server_settings WHERE key = $1", key).Scan(&v)
	if errors.Is(err, sql.ErrNoRows) {
		return def, nil
	}
	return v, err
}

// SetSetting writes a server setting.
func (s *Store) SetSetting(ctx context.Context, key, value string) error {
	_, err := s.db.ExecContext(ctx,
		"INSERT INTO server_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
		key, value)
	return err
}

// Audit records something a staff member did (staffID 0: nobody signed in yet).
func (s *Store) Audit(ctx context.Context, staffID int64, action, detail, ip string) error {
	_, err := s.db.ExecContext(ctx,
		"INSERT INTO audit_log (at, staff_id, action, detail, ip) VALUES ($1, $2, $3, $4, $5)",
		s.millis(), nullID(staffID), action, detail, ip)
	return err
}

// AuditEntry is one line of the audit log.
type AuditEntry struct {
	At      int64  `json:"at"`
	StaffID int64  `json:"staff_id,omitempty"`
	Email   string `json:"email,omitempty"`
	Action  string `json:"action"`
	Detail  string `json:"detail,omitempty"`
	IP      string `json:"ip,omitempty"`
}

// AuditLog returns the newest entries first.
func (s *Store) AuditLog(ctx context.Context, limit int) ([]AuditEntry, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT a.at, COALESCE(a.staff_id, 0), COALESCE(st.email, ''), a.action, a.detail, a.ip
		FROM audit_log a LEFT JOIN staff st ON st.id = a.staff_id
		ORDER BY a.at DESC, a.id DESC LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []AuditEntry{}
	for rows.Next() {
		var e AuditEntry
		if err := rows.Scan(&e.At, &e.StaffID, &e.Email, &e.Action, &e.Detail, &e.IP); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

func nullID(id int64) any {
	if id == 0 {
		return nil
	}
	return id
}

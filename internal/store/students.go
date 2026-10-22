package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"slices"
	"strings"

	"modernc.org/sqlite"
	sqlite3 "modernc.org/sqlite/lib"
)

// Student is a profile: one to four first names (students sharing a kit) and a school.
type Student struct {
	ID        int64           `json:"id"`
	Names     []string        `json:"names"`
	School    string          `json:"school"`
	Settings  json.RawMessage `json:"settings"`
	CreatedAt int64           `json:"created_at"`
	LastSeen  int64           `json:"last_seen"`
}

// StudentSummary is what the welcome screen shows when picking a name.
type StudentSummary struct {
	ID       int64    `json:"id"`
	Names    []string `json:"names"`
	School   string   `json:"school"`
	LastSeen int64    `json:"last_seen"`
}

// NewStudent holds what's needed to create a profile.
type NewStudent struct {
	Names    []string
	School   string
	Settings json.RawMessage
}

func isUnique(err error) bool {
	var se *sqlite.Error
	return errors.As(err, &se) && se.Code() == sqlite3.SQLITE_CONSTRAINT_UNIQUE
}

// NameKey is used to spot two profiles with the same names at the same
// school. Name order doesn't matter.
func NameKey(names []string, school string) string {
	low := make([]string, len(names))
	for i, n := range names {
		low[i] = strings.ToLower(strings.Join(strings.Fields(n), " "))
	}
	slices.Sort(low)
	return strings.Join(low, "|") + "@" + strings.ToLower(strings.Join(strings.Fields(school), " "))
}

// CreateStudent adds a profile. It returns ErrExists if a profile with the
// same names and school is already on this laptop.
func (s *Store) CreateStudent(ctx context.Context, n NewStudent) (Student, error) {
	names, err := json.Marshal(n.Names)
	if err != nil {
		return Student{}, err
	}
	settings := n.Settings
	if len(settings) == 0 {
		settings = json.RawMessage("{}")
	}
	now := s.millis()
	res, err := s.db.ExecContext(ctx, `
		INSERT INTO students (names, name_key, school, picture_hash, settings, created_at, last_seen)
		VALUES (?, ?, ?, '', ?, ?, ?)`,
		string(names), NameKey(n.Names, n.School), n.School, string(settings), now, now)
	if isUnique(err) {
		return Student{}, ErrExists
	}
	if err != nil {
		return Student{}, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return Student{}, err
	}
	return Student{ID: id, Names: n.Names, School: n.School, Settings: settings, CreatedAt: now, LastSeen: now}, nil
}

// ListStudents lists every profile on this laptop, A to Z.
func (s *Store) ListStudents(ctx context.Context) ([]StudentSummary, error) {
	rows, err := s.db.QueryContext(ctx,
		"SELECT id, names, school, last_seen FROM students ORDER BY name_key")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []StudentSummary{}
	for rows.Next() {
		var st StudentSummary
		var names string
		if err := rows.Scan(&st.ID, &names, &st.School, &st.LastSeen); err != nil {
			return nil, err
		}
		if err := json.Unmarshal([]byte(names), &st.Names); err != nil {
			return nil, err
		}
		out = append(out, st)
	}
	return out, rows.Err()
}

// GetStudent loads a profile.
func (s *Store) GetStudent(ctx context.Context, id int64) (Student, error) {
	var st Student
	var names, settings string
	err := s.db.QueryRowContext(ctx,
		"SELECT id, names, school, settings, created_at, last_seen FROM students WHERE id = ?", id).
		Scan(&st.ID, &names, &st.School, &settings, &st.CreatedAt, &st.LastSeen)
	if errors.Is(err, sql.ErrNoRows) {
		return Student{}, ErrNotFound
	}
	if err != nil {
		return Student{}, err
	}
	st.Settings = json.RawMessage(settings)
	return st, json.Unmarshal([]byte(names), &st.Names)
}

// UpdateSettings replaces a student's settings (already validated JSON).
func (s *Store) UpdateSettings(ctx context.Context, id int64, settings json.RawMessage) error {
	return s.execOne(ctx, "UPDATE students SET settings = ? WHERE id = ?", string(settings), id)
}

// Touch records that a student was just seen.
func (s *Store) Touch(ctx context.Context, id int64) error {
	return s.execOne(ctx, "UPDATE students SET last_seen = ? WHERE id = ?", s.millis(), id)
}

// WipeAll deletes every profile and everything they saved (the WIPE page),
// then compacts the file so nothing can be read back from it.
func (s *Store) WipeAll(ctx context.Context) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, q := range []string{
		"DELETE FROM sessions", "DELETE FROM sketches", "DELETE FROM progress",
		"DELETE FROM students", "DELETE FROM classes",
	} {
		if _, err := tx.ExecContext(ctx, q); err != nil {
			return err
		}
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	if _, err := s.db.ExecContext(ctx, "VACUUM"); err != nil {
		return err
	}
	_, err = s.db.ExecContext(ctx, "PRAGMA wal_checkpoint(TRUNCATE)")
	return err
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

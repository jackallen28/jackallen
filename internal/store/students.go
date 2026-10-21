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

// Class is a group of students, such as "9D Tuesday".
type Class struct {
	ID       int64  `json:"id"`
	Name     string `json:"name"`
	Students int    `json:"students"`
}

// Student is a profile: one to four first names (students sharing a kit) and a school.
type Student struct {
	ID        int64           `json:"id"`
	ClassID   int64           `json:"class_id,omitempty"` // 0 when not in a class
	Names     []string        `json:"names"`
	School    string          `json:"school"`
	Settings  json.RawMessage `json:"settings"`
	CreatedAt int64           `json:"created_at"`
	LastSeen  int64           `json:"last_seen"`
}

// StudentSummary is what the login screen shows when picking a name.
type StudentSummary struct {
	ID     int64    `json:"id"`
	Names  []string `json:"names"`
	School string   `json:"school"`
}

// NewStudent holds what's needed to create a profile.
type NewStudent struct {
	ClassID     int64
	Names       []string
	School      string
	PictureHash string
	Settings    json.RawMessage
}

func isUnique(err error) bool {
	var se *sqlite.Error
	return errors.As(err, &se) && se.Code() == sqlite3.SQLITE_CONSTRAINT_UNIQUE
}

func nullID(id int64) any {
	if id == 0 {
		return nil
	}
	return id
}

// NameKey is used to spot two profiles with the same names at the same
// school in the same class. Name order doesn't matter.
func NameKey(names []string, school string) string {
	low := make([]string, len(names))
	for i, n := range names {
		low[i] = strings.ToLower(strings.Join(strings.Fields(n), " "))
	}
	slices.Sort(low)
	return strings.Join(low, "|") + "@" + strings.ToLower(strings.Join(strings.Fields(school), " "))
}

// CreateClass adds a class.
func (s *Store) CreateClass(ctx context.Context, name string) (Class, error) {
	res, err := s.db.ExecContext(ctx, "INSERT INTO classes (name, created_at) VALUES (?, ?)", name, s.millis())
	if isUnique(err) {
		return Class{}, ErrExists
	}
	if err != nil {
		return Class{}, err
	}
	id, err := res.LastInsertId()
	return Class{ID: id, Name: name}, err
}

// ListClasses lists every class, A to Z.
func (s *Store) ListClasses(ctx context.Context) ([]Class, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT c.id, c.name, COUNT(s.id) FROM classes c
		LEFT JOIN students s ON s.class_id = c.id
		GROUP BY c.id ORDER BY c.name COLLATE NOCASE`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Class{}
	for rows.Next() {
		var c Class
		if err := rows.Scan(&c.ID, &c.Name, &c.Students); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

// ClassExists reports whether a class with this id exists.
func (s *Store) ClassExists(ctx context.Context, id int64) (bool, error) {
	var n int
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM classes WHERE id = ?", id).Scan(&n)
	return n > 0, err
}

// CreateStudent adds a profile. It returns ErrExists if the same names and
// school are already in the class.
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
		INSERT INTO students (class_id, names, name_key, school, picture_hash, settings, created_at, last_seen)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		nullID(n.ClassID), string(names), NameKey(n.Names, n.School), n.School, n.PictureHash, string(settings), now, now)
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
	return Student{ID: id, ClassID: n.ClassID, Names: n.Names, School: n.School, Settings: settings, CreatedAt: now, LastSeen: now}, nil
}

// ListStudents lists the profiles in a class (classID 0: profiles in no class).
func (s *Store) ListStudents(ctx context.Context, classID int64) ([]StudentSummary, error) {
	rows, err := s.db.QueryContext(ctx,
		"SELECT id, names, school FROM students WHERE IFNULL(class_id, 0) = ? ORDER BY name_key", classID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []StudentSummary{}
	for rows.Next() {
		var st StudentSummary
		var names string
		if err := rows.Scan(&st.ID, &names, &st.School); err != nil {
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
	var classID sql.NullInt64
	var names, settings string
	err := s.db.QueryRowContext(ctx,
		"SELECT id, class_id, names, school, settings, created_at, last_seen FROM students WHERE id = ?", id).
		Scan(&st.ID, &classID, &names, &st.School, &settings, &st.CreatedAt, &st.LastSeen)
	if errors.Is(err, sql.ErrNoRows) {
		return Student{}, ErrNotFound
	}
	if err != nil {
		return Student{}, err
	}
	st.ClassID = classID.Int64
	st.Settings = json.RawMessage(settings)
	return st, json.Unmarshal([]byte(names), &st.Names)
}

// PictureHash returns the stored hash of a student's picture password.
func (s *Store) PictureHash(ctx context.Context, id int64) (string, error) {
	var h string
	err := s.db.QueryRowContext(ctx, "SELECT picture_hash FROM students WHERE id = ?", id).Scan(&h)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrNotFound
	}
	return h, err
}

// SetPictureHash replaces a student's picture password.
func (s *Store) SetPictureHash(ctx context.Context, id int64, hash string) error {
	return s.execOne(ctx, "UPDATE students SET picture_hash = ? WHERE id = ?", hash, id)
}

// UpdateSettings replaces a student's settings (already validated JSON).
func (s *Store) UpdateSettings(ctx context.Context, id int64, settings json.RawMessage) error {
	return s.execOne(ctx, "UPDATE students SET settings = ? WHERE id = ?", string(settings), id)
}

// Touch records that a student was just seen.
func (s *Store) Touch(ctx context.Context, id int64) error {
	return s.execOne(ctx, "UPDATE students SET last_seen = ? WHERE id = ?", s.millis(), id)
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

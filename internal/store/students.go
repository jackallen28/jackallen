package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"time"
)

// Class is a group of students, such as "9D Tuesday".
type Class struct {
	ID        int64  `json:"id"`
	Name      string `json:"name"`
	Students  int    `json:"students"`
	CreatedAt int64  `json:"created_at"`
}

// Student is a student account: a class, a number in it, and settings.
// There is no name: students sign in with a code, and only a keyed hash
// of the code is stored.
type Student struct {
	ID        int64           `json:"id"`
	ClassID   int64           `json:"class_id"`
	ClassName string          `json:"class_name"`
	Number    int             `json:"number"`
	Settings  json.RawMessage `json:"settings"`
	CreatedAt int64           `json:"created_at"`
	LastSeen  int64           `json:"last_seen"`
}

// StudentSummary is what the Teacher page shows for a student.
type StudentSummary struct {
	ID       int64 `json:"id"`
	Number   int   `json:"number"`
	LastSeen int64 `json:"last_seen"`
	Projects int   `json:"projects"` // projects with saved code or progress
}

// CreateClass adds a class.
func (s *Store) CreateClass(ctx context.Context, name string, staffID int64) (Class, error) {
	c := Class{Name: name, CreatedAt: s.millis()}
	err := s.db.QueryRowContext(ctx,
		"INSERT INTO classes (name, created_at, created_by) VALUES ($1, $2, $3) RETURNING id",
		name, c.CreatedAt, nullID(staffID)).Scan(&c.ID)
	if isUnique(err) {
		return Class{}, ErrExists
	}
	return c, err
}

// ListClasses lists every class, A to Z, with how many students each has.
func (s *Store) ListClasses(ctx context.Context) ([]Class, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT c.id, c.name, c.created_at, COUNT(st.id) FROM classes c
		LEFT JOIN students st ON st.class_id = c.id
		GROUP BY c.id ORDER BY lower(c.name)`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Class{}
	for rows.Next() {
		var c Class
		if err := rows.Scan(&c.ID, &c.Name, &c.CreatedAt, &c.Students); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

// GetClass loads one class.
func (s *Store) GetClass(ctx context.Context, id int64) (Class, error) {
	var c Class
	err := s.db.QueryRowContext(ctx, `
		SELECT c.id, c.name, c.created_at, (SELECT COUNT(*) FROM students WHERE class_id = c.id)
		FROM classes c WHERE c.id = $1`, id).Scan(&c.ID, &c.Name, &c.CreatedAt, &c.Students)
	if errors.Is(err, sql.ErrNoRows) {
		return Class{}, ErrNotFound
	}
	return c, err
}

// DeleteClass deletes a class and everything its students saved.
func (s *Store) DeleteClass(ctx context.Context, id int64) error {
	return s.execOne(ctx, "DELETE FROM classes WHERE id = $1", id)
}

// NewStudentCode is a student to add: its code hash (the code itself is
// only ever shown to the teacher once).
type NewStudentCode struct {
	Number   int
	CodeHash string
}

// AddStudents adds students to a class with the next free numbers. hashes
// are the keyed hashes of their codes. It returns the numbers given, in
// order. ErrExists means a code hash clashed (generate new codes and retry).
func (s *Store) AddStudents(ctx context.Context, classID int64, hashes []string, settings json.RawMessage) ([]int, error) {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()
	// Lock the class row so two teachers adding at once get different numbers.
	var exists int64
	if err := tx.QueryRowContext(ctx, "SELECT id FROM classes WHERE id = $1 FOR UPDATE", classID).Scan(&exists); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	var next int
	if err := tx.QueryRowContext(ctx, "SELECT COALESCE(MAX(number), 0) + 1 FROM students WHERE class_id = $1", classID).Scan(&next); err != nil {
		return nil, err
	}
	if len(settings) == 0 {
		settings = json.RawMessage("{}")
	}
	now := s.millis()
	numbers := make([]int, 0, len(hashes))
	for i, h := range hashes {
		n := next + i
		if _, err := tx.ExecContext(ctx,
			"INSERT INTO students (class_id, number, code_hash, settings, created_at) VALUES ($1, $2, $3, $4, $5)",
			classID, n, h, string(settings), now); err != nil {
			if isUnique(err) {
				return nil, ErrExists
			}
			return nil, err
		}
		numbers = append(numbers, n)
	}
	return numbers, tx.Commit()
}

// StudentByCodeHash finds the student with this code.
func (s *Store) StudentByCodeHash(ctx context.Context, hash string) (int64, error) {
	var id int64
	err := s.db.QueryRowContext(ctx, "SELECT id FROM students WHERE code_hash = $1", hash).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, ErrNotFound
	}
	return id, err
}

// SetStudentCode gives a student a new code (the old one stops working and
// they are signed out everywhere).
func (s *Store) SetStudentCode(ctx context.Context, id int64, hash string) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	res, err := tx.ExecContext(ctx, "UPDATE students SET code_hash = $1 WHERE id = $2", hash, id)
	if isUnique(err) {
		return ErrExists
	}
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrNotFound
	}
	if _, err := tx.ExecContext(ctx, "DELETE FROM student_sessions WHERE student_id = $1", id); err != nil {
		return err
	}
	return tx.Commit()
}

// ListStudents lists a class's students by number.
func (s *Store) ListStudents(ctx context.Context, classID int64) ([]StudentSummary, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT st.id, st.number, st.last_seen,
		  (SELECT COUNT(*) FROM (
		     SELECT project_id FROM sketches WHERE student_id = st.id
		     UNION SELECT project_id FROM progress WHERE student_id = st.id) p)
		FROM students st WHERE st.class_id = $1 ORDER BY st.number`, classID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []StudentSummary{}
	for rows.Next() {
		var st StudentSummary
		if err := rows.Scan(&st.ID, &st.Number, &st.LastSeen, &st.Projects); err != nil {
			return nil, err
		}
		out = append(out, st)
	}
	return out, rows.Err()
}

// GetStudent loads a student.
func (s *Store) GetStudent(ctx context.Context, id int64) (Student, error) {
	var st Student
	var settings string
	err := s.db.QueryRowContext(ctx, `
		SELECT st.id, st.class_id, c.name, st.number, st.settings, st.created_at, st.last_seen
		FROM students st JOIN classes c ON c.id = st.class_id WHERE st.id = $1`, id).
		Scan(&st.ID, &st.ClassID, &st.ClassName, &st.Number, &settings, &st.CreatedAt, &st.LastSeen)
	if errors.Is(err, sql.ErrNoRows) {
		return Student{}, ErrNotFound
	}
	st.Settings = json.RawMessage(settings)
	return st, err
}

// DeleteStudent deletes a student and everything they saved.
func (s *Store) DeleteStudent(ctx context.Context, id int64) error {
	return s.execOne(ctx, "DELETE FROM students WHERE id = $1", id)
}

// UpdateSettings replaces a student's settings (already validated JSON).
func (s *Store) UpdateSettings(ctx context.Context, id int64, settings json.RawMessage) error {
	return s.execOne(ctx, "UPDATE students SET settings = $1 WHERE id = $2", string(settings), id)
}

// Touch records that a student was just seen.
func (s *Store) Touch(ctx context.Context, id int64) error {
	return s.execOne(ctx, "UPDATE students SET last_seen = $1 WHERE id = $2", s.millis(), id)
}

// CreateStudentSession stores a student's sign-in (only a hash of the token).
func (s *Store) CreateStudentSession(ctx context.Context, tokenHash string, studentID int64, ttl time.Duration) error {
	now := s.now()
	_, err := s.db.ExecContext(ctx,
		"INSERT INTO student_sessions (token_hash, student_id, created_at, expires_at) VALUES ($1, $2, $3, $4)",
		tokenHash, studentID, now.UnixMilli(), now.Add(ttl).UnixMilli())
	return err
}

// StudentSession returns the student a live session belongs to.
func (s *Store) StudentSession(ctx context.Context, tokenHash string) (int64, error) {
	var id int64
	err := s.db.QueryRowContext(ctx,
		"SELECT student_id FROM student_sessions WHERE token_hash = $1 AND expires_at > $2", tokenHash, s.millis()).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, ErrNotFound
	}
	return id, err
}

// DeleteStudentSession signs a student out.
func (s *Store) DeleteStudentSession(ctx context.Context, tokenHash string) error {
	_, err := s.db.ExecContext(ctx, "DELETE FROM student_sessions WHERE token_hash = $1", tokenHash)
	return err
}

// DeleteExpiredSessions tidies up old sign-ins (students and staff).
func (s *Store) DeleteExpiredSessions(ctx context.Context) error {
	now := s.millis()
	if _, err := s.db.ExecContext(ctx, "DELETE FROM student_sessions WHERE expires_at <= $1", now); err != nil {
		return err
	}
	_, err := s.db.ExecContext(ctx, "DELETE FROM staff_sessions WHERE expires_at <= $1", now)
	return err
}

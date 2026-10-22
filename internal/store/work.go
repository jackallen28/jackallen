package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"regexp"
	"unicode/utf8"
)

// Sketch is a student's code for one project.
type Sketch struct {
	ProjectID string `json:"project_id"`
	Code      string `json:"code"`
	UpdatedAt int64  `json:"updated_at"` // Unix milliseconds
}

// Progress is a student's progress through one project (steps, stars, hints,
// wiring done...). The server stores it as a JSON object.
type Progress struct {
	ProjectID string          `json:"project_id"`
	Data      json.RawMessage `json:"data"`
	UpdatedAt int64           `json:"updated_at"`
}

// PutSketch saves a sketch and returns when it was saved.
func (s *Store) PutSketch(ctx context.Context, studentID int64, projectID, code string) (int64, error) {
	now := s.millis()
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO sketches (student_id, project_id, code, updated_at) VALUES (?, ?, ?, ?)
		ON CONFLICT (student_id, project_id) DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at`,
		studentID, projectID, code, now)
	return now, err
}

// GetSketch loads one sketch.
func (s *Store) GetSketch(ctx context.Context, studentID int64, projectID string) (Sketch, error) {
	sk := Sketch{ProjectID: projectID}
	err := s.db.QueryRowContext(ctx,
		"SELECT code, updated_at FROM sketches WHERE student_id = ? AND project_id = ?", studentID, projectID).
		Scan(&sk.Code, &sk.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Sketch{}, ErrNotFound
	}
	return sk, err
}

// ListSketches loads all of a student's sketches.
func (s *Store) ListSketches(ctx context.Context, studentID int64) ([]Sketch, error) {
	rows, err := s.db.QueryContext(ctx,
		"SELECT project_id, code, updated_at FROM sketches WHERE student_id = ? ORDER BY project_id", studentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Sketch{}
	for rows.Next() {
		var sk Sketch
		if err := rows.Scan(&sk.ProjectID, &sk.Code, &sk.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, sk)
	}
	return out, rows.Err()
}

// PutProgress saves progress for a project and returns when it was saved.
func (s *Store) PutProgress(ctx context.Context, studentID int64, projectID string, data json.RawMessage) (int64, error) {
	now := s.millis()
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO progress (student_id, project_id, data, updated_at) VALUES (?, ?, ?, ?)
		ON CONFLICT (student_id, project_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at`,
		studentID, projectID, string(data), now)
	return now, err
}

// ListProgress loads a student's progress in every project.
func (s *Store) ListProgress(ctx context.Context, studentID int64) ([]Progress, error) {
	rows, err := s.db.QueryContext(ctx,
		"SELECT project_id, data, updated_at FROM progress WHERE student_id = ? ORDER BY project_id", studentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Progress{}
	for rows.Next() {
		var p Progress
		var data string
		if err := rows.Scan(&p.ProjectID, &data, &p.UpdatedAt); err != nil {
			return nil, err
		}
		p.Data = json.RawMessage(data)
		out = append(out, p)
	}
	return out, rows.Err()
}

// ImportWork writes sketches and progress from a save file in one
// transaction, keeping the times they were saved in the file.
func (s *Store) ImportWork(ctx context.Context, studentID int64, sketches []Sketch, progress []Progress) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, sk := range sketches {
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO sketches (student_id, project_id, code, updated_at) VALUES (?, ?, ?, ?)
			ON CONFLICT (student_id, project_id) DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at`,
			studentID, sk.ProjectID, sk.Code, sk.UpdatedAt); err != nil {
			return err
		}
	}
	for _, p := range progress {
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO progress (student_id, project_id, data, updated_at) VALUES (?, ?, ?, ?)
			ON CONFLICT (student_id, project_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at`,
			studentID, p.ProjectID, string(p.Data), p.UpdatedAt); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// Limits on what one student can store.
const (
	MaxSketchBytes   = 100 << 10 // one sketch
	MaxProgressBytes = 64 << 10  // one project's progress
)

var projectIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,63}$`)

// ValidProjectID reports whether id can name a project's work ("freeplay"
// and ids from content/projects). It doesn't need to be a current project:
// work for a project a teacher removed is kept.
func ValidProjectID(id string) bool { return projectIDPattern.MatchString(id) }

// ValidProgress reports whether data is a JSON object small enough to store.
func ValidProgress(data []byte) bool {
	if len(data) > MaxProgressBytes || !json.Valid(data) {
		return false
	}
	var obj map[string]json.RawMessage
	return json.Unmarshal(data, &obj) == nil && obj != nil
}

// ValidSketch reports whether code is small enough and valid text.
func ValidSketch(code string) bool {
	return len(code) <= MaxSketchBytes && utf8.ValidString(code)
}

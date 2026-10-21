package store

import (
	"context"
	"database/sql"
	"errors"
	"time"
)

// CreateSession stores a login. Only a hash of the cookie's token is kept.
func (s *Store) CreateSession(ctx context.Context, tokenHash string, studentID int64, ttl time.Duration) error {
	now := s.now()
	_, err := s.db.ExecContext(ctx,
		"INSERT INTO sessions (token_hash, student_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
		tokenHash, studentID, now.UnixMilli(), now.Add(ttl).UnixMilli())
	return err
}

// SessionStudent returns the student a live session belongs to.
func (s *Store) SessionStudent(ctx context.Context, tokenHash string) (int64, error) {
	var id int64
	err := s.db.QueryRowContext(ctx,
		"SELECT student_id FROM sessions WHERE token_hash = ? AND expires_at > ?", tokenHash, s.millis()).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, ErrNotFound
	}
	return id, err
}

// DeleteSession logs a session out.
func (s *Store) DeleteSession(ctx context.Context, tokenHash string) error {
	_, err := s.db.ExecContext(ctx, "DELETE FROM sessions WHERE token_hash = ?", tokenHash)
	return err
}

// DeleteStudentSessions logs a student out everywhere.
func (s *Store) DeleteStudentSessions(ctx context.Context, studentID int64) error {
	_, err := s.db.ExecContext(ctx, "DELETE FROM sessions WHERE student_id = ?", studentID)
	return err
}

// DeleteExpiredSessions tidies up old logins.
func (s *Store) DeleteExpiredSessions(ctx context.Context) error {
	_, err := s.db.ExecContext(ctx, "DELETE FROM sessions WHERE expires_at <= ?", s.millis())
	return err
}

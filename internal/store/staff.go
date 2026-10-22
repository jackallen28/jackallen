package store

import (
	"context"
	"database/sql"
	"errors"
	"time"
)

// Staff is a teacher's account. Every account needs a password and an
// authenticator app (TOTP); admins can also invite and remove staff.
type Staff struct {
	ID                int64  `json:"id"`
	Email             string `json:"email"`
	PasswordHash      string `json:"-"`
	TOTPSecret        string `json:"-"` // encrypted
	TOTPEnabled       bool   `json:"totp_enabled"`
	TOTPLastStep      int64  `json:"-"`
	IsAdmin           bool   `json:"is_admin"`
	FailedLogins      int    `json:"-"`
	LockedUntil       int64  `json:"-"`
	CreatedAt         int64  `json:"created_at"`
	LastLogin         int64  `json:"last_login"`
	PasswordChangedAt int64  `json:"-"`
}

const staffColumns = `id, email, password_hash, totp_secret, totp_enabled, totp_last_step, is_admin,
	failed_logins, locked_until, created_at, last_login, password_changed_at`

func scanStaff(row interface{ Scan(...any) error }) (Staff, error) {
	var st Staff
	err := row.Scan(&st.ID, &st.Email, &st.PasswordHash, &st.TOTPSecret, &st.TOTPEnabled, &st.TOTPLastStep,
		&st.IsAdmin, &st.FailedLogins, &st.LockedUntil, &st.CreatedAt, &st.LastLogin, &st.PasswordChangedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Staff{}, ErrNotFound
	}
	return st, err
}

// StaffCount says how many staff accounts exist (0: the first admin hasn't been set up).
func (s *Store) StaffCount(ctx context.Context) (int, error) {
	var n int
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM staff").Scan(&n)
	return n, err
}

// CreateStaff adds an account (its authenticator isn't set up yet).
// With onlyIfNone, it fails with ErrExists if any staff account exists
// (for the very first admin).
func (s *Store) CreateStaff(ctx context.Context, email, passwordHash, totpSecret string, isAdmin, onlyIfNone bool) (Staff, error) {
	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return Staff{}, err
	}
	defer tx.Rollback()
	if onlyIfNone {
		var n int
		if err := tx.QueryRowContext(ctx, "SELECT COUNT(*) FROM staff").Scan(&n); err != nil {
			return Staff{}, err
		}
		if n > 0 {
			return Staff{}, ErrExists
		}
	}
	now := s.millis()
	st, err := scanStaff(tx.QueryRowContext(ctx, `
		INSERT INTO staff (email, password_hash, totp_secret, is_admin, created_at, password_changed_at)
		VALUES ($1, $2, $3, $4, $5, $5) RETURNING `+staffColumns,
		email, passwordHash, totpSecret, isAdmin, now))
	if isUnique(err) {
		return Staff{}, ErrExists
	}
	if err != nil {
		return Staff{}, err
	}
	return st, tx.Commit()
}

// StaffByEmail finds an account by email (any case).
func (s *Store) StaffByEmail(ctx context.Context, email string) (Staff, error) {
	return scanStaff(s.db.QueryRowContext(ctx, "SELECT "+staffColumns+" FROM staff WHERE lower(email) = lower($1)", email))
}

// GetStaff loads an account.
func (s *Store) GetStaff(ctx context.Context, id int64) (Staff, error) {
	return scanStaff(s.db.QueryRowContext(ctx, "SELECT "+staffColumns+" FROM staff WHERE id = $1", id))
}

// ListStaff lists every account.
func (s *Store) ListStaff(ctx context.Context) ([]Staff, error) {
	rows, err := s.db.QueryContext(ctx, "SELECT "+staffColumns+" FROM staff ORDER BY lower(email)")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Staff{}
	for rows.Next() {
		st, err := scanStaff(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, st)
	}
	return out, rows.Err()
}

// DeleteStaff removes an account (and signs it out).
func (s *Store) DeleteStaff(ctx context.Context, id int64) error {
	return s.execOne(ctx, "DELETE FROM staff WHERE id = $1", id)
}

// RecordLoginFailure counts a wrong password or code; after max failures in a
// row the account is locked for lockFor. It returns the new lock time (0: not locked).
func (s *Store) RecordLoginFailure(ctx context.Context, id int64, max int, lockFor time.Duration) (int64, error) {
	var failed int
	if err := s.db.QueryRowContext(ctx,
		"UPDATE staff SET failed_logins = failed_logins + 1 WHERE id = $1 RETURNING failed_logins", id).Scan(&failed); err != nil {
		return 0, err
	}
	if failed < max {
		return 0, nil
	}
	until := s.now().Add(lockFor).UnixMilli()
	_, err := s.db.ExecContext(ctx, "UPDATE staff SET failed_logins = 0, locked_until = $1 WHERE id = $2", until, id)
	return until, err
}

// RecordLoginSuccess clears the failure count and notes the sign-in.
func (s *Store) RecordLoginSuccess(ctx context.Context, id int64) error {
	return s.execOne(ctx, "UPDATE staff SET failed_logins = 0, locked_until = 0, last_login = $1 WHERE id = $2", s.millis(), id)
}

// SetStaffPassword replaces a password and signs the account out everywhere
// except keepSession (a token hash, or "").
func (s *Store) SetStaffPassword(ctx context.Context, id int64, hash, keepSession string) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, "UPDATE staff SET password_hash = $1, password_changed_at = $2 WHERE id = $3", hash, s.millis(), id); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, "DELETE FROM staff_sessions WHERE staff_id = $1 AND token_hash <> $2", id, keepSession); err != nil {
		return err
	}
	return tx.Commit()
}

// SetTOTPSecret stores a new (encrypted) authenticator secret, not yet enabled.
func (s *Store) SetTOTPSecret(ctx context.Context, id int64, secret string) error {
	return s.execOne(ctx, "UPDATE staff SET totp_secret = $1, totp_enabled = FALSE, totp_last_step = 0 WHERE id = $2", secret, id)
}

// EnableTOTP turns the authenticator on.
func (s *Store) EnableTOTP(ctx context.Context, id int64) error {
	return s.execOne(ctx, "UPDATE staff SET totp_enabled = TRUE WHERE id = $1", id)
}

// UseTOTPStep records that an authenticator code (its time step) has been
// used. It returns false if that step (or a later one) was already used, so
// a code can never be used twice.
func (s *Store) UseTOTPStep(ctx context.Context, id, step int64) (bool, error) {
	res, err := s.db.ExecContext(ctx, "UPDATE staff SET totp_last_step = $1 WHERE id = $2 AND totp_last_step < $1", step, id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n == 1, err
}

// SetRecoveryCodes replaces an account's recovery codes (hashes).
func (s *Store) SetRecoveryCodes(ctx context.Context, id int64, hashes []string) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, "DELETE FROM staff_recovery_codes WHERE staff_id = $1", id); err != nil {
		return err
	}
	for _, h := range hashes {
		if _, err := tx.ExecContext(ctx, "INSERT INTO staff_recovery_codes (staff_id, code_hash) VALUES ($1, $2)", id, h); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// UseRecoveryCode marks a recovery code used. It returns false if the code
// isn't one of the account's unused codes.
func (s *Store) UseRecoveryCode(ctx context.Context, id int64, hash string) (bool, error) {
	res, err := s.db.ExecContext(ctx,
		"UPDATE staff_recovery_codes SET used_at = $1 WHERE staff_id = $2 AND code_hash = $3 AND used_at = 0", s.millis(), id, hash)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n == 1, err
}

// RecoveryCodesLeft counts unused recovery codes.
func (s *Store) RecoveryCodesLeft(ctx context.Context, id int64) (int, error) {
	var n int
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM staff_recovery_codes WHERE staff_id = $1 AND used_at = 0", id).Scan(&n)
	return n, err
}

// StaffSession is a staff sign-in. MFAAt is 0 until the authenticator code
// (or a recovery code) has been given.
type StaffSession struct {
	StaffID   int64
	CreatedAt int64
	ExpiresAt int64
	LastSeen  int64
	MFAAt     int64
}

// CreateStaffSession stores a sign-in (only a hash of the token).
func (s *Store) CreateStaffSession(ctx context.Context, tokenHash string, staffID int64, ttl time.Duration, mfaAt int64, ip string) error {
	now := s.now()
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO staff_sessions (token_hash, staff_id, created_at, expires_at, last_seen, mfa_at, ip)
		VALUES ($1, $2, $3, $4, $3, $5, $6)`,
		tokenHash, staffID, now.UnixMilli(), now.Add(ttl).UnixMilli(), mfaAt, ip)
	return err
}

// GetStaffSession loads a live session.
func (s *Store) GetStaffSession(ctx context.Context, tokenHash string) (StaffSession, error) {
	var ss StaffSession
	err := s.db.QueryRowContext(ctx,
		"SELECT staff_id, created_at, expires_at, last_seen, mfa_at FROM staff_sessions WHERE token_hash = $1 AND expires_at > $2",
		tokenHash, s.millis()).Scan(&ss.StaffID, &ss.CreatedAt, &ss.ExpiresAt, &ss.LastSeen, &ss.MFAAt)
	if errors.Is(err, sql.ErrNoRows) {
		return StaffSession{}, ErrNotFound
	}
	return ss, err
}

// TouchStaffSession records activity (for the idle time-out).
func (s *Store) TouchStaffSession(ctx context.Context, tokenHash string) error {
	_, err := s.db.ExecContext(ctx, "UPDATE staff_sessions SET last_seen = $1 WHERE token_hash = $2", s.millis(), tokenHash)
	return err
}

// MarkStaffMFA records that the authenticator code was just given.
func (s *Store) MarkStaffMFA(ctx context.Context, tokenHash string) error {
	return s.execOne(ctx, "UPDATE staff_sessions SET mfa_at = $1 WHERE token_hash = $2", s.millis(), tokenHash)
}

// DeleteStaffSession signs a session out.
func (s *Store) DeleteStaffSession(ctx context.Context, tokenHash string) error {
	_, err := s.db.ExecContext(ctx, "DELETE FROM staff_sessions WHERE token_hash = $1", tokenHash)
	return err
}

// Invite is a one-time link for a new staff account.
type Invite struct {
	Email     string `json:"email"`
	IsAdmin   bool   `json:"is_admin"`
	ExpiresAt int64  `json:"expires_at"`
}

// CreateInvite stores an invite (only a hash of its token).
func (s *Store) CreateInvite(ctx context.Context, tokenHash, email string, isAdmin bool, createdBy int64, ttl time.Duration) error {
	now := s.now()
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO staff_invites (token_hash, email, is_admin, created_by, created_at, expires_at)
		VALUES ($1, $2, $3, $4, $5, $6)`,
		tokenHash, email, isAdmin, createdBy, now.UnixMilli(), now.Add(ttl).UnixMilli())
	return err
}

// GetInvite loads an unused, unexpired invite.
func (s *Store) GetInvite(ctx context.Context, tokenHash string) (Invite, error) {
	var inv Invite
	err := s.db.QueryRowContext(ctx,
		"SELECT email, is_admin, expires_at FROM staff_invites WHERE token_hash = $1 AND used_at = 0 AND expires_at > $2",
		tokenHash, s.millis()).Scan(&inv.Email, &inv.IsAdmin, &inv.ExpiresAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Invite{}, ErrNotFound
	}
	return inv, err
}

// UseInvite marks an invite used; false if it was already used or has expired.
func (s *Store) UseInvite(ctx context.Context, tokenHash string) (bool, error) {
	res, err := s.db.ExecContext(ctx,
		"UPDATE staff_invites SET used_at = $1 WHERE token_hash = $2 AND used_at = 0 AND expires_at > $1", s.millis(), tokenHash)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n == 1, err
}

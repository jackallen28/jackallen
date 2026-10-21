// Package auth handles picture passwords, login tokens and rate limits.
//
// A picture password is 3 of the 9 pictures, tapped in order (504 possible
// passwords). It isn't meant to stop a determined attacker, only to stop
// classmates opening each other's work on a shared server, so it is paired
// with a lockout: 5 wrong tries locks that profile for a minute.
package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"slices"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/bcrypt"
)

// Pictures are the 9 pictures on the picture-password grid. The ids are
// stored (hashed), so never rename or remove one; the UI draws them.
var Pictures = []string{"apple", "cat", "fish", "rocket", "star", "sun", "tree", "car", "umbrella"}

// PictureCount is how many pictures make a password.
const PictureCount = 3

// ErrBadPictures means a picture password isn't 3 different known pictures.
var ErrBadPictures = errors.New("pick 3 different pictures")

// ValidPictures checks a picture password's shape.
func ValidPictures(p []string) error {
	if len(p) != PictureCount {
		return ErrBadPictures
	}
	for i, id := range p {
		if !slices.Contains(Pictures, id) || slices.Contains(p[:i], id) {
			return ErrBadPictures
		}
	}
	return nil
}

func picturesSecret(p []string) []byte {
	return []byte("circuitpath-pictures-v1:" + strings.Join(p, ","))
}

// HashPictures hashes a picture password for storage.
func HashPictures(p []string) (string, error) {
	if err := ValidPictures(p); err != nil {
		return "", err
	}
	h, err := bcrypt.GenerateFromPassword(picturesSecret(p), bcrypt.DefaultCost)
	return string(h), err
}

// CheckPictures reports whether p matches a stored hash.
func CheckPictures(hash string, p []string) bool {
	if ValidPictures(p) != nil {
		return false
	}
	return bcrypt.CompareHashAndPassword([]byte(hash), picturesSecret(p)) == nil
}

// NewToken makes a random login token and the hash to store for it.
func NewToken() (token, hash string, err error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", "", err
	}
	token = base64.RawURLEncoding.EncodeToString(b)
	return token, HashToken(token), nil
}

// HashToken hashes a login token so the database never holds a usable one.
func HashToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

// Lockout locks a key (a profile) after too many wrong tries in a row.
type Lockout struct {
	MaxFails int
	LockFor  time.Duration
	Now      func() time.Time

	mu      sync.Mutex
	entries map[string]*lockEntry
}

type lockEntry struct {
	fails       int
	lockedUntil time.Time
}

// NewLockout makes a Lockout: maxFails wrong tries locks for lockFor.
func NewLockout(maxFails int, lockFor time.Duration) *Lockout {
	return &Lockout{MaxFails: maxFails, LockFor: lockFor, Now: time.Now, entries: map[string]*lockEntry{}}
}

// Wait returns how long key must wait before trying again (0: try now).
func (l *Lockout) Wait(key string) time.Duration {
	l.mu.Lock()
	defer l.mu.Unlock()
	e := l.entries[key]
	if e == nil {
		return 0
	}
	if d := e.lockedUntil.Sub(l.Now()); d > 0 {
		return d
	}
	return 0
}

// Fail records a wrong try and returns how long key is now locked for.
func (l *Lockout) Fail(key string) time.Duration {
	l.mu.Lock()
	defer l.mu.Unlock()
	e := l.entries[key]
	if e == nil {
		e = &lockEntry{}
		l.entries[key] = e
	}
	e.fails++
	if e.fails >= l.MaxFails {
		e.fails = 0
		e.lockedUntil = l.Now().Add(l.LockFor)
		return l.LockFor
	}
	return 0
}

// Succeed clears key's wrong tries.
func (l *Lockout) Succeed(key string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	delete(l.entries, key)
}

// Window allows at most Max events per key in each Period (for example,
// profiles created from one laptop in an hour).
type Window struct {
	Max    int
	Period time.Duration
	Now    func() time.Time

	mu     sync.Mutex
	events map[string][]time.Time
}

// NewWindow makes a Window.
func NewWindow(max int, period time.Duration) *Window {
	return &Window{Max: max, Period: period, Now: time.Now, events: map[string][]time.Time{}}
}

// Allow records an event for key, or returns false if key is over the limit.
func (w *Window) Allow(key string) bool {
	w.mu.Lock()
	defer w.mu.Unlock()
	now := w.Now()
	cut := now.Add(-w.Period)
	ev := slices.DeleteFunc(w.events[key], func(t time.Time) bool { return !t.After(cut) })
	if len(ev) >= w.Max {
		w.events[key] = ev
		return false
	}
	w.events[key] = append(ev, now)
	return true
}

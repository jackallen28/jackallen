// Package auth handles sign-in: student codes, staff passwords (Argon2id),
// authenticator codes (TOTP), recovery codes, login tokens and rate limits.
//
// Students sign in with a code the teacher hands out (no names anywhere).
// Staff sign in with an email, a long password and an authenticator app.
package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"slices"
	"sync"
	"time"
)

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

// Lockout locks a key (an address) after too many wrong tries in a row.
type Lockout struct {
	MaxFails int
	LockFor  time.Duration
	Now      func() time.Time

	mu      sync.Mutex
	entries map[string]*lockEntry
}

type lockEntry struct {
	fails       int
	lastFail    time.Time
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
	e.lastFail = l.Now()
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

// Sweep forgets keys with no recent wrong tries (so memory doesn't grow).
func (l *Lockout) Sweep(olderThan time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.Now()
	for k, e := range l.entries {
		if now.After(e.lockedUntil) && now.Sub(e.lastFail) > olderThan {
			delete(l.entries, k)
		}
	}
}

// Window allows at most Max events per key in each Period (for example,
// wrong student codes from one address in a minute).
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

func (w *Window) recent(key string, now time.Time) []time.Time {
	cut := now.Add(-w.Period)
	return slices.DeleteFunc(w.events[key], func(t time.Time) bool { return !t.After(cut) })
}

// Allow records an event for key, or returns false if key is over the limit.
func (w *Window) Allow(key string) bool {
	w.mu.Lock()
	defer w.mu.Unlock()
	now := w.Now()
	ev := w.recent(key, now)
	if len(ev) >= w.Max {
		w.events[key] = ev
		return false
	}
	w.events[key] = append(ev, now)
	return true
}

// Full reports whether key is at the limit, without recording an event.
func (w *Window) Full(key string) bool {
	w.mu.Lock()
	defer w.mu.Unlock()
	ev := w.recent(key, w.Now())
	w.events[key] = ev
	return len(ev) >= w.Max
}

// Sweep forgets keys with no events in the last Period.
func (w *Window) Sweep() {
	w.mu.Lock()
	defer w.mu.Unlock()
	now := w.Now()
	for k := range w.events {
		if ev := w.recent(k, now); len(ev) == 0 {
			delete(w.events, k)
		} else {
			w.events[k] = ev
		}
	}
}

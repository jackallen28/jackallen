package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"strings"
	"sync"
	"unicode/utf8"

	"golang.org/x/crypto/argon2"
)

// Argon2id settings (OWASP's recommendation is at least 19 MiB, 2 passes).
// They are stored with each hash, so they can be raised later.
const (
	argonTime    = 3
	argonMemory  = 64 * 1024 // KiB
	argonThreads = 1
	argonKeyLen  = 32
)

// MinPasswordLength and MaxPasswordLength bound staff passwords.
const (
	MinPasswordLength = 12
	MaxPasswordLength = 128
)

// hashSlots stops many logins at once using up the server's memory
// (each hash takes 64 MiB for a moment).
var hashSlots = make(chan struct{}, 2)

// HashPassword hashes a staff password with Argon2id (PHC string format).
func HashPassword(pw string) (string, error) {
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	hashSlots <- struct{}{}
	key := argon2.IDKey([]byte(pw), salt, argonTime, argonMemory, argonThreads, argonKeyLen)
	<-hashSlots
	b64 := base64.RawStdEncoding
	return fmt.Sprintf("$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s",
		argon2.Version, argonMemory, argonTime, argonThreads, b64.EncodeToString(salt), b64.EncodeToString(key)), nil
}

// CheckPassword reports whether pw matches a stored hash (in constant time).
func CheckPassword(hash, pw string) bool {
	parts := strings.Split(hash, "$")
	if len(parts) != 6 || parts[1] != "argon2id" {
		return false
	}
	var v int
	var m uint32
	var t uint32
	var p uint8
	if _, err := fmt.Sscanf(parts[2], "v=%d", &v); err != nil || v != argon2.Version {
		return false
	}
	if _, err := fmt.Sscanf(parts[3], "m=%d,t=%d,p=%d", &m, &t, &p); err != nil || m == 0 || m > 1<<20 || t == 0 || t > 20 || p == 0 {
		return false
	}
	b64 := base64.RawStdEncoding
	salt, err := b64.DecodeString(parts[4])
	if err != nil {
		return false
	}
	want, err := b64.DecodeString(parts[5])
	if err != nil || len(want) == 0 {
		return false
	}
	hashSlots <- struct{}{}
	got := argon2.IDKey([]byte(pw), salt, t, m, p, uint32(len(want)))
	<-hashSlots
	return subtle.ConstantTimeCompare(got, want) == 1
}

var (
	dummyOnce sync.Once
	dummyHash string
)

// DummyCheck takes as long as CheckPassword, for an email with no account,
// so the time taken doesn't give away which emails have accounts.
func DummyCheck(pw string) {
	dummyOnce.Do(func() { dummyHash, _ = HashPassword("circuitpath-dummy-password") })
	CheckPassword(dummyHash, pw)
}

// ErrWeakPassword explains why a password was refused.
type ErrWeakPassword struct{ Reason string }

func (e ErrWeakPassword) Error() string { return e.Reason }

// common are passwords (and patterns) people often pick; any password that is
// mostly one of these is refused.
var common = []string{
	"password", "passw0rd", "123456", "12345678", "qwerty", "letmein", "welcome", "iloveyou",
	"admin", "teacher", "school", "student", "circuitpath", "arduino", "abc123", "monkey",
	"dragon", "football", "baseball", "sunshine", "princess", "trustno1", "changeme", "banyule",
	"nillumbik", "bnts", "qwertyuiop", "asdfghjkl", "zxcvbnm", "1q2w3e4r", "111111", "000000",
}

// CheckPasswordPolicy checks a new staff password: at least 12 characters,
// not too short or too long, not mostly a common password, not the email.
func CheckPasswordPolicy(pw, email string) error {
	n := utf8.RuneCountInString(pw)
	if n < MinPasswordLength {
		return ErrWeakPassword{fmt.Sprintf("Use at least %d characters. A short sentence you'll remember works well.", MinPasswordLength)}
	}
	if len(pw) > MaxPasswordLength {
		return ErrWeakPassword{fmt.Sprintf("Use at most %d characters.", MaxPasswordLength)}
	}
	lower := strings.ToLower(pw)
	if local, _, ok := strings.Cut(strings.ToLower(email), "@"); ok && len(local) >= 3 && strings.Contains(lower, local) {
		return ErrWeakPassword{"Don't use your email address in your password."}
	}
	rest := lower
	for _, c := range common {
		rest = strings.ReplaceAll(rest, c, "")
	}
	if utf8.RuneCountInString(rest) < 8 {
		return ErrWeakPassword{"That password is too easy to guess. Try a few unrelated words."}
	}
	distinct := map[rune]bool{}
	for _, r := range pw {
		distinct[r] = true
	}
	if len(distinct) < 6 {
		return ErrWeakPassword{"That password repeats itself too much. Try a few unrelated words."}
	}
	return nil
}

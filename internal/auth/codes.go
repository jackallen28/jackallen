package auth

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"math/big"
	"strings"
)

// CodeAlphabet is the characters in student and recovery codes: no 0/O,
// 1/I/L or U/V, so codes are easy to read off a printed sheet.
const CodeAlphabet = "23456789ABCDEFGHJKMNPQRSTWXYZ"

// CodeLength is how many characters a student code has (shown as XXXX-XXXX).
// 29^8 is about 500 billion codes, so guessing one is hopeless with rate limits.
const CodeLength = 8

// ErrBadCode means a code isn't the right shape.
var ErrBadCode = errors.New("that doesn't look like a student code")

func randomCode(n int) (string, error) {
	max := big.NewInt(int64(len(CodeAlphabet)))
	b := make([]byte, n)
	for i := range b {
		k, err := rand.Int(rand.Reader, max)
		if err != nil {
			return "", err
		}
		b[i] = CodeAlphabet[k.Int64()]
	}
	return string(b), nil
}

// NewStudentCode makes a random student code, formatted XXXX-XXXX.
func NewStudentCode() (string, error) {
	c, err := randomCode(CodeLength)
	if err != nil {
		return "", err
	}
	return FormatCode(c), nil
}

// FormatCode writes a normalised code as XXXX-XXXX.
func FormatCode(c string) string {
	if len(c) != CodeLength {
		return c
	}
	return c[:4] + "-" + c[4:]
}

// NormaliseCode tidies what a student typed: any case, spaces and dashes are fine.
func NormaliseCode(s string) (string, error) {
	if len(s) > 32 {
		return "", ErrBadCode
	}
	var b strings.Builder
	for _, r := range strings.ToUpper(s) {
		switch r {
		case ' ', '-', '\t':
			continue
		}
		if !strings.ContainsRune(CodeAlphabet, r) {
			return "", ErrBadCode
		}
		b.WriteRune(r)
	}
	if b.Len() != CodeLength {
		return "", ErrBadCode
	}
	return b.String(), nil
}

// Keyed hashes the server keeps (a code can't be worked out from its hash
// without the server secret).
func keyedHash(secret []byte, purpose, value string) string {
	m := hmac.New(sha256.New, secret)
	m.Write([]byte(purpose))
	m.Write([]byte{0})
	m.Write([]byte(value))
	return hex.EncodeToString(m.Sum(nil))
}

// HashStudentCode is the stored form of a normalised student code.
func HashStudentCode(secret []byte, code string) string {
	return keyedHash(secret, "student-code-v1", code)
}

// RecoveryCodeCount is how many recovery codes a staff member gets.
const RecoveryCodeCount = 10

// NewRecoveryCodes makes a set of one-time recovery codes (XXXXX-XXXXX).
func NewRecoveryCodes() ([]string, error) {
	out := make([]string, RecoveryCodeCount)
	for i := range out {
		c, err := randomCode(10)
		if err != nil {
			return nil, err
		}
		out[i] = c[:5] + "-" + c[5:]
	}
	return out, nil
}

// HashRecoveryCode is the stored form of a recovery code (as typed: any case,
// with or without the dash). ok is false if it can't be one.
func HashRecoveryCode(secret []byte, code string) (hash string, ok bool) {
	c := strings.ToUpper(strings.NewReplacer("-", "", " ", "").Replace(code))
	if len(c) != 10 || strings.Trim(c, CodeAlphabet) != "" {
		return "", false
	}
	return keyedHash(secret, "recovery-code-v1", c), true
}

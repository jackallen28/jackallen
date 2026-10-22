package auth

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base32"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"
)

// TOTP (RFC 6238) as authenticator apps expect it: SHA-1, 6 digits, 30 seconds.
const (
	totpPeriod = 30
	totpDigits = 6
	totpSkew   = 1 // also accept the code just before and just after (clock drift)
)

var b32 = base32.StdEncoding.WithPadding(base32.NoPadding)

// NewTOTPSecret makes a random authenticator secret (base32, as apps show it).
func NewTOTPSecret() (string, error) {
	b := make([]byte, 20)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return b32.EncodeToString(b), nil
}

// TOTPURI is the otpauth:// link a QR code holds for an authenticator app.
func TOTPURI(secret, issuer, account string) string {
	label := url.PathEscape(issuer) + ":" + url.PathEscape(account)
	q := url.Values{}
	q.Set("secret", secret)
	q.Set("issuer", issuer)
	q.Set("algorithm", "SHA1")
	q.Set("digits", fmt.Sprint(totpDigits))
	q.Set("period", fmt.Sprint(totpPeriod))
	return "otpauth://totp/" + label + "?" + q.Encode()
}

// TOTPCode is the code for a time step.
func TOTPCode(secret string, step int64) (string, error) {
	key, err := b32.DecodeString(strings.ToUpper(secret))
	if err != nil {
		return "", err
	}
	var msg [8]byte
	binary.BigEndian.PutUint64(msg[:], uint64(step))
	m := hmac.New(sha1.New, key)
	m.Write(msg[:])
	sum := m.Sum(nil)
	off := sum[len(sum)-1] & 0x0f
	n := binary.BigEndian.Uint32(sum[off:off+4]) & 0x7fffffff
	return fmt.Sprintf("%0*d", totpDigits, n%1000000), nil
}

// TOTPStep is the time step for a moment.
func TOTPStep(t time.Time) int64 { return t.Unix() / totpPeriod }

// CheckTOTP checks a code typed at time now. It returns the step the code
// belongs to (to record, so the same code can't be used twice) and whether
// it matched.
func CheckTOTP(secret, code string, now time.Time) (int64, bool) {
	code = strings.ReplaceAll(strings.TrimSpace(code), " ", "")
	if len(code) != totpDigits {
		return 0, false
	}
	step := TOTPStep(now)
	matched, found := int64(0), false
	for d := int64(-totpSkew); d <= totpSkew; d++ {
		want, err := TOTPCode(secret, step+d)
		if err != nil {
			return 0, false
		}
		// Check every step (no early exit) so timing doesn't leak anything.
		if subtle.ConstantTimeCompare([]byte(want), []byte(code)) == 1 && !found {
			matched, found = step+d, true
		}
	}
	return matched, found
}

// Sealing keeps authenticator secrets encrypted in the database (AES-256-GCM
// with a key made from the server secret), so a copy of the database alone
// can't make codes.

func sealKey(serverSecret []byte) []byte {
	m := hmac.New(sha256.New, serverSecret)
	m.Write([]byte("totp-seal-v1"))
	return m.Sum(nil)
}

// Seal encrypts a value with the server secret.
func Seal(serverSecret []byte, plain string) (string, error) {
	block, err := aes.NewCipher(sealKey(serverSecret))
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	out := gcm.Seal(nonce, nonce, []byte(plain), nil)
	return "v1:" + base64.RawStdEncoding.EncodeToString(out), nil
}

// ErrUnseal means a sealed value is damaged or the server secret has changed.
var ErrUnseal = errors.New("can't decrypt (has CIRCUITPATH_SECRET changed?)")

// Unseal decrypts a value from Seal.
func Unseal(serverSecret []byte, sealed string) (string, error) {
	rest, ok := strings.CutPrefix(sealed, "v1:")
	if !ok {
		return "", ErrUnseal
	}
	raw, err := base64.RawStdEncoding.DecodeString(rest)
	if err != nil {
		return "", ErrUnseal
	}
	block, err := aes.NewCipher(sealKey(serverSecret))
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	if len(raw) < gcm.NonceSize() {
		return "", ErrUnseal
	}
	plain, err := gcm.Open(nil, raw[:gcm.NonceSize()], raw[gcm.NonceSize():], nil)
	if err != nil {
		return "", ErrUnseal
	}
	return string(plain), nil
}

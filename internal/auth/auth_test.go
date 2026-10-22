package auth

import (
	"strings"
	"testing"
	"time"
)

func TestTokens(t *testing.T) {
	a, ah, err := NewToken()
	if err != nil {
		t.Fatal(err)
	}
	b, _, _ := NewToken()
	if a == b || len(a) < 40 {
		t.Fatalf("weak tokens %q %q", a, b)
	}
	if HashToken(a) != ah || ah == a {
		t.Fatal("hash mismatch")
	}
}

func TestStudentCodes(t *testing.T) {
	seen := map[string]bool{}
	for range 200 {
		c, err := NewStudentCode()
		if err != nil {
			t.Fatal(err)
		}
		if len(c) != 9 || c[4] != '-' {
			t.Fatalf("bad shape %q", c)
		}
		n, err := NormaliseCode(c)
		if err != nil || FormatCode(n) != c {
			t.Fatalf("round trip %q -> %q %v", c, n, err)
		}
		if seen[c] {
			t.Fatalf("repeat %q", c)
		}
		seen[c] = true
	}
	for in, want := range map[string]string{
		"abcd-efgh":     "ABCDEFGH",
		" ab cd ef gh ": "ABCDEFGH",
		"23456789":      "23456789",
	} {
		if got, err := NormaliseCode(in); err != nil || got != want {
			t.Errorf("%q -> %q %v", in, got, err)
		}
	}
	for _, bad := range []string{"", "ABC", "ABCDEFGHJ", "ABCD-EFG0", "ABCD-EFGI", "<script>", strings.Repeat("A", 40)} {
		if _, err := NormaliseCode(bad); err == nil {
			t.Errorf("%q accepted", bad)
		}
	}
	k1, k2 := []byte("secret-one"), []byte("secret-two")
	if HashStudentCode(k1, "ABCDEFGH") == HashStudentCode(k2, "ABCDEFGH") {
		t.Fatal("hash doesn't depend on the secret")
	}
	if HashStudentCode(k1, "ABCDEFGH") == HashStudentCode(k1, "ABCDEFGJ") {
		t.Fatal("hash collision")
	}
}

func TestRecoveryCodes(t *testing.T) {
	k := []byte("k")
	codes, err := NewRecoveryCodes()
	if err != nil || len(codes) != RecoveryCodeCount {
		t.Fatal(codes, err)
	}
	h, ok := HashRecoveryCode(k, codes[0])
	h2, ok2 := HashRecoveryCode(k, strings.ToLower(strings.ReplaceAll(codes[0], "-", "")))
	if !ok || !ok2 || h != h2 {
		t.Fatal("recovery code forms don't match")
	}
	if _, ok := HashRecoveryCode(k, "short"); ok {
		t.Fatal("bad code accepted")
	}
}

func TestPasswords(t *testing.T) {
	h, err := HashPassword("correct horse battery staple")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(h, "$argon2id$v=19$m=65536,t=3,p=1$") {
		t.Fatalf("hash format %q", h)
	}
	if !CheckPassword(h, "correct horse battery staple") {
		t.Fatal("right password refused")
	}
	if CheckPassword(h, "correct horse battery stapler") || CheckPassword(h, "") {
		t.Fatal("wrong password accepted")
	}
	for _, bad := range []string{"", "x", "$argon2id$v=19$m=0,t=1,p=1$AA$AA", "$2a$10$abc"} {
		if CheckPassword(bad, "x") {
			t.Fatalf("bad hash %q accepted", bad)
		}
	}
	DummyCheck("anything")
}

func TestPasswordPolicy(t *testing.T) {
	for _, bad := range []string{
		"short",
		"password1234",
		"Password123456!",
		"aaaaaaaaaaaaaaaa",
		"jsmith-is-the-best",
		strings.Repeat("abcdefgh", 20),
	} {
		if CheckPasswordPolicy(bad, "jsmith@school.vic.edu.au") == nil {
			t.Errorf("%q accepted", bad)
		}
	}
	for _, good := range []string{"purple kettle rides north", "Tr4ffic-Lights&Blink!"} {
		if err := CheckPasswordPolicy(good, "jsmith@school.vic.edu.au"); err != nil {
			t.Errorf("%q refused: %v", good, err)
		}
	}
}

func TestTOTP(t *testing.T) {
	// RFC 6238 test vector (SHA-1, secret "12345678901234567890").
	secret := b32.EncodeToString([]byte("12345678901234567890"))
	for at, want := range map[int64]string{59: "287082", 1111111109: "081804", 1234567890: "005924", 2000000000: "279037"} {
		got, err := TOTPCode(secret, at/30)
		if err != nil || got != want {
			t.Errorf("t=%d: %s, want %s (%v)", at, got, want, err)
		}
	}
	now := time.Unix(1234567890, 0)
	code, _ := TOTPCode(secret, TOTPStep(now))
	if step, ok := CheckTOTP(secret, code, now); !ok || step != TOTPStep(now) {
		t.Fatal("current code refused")
	}
	prev, _ := TOTPCode(secret, TOTPStep(now)-1)
	if step, ok := CheckTOTP(secret, prev, now); !ok || step != TOTPStep(now)-1 {
		t.Fatal("previous code refused")
	}
	old, _ := TOTPCode(secret, TOTPStep(now)-3)
	if _, ok := CheckTOTP(secret, old, now); ok {
		t.Fatal("old code accepted")
	}
	if _, ok := CheckTOTP(secret, "12345", now); ok {
		t.Fatal("short code accepted")
	}
	s, _ := NewTOTPSecret()
	uri := TOTPURI(s, "CircuitPath", "a@b.c")
	if !strings.HasPrefix(uri, "otpauth://totp/CircuitPath:a@b.c?") || !strings.Contains(uri, "secret="+s) {
		t.Fatal(uri)
	}
}

func TestSeal(t *testing.T) {
	k := []byte("server secret")
	sealed, err := Seal(k, "JBSWY3DPEHPK3PXP")
	if err != nil || strings.Contains(sealed, "JBSWY3DP") {
		t.Fatal(sealed, err)
	}
	if got, err := Unseal(k, sealed); err != nil || got != "JBSWY3DPEHPK3PXP" {
		t.Fatal(got, err)
	}
	if _, err := Unseal([]byte("other secret"), sealed); err == nil {
		t.Fatal("opened with the wrong secret")
	}
	if _, err := Unseal(k, sealed[:len(sealed)-2]+"AA"); err == nil {
		t.Fatal("tampered value opened")
	}
}

func TestLockout(t *testing.T) {
	now := time.Unix(0, 0)
	l := NewLockout(3, time.Minute)
	l.Now = func() time.Time { return now }
	l.Fail("a")
	l.Fail("a")
	if l.Wait("a") != 0 {
		t.Fatal("locked too early")
	}
	if l.Fail("a") != time.Minute || l.Wait("a") == 0 {
		t.Fatal("not locked")
	}
	now = now.Add(61 * time.Second)
	if l.Wait("a") != 0 {
		t.Fatal("still locked")
	}
	l.Sweep(time.Second)
	if len(l.entries) != 0 {
		t.Fatal("not swept")
	}
}

func TestWindow(t *testing.T) {
	now := time.Unix(0, 0)
	w := NewWindow(2, time.Minute)
	w.Now = func() time.Time { return now }
	if !w.Allow("x") || !w.Allow("x") || w.Allow("x") || !w.Full("x") {
		t.Fatal("limit not enforced")
	}
	if !w.Allow("y") {
		t.Fatal("keys not separate")
	}
	now = now.Add(2 * time.Minute)
	if w.Full("x") || !w.Allow("x") {
		t.Fatal("window didn't move")
	}
	now = now.Add(2 * time.Minute)
	w.Sweep()
	if len(w.events) != 0 {
		t.Fatal("not swept")
	}
}

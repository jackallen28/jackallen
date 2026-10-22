package auth

import "testing"

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

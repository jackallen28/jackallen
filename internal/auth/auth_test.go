package auth

import (
	"testing"
	"time"
)

func TestPictures(t *testing.T) {
	good := []string{"cat", "rocket", "apple"}
	h, err := HashPictures(good)
	if err != nil {
		t.Fatal(err)
	}
	if !CheckPictures(h, good) {
		t.Fatal("right pictures rejected")
	}
	if CheckPictures(h, []string{"rocket", "cat", "apple"}) {
		t.Fatal("pictures in the wrong order accepted")
	}
	if CheckPictures(h, []string{"cat", "rocket", "star"}) {
		t.Fatal("wrong pictures accepted")
	}
	for _, bad := range [][]string{
		nil,
		{"cat", "rocket"},
		{"cat", "rocket", "apple", "sun"},
		{"cat", "cat", "apple"},
		{"cat", "rocket", "dragon"},
	} {
		if ValidPictures(bad) == nil {
			t.Errorf("%v accepted", bad)
		}
		if _, err := HashPictures(bad); err == nil {
			t.Errorf("hashed %v", bad)
		}
	}
}

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
		t.Fatal("token hash mismatch")
	}
}

func TestLockout(t *testing.T) {
	now := time.Unix(1000, 0)
	l := NewLockout(5, time.Minute)
	l.Now = func() time.Time { return now }
	for i := 0; i < 4; i++ {
		if l.Fail("7") != 0 {
			t.Fatalf("locked after %d tries", i+1)
		}
	}
	if l.Wait("7") != 0 {
		t.Fatal("waiting before the 5th try")
	}
	if l.Fail("7") != time.Minute || l.Wait("7") != time.Minute {
		t.Fatal("not locked after 5 tries")
	}
	if l.Wait("8") != 0 {
		t.Fatal("another profile is locked too")
	}
	now = now.Add(61 * time.Second)
	if l.Wait("7") != 0 {
		t.Fatal("still locked after a minute")
	}
	l.Fail("7")
	l.Succeed("7")
	for i := 0; i < 4; i++ {
		l.Fail("7")
	}
	if l.Wait("7") != 0 {
		t.Fatal("a right password didn't reset the count")
	}
}

func TestWindow(t *testing.T) {
	now := time.Unix(1000, 0)
	w := NewWindow(3, time.Hour)
	w.Now = func() time.Time { return now }
	for i := 0; i < 3; i++ {
		if !w.Allow("laptop") {
			t.Fatalf("refused event %d", i+1)
		}
	}
	if w.Allow("laptop") {
		t.Fatal("allowed a 4th event")
	}
	if !w.Allow("other") {
		t.Fatal("refused another key")
	}
	now = now.Add(time.Hour + time.Second)
	if !w.Allow("laptop") {
		t.Fatal("still refused after the period")
	}
}

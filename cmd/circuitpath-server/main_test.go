package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"circuitpath/internal/content"
)

func TestRedirectToHTTPS(t *testing.T) {
	cases := []struct{ httpsAddr, host, path, want string }{
		{":443", "circuitpath.local", "/teacher?x=1", "https://circuitpath.local/teacher?x=1"},
		{":443", "circuitpath.local:80", "/", "https://circuitpath.local/"},
		{":8443", "localhost:8080", "/projects", "https://localhost:8443/projects"},
	}
	for _, c := range cases {
		req := httptest.NewRequest("GET", "http://"+c.host+c.path, nil)
		req.Host = c.host
		rec := httptest.NewRecorder()
		redirectHandler(c.httpsAddr).ServeHTTP(rec, req)
		if rec.Code != http.StatusMovedPermanently || rec.Header().Get("Location") != c.want {
			t.Errorf("%s%s → %d %q, want %q", c.host, c.path, rec.Code, rec.Header().Get("Location"), c.want)
		}
	}
}

func TestNightlyClock(t *testing.T) {
	melb, err := time.LoadLocation("Australia/Melbourne")
	if err != nil {
		t.Skip(err)
	}
	h, m, err := parseClock("03:00")
	if err != nil || h != 3 || m != 0 {
		t.Fatalf("parseClock = %d %d %v", h, m, err)
	}
	for _, bad := range []string{"3am", "25:00", ""} {
		if _, _, err := parseClock(bad); err == nil {
			t.Errorf("parseClock(%q) accepted", bad)
		}
	}
	cases := []struct{ now, want string }{
		{"2026-10-21 14:00", "2026-10-22 03:00"}, // afternoon: tomorrow
		{"2026-10-21 02:59", "2026-10-21 03:00"}, // just before: today
		{"2026-10-21 03:00", "2026-10-22 03:00"}, // exactly now: tomorrow
		{"2026-04-04 12:00", "2026-04-05 03:00"}, // daylight saving ends overnight
	}
	for _, c := range cases {
		now, _ := time.ParseInLocation("2006-01-02 15:04", c.now, melb)
		if got := nextAt(now, 3, 0).Format("2006-01-02 15:04"); got != c.want {
			t.Errorf("nextAt(%s) = %s, want %s", c.now, got, c.want)
		}
	}
}

func TestBoardsToCheckIncludesVariants(t *testing.T) {
	cat, problems := content.Load(os.DirFS("../../content"))
	if len(problems) > 0 {
		t.Fatal(problems)
	}
	boards := boardsToCheck(cat)
	seen := map[string]bool{}
	for _, b := range boards {
		seen[b.FQBN] = true
	}
	for _, fqbn := range []string{"arduino:avr:uno", "arduino:avr:nano", "arduino:avr:nano:cpu=atmega328old", "esp8266:esp8266:nodemcuv2", "esp32:esp32:esp32"} {
		if !seen[fqbn] {
			t.Errorf("%s isn't checked (%v)", fqbn, boards)
		}
	}
}

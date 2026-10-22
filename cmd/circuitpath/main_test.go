package main

import (
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"testing"
	"time"

	"circuitpath/internal/content"
)

func TestDefaults(t *testing.T) {
	cfg := config{}
	cfg.applyDefaults()
	if cfg.port != defaultPort || cfg.dataDir == "" || cfg.dev || cfg.noBrowser {
		t.Fatalf("defaults = %+v", cfg)
	}
	dev := config{dev: true, idleExit: time.Minute}
	dev.applyDefaults()
	if dev.port != 8080 || dev.dataDir != "dev-data" || !dev.noBrowser || dev.idleExit != 0 {
		t.Fatalf("dev defaults = %+v", dev)
	}
	t.Setenv("LOCALAPPDATA", `C:\Users\student\AppData\Local`)
	if d := defaultDataDir(); d == "" {
		t.Fatal("no data folder")
	}
}

func TestRunningSpotsCircuitPath(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"app":"CircuitPath"}`))
	}))
	defer ts.Close()
	_, port, _ := net.SplitHostPort(ts.Listener.Addr().String())
	p, _ := strconv.Atoi(port)
	if !running(p) {
		t.Fatal("didn't spot CircuitPath")
	}
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`<html>something else</html>`))
	}))
	defer other.Close()
	_, port, _ = net.SplitHostPort(other.Listener.Addr().String())
	p, _ = strconv.Atoi(port)
	if running(p) {
		t.Fatal("mistook another program for CircuitPath")
	}
}

func TestIdleTracker(t *testing.T) {
	var it idleTracker
	it.touch()
	h := it.wrap(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	it.last.Store(time.Now().Add(-time.Hour).UnixNano())
	if it.since() < 59*time.Minute {
		t.Fatal("not idle")
	}
	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/api/ping", nil))
	if it.since() > time.Minute {
		t.Fatal("a request didn't count as activity")
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

package arduino

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// fakeCLI is a shell script standing in for arduino-cli: it logs its
// arguments, reports its version, and fails to compile for "bad" boards.
const fakeCLI = `#!/bin/sh
if [ "$1" = version ]; then echo '{"VersionString":"1.5.1"}'; exit 0; fi
echo "$@" >> "$HOME/calls.log"
case "$*" in *bad:board*) echo "error: it broke"; exit 1;; esac
exit 0
`

func tarGz(t *testing.T, name string, data []byte) []byte {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	tw.WriteHeader(&tar.Header{Name: name, Mode: 0o755, Size: int64(len(data)), Typeflag: tar.TypeReg})
	tw.Write(data)
	tw.Close()
	gz.Close()
	return buf.Bytes()
}

func fakeDownloads(t *testing.T, archive []byte, sum string) *httptest.Server {
	plat, err := cliPlatform()
	if err != nil {
		t.Skip(err)
	}
	name := fmt.Sprintf("arduino-cli_1.5.1_%s.tar.gz", plat)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch strings.TrimPrefix(r.URL.Path, "/") {
		case "arduino-cli_1.5.1_checksums.txt":
			fmt.Fprintf(w, "%s  %s\n0000  arduino-cli_1.5.1_Other.tar.gz\n", sum, name)
		case name:
			w.Write(archive)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newEnv(t *testing.T, base string) *Env {
	return &Env{
		Dir:          t.TempDir(),
		DownloadBase: base,
		Log:          slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
}

func TestPinnedRequirements(t *testing.T) {
	r := Pinned()
	if r.CLI == "" || len(r.Cores) != 3 || len(r.Libraries) == 0 || len(r.BoardManagerURLs) != 2 {
		t.Fatalf("requirements.json = %+v", r)
	}
	for _, p := range append(r.Cores, r.Libraries...) {
		if p.Name == "" || p.Version == "" {
			t.Errorf("%+v needs a name and an exact version", p)
		}
	}
	other := r
	other.Cores = append([]Package{}, r.Cores...)
	other.Cores[0].Version = "0.0.1"
	if r.Hash() == other.Hash() {
		t.Error("changing a version doesn't change the hash")
	}
	if !bytes.Contains(kitCheckSketch, []byte("void setup()")) {
		t.Error("the kit-check sketch is missing")
	}
}

func TestSetupInstallsThePinnedVersions(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("uses a shell script")
	}
	archive := tarGz(t, "arduino-cli", []byte(fakeCLI))
	sum := sha256.Sum256(archive)
	srv := fakeDownloads(t, archive, hex.EncodeToString(sum[:]))
	e := newEnv(t, srv.URL)
	if e.Ready() {
		t.Fatal("ready before setup")
	}
	if err := e.Setup(context.Background()); err != nil {
		t.Fatal(err)
	}
	if !e.Ready() {
		t.Fatal("not ready after setup")
	}
	calls, _ := os.ReadFile(filepath.Join(e.Dir, "calls.log"))
	log := string(calls)
	for _, want := range []string{
		"core update-index", "lib update-index",
		"core install arduino:avr@", "core install esp32:esp32@",
		"lib install --no-deps Adafruit NeoPixel@",
	} {
		if !strings.Contains(log, want) {
			t.Errorf("arduino-cli was never asked to %q:\n%s", want, log)
		}
	}
	cfg, _ := os.ReadFile(e.ConfigFile())
	for _, want := range []string{"additional_urls", "package_esp32_index.json", "build_cache:", filepath.Join(e.Dir, "user")} {
		if !strings.Contains(string(cfg), want) {
			t.Errorf("arduino-cli.yaml has no %q:\n%s", want, cfg)
		}
	}

	// A release with different versions makes it not ready again.
	e.Req = Pinned()
	e.Req.Libraries = append(e.Req.Libraries, Package{Name: "New Library", Version: "1.0.0"})
	if e.Ready() {
		t.Fatal("still ready after the requirements changed")
	}
}

func TestSetupRefusesABadDownload(t *testing.T) {
	archive := tarGz(t, "arduino-cli", []byte(fakeCLI))
	srv := fakeDownloads(t, archive, strings.Repeat("ab", 32))
	e := newEnv(t, srv.URL)
	if err := e.Setup(context.Background()); err == nil || !strings.Contains(err.Error(), "checksum") {
		t.Fatalf("Setup = %v, want a checksum error", err)
	}
	if _, err := os.Stat(e.CLI()); err == nil {
		t.Fatal("installed an arduino-cli that failed its checksum")
	}
}

func TestCheckCompilesEveryBoard(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("uses a shell script")
	}
	e := newEnv(t, "")
	os.MkdirAll(filepath.Dir(e.CLI()), 0o755)
	os.WriteFile(e.CLI(), []byte(fakeCLI), 0o755)
	results, err := e.Check(context.Background(), []Board{
		{Name: "Uno", FQBN: "arduino:avr:uno"},
		{Name: "Broken", FQBN: "bad:board:x"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 || !results[0].OK || results[1].OK || !strings.Contains(results[1].Output, "it broke") {
		t.Fatalf("results = %+v", results)
	}
	calls, _ := os.ReadFile(filepath.Join(e.Dir, "calls.log"))
	if !strings.Contains(string(calls), "compile --fqbn arduino:avr:uno") {
		t.Fatalf("calls:\n%s", calls)
	}
}

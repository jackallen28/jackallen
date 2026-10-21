package update

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"errors"
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

func TestVersions(t *testing.T) {
	cases := []struct {
		a, b  string
		newer bool
	}{
		{"1.0.1", "1.0.0", true},
		{"1.10.0", "1.9.9", true},
		{"2.0.0", "1.99.99", true},
		{"v1.2.0", "1.1.0", true},
		{"1.0.0", "1.0.0", false},
		{"0.9.0", "1.0.0", false},
		{"1.0.0", "dev", false},
		{"dev", "1.0.0", false},
		{"1.0", "0.9.0", false},
		{"1.0.0-beta", "0.9.0", false},
		{"01.0.0", "0.9.0", false},
	}
	for _, c := range cases {
		if got := Newer(c.a, c.b); got != c.newer {
			t.Errorf("Newer(%q, %q) = %v", c.a, c.b, got)
		}
	}
}

func TestKeys(t *testing.T) {
	pub, priv, _ := ed25519.GenerateKey(rand.Reader)
	pk, err := ParsePublicKey("# comment\n" + encode(pub) + "\n")
	if err != nil || !pk.Equal(pub) {
		t.Fatalf("ParsePublicKey: %v", err)
	}
	sk, err := ParsePrivateKey(encode(priv.Seed()))
	if err != nil || !sk.Equal(priv) {
		t.Fatalf("ParsePrivateKey: %v", err)
	}
	if _, err := ParsePublicKey("# nothing here\n"); err == nil {
		t.Fatal("parsed an empty key file")
	}
	// The committed key file either has no key yet or a real one.
	if _, err := ParsePublicKey(publicKeyFile); err != nil && !strings.Contains(publicKeyFile, "There is no key yet") {
		t.Fatalf("update-public-key.txt: %v", err)
	}
	sig := Sign(priv, []byte("manifest"))
	if Verify(pub, []byte("manifest"), sig) != nil {
		t.Fatal("good signature rejected")
	}
	if Verify(pub, []byte("manifesT"), sig) == nil {
		t.Fatal("signature accepted for changed data")
	}
	otherPub, _, _ := ed25519.GenerateKey(rand.Reader)
	if Verify(otherPub, []byte("manifest"), sig) == nil {
		t.Fatal("signature accepted with another key")
	}
}

func encode(b []byte) string { return base64.StdEncoding.EncodeToString(b) }

// release is a fake GitHub release: update.json, its signature and a binary.
type release struct {
	t        *testing.T
	priv     ed25519.PrivateKey
	pub      ed25519.PublicKey
	srv      *httptest.Server
	files    map[string][]byte
	requests int
}

func newRelease(t *testing.T, version string, binary []byte) *release {
	pub, priv, _ := ed25519.GenerateKey(rand.Reader)
	r := &release{t: t, priv: priv, pub: pub, files: map[string][]byte{}}
	r.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		r.requests++
		b, ok := r.files[strings.TrimPrefix(req.URL.Path, "/")]
		if !ok {
			http.NotFound(w, req)
			return
		}
		w.Write(b)
	}))
	t.Cleanup(r.srv.Close)
	r.publish(version, binary)
	return r
}

func (r *release) publish(version string, binary []byte) {
	dir := r.t.TempDir()
	bin := filepath.Join(dir, "circuitpath-server-"+Platform())
	os.WriteFile(bin, binary, 0o755)
	m, err := BuildManifest(version, r.srv.URL+"/download", map[string]string{Platform(): bin})
	if err != nil {
		r.t.Fatal(err)
	}
	r.files["download/"+filepath.Base(bin)] = binary
	r.files[ManifestName] = m
	r.files[SigName] = Sign(r.priv, m)
}

type fakeDB struct {
	version  int
	backups  []string
	restored string
}

func newUpdater(t *testing.T, r *release, current string, db *fakeDB) *Updater {
	t.Helper()
	dir := t.TempDir()
	exe := filepath.Join(dir, "bin", "circuitpath-server")
	os.MkdirAll(filepath.Dir(exe), 0o755)
	os.WriteFile(exe, []byte("old binary "+current), 0o755)
	u := &Updater{
		Dir:         filepath.Join(dir, "data", "update"),
		BackupDir:   filepath.Join(dir, "data", "backups"),
		Exe:         exe,
		Current:     current,
		ManifestURL: r.srv.URL + "/" + ManifestName,
		PublicKey:   r.pub,
		Log:         slog.New(slog.NewTextHandler(io.Discard, nil)),
		RunVersion: func(_ context.Context, path string) (string, error) {
			b, err := os.ReadFile(path)
			return strings.TrimPrefix(string(b), "new binary "), err
		},
	}
	if db != nil {
		u.Hooks = Hooks{
			BackupDB: func(_ context.Context, path string) (int, error) {
				db.backups = append(db.backups, path)
				return db.version, os.WriteFile(path, []byte("backup"), 0o644)
			},
			DBVersion: func() (int, error) { return db.version, nil },
			RestoreDB: func(path string) error { db.restored = path; return nil },
		}
	}
	return u
}

func read(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func TestInstallsANewerVersion(t *testing.T) {
	r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
	db := &fakeDB{version: 1}
	u := newUpdater(t, r, "1.0.0", db)
	installed, err := u.Run(context.Background())
	if err != nil || !installed {
		t.Fatalf("Run = %v, %v", installed, err)
	}
	if read(t, u.Exe) != "new binary 1.1.0" || read(t, u.Exe+".previous") != "old binary 1.0.0" {
		t.Fatal("binaries not swapped")
	}
	if len(db.backups) != 1 || !strings.Contains(db.backups[0], "before-update-1.0.0-to-1.1.0") {
		t.Fatalf("backups = %v", db.backups)
	}
	leftovers, _ := filepath.Glob(filepath.Join(filepath.Dir(u.Exe), ".circuitpath-update-*"))
	if len(leftovers) != 0 {
		t.Fatalf("left behind %v", leftovers)
	}

	// The new version starts, runs for a while and confirms.
	u.Current = "1.1.0"
	if restart, err := u.Startup(); restart || err != nil {
		t.Fatalf("Startup = %v, %v", restart, err)
	}
	if err := u.Confirm(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(u.statePath()); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("state not cleared after confirming")
	}
	// Now it's up to date.
	installed, err = u.Run(context.Background())
	if err != nil || installed {
		t.Fatalf("second Run = %v, %v", installed, err)
	}
}

func TestDoesNothingWhenUpToDateOrOlder(t *testing.T) {
	for _, current := range []string{"1.1.0", "2.0.0"} {
		r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
		u := newUpdater(t, r, current, nil)
		installed, err := u.Run(context.Background())
		if err != nil || installed {
			t.Fatalf("current %s: Run = %v, %v", current, installed, err)
		}
		if read(t, u.Exe) != "old binary "+current {
			t.Fatal("binary changed")
		}
	}
}

func TestRefusesBadUpdates(t *testing.T) {
	cases := map[string]func(r *release, u *Updater){
		"wrong key": func(r *release, u *Updater) {
			_, other, _ := ed25519.GenerateKey(rand.Reader)
			r.files[SigName] = Sign(other, r.files[ManifestName])
		},
		"changed manifest": func(r *release, u *Updater) {
			r.files[ManifestName] = []byte(strings.Replace(string(r.files[ManifestName]), "1.1.0", "1.2.0", 1))
		},
		"changed binary": func(r *release, u *Updater) {
			r.files["download/circuitpath-server-"+Platform()] = []byte("new binary 1.1.0 + something")
		},
		"same size, different binary": func(r *release, u *Updater) {
			r.files["download/circuitpath-server-"+Platform()] = []byte("NEW binary 1.1.0")
		},
		"binary doesn't run": func(r *release, u *Updater) {
			u.RunVersion = func(context.Context, string) (string, error) { return "", errors.New("exec format error") }
		},
		"binary is another version": func(r *release, u *Updater) {
			u.RunVersion = func(context.Context, string) (string, error) { return "1.0.9", nil }
		},
		"no signature": func(r *release, u *Updater) { delete(r.files, SigName) },
		"no key":       func(r *release, u *Updater) { u.PublicKey = nil },
		"dev build":    func(r *release, u *Updater) { u.Current = "dev" },
		"plain http": func(r *release, u *Updater) {
			u.ManifestURL = strings.Replace(u.ManifestURL, "127.0.0.1", "example.com", 1)
		},
	}
	for name, breakIt := range cases {
		r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
		u := newUpdater(t, r, "1.0.0", &fakeDB{})
		breakIt(r, u)
		installed, err := u.Run(context.Background())
		if installed || err == nil {
			t.Errorf("%s: Run = %v, %v", name, installed, err)
		}
		if read(t, u.Exe) != "old binary 1.0.0" {
			t.Errorf("%s: binary changed", name)
		}
		if _, err := os.Stat(u.statePath()); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("%s: state left behind", name)
		}
	}
}

func TestNoInternetIsJustAnError(t *testing.T) {
	r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
	u := newUpdater(t, r, "1.0.0", nil)
	r.srv.Close()
	installed, err := u.Run(context.Background())
	if installed || err == nil {
		t.Fatalf("Run = %v, %v", installed, err)
	}
}

func TestRollsBackAVersionThatKeepsStopping(t *testing.T) {
	r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
	db := &fakeDB{version: 1}
	u := newUpdater(t, r, "1.0.0", db)
	if installed, err := u.Run(context.Background()); !installed || err != nil {
		t.Fatalf("Run = %v, %v", installed, err)
	}

	// The new version migrates the database, then keeps stopping.
	u.Current = "1.1.0"
	db.version = 2
	for i := 1; i <= maxStarts; i++ {
		if restart, err := u.Startup(); restart || err != nil {
			t.Fatalf("start %d: Startup = %v, %v", i, restart, err)
		}
	}
	restart, err := u.Startup()
	if !restart || err != nil {
		t.Fatalf("Startup after %d failed starts = %v, %v", maxStarts, restart, err)
	}
	if read(t, u.Exe) != "old binary 1.0.0" {
		t.Fatal("old binary not put back")
	}
	if db.restored == "" {
		t.Fatal("database not restored after the new version changed it")
	}

	// Back on the old version, the bad version is never installed again...
	u.Current = "1.0.0"
	if restart, err := u.Startup(); restart || err != nil {
		t.Fatalf("Startup on old version = %v, %v", restart, err)
	}
	if installed, err := u.Run(context.Background()); installed || err != nil {
		t.Fatalf("reinstalled the bad version: %v, %v", installed, err)
	}
	// ...but a fixed one is.
	r.publish("1.1.1", []byte("new binary 1.1.1"))
	if installed, err := u.Run(context.Background()); !installed || err != nil {
		t.Fatalf("fixed version: Run = %v, %v", installed, err)
	}
}

func TestRollbackKeepsTheDatabaseIfUnchanged(t *testing.T) {
	r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
	db := &fakeDB{version: 1}
	u := newUpdater(t, r, "1.0.0", db)
	u.Run(context.Background())
	u.Current = "1.1.0"
	for i := 0; i <= maxStarts; i++ {
		u.Startup()
	}
	if db.restored != "" {
		t.Fatal("restored a database the new version never changed")
	}
}

func TestKeepsOnlyRecentBackups(t *testing.T) {
	r := newRelease(t, "1.1.0", []byte("new binary 1.1.0"))
	u := newUpdater(t, r, "1.0.0", &fakeDB{})
	os.MkdirAll(u.BackupDir, 0o755)
	for _, v := range []string{"0.1.0", "0.2.0", "0.3.0", "0.4.0"} {
		os.WriteFile(filepath.Join(u.BackupDir, "before-update-"+v+"-to-x.db"), nil, 0o644)
	}
	u.Run(context.Background())
	files, _ := filepath.Glob(filepath.Join(u.BackupDir, "before-update-*.db"))
	if len(files) != keepDBBackups {
		t.Fatalf("%d backups kept: %v", len(files), files)
	}
}

func TestRunVersionRunsTheBinary(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("uses a shell script")
	}
	script := filepath.Join(t.TempDir(), "fake-server")
	os.WriteFile(script, []byte("#!/bin/sh\n[ \"$1\" = -version ] && echo 1.2.3\n"), 0o755)
	got, err := runVersion(context.Background(), script)
	if err != nil || got != "1.2.3" {
		t.Fatalf("runVersion = %q, %v", got, err)
	}
}

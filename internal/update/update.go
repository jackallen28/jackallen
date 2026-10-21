// Package update keeps the Pi's CircuitPath up to date.
//
// Every time the server starts it asks GitHub Releases for update.json and
// update.json.sig. If the manifest is signed by CircuitPath's update key and
// names a newer version, the server downloads the binary for this computer,
// checks its size, SHA-256 and that it runs, backs up the database, swaps the
// binary in (keeping the old one) and restarts into it.
//
// If the new version can't stay up (it stops 3 times before it has run for a
// couple of minutes), the next start puts the old binary back, restores the
// database backup if the new version had changed it, and never tries that
// version again.
//
// No internet, no key, a dev build or any problem at all: the server just
// starts as it is.
package update

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	_ "embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Names of the files a release publishes.
const (
	ManifestName = "update.json"
	SigName      = "update.json.sig"
	Format       = "circuitpath-update"
)

const (
	maxManifestBytes = 64 << 10
	maxSigBytes      = 1 << 10
	maxBinaryBytes   = 256 << 20
	maxStarts        = 3 // starts allowed before a new version must have confirmed
	keepDBBackups    = 3
)

// Manifest is update.json: what the newest release is and where its files are.
type Manifest struct {
	Format      string          `json:"format"`
	Version     string          `json:"version"`
	PublishedAt string          `json:"published_at,omitempty"`
	Files       map[string]File `json:"files"` // keyed by Platform(), e.g. "linux-arm64"
}

// File is one downloadable server binary.
type File struct {
	URL    string `json:"url"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
}

// Platform names this computer's binary in a manifest, e.g. "linux-arm64".
func Platform() string { return runtime.GOOS + "-" + runtime.GOARCH }

// ParseVersion reads "1.2.3" (or "v1.2.3").
func ParseVersion(s string) ([3]int, bool) {
	var v [3]int
	parts := strings.Split(strings.TrimPrefix(s, "v"), ".")
	if len(parts) != 3 {
		return v, false
	}
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 || p != strconv.Itoa(n) {
			return v, false
		}
		v[i] = n
	}
	return v, true
}

// Newer reports whether version a is newer than version b. Anything that
// isn't a plain x.y.z version is never newer.
func Newer(a, b string) bool {
	va, ok1 := ParseVersion(a)
	vb, ok2 := ParseVersion(b)
	if !ok1 || !ok2 {
		return false
	}
	for i := range va {
		if va[i] != vb[i] {
			return va[i] > vb[i]
		}
	}
	return false
}

//go:embed update-public-key.txt
var publicKeyFile string

// BuildKey replaces update-public-key.txt in a build made with
// -ldflags "-X circuitpath/internal/update.BuildKey=<base64 key>" (tests
// use it; so can a school that publishes its own releases).
var BuildKey = ""

// PublicKey is the key releases are signed with (update-public-key.txt).
// ok is false until a key has been made with tools/updatekey.
func PublicKey() (key ed25519.PublicKey, ok bool) {
	text := publicKeyFile
	if BuildKey != "" {
		text = BuildKey
	}
	key, err := ParsePublicKey(text)
	return key, err == nil
}

// ParsePublicKey reads a base64 Ed25519 public key, ignoring # comments.
func ParsePublicKey(text string) (ed25519.PublicKey, error) {
	b, err := decodeKey(text)
	if err != nil {
		return nil, err
	}
	if len(b) != ed25519.PublicKeySize {
		return nil, errors.New("not an update public key")
	}
	return ed25519.PublicKey(b), nil
}

// ParsePrivateKey reads a base64 Ed25519 private key seed.
func ParsePrivateKey(text string) (ed25519.PrivateKey, error) {
	b, err := decodeKey(text)
	if err != nil {
		return nil, err
	}
	if len(b) != ed25519.SeedSize {
		return nil, errors.New("not an update private key")
	}
	return ed25519.NewKeyFromSeed(b), nil
}

func decodeKey(text string) ([]byte, error) {
	var lines []string
	for _, l := range strings.Split(text, "\n") {
		if l = strings.TrimSpace(l); l != "" && !strings.HasPrefix(l, "#") {
			lines = append(lines, l)
		}
	}
	if len(lines) != 1 {
		return nil, errors.New("no key")
	}
	return base64.StdEncoding.DecodeString(lines[0])
}

// Sign signs a manifest, returning the contents of update.json.sig.
func Sign(key ed25519.PrivateKey, manifest []byte) []byte {
	return []byte(base64.StdEncoding.EncodeToString(ed25519.Sign(key, manifest)) + "\n")
}

// Verify checks update.json.sig against update.json.
func Verify(key ed25519.PublicKey, manifest, sig []byte) error {
	raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(string(sig)))
	if err != nil || !ed25519.Verify(key, manifest, raw) {
		return errors.New("the update's signature doesn't match CircuitPath's update key")
	}
	return nil
}

// Hooks let the updater back up and restore the database without knowing
// how it's stored.
type Hooks struct {
	// BackupDB writes a copy of the database to path and returns its schema version.
	BackupDB func(ctx context.Context, path string) (int, error)
	// DBVersion reads the database's schema version (the database isn't open yet).
	DBVersion func() (int, error)
	// RestoreDB puts the backup at path back (the database isn't open yet).
	RestoreDB func(path string) error
}

// Updater checks for, installs and (if needed) rolls back updates.
type Updater struct {
	Dir         string                                                 // where state.json and skip.json live (in the data folder)
	BackupDir   string                                                 // where database backups go
	Exe         string                                                 // the running server binary
	Current     string                                                 // the running version
	ManifestURL string                                                 // where update.json is; update.json.sig is next to it
	PublicKey   ed25519.PublicKey                                      // the release signing key
	Client      *http.Client                                           // nil: a client that honours HTTPS_PROXY
	Log         *slog.Logger                                           // nil: slog.Default()
	Hooks       Hooks                                                  //
	RunVersion  func(ctx context.Context, path string) (string, error) // nil: runs "<path> -version"
}

func (u *Updater) log() *slog.Logger {
	if u.Log != nil {
		return u.Log
	}
	return slog.Default()
}

func (u *Updater) client() *http.Client {
	if u.Client != nil {
		return u.Client
	}
	return &http.Client{
		Transport: &http.Transport{
			Proxy:                 http.ProxyFromEnvironment, // school proxies
			DialContext:           (&net.Dialer{Timeout: 10 * time.Second}).DialContext,
			TLSHandshakeTimeout:   10 * time.Second,
			ResponseHeaderTimeout: 15 * time.Second,
		},
	}
}

// Run checks for an update and installs it. It returns true when a new
// version is in place and the server should restart.
func (u *Updater) Run(ctx context.Context) (bool, error) {
	m, err := u.Check(ctx)
	if err != nil || m == nil {
		return false, err
	}
	u.log().Info("downloading an update", "from", u.Current, "to", m.Version)
	path, err := u.Download(ctx, m)
	if err != nil {
		return false, err
	}
	if err := u.Install(ctx, m, path); err != nil {
		os.Remove(path)
		return false, err
	}
	u.log().Info("update installed; restarting", "version", m.Version)
	return true, nil
}

// Check fetches and verifies the manifest. It returns nil (and no error)
// when this server is up to date.
func (u *Updater) Check(ctx context.Context) (*Manifest, error) {
	if _, ok := ParseVersion(u.Current); !ok {
		return nil, fmt.Errorf("this build has no version number (%q), so it can't compare", u.Current)
	}
	if len(u.PublicKey) != ed25519.PublicKeySize {
		return nil, errors.New("no update key is set up (see docs/updates.md)")
	}
	if u.ManifestURL == "" {
		return nil, errors.New("this build doesn't know where updates come from")
	}
	raw, err := u.get(ctx, u.ManifestURL, maxManifestBytes)
	if err != nil {
		return nil, err
	}
	sig, err := u.get(ctx, u.ManifestURL+".sig", maxSigBytes)
	if err != nil {
		return nil, err
	}
	if err := Verify(u.PublicKey, raw, sig); err != nil {
		return nil, err
	}
	var m Manifest
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&m); err != nil || m.Format != Format {
		return nil, errors.New("update.json isn't a CircuitPath update manifest")
	}
	if _, ok := ParseVersion(m.Version); !ok {
		return nil, fmt.Errorf("update.json has a bad version %q", m.Version)
	}
	if !Newer(m.Version, u.Current) {
		u.log().Info("CircuitPath is up to date", "version", u.Current, "latest", m.Version)
		return nil, nil
	}
	if slices.Contains(u.skipped(), m.Version) {
		u.log().Warn("not installing an update that failed to start before", "version", m.Version)
		return nil, nil
	}
	return &m, nil
}

func (u *Updater) get(ctx context.Context, rawURL string, limit int64) ([]byte, error) {
	if err := checkURL(rawURL); err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "CircuitPath/"+u.Current)
	res, err := u.client().Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s: %s", rawURL, res.Status)
	}
	b, err := io.ReadAll(io.LimitReader(res.Body, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(b)) > limit {
		return nil, fmt.Errorf("%s is too big", rawURL)
	}
	return b, nil
}

// checkURL allows HTTPS, and plain HTTP only to this computer (for tests).
func checkURL(raw string) error {
	p, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if p.Scheme == "https" {
		return nil
	}
	if p.Scheme == "http" {
		if ip := net.ParseIP(p.Hostname()); ip != nil && ip.IsLoopback() {
			return nil
		}
	}
	return fmt.Errorf("refusing to fetch an update over %q", raw)
}

// Download fetches the binary for this computer next to the running one,
// checks its size and SHA-256, and checks it runs and reports the expected
// version. It returns the downloaded file's path.
func (u *Updater) Download(ctx context.Context, m *Manifest) (string, error) {
	f, ok := m.Files[Platform()]
	if !ok {
		return "", fmt.Errorf("version %s has no file for %s", m.Version, Platform())
	}
	want, err := hex.DecodeString(f.SHA256)
	if err != nil || len(want) != sha256.Size || f.Size <= 0 || f.Size > maxBinaryBytes {
		return "", errors.New("update.json describes the file badly")
	}
	if err := checkURL(f.URL); err != nil {
		return "", err
	}
	tmp, err := os.CreateTemp(filepath.Dir(u.Exe), ".circuitpath-update-*")
	if err != nil {
		return "", fmt.Errorf("can't write next to %s: %w", u.Exe, err)
	}
	path := tmp.Name()
	fail := func(err error) (string, error) {
		tmp.Close()
		os.Remove(path)
		return "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, f.URL, nil)
	if err != nil {
		return fail(err)
	}
	req.Header.Set("User-Agent", "CircuitPath/"+u.Current)
	res, err := u.client().Do(req)
	if err != nil {
		return fail(err)
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return fail(fmt.Errorf("%s: %s", f.URL, res.Status))
	}
	h := sha256.New()
	n, err := io.Copy(io.MultiWriter(tmp, h), io.LimitReader(res.Body, f.Size+1))
	if err != nil {
		return fail(err)
	}
	if n != f.Size || !bytes.Equal(h.Sum(nil), want) {
		return fail(errors.New("the downloaded file doesn't match update.json"))
	}
	if err := tmp.Chmod(0o755); err != nil {
		return fail(err)
	}
	if err := tmp.Sync(); err != nil {
		return fail(err)
	}
	if err := tmp.Close(); err != nil {
		return fail(err)
	}
	run := u.RunVersion
	if run == nil {
		run = runVersion
	}
	got, err := run(ctx, path)
	if err != nil || got != m.Version {
		os.Remove(path)
		return "", fmt.Errorf("the new version didn't run properly (said %q, %v)", got, err)
	}
	return path, nil
}

// runVersion runs "<path> -version" and returns what it prints.
func runVersion(ctx context.Context, path string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, path, "-version").Output()
	return strings.TrimSpace(string(out)), err
}

// state is written just before a new binary is swapped in, and removed once
// the new version has been running for a while (Confirm).
type state struct {
	From            string `json:"from"`
	To              string `json:"to"`
	Previous        string `json:"previous"`
	DBBackup        string `json:"db_backup,omitempty"`
	DBVersionBefore int    `json:"db_version_before"`
	Starts          int    `json:"starts"`
	InstalledAt     string `json:"installed_at"`
}

func (u *Updater) statePath() string { return filepath.Join(u.Dir, "state.json") }
func (u *Updater) skipPath() string  { return filepath.Join(u.Dir, "skip.json") }

func (u *Updater) readState() (*state, error) {
	b, err := os.ReadFile(u.statePath())
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var st state
	if err := json.Unmarshal(b, &st); err != nil {
		return nil, err
	}
	return &st, nil
}

func (u *Updater) writeState(st *state) error {
	b, _ := json.MarshalIndent(st, "", "  ")
	return writeFileAtomic(u.statePath(), b, 0o644)
}

func (u *Updater) skipped() []string {
	var list []string
	if b, err := os.ReadFile(u.skipPath()); err == nil {
		json.Unmarshal(b, &list)
	}
	return list
}

func (u *Updater) skip(version string) error {
	list := u.skipped()
	if slices.Contains(list, version) {
		return nil
	}
	b, _ := json.MarshalIndent(append(list, version), "", "  ")
	return writeFileAtomic(u.skipPath(), b, 0o644)
}

// Install backs up the database, records what is being installed (so a
// failed start can be rolled back) and swaps the downloaded binary in.
func (u *Updater) Install(ctx context.Context, m *Manifest, path string) error {
	if err := os.MkdirAll(u.Dir, 0o750); err != nil {
		return err
	}
	st := &state{
		From:        u.Current,
		To:          m.Version,
		Previous:    u.Exe + ".previous",
		InstalledAt: time.Now().UTC().Format(time.RFC3339),
	}
	if u.Hooks.BackupDB != nil {
		if err := os.MkdirAll(u.BackupDir, 0o750); err != nil {
			return err
		}
		st.DBBackup = filepath.Join(u.BackupDir, fmt.Sprintf("before-update-%s-to-%s.db", u.Current, m.Version))
		os.Remove(st.DBBackup)
		v, err := u.Hooks.BackupDB(ctx, st.DBBackup)
		if err != nil {
			return fmt.Errorf("backing up the database: %w", err)
		}
		st.DBVersionBefore = v
		u.pruneBackups()
	}
	if err := u.writeState(st); err != nil {
		return err
	}
	os.Remove(st.Previous)
	if err := os.Rename(u.Exe, st.Previous); err != nil {
		os.Remove(u.statePath())
		return err
	}
	if err := os.Rename(path, u.Exe); err != nil {
		os.Rename(st.Previous, u.Exe)
		os.Remove(u.statePath())
		return err
	}
	syncDir(filepath.Dir(u.Exe))
	return nil
}

// pruneBackups keeps the newest few before-update database backups.
func (u *Updater) pruneBackups() {
	files, _ := filepath.Glob(filepath.Join(u.BackupDir, "before-update-*.db"))
	if len(files) <= keepDBBackups {
		return
	}
	sort.Slice(files, func(i, j int) bool {
		a, _ := os.Stat(files[i])
		b, _ := os.Stat(files[j])
		return a != nil && b != nil && a.ModTime().After(b.ModTime())
	})
	for _, f := range files[keepDBBackups:] {
		os.Remove(f)
	}
}

// Startup runs first thing when the server starts. After an update it
// counts the new version's starts; if it has started too many times without
// confirming, it puts the old version back and returns true (restart now).
func (u *Updater) Startup() (bool, error) {
	st, err := u.readState()
	if err != nil || st == nil {
		return false, err
	}
	if st.To != u.Current {
		// Not the version that was installed (it was replaced by hand, or a
		// rollback already happened): nothing to watch.
		return false, os.Remove(u.statePath())
	}
	st.Starts++
	if st.Starts <= maxStarts {
		return false, u.writeState(st)
	}
	u.log().Error("the new version keeps stopping; going back to the old one", "new", st.To, "old", st.From)
	if err := os.Rename(st.Previous, u.Exe); err != nil {
		return false, fmt.Errorf("putting the old version back: %w", err)
	}
	syncDir(filepath.Dir(u.Exe))
	if st.DBBackup != "" && u.Hooks.DBVersion != nil && u.Hooks.RestoreDB != nil {
		if v, err := u.Hooks.DBVersion(); err != nil || v != st.DBVersionBefore {
			u.log().Warn("restoring the database from before the update", "backup", st.DBBackup)
			if err := u.Hooks.RestoreDB(st.DBBackup); err != nil {
				return false, fmt.Errorf("restoring the database: %w", err)
			}
		}
	}
	if err := u.skip(st.To); err != nil {
		return false, err
	}
	return true, os.Remove(u.statePath())
}

// Confirm says the running version is healthy: it stays, and the old one
// can be forgotten.
func (u *Updater) Confirm() error {
	st, err := u.readState()
	if err != nil || st == nil || st.To != u.Current {
		return err
	}
	u.log().Info("update confirmed", "version", st.To)
	return os.Remove(u.statePath())
}

// BuildManifest describes release binaries for update.json. files maps a
// platform ("linux-arm64") to a local file; baseURL is where the release
// publishes them.
func BuildManifest(version, baseURL string, files map[string]string) ([]byte, error) {
	if _, ok := ParseVersion(version); !ok {
		return nil, fmt.Errorf("%q isn't a version like 1.2.3", version)
	}
	m := Manifest{Format: Format, Version: version, PublishedAt: time.Now().UTC().Format(time.RFC3339), Files: map[string]File{}}
	for platform, path := range files {
		b, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		sum := sha256.Sum256(b)
		m.Files[platform] = File{
			URL:    strings.TrimSuffix(baseURL, "/") + "/" + filepath.Base(path),
			SHA256: hex.EncodeToString(sum[:]),
			Size:   int64(len(b)),
		}
	}
	b, err := json.MarshalIndent(m, "", "  ")
	return append(b, '\n'), err
}

func writeFileAtomic(path string, data []byte, perm os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".tmp-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Chmod(perm); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		return err
	}
	syncDir(filepath.Dir(path))
	return nil
}

// syncDir makes a rename survive a power cut (not possible on Windows).
func syncDir(dir string) {
	if d, err := os.Open(dir); err == nil {
		d.Sync()
		d.Close()
	}
}

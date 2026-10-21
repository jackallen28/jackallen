package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"circuitpath/internal/update"
)

// TestUpdatesItselfAtStartup builds two real servers (1.0.0 and 1.1.0),
// publishes 1.1.0 as a signed release on a local web server, and checks
// that 1.0.0 installs it at startup, restarts, and comes back as 1.1.0.
func TestUpdatesItselfAtStartup(t *testing.T) {
	if testing.Short() || runtime.GOOS == "windows" {
		t.Skip("builds and runs real servers")
	}
	pub, priv, _ := ed25519.GenerateKey(rand.Reader)
	key := base64.StdEncoding.EncodeToString(pub)
	tmp := t.TempDir()
	build := func(version string) string {
		out := filepath.Join(tmp, "build-"+version, "circuitpath-server-"+update.Platform())
		cmd := exec.Command("go", "build", "-o", out,
			"-ldflags", "-X circuitpath.Version="+version+" -X circuitpath/internal/update.BuildKey="+key,
			".")
		cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
		if b, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("building %s: %v\n%s", version, err, b)
		}
		return out
	}
	oldBin, newBin := build("1.0.0"), build("1.1.0")

	// The "GitHub release".
	files := map[string][]byte{}
	release := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, ok := files[strings.TrimPrefix(r.URL.Path, "/")]
		if !ok {
			http.NotFound(w, r)
			return
		}
		w.Write(b)
	}))
	defer release.Close()
	manifest, err := update.BuildManifest("1.1.0", release.URL+"/download", map[string]string{update.Platform(): newBin})
	if err != nil {
		t.Fatal(err)
	}
	files["update.json"] = manifest
	files["update.json.sig"] = update.Sign(priv, manifest)
	files["download/"+filepath.Base(newBin)], _ = os.ReadFile(newBin)

	// The installed server.
	exe := filepath.Join(tmp, "opt", "circuitpath-server")
	os.MkdirAll(filepath.Dir(exe), 0o755)
	data, _ := os.ReadFile(oldBin)
	os.WriteFile(exe, data, 0o755)
	port := freePort(t)
	start := func() *exec.Cmd {
		cmd := exec.Command(exe, "-data", filepath.Join(tmp, "data"), "-https", "127.0.0.1:"+port, "-http", "off",
			"-hostname", "test", "-update-url", release.URL+"/update.json")
		cmd.Stdout, cmd.Stderr = os.Stderr, os.Stderr
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		return cmd
	}

	// 1.0.0 finds 1.1.0, installs it and exits to be restarted.
	cmd := start()
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		var exit *exec.ExitError
		if !errors.As(err, &exit) || exit.ExitCode() != exitRestart {
			t.Fatalf("old server exited with %v, want code %d", err, exitRestart)
		}
	case <-time.After(60 * time.Second):
		cmd.Process.Kill()
		t.Fatal("old server didn't restart for the update")
	}
	if v, _ := exec.Command(exe, "-version").Output(); strings.TrimSpace(string(v)) != "1.1.0" {
		t.Fatalf("installed binary says %q", v)
	}
	if v, _ := exec.Command(exe+".previous", "-version").Output(); strings.TrimSpace(string(v)) != "1.0.0" {
		t.Fatalf("previous binary says %q", v)
	}
	if _, err := os.Stat(filepath.Join(tmp, "data", "backups")); err != nil {
		t.Fatal("no database backup was made")
	}

	// "systemd" starts it again: now it's 1.1.0, up to date, and serving.
	cmd = start()
	defer func() {
		cmd.Process.Signal(os.Interrupt)
		cmd.Wait()
	}()
	client := &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}}
	deadline := time.Now().Add(60 * time.Second)
	for {
		res, err := client.Get("https://127.0.0.1:" + port + "/api/info")
		if err == nil {
			var info struct{ Version string }
			json.NewDecoder(res.Body).Decode(&info)
			res.Body.Close()
			if res.StatusCode == http.StatusOK {
				if info.Version != "1.1.0" {
					t.Fatalf("serving version %q", info.Version)
				}
				return
			}
		}
		if time.Now().After(deadline) {
			t.Fatalf("new server never served the app (last error %v)", err)
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func freePort(t *testing.T) string {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer l.Close()
	return strconv.Itoa(l.Addr().(*net.TCPAddr).Port)
}

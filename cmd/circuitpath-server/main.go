// Command circuitpath-server is the CircuitPath server: it serves the web app
// over HTTPS and stores students' work.
//
// On the Pi it runs from systemd with the defaults. For development:
//
//	go run ./cmd/circuitpath-server -dev
//
// then open https://localhost:8443 (accept the certificate warning, or trust
// dev-data/tls/ca.crt).
package main

import (
	"context"
	"crypto/tls"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"circuitpath"
	"circuitpath/internal/content"
	"circuitpath/internal/server"
	"circuitpath/internal/store"
	"circuitpath/internal/tlsca"
)

type config struct {
	dev        bool
	dataDir    string
	httpsAddr  string
	httpAddr   string
	hostname   string
	extraNames string
	uiDir      string
	contentDir string
	school     string
	demo       bool
}

func main() {
	var cfg config
	flag.BoolVar(&cfg.dev, "dev", false, "development mode: ports 8443/8080, data in ./dev-data, ui/ and content/ read live from disk, demo classes")
	flag.StringVar(&cfg.dataDir, "data", "", "folder for the database and certificates (default /var/lib/circuitpath, or ./dev-data with -dev)")
	flag.StringVar(&cfg.httpsAddr, "https", "", "HTTPS address (default :443, or :8443 with -dev)")
	flag.StringVar(&cfg.httpAddr, "http", "", "HTTP address that redirects to HTTPS; \"off\" to turn it off (default :80, or :8080 with -dev)")
	flag.StringVar(&cfg.hostname, "hostname", "circuitpath", "the name the Pi announces (circuitpath.local)")
	flag.StringVar(&cfg.extraNames, "extra-names", "", "comma-separated extra DNS names, e.g. circuitpath.school.vic.edu.au (set before the first start: the certificate authority only signs these names)")
	flag.StringVar(&cfg.uiDir, "ui", "", "serve the web app from this folder instead of the built-in copy")
	flag.StringVar(&cfg.contentDir, "content", "", "read content from this folder instead of the built-in copy")
	flag.StringVar(&cfg.school, "school", "", "the school name shown on the welcome screen (saved; only needed once)")
	flag.BoolVar(&cfg.demo, "demo", false, "add demo classes if there are none (always on with -dev)")
	flag.Parse()

	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	if err := run(cfg, log); err != nil {
		log.Error("CircuitPath stopped", "err", err)
		os.Exit(1)
	}
}

func run(cfg config, log *slog.Logger) error {
	def := func(v *string, prod, dev string) {
		if *v == "" {
			*v = prod
			if cfg.dev {
				*v = dev
			}
		}
	}
	def(&cfg.dataDir, "/var/lib/circuitpath", "dev-data")
	def(&cfg.httpsAddr, ":443", ":8443")
	def(&cfg.httpAddr, ":80", ":8080")
	if cfg.dev {
		def(&cfg.uiDir, "", "ui")
		def(&cfg.contentDir, "", "content")
		cfg.demo = true
	}
	if err := os.MkdirAll(cfg.dataDir, 0o750); err != nil {
		return err
	}

	db, err := store.Open(filepath.Join(cfg.dataDir, "circuitpath.db"))
	if err != nil {
		return err
	}
	defer db.Close()
	ctx := context.Background()
	if cfg.school != "" {
		if err := db.SetSetting(ctx, "school", cfg.school); err != nil {
			return err
		}
	}
	if cfg.demo {
		if err := addDemoClasses(ctx, db); err != nil {
			return err
		}
	}

	var uiFS, contentFS fs.FS = circuitpath.UI(), circuitpath.Content()
	if cfg.uiDir != "" {
		uiFS = os.DirFS(cfg.uiDir)
	}
	if cfg.contentDir != "" {
		contentFS = os.DirFS(cfg.contentDir)
	}
	cat, problems := content.Load(contentFS)
	for _, p := range problems {
		log.Warn("content problem (skipped)", "file", p.File, "problem", p.Message)
	}

	school, _ := db.Setting(ctx, "school", "")
	extra := splitList(cfg.extraNames)
	ca, err := tlsca.Open(filepath.Join(cfg.dataDir, "tls"), school, extra)
	if err != nil {
		return err
	}
	if _, err := ca.Ensure(tlsca.LocalNames(cfg.hostname, extra)); err != nil {
		return fmt.Errorf("making the HTTPS certificate: %w", err)
	}

	srv := &server.Server{
		Store:       db,
		Catalogue:   cat,
		Problems:    problems,
		UI:          uiFS,
		Version:     circuitpath.Version,
		Log:         log,
		CacheStatic: cfg.uiDir == "",
	}
	https := &http.Server{
		Addr:              cfg.httpsAddr,
		Handler:           srv.Handler(),
		TLSConfig:         &tls.Config{GetCertificate: ca.GetCertificate, MinVersion: tls.VersionTLS12},
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       60 * time.Second,
		WriteTimeout:      120 * time.Second,
		IdleTimeout:       120 * time.Second,
		ErrorLog:          slog.NewLogLogger(log.Handler(), slog.LevelDebug),
	}
	errs := make(chan error, 2)
	go func() { errs <- https.ListenAndServeTLS("", "") }()

	var redirect *http.Server
	if cfg.httpAddr != "off" {
		redirect = &http.Server{
			Addr:              cfg.httpAddr,
			Handler:           redirectHandler(cfg.httpsAddr),
			ReadHeaderTimeout: 10 * time.Second,
		}
		go func() { errs <- redirect.ListenAndServe() }()
	}

	// Keep the certificate up to date with the Pi's addresses, and tidy old logins.
	stopTicker := make(chan struct{})
	go func() {
		t := time.NewTicker(10 * time.Minute)
		defer t.Stop()
		for {
			select {
			case <-t.C:
				if issued, err := ca.Ensure(tlsca.LocalNames(cfg.hostname, extra)); err != nil {
					log.Error("renewing the HTTPS certificate", "err", err)
				} else if issued {
					log.Info("issued a new HTTPS certificate")
				}
				db.DeleteExpiredSessions(context.Background())
			case <-stopTicker:
				return
			}
		}
	}()

	log.Info("CircuitPath is ready", "version", circuitpath.Version, "urls", strings.Join(urls(cfg), " "),
		"projects", len(cat.Projects), "boards", len(cat.Boards))

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	select {
	case err := <-errs:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case s := <-sig:
		log.Info("stopping", "signal", s.String())
	}
	close(stopTicker)
	shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if redirect != nil {
		redirect.Shutdown(shutdown)
	}
	return https.Shutdown(shutdown)
}

// redirectHandler sends plain-HTTP visitors to the HTTPS site.
func redirectHandler(httpsAddr string) http.Handler {
	_, port, _ := net.SplitHostPort(httpsAddr)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host := r.Host
		if h, _, err := net.SplitHostPort(host); err == nil {
			host = h
		}
		if host == "" {
			host = "circuitpath.local"
		}
		if port != "" && port != "443" {
			host = net.JoinHostPort(host, port)
		}
		http.Redirect(w, r, "https://"+host+r.URL.RequestURI(), http.StatusMovedPermanently)
	})
}

func urls(cfg config) []string {
	_, port, _ := net.SplitHostPort(cfg.httpsAddr)
	suffix := ""
	if port != "" && port != "443" {
		suffix = ":" + port
	}
	out := []string{"https://" + cfg.hostname + ".local" + suffix}
	if cfg.dev {
		out = append(out, "https://localhost"+suffix)
	}
	for _, ip := range tlsca.LocalNames("", nil).IPs {
		if ip.To4() != nil && !ip.IsLoopback() && tlsca.IsPrivate(ip) {
			out = append(out, "https://"+ip.String()+suffix)
		}
	}
	return out
}

func splitList(s string) []string {
	var out []string
	for _, p := range strings.Split(s, ",") {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func addDemoClasses(ctx context.Context, db *store.Store) error {
	classes, err := db.ListClasses(ctx)
	if err != nil || len(classes) > 0 {
		return err
	}
	for _, name := range []string{"7B Monday", "9D Tuesday", "10A Thursday"} {
		if _, err := db.CreateClass(ctx, name); err != nil {
			return err
		}
	}
	return nil
}

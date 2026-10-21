// Package tlsca makes and looks after the Pi's own small certificate authority.
//
// On first start it creates a CA (kept in the data folder) and a server
// certificate signed by it. IT installs the CA once on the school laptops as a
// trusted root, so https://circuitpath.local shows a padlock. The server
// certificate is re-issued from the same CA whenever the Pi's names or
// addresses change or it gets close to expiry, so laptops never need the CA
// pushed again.
//
// The CA is name-constrained: it can only sign certificates for .local names,
// localhost, the extra names it was created with, and private IP addresses.
// Anyone who copies the SD card can't use the CA to impersonate other websites.
package tlsca

import (
	"bytes"
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"fmt"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const (
	caCertFile     = "ca.crt"
	caKeyFile      = "ca.key"
	serverCertFile = "server.crt"
	serverKeyFile  = "server.key"

	caLifetime     = 20 * 365 * 24 * time.Hour
	serverLifetime = 397 * 24 * time.Hour
	renewBefore    = 30 * 24 * time.Hour
)

// PrivateRanges are the IP ranges the CA may sign for.
var PrivateRanges = []string{
	"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
	"169.254.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10",
}

// IsPrivate reports whether ip is in one of the ranges the CA may sign for.
func IsPrivate(ip net.IP) bool {
	for _, r := range PrivateRanges {
		if _, ipn, err := net.ParseCIDR(r); err == nil && ipn.Contains(ip) {
			return true
		}
	}
	return false
}

// Names lists what the server certificate must cover.
type Names struct {
	DNS []string
	IPs []net.IP
}

// Authority holds the CA and the current server certificate.
type Authority struct {
	dir    string
	school string
	caCert *x509.Certificate
	caKey  crypto.Signer
	caPEM  []byte

	mu      sync.Mutex // serialises Ensure
	current atomic.Pointer[tls.Certificate]
	now     func() time.Time
}

// Open loads the CA from dir, creating it the first time. extraDomains are
// added to the CA's permitted names (for example a school DNS name that IT
// sets up); "local" and "localhost" are always permitted.
func Open(dir, school string, extraDomains []string) (*Authority, error) {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	a := &Authority{dir: dir, school: school, now: time.Now}
	certPath := filepath.Join(dir, caCertFile)
	if _, err := os.Stat(certPath); errors.Is(err, os.ErrNotExist) {
		if err := a.createCA(extraDomains); err != nil {
			return nil, fmt.Errorf("making the certificate authority: %w", err)
		}
	}
	if err := a.loadCA(); err != nil {
		return nil, fmt.Errorf("loading the certificate authority: %w", err)
	}
	return a, nil
}

// CACertPEM is the CA certificate for IT to install as a trusted root.
func (a *Authority) CACertPEM() []byte { return bytes.Clone(a.caPEM) }

// CACert returns the parsed CA certificate.
func (a *Authority) CACert() *x509.Certificate { return a.caCert }

// GetCertificate is used as tls.Config.GetCertificate.
func (a *Authority) GetCertificate(*tls.ClientHelloInfo) (*tls.Certificate, error) {
	c := a.current.Load()
	if c == nil {
		return nil, errors.New("no server certificate yet")
	}
	return c, nil
}

// Ensure makes sure the server certificate covers want and is not close to
// expiry, issuing a new one when needed. It returns true if it issued one.
func (a *Authority) Ensure(want Names) (bool, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	want = a.permittedOnly(want)
	if cert, leaf, err := a.loadServer(); err == nil && a.covers(leaf, want) {
		a.current.Store(cert)
		return false, nil
	}
	cert, err := a.issueServer(want)
	if err != nil {
		return false, err
	}
	a.current.Store(cert)
	return true, nil
}

// LocalNames returns the names the server should answer to: the hostname,
// hostname.local, localhost and the machine's current IP addresses.
func LocalNames(hostname string, extra []string) Names {
	n := Names{DNS: []string{"localhost"}}
	if hostname != "" {
		n.DNS = append(n.DNS, hostname, hostname+".local")
	}
	n.DNS = append(n.DNS, extra...)
	n.IPs = []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")}
	if addrs, err := net.InterfaceAddrs(); err == nil {
		for _, ad := range addrs {
			if ipn, ok := ad.(*net.IPNet); ok && !ipn.IP.IsLoopback() {
				n.IPs = append(n.IPs, ipn.IP)
			}
		}
	}
	return n
}

func (a *Authority) createCA(extraDomains []string) error {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	serial, err := randomSerial()
	if err != nil {
		return err
	}
	name := "CircuitPath Local CA"
	if a.school != "" {
		name = "CircuitPath Local CA (" + a.school + ")"
	}
	var ipRanges []*net.IPNet
	for _, r := range PrivateRanges {
		_, ipn, err := net.ParseCIDR(r)
		if err != nil {
			return err
		}
		ipRanges = append(ipRanges, ipn)
	}
	domains := []string{"local", "localhost"}
	for _, d := range extraDomains {
		d = strings.Trim(strings.ToLower(d), ".")
		if d != "" && !slices.Contains(domains, d) {
			domains = append(domains, d)
		}
	}
	now := time.Now()
	tmpl := &x509.Certificate{
		SerialNumber:                serial,
		Subject:                     pkix.Name{CommonName: name, Organization: []string{"CircuitPath"}},
		NotBefore:                   now.Add(-time.Hour),
		NotAfter:                    now.Add(caLifetime),
		IsCA:                        true,
		BasicConstraintsValid:       true,
		MaxPathLen:                  0,
		MaxPathLenZero:              true,
		KeyUsage:                    x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		PermittedDNSDomainsCritical: true,
		PermittedDNSDomains:         domains,
		PermittedIPRanges:           ipRanges,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, key.Public(), key)
	if err != nil {
		return err
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return err
	}
	if err := writeFileAtomic(filepath.Join(a.dir, caKeyFile), pemBlock("PRIVATE KEY", keyDER), 0o600); err != nil {
		return err
	}
	return writeFileAtomic(filepath.Join(a.dir, caCertFile), pemBlock("CERTIFICATE", der), 0o644)
}

func (a *Authority) loadCA() error {
	certPEM, err := os.ReadFile(filepath.Join(a.dir, caCertFile))
	if err != nil {
		return err
	}
	keyPEM, err := os.ReadFile(filepath.Join(a.dir, caKeyFile))
	if err != nil {
		return err
	}
	pair, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		return err
	}
	cert, err := x509.ParseCertificate(pair.Certificate[0])
	if err != nil {
		return err
	}
	signer, ok := pair.PrivateKey.(crypto.Signer)
	if !ok || !cert.IsCA {
		return errors.New("ca.crt is not a CA certificate")
	}
	a.caCert, a.caKey, a.caPEM = cert, signer, certPEM
	return nil
}

func (a *Authority) loadServer() (*tls.Certificate, *x509.Certificate, error) {
	pair, err := tls.LoadX509KeyPair(filepath.Join(a.dir, serverCertFile), filepath.Join(a.dir, serverKeyFile))
	if err != nil {
		return nil, nil, err
	}
	leaf, err := x509.ParseCertificate(pair.Certificate[0])
	if err != nil {
		return nil, nil, err
	}
	pair.Leaf = leaf
	return &pair, leaf, nil
}

// covers reports whether leaf was signed by this CA, is not near expiry and
// includes every wanted name.
func (a *Authority) covers(leaf *x509.Certificate, want Names) bool {
	if leaf.CheckSignatureFrom(a.caCert) != nil {
		return false
	}
	if a.now().Add(renewBefore).After(leaf.NotAfter) {
		return false
	}
	for _, d := range want.DNS {
		if !slices.Contains(leaf.DNSNames, d) {
			return false
		}
	}
	for _, ip := range want.IPs {
		if !slices.ContainsFunc(leaf.IPAddresses, ip.Equal) {
			return false
		}
	}
	return true
}

// permittedOnly drops names the CA's constraints wouldn't allow (a public IP
// address, say), so a certificate is still issued for the rest.
func (a *Authority) permittedOnly(want Names) Names {
	var out Names
	for _, d := range want.DNS {
		d = strings.ToLower(strings.TrimSuffix(d, "."))
		if d == "" || slices.Contains(out.DNS, d) {
			continue
		}
		if len(a.caCert.PermittedDNSDomains) == 0 || slices.ContainsFunc(a.caCert.PermittedDNSDomains, func(p string) bool {
			p = strings.TrimPrefix(p, ".")
			return d == p || strings.HasSuffix(d, "."+p)
		}) {
			out.DNS = append(out.DNS, d)
		}
	}
	for _, ip := range want.IPs {
		if ip == nil || slices.ContainsFunc(out.IPs, ip.Equal) {
			continue
		}
		if len(a.caCert.PermittedIPRanges) == 0 || slices.ContainsFunc(a.caCert.PermittedIPRanges, func(r *net.IPNet) bool { return r.Contains(ip) }) {
			out.IPs = append(out.IPs, ip)
		}
	}
	return out
}

func (a *Authority) issueServer(want Names) (*tls.Certificate, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, err
	}
	serial, err := randomSerial()
	if err != nil {
		return nil, err
	}
	cn := "circuitpath.local"
	if len(want.DNS) > 0 {
		cn = want.DNS[0]
	}
	now := a.now()
	tmpl := &x509.Certificate{
		SerialNumber: serial,
		Subject:      pkix.Name{CommonName: cn, Organization: []string{"CircuitPath"}},
		NotBefore:    now.Add(-time.Hour),
		NotAfter:     now.Add(serverLifetime),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:     want.DNS,
		IPAddresses:  want.IPs,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, a.caCert, key.Public(), a.caKey)
	if err != nil {
		return nil, err
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, err
	}
	certPEM := append(pemBlock("CERTIFICATE", der), a.caPEM...)
	keyPEM := pemBlock("PRIVATE KEY", keyDER)
	if err := writeFileAtomic(filepath.Join(a.dir, serverKeyFile), keyPEM, 0o600); err != nil {
		return nil, err
	}
	if err := writeFileAtomic(filepath.Join(a.dir, serverCertFile), certPEM, 0o644); err != nil {
		return nil, err
	}
	pair, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		return nil, err
	}
	pair.Leaf, err = x509.ParseCertificate(der)
	return &pair, err
}

func randomSerial() (*big.Int, error) {
	return rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
}

func pemBlock(typ string, der []byte) []byte {
	return pem.EncodeToMemory(&pem.Block{Type: typ, Bytes: der})
}

// writeFileAtomic writes to a temporary file, syncs it and renames it into
// place, so a power cut never leaves a half-written key.
func writeFileAtomic(path string, data []byte, perm os.FileMode) error {
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
	return os.Rename(tmp.Name(), path)
}

package tlsca

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func verify(t *testing.T, a *Authority, host string) error {
	t.Helper()
	cert, err := a.GetCertificate(nil)
	if err != nil {
		t.Fatal(err)
	}
	roots := x509.NewCertPool()
	roots.AddCert(a.CACert())
	_, err = cert.Leaf.Verify(x509.VerifyOptions{DNSName: host, Roots: roots})
	return err
}

func TestCreatesCAOnceAndIssuesServerCert(t *testing.T) {
	dir := t.TempDir()
	a, err := Open(dir, "BNTS", nil)
	if err != nil {
		t.Fatal(err)
	}
	want := Names{DNS: []string{"circuitpath.local", "localhost"}, IPs: []net.IP{net.ParseIP("192.168.1.20")}}
	issued, err := a.Ensure(want)
	if err != nil || !issued {
		t.Fatalf("Ensure = %v, %v; want a new certificate", issued, err)
	}
	for _, host := range []string{"circuitpath.local", "localhost", "192.168.1.20"} {
		if err := verify(t, a, host); err != nil {
			t.Errorf("%s: %v", host, err)
		}
	}
	if fi, err := os.Stat(filepath.Join(dir, caKeyFile)); err != nil || fi.Mode().Perm() != 0o600 {
		t.Errorf("ca.key permissions: %v %v", fi.Mode(), err)
	}

	// Opening again keeps the same CA and the same server certificate.
	b, err := Open(dir, "BNTS", nil)
	if err != nil {
		t.Fatal(err)
	}
	if !b.CACert().Equal(a.CACert()) {
		t.Fatal("CA changed between starts")
	}
	issued, err = b.Ensure(want)
	if err != nil || issued {
		t.Fatalf("second Ensure = %v, %v; want the saved certificate", issued, err)
	}
}

func TestReissuesWhenAddressChanges(t *testing.T) {
	a, err := Open(t.TempDir(), "", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := a.Ensure(Names{DNS: []string{"circuitpath.local"}, IPs: []net.IP{net.ParseIP("10.0.0.5")}}); err != nil {
		t.Fatal(err)
	}
	issued, err := a.Ensure(Names{DNS: []string{"circuitpath.local"}, IPs: []net.IP{net.ParseIP("10.0.0.9")}})
	if err != nil || !issued {
		t.Fatalf("Ensure after new IP = %v, %v; want a new certificate", issued, err)
	}
	if err := verify(t, a, "10.0.0.9"); err != nil {
		t.Fatal(err)
	}
}

func TestRenewsNearExpiry(t *testing.T) {
	a, err := Open(t.TempDir(), "", nil)
	if err != nil {
		t.Fatal(err)
	}
	want := Names{DNS: []string{"circuitpath.local"}}
	if _, err := a.Ensure(want); err != nil {
		t.Fatal(err)
	}
	a.now = func() time.Time { return time.Now().Add(380 * 24 * time.Hour) }
	issued, err := a.Ensure(want)
	if err != nil || !issued {
		t.Fatalf("Ensure near expiry = %v, %v; want a renewed certificate", issued, err)
	}
}

func TestNameConstraints(t *testing.T) {
	a, err := Open(t.TempDir(), "", []string{"school.example.edu.au"})
	if err != nil {
		t.Fatal(err)
	}
	// Public names and addresses are dropped rather than signed.
	_, err = a.Ensure(Names{
		DNS: []string{"circuitpath.local", "circuitpath.school.example.edu.au", "www.google.com"},
		IPs: []net.IP{net.ParseIP("8.8.8.8"), net.ParseIP("192.168.0.4")},
	})
	if err != nil {
		t.Fatal(err)
	}
	cert, _ := a.GetCertificate(nil)
	for _, d := range cert.Leaf.DNSNames {
		if d == "www.google.com" {
			t.Fatal("signed a public name")
		}
	}
	for _, ip := range cert.Leaf.IPAddresses {
		if ip.Equal(net.ParseIP("8.8.8.8")) {
			t.Fatal("signed a public IP")
		}
	}
	if err := verify(t, a, "circuitpath.school.example.edu.au"); err != nil {
		t.Fatal(err)
	}

	// Even a certificate made directly with the CA key fails for an outside name.
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(99),
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(time.Hour),
		DNSNames:     []string{"www.google.com"},
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, a.caCert, key.Public(), a.caKey)
	if err != nil {
		t.Fatal(err)
	}
	forged, _ := x509.ParseCertificate(der)
	roots := x509.NewCertPool()
	roots.AddCert(a.CACert())
	if _, err := forged.Verify(x509.VerifyOptions{DNSName: "www.google.com", Roots: roots}); err == nil {
		t.Fatal("a forged certificate for www.google.com verified")
	}
}

// Command updatesign writes and signs update.json for a release (the release
// workflow runs it).
//
//	CIRCUITPATH_UPDATE_KEY=... go run ./tools/updatesign -version 1.2.3 \
//	  -base-url https://github.com/OWNER/REPO/releases/download/v1.2.3 -out dist \
//	  linux-arm64=dist/circuitpath-server-linux-arm64 linux-amd64=dist/circuitpath-server-linux-amd64
//
// It refuses to sign with a key that doesn't match the committed public key,
// because Pis would reject the update.
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"circuitpath/internal/update"
)

func main() {
	version := flag.String("version", "", "the release's version, like 1.2.3")
	baseURL := flag.String("base-url", "", "where the release's files can be downloaded from")
	out := flag.String("out", ".", "folder to write update.json and update.json.sig to")
	keyEnv := flag.String("key-env", "CIRCUITPATH_UPDATE_KEY", "environment variable holding the private key")
	flag.Parse()

	fail := func(format string, args ...any) {
		fmt.Fprintf(os.Stderr, "updatesign: "+format+"\n", args...)
		os.Exit(1)
	}
	priv, err := update.ParsePrivateKey(os.Getenv(*keyEnv))
	if err != nil {
		fail("$%s doesn't hold an update private key (make one with: go run ./tools/updatekey)", *keyEnv)
	}
	pub, ok := update.PublicKey()
	if !ok {
		fail("internal/update/update-public-key.txt has no key yet (go run ./tools/updatekey)")
	}
	if !pub.Equal(priv.Public()) {
		fail("the private key in $%s doesn't match internal/update/update-public-key.txt", *keyEnv)
	}
	if *baseURL == "" || flag.NArg() == 0 {
		fail("give -base-url and at least one platform=file")
	}
	files := map[string]string{}
	for _, arg := range flag.Args() {
		platform, path, ok := strings.Cut(arg, "=")
		if !ok {
			fail("%q should look like linux-arm64=path/to/binary", arg)
		}
		files[platform] = path
	}
	manifest, err := update.BuildManifest(*version, *baseURL, files)
	if err != nil {
		fail("%v", err)
	}
	sig := update.Sign(priv, manifest)
	if err := update.Verify(pub, manifest, sig); err != nil {
		fail("%v", err)
	}
	if err := os.WriteFile(filepath.Join(*out, update.ManifestName), manifest, 0o644); err != nil {
		fail("%v", err)
	}
	if err := os.WriteFile(filepath.Join(*out, update.SigName), sig, 0o644); err != nil {
		fail("%v", err)
	}
	fmt.Printf("Signed %s for version %s.\n", filepath.Join(*out, update.ManifestName), *version)
}

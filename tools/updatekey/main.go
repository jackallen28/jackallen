// Command updatekey makes CircuitPath's update signing key (once).
//
//	go run ./tools/updatekey
//
// It writes the public key into internal/update/update-public-key.txt (commit
// it) and prints the private key once, to paste into the GitHub secret
// CIRCUITPATH_UPDATE_KEY. Pis only install updates signed with that key.
package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"flag"
	"fmt"
	"os"

	"circuitpath/internal/update"
)

func main() {
	path := flag.String("public", "internal/update/update-public-key.txt", "the public key file to write")
	force := flag.Bool("force", false, "replace an existing key (Pis with the old key will need the next version installed by hand)")
	flag.Parse()

	if old, err := os.ReadFile(*path); err == nil {
		if _, err := update.ParsePublicKey(string(old)); err == nil && !*force {
			fmt.Fprintf(os.Stderr, "%s already has a key. Use -force only if the private key was lost or leaked.\n", *path)
			os.Exit(1)
		}
	}
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	file := "# CircuitPath's update public key (base64 Ed25519). The Pi only installs\n" +
		"# updates signed with the matching private key, which lives in the GitHub\n" +
		"# secret CIRCUITPATH_UPDATE_KEY. Made with: go run ./tools/updatekey\n" +
		base64.StdEncoding.EncodeToString(pub) + "\n"
	if err := os.WriteFile(*path, []byte(file), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf(`Wrote the public key to %s. Commit that file.

Now add the private key to GitHub, once:
  1. Open the repository on github.com > Settings > Secrets and variables > Actions.
  2. New repository secret. Name: CIRCUITPATH_UPDATE_KEY
  3. Secret (copy this line exactly):

%s

Keep it secret: anyone with it can make updates every Pi will install.
Don't save it in the repository. This is the only time it's shown.
`, *path, base64.StdEncoding.EncodeToString(priv.Seed()))
}

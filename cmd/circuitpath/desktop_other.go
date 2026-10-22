//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
)

// openBrowser opens url in the default browser (for development on a Mac
// or Linux; on Windows it opens an Edge or Chrome app window).
func openBrowser(url string) error {
	name := "xdg-open"
	if runtime.GOOS == "darwin" {
		name = "open"
	}
	cmd := exec.Command(name, url)
	if err := cmd.Start(); err != nil {
		return err
	}
	go cmd.Wait()
	return nil
}

func showError(title, text string) {
	fmt.Fprintf(os.Stderr, "%s: %s\n", title, text)
}

// Command packboards builds the board tools bundle for CircuitPath (CI runs
// it after -setup-arduino on each operating system):
//
//	go run ./tools/packboards -in $RUNNER_TEMP/cp/arduino -out dist/boards.zip
//	go run ./tools/packboards -append dist/CircuitPath.exe -bundle dist/boards.zip
//
// The first packs an installed Arduino folder (see internal/arduino); the
// second adds the bundle to the end of CircuitPath.exe.
package main

import (
	"flag"
	"fmt"
	"os"

	"circuitpath/internal/arduino"
)

func main() {
	in := flag.String("in", "", "the Arduino folder made by -setup-arduino")
	out := flag.String("out", "boards.zip", "the bundle to write")
	appendTo := flag.String("append", "", "add -bundle to the end of this program instead")
	bundle := flag.String("bundle", "boards.zip", "the bundle to add (with -append)")
	flag.Parse()
	if err := run(*in, *out, *appendTo, *bundle); err != nil {
		fmt.Fprintln(os.Stderr, "packboards:", err)
		os.Exit(1)
	}
}

func run(in, out, appendTo, bundle string) error {
	if appendTo != "" {
		if err := arduino.AppendBundle(appendTo, bundle); err != nil {
			return err
		}
		b, err := arduino.OpenBundle(appendTo)
		if err != nil {
			return fmt.Errorf("checking %s: %w", appendTo, err)
		}
		defer b.Close()
		fmt.Printf("added the board tools to %s (%d families)\n", appendTo, len(b.Manifest.Families))
		return nil
	}
	env := &arduino.Env{Dir: in}
	if !env.Ready() {
		return fmt.Errorf("%s has no board tools installed at the pinned versions (run -setup-arduino)", in)
	}
	f, err := os.Create(out)
	if err != nil {
		return err
	}
	m, err := arduino.Pack(in, f, arduino.Pinned().Hash())
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		return err
	}
	fi, _ := os.Stat(out)
	fmt.Printf("wrote %s (%.0f MB) for %s/%s\n", out, float64(fi.Size())/1e6, m.OS, m.Arch)
	for _, fam := range append([]string{"common"}, arduino.Families...) {
		info := m.Families[fam]
		fmt.Printf("  %-8s %6d files %8.0f MB unpacked\n", fam, info.Files, float64(info.Bytes)/1e6)
	}
	return nil
}

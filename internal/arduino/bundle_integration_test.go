package arduino

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"circuitpath/internal/content"
)

// TestRealBundle unpacks a real bundle (CI sets CIRCUITPATH_BOARDS to a
// boards.zip or a CircuitPath.exe with the tools appended) and compiles for
// every board: a blink everywhere, the whole kit check (every library) on
// the boards whose tools were trimmed when packing, and a broken sketch.
func TestRealBundle(t *testing.T) {
	path := os.Getenv("CIRCUITPATH_BOARDS")
	if path == "" {
		t.Skip("CIRCUITPATH_BOARDS isn't set")
	}
	b, err := OpenBundle(path)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	if b.Manifest.Hash != Pinned().Hash() {
		t.Fatalf("the bundle has tools %s, this build pins %s", b.Manifest.Hash, Pinned().Hash())
	}
	data := t.TempDir()
	tools := NewTools(b, data, nil)
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Minute)
	defer cancel()

	type board struct {
		ID       string `json:"id"`
		FQBN     string `json:"fqbn"`
		Variants []struct {
			FQBN string `json:"fqbn"`
		} `json:"variants"`
	}
	files, _ := filepath.Glob("../../content/boards/*.json")
	if len(files) == 0 {
		t.Fatal("no boards")
	}
	blink := "void setup() {\n  pinMode(LED_BUILTIN, OUTPUT);\n  Serial.begin(9600);\n}\n\nvoid loop() {\n  digitalWrite(LED_BUILTIN, HIGH);\n  delay(500);\n  digitalWrite(LED_BUILTIN, LOW);\n  delay(500);\n  Serial.println(\"blink\");\n}\n"
	for _, f := range files {
		raw, _ := os.ReadFile(f)
		var bd board
		if err := json.Unmarshal(raw, &bd); err != nil {
			t.Fatal(err)
		}
		fqbns := []string{bd.FQBN}
		for _, v := range bd.Variants {
			fqbns = append(fqbns, v.FQBN)
		}
		for _, fqbn := range fqbns {
			sketches := map[string]string{"blink": blink}
			if bd.ID == "uno" || strings.HasPrefix(fqbn, "esp32:") {
				sketches["kit check"] = string(kitCheckSketch)
			}
			for name, code := range sketches {
				start := time.Now()
				res, err := tools.Compile(ctx, code, fqbn, nil)
				if err != nil || !res.OK {
					t.Errorf("%s, %s: %v\n%s", fqbn, name, err, tail(res.Output, 40))
					continue
				}
				if res.Size == nil {
					t.Errorf("%s, %s: no size reported; output starts %q", fqbn, name, firstChars(res.Output, 400))
					continue
				}
				t.Logf("%-45s %-9s ok in %s (flash %d of %d)", fqbn, name, time.Since(start).Round(time.Second), res.Size.Flash, res.Size.FlashMax)
			}
		}
	}

	res, err := tools.Compile(ctx, "void setup() {\n  pinMode(13, OUTPUT)\n}\n\nvoid loop() {\n  digitalwrite(13, HIGH);\n}\n", "arduino:avr:uno", nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.OK || len(res.Diagnostics) == 0 {
		t.Fatalf("a broken sketch compiled: %+v", res)
	}
	found := map[string]bool{}
	for _, d := range res.Diagnostics {
		t.Logf("diagnostic: %+v", d)
		if d.File == "sketch.ino" && d.Severity == "error" {
			found[strings.SplitN(d.Message, " ", 2)[0]+":"+strconv.Itoa(d.Line)] = true
		}
	}
	if !found["expected:2"] && !found["expected:3"] {
		t.Errorf("no \"expected ';'\" error on line 2 or 3: %+v", res.Diagnostics)
	}
	// Every broken sketch in the Coach's errors database gives a compiler
	// message that maps to its own entry.
	cat, problems := content.Load(os.DirFS("../../content"))
	if len(problems) > 0 {
		t.Fatal(problems)
	}
	for _, e := range cat.Errors {
		if e.Example == "" {
			continue
		}
		boardID := e.ExampleBoard
		if boardID == "" {
			boardID = "uno"
		}
		b, ok := cat.Board(boardID)
		if !ok {
			t.Errorf("%s: unknown board %s", e.ID, boardID)
			continue
		}
		res, err := tools.Compile(ctx, e.Example, b.FQBN, nil)
		if err != nil {
			t.Errorf("%s: %v", e.ID, err)
			continue
		}
		text := CoachText(res.Diagnostics)
		got, _ := content.MatchError(cat.Errors, "compile", text)
		switch {
		case res.OK:
			t.Errorf("%s: the example compiled", e.ID)
		case got == nil || got.ID != e.ID:
			t.Errorf("%s: the compiler said %q, which maps to %v", e.ID, text, got)
		default:
			t.Logf("errors.json %-28s <- %q", e.ID, strings.SplitN(text, "\n", 2)[0])
		}
	}

	for fam, st := range tools.Status() {
		t.Logf("%s: %s", fam, st.State)
	}
}

func firstChars(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

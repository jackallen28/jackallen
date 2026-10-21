package store

import (
	"context"
	"encoding/json"
	"errors"
	"path/filepath"
	"testing"
	"time"
)

func openTest(t *testing.T) *Store {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "cp.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func TestMigrations(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cp.db")
	s, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	if v, _ := s.Version(ctx); v != SchemaVersion {
		t.Fatalf("version = %d, want %d", v, SchemaVersion)
	}
	var mode string
	s.db.QueryRow("PRAGMA journal_mode").Scan(&mode)
	if mode != "wal" {
		t.Errorf("journal_mode = %q, want wal", mode)
	}
	if _, err := s.CreateClass(ctx, "9D Tuesday"); err != nil {
		t.Fatal(err)
	}
	s.Close()

	// Reopening keeps the data and doesn't re-run migrations.
	s, err = Open(path)
	if err != nil {
		t.Fatal(err)
	}
	classes, _ := s.ListClasses(ctx)
	if len(classes) != 1 {
		t.Fatalf("classes after reopen = %v", classes)
	}

	// A database from a newer server is refused, not damaged.
	s.db.Exec("PRAGMA user_version = 999")
	s.Close()
	if _, err := Open(path); err == nil {
		t.Fatal("opened a database from a newer version")
	}
}

func TestStudents(t *testing.T) {
	s := openTest(t)
	ctx := context.Background()
	c, err := s.CreateClass(ctx, "9D Tuesday")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.CreateClass(ctx, "9d tuesday"); !errors.Is(err, ErrExists) {
		t.Fatalf("duplicate class: %v", err)
	}
	st, err := s.CreateStudent(ctx, NewStudent{ClassID: c.ID, Names: []string{"Mia", "Leo"}, School: "Eltham High", PictureHash: "h"})
	if err != nil {
		t.Fatal(err)
	}
	// Same names in a different order at the same school is the same profile.
	if _, err := s.CreateStudent(ctx, NewStudent{ClassID: c.ID, Names: []string{"leo", " Mia "}, School: "eltham high", PictureHash: "h"}); !errors.Is(err, ErrExists) {
		t.Fatalf("duplicate student: %v", err)
	}
	// ...but fine in another class, or with no class.
	if _, err := s.CreateStudent(ctx, NewStudent{Names: []string{"Mia", "Leo"}, School: "Eltham High", PictureHash: "h"}); err != nil {
		t.Fatal(err)
	}
	list, err := s.ListStudents(ctx, c.ID)
	if err != nil || len(list) != 1 || list[0].Names[1] != "Leo" {
		t.Fatalf("ListStudents = %v, %v", list, err)
	}
	got, err := s.GetStudent(ctx, st.ID)
	if err != nil || got.School != "Eltham High" || got.ClassID != c.ID || string(got.Settings) != "{}" {
		t.Fatalf("GetStudent = %+v, %v", got, err)
	}
	if err := s.UpdateSettings(ctx, st.ID, json.RawMessage(`{"board":"uno"}`)); err != nil {
		t.Fatal(err)
	}
	got, _ = s.GetStudent(ctx, st.ID)
	if string(got.Settings) != `{"board":"uno"}` {
		t.Fatalf("settings = %s", got.Settings)
	}
	if _, err := s.GetStudent(ctx, 999); !errors.Is(err, ErrNotFound) {
		t.Fatalf("missing student: %v", err)
	}
}

func TestSessionsExpire(t *testing.T) {
	s := openTest(t)
	ctx := context.Background()
	st, _ := s.CreateStudent(ctx, NewStudent{Names: []string{"Ava"}, School: "X", PictureHash: "h"})
	if err := s.CreateSession(ctx, "tok", st.ID, time.Hour); err != nil {
		t.Fatal(err)
	}
	if id, err := s.SessionStudent(ctx, "tok"); err != nil || id != st.ID {
		t.Fatalf("SessionStudent = %d, %v", id, err)
	}
	s.now = func() time.Time { return time.Now().Add(2 * time.Hour) }
	if _, err := s.SessionStudent(ctx, "tok"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("expired session still works: %v", err)
	}
	s.DeleteExpiredSessions(ctx)
	var n int
	s.db.QueryRow("SELECT COUNT(*) FROM sessions").Scan(&n)
	if n != 0 {
		t.Fatalf("%d sessions left", n)
	}
}

func TestWorkIsPerStudent(t *testing.T) {
	s := openTest(t)
	ctx := context.Background()
	a, _ := s.CreateStudent(ctx, NewStudent{Names: []string{"Ava"}, School: "X", PictureHash: "h"})
	b, _ := s.CreateStudent(ctx, NewStudent{Names: []string{"Ben"}, School: "X", PictureHash: "h"})
	if _, err := s.PutSketch(ctx, a.ID, "blink", "void setup() {}"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.PutSketch(ctx, a.ID, "blink", "void setup() { }\nvoid loop() {}"); err != nil {
		t.Fatal(err)
	}
	sk, err := s.GetSketch(ctx, a.ID, "blink")
	if err != nil || sk.Code != "void setup() { }\nvoid loop() {}" {
		t.Fatalf("GetSketch = %+v, %v", sk, err)
	}
	if _, err := s.GetSketch(ctx, b.ID, "blink"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("Ben can see Ava's sketch: %v", err)
	}
	if _, err := s.PutProgress(ctx, a.ID, "blink", json.RawMessage(`{"step":2}`)); err != nil {
		t.Fatal(err)
	}
	ps, _ := s.ListProgress(ctx, a.ID)
	if len(ps) != 1 || string(ps[0].Data) != `{"step":2}` {
		t.Fatalf("ListProgress = %+v", ps)
	}
	if err := s.ImportWork(ctx, b.ID, []Sketch{{ProjectID: "dice", Code: "x", UpdatedAt: 5}}, []Progress{{ProjectID: "dice", Data: json.RawMessage(`{}`), UpdatedAt: 5}}); err != nil {
		t.Fatal(err)
	}
	sks, _ := s.ListSketches(ctx, b.ID)
	if len(sks) != 1 || sks[0].UpdatedAt != 5 {
		t.Fatalf("imported sketches = %+v", sks)
	}
}

func TestSettings(t *testing.T) {
	s := openTest(t)
	ctx := context.Background()
	if v, _ := s.Setting(ctx, "school", "BNTS"); v != "BNTS" {
		t.Fatalf("default = %q", v)
	}
	s.SetSetting(ctx, "school", "Eltham High")
	s.SetSetting(ctx, "school", "Diamond Valley")
	if v, _ := s.Setting(ctx, "school", "BNTS"); v != "Diamond Valley" {
		t.Fatalf("setting = %q", v)
	}
}

// Package storetest gives each test its own empty database: a fresh Postgres
// schema in the database named by TEST_DATABASE_URL, dropped afterwards.
package storetest

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"net/url"
	"os"
	"testing"

	"circuitpath/internal/store"
)

// URL returns a database URL for a new, empty schema (and drops it after the
// test). Tests are skipped when TEST_DATABASE_URL isn't set, except in CI.
func URL(t testing.TB) string {
	t.Helper()
	base := os.Getenv("TEST_DATABASE_URL")
	if base == "" {
		if os.Getenv("CI") != "" {
			t.Fatal("TEST_DATABASE_URL isn't set")
		}
		t.Skip("TEST_DATABASE_URL isn't set (see docs/development.md)")
	}
	b := make([]byte, 6)
	rand.Read(b)
	schema := "t_" + hex.EncodeToString(b)
	db, err := sql.Open("pgx", base)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("CREATE SCHEMA " + schema); err != nil {
		db.Close()
		t.Fatal(err)
	}
	t.Cleanup(func() {
		db.Exec("DROP SCHEMA " + schema + " CASCADE")
		db.Close()
	})
	u, err := url.Parse(base)
	if err != nil {
		t.Fatal(err)
	}
	q := u.Query()
	q.Set("search_path", schema)
	u.RawQuery = q.Encode()
	return u.String()
}

// Open opens a store on a new, empty schema.
func Open(t testing.TB) *store.Store {
	t.Helper()
	s, err := store.Open(context.Background(), URL(t))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

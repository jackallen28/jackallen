package store

import "time"

// Hooks for the store_test package.

func ExecForTest(s *Store, q string) { s.db.Exec(q) }

func SetNowForTest(s *Store, now func() time.Time) { s.now = now }

package store_test

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"circuitpath/internal/store"
	"circuitpath/internal/store/storetest"
)

var ctx = context.Background()

func TestMigrations(t *testing.T) {
	url := storetest.URL(t)
	s, err := store.Open(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	if v, _ := s.Version(ctx); v != store.SchemaVersion {
		t.Fatalf("version = %d, want %d", v, store.SchemaVersion)
	}
	if _, err := s.CreateClass(ctx, "9D Tuesday", 0); err != nil {
		t.Fatal(err)
	}
	s.Close()

	// Reopening keeps the data and doesn't re-run migrations.
	s, err = store.Open(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	classes, _ := s.ListClasses(ctx)
	if len(classes) != 1 {
		t.Fatalf("classes after reopen = %v", classes)
	}
	// A database from a newer server is refused, not damaged.
	store.ExecForTest(s, "INSERT INTO schema_version (version) VALUES (999)")
	s.Close()
	if _, err := store.Open(ctx, url); err == nil {
		t.Fatal("opened a database from a newer version")
	}
}

func TestClassesAndStudents(t *testing.T) {
	s := storetest.Open(t)
	c, err := s.CreateClass(ctx, "9D Tuesday", 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.CreateClass(ctx, "9d tuesday", 0); !errors.Is(err, store.ErrExists) {
		t.Fatalf("duplicate class: %v", err)
	}
	nums, err := s.AddStudents(ctx, c.ID, []string{"h1", "h2", "h3"}, nil)
	if err != nil || len(nums) != 3 || nums[0] != 1 || nums[2] != 3 {
		t.Fatalf("AddStudents = %v, %v", nums, err)
	}
	nums, err = s.AddStudents(ctx, c.ID, []string{"h4"}, json.RawMessage(`{"board":"uno"}`))
	if err != nil || nums[0] != 4 {
		t.Fatalf("numbering continues: %v, %v", nums, err)
	}
	if _, err := s.AddStudents(ctx, c.ID, []string{"h5", "h1"}, nil); !errors.Is(err, store.ErrExists) {
		t.Fatalf("clashing code: %v", err)
	}
	if list, _ := s.ListStudents(ctx, c.ID); len(list) != 4 {
		t.Fatalf("a failed add left students behind: %v", list)
	}
	if _, err := s.AddStudents(ctx, 9999, []string{"x"}, nil); !errors.Is(err, store.ErrNotFound) {
		t.Fatalf("missing class: %v", err)
	}

	id, err := s.StudentByCodeHash(ctx, "h2")
	if err != nil {
		t.Fatal(err)
	}
	st, err := s.GetStudent(ctx, id)
	if err != nil || st.Number != 2 || st.ClassName != "9D Tuesday" || string(st.Settings) != "{}" {
		t.Fatalf("GetStudent = %+v, %v", st, err)
	}
	if err := s.UpdateSettings(ctx, id, json.RawMessage(`{"board":"esp32"}`)); err != nil {
		t.Fatal(err)
	}
	st, _ = s.GetStudent(ctx, id)
	if string(st.Settings) != `{"board":"esp32"}` {
		t.Fatalf("settings = %s", st.Settings)
	}

	// A new code: the old one stops working and sessions end.
	s.CreateStudentSession(ctx, "tok", id, time.Hour)
	if err := s.SetStudentCode(ctx, id, "h2-new"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.StudentByCodeHash(ctx, "h2"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("old code still works")
	}
	if _, err := s.StudentSession(ctx, "tok"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("session survived a new code")
	}
	if err := s.SetStudentCode(ctx, id, "h3"); !errors.Is(err, store.ErrExists) {
		t.Fatalf("clashing new code: %v", err)
	}

	s.PutSketch(ctx, id, "blink", "x")
	list, _ := s.ListStudents(ctx, c.ID)
	if list[1].Projects != 1 || list[0].Projects != 0 {
		t.Fatalf("project counts = %+v", list)
	}
	classes, _ := s.ListClasses(ctx)
	if len(classes) != 1 || classes[0].Students != 4 {
		t.Fatalf("ListClasses = %+v", classes)
	}

	if err := s.DeleteStudent(ctx, id); err != nil {
		t.Fatal(err)
	}
	if _, err := s.GetSketch(ctx, id, "blink"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("a deleted student's work is still there")
	}
	if err := s.DeleteClass(ctx, c.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.StudentByCodeHash(ctx, "h1"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("deleting a class left its students")
	}
	if _, err := s.GetStudent(ctx, 99999); !errors.Is(err, store.ErrNotFound) {
		t.Fatalf("missing student: %v", err)
	}
}

func TestStudentSessionsExpire(t *testing.T) {
	s := storetest.Open(t)
	c, _ := s.CreateClass(ctx, "A", 0)
	s.AddStudents(ctx, c.ID, []string{"h"}, nil)
	id, _ := s.StudentByCodeHash(ctx, "h")
	if err := s.CreateStudentSession(ctx, "tok", id, time.Hour); err != nil {
		t.Fatal(err)
	}
	if got, err := s.StudentSession(ctx, "tok"); err != nil || got != id {
		t.Fatalf("StudentSession = %d, %v", got, err)
	}
	store.SetNowForTest(s, func() time.Time { return time.Now().Add(2 * time.Hour) })
	if _, err := s.StudentSession(ctx, "tok"); !errors.Is(err, store.ErrNotFound) {
		t.Fatalf("expired session still works: %v", err)
	}
	if err := s.DeleteExpiredSessions(ctx); err != nil {
		t.Fatal(err)
	}
}

func TestWorkIsPerStudent(t *testing.T) {
	s := storetest.Open(t)
	c, _ := s.CreateClass(ctx, "A", 0)
	s.AddStudents(ctx, c.ID, []string{"a", "b"}, nil)
	a, _ := s.StudentByCodeHash(ctx, "a")
	b, _ := s.StudentByCodeHash(ctx, "b")
	if _, err := s.PutSketch(ctx, a, "blink", "void setup() {}"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.PutSketch(ctx, a, "blink", "void setup() { }\nvoid loop() {}"); err != nil {
		t.Fatal(err)
	}
	sk, err := s.GetSketch(ctx, a, "blink")
	if err != nil || sk.Code != "void setup() { }\nvoid loop() {}" {
		t.Fatalf("GetSketch = %+v, %v", sk, err)
	}
	if _, err := s.GetSketch(ctx, b, "blink"); !errors.Is(err, store.ErrNotFound) {
		t.Fatalf("one student can see another's sketch: %v", err)
	}
	if _, err := s.PutProgress(ctx, a, "blink", json.RawMessage(`{"step":2}`)); err != nil {
		t.Fatal(err)
	}
	ps, _ := s.ListProgress(ctx, a)
	if len(ps) != 1 || string(ps[0].Data) != `{"step":2}` {
		t.Fatalf("ListProgress = %+v", ps)
	}
	if err := s.ImportWork(ctx, b, []store.Sketch{{ProjectID: "dice", Code: "x", UpdatedAt: 5}}, []store.Progress{{ProjectID: "dice", Data: json.RawMessage(`{}`), UpdatedAt: 5}}); err != nil {
		t.Fatal(err)
	}
	sks, _ := s.ListSketches(ctx, b)
	if len(sks) != 1 || sks[0].UpdatedAt != 5 {
		t.Fatalf("imported sketches = %+v", sks)
	}
}

func TestSettingsAndAudit(t *testing.T) {
	s := storetest.Open(t)
	if v, _ := s.Setting(ctx, "school", "BNTS"); v != "BNTS" {
		t.Fatalf("default = %q", v)
	}
	s.SetSetting(ctx, "school", "Eltham High")
	s.SetSetting(ctx, "school", "Diamond Valley")
	if v, _ := s.Setting(ctx, "school", "BNTS"); v != "Diamond Valley" {
		t.Fatalf("setting = %q", v)
	}
	st, _ := s.CreateStaff(ctx, "a@b.c", "h", "", true, false)
	s.Audit(ctx, 0, "setup", "", "1.2.3.4")
	s.Audit(ctx, st.ID, "login", "ok", "1.2.3.4")
	log, err := s.AuditLog(ctx, 10)
	if err != nil || len(log) != 2 || log[0].Action != "login" || log[0].Email != "a@b.c" || log[1].StaffID != 0 {
		t.Fatalf("AuditLog = %+v, %v", log, err)
	}
}

func TestStaff(t *testing.T) {
	s := storetest.Open(t)
	if n, _ := s.StaffCount(ctx); n != 0 {
		t.Fatal(n)
	}
	a, err := s.CreateStaff(ctx, "Admin@School.vic.edu.au", "hash", "sealed", true, true)
	if err != nil || !a.IsAdmin || a.TOTPEnabled {
		t.Fatalf("CreateStaff = %+v, %v", a, err)
	}
	if _, err := s.CreateStaff(ctx, "other@x.y", "hash", "", true, true); !errors.Is(err, store.ErrExists) {
		t.Fatalf("a second first admin: %v", err)
	}
	if _, err := s.CreateStaff(ctx, "admin@school.vic.edu.au", "hash", "", false, false); !errors.Is(err, store.ErrExists) {
		t.Fatalf("duplicate email: %v", err)
	}
	got, err := s.StaffByEmail(ctx, "ADMIN@school.vic.edu.au")
	if err != nil || got.ID != a.ID || got.TOTPSecret != "sealed" {
		t.Fatalf("StaffByEmail = %+v, %v", got, err)
	}

	// Lockout: the 3rd failure locks.
	for i, want := range []bool{false, false, true} {
		until, err := s.RecordLoginFailure(ctx, a.ID, 3, time.Minute)
		if err != nil || (until != 0) != want {
			t.Fatalf("failure %d: %d, %v", i, until, err)
		}
	}
	got, _ = s.GetStaff(ctx, a.ID)
	if got.LockedUntil == 0 || got.FailedLogins != 0 {
		t.Fatalf("after lock: %+v", got)
	}
	s.RecordLoginSuccess(ctx, a.ID)
	got, _ = s.GetStaff(ctx, a.ID)
	if got.LockedUntil != 0 || got.LastLogin == 0 {
		t.Fatalf("after success: %+v", got)
	}

	// TOTP steps can't be reused.
	s.EnableTOTP(ctx, a.ID)
	if ok, _ := s.UseTOTPStep(ctx, a.ID, 100); !ok {
		t.Fatal("first use refused")
	}
	if ok, _ := s.UseTOTPStep(ctx, a.ID, 100); ok {
		t.Fatal("same step used twice")
	}
	if ok, _ := s.UseTOTPStep(ctx, a.ID, 99); ok {
		t.Fatal("older step accepted")
	}
	if ok, _ := s.UseTOTPStep(ctx, a.ID, 101); !ok {
		t.Fatal("next step refused")
	}
	s.SetTOTPSecret(ctx, a.ID, "new")
	got, _ = s.GetStaff(ctx, a.ID)
	if got.TOTPEnabled || got.TOTPLastStep != 0 || got.TOTPSecret != "new" {
		t.Fatalf("after new secret: %+v", got)
	}

	// Recovery codes are one-time.
	s.SetRecoveryCodes(ctx, a.ID, []string{"r1", "r2"})
	if ok, _ := s.UseRecoveryCode(ctx, a.ID, "r1"); !ok {
		t.Fatal("recovery code refused")
	}
	if ok, _ := s.UseRecoveryCode(ctx, a.ID, "r1"); ok {
		t.Fatal("recovery code used twice")
	}
	if n, _ := s.RecoveryCodesLeft(ctx, a.ID); n != 1 {
		t.Fatalf("left = %d", n)
	}
	s.SetRecoveryCodes(ctx, a.ID, []string{"r3"})
	if ok, _ := s.UseRecoveryCode(ctx, a.ID, "r2"); ok {
		t.Fatal("replaced code still works")
	}

	// Sessions: MFA marking, password change signs out other sessions.
	if err := s.CreateStaffSession(ctx, "s1", a.ID, time.Hour, 0, "ip"); err != nil {
		t.Fatal(err)
	}
	s.CreateStaffSession(ctx, "s2", a.ID, time.Hour, 1, "ip")
	ss, err := s.GetStaffSession(ctx, "s1")
	if err != nil || ss.StaffID != a.ID || ss.MFAAt != 0 {
		t.Fatalf("GetStaffSession = %+v, %v", ss, err)
	}
	s.MarkStaffMFA(ctx, "s1")
	ss, _ = s.GetStaffSession(ctx, "s1")
	if ss.MFAAt == 0 {
		t.Fatal("MFA not marked")
	}
	if err := s.SetStaffPassword(ctx, a.ID, "hash2", "s1"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.GetStaffSession(ctx, "s2"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("other session survived a password change")
	}
	if _, err := s.GetStaffSession(ctx, "s1"); err != nil {
		t.Fatal("current session ended by a password change")
	}

	// Invites are one-time and expire.
	if err := s.CreateInvite(ctx, "inv", "new@x.y", false, a.ID, time.Hour); err != nil {
		t.Fatal(err)
	}
	inv, err := s.GetInvite(ctx, "inv")
	if err != nil || inv.Email != "new@x.y" {
		t.Fatalf("GetInvite = %+v, %v", inv, err)
	}
	if ok, _ := s.UseInvite(ctx, "inv"); !ok {
		t.Fatal("invite refused")
	}
	if ok, _ := s.UseInvite(ctx, "inv"); ok {
		t.Fatal("invite used twice")
	}
	s.CreateInvite(ctx, "old", "old@x.y", false, a.ID, time.Hour)
	store.SetNowForTest(s, func() time.Time { return time.Now().Add(2 * time.Hour) })
	if _, err := s.GetInvite(ctx, "old"); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("expired invite works")
	}

	if list, _ := s.ListStaff(ctx); len(list) != 1 {
		t.Fatal(list)
	}
	if err := s.DeleteStaff(ctx, a.ID); err != nil {
		t.Fatal(err)
	}
}

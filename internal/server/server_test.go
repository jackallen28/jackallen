package server

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"

	"circuitpath/internal/content"
	"circuitpath/internal/store"
)

type env struct {
	t     *testing.T
	ts    *httptest.Server
	store *store.Store
}

func newEnv(t *testing.T) *env {
	t.Helper()
	st, err := store.Open(filepath.Join(t.TempDir(), "cp.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { st.Close() })
	cat, problems := content.Load(os.DirFS("../../content"))
	if len(problems) > 0 {
		t.Fatal(problems)
	}
	s := &Server{
		Store:     st,
		Catalogue: cat,
		UI:        fstest.MapFS{"index.html": {Data: []byte("<!doctype html><title>CircuitPath</title>")}, "js/main.js": {Data: []byte("export {}")}},
		Version:   "test",
		Log:       slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
	ts := httptest.NewTLSServer(s.Handler())
	t.Cleanup(ts.Close)
	return &env{t: t, ts: ts, store: st}
}

// client is one browser, with its own cookies.
type client struct {
	e *env
	c *http.Client
}

func (e *env) client() *client {
	jar, _ := cookiejar.New(nil)
	c := e.ts.Client()
	c = &http.Client{Transport: c.Transport, Jar: jar}
	return &client{e: e, c: c}
}

func (c *client) do(method, path string, body any, headers ...string) (*http.Response, []byte) {
	c.e.t.Helper()
	var rd io.Reader
	ct := "application/json"
	switch b := body.(type) {
	case nil:
	case []byte:
		rd, ct = bytes.NewReader(b), "application/octet-stream"
	case string:
		rd = strings.NewReader(b)
	default:
		data, _ := json.Marshal(b)
		rd = bytes.NewReader(data)
	}
	req, _ := http.NewRequest(method, c.e.ts.URL+path, rd)
	if rd != nil {
		req.Header.Set("Content-Type", ct)
	}
	if method != http.MethodGet {
		req.Header.Set("X-CircuitPath", "1")
	}
	for i := 0; i+1 < len(headers); i += 2 {
		if headers[i+1] == "" {
			req.Header.Del(headers[i])
		} else {
			req.Header.Set(headers[i], headers[i+1])
		}
	}
	res, err := c.c.Do(req)
	if err != nil {
		c.e.t.Fatal(err)
	}
	defer res.Body.Close()
	data, _ := io.ReadAll(res.Body)
	return res, data
}

func (c *client) want(status int, method, path string, body any, headers ...string) []byte {
	c.e.t.Helper()
	res, data := c.do(method, path, body, headers...)
	if res.StatusCode != status {
		c.e.t.Fatalf("%s %s = %d %s, want %d", method, path, res.StatusCode, data, status)
	}
	return data
}

var pics = []string{"cat", "rocket", "apple"}

func (c *client) signUp(classID int64, names ...string) meResponse {
	c.e.t.Helper()
	var me meResponse
	data := c.want(http.StatusCreated, "POST", "/api/students", map[string]any{
		"class_id": classID, "names": names, "school": "Eltham High", "pictures": pics,
	})
	json.Unmarshal(data, &me)
	return me
}

func TestInfoCatalogueAndStatic(t *testing.T) {
	e := newEnv(t)
	c := e.client()
	var info map[string]any
	json.Unmarshal(c.want(200, "GET", "/api/info", nil), &info)
	if info["school"] != defaultSchool || len(info["pictures"].([]any)) != 9 {
		t.Fatalf("info = %v", info)
	}
	var cat struct {
		Projects []map[string]any
		Boards   []map[string]any
	}
	json.Unmarshal(c.want(200, "GET", "/api/catalogue", nil), &cat)
	if len(cat.Projects) < 20 || len(cat.Boards) < 4 || cat.Projects[0]["steps"] != nil {
		t.Fatalf("catalogue: %d projects, %d boards", len(cat.Projects), len(cat.Boards))
	}
	c.want(200, "GET", "/api/projects/blink-traffic-lights", nil)
	c.want(404, "GET", "/api/projects/nope", nil)
	c.want(404, "GET", "/api/nothing-here", nil)

	res, body := c.do("GET", "/", nil)
	if res.StatusCode != 200 || !strings.Contains(string(body), "CircuitPath") {
		t.Fatalf("GET / = %d %s", res.StatusCode, body)
	}
	if csp := res.Header.Get("Content-Security-Policy"); !strings.Contains(csp, "default-src 'self'") {
		t.Errorf("CSP = %q", csp)
	}
	res, _ = c.do("GET", "/js/main.js", nil)
	if ct := res.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/javascript") {
		t.Errorf("main.js Content-Type = %q", ct)
	}
	c.want(404, "GET", "/missing.js", nil)
}

func TestSignUpWithoutClasses(t *testing.T) {
	e := newEnv(t)
	c := e.client()
	if string(c.want(200, "GET", "/api/classes", nil)) != "[]\n" {
		t.Fatal("expected no classes")
	}
	me := c.signUp(0, "mia", "Leo")
	if me.Student.Names[0] != "Mia" || me.Settings.Board != "uno" || me.Settings.HelpLevel != "" || !me.Settings.Nudges {
		t.Fatalf("me = %+v", me)
	}
	c.want(200, "GET", "/api/me", nil)
	var list []store.StudentSummary
	json.Unmarshal(c.want(200, "GET", "/api/classes/0/students", nil), &list)
	if len(list) != 1 || list[0].Names[1] != "Leo" {
		t.Fatalf("students = %+v", list)
	}
	// The same names at the same school can't be made twice.
	c2 := e.client()
	c2.want(409, "POST", "/api/students", map[string]any{
		"class_id": 0, "names": []string{"Leo", "Mia"}, "school": "eltham high", "pictures": pics,
	})
}

func TestSignUpChecksInput(t *testing.T) {
	e := newEnv(t)
	cls, _ := e.store.CreateClass(context.Background(), "9D Tuesday")
	c := e.client()
	ok := map[string]any{"class_id": cls.ID, "names": []string{"Ava"}, "school": "Eltham High", "pictures": pics}
	bad := []map[string]any{
		{"class_id": 0, "names": []string{"Ava"}, "school": "Eltham High", "pictures": pics},              // classes exist now
		{"class_id": 999, "names": []string{"Ava"}, "school": "Eltham High", "pictures": pics},            // no such class
		{"class_id": cls.ID, "names": []string{}, "school": "Eltham High", "pictures": pics},              // no names
		{"class_id": cls.ID, "names": []string{"A", "B", "C", "D", "E"}, "school": "X", "pictures": pics}, // 5 names
		{"class_id": cls.ID, "names": []string{"<script>"}, "school": "X", "pictures": pics},
		{"class_id": cls.ID, "names": []string{"Ava", "ava"}, "school": "X", "pictures": pics},
		{"class_id": cls.ID, "names": []string{"Ava"}, "school": "", "pictures": pics},
		{"class_id": cls.ID, "names": []string{"Ava"}, "school": "X", "pictures": []string{"cat", "cat", "sun"}},
		{"class_id": cls.ID, "names": []string{"Ava"}, "school": "X", "pictures": pics, "surname": "Smith"},
	}
	for _, b := range bad {
		if res, data := c.do("POST", "/api/students", b); res.StatusCode != 400 {
			t.Errorf("%v: %d %s", b, res.StatusCode, data)
		}
	}
	if res, _ := c.do("POST", "/api/students", "{not json"); res.StatusCode != 400 {
		t.Errorf("bad JSON = %d", res.StatusCode)
	}
	c.want(201, "POST", "/api/students", ok)
}

func TestCrossSiteWritesAreBlocked(t *testing.T) {
	e := newEnv(t)
	c := e.client()
	body := map[string]any{"class_id": 0, "names": []string{"Ava"}, "school": "X", "pictures": pics}
	c.want(403, "POST", "/api/students", body, "X-CircuitPath", "")
	c.want(403, "POST", "/api/students", body, "Sec-Fetch-Site", "cross-site")
	c.want(201, "POST", "/api/students", body, "Sec-Fetch-Site", "same-origin")
}

func TestLoginAndLockout(t *testing.T) {
	e := newEnv(t)
	me := e.client().signUp(0, "Ava")
	c := e.client()
	c.want(401, "GET", "/api/me", nil)
	wrong := map[string]any{"student_id": me.Student.ID, "pictures": []string{"rocket", "cat", "apple"}}
	right := map[string]any{"student_id": me.Student.ID, "pictures": pics}
	for i := 0; i < 4; i++ {
		c.want(401, "POST", "/api/login", wrong)
	}
	res, data := c.do("POST", "/api/login", wrong)
	if res.StatusCode != 429 || res.Header.Get("Retry-After") == "" || !strings.Contains(string(data), "locked") {
		t.Fatalf("5th wrong try = %d %s", res.StatusCode, data)
	}
	// Even the right pictures wait out the lock.
	c.want(429, "POST", "/api/login", right)
	c.want(404, "POST", "/api/login", map[string]any{"student_id": 999, "pictures": pics})

	// A fresh profile logs in fine.
	other := e.client().signUp(0, "Ben")
	c.want(200, "POST", "/api/login", map[string]any{"student_id": other.Student.ID, "pictures": pics})
	c.want(200, "GET", "/api/me", nil)
	c.want(204, "POST", "/api/logout", nil)
	c.want(401, "GET", "/api/me", nil)
}

func TestSettings(t *testing.T) {
	e := newEnv(t)
	c := e.client()
	c.signUp(0, "Ava")
	c.want(200, "PUT", "/api/me/settings", map[string]any{"help_level": "advanced", "board": "esp32", "nudges": false})
	var me meResponse
	json.Unmarshal(c.want(200, "GET", "/api/me", nil), &me)
	if me.Settings.HelpLevel != "advanced" || me.Settings.Board != "esp32" || me.Settings.Nudges {
		t.Fatalf("settings = %+v", me.Settings)
	}
	c.want(200, "PUT", "/api/me/settings", map[string]any{"help_level": "beginner", "board": "nano", "nudges": true, "board_variant": "old-bootloader"})
	c.want(400, "PUT", "/api/me/settings", map[string]any{"help_level": "expert", "board": "uno", "nudges": true})
	c.want(400, "PUT", "/api/me/settings", map[string]any{"help_level": "beginner", "board": "pico", "nudges": true})
	c.want(400, "PUT", "/api/me/settings", map[string]any{"help_level": "beginner", "board": "uno", "nudges": true, "board_variant": "old-bootloader"})
	c.want(400, "PUT", "/api/me/settings", map[string]any{"help_level": "beginner", "board": "uno", "theme": "dark"})
}

func TestAutosaveIsPrivate(t *testing.T) {
	e := newEnv(t)
	ava, ben := e.client(), e.client()
	ava.signUp(0, "Ava")
	ben.signUp(0, "Ben")
	code := "void setup() {\n  pinMode(13, OUTPUT);\n}\n"
	ava.want(200, "PUT", "/api/me/sketches/blink-traffic-lights", map[string]any{"code": code})
	var sk store.Sketch
	json.Unmarshal(ava.want(200, "GET", "/api/me/sketches/blink-traffic-lights", nil), &sk)
	if sk.Code != code || sk.UpdatedAt == 0 {
		t.Fatalf("sketch = %+v", sk)
	}
	ben.want(404, "GET", "/api/me/sketches/blink-traffic-lights", nil)
	e.client().want(401, "GET", "/api/me/sketches/blink-traffic-lights", nil)

	ava.want(400, "PUT", "/api/me/sketches/..%2Fx", map[string]any{"code": "x"})
	ava.want(400, "PUT", "/api/me/sketches/Bad_Name", map[string]any{"code": "x"})
	ava.want(413, "PUT", "/api/me/sketches/freeplay", map[string]any{"code": strings.Repeat("a", store.MaxSketchBytes+1)})

	ava.want(200, "PUT", "/api/me/progress/blink-traffic-lights", map[string]any{"step": 3, "stars": 2})
	ava.want(400, "PUT", "/api/me/progress/blink-traffic-lights", []int{1, 2})
	var prog []store.Progress
	json.Unmarshal(ava.want(200, "GET", "/api/me/progress", nil), &prog)
	if len(prog) != 1 || string(prog[0].Data) != `{"stars":2,"step":3}` {
		t.Fatalf("progress = %+v", prog)
	}
	json.Unmarshal(ben.want(200, "GET", "/api/me/progress", nil), &prog)
	if len(prog) != 0 {
		t.Fatalf("Ben sees progress %+v", prog)
	}
}

func TestSaveMyWorkAndOpenMyWork(t *testing.T) {
	e := newEnv(t)
	ava := e.client()
	ava.signUp(0, "Ava", "Zoë")
	ava.want(200, "PUT", "/api/me/sketches/freeplay", map[string]any{"code": "// Ava's"})
	ava.want(200, "PUT", "/api/me/sketches/blink-traffic-lights", map[string]any{"code": "// blink"})
	ava.want(200, "PUT", "/api/me/progress/blink-traffic-lights", map[string]any{"step": 2})

	res, file := ava.do("GET", "/api/me/export", nil)
	if res.StatusCode != 200 || res.Header.Get("Content-Type") != "application/zip" {
		t.Fatalf("export = %d", res.StatusCode)
	}
	if cd := res.Header.Get("Content-Disposition"); !strings.Contains(cd, `filename="Ava-Zo-_CircuitPath_`) && !strings.Contains(cd, `filename="Ava-Zo_CircuitPath_`) {
		t.Errorf("Content-Disposition = %q", cd)
	}
	if _, err := zip.NewReader(bytes.NewReader(file), int64(len(file))); err != nil {
		t.Fatal(err)
	}

	// Ben has an older blink of his own.
	ben := e.client()
	ben.signUp(0, "Ben")
	ben.want(200, "PUT", "/api/me/sketches/blink-traffic-lights", map[string]any{"code": "// Ben's newer blink"})

	var preview struct {
		SameName bool `json:"same_name"`
		Changes  []struct {
			ProjectID string `json:"project_id"`
			Action    string
		}
	}
	json.Unmarshal(ben.want(200, "POST", "/api/me/import?mode=preview", file), &preview)
	actions := map[string]string{}
	for _, c := range preview.Changes {
		actions[c.ProjectID] = c.Action
	}
	if preview.SameName || actions["freeplay"] != "add" || actions["blink-traffic-lights"] != "keep" {
		t.Fatalf("preview = %+v", preview)
	}
	var applied map[string]int
	json.Unmarshal(ben.want(200, "POST", "/api/me/import?mode=apply&replace=true", file), &applied)
	if applied["added"] != 1 || applied["replaced"] != 0 {
		t.Fatalf("applied = %v", applied)
	}
	var sk store.Sketch
	json.Unmarshal(ben.want(200, "GET", "/api/me/sketches/blink-traffic-lights", nil), &sk)
	if sk.Code != "// Ben's newer blink" {
		t.Fatal("an older copy replaced newer work")
	}
	json.Unmarshal(ben.want(200, "GET", "/api/me/sketches/freeplay", nil), &sk)
	if sk.Code != "// Ava's" {
		t.Fatal("Free Play wasn't added")
	}

	ben.want(400, "POST", "/api/me/import?mode=preview", []byte("not a zip"))
	ben.want(400, "POST", "/api/me/import?mode=sideways", file)
	ben.want(413, "POST", "/api/me/import?mode=preview", make([]byte, 9<<20))
}

func TestStoredSettingsAreLenient(t *testing.T) {
	cat, _ := content.Load(os.DirFS("../../content"))
	cases := map[string]Settings{
		`{"help_level":"advanced","board":"esp32","nudges":false,"theme":"from a newer version"}`: {HelpLevel: "advanced", Board: "esp32"},
		`{"help_level":"advanced","board":"a-removed-board","nudges":true}`:                       {HelpLevel: "advanced", Board: "uno", Nudges: true},
		`{"help_level":"guru","board":"nano","board_variant":"nope","nudges":true}`:               {Board: "nano", Nudges: true},
		`not json`: {Board: "uno", Nudges: true},
	}
	for in, want := range cases {
		if got := storedSettings([]byte(in), cat); got != want {
			t.Errorf("%s: got %+v, want %+v", in, got, want)
		}
	}
}

func TestNameCleaning(t *testing.T) {
	cases := map[string]string{
		"mia":                             "Mia",
		"  mary   jane ":                  "Mary Jane",
		"O'Brien":                         "O'Brien",
		"zoë":                             "Zoë",
		"McDonald":                        "McDonald",
		"Ngọc":                            "Ngọc",
		"123":                             "",
		"\u0301\u0301":                    "",
		"<b>":                             "",
		"":                                "",
		"abcdefghijklmnopqrstuvwxyzabcde": "",
	}
	for in, want := range cases {
		if got := cleanName(in); got != want {
			t.Errorf("cleanName(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestStartingHandler(t *testing.T) {
	st, _ := store.Open(filepath.Join(t.TempDir(), "cp.db"))
	defer st.Close()
	cat, _ := content.Load(os.DirFS("../../content"))
	s := &Server{
		Store:     st,
		Catalogue: cat,
		UI:        fstest.MapFS{"updating.html": {Data: []byte("getting ready")}, "theme.css": {Data: []byte("body{}")}},
		Log:       slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
	h := s.StartingHandler()
	for path, want := range map[string]int{"/": 503, "/api/me": 503, "/api/me/sketches/blink": 503, "/theme.css": 200} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest("GET", path, nil))
		if rec.Code != want {
			t.Errorf("%s = %d, want %d", path, rec.Code, want)
		}
		if rec.Header().Get("Content-Security-Policy") == "" {
			t.Errorf("%s has no CSP", path)
		}
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/", nil))
	if !strings.Contains(rec.Body.String(), "getting ready") {
		t.Errorf("page = %q", rec.Body.String())
	}
}

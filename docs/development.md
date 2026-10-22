# Developing CircuitPath

The brief is [CLAUDE.md](../CLAUDE.md). This page says what is built so far and how the pieces fit.

## Build progress

| Step (CLAUDE.md §13) | State |
|---|---|
| 1. Skeleton: the Windows app (`CircuitPath.exe`), SQLite, profiles, autosave, save files, the WIPE page, Vista theme, welcome → picker | **Done**; CI tests it on real Windows |
| Arduino tools pinned and checked (arduino-cli, AVR / ESP8266 / ESP32 cores, every project library, a kit-check compile for every board) | **Done**: `internal/arduino` and the CI **boards** job (not yet used by the app) |
| 2. Fritzing import + renderer | Not started |
| 3. Interpreter + simulated API, Serial Monitor | Not started |
| 4. Wiring Wizard | Not started |
| 5. Compiling for Upload, Coach, Web Serial upload | Not started (needs a decision: see below) |
| 7. Project content (steps, demos), Free Play, other tiers | Projects have their picker details only (no steps yet: they show "Coming soon") |
| 8. Adaptive coach, help levels, code review, curriculum | Help level and nudges are saved in Settings; nothing uses them yet |

## Running it

```
go run ./cmd/circuitpath -dev
```

Then open http://localhost:8080. `-dev` means:

- port 8080, no browser window, never closes by itself
- data in `./dev-data` (delete it to start again)
- `ui/` and `content/` are read from disk, so edits show on reload

Without `-dev` (as `CircuitPath.exe`): port 47820, data in `%LOCALAPPDATA%\CircuitPath`, `ui/`
and `content/` built into the program, an Edge / Chrome app window opens, and it closes itself
20 minutes after the last window closes. Other flags: `go run ./cmd/circuitpath -h`.

Build the Windows app (one file, no cgo, no console window):

```
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-H windowsgui -s -w -X circuitpath.Version=0.2.0" -o dist/CircuitPath.exe ./cmd/circuitpath
```

The icon, version details and manifest come from `cmd/circuitpath/rsrc_windows_*.syso`, made
from `cmd/circuitpath/winres/` with [go-winres](https://github.com/tc-hib/go-winres):

```
go install github.com/tc-hib/go-winres@v0.3.3
cd cmd/circuitpath && go-winres make --in winres/winres.json --arch amd64,arm64
```

## Layout

```
circuitpath.go            embeds ui/ and content/ into the program
cmd/circuitpath/          main: flags, the local web server, opening the app window, closing when idle
  desktop_windows.go      finds Edge / Chrome, message boxes
  winres/                 the icon and version details for CircuitPath.exe
internal/store/           SQLite: schema migrations, profiles, sessions, sketches, progress, wipe
internal/auth/            login tokens
internal/content/         loads content/ and checks it against content/schema
internal/savefile/        .circuit save files: write, read (with limits), merge plan
internal/server/          the JSON API and the web app's files
internal/arduino/         the pinned Arduino tools (requirements.json), their setup and the kit check
ui/                       the web app: plain HTML, CSS and ES modules, no build step
  theme.css               every colour, gradient and font, plus the Vista pieces
  app.css                 screen layouts
  js/main.js              start-up and routing (#/projects, #/project/<id>, #/freeplay, #/setup, #/wipe)
  js/screens/             welcome (login), setup, picker, workspace, WIPE
  js/dialogs/             Settings (help, board, Save / Open my work), About
  js/widgets/             window chrome and dialogs, code editor
  js/autosave.js          autosave with an offline queue (tested in Node)
  img/                    icon sprite, BNTS pixel squares
content/                  data a teacher can edit: tiers, parts, kit, boards, projects, and their JSON schemas
tests/js/                 Node tests for the web app's logic
tests/e2e/                Playwright GUI smoke test (saves screenshots to test-results/screenshots)
tests/windows/smoke.ps1   starts the real CircuitPath.exe on Windows and uses it (CI and releases)
```

## Decisions

- **A Windows app, not a server.** The school network blocked reaching a Raspberry Pi, so
  CircuitPath runs on each student laptop: a Go program serving the web app to that laptop only,
  opened in Edge / Chrome. The web app is the same one the server would have served. (The
  unfinished cloud version, with student codes and staff logins, is parked in the history at
  the "Park the unfinished cloud version" commit.)
- **Only this laptop can reach it.** It listens on `127.0.0.1` (and `::1`) only, answers only the
  `Host` names `localhost`, `127.0.0.1` and `::1` (so a website can't reach it by DNS rebinding),
  and every write must carry an `X-CircuitPath: 1` header, which other websites can't add. A
  strict Content-Security-Policy is sent with every page.
- **`http://localhost` is a secure context**, so Web Serial (upload) works without HTTPS. The
  login cookie is `HttpOnly`, `SameSite=Strict` (not `Secure`, since it's plain HTTP on localhost).
- **The same port every time (47820)**, so the browser keeps the same site, with anything it saved
  for it (like code waiting to save). A second launch finds the running copy and just opens a window.
- **It closes itself** 20 minutes after the last window closes (open windows ping every minute).
- **SQLite** via `modernc.org/sqlite` (pure Go, no cgo), in `%LOCALAPPDATA%\CircuitPath`: inside
  the Windows account, no admin rights needed. WAL mode, `synchronous=FULL`, foreign keys on. The
  schema version is `PRAGMA user_version`; migrations are append-only, and a database from a newer
  version is refused rather than touched. (Schema 1 still has the Pi's `classes` table and
  `picture_hash` column; they stay empty.)
- **Content is JSON**, checked against JSON Schemas in `content/schema`. A broken file is skipped
  and logged; it never stops the app. A project with no steps shows as "Coming soon".
- **Profiles** are 1 to 4 first names plus a school, like PiPath. No password: it's the
  student's own laptop. The same names at the same school can't be made twice.
- **The WIPE page** (`#/wipe`, linked from the welcome screen) offers a zip of everyone's
  `.circuit` files, then deletes every profile once WIPE is typed, and compacts the database
  (`VACUUM`) so the deleted work can't be read back from the file.
- **Autosave** sends code a second after typing stops. If CircuitPath has closed, the code is kept
  in IndexedDB and sent when it's back. When a project opens, a browser copy newer than the saved
  one wins; an older one is dropped.
- **Save files** (`.circuit`) are zips: `manifest.json`, `profile.json`, `progress.json`,
  `sketches.json` and `sketches/<project>.ino`. Opening one adds projects that aren't here, asks
  before replacing older work with newer copies from the file, and never replaces newer work with
  older copies. Files are size-limited and checked entry by entry.
- **The code editor** is a plain text area with line numbers for now; CodeMirror (vendored)
  replaces it when the Coach arrives.

## Still to decide: compiling for Upload

Uploading to a real board needs the sketch compiled by arduino-cli. On a laptop that means
shipping arduino-cli and the board cores with the app (roughly 300 MB for Uno / Nano, over 1 GB with
ESP32), unpacked into `%LOCALAPPDATA%` on first use; no admin rights are needed for that. The
simulator needs none of it.

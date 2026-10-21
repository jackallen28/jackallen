# Developing CircuitPath

The brief is [CLAUDE.md](../CLAUDE.md). This page says what is built so far and how the pieces fit.

## Build progress

| Step (CLAUDE.md §13) | State |
|---|---|
| 1. Skeleton: Go server, HTTPS with its own CA, SQLite, accounts + picture passwords, autosave, save files, Vista theme, login → picker | **Done** |
| Automatic updates at every startup and nightly (signed releases, database backup, rollback); release workflow | **Done**: needs the update key secret added once ([updates.md](updates.md)) |
| Installer for Raspberry Pi OS (`deploy/install.sh`): service, Arduino tools, OS updates, firewall, name | **Done**: [try-it-on-a-pi.md](try-it-on-a-pi.md); checked by the Pi simulation |
| Arduino tools pinned and checked (arduino-cli, AVR / ESP8266 / ESP32 cores, every project library, a kit-check compile for every board) | **Done**: `internal/arduino`; the CI **boards** job and the Pi simulation |
| 2. Fritzing import + renderer | Not started |
| 3. Interpreter + simulated API, Serial Monitor | Not started |
| 4. Wiring Wizard | Not started |
| 5. Compile queue, Coach, Web Serial upload | Not started |
| 6. SD card image, Teacher page | Not started |
| 7. Project content (steps, demos), Free Play, other tiers | Projects have their picker details only (no steps yet: they show "Coming soon") |
| 8. Adaptive coach, help levels, code review, curriculum | Help level and nudges are saved in Settings; nothing uses them yet |

## Running it

```
go run ./cmd/circuitpath-server -dev
```

Then open https://localhost:8443 and accept the certificate warning (or trust
`dev-data/tls/ca.crt` on your computer). `-dev` means:

- ports 8443 (HTTPS) and 8080 (redirects to HTTPS), so no root is needed
- data in `./dev-data` (delete it to start again)
- `ui/` and `content/` are read from disk, so edits show on reload
- three demo classes are added if there are none

On the Pi the defaults are ports 443 / 80 and data in `/var/lib/circuitpath`, with
`ui/` and `content/` built into the binary. Other flags: `go run ./cmd/circuitpath-server -h`.

Build the Pi's binary (one static file, no cgo):

```
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags "-s -w -X circuitpath.Version=1.0.0" -o circuitpath-server ./cmd/circuitpath-server
```

## Layout

```
circuitpath.go            embeds ui/ and content/ into the binary
cmd/circuitpath-server/   main: flags, HTTPS + redirect servers, certificate renewal
internal/tlsca/           the Pi's own certificate authority (name-constrained) and server certificate
internal/store/           SQLite: schema migrations, classes, students, sessions, sketches, progress
internal/auth/            picture passwords (bcrypt), login tokens, lockout and rate limits
internal/content/         loads content/ and checks it against content/schema
internal/savefile/        .circuit save files: write, read (with limits), merge plan
internal/server/          the JSON API and the web app's files
internal/update/          automatic updates: check, verify, download, install, roll back
internal/arduino/         the pinned Arduino tools (requirements.json), their setup and the kit check
tools/updatekey/          makes the update signing key (once)
tools/updatesign/         writes and signs update.json (the release workflow runs it)
deploy/                   install.sh (the installer) and the systemd unit
tests/pi/                 the Pi simulation: Raspberry Pi OS in a container on arm64, running install.sh
ui/                       the web app: plain HTML, CSS and ES modules, no build step
  theme.css               every colour, gradient and font, plus the Vista pieces
  app.css                 screen layouts
  js/main.js              start-up and routing (#/projects, #/project/<id>, #/freeplay, #/setup)
  js/screens/             login, setup, picker, workspace
  js/dialogs/             Settings (help, board, Save / Open my work), About
  js/widgets/             window chrome and dialogs, picture grid, code editor
  js/autosave.js          autosave with an offline queue (tested in Node)
  img/                    icon sprite, picture-password pictures, BNTS pixel squares
content/                  data a teacher can edit: tiers, parts, kit, boards, projects, and their JSON schemas
tests/js/                 Node tests for the web app's logic
tests/e2e/                Playwright GUI smoke test (saves screenshots to test-results/screenshots)
```

## Decisions made in this step

- **SQLite** via `modernc.org/sqlite` (pure Go), so the Pi binary is one static file. WAL mode,
  `synchronous=FULL`, foreign keys on. The schema version is `PRAGMA user_version`; migrations
  are append-only, and a database from a newer server is refused rather than touched.
- **Content is JSON**, checked against JSON Schemas in `content/schema` (editors such as VS Code
  use the `$schema` line in each file to show mistakes as you type). A broken file is skipped and
  logged; it never stops the server. A project with no steps shows as "Coming soon".
- **Picture passwords** are 3 of 9 pictures, tapped in order (504 combinations), hashed with
  bcrypt. Five wrong tries lock that profile for a minute. They keep classmates out of each
  other's work; they aren't meant to stop a determined attacker.
- **Profiles** are 1 to 4 first names plus a school. The same names at the same school can't be
  made twice in one class. If the teacher hasn't made any classes, the class step is skipped.
- **Logins** use a random token in an `HttpOnly`, `Secure`, `SameSite=Strict` session cookie
  (gone when the browser closes, and ended by the server after 12 hours). The database stores only
  a hash of the token. Every write must carry an `X-CircuitPath: 1` header, which other websites
  can't add, and the server sends a strict Content-Security-Policy.
- **HTTPS**: on first start the server makes a certificate authority that can only sign `.local`
  names, `localhost`, names given with `-extra-names`, and private IP addresses, so a copied SD
  card can't be used to impersonate other websites. The server certificate is re-issued from it
  when the Pi's address changes or it nears expiry. No HSTS header is sent, so a laptop that
  doesn't trust the certificate yet can still click through the warning.
- **Autosave** sends code a second after typing stops. If the server can't be reached, the code is
  kept in IndexedDB and sent when it's back ("Offline, will save when you're back"). When a project
  opens, a browser copy newer than the server's wins; an older one is dropped.
- **Save files** (`.circuit`) are zips: `manifest.json`, `profile.json`, `progress.json`,
  `sketches.json` and `sketches/<project>.ino`. Never the picture password. Opening one adds
  projects that aren't here, asks before replacing older work with newer copies from the file,
  and never replaces newer work with older copies. Files are size-limited and checked entry by
  entry.
- **Updates** happen at every startup (see [updates.md](updates.md)): signed with Ed25519 (the
  public key is committed, the private key is a GitHub secret), a database backup first, the old
  binary kept, and an automatic rollback if the new version stops 3 times in its first 2 minutes.
  While it checks, students see a "getting ready" page and the API answers 503, so autosave waits.
- **The code editor** is a plain text area with line numbers for now; CodeMirror (vendored)
  replaces it when the Coach arrives.

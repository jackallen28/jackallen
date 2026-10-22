# CircuitPath

A step-by-step Arduino and ESP coding tutor for secondary students, made for the
Banyule Nillumbik Tech School (BNTS).

- **One file on each student laptop: `CircuitPath.exe`.** Double-click it and CircuitPath opens
  in Edge or Chrome. Nothing to install, no admin rights, no server, no internet needed.
- **Welcome screen like PiPath:** students pick their name, or make a profile with their first
  name(s) and school. Work saves on the laptop by itself.
- **A WIPE page** clears the laptop for the next group (after offering to save everyone's work).
- A **simulator** for every project, and **upload to real boards** from the browser: Arduino Uno,
  Arduino Nano, NodeMCU and other ESP8266 / ESP32 boards.
- Every project starts with a **Wiring Wizard**: meet the parts, wire them step by step with
  breadboard and schematic diagrams, then a test program checks your wiring before you start coding.
- A **Coach** explains errors in plain English, with hints that adapt to each student.
  No AI: every hint was written and reviewed by teachers.
- A Windows Vista look in the school's colours.

Status: being built. The skeleton is done: the Windows app, profiles, autosave, save files, the
WIPE page, the Vista look, and welcome → setup → project picker. The full brief is in
[CLAUDE.md](CLAUDE.md); what's built so far is in [docs/development.md](docs/development.md).

## Trying it on a student laptop

Download `CircuitPath.exe` from the latest release (or from a CI run's **CircuitPath-exe**
download) and double-click it. See [docs/windows-app.md](docs/windows-app.md) for what to expect,
where the work is kept, and what to do if Windows blocks it.

## For developers

You need Go 1.24+. Node 22 is only needed to run the JavaScript and browser tests.

```
go run ./cmd/circuitpath -dev            # then open http://localhost:8080
go test ./...                            # Go tests
npm ci && npm test                       # JavaScript tests
npm run e2e                              # GUI smoke test (Playwright)
```

Build the Windows app (from any computer):

```
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-H windowsgui -s -w -X circuitpath.Version=0.2.0" -o dist/CircuitPath.exe ./cmd/circuitpath
```

See [docs/development.md](docs/development.md) for how it fits together. To publish a release,
change the `VERSION` file: the Release workflow tests on Windows and publishes `CircuitPath.exe`.

Part images come from the [Fritzing parts library](https://github.com/fritzing/fritzing-parts)
(CC BY-SA 3.0).

# CircuitPath

A step-by-step Arduino and ESP coding tutor for secondary students, made for the
Banyule Nillumbik Tech School (BNTS).

- **Runs from a Raspberry Pi 5 on the school network.** Flash the CircuitPath image onto a microSD
  card, put it in the Pi, plug in power and a network cable. No screen or keyboard needed.
- **Students just open a web page** (`https://circuitpath.local`) in Edge or Chrome. Nothing to
  install on their laptops, and their work follows them to any laptop.
- A **simulator** for every project, and **upload to real boards** from the browser: Arduino Uno,
  Arduino Nano, NodeMCU and other ESP8266 / ESP32 boards.
- Every project starts with a **Wiring Wizard**: meet the parts, wire them step by step with
  breadboard and schematic diagrams, then a test program checks your wiring before you start coding.
- A **Coach** explains errors in plain English, with hints that adapt to each student.
  No AI: every hint was written and reviewed by teachers.
- A **Teacher page** for looking after the Pi: classes, backups, Wipe session, updates.
- A Windows Vista look in the school's colours.

Status: being built. Step 1 of the build order (the skeleton) is done: the server, logins with
picture passwords, autosave, save files, the Vista look, and login → setup → project picker.
The full brief is in [CLAUDE.md](CLAUDE.md); what's built so far is in
[docs/development.md](docs/development.md).

## Setting up (when it's built)

1. Download `circuitpath-<version>.img.xz` from Releases.
2. Flash it to a 32 GB+ microSD card with **Raspberry Pi Imager** (Choose OS > Use custom).
3. Optional: open the card's boot partition on your computer and add `circuitpath.toml` (school
   name, Wi-Fi, a teacher password).
4. Put the card in a Raspberry Pi 5, plug in a network cable and power. Wait about 2 minutes
   (green light steady = ready).
5. On your laptop, open `https://circuitpath.local/teacher` and log in with the password from
   `circuitpath-first-login.txt` on the card's boot partition (or the one you set).
6. Ask IT to trust the Pi's certificate (Teacher page > Download certificate) and to install the
   CH340 / CP2102 USB drivers on student laptops (or use boards that need no driver).

## For developers

You need Go 1.24+. Node 22 is only needed to run the JavaScript and browser tests.

```
go run ./cmd/circuitpath-server -dev     # then open https://localhost:8443
go test ./...                            # server tests
npm ci && npm test                       # JavaScript tests
npm run e2e                              # GUI smoke test (Playwright)
```

See [docs/development.md](docs/development.md) for how it fits together.

Part images come from the [Fritzing parts library](https://github.com/fritzing/fritzing-parts)
(CC BY-SA 3.0).

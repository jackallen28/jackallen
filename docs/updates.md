# Automatic updates

Everything on the Pi updates itself. Nobody needs to do anything on the Pi.

| What | When |
|---|---|
| **CircuitPath** | every time the Pi starts, and every night at 03:00 |
| **Board cores and libraries** (Arduino AVR, ESP8266, ESP32, every project library) | with CircuitPath: each release pins exact, tested versions (`internal/arduino/requirements.json`); after an update the Pi installs any that changed, in the background |
| **Raspberry Pi OS** (every update, not just security fixes) | daily, by `unattended-upgrades`; if an update needs a restart, the Pi restarts at 03:30 |

All of these need the internet. Without it, everything keeps working as it is.

## CircuitPath: what happens at startup (and at 03:00)

1. The server starts and shows students a "CircuitPath is getting ready" page (it refreshes by itself).
2. It asks GitHub for the latest release's `update.json` and `update.json.sig`.
   - **No internet, or GitHub can't be reached:** it gives up within seconds and starts as it is.
   - **Already up to date:** it starts as it is.
3. If there's a newer version, it checks the release is genuine (the signature must match
   CircuitPath's update key), downloads the server for the Pi, checks its size and SHA-256, and
   checks it runs and reports the right version.
4. It backs up the database (`/var/lib/circuitpath/backups/before-update-<old>-to-<new>.db`, the
   newest 3 are kept), swaps the new server in (keeping the old one as `circuitpath-server.previous`)
   and restarts. systemd starts the new version straight away.
5. Once the new version has run for 2 minutes, the update counts as good.

**If the new version keeps stopping** (3 starts without lasting 2 minutes), the Pi puts the old
version back by itself, restores the database backup if the new version had changed the
database, and never tries that version again. A later, fixed version is installed as normal.

It never installs an older version, a version without a valid signature, or a file that doesn't
match `update.json`. A development build (`-dev`, or version `dev`) never updates itself.

## Setting up the update key (once)

Releases are signed so a Pi only installs updates that really came from you.

1. On your computer, in the repository: `go run ./tools/updatekey`
2. It writes the public key into `internal/update/update-public-key.txt`. Commit and push that file.
3. It prints the private key once. On github.com open the repository > **Settings** > **Secrets
   and variables** > **Actions** > **New repository secret**. Name it `CIRCUITPATH_UPDATE_KEY`
   and paste the key. Don't save it anywhere else.

Until this is done, Pis don't update themselves (they log "no update key is set up").

A key has already been made for this repository: its public half is committed in
`internal/update/update-public-key.txt`, and the private half was handed over separately to
add as the `CIRCUITPATH_UPDATE_KEY` secret. If you'd rather make your own, run
`go run ./tools/updatekey -force` before the first Pi is set up (no Pi has the key yet, so
replacing it now costs nothing), commit the new public key and add the new private key as
the secret.

If the private key is ever leaked, make a new one with `go run ./tools/updatekey -force`. Pis
that have the old public key won't accept updates signed with the new one, so each will need
the next version installed by hand (or reflashed with a new image).

## Publishing a release

Change the `VERSION` file to the new version (e.g. `1.2.3`) and commit it. On github.com:
open `VERSION` on the `BNTS_CircuitPath` branch > the pencil (edit) > type the new version >
**Commit changes**. (Or push a tag: `git tag v1.2.3 && git push origin v1.2.3`.)

The **Release** workflow tests everything, builds the server for the Pi (`linux-arm64`, and
`linux-amd64` for testing on a PC), writes and signs `update.json`, and publishes a GitHub
release. Every Pi installs it the next time it starts.

Versions are plain `x.y.z` and must go up. A release with a problem is fixed by releasing a
higher version.

## Turning it off, proxies, testing

- **Off:** start the server with `-auto-update=false` (the Teacher page will get a switch);
  `-update-time off` turns off just the nightly check. For Raspberry Pi OS, remove
  `/etc/apt/apt.conf.d/52circuitpath-unattended-upgrades` (security updates still install).
- **School proxy:** if the Pi needs a proxy to reach GitHub, set `HTTPS_PROXY` in the systemd
  unit (`deploy/circuitpath.service` has the line to uncomment).
- **Somewhere else:** `-update-url https://.../update.json` checks another address (still signed).
- **Tests:** `go test ./cmd/circuitpath-server -run UpdatesItself` builds a 1.0.0 and a 1.1.0
  server, publishes 1.1.0 on a local web server and checks 1.0.0 installs it and comes back as 1.1.0.

## Things to know

- The server's folder (`/opt/circuitpath`) must be writable by the `circuitpath` user, so it can
  replace itself. The SD card image sets this up.
- Board cores and libraries are never upgraded to untested versions: they only change when a
  CircuitPath release changes `requirements.json`, and the CI compiles every board with the
  new versions first (the **boards** job and the Pi simulation).

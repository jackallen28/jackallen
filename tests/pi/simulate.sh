#!/usr/bin/env bash
# The Pi simulation: installs CircuitPath with deploy/install.sh on the real
# Raspberry Pi OS Lite (64-bit) userland, in a container booting systemd on an
# arm64 machine (GitHub's ubuntu-24.04-arm runner, or any arm64 Linux with
# Docker and sudo), then checks it the way a school would use it:
#
#   1. install: service running, HTTPS answering, a student can sign up
#   2. every board compiles the kit check (arduino-cli, all cores and libraries)
#   3. automatic OS updates, firewall and circuitpath.local are set up
#   4. a new release is published → restart → the Pi updates itself, work kept
#   5. the "Pi" restarts → CircuitPath comes back by itself, work kept
#
# Releases come from a local web server, signed with a throwaway key; the
# real release process is the same apart from the address and the key.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$PWD"
WORK="${WORK:-$ROOT/test-results/pi}"
IMAGE_URL="${IMAGE_URL:-https://downloads.raspberrypi.com/raspios_lite_arm64_latest}"
ARDUINO_CACHE="${ARDUINO_CACHE:-$WORK/arduino-cache}"
PORT=9443

step() { printf '\n\033[1;36m==== %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mFAILED: %s\033[0m\n' "$*" >&2; docker exec pi journalctl -u circuitpath --no-pager -n 80 2>/dev/null || true; exit 1; }
pi() { docker exec pi "$@"; }

[ "$(uname -m)" = aarch64 ] || { echo "Run this on an arm64 machine (the Pi's CPU)." >&2; exit 1; }
mkdir -p "$WORK" "$ARDUINO_CACHE"

step "Raspberry Pi OS Lite (64-bit) as a container"
if ! docker image inspect circuitpath/rpios >/dev/null 2>&1; then
  if [ ! -f "$WORK/rpios.img" ]; then
    curl -fL --retry 3 -o "$WORK/rpios.img.xz" "$IMAGE_URL"
    xz -d -f "$WORK/rpios.img.xz"
  fi
  LOOP="$(sudo losetup -Pf --show "$WORK/rpios.img")"
  sudo mkdir -p /mnt/rpios
  sudo mount -o ro "${LOOP}p2" /mnt/rpios
  sudo tar -C /mnt/rpios -c . | docker import - circuitpath/rpios-rootfs
  sudo umount /mnt/rpios
  sudo losetup -d "$LOOP"
  docker build -q -t circuitpath/rpios tests/pi
fi
docker rm -f pi >/dev/null 2>&1 || true
docker run -d --name pi --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  --tmpfs /run --tmpfs /run/lock -v "$ARDUINO_CACHE:/var/lib/circuitpath/arduino" \
  -p "$PORT:443" circuitpath/rpios >/dev/null
for _ in $(seq 1 60); do
  state="$(pi systemctl is-system-running 2>/dev/null || true)"
  case "$state" in running|degraded) break ;; esac
  sleep 2
done
echo "systemd: $state"
pi cat /etc/os-release | grep PRETTY_NAME

step "Two signed test releases (0.0.1 and 0.0.2)"
rm -rf "$WORK/release" "$WORK/key"
mkdir -p "$WORK/release" "$WORK/key"
go run ./tools/updatekey -public "$WORK/key/pub.txt" -private-out "$WORK/key/priv.txt" >/dev/null
PUB="$(grep -v '^#' "$WORK/key/pub.txt")"
LDKEY="-X circuitpath/internal/update.BuildKey=$PUB"
release() { # release VERSION
  local dir="$WORK/release/v$1"
  mkdir -p "$dir"
  CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags "-s -w -X circuitpath.Version=$1 $LDKEY" \
    -o "$dir/circuitpath-server-linux-arm64" ./cmd/circuitpath-server
  CIRCUITPATH_UPDATE_KEY="$(cat "$WORK/key/priv.txt")" go run -ldflags "$LDKEY" ./tools/updatesign -version "$1" -out "$dir" \
    -base-url "http://127.0.0.1:8600/v$1" linux-arm64="$dir/circuitpath-server-linux-arm64" >/dev/null
  cp deploy/circuitpath.service deploy/install.sh "$dir/"
  (cd "$dir" && sha256sum circuitpath-server-linux-arm64 > SHA256SUMS)
}
release 0.0.1
release 0.0.2
ln -sfn v0.0.1 "$WORK/release/latest"
pi rm -rf /srv/release
docker cp "$WORK/release" pi:/srv/release
pi bash -c 'nohup python3 -m http.server 8600 --bind 127.0.0.1 --directory /srv/release >/var/log/release-server.log 2>&1 &'
sleep 1

step "1. Install with deploy/install.sh (as on a Pi)"
start=$(date +%s)
pi bash /srv/release/v0.0.1/install.sh \
  --release-url http://127.0.0.1:8600/latest --update-url http://127.0.0.1:8600/latest/update.json \
  || fail "the installer stopped"
echo "Installed in $(( $(date +%s) - start ))s"

api() { curl -fsSk --connect-timeout 5 --max-time 20 "https://127.0.0.1:$PORT$1"; }
version() { api /api/info | sed -n 's/.*"version":"\([^"]*\)".*/\1/p'; }
wait_version() { # wait_version WANT
  for _ in $(seq 1 90); do [ "$(version 2>/dev/null)" = "$1" ] && return 0; sleep 2; done
  fail "expected version $1, got '$(version 2>/dev/null)'"
}

pi systemctl is-active circuitpath || fail "the service isn't running"
pi systemctl is-enabled circuitpath || fail "the service won't start at boot"
wait_version 0.0.1
echo "HTTPS answers from outside the Pi: version $(version)"
curl -fsSk --max-time 20 -o /dev/null "https://127.0.0.1:$PORT/" || fail "the web app isn't served"
curl -fsSk --max-time 20 -X POST -H 'Content-Type: application/json' -H 'X-CircuitPath: 1' \
  -d '{"class_id":0,"names":["Sim"],"school":"Pi Simulation High","pictures":["cat","rocket","apple"]}' \
  "https://127.0.0.1:$PORT/api/students" >/dev/null || fail "a student couldn't sign up"
api /api/classes/0/students | grep -q Sim || fail "the new student isn't listed"
echo "A student signed up."

step "2. Board cores and libraries"
pi runuser -u circuitpath -- env HOME=/var/lib/circuitpath /opt/circuitpath/circuitpath-server \
  -data /var/lib/circuitpath -check-arduino || fail "a board failed the kit check"

step "3. Automatic OS updates, firewall, name"
pi systemctl is-active avahi-daemon || fail "avahi (circuitpath.local) isn't running"
pi systemctl is-enabled apt-daily-upgrade.timer || fail "automatic OS updates aren't on"
# The update rules must name the package sources exactly as Raspberry Pi
# OS reports them (checked without downloading or installing anything).
pi apt-config dump | grep -A8 "Origins-Pattern" | tee "$WORK/allowed-origins.txt"
pi apt-cache policy > "$WORK/apt-policy.txt"
codename="$(pi sh -c '. /etc/os-release && echo "$VERSION_CODENAME"')"
echo "Package sources (codename $codename):"
grep -E '^ +release ' "$WORK/apt-policy.txt" | sort -u | sed 's/^ */  /'
grep -A2 'archive\.raspberrypi\.com' "$WORK/apt-policy.txt" | grep -q "origin archive.raspberrypi.com" \
  || fail "the Raspberry Pi archive isn't a package source"
grep -q "site=archive.raspberrypi.com" "$WORK/allowed-origins.txt" \
  || fail "Raspberry Pi OS updates aren't allowed"
grep -q "n=$codename-security,l=Debian-Security" "$WORK/apt-policy.txt" \
  || fail "the Debian security archive doesn't match the update rule"
grep -q "origin=Debian,codename=\${distro_codename}-security,label=Debian-Security" "$WORK/allowed-origins.txt" \
  || fail "Debian security updates aren't allowed"
grep -q "n=$codename-updates" "$WORK/apt-policy.txt" || fail "the Debian updates archive isn't there"
grep -q "origin=Debian,codename=\${distro_codename}-updates" "$WORK/allowed-origins.txt" \
  || fail "Debian updates aren't allowed"
pi nft list ruleset | grep -q "443" || fail "the firewall isn't loaded"
echo "Firewall loaded; unattended-upgrades will install every update."

step "4. Publish 0.0.2 → the Pi updates itself when it restarts"
pi ln -sfn v0.0.2 /srv/release/latest
pi systemctl restart circuitpath
wait_version 0.0.2
pi test -f /opt/circuitpath/circuitpath-server.previous || fail "the old version wasn't kept"
pi bash -c 'ls /var/lib/circuitpath/backups/before-update-0.0.1-to-0.0.2.db' || fail "no database backup before the update"
api /api/classes/0/students | grep -q Sim || fail "the student was lost in the update"
echo "Updated to $(version); the student's profile is still there."

step "5. The Pi restarts → CircuitPath comes back by itself"
docker restart pi >/dev/null
pi bash -c 'nohup python3 -m http.server 8600 --bind 127.0.0.1 --directory /srv/release >/var/log/release-server.log 2>&1 &'
wait_version 0.0.2
api /api/classes/0/students | grep -q Sim || fail "the student was lost after the restart"
echo "Back after the restart: version $(version), work kept."

pi journalctl -u circuitpath --no-pager > "$WORK/circuitpath.log" 2>&1 || true
printf '\n\033[1;32mThe Pi simulation passed.\033[0m\n'

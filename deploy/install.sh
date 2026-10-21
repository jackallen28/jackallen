#!/usr/bin/env bash
# CircuitPath installer for Raspberry Pi OS Lite (64-bit), on a Raspberry Pi 5.
#
# On a fresh Raspberry Pi OS card (with SSH turned on in Raspberry Pi Imager):
#   curl -fsSL https://github.com/jackallen28/jackallen/releases/latest/download/install.sh | sudo bash
#
# It installs the latest CircuitPath release as a service, the Arduino board
# cores and libraries (this part takes 15-30 minutes), automatic updates for
# CircuitPath and Raspberry Pi OS, the circuitpath.local name and a firewall.
# Run it again at any time: it only changes what needs changing.
#
# Options:
#   --proxy URL         the school's web proxy, if the Pi needs one (e.g. http://proxy:8080)
#   --hostname NAME     the Pi's name (default circuitpath → https://circuitpath.local)
#   --timezone ZONE     default Australia/Melbourne
#   --no-arduino        skip the board cores and libraries (you can't compile until they're in)
#   --no-firewall       don't set up the firewall
#   --release-url URL   install from another release (testing); default: the latest GitHub release
#   --update-url URL    check this update.json for updates (testing)
#
# The SD card image will run this same script when it's built, so nothing
# needs doing by hand on the Pi.
set -euo pipefail

REPO="jackallen28/jackallen" # the release workflow writes the real repository here
RELEASE_URL="https://github.com/${REPO}/releases/latest/download"
UPDATE_URL=""
PROXY=""
NAME="circuitpath"
TIMEZONE="Australia/Melbourne"
ARDUINO=1
FIREWALL=1

while [ $# -gt 0 ]; do
  case "$1" in
    --proxy) PROXY="$2"; shift 2 ;;
    --hostname) NAME="$2"; shift 2 ;;
    --timezone) TIMEZONE="$2"; shift 2 ;;
    --no-arduino) ARDUINO=0; shift ;;
    --no-firewall) FIREWALL=0; shift ;;
    --release-url) RELEASE_URL="${2%/}"; shift 2 ;;
    --update-url) UPDATE_URL="$2"; shift 2 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }
die() { printf '\n\033[1;31mCircuitPath could not be installed: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run it with sudo (… | sudo bash)"
case "$(uname -m)" in
  aarch64|arm64) ARCH=arm64 ;;
  x86_64|amd64) ARCH=amd64 ;;
  *) die "it needs the 64-bit Raspberry Pi OS (this is $(uname -m)). Flash 'Raspberry Pi OS Lite (64-bit)'." ;;
esac
command -v systemctl >/dev/null || die "it needs systemd (Raspberry Pi OS has it)"
command -v apt-get >/dev/null || die "it needs Raspberry Pi OS (or Debian)"
if [[ ! "$NAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then die "--hostname must be lower-case letters, numbers and dashes"; fi
[ -e "/usr/share/zoneinfo/$TIMEZONE" ] || die "unknown time zone $TIMEZONE"

if [ -n "$PROXY" ]; then
  export http_proxy="$PROXY" https_proxy="$PROXY" HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
  printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY" "$PROXY" > /etc/apt/apt.conf.d/95circuitpath-proxy
fi

step "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends ca-certificates curl avahi-daemon unattended-upgrades nftables

step "Name and time zone"
if ! timedatectl set-timezone "$TIMEZONE" 2>/dev/null; then
  ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime
  echo "$TIMEZONE" > /etc/timezone
fi
note "Time zone: $TIMEZONE"
if [ "$(hostname)" != "$NAME" ]; then
  hostnamectl set-hostname "$NAME" 2>/dev/null || { echo "$NAME" > /etc/hostname; hostname "$NAME" 2>/dev/null || true; }
  if grep -q '^127\.0\.1\.1' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NAME/" /etc/hosts
  else
    printf '127.0.1.1\t%s\n' "$NAME" >> /etc/hosts
  fi
fi
systemctl enable --now avahi-daemon >/dev/null 2>&1 || note "(avahi didn't start: circuitpath.local may not work; use the IP address)"
note "Name: $NAME.local"

step "The circuitpath user and folders"
if ! id circuitpath >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/circuitpath --no-create-home --shell /usr/sbin/nologin circuitpath
fi
install -d -o circuitpath -g circuitpath -m 750 /var/lib/circuitpath
install -d -o circuitpath -g circuitpath -m 755 /opt/circuitpath
chown -R circuitpath:circuitpath /var/lib/circuitpath /opt/circuitpath

step "Downloading CircuitPath"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fetch() { curl -fsSL --retry 3 --connect-timeout 20 -o "$2" "$1" || die "couldn't download $1 (is the Pi on the internet${PROXY:+ through $PROXY}?)"; }
BIN="circuitpath-server-linux-$ARCH"
fetch "$RELEASE_URL/$BIN" "$TMP/$BIN"
fetch "$RELEASE_URL/SHA256SUMS" "$TMP/SHA256SUMS"
fetch "$RELEASE_URL/circuitpath.service" "$TMP/circuitpath.service"
(cd "$TMP" && grep " $BIN\$" SHA256SUMS | sha256sum -c --quiet -) || die "the download doesn't match its checksum; try again"
chmod 755 "$TMP/$BIN"
VERSION="$("$TMP/$BIN" -version)" || die "the downloaded server doesn't run on this Pi"
note "Version $VERSION"

if systemctl is-active --quiet circuitpath; then systemctl stop circuitpath; fi
install -o circuitpath -g circuitpath -m 755 "$TMP/$BIN" /opt/circuitpath/circuitpath-server
rm -f /opt/circuitpath/circuitpath-server.previous
install -m 644 "$TMP/circuitpath.service" /etc/systemd/system/circuitpath.service
mkdir -p /etc/systemd/system/circuitpath.service.d
{
  echo "# Written by install.sh"
  echo "[Service]"
  if [ -n "$PROXY" ]; then
    echo "Environment=HTTPS_PROXY=$PROXY HTTP_PROXY=$PROXY https_proxy=$PROXY http_proxy=$PROXY"
  fi
  echo "ExecStart="
  echo "ExecStart=/opt/circuitpath/circuitpath-server -hostname $NAME${UPDATE_URL:+ -update-url $UPDATE_URL}"
} > /etc/systemd/system/circuitpath.service.d/install.conf
systemctl daemon-reload

if [ "$ARDUINO" -eq 1 ]; then
  step "Board cores and libraries (15-30 minutes: ESP32 is big)"
  runuser -u circuitpath -- env HOME=/var/lib/circuitpath ${PROXY:+HTTPS_PROXY=$PROXY HTTP_PROXY=$PROXY} \
    /opt/circuitpath/circuitpath-server -data /var/lib/circuitpath -setup-arduino \
    || die "the board cores and libraries didn't install (see above). Run the installer again to retry."
fi

step "Automatic updates (CircuitPath and Raspberry Pi OS)"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
// Written by the CircuitPath installer: check for and install updates every day.
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/52circuitpath-unattended-upgrades <<'EOF'
// Written by the CircuitPath installer: install every Raspberry Pi OS and
// Debian update automatically (not just security fixes), and restart at
// night when an update needs it. CircuitPath checks for its own updates every
// time it starts and every night at 03:00.
Unattended-Upgrade::Origins-Pattern {
        "origin=Debian,codename=${distro_codename},label=Debian";
        "origin=Debian,codename=${distro_codename}-updates";
        "origin=Debian,codename=${distro_codename},label=Debian-Security";
        "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
        "origin=Raspberry Pi Foundation,codename=${distro_codename},label=Raspberry Pi Foundation";
};
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "03:30";
EOF
systemctl enable --now apt-daily.timer apt-daily-upgrade.timer >/dev/null 2>&1 || true
note "Raspberry Pi OS: every update, daily; restarts at 03:30 when one needs it"
note "CircuitPath: at every start and every night at 03:00"

if [ "$FIREWALL" -eq 1 ]; then
  step "Firewall (only SSH, web and circuitpath.local get in)"
  cat > /etc/nftables.conf <<'EOF'
#!/usr/sbin/nft -f
# Written by the CircuitPath installer.
flush ruleset
table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;
    iif lo accept
    ct state established,related accept
    ct state invalid drop
    meta l4proto { icmp, ipv6-icmp } accept
    udp dport { 68, 546 } accept comment "DHCP"
    udp dport 5353 accept comment "mDNS: circuitpath.local"
    tcp dport { 22, 80, 443 } accept comment "SSH (emergencies) and CircuitPath"
  }
  chain forward {
    type filter hook forward priority 0; policy drop;
  }
  chain output {
    type filter hook output priority 0; policy accept;
  }
}
EOF
  nft -f /etc/nftables.conf || die "the firewall rules didn't load"
  systemctl enable nftables >/dev/null 2>&1 || true
fi

step "Starting CircuitPath"
systemctl enable circuitpath >/dev/null 2>&1
systemctl restart circuitpath
for _ in $(seq 1 90); do
  if curl -fsk -o /dev/null https://127.0.0.1/api/info; then break; fi
  sleep 2
done
curl -fsk -o /dev/null https://127.0.0.1/api/info || die "CircuitPath didn't start. See: journalctl -u circuitpath"

ADDRS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.' | sed 's#^#https://#' | tr '\n' ' ')"
printf '\n\033[1;32mCircuitPath %s is running.\033[0m\n\n' "$(curl -fsk https://127.0.0.1/api/info | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')"
echo "Open it in Edge or Chrome:  https://$NAME.local   ${ADDRS:+(or $ADDRS)}"
echo "The browser will warn about the certificate until IT trusts the Pi's"
echo "certificate (/var/lib/circuitpath/tls/ca.crt). For a test, choose Advanced > Continue."
echo
echo "Logs:     journalctl -u circuitpath -f"
echo "Restart:  sudo systemctl restart circuitpath   (it checks for updates as it starts)"

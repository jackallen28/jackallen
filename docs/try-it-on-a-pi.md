# Try CircuitPath on a Raspberry Pi now

Until the ready-made SD card image is built (build step 6), you put CircuitPath on a normal
Raspberry Pi OS card with one command. The SD card image will run the same installer, so what
you test now is what schools will get.

You need: a Raspberry Pi 5, a 32 GB+ microSD card, a laptop on the same network, and internet
for the Pi (once, for about 30 minutes).

## Once: publish the first release

The Pi installs CircuitPath from the repository's GitHub Releases.

1. **Add the update key to GitHub** (lets releases be signed, so Pis only install real updates):
   repository on github.com > **Settings** > **Secrets and variables** > **Actions** >
   **New repository secret**. Name: `CIRCUITPATH_UPDATE_KEY`. Value: the private key (one line).
   See [updates.md](updates.md) for where the key comes from.
2. **Publish version 0.1.0** (already done for 0.1.0): the `VERSION` file on the
   `BNTS_CircuitPath` branch says which version to publish. Changing it publishes that version.
3. Watch **Actions** > **Release**. After about 5 minutes the release has
   `circuitpath-server-linux-arm64`, `install.sh` and the other files.

## Set up the Pi (about 40 minutes, mostly waiting)

1. **Flash the card** with [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Device: **Raspberry Pi 5**. OS: **Raspberry Pi OS (other) > Raspberry Pi OS Lite (64-bit)**.
   - **Edit settings** (customisation): hostname `circuitpath`, a username and password,
     Wi-Fi if you're not using a network cable, time zone `Australia/Melbourne`, and on
     **Services**: **Enable SSH** (password authentication).
2. Put the card in the Pi, plug in the network cable and power, and wait 2 minutes.
3. On your laptop, open **Terminal** (Windows: Windows Terminal or PowerShell) and connect:
   ```
   ssh yourusername@circuitpath.local
   ```
   (If `circuitpath.local` isn't found, use the Pi's IP address from your router or IT.)
4. Install CircuitPath:
   ```
   curl -fsSL https://github.com/jackallen28/jackallen/releases/latest/download/install.sh | sudo bash
   ```
   Behind a school proxy, add it at the end: `... | sudo bash -s -- --proxy http://proxy.school:8080`.
   It takes 20–40 minutes; most of it is the ESP32 board package. It ends with
   **CircuitPath 0.1.0 is running** and a table of boards that all compiled.
5. Open **https://circuitpath.local** in Edge or Chrome. The browser warns about the
   certificate (IT trusts it later, see [the brief](../CLAUDE.md) §3): choose **Advanced** >
   **Continue**. Make a profile and try the picker and Free Play.

## Check that updates work

1. Publish a newer version: change `VERSION` to `0.1.1` (on github.com: open the file > edit >
   **Commit changes**), and wait about 5 minutes for **Actions > Release** to finish.
2. Restart the Pi: `sudo reboot` (or unplug it and plug it back in).
3. While it starts you may see **CircuitPath is getting ready**. Then **About** shows 0.1.1, and
   your profile and code are still there. (`journalctl -u circuitpath` shows "downloading an update".)

Raspberry Pi OS updates install by themselves every day; if one needs a restart, the Pi
restarts at 03:30. CircuitPath also checks for an update every night at 03:00.

## Useful commands on the Pi

| | |
|---|---|
| What's it doing? | `journalctl -u circuitpath -f` |
| Restart (and check for updates) | `sudo systemctl restart circuitpath` |
| Is every board ready? | `sudo -u circuitpath /opt/circuitpath/circuitpath-server -data /var/lib/circuitpath -check-arduino` |
| Run the installer again (repairs anything) | the `curl ... \| sudo bash` line above |
| The certificate IT needs to trust | `/var/lib/circuitpath/tls/ca.crt` |

## How this was tested without a Pi

The **Pi simulation** (GitHub Actions > Pi simulation, `tests/pi/simulate.sh`) runs on an arm64
machine (the Pi 5's kind of processor) with the real Raspberry Pi OS Lite (64-bit) files from the
official image, booting systemd in a container. It runs `install.sh` exactly as above, then
checks: the service runs and starts at boot, HTTPS answers, a student can sign up, every board
compiles the kit check, OS updates and the firewall are on, publishing a new release makes it
update itself (with a database backup and the student's work kept), and it comes back after a
restart. What it can't check is the Pi's own hardware (its kernel, firmware, Wi-Fi and USB), so
do the steps above on a real Pi before a class uses it.

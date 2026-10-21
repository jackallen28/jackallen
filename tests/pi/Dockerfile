# Raspberry Pi OS Lite (64-bit) as a container, booting systemd, for the Pi
# simulation (tests/pi/simulate.sh). The base image is the real Raspberry Pi
# OS root filesystem, imported from the official .img.xz.
FROM circuitpath/rpios-rootfs
ENV container=docker
# Things that only make sense on real hardware or at a real first boot, and
# network managers (Docker sets up the container's network itself).
RUN : > /etc/fstab \
 && for u in cloud-init.service cloud-init-local.service cloud-init-main.service cloud-init-network.service \
             cloud-config.service cloud-final.service userconfig.service rpi-resize.service resize2fs_once.service \
             sshswitch.service regenerate_ssh_host_keys.service systemd-remount-fs.service \
             getty@tty1.service serial-getty@ttyAMA0.service serial-getty@ttyS0.service \
             rpi-eeprom-update.service NetworkManager.service NetworkManager-wait-online.service \
             NetworkManager-dispatcher.service systemd-networkd-wait-online.service \
             dhcpcd.service wpa_supplicant.service ModemManager.service \
             bluetooth.service hciuart.service; do \
      systemctl mask "$u" >/dev/null 2>&1 || true; done
STOPSIGNAL SIGRTMIN+3
CMD ["/lib/systemd/systemd"]

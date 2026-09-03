#!/bin/sh
# Mounted disks (Render, Fly, plain Docker) arrive owned by root, which a
# non-root process cannot write to. Start as root, hand the data directory to
# the unprivileged user, then drop privileges before running the app.
#
# If dropping privileges is not possible we log it and run anyway: a prototype
# that boots and warns is more useful than one that exits.
set -e

DATA_DIR="${DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR" 2>/dev/null || true
  chown -R app:app "$DATA_DIR" 2>/dev/null || echo "[entrypoint] could not chown $DATA_DIR"

  if command -v setpriv >/dev/null 2>&1 && setpriv --reuid=app --regid=app --init-groups true 2>/dev/null; then
    exec setpriv --reuid=app --regid=app --init-groups "$@"
  fi
  if id app >/dev/null 2>&1; then
    exec su -s /bin/sh -c "exec $*" app
  fi
  echo "[entrypoint] no unprivileged 'app' user available — running as root"
fi

exec "$@"

"""Test helper: run a program through the GPIO shim on simulated pins, with timed button presses.

    out = run_shim(code, events=["1.0 press 23", "1.2 release 23"], seconds=4)
    out.stdout, out.stderr, out.rc, out.devices, out.values, out.stopped
"""
from __future__ import annotations

import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIM = ROOT / "pipath" / "gpio_shim.py"
SIM_ENV = {"GPIOZERO_PIN_FACTORY": "mock", "GPIOZERO_MOCK_PIN_CLASS": "mockpwmpin", "PIPATH_CAMERA": "sim"}

try:
    import gpiozero  # noqa: F401
    HAVE_GPIOZERO = True
except ImportError:
    HAVE_GPIOZERO = False


@dataclass
class ShimResult:
    stdout: str
    stderr: str
    rc: int
    stopped: bool                      # True if we sent Stop (SIGTERM), like the student pressing Stop
    messages: list = field(default_factory=list)
    folder: Path | None = None

    @property
    def devices(self) -> list:
        """The most devices the program had at any one time."""
        found = [m["devices"] for m in self.messages if m.get("t") == "devices"]
        return max(found, key=len, default=[])

    def ever_on(self, pin: int) -> bool:
        return any(m.get("t") == "pins" and m["pins"].get(str(pin), 0) > 0 for m in self.messages)


def run_shim(code: str, events: list | None = None, seconds: float | None = None, stdin: str = "",
             env: dict | None = None, timeout: float = 40, file_name: str = "student.py",
             keep_folder: bool = False) -> ShimResult:
    d = tempfile.mkdtemp(prefix="pipath_test_")
    path = Path(d) / file_name
    path.write_text(code, encoding="utf-8")
    sr, sw = os.pipe()
    cr, cw = os.pipe()
    e = dict(os.environ, PYTHONUNBUFFERED="1", PIPATH_STATE_FD=str(sw), PIPATH_CMD_FD=str(cr), **SIM_ENV)
    e.update(env or {})
    p = subprocess.Popen([sys.executable, "-u", str(SHIM), file_name], cwd=d, env=e, pass_fds=(sw, cr),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(sw)
    os.close(cr)
    if stdin:
        p.stdin.write(stdin.encode())
        p.stdin.flush()
    todo = sorted((float(t), f"{a} {pin}") for t, a, pin in (str(ev).split() for ev in (events or [])))
    start = time.monotonic()
    buf, out, err = b"", b"", b""
    stopped = False
    streams = {sr: "state", p.stdout.fileno(): "out", p.stderr.fileno(): "err"}
    while streams:
        now = time.monotonic() - start
        while todo and todo[0][0] <= now:
            try:
                os.write(cw, (todo.pop(0)[1] + "\n").encode())
            except OSError:
                pass
        if seconds is not None and now >= seconds and not stopped and p.poll() is None:
            p.send_signal(signal.SIGTERM)
            stopped = True
        if now > timeout:
            p.kill()
            break
        ready, _, _ = select.select(list(streams), [], [], 0.02)
        for fd in ready:
            chunk = os.read(fd, 65536)
            if not chunk:
                del streams[fd]
                continue
            kind = streams[fd]
            if kind == "state":
                buf += chunk
            elif kind == "out":
                out += chunk
            else:
                err += chunk
    rc = p.wait()
    for f in (p.stdin, p.stdout, p.stderr):
        f.close()
    os.close(sr)
    os.close(cw)
    msgs = [json.loads(line) for line in buf.decode().splitlines() if line.strip()]
    if not keep_folder:
        shutil.rmtree(d, ignore_errors=True)
    return ShimResult(out.decode(), err.decode(), rc, stopped, msgs, Path(d) if keep_folder else None)

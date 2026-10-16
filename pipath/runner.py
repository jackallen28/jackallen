"""Runs a student's program in a separate Python process.

- Output streams back live (including input() prompts that have no newline).
- The student can type answers, which go to the program's stdin.
- Runaway programs are stopped: too much output, or a CPU-busy loop that
  produces nothing (detected from /proc on Linux / Raspberry Pi OS).
- GPIO programs can run through pipath/gpio_shim.py, which reports pin states
  (("gpio", message) events) and takes commands like "press 23" (send_command).
- Warm start: warm_up() starts a spare shim process in the background with gpiozero (etc.)
  already imported. The next start() hands it the program, so Run feels instant on a Pi 3B
  instead of waiting a second or two for Python and gpiozero to load.
"""
from __future__ import annotations

import codecs
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


class Runner:
    def __init__(self, busy_seconds: float = 8, max_lines: int = 3000):
        self.busy_seconds = busy_seconds
        self.max_lines = max_lines
        self.proc: subprocess.Popen | None = None
        self.events: queue.Queue = queue.Queue()
        self.stdout_text: list[str] = []
        self.stderr_text: list[str] = []
        self._lines = 0
        self._stop_reason: str | None = None
        self._last_output = 0.0
        self._busy_since: float | None = None
        self._last_cpu: tuple[float, float] | None = None
        self._cmd_fd: int | None = None
        self._warm: tuple | None = None       # (proc, events, cmd_fd, shim, preload) waiting for a program

    # ---------------------------------------------------------------- control
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, script: Path, cwd: Path, extra_env: dict | None = None, shim: Path | None = None) -> None:
        """Run script in cwd. With shim, run it through the GPIO shim and listen for pin states."""
        self.stop()
        self._close_cmd()
        self.stdout_text, self.stderr_text = [], []
        self._lines = 0
        self._stop_reason = None
        self._last_output = time.monotonic()
        self._busy_since = None
        self._last_cpu = None
        if shim is not None and self._take_warm(shim):
            order = {"run": str(Path(cwd) / script.name), "cwd": str(cwd), "env": extra_env or {}}
            self.send_command(json.dumps(order))
            return
        args = [sys.executable, "-u", script.name] if shim is None else [sys.executable, "-u", str(shim), script.name]
        self.proc, self.events, self._cmd_fd = self._spawn(args, cwd, self._env(extra_env), shim is not None)

    def warm_up(self, shim: Path, preload: list | tuple = ()) -> None:
        """Start a spare shim process now (with `preload` modules imported) for the next start()."""
        preload = tuple(preload)
        w = self._warm
        if w is not None and w[0].poll() is None and w[3] == shim and w[4] == preload:
            return
        self._drop_warm()
        env = self._env({"PIPATH_PRELOAD": ",".join(preload)})
        for key in ("GPIOZERO_PIN_FACTORY", "GPIOZERO_MOCK_PIN_CLASS"):
            env.pop(key, None)        # each run says which pins to use (Simulator or real)
        try:
            proc, events, cmd_fd = self._spawn([sys.executable, "-u", str(shim), "--wait"], shim.parent,
                                               env, True)
        except OSError:
            return
        self._warm = (proc, events, cmd_fd, shim, preload)

    @property
    def warm(self) -> bool:
        """True when a spare process is waiting, so the next shim start() is instant."""
        return self._warm is not None and self._warm[0].poll() is None

    def close(self) -> None:
        """Stop the program and the spare process (when leaving the workspace)."""
        self.stop()
        self._close_cmd()
        self._drop_warm()

    def _take_warm(self, shim: Path) -> bool:
        warm, self._warm = self._warm, None
        if warm is None:
            return False
        proc, events, cmd_fd, warm_shim, _preload = warm
        ok = proc.poll() is None and warm_shim == shim
        while ok:              # anything it said while loading isn't part of the student's run
            try:
                ev = events.get_nowait()
            except queue.Empty:
                break
            ok = ev[0] not in ("exit", "closed")
        if not ok:
            self._warm = warm
            self._drop_warm()
            return False
        self.proc, self.events, self._cmd_fd = proc, events, cmd_fd
        return True

    def _drop_warm(self) -> None:
        warm, self._warm = self._warm, None
        if warm is None:
            return
        proc, _events, cmd_fd, _shim, _preload = warm
        try:
            os.close(cmd_fd)            # a waiting shim exits when its command pipe closes
        except OSError:
            pass
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    @staticmethod
    def _env(extra: dict | None) -> dict:
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        env.update(extra or {})
        return env

    def _spawn(self, args: list, cwd, env: dict, shim: bool):
        """Start a process. Each one gets its own event queue, so late events never leak into a new run."""
        events: queue.Queue = queue.Queue()
        pass_fds, state_r, cmd_w = (), None, None
        if shim:
            state_r, state_w = os.pipe()
            cmd_r, cmd_w = os.pipe()
            env = dict(env, PIPATH_STATE_FD=str(state_w), PIPATH_CMD_FD=str(cmd_r))
            pass_fds = (state_w, cmd_r)
        try:
            proc = subprocess.Popen(
                args, cwd=str(cwd), env=env, pass_fds=pass_fds,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:
            for fd in (state_r, cmd_w):
                if fd is not None:
                    os.close(fd)
            raise
        finally:
            for fd in pass_fds:      # the child has its own copies now
                os.close(fd)
        if shim:
            threading.Thread(target=self._pump_state, args=(state_r, events), daemon=True).start()
        for stream, kind in ((proc.stdout, "out"), (proc.stderr, "err")):
            threading.Thread(target=self._pump, args=(stream, kind, events), daemon=True).start()
        threading.Thread(target=self._wait, args=(proc, events), daemon=True).start()
        return proc, events, cmd_w

    def send_command(self, text: str) -> None:
        """Send a command to the GPIO shim, e.g. "press 23". Ignored if there's no shim."""
        if self._cmd_fd is not None and self.running:
            try:
                os.write(self._cmd_fd, (text + "\n").encode("utf-8"))
            except OSError:
                pass

    def _close_cmd(self) -> None:
        if self._cmd_fd is not None:
            try:
                os.close(self._cmd_fd)
            except OSError:
                pass
            self._cmd_fd = None

    def send_input(self, text: str) -> None:
        if self.running and self.proc.stdin:
            try:
                self.proc.stdin.write((text + "\n").encode("utf-8"))
                self.proc.stdin.flush()
                self._last_output = time.monotonic()
            except (BrokenPipeError, OSError, ValueError):   # it has just finished
                pass

    def stop(self, reason: str = "user") -> None:
        if self.running:
            self._stop_reason = reason
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except OSError:
                pass

    # ---------------------------------------------------------------- threads
    def _pump(self, stream, kind: str, q: queue.Queue) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        fd = stream.fileno()
        while True:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            text = decoder.decode(chunk)
            if text:
                q.put((kind, text))
        tail = decoder.decode(b"", final=True)
        if tail:
            q.put((kind, tail))
        stream.close()
        q.put(("closed", kind))

    def _pump_state(self, fd: int, q: queue.Queue) -> None:
        buf = b""
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                try:
                    q.put(("gpio", json.loads(line)))
                except ValueError:
                    pass
        os.close(fd)

    def _wait(self, proc: subprocess.Popen, q: queue.Queue) -> None:
        rc = proc.wait()
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass
        q.put(("exit", rc))

    # ---------------------------------------------------------------- polling (call from the GUI thread)
    def poll(self) -> list[tuple]:
        """Drain pending events. Also watches for runaway programs."""
        out = []
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            kind = ev[0]
            if kind == "out":
                self.stdout_text.append(ev[1])
                self._lines += ev[1].count("\n")
                self._last_output = time.monotonic()
            elif kind == "err":
                self.stderr_text.append(ev[1])
            elif kind == "exit":
                self._close_cmd()
            out.append(ev)
        if self.running:
            if self._lines > self.max_lines:
                self.stop("runaway_output")
            elif self._is_busy_too_long():
                self.stop("runaway_busy")
        return out

    def _is_busy_too_long(self) -> bool:
        now = time.monotonic()
        if self._last_cpu is not None and now - self._last_cpu[0] < 0.5:
            return False                # look twice a second, not on every poll
        try:
            with open(f"/proc/{self.proc.pid}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            cpu = (int(fields[11]) + int(fields[12])) / CLK_TCK
        except (OSError, IndexError, ValueError):
            return False
        if self._last_cpu is None:
            self._last_cpu = (now, cpu)
            return False
        t0, c0 = self._last_cpu
        self._last_cpu = (now, cpu)
        busy = (cpu - c0) / (now - t0) > 0.6
        quiet = now - self._last_output > 1.0
        if busy and quiet:
            self._busy_since = self._busy_since or t0
            return now - self._busy_since > self.busy_seconds
        self._busy_since = None
        return False

    # ---------------------------------------------------------------- results
    @property
    def stop_reason(self) -> str | None:
        return self._stop_reason

    @property
    def stdout(self) -> str:
        return "".join(self.stdout_text)

    @property
    def stderr(self) -> str:
        return "".join(self.stderr_text)

"""Runs a student's program in a separate Python process.

- Output streams back live (including input() prompts that have no newline).
- The student can type answers, which go to the program's stdin.
- Runaway programs are stopped: too much output, or a CPU-busy loop that
  produces nothing (detected from /proc on Linux / Raspberry Pi OS).
"""
from __future__ import annotations

import codecs
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

    # ---------------------------------------------------------------- control
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, script: Path, cwd: Path, extra_env: dict | None = None) -> None:
        self.stop()
        self.events = queue.Queue()
        self.stdout_text, self.stderr_text = [], []
        self._lines = 0
        self._stop_reason = None
        self._last_output = time.monotonic()
        self._busy_since = None
        self._last_cpu = None
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                   PYTHONDONTWRITEBYTECODE="1")
        if extra_env:
            env.update(extra_env)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", script.name],
            cwd=str(cwd), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        for stream, kind in ((self.proc.stdout, "out"), (self.proc.stderr, "err")):
            threading.Thread(target=self._pump, args=(stream, kind), daemon=True).start()
        threading.Thread(target=self._wait, args=(self.proc,), daemon=True).start()

    def send_input(self, text: str) -> None:
        if self.running and self.proc.stdin:
            try:
                self.proc.stdin.write((text + "\n").encode("utf-8"))
                self.proc.stdin.flush()
                self._last_output = time.monotonic()
            except (BrokenPipeError, OSError):
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
    def _pump(self, stream, kind: str) -> None:
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
                self.events.put((kind, text))
        tail = decoder.decode(b"", final=True)
        if tail:
            self.events.put((kind, tail))
        self.events.put(("closed", kind))

    def _wait(self, proc: subprocess.Popen) -> None:
        rc = proc.wait()
        self.events.put(("exit", rc))

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
            out.append(ev)
        if self.running:
            if self._lines > self.max_lines:
                self.stop("runaway_output")
            elif self._is_busy_too_long():
                self.stop("runaway_busy")
        return out

    def _is_busy_too_long(self) -> bool:
        try:
            with open(f"/proc/{self.proc.pid}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            cpu = (int(fields[11]) + int(fields[12])) / CLK_TCK
        except (OSError, IndexError, ValueError):
            return False
        now = time.monotonic()
        if self._last_cpu is None:
            self._last_cpu = (now, cpu)
            return False
        t0, c0 = self._last_cpu
        if now - t0 < 0.5:
            return False
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

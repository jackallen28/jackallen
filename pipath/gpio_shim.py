"""Runs a student's program so PiPath can show (and poke) its GPIO pins.

    python3 -u pipath/gpio_shim.py <student_file>

This file runs INSIDE the student's process, never inside the app.

- Simulator mode (GPIOZERO_PIN_FACTORY=mock): pins are pretend. The app can press
  buttons and trigger the motion sensor by sending commands.
- Real Pi mode: pins are real. The shim only reports what the code is doing, so the
  on-screen board mirrors the program next to the real breadboard.

Messages to the app are JSON lines on the fd named in PIPATH_STATE_FD:
    {"t": "devices", "devices": [{"kind": "LED", "pins": [17]}, ...]}
    {"t": "pins", "pins": {"17": 1.0, "23": 0}}     (outputs: brightness 0-1, inputs: 1 = active)
    {"t": "photo", "path": "/full/path/photo.png"}      (sent by pipath_camera)
Commands from the app are text lines on the fd named in PIPATH_CMD_FD:
    press 23 / release 23   (activate / deactivate an input, Simulator only)
    show circle             (what the simulated camera can see)

Tracebacks are trimmed so they start in the student's file, and a Stop (SIGTERM)
exits cleanly, so gpiozero switches real LEDs and buzzers off.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import json
import os
import runpy
import signal
import sys
import threading
import time
import traceback
import weakref
from pathlib import Path

HERE = Path(__file__).resolve().parent
TICK = 0.05

_send_lock = threading.Lock()
_state_fd = int(os.environ["PIPATH_STATE_FD"]) if os.environ.get("PIPATH_STATE_FD") else None
_student = ""                # full path of the student's file
_callback_crashed: list = []  # set when an event handler (e.g. when_pressed) crashes
_devices: list = []          # weakrefs to gpiozero devices, in the order they were made
_groups: list = []           # weakrefs to RGBLEDs (three pins shown as one light)
camera_view = {"object": "circle"}   # read by pipath_camera's simulated camera
_gz = None                    # the gpiozero module, once the student imports it


def send(msg: dict) -> None:
    """Send one message to the app (ignored when not running inside PiPath)."""
    if _state_fd is None:
        return
    data = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
    with _send_lock:
        try:
            os.write(_state_fd, data)
        except OSError:
            pass


# ---------------------------------------------------------------- watching gpiozero

def _bcm(pin) -> int | None:
    name = getattr(getattr(pin, "info", None), "name", "") or ""
    return int(name[4:]) if name.startswith("GPIO") and name[4:].isdigit() else None


def _patch_gpiozero(gz) -> None:
    """Remember every device the student makes, so the board knows what to draw."""
    global _gz
    _gz = gz
    orig_init = gz.GPIODevice.__init__

    def gpio_init(self, *a, **kw):
        orig_init(self, *a, **kw)
        _devices.append(weakref.ref(self))

    gz.GPIODevice.__init__ = gpio_init

    orig_rgb = gz.RGBLED.__init__

    def rgb_init(self, *a, **kw):
        orig_rgb(self, *a, **kw)
        _groups.append(weakref.ref(self))

    gz.RGBLED.__init__ = rgb_init


class _GpiozeroHook(importlib.abc.MetaPathFinder):
    """Patch gpiozero the moment the student imports it (and never import it otherwise)."""

    def find_spec(self, name, path=None, target=None):
        if name != "gpiozero":
            return None
        sys.meta_path.remove(self)
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None:
            return spec
        loader = spec.loader
        orig_exec = loader.exec_module

        def exec_module(module):
            orig_exec(module)
            _patch_gpiozero(module)

        loader.exec_module = exec_module
        return spec


def _snapshot():
    devs, pins, in_group = [], {}, set()
    for ref in list(_groups):
        g = ref()
        if g is None or g.closed:
            continue
        ps = [_bcm(led.pin) for led in g._leds]
        if None not in ps:
            devs.append({"kind": "RGBLED", "pins": ps})
            in_group.update(ps)
    for ref in list(_devices):
        d = ref()
        if d is None or d.closed:
            continue
        p = _bcm(d.pin)
        if p is None:
            continue
        try:
            # outputs: how bright / on (honours active_high); inputs: pressed / motion seen
            state = d.value if isinstance(d, _gz.OutputDevice) else d.is_active
        except Exception:
            continue
        pins[str(p)] = round(float(state), 2)
        if p not in in_group:
            devs.append({"kind": type(d).__name__, "pins": [p]})
    return devs, pins


def _reporter() -> None:
    last_devs, last_pins = None, None
    while True:
        time.sleep(TICK)
        try:
            devs, pins = _snapshot()
        except Exception:
            continue
        if devs != last_devs:
            send({"t": "devices", "devices": devs})
            last_devs = devs
        if pins != last_pins:
            send({"t": "pins", "pins": pins})
            last_pins = pins


def _find_device(pin_no: int):
    for ref in list(_devices):
        d = ref()
        if d is not None and not d.closed and _bcm(d.pin) == pin_no:
            return d
    return None


def _listener(fd: int) -> None:
    buf = b""
    while True:
        try:
            chunk = os.read(fd, 1024)
        except OSError:
            return
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            _command(line.decode("utf-8", "replace").split())


def _command(words: list[str]) -> None:
    if len(words) == 2 and words[0] == "show":
        camera_view["object"] = words[1]
        return
    if len(words) != 2 or words[0] not in ("press", "release") or not words[1].isdigit():
        return
    if os.environ.get("GPIOZERO_PIN_FACTORY") != "mock":
        return   # never drive real pins from the screen
    d = _find_device(int(words[1]))
    if d is None:
        return
    pin = d.pin
    active_low = getattr(pin, "pull", "") == "up"     # buttons: pressed pulls the pin to GND
    on = words[0] == "press"
    # The student's when_pressed handler runs right here; if it crashes, the error
    # reaches _thread_crashed below, just like a crash in the main program.
    if on == active_low:
        pin.drive_low()
    else:
        pin.drive_high()


# ---------------------------------------------------------------- running the student's file

def _stop(_signum, _frame):
    raise SystemExit(0)


def _thread_crashed(args) -> None:
    """An event handler crashed in a background thread: report it and end the program."""
    if args.exc_type is SystemExit:
        return
    _print_student_traceback(args.exc_value, _student)
    _callback_crashed.append(True)
    os.kill(os.getpid(), signal.SIGTERM)   # a real signal also wakes pause() and sleep()


def _print_student_traceback(exc: BaseException, student: str) -> None:
    """Print the traceback starting at the student's file, without this shim or runpy."""
    tb = exc.__traceback__
    while tb is not None and os.path.abspath(tb.tb_frame.f_code.co_filename) != student:
        tb = tb.tb_next
    te = traceback.TracebackException(type(exc), exc, tb)
    sys.stderr.write("".join(te.format()))
    sys.stderr.flush()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gpio_shim.py <student_file>", file=sys.stderr)
        return 2
    global _student
    student = _student = os.path.abspath(sys.argv[1])
    sys.argv = [student] + sys.argv[2:]
    sys.path[0] = os.path.dirname(student)
    sys.path.append(str(HERE / "student_lib"))
    sys.meta_path.insert(0, _GpiozeroHook())
    signal.signal(signal.SIGTERM, _stop)
    threading.excepthook = _thread_crashed
    sys.modules["pipath_shim"] = sys.modules[__name__]

    if _state_fd is not None:
        threading.Thread(target=_reporter, daemon=True).start()
    if os.environ.get("PIPATH_CMD_FD"):
        threading.Thread(target=_listener, args=(int(os.environ["PIPATH_CMD_FD"]),), daemon=True).start()
    send({"t": "hello", "mode": "sim" if os.environ.get("GPIOZERO_PIN_FACTORY") == "mock" else "real"})

    try:
        runpy.run_path(student, run_name="__main__")
    except SystemExit:
        if _callback_crashed:
            return 1
        raise
    except KeyboardInterrupt:
        return 130
    except BaseException as e:   # noqa: BLE001 - every crash is reported, then the app explains it
        _print_student_traceback(e, student)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

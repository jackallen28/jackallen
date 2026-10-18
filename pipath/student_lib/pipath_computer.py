"""pipath_computer: let your program talk to the computer it runs on.

    from pipath_computer import cpu_temp, cpu_load, ram_used, open_file, open_website

    cpu_temp()            how hot the Pi's processor is, in °C (like 48.3)
    cpu_load()            how busy the processor is, as a percentage (0 to 100)
    ram_used()            how much of the memory (RAM) is in use, as a percentage
    open_file("song.mp3") open a file with the Pi's normal app (a video, song or picture)
    open_website(url)     open a web page in the browser (needs the internet)
    take_screenshot()     save a picture of the whole screen, and return its file name
    change_volume(5)      turn the sound up 5% (or down, with -5)
    show_message("Hi!")   pop up a message box on the screen

How it works (no magic): the Pi keeps these numbers in special files.
    /sys/class/thermal/thermal_zone0/temp   the temperature in thousandths of a degree
    /proc/stat                              how long the processor has spent busy and idle
    /proc/meminfo                           how much memory there is, and how much is free

In the Simulator, "Watch the goal" can pretend the Pi is hot or busy, so you can see the
lights change. Everywhere else the numbers are real.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

__all__ = ["cpu_temp", "cpu_load", "ram_used", "open_file", "open_website", "take_screenshot", "change_volume",
           "show_message"]

TEMP_FILE = "/sys/class/thermal/thermal_zone0/temp"
_last_cpu: tuple[float, float, float] | None = None     # (time, busy, total) at the last cpu_load()
_last_load = 0.0
_told_pretend = False


def _sim(name: str) -> float | None:
    """A pretend value set by the Simulator (Watch the goal), or None."""
    value = os.environ.get(f"PIPATH_SIM_{name.upper()}")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


# ---------------------------------------------------------------- reading the Pi's numbers

def cpu_temp() -> float:
    """The processor's temperature in °C, to one decimal place."""
    sim = _sim("temp")
    if sim is not None:
        return round(sim, 1)
    try:
        with open(TEMP_FILE) as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (OSError, ValueError):
        global _told_pretend
        if not _told_pretend:
            _told_pretend = True
            print("(This computer doesn't share its temperature, so cpu_temp() makes up a pretend one.)")
        return round(40 + cpu_load() * 0.3, 1)


def _cpu_times() -> tuple[float, float] | None:
    """(busy, total) processor time since the Pi started, from /proc/stat."""
    try:
        with open("/proc/stat") as f:
            fields = [float(x) for x in f.readline().split()[1:9]]
    except (OSError, ValueError):
        return None
    idle = fields[3] + fields[4]           # idle + waiting for the SD card
    total = sum(fields)
    return total - idle, total


def cpu_load() -> float:
    """How busy the processor has been since you last asked, as a percentage (0 to 100)."""
    global _last_cpu, _last_load
    sim = _sim("load")
    if sim is not None:
        return round(max(0.0, min(100.0, sim)), 1)
    now = time.monotonic()
    times = _cpu_times()
    if times is None:                      # not Linux: use the load average instead
        try:
            return round(min(100.0, os.getloadavg()[0] / (os.cpu_count() or 1) * 100), 1)
        except (OSError, AttributeError):
            return 0.0
    if _last_cpu is None or now - _last_cpu[0] > 30:
        _last_cpu = (now, *times)          # first time: measure over a fifth of a second
        time.sleep(0.2)
        now, times = time.monotonic(), _cpu_times() or times
    elif now - _last_cpu[0] < 0.1:
        return _last_load                  # asked twice in a row: same answer
    busy = times[0] - _last_cpu[1]
    total = times[1] - _last_cpu[2]
    _last_cpu = (now, *times)
    _last_load = round(100 * busy / total, 1) if total > 0 else 0.0
    return _last_load


def ram_used() -> float:
    """How much of the memory (RAM) is in use, as a percentage."""
    sim = _sim("ram")
    if sim is not None:
        return round(max(0.0, min(100.0, sim)), 1)
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = float(rest.split()[0])
        return round(100 * (1 - info["MemAvailable"] / info["MemTotal"]), 1)
    except (OSError, ValueError, KeyError, ZeroDivisionError):
        return 50.0


# ---------------------------------------------------------------- opening things on the screen

def _just_pretend() -> bool:
    """Watch the goal (and tests) only show what would open. So does a computer with no screen."""
    return bool(os.environ.get("PIPATH_DEMO")) or not (os.environ.get("DISPLAY") or
                                                       os.environ.get("WAYLAND_DISPLAY"))


def _launch(target: str) -> None:
    """Open a file or web address with the desktop's normal app, without waiting for it."""
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", target], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        webbrowser.open(target)


def open_file(path) -> None:
    """Open a video, song or picture with the Pi's normal app (like double-clicking it)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"There's no file called '{path}' in the {Path.cwd().name} folder")
    print(f"▶ Opening {p.name}", flush=True)
    if not _just_pretend():
        _launch(str(p.resolve()))


def open_website(url: str) -> None:
    """Open a web page in the browser. The Pi needs to be on the internet for this one."""
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"A web address starts with https:// (you gave '{url}')")
    print(f"▶ Opening {url}", flush=True)
    if not _just_pretend():
        _launch(url)


# ---------------------------------------------------------------- the desktop: screenshots, sound, messages

def _run_first(commands: list[list[str]]) -> bool:
    """Run the first command that's installed. True if it worked."""
    for cmd in commands:
        if shutil.which(cmd[0]):
            try:
                return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      timeout=10).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                continue
    return False


def take_screenshot(name: str = "screenshot.png") -> str:
    """Save a picture of the whole screen (a .png) and return the file name."""
    p = Path(str(name))
    if p.suffix.lower() != ".png":
        p = p.with_suffix(".png")
    ok = False
    if not _just_pretend():
        ok = _run_first([["grim", str(p)],                              # Raspberry Pi OS (Wayland)
                         ["scrot", "-o", str(p)], ["import", "-window", "root", str(p)],
                         ["gnome-screenshot", "-f", str(p)]])
    if not ok:                      # Watch the goal, or no screenshot tool: a small grey picture instead
        from pipath_camera import write_png
        write_png(p, 64, 36, bytes([192, 192, 192]) * (64 * 36))
    print(f"▶ Screenshot saved: {p.name}", flush=True)
    return str(p)


def change_volume(step: int = 5) -> None:
    """Turn the sound up (step > 0) or down (step < 0) by step percent."""
    step = int(step)
    sign = "+" if step >= 0 else "-"
    print(f"▶ Volume {'up' if step >= 0 else 'down'} {abs(step)}%", flush=True)
    if not _just_pretend():
        _run_first([["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{abs(step)}%{sign}"],
                    ["amixer", "-q", "sset", "Master", f"{abs(step)}%{sign}"]])


def show_message(text: str, title: str = "PiPath") -> None:
    """Pop up a message box with an OK button (the program waits until it's closed)."""
    print(f"▶ Message: {text}", flush=True)
    if _just_pretend():
        return
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo(title, str(text), parent=root)
        root.destroy()
    except Exception:
        pass                        # no screen: the printed line is the message

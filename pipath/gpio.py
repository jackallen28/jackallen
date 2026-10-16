"""GPIO helpers for the app: Simulator vs Real Pi, wiring parts, the 40-pin header, wiring checks."""
from __future__ import annotations

import os
from pathlib import Path

SHIM = Path(__file__).resolve().parent / "gpio_shim.py"

SIM_ENV = {"GPIOZERO_PIN_FACTORY": "mock", "GPIOZERO_MOCK_PIN_CLASS": "mockpwmpin"}

# What each gpiozero class looks like on the on-screen board
BOARD_KIND = {
    "LED": "led", "PWMLED": "led", "OutputDevice": "led", "DigitalOutputDevice": "led",
    "PWMOutputDevice": "led", "Buzzer": "buzzer", "TonalBuzzer": "buzzer",
    "Button": "button", "MotionSensor": "pir", "RGBLED": "rgbled",
    "LineSensor": "switch", "LightSensor": "switch", "DigitalInputDevice": "switch", "InputDevice": "switch",
}
INPUT_KINDS = {"button", "switch", "pir"}

# Physical header pin -> what it is (Raspberry Pi 3B, 40 pins). Ints are GPIO (BCM) numbers.
HEADER = {
    1: "3V3", 2: "5V", 3: 2, 4: "5V", 5: 3, 6: "GND", 7: 4, 8: 14, 9: "GND", 10: 15,
    11: 17, 12: 18, 13: 27, 14: "GND", 15: 22, 16: 23, 17: "3V3", 18: 24, 19: 10, 20: "GND",
    21: 9, 22: 25, 23: 11, 24: 8, 25: "GND", 26: 7, 27: "ID", 28: "ID", 29: 5, 30: "GND",
    31: 6, 32: 12, 33: 13, 34: "GND", 35: 19, 36: 16, 37: 26, 38: 20, 39: "GND", 40: 21,
}

SAFETY = [
    "Turn the Pi **off** before you change any wires.",
    "Always put a **330Ω resistor** in series with an LED.",
    "**Never** connect a 5V pin to a GPIO pin.",
    "No motors straight from the GPIO pins.",
    "Not sure? Ask your teacher to check your circuit before you switch on.",
]


def on_real_pi() -> bool:
    """True on a Raspberry Pi (set PIPATH_FORCE_SIM=1 to pretend otherwise)."""
    if os.environ.get("PIPATH_FORCE_SIM"):
        return False
    try:
        return "Raspberry Pi" in Path("/proc/device-tree/model").read_text(errors="ignore")
    except OSError:
        return False


def mode_env(mode: str) -> dict:
    return dict(SIM_ENV) if mode == "sim" else {}


def expand_events(events: list | None) -> list[tuple[float, str]]:
    """Turn a step's demo_events into timed shim commands.

    "1.5 press 23" / "1.8 release 23"     one command at 1.5 s / 1.8 s
    "2 tap 23"                            press, then release 0.2 s later
    "1 tap 23 every 0.8 until 30"         keep tapping (for games with random waits)
    """
    out: list[tuple[float, str]] = []
    for ev in events or []:
        w = str(ev).split()
        t, action, pin = float(w[0]), w[1], w[2]
        every = float(w[w.index("every") + 1]) if "every" in w else None
        until = float(w[w.index("until") + 1]) if "until" in w else t
        times = [t] if not every else [t + i * every for i in range(int((until - t) / every) + 1)]
        for x in times:
            if action == "tap":
                out += [(x, f"press {pin}"), (x + 0.2, f"release {pin}")]
            else:
                out.append((x, f"{action} {pin}"))
    return sorted(out)


def wiring_parts(lesson: dict) -> list[dict]:
    """The [[wiring]] rows that describe a part on a pin (rows without a kind are tips)."""
    parts = []
    for row in lesson.get("wiring", []):
        kind = row.get("kind")
        pins = row.get("pins") or ([row["pin"]] if "pin" in row else [])
        if kind and pins:
            parts.append({"kind": kind, "pins": [int(p) for p in pins], "label": row.get("part", kind),
                          "colour": row.get("colour", "red")})
    return parts


def wiring_check_program(parts: list[dict]) -> str:
    """A tiny program that tests each part in turn and prints ✓ / ✗ lines the app can read."""
    lines = [
        "from gpiozero import LED, Button, Buzzer, MotionSensor, RGBLED",
        "from time import sleep",
        "",
        'print("Checking your wiring, one part at a time.")',
    ]
    for p in parts:
        name, pins, k = p["label"], p["pins"], p["kind"]
        pin = pins[0]
        if k == "led":
            lines += [f'print("Watch the {name} (GPIO{pin}): it should blink 3 times.")',
                      f"d = LED({pin})", "d.blink(0.3, 0.3, n=3, background=False)", "d.close()",
                      f'print("• {name} (GPIO{pin}) done. Did it blink? If not, check its long leg and resistor.")']
        elif k == "rgbled":
            lines += [f'print("Watch the {name}: red, then green, then blue.")',
                      f"d = RGBLED({pins[0]}, {pins[1]}, {pins[2]})",
                      "for c in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:", "    d.color = c", "    sleep(0.6)",
                      "d.close()", f'print("• {name} done. Did you see all three colours?")']
        elif k == "buzzer":
            lines += [f'print("Listen to the {name} (GPIO{pin}): 3 beeps.")',
                      f"d = Buzzer({pin})", "d.beep(0.1, 0.2, n=3, background=False)", "d.close()",
                      f'print("• {name} (GPIO{pin}) done. Did you hear it? If not, check + goes to GPIO{pin}.")']
        elif k in ("button", "switch"):
            lines += [f"d = Button({pin})", f'print("Press the {name} (GPIO{pin}) now...")',
                      "ok = d.wait_for_press(timeout=10)", "d.close()",
                      f'print("✓ {name} (GPIO{pin}) works!" if ok else '
                      f'"✗ No press from the {name} (GPIO{pin}). Check its legs cross the middle gap.")']
        elif k == "pir":
            lines += [f"d = MotionSensor({pin})",
                      f'print("Wave your hand in front of the {name} (GPIO{pin})...")',
                      "ok = d.wait_for_motion(timeout=20)", "d.close()",
                      f'print("✓ {name} (GPIO{pin}) works!" if ok else '
                      f'"✗ No motion from the {name} (GPIO{pin}). Give it a minute to warm up, then check VCC, OUT and GND.")']
    lines.append('print("Wiring check finished.")')
    return "\n".join(lines) + "\n"

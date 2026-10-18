"""Free Play: the logic behind the sandbox (no Tk here, so it can be tested).

- parts_from_code(code)  the hardware a program makes (LED(17), Button(23), DistanceSensor(...)),
                         as wiring parts, so the Wiring card can show how to hook them up
- wiring_rows(parts)     lesson-style [[wiring]] rows with "connect" text and physical pin numbers
- add_part(code, part)   the code with a part from data/freeplay.toml added at a position, using
                         free pins from the standard pin plan and a fresh variable name
- load()                 the parts library and starter ideas
"""
from __future__ import annotations

import ast
import re
import tomllib

from .content import DATA_DIR
from .gpio import HEADER

FILE = DATA_DIR / "freeplay.toml"
PHYSICAL = {what: phys for phys, what in HEADER.items() if isinstance(what, int)}   # GPIO -> pin

# The standard pin plan (CLAUDE.md §7): which pins each kind of part uses first
PLAN = {"led": [17, 27, 22, 5, 6, 13], "button": [23, 24, 25], "buzzer": [18]}
NAMES = {"led": "led", "button": "button", "buzzer": "buzzer", "distance": "sensor", "rgbled": "lamp",
         "bar": "bar", "camera": "cam", "software": "x"}

# gpiozero class -> board kind
DEVICE_KINDS = {"LED": "led", "PWMLED": "led", "Button": "button", "Buzzer": "buzzer", "TonalBuzzer": "buzzer",
                "MotionSensor": "pir", "DistanceSensor": "distance", "RGBLED": "rgbled",
                "LEDBoard": "leds", "LEDBarGraph": "leds", "LineSensor": "button", "LightSensor": "button"}
COLOURS = ["red", "amber", "green", "yellow", "blue", "white"]


def load() -> dict:
    with open(FILE, "rb") as f:
        data = tomllib.load(f)
    return {"parts": data.get("part", []), "ideas": data.get("idea", [])}


# ---------------------------------------------------------------- reading the student's code

def _int(node) -> int | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, int) else None


def parts_from_code(code: str) -> list[dict]:
    """The GPIO parts a program makes, in order: [{kind, pins, label, colour}]. Only pins written as
    plain numbers count (a pin in a variable can't be known before the program runs)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    names = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and len(n.targets) == 1:
            t = n.targets[0]
            names[id(n.value)] = t.id if isinstance(t, ast.Name) else ast.unparse(t)
    parts, used = [], set()
    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
    for call in calls:
        fname = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
        kind = DEVICE_KINDS.get(fname)
        if not kind:
            continue
        var = names.get(id(call))
        kw = {k.arg: _int(k.value) for k in call.keywords if k.arg}
        if kind == "distance":
            echo, trig = kw.get("echo"), kw.get("trigger")
            if echo is None and call.args:
                echo = _int(call.args[0])
            if trig is None and len(call.args) > 1:
                trig = _int(call.args[1])
            if echo is not None and trig is not None:
                parts.append({"kind": "distance", "pins": [echo, trig], "label": _label(var, "distance sensor")})
                used.update((echo, trig))
            continue
        pins = [p for p in (_int(a) for a in call.args) if p is not None]
        if not pins and kw.get("pin") is not None:
            pins = [kw["pin"]]
        if kind == "rgbled" and len(pins) >= 3:
            parts.append({"kind": "rgbled", "pins": pins[:3], "label": _label(var, "RGB LED")})
        elif kind == "leds":
            for i, p in enumerate(pins):
                parts.append({"kind": "led", "pins": [p], "label": f"{_label(var, 'LEDs')} {i + 1}",
                              "colour": COLOURS[i % len(COLOURS)]})
        elif pins and kind != "leds":
            p = pins[0]
            part = {"kind": kind, "pins": [p], "label": _label(var, fname)}
            if kind == "led":
                part["colour"] = COLOURS[sum(1 for q in parts if q["kind"] == "led") % len(COLOURS)]
            parts.append(part)
        used.update(pins)
    return parts


def _label(var: str | None, fallback: str) -> str:
    return var if var else fallback


def _pin(gpio: int) -> str:
    phys = PHYSICAL.get(gpio)
    return f"GPIO{gpio} (pin {phys})" if phys else f"GPIO{gpio}"


def wiring_rows(parts: list[dict]) -> list[dict]:
    """Rows like a lesson's [[wiring]], with plain-English connections, for the Wiring card."""
    rows = []
    for p in parts:
        k, pins = p["kind"], p["pins"]
        row = {"part": p["label"], "kind": k, "pins": pins}
        if k == "led":
            row["colour"] = p.get("colour", "red")
            row["connect"] = f"{_pin(pins[0])} → 330Ω resistor → LED long leg (+). Short leg (−) → GND."
        elif k == "button":
            row["connect"] = f"One leg → {_pin(pins[0])}. The leg across the middle gap → GND."
        elif k == "buzzer":
            row["connect"] = f"An *active* buzzer: + (the longer leg) → {_pin(pins[0])}. − → GND."
        elif k == "pir":
            row["connect"] = f"VCC → 5V (pin 2), OUT → {_pin(pins[0])}, GND → GND."
        elif k == "rgbled":
            r, g, b = pins
            row["connect"] = (f"Red → 330Ω → {_pin(r)}, green → 330Ω → {_pin(g)}, blue → 330Ω → {_pin(b)}. "
                              "The longest leg → GND (common cathode).")
        elif k == "distance":
            echo, trig = pins
            row["connect"] = (f"VCC → 5V (pin 2). GND → GND (pin 6). TRIG → {_pin(trig)}. ECHO → 1kΩ resistor → "
                              f"{_pin(echo)}, plus a 2kΩ resistor from GPIO{echo} to GND (keeps the 5V echo safe).")
        rows.append(row)
    return rows


def pin_warnings(parts: list[dict]) -> list[str]:
    """Clashes a student should know about before they wire anything."""
    seen: dict[int, str] = {}
    out = []
    for p in parts:
        for pin in p["pins"]:
            if pin in seen:
                out.append(f"GPIO{pin} is used by both **{seen[pin]}** and **{p['label']}**. Each part needs its own pin.")
            elif pin in (2, 3, 14, 15) or not 2 <= pin <= 27:
                out.append(f"GPIO{pin} ({p['label']}) isn't a good pin to use. Try one from the pin plan, like 17 or 23.")
            seen[pin] = p["label"]
    return out


# ---------------------------------------------------------------- adding a part

def free_pins(code: str, kind: str, count: int = 1) -> list[int]:
    """Pins from the standard plan that the code doesn't use yet (LEDs, buttons and the buzzer)."""
    used = {p for part in parts_from_code(code) for p in part["pins"]}
    used |= {int(n) for n in re.findall(r"\b(\d{1,2})\b", code) if 2 <= int(n) <= 27} & set(sum(PLAN.values(), []))
    pool = PLAN["led"] if kind in ("led", "rgbled", "bar") else PLAN.get(kind, [])
    free = [p for p in pool if p not in used]
    if len(free) < count:                         # all taken: reuse from the start (the Coach will warn)
        free += [p for p in pool if p not in free]
    return free[:count]


def fresh_name(code: str, base: str) -> str:
    taken = set(re.findall(r"\b[A-Za-z_]\w*\b", code))
    if base not in taken:
        return base
    n = 2
    while f"{base}{n}" in taken:
        n += 1
    return f"{base}{n}"


def add_part(code: str, part: dict, position: int | None = None) -> tuple[str, str, int]:
    """Add a part to code. position: a character offset (default: the end). Returns
    (new code, the Coach's tip, where the cursor should go)."""
    kind = part.get("kind", "software")
    name = fresh_name(code, NAMES.get(kind, "x"))
    count = 6 if kind == "bar" else 3 if kind == "rgbled" else 1
    pins = free_pins(code, kind, count) if kind in ("led", "button", "buzzer", "rgbled", "bar") else []
    values = {"name": name, "pin": pins[0] if pins else "", "pins": ", ".join(map(str, pins))}
    snippet = part["code"].strip("\n").format(**values) + "\n"
    tip = part.get("tip", "").format(**values)

    lines = code.splitlines()
    have = {l.strip() for l in lines}
    missing = [imp for imp in part.get("imports", []) if imp not in have and not _imported(code, imp)]
    pos = _safe_position(code, len(code) if position is None else max(0, min(position, len(code))))
    before, after = code[:pos], code[pos:]
    if before and not before.endswith("\n"):
        before += "\n"
    body = before + ("\n" if before.strip() and not before.endswith("\n\n") else "") + snippet
    cursor = len(body)
    new = body + after
    if missing:
        # with the other imports at the top (after any comment lines), all in one block
        top = new.splitlines(keepends=True)
        at, i, saw_import = 0, 0, False
        while i < len(top):
            line = top[i].strip()
            if line.startswith(("import ", "from ")):
                saw_import, at = True, sum(len(t) for t in top[:i + 1])
            elif line.startswith("#") or (not line and not saw_import):
                if not saw_import:
                    at = sum(len(t) for t in top[:i + 1])
            else:
                break
            i += 1
        head = "\n".join(missing) + "\n"
        rest = new[at:]
        if not saw_import and rest.strip() and not rest.startswith("\n"):
            head += "\n"
        new = new[:at] + head + rest
        cursor = new.rfind(snippet) + len(snippet)
    return new, tip, cursor


def _safe_position(code: str, pos: int) -> int:
    """Where new top-level code can really go: never in the middle of a line or inside a block
    (it goes after that block), and never after a pause() or a `while True` loop that would stop
    it ever running (it goes before them)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return pos if pos == len(code) or code[pos - 1:pos] in ("", "\n") else code.find("\n", pos) + 1 or len(code)
    starts = [0] + [i + 1 for i, ch in enumerate(code) if ch == "\n"]

    def offset(line: int) -> int:                      # start of a 1-based line
        return starts[line - 1] if line - 1 < len(starts) else len(code)

    line = code.count("\n", 0, pos) + 1
    for node in tree.body:                               # inside a block -> just after it
        if node.lineno <= line <= (node.end_lineno or node.lineno):
            if line > node.lineno or pos > offset(line):
                pos = offset((node.end_lineno or node.lineno) + 1)
            break
    for node in tree.body:                               # never after code that runs forever
        forever = (isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value) or (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", getattr(node.value.func, "attr", "")) in ("pause", "done", "mainloop"))
        if forever and pos >= offset(node.lineno):
            return offset(node.lineno)
    return pos


def _imported(code: str, imp: str) -> bool:
    """Is what `imp` brings in already imported some other way? ("from gpiozero import LED" vs
    "from gpiozero import LED, Button")."""
    m = re.match(r"from (\S+) import (.+)", imp)
    if m:
        mod, names = m.group(1), [n.strip() for n in m.group(2).split(",")]
        for line in code.splitlines():
            lm = re.match(rf"\s*from {re.escape(mod)} import (.+)", line)
            if lm and all(n in [x.strip() for x in lm.group(1).split(",")] for n in names):
                return True
        return False
    return re.search(rf"^\s*{re.escape(imp)}\b", code, re.M) is not None

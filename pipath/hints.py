"""The Coach: turns crashes and failed checks into friendly, tiered hints.

No AI. Three layers:
  1. precheck()        - before running: blanks left in, empty file
     gpio_lint()       - before running GPIO code: friendly warnings (never blocks a run)
  2. diagnose()        - after a crash: parse the traceback, match errors.toml
  3. evaluate_checks() - after a clean run: did the program do what the step asked?
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from .content import load_errors


# ------------------------------------------------------------------ data types

@dataclass
class ErrorInfo:
    type: str                 # e.g. "TypeError"
    message: str              # e.g. 'can only concatenate str (not "int") to str'
    line: int | None = None   # line number in the student's file
    code_line: str = ""       # text of that line
    raw: str = ""             # full traceback


@dataclass
class Diagnosis:
    entry_id: str
    title: str
    explain: str
    hints: list[str] = field(default_factory=list)
    line: int | None = None
    code_line: str = ""
    error_type: str = ""
    message: str = ""


@dataclass
class CheckResult:
    label: str
    passed: bool
    fail: str = ""
    type: str = ""


# ------------------------------------------------------------------ traceback parsing

_FRAME_RE = re.compile(r'^\s*File "(?P<file>.+?)", line (?P<line>\d+)')
_LAST_RE = re.compile(r"^(?P<type>[A-Za-z_][\w.]*)(?::\s?(?P<msg>.*))?$")


def parse_traceback(stderr: str, student_file: str, code: str) -> ErrorInfo | None:
    lines = [l for l in stderr.rstrip().splitlines() if l.strip()]
    if not lines:
        return None
    # The last line that looks like "SomeError: message"
    err_type, msg = None, ""
    for l in reversed(lines):
        if l.startswith((" ", "\t")):
            continue
        m = _LAST_RE.match(l.strip())
        if m:
            err_type = m.group("type").split(".")[-1]    # gpiozero.exc.GPIOPinInUse -> GPIOPinInUse
            msg = (m.group("msg") or "").strip()
            break
    if err_type is None:
        return None

    # The deepest frame that's in the student's own file
    target = Path(student_file).name
    line_no = None
    for l in lines:
        fm = _FRAME_RE.match(l)
        if fm and Path(fm.group("file")).name == target:
            line_no = int(fm.group("line"))
    code_lines = code.splitlines()
    code_line = code_lines[line_no - 1].strip() if line_no and 0 < line_no <= len(code_lines) else ""
    return ErrorInfo(err_type, msg, line_no, code_line, stderr)


# ------------------------------------------------------------------ code analysis

def code_features(code: str) -> dict[str, int]:
    """Count the language features a program uses, e.g. {'call:print': 3, 'node:While': 1}."""
    feats: dict[str, int] = {}

    def add(key: str) -> None:
        feats[key] = feats.get(key, 0) + 1

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return feats
    for node in ast.walk(tree):
        add(f"node:{type(node).__name__}")
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                add(f"call:{f.id}")
            elif isinstance(f, ast.Attribute):
                add(f"call:{f.attr}")
        elif isinstance(node, ast.Attribute):
            add(f"attr:{node.attr}")
        elif isinstance(node, ast.Import):
            for a in node.names:
                add(f"import:{a.name.split('.')[0]}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            add(f"import:{node.module.split('.')[0]}")
            for a in node.names:
                add(f"import:{a.name}")
        elif isinstance(node, ast.JoinedStr):
            add("fstring")
    feats["elif"] = len(re.findall(r"^\s*elif\b", code, re.M))
    return feats


def precheck(code: str, starter: str = "") -> ErrorInfo | None:
    """Problems worth catching before we even run the program.

    Blanks: a line still containing ___ exactly as it appeared in the step's
    starter code. (Students' own ___ - e.g. in ASCII art - are left alone.)
    """
    blank_lines = {l.strip() for l in starter.splitlines() if "___" in l and not l.lstrip().startswith("#")}
    if not blank_lines:
        return None
    for i, l in enumerate(code.splitlines(), 1):
        if l.strip() in blank_lines:
            return ErrorInfo("PiPathBlanks", "blanks left", i, l.strip())
    return None


# ------------------------------------------------------------------ text formatting

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fill(template: str, values: dict) -> str:
    template = template.replace("{{", "\x00").replace("}}", "\x01")
    out = _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values
                           and values[m.group(1)] is not None else m.group(0), template)
    return out.replace("\x00", "{").replace("\x01", "}")


# ------------------------------------------------------------------ the engine

class HintEngine:
    def __init__(self, errors: list[dict] | None = None):
        self.errors = errors if errors is not None else load_errors()
        self._compiled = []
        for e in self.errors:
            self._compiled.append((
                e,
                re.compile(e["message"]) if e.get("message") else None,
                re.compile(e["code"]) if e.get("code") else None,
            ))

    def diagnose(self, err: ErrorInfo, step: dict | None = None) -> Diagnosis:
        values: dict = {"line": err.line or "?", "code_line": err.code_line,
                        "type": err.type, "message": err.message}
        chosen = None
        for entry, msg_re, code_re in self._compiled:
            if entry["type"] not in (err.type, "*"):
                continue
            m = None
            if msg_re is not None:
                m = msg_re.search(err.message)
                if not m:
                    continue
            if code_re is not None and not code_re.search(err.code_line):
                continue
            if m:
                values.update({k: v for k, v in m.groupdict().items() if v is not None})
            chosen = entry
            break
        if chosen is None:  # errors.toml always ends with a "*" entry, but just in case
            chosen = {"id": "generic", "title": "Something went wrong",
                      "explain": "Python stopped with a {type}: {message}", "hints": []}

        hints = [fill(h, values) for h in chosen.get("hints", [])]
        # A lesson step can add its own hint for this error type; it goes first.
        if step:
            extra = step.get("error_hints", {}).get(err.type)
            if extra:
                hints.insert(0, fill(extra, values))
        return Diagnosis(
            entry_id=chosen["id"],
            title=fill(chosen["title"], values),
            explain=fill(chosen["explain"], values),
            hints=hints[:3],
            line=err.line,
            code_line=err.code_line,
            error_type=err.type,
            message=err.message,
        )


def evaluate_checks(checks: list[dict], code: str, output: str, crashed: bool,
                    runs_this_step: int = 1, confirmed: set[int] | None = None) -> list[CheckResult]:
    """confirmed: indexes of "confirm" checks the student has ticked. None means all ticked."""
    feats = code_features(code)
    out_lines = [l for l in output.splitlines() if l.strip()]
    results = []
    for i, c in enumerate(checks):
        t = c["type"]
        label = c.get("label", t)
        flags = re.I if c.get("ignore_case", t in ("output_contains",)) else 0
        if t == "runs_ok":
            ok = not crashed
        elif t == "output_contains":
            ok = (c["value"].lower() in output.lower()) if flags else (c["value"] in output)
        elif t == "output_regex":
            ok = re.search(c["value"], output, flags | re.M) is not None
        elif t == "output_lines_min":
            ok = len(out_lines) >= c.get("min", 1)
        elif t == "code_contains":
            ok = c["value"] in code
        elif t == "code_regex":
            ok = re.search(c["value"], code, flags | re.M) is not None
        elif t == "code_uses":
            ok = feats.get(c["value"], 0) > 0
        elif t == "code_count":
            ok = feats.get(c["value"], 0) >= c.get("min", 1)
        elif t == "run_count_min":
            ok = runs_this_step >= c.get("min", 1)
        elif t == "confirm":
            ok = confirmed is None or i in confirmed
        else:
            ok = True  # unknown check types never block a student
        results.append(CheckResult(label, ok, c.get("fail", ""), t))
    return results


# ------------------------------------------------------------------ GPIO lint

EVENT_ATTRS = {"when_pressed", "when_released", "when_held", "when_motion", "when_no_motion",
               "when_activated", "when_deactivated", "when_light", "when_dark", "when_line", "when_no_line"}
WAITING_CALLS = {"sleep", "pause", "wait_for_press", "wait_for_release", "wait_for_motion",
                 "wait_for_no_motion", "wait_for_active", "wait_for_inactive", "input", "wait",
                 "take_photo", "capture_grid", "join"}
# gpiozero classes whose arguments are pin numbers (positional, or these keywords)
PIN_CLASSES = {
    "LED": ("pin",), "PWMLED": ("pin",), "Button": ("pin",), "Buzzer": ("pin",), "TonalBuzzer": ("pin",),
    "MotionSensor": ("pin",), "LineSensor": ("pin",), "LightSensor": ("pin",),
    "DigitalInputDevice": ("pin",), "DigitalOutputDevice": ("pin",), "OutputDevice": ("pin",),
    "InputDevice": ("pin",), "PWMOutputDevice": ("pin",),
    "RGBLED": ("red", "green", "blue"), "TrafficLights": ("red", "amber", "yellow", "green"),
    "LEDBoard": (), "LEDBarGraph": (), "DistanceSensor": ("echo", "trigger"),
}


def _pin_args(call: ast.Call) -> list[int]:
    name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
    if name not in PIN_CLASSES:
        return []
    vals = [a for a in call.args]
    vals += [k.value for k in call.keywords if k.arg in PIN_CLASSES[name] or (not PIN_CLASSES[name] and k.arg is None)]
    if name not in ("LEDBoard", "LEDBarGraph", "RGBLED", "TrafficLights", "DistanceSensor"):
        vals = vals[:1]
    return [v.value for v in vals if isinstance(v, ast.Constant) and type(v.value) is int]


def gpio_lint(code: str) -> list[str]:
    """Friendly warnings for common GPIO slip-ups. Each starts with the line number."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    if "gpiozero" not in code:
        return []
    warnings: list[tuple[int, str]] = []
    user_funcs = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    seen_pins: dict[int, int] = {}

    for node in ast.walk(tree):
        # 1. button.when_pressed = light.on()   <- brackets run it now, not later
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and t.attr in EVENT_ATTRS:
                    call = ast.get_source_segment(code, node.value) or "..."
                    if not node.value.args and not node.value.keywords and call.endswith("()"):
                        fix = f"`{ast.get_source_segment(code, t)} = {call[:-2]}`"
                    else:
                        fix = "a function name with no brackets"
                    warnings.append((node.lineno, f"`{t.attr} = {call}` has brackets, so it runs straight away "
                                                  f"instead of waiting for the event. Use {fix}."))
        # 2. while True: with nothing that waits
        elif isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value in (True, 1):
            calls = {(n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
                     for n in ast.walk(node) if isinstance(n, ast.Call)}
            if not calls & (WAITING_CALLS | user_funcs):
                warnings.append((node.lineno, "this `while True` loop never waits, so it runs flat out and keeps "
                                              "the Pi busy. Add `sleep(0.01)` inside it, or use `when_pressed`."))
        # 3 + 4. pin numbers
        elif isinstance(node, ast.Call):
            for pin in _pin_args(node):
                if not 2 <= pin <= 27:
                    warnings.append((node.lineno, f"pin `{pin}` isn't a GPIO number. On a Pi they go from 2 to 27. "
                                                  "Use the GPIO number (like 17), not the pin's position on the board."))
                elif pin in (2, 3, 14, 15):
                    warnings.append((node.lineno, f"GPIO{pin} is a special pin ({'I²C' if pin < 4 else 'serial'}). "
                                                  "It may not behave like the others. The pin plan uses 4-6, 13 and 17-27."))
                elif pin in seen_pins and seen_pins[pin] != node.lineno:
                    warnings.append((node.lineno, f"GPIO{pin} is already used on line {seen_pins[pin]}. "
                                                  "Each part needs its own pin."))
                else:
                    seen_pins.setdefault(pin, node.lineno)
    return [f"Line {n}: {w}" for n, w in sorted(warnings)]

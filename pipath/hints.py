"""The Coach: turns crashes and failed checks into friendly, tiered hints.

No AI. Three layers:
  1. precheck()        - before running: blanks left in, empty file
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
                    runs_this_step: int = 1) -> list[CheckResult]:
    feats = code_features(code)
    out_lines = [l for l in output.splitlines() if l.strip()]
    results = []
    for c in checks:
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
        else:
            ok = True  # unknown check types never block a student
        results.append(CheckResult(label, ok, c.get("fail", "")))
    return results

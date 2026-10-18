"""Student profiles, lesson progress and saved code.

Everything lives in plain files under ~/PiPath (or $PIPATH_HOME):

    ~/PiPath/
        app.json                      last student used, etc.
        students/<slug>/
            profile.json              first_name (all the names, joined), names, school, help_level, show,
                                      tour_done (older profiles may have class_code, and no names / show)
            progress.json             per-lesson status, step, hints used
            lessons/<file>.py         code for each lesson
            lessons/backups/          code saved before a step replaces it
            projects/<name>.py        Free Play projects
        exports/                      progress CSV exports (older versions)
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .levels import DEFAULT as DEFAULT_LEVEL, normalise as normalise_level

APP_HOME = Path(os.environ.get("PIPATH_HOME", Path.home() / "PiPath"))
STUDENTS = APP_HOME / "students"

# Project names that would shadow a module students import
RESERVED_NAMES = {
    "random", "time", "turtle", "math", "string", "gpiozero", "tkinter", "csv",
    "datetime", "json", "os", "sys", "signal", "statistics", "test", "code", "pipath",
    "pipath_camera", "pipath_computer", "picamera2", "glob", "subprocess", "webbrowser", "wave",
} | set(getattr(sys, "stdlib_module_names", ()))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, data) -> None:
    """Write atomically so a power cut never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default
    return data if type(data) is type(default) else default      # e.g. a profile that isn't a {...}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "student"


# ---------------------------------------------------------------- validation

NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|['’ \-]){0,29}$")      # letters in any language (Thảo, Ngāti, Łukasz)
MAX_NAMES = 4                     # students can share a Pi (pair or group work)
SHOW_CHOICES = ["all", "simple", "moderate", "computer", "advanced", "lab", "camera"]   # tier ids


def _show_ok(value) -> bool:
    """"all" or any tier id (a teacher can add tiers to catalog.toml)."""
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,30}", value) is not None


def join_names(names: list[str]) -> str:
    """["Sam"] -> "Sam", ["Sam", "Alex"] -> "Sam & Alex", three or more -> "Sam, Alex & Priya"."""
    names = [n.strip() for n in names if n and n.strip()]
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " & " + names[-1]


def validate_names(names: list[str], school: str) -> dict:
    """Errors keyed by "name0", "name1"... and "school". Blank extra name boxes are ignored."""
    errors: dict[str, str] = {}
    filled = [(i, n.strip()) for i, n in enumerate(names) if n.strip()]
    if not filled:
        errors["name0"] = "Please type your first name."
    for i, n in filled:
        if not NAME_RE.match(n):
            errors[f"name{i}"] = "Use letters only (up to 30)."
    seen = set()
    for i, n in filled:
        if n.lower() in seen:
            errors[f"name{i}"] = "That name is already in the list."
        seen.add(n.lower())
    school_err = validate_profile("x", school).get("school")
    if school_err:
        errors["school"] = school_err
    return errors


def validate_profile(first_name: str, school: str, class_code: str = "") -> dict[str, str]:
    errors = {}
    if not first_name.strip():
        errors["first_name"] = "Please type your first name."
    elif not NAME_RE.match(first_name.strip()):
        errors["first_name"] = "Use letters only (up to 30)."
    if not school.strip():
        errors["school"] = "Please type your school's name."
    elif len(school.strip()) > 60:
        errors["school"] = "That's a bit long. Try a shorter version."
    if len(class_code.strip()) > 15:
        errors["class_code"] = "Keep the class short, like 8B or Room 4."
    return errors


def validate_project_name(name: str) -> str | None:
    name = name.strip()
    if not name:
        return "Give your project a name."
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_ \-]{0,39}", name):
        return "Start with a letter. Use letters, numbers, spaces, - or _."
    if file_stem(name) in RESERVED_NAMES:
        return f"'{name}' is the name of a Python module. Pick another name so they don't clash."
    return None


def file_stem(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", name.strip()).lower()


# ---------------------------------------------------------------- app state

def app_state() -> dict:
    return read_json(APP_HOME / "app.json", {})


def set_app_state(**kw) -> None:
    s = app_state()
    s.update(kw)
    write_json(APP_HOME / "app.json", s)


# ---------------------------------------------------------------- students

class Student:
    def __init__(self, folder: Path):
        self.folder = folder
        self.profile = read_json(folder / "profile.json", {})
        self._progress = None        # read when first needed (the welcome screen lists everyone)

    @property
    def progress(self) -> dict:
        if self._progress is None:
            self._progress = read_json(self.folder / "progress.json", {"lessons": {}})
        return self._progress

    @progress.setter
    def progress(self, value: dict) -> None:
        self._progress = value

    @property
    def help_level(self) -> str:
        return normalise_level(self.profile.get("help_level"))

    def set_help_level(self, level: str) -> None:
        self.profile["help_level"] = normalise_level(level)
        self.save_profile()

    @property
    def show(self) -> str:
        """Which tier the activity picker shows ("all" = everything)."""
        value = self.profile.get("show", "all")
        return value if _show_ok(value) else "all"

    def set_show(self, value: str) -> None:
        self.profile["show"] = value if _show_ok(value) else "all"
        self.save_profile()

    @property
    def names(self) -> list[str]:
        names = self.profile.get("names")
        if isinstance(names, list) and names and all(isinstance(n, str) for n in names):
            return list(names)
        return [self.first_name]

    def set_names(self, names: list[str]) -> None:
        names = [n.strip() for n in names if n.strip()][:MAX_NAMES]
        if names:
            self.profile["names"] = names
            self.profile["first_name"] = join_names(names)
            self.save_profile()

    # -- identity
    @property
    def slug(self) -> str:
        return self.folder.name

    @property
    def first_name(self) -> str:
        return self.profile.get("first_name", "Student")

    @property
    def label(self) -> str:
        bits = [self.profile.get("class_code", ""), self.profile.get("school", "")]
        return " · ".join(b for b in bits if b)

    def save_profile(self) -> None:
        write_json(self.folder / "profile.json", self.profile)

    def save_progress(self) -> None:
        write_json(self.folder / "progress.json", self.progress)

    # -- lesson progress
    def lesson(self, lesson_id: str) -> dict:
        lessons = self.progress.setdefault("lessons", {})
        return lessons.setdefault(lesson_id, {
            "status": "new",          # new | in_progress | complete
            "step": 0,
            "steps_done": [],
            "steps_started": [],
            "hints_used": 0,
            "runs": 0,
            "errors": 0,
            "started": None,
            "completed": None,
        })

    def lesson_status(self, lesson_id: str) -> str:
        return self.progress.get("lessons", {}).get(lesson_id, {}).get("status", "new")

    def mark_started(self, lesson_id: str) -> None:
        lp = self.lesson(lesson_id)
        if lp["status"] == "new":
            lp["status"] = "in_progress"
            lp["started"] = _now()
        self.save_progress()

    def mark_complete(self, lesson_id: str) -> None:
        lp = self.lesson(lesson_id)
        lp["status"] = "complete"
        lp["completed"] = lp["completed"] or _now()
        self.save_progress()

    # -- code files
    def lesson_code_path(self, file_name: str) -> Path:
        return self.folder / "lessons" / file_name

    def read_lesson_code(self, file_name: str) -> str | None:
        p = self.lesson_code_path(file_name)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def save_lesson_code(self, file_name: str, code: str) -> Path:
        p = self.lesson_code_path(file_name)
        write_text(p, code)
        return p

    def backup_lesson_code(self, file_name: str, step_no: int) -> None:
        code = self.read_lesson_code(file_name)
        if code and code.strip():
            stem = Path(file_name).stem
            write_text(self.folder / "lessons" / "backups" / f"{stem}_before_step{step_no}.py", code)

    # -- free build projects
    @property
    def projects_dir(self) -> Path:
        return self.folder / "projects"

    def list_projects(self) -> list[Path]:
        if not self.projects_dir.exists():
            return []
        return sorted(self.projects_dir.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)

    def project_path(self, name: str) -> Path:
        return self.projects_dir / f"{file_stem(name)}.py"


def list_students() -> list[Student]:
    if not STUDENTS.exists():
        return []
    out = [Student(d) for d in STUDENTS.iterdir() if (d / "profile.json").exists()]
    return sorted(out, key=lambda s: s.profile.get("last_seen", ""), reverse=True)


def _names_key(names) -> tuple:
    if isinstance(names, str):
        names = [names]
    return tuple(sorted(n.strip().lower() for n in names if n.strip()))


def find_student(names, school: str) -> Student | None:
    """An existing profile with the same name(s) and school (ignoring capitals, spaces and order)."""
    key = (_names_key(names), " ".join(school.lower().split()))
    for s in list_students():
        if (_names_key(s.names), " ".join(str(s.profile.get("school") or "").lower().split())) == key:
            return s
    return None


def create_student(names, school: str, class_code: str = "", help_level: str | None = None,
                   show: str = "all") -> Student:
    """names: one first name, or a list of first names for students sharing a Pi."""
    names = [names] if isinstance(names, str) else list(names)
    names = [n.strip() for n in names if n.strip()][:MAX_NAMES]
    first_name = join_names(names)
    base = slugify("-".join(names) + (f"-{class_code}" if class_code.strip() else ""))
    folder = STUDENTS / base
    n = 2
    while folder.exists():
        folder = STUDENTS / f"{base}-{n}"
        n += 1
    folder.mkdir(parents=True)
    s = Student(folder)
    s.profile = {
        "first_name": first_name,
        "names": names,
        "school": school.strip(),
        "class_code": class_code.strip(),
        "created": _now(),
        "last_seen": _now(),
        "tour_done": False,
        "help_level": normalise_level(help_level or DEFAULT_LEVEL),
        "show": show if _show_ok(show) else "all",
    }
    s.save_profile()
    s.save_progress()
    return s


def touch_student(s: Student) -> None:
    s.profile["last_seen"] = _now()
    s.save_profile()
    set_app_state(last_student=s.slug)


# ---------------------------------------------------------------- progress summary

def _cell(value) -> str:
    """Spreadsheets run a cell starting with = + - @ as a formula: make it plain text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def _progress_rows(catalog_projects: list[dict]):
    header = ["first_name", "class", "school", "help_level", "last_seen"]
    for p in catalog_projects:
        header += [f"{p['id']}_status", f"{p['id']}_hints", f"{p['id']}_runs"]
    yield header
    for s in list_students():
        row = [_cell(v) for v in (s.first_name, s.profile.get("class_code", ""), s.profile.get("school", ""),
                                  s.help_level, s.profile.get("last_seen", ""))]
        for p in catalog_projects:
            lp = s.progress.get("lessons", {}).get(p["id"], {})
            row += [lp.get("status", "new"), lp.get("hints_used", 0), lp.get("runs", 0)]
        yield row


def export_progress_csv(catalog_projects: list[dict]) -> Path:
    out = APP_HOME / "exports" / f"progress_{datetime.now():%Y-%m-%d_%H%M}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(_progress_rows(catalog_projects))
    return out


# ---------------------------------------------------------------- save a copy, wipe the session

def wipe_summary() -> dict:
    """What a wipe would delete: student profiles, their saved files, and old CSV exports."""
    students = list_students()
    files = sum(1 for p in STUDENTS.rglob("*") if p.is_file()) if STUDENTS.exists() else 0
    exports = APP_HOME / "exports"
    return {"students": len(students), "files": files,
            "schools": sorted({s.profile.get("school", "") for s in students} - {""}),
            "exports": sum(1 for p in exports.rglob("*") if p.is_file()) if exports.exists() else 0}


def downloads_folder() -> Path:
    """Where "Save a copy" puts the zip: the Pi's Downloads folder (made if it isn't there)."""
    return Path(os.environ.get("PIPATH_DOWNLOADS", Path.home() / "Downloads"))


_PACKED = {".jpg", ".jpeg", ".png", ".gif", ".wav", ".mp3", ".ogg", ".mp4", ".zip"}


def save_copy(catalog_projects: list[dict] | None = None, dest: Path | None = None) -> Path:
    """Zip every student's save data (profiles, progress, code, photos, projects) into dest
    (Downloads by default), with a progress.csv summary a teacher can open in a spreadsheet."""
    dest = dest or downloads_folder()
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"PiPath_save_{datetime.now():%Y-%m-%d_%H%M%S}.zip"
    tmp = out.with_name(out.name + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for folder in (STUDENTS, APP_HOME / "exports"):
            if folder.exists():
                for f in sorted(folder.rglob("*")):
                    if f.is_file() and not f.name.endswith(".tmp"):
                        packed = f.suffix.lower() in _PACKED       # photos and sounds: already squeezed
                        z.write(f, Path("PiPath") / f.relative_to(APP_HOME),
                                compress_type=zipfile.ZIP_STORED if packed else zipfile.ZIP_DEFLATED)
        if catalog_projects is not None:
            import io
            buf = io.StringIO()
            csv.writer(buf).writerows(_progress_rows(catalog_projects))
            z.writestr("PiPath/progress.csv", buf.getvalue())
    os.replace(tmp, out)
    return out


def _remove(folder: Path) -> None:
    """Move the folder aside first, so a power cut mid-delete never leaves half a profile behind."""
    if not folder.exists():
        return
    aside = folder.with_name(f".wiping_{folder.name}_{datetime.now():%Y%m%d%H%M%S%f}")
    os.replace(folder, aside)
    shutil.rmtree(aside, ignore_errors=True)


def wipe_all(keep_exports: bool = False) -> dict:
    """Wipe the session: delete every student profile, their progress, code, photos and projects
    (and old CSV exports unless keep_exports). The Pi's own settings (Simulator / Real Pi, camera) stay."""
    done = wipe_summary()
    _remove(STUDENTS)
    if not keep_exports:
        _remove(APP_HOME / "exports")
    for left in APP_HOME.glob(".wiping_*"):          # anything an earlier, interrupted wipe left
        shutil.rmtree(left, ignore_errors=True)
    state = app_state()
    if state.pop("last_student", None) is not None:
        write_json(APP_HOME / "app.json", state)
    return done

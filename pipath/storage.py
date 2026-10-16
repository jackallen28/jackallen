"""Student profiles, lesson progress and saved code.

Everything lives in plain files under ~/PiPath (or $PIPATH_HOME):

    ~/PiPath/
        app.json                      last student used, etc.
        students/<slug>/
            profile.json              first name, school, class, tour_done
            progress.json             per-lesson status, step, hints used
            lessons/<file>.py         code for each lesson
            lessons/backups/          code saved before a step replaces it
            projects/<name>.py        Free Build projects
        exports/                      teacher CSV exports
"""
from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

APP_HOME = Path(os.environ.get("PIPATH_HOME", Path.home() / "PiPath"))
STUDENTS = APP_HOME / "students"

# Project names that would shadow a module students import
RESERVED_NAMES = {
    "random", "time", "turtle", "math", "string", "gpiozero", "tkinter", "csv",
    "datetime", "json", "os", "sys", "signal", "statistics", "test", "code", "pipath",
}


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
            return json.load(f)
    except (OSError, ValueError):
        return default


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

NAME_RE = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' \-]{0,29}$")


def validate_profile(first_name: str, school: str, class_code: str) -> dict[str, str]:
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
        self.progress = read_json(folder / "progress.json", {"lessons": {}})

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


def create_student(first_name: str, school: str, class_code: str) -> Student:
    base = slugify(f"{first_name}-{class_code}" if class_code.strip() else first_name)
    folder = STUDENTS / base
    n = 2
    while folder.exists():
        folder = STUDENTS / f"{base}-{n}"
        n += 1
    folder.mkdir(parents=True)
    s = Student(folder)
    s.profile = {
        "first_name": first_name.strip(),
        "school": school.strip(),
        "class_code": class_code.strip(),
        "created": _now(),
        "last_seen": _now(),
        "tour_done": False,
    }
    s.save_profile()
    s.save_progress()
    return s


def touch_student(s: Student) -> None:
    s.profile["last_seen"] = _now()
    s.save_profile()
    set_app_state(last_student=s.slug)


# ---------------------------------------------------------------- teacher export

def export_progress_csv(catalog_projects: list[dict]) -> Path:
    out = APP_HOME / "exports" / f"progress_{datetime.now():%Y-%m-%d_%H%M}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["first_name", "class", "school", "last_seen"]
        for p in catalog_projects:
            header += [f"{p['id']}_status", f"{p['id']}_hints", f"{p['id']}_runs"]
        w.writerow(header)
        for s in list_students():
            row = [s.first_name, s.profile.get("class_code", ""), s.profile.get("school", ""),
                   s.profile.get("last_seen", "")]
            for p in catalog_projects:
                lp = s.progress.get("lessons", {}).get(p["id"], {})
                row += [lp.get("status", "new"), lp.get("hints_used", 0), lp.get("runs", 0)]
            w.writerow(row)
    return out

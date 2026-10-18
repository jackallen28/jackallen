"""Loads the teacher-editable data files: config, catalogue, lessons and the errors database."""
from __future__ import annotations

import tomllib
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config() -> dict:
    cfg = {
        "app_name": "PiPath",
        "tagline": "Learn Python one step at a time.",
        "busy_loop_seconds": 8,
        "max_output_lines": 3000,
        "three_star_max_hints": 2,
        "two_star_max_hints": 6,
    }
    path = DATA_DIR / "config.toml"
    if path.exists():
        cfg.update(_load(path))
    return cfg


class Catalog:
    """The list of tiers and projects shown on the home screen."""

    def __init__(self) -> None:
        raw = _load(DATA_DIR / "catalog.toml")
        self.tiers: list[dict] = raw.get("tier", [])
        self.projects: list[dict] = raw.get("project", [])
        self._lessons: dict[str, dict] = {}

    def projects_in(self, tier_id: str) -> list[dict]:
        return [p for p in self.projects if p["tier"] == tier_id]

    def project(self, project_id: str) -> dict | None:
        return next((p for p in self.projects if p["id"] == project_id), None)

    def next_project(self, project_id: str) -> dict | None:
        ids = [p["id"] for p in self.projects]
        i = ids.index(project_id)
        return self.projects[i + 1] if i + 1 < len(ids) else None

    def lesson(self, project_id: str) -> dict:
        """Full lesson content (steps, checks, hints) for a ready project."""
        if project_id not in self._lessons:
            lesson = _load(DATA_DIR / "lessons" / f"{project_id}.toml")
            for i, step in enumerate(lesson.get("steps", [])):
                step.setdefault("id", f"step{i + 1}")
                step.setdefault("support", "scaffolded")
                step.setdefault("starter_mode", "keep")
                step.setdefault("checks", [{"type": "runs_ok", "label": "Your program runs"}])
                step.setdefault("hints", [])
                step.setdefault("error_hints", {})
            self._lessons[project_id] = lesson
        return self._lessons[project_id]


def load_errors() -> list[dict]:
    return _load(DATA_DIR / "errors.toml").get("error", [])

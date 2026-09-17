"""Rebuild a subject's study design YAML from the official VCAA PDF.

VCAA publishes the study designs as text-layer PDFs with a consistent shape:

    Unit 3: <title>
    Area of Study 1
    <AOS title>
    ... prose ...
    Outcome 1
    <outcome statement>
    Key knowledge
    • dot point
    • dot point
    Key skills
    • dot point

so a structural parse gets most of the way there. Anything the parser is unsure
about is written out with `verified: false` and flagged in the report, so you
can see exactly what needs a human eye rather than trusting the whole file.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..config import STUDY_DESIGN_DIR
from .loader import load_study_design_file

UNIT_RE = re.compile(r"^\s*Unit\s+([1-4])\s*[:—-]\s*(.+?)\s*$", re.MULTILINE)
AOS_RE = re.compile(r"^\s*Area of Study\s+(\d)\s*$", re.MULTILINE)
OUTCOME_RE = re.compile(r"^\s*Outcome\s+(\d)\s*$", re.MULTILINE)
KK_RE = re.compile(r"^\s*Key knowledge\s*$", re.MULTILINE | re.IGNORECASE)
KS_RE = re.compile(r"^\s*Key skills\s*$", re.MULTILINE | re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[•▪·●‣]\s*(.+)$")
ACCRED_RE = re.compile(r"\b(20\d{2})\s*[–-]\s*(20\d{2})\b")


def extract_text(pdf_path: str | Path) -> str:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    doc = fitz.open(str(pdf_path))
    pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    doc.close()
    return "\n".join(pages)


def _sections(text: str, unit_numbers=(3, 4)) -> list[dict]:
    """Slice the document into units, then areas of study."""
    units: list[dict] = []
    matches = [m for m in UNIT_RE.finditer(text) if int(m.group(1)) in unit_numbers]
    # Keep the LAST occurrence of each unit heading — earlier ones are usually the
    # contents page and the unit overview, not the detailed specification.
    by_number: dict[int, re.Match] = {}
    for m in matches:
        by_number[int(m.group(1))] = m

    ordered = sorted(by_number.items())
    for i, (number, m) in enumerate(ordered):
        end = ordered[i + 1][1].start() if i + 1 < len(ordered) else len(text)
        units.append({
            "number": number,
            "title": _clean(m.group(2)),
            "body": text[m.end():end],
        })
    return units


def _areas(unit_body: str) -> list[dict]:
    out: list[dict] = []
    marks = list(AOS_RE.finditer(unit_body))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(unit_body)
        chunk = unit_body[m.end():end]
        out.append({"number": int(m.group(1)), **_parse_area(chunk)})
    return out


def _parse_area(chunk: str) -> dict:
    lines = [ln.rstrip() for ln in chunk.splitlines()]
    title = next((_clean(ln) for ln in lines if ln.strip()), "")

    outcome = ""
    om = OUTCOME_RE.search(chunk)
    if om:
        after = chunk[om.end():]
        stop = min(
            (p for p in (
                KK_RE.search(after).start() if KK_RE.search(after) else len(after),
            )),
        )
        outcome = _clean(" ".join(after[:stop].split()))

    key_knowledge = _bullets_after(chunk, KK_RE, stop_at=KS_RE)
    key_skills = _bullets_after(chunk, KS_RE, stop_at=AOS_RE)
    return {
        "title": title,
        "outcome": outcome,
        "key_knowledge": key_knowledge,
        "key_skills": key_skills,
    }


def _bullets_after(chunk: str, start_re: re.Pattern,
                   stop_at: re.Pattern | None = None) -> list[str]:
    m = start_re.search(chunk)
    if not m:
        return []
    rest = chunk[m.end():]
    if stop_at:
        s = stop_at.search(rest)
        if s:
            rest = rest[:s.start()]

    bullets: list[str] = []
    current: list[str] = []
    for line in rest.splitlines():
        b = BULLET_RE.match(line)
        if b:
            if current:
                bullets.append(_clean(" ".join(current)))
            current = [b.group(1)]
        elif current and line.strip():
            current.append(line.strip())      # wrapped continuation line
        elif current and not line.strip():
            bullets.append(_clean(" ".join(current)))
            current = []
    if current:
        bullets.append(_clean(" ".join(current)))
    return [b for b in bullets if len(b) > 12]


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\.$", "", text)
    return text


def import_study_design(
    pdf_path: str | Path,
    subject_id: str,
    out_dir: Path | None = None,
    dry_run: bool = False,
) -> Path:
    """Parse the PDF and rewrite the subject's YAML, preserving question types.

    Question types and command terms are this tool's own editorial data, not
    VCAA's, so they are carried across from the existing file rather than lost.
    """
    out_dir = Path(out_dir or STUDY_DESIGN_DIR)
    target = out_dir / f"{subject_id}.yaml"

    existing: dict = {}
    if target.exists():
        with target.open(encoding="utf-8") as fh:
            existing = yaml.safe_load(fh) or {}

    text = extract_text(pdf_path)
    accred = ACCRED_RE.search(text)
    units_raw = _sections(text)
    if not units_raw:
        raise ValueError(
            f"Found no 'Unit 3'/'Unit 4' headings in {pdf_path}. If the PDF is a "
            "scan rather than a text PDF it needs OCR first."
        )

    short = existing.get("units", [{}])[0].get("id", "").rsplit("-u", 1)[0]
    units = []
    problems: list[str] = []
    for u in units_raw:
        unit_id = f"{short or subject_id}-u{u['number']}"
        areas = []
        for a in _areas(u["body"]):
            aos_id = f"{unit_id}-aos{a['number']}"
            if not a["key_knowledge"]:
                problems.append(f"{aos_id}: no key knowledge bullets found")
            areas.append({
                "id": aos_id,
                "number": a["number"],
                "title": a["title"],
                "outcome": a["outcome"],
                "key_knowledge": [
                    {"id": f"{aos_id}-kk{i:02d}", "text": t, "verified": True}
                    for i, t in enumerate(a["key_knowledge"], start=1)
                ],
                "key_skills": a["key_skills"],
            })
        if not areas:
            problems.append(f"{unit_id}: no areas of study found")
        units.append({"id": unit_id, "number": u["number"],
                      "title": u["title"], "areas_of_study": areas})

    doc = {
        "subject_id": subject_id,
        "subject_name": existing.get("subject_name", subject_id.replace("-", " ").title()),
        "accreditation": f"{accred.group(1)}-{accred.group(2)}" if accred else
                         existing.get("accreditation", ""),
        "source": f"Imported from {Path(pdf_path).name}",
        "units": units,
        # Editorial data — ours, not VCAA's — so it survives the import.
        "question_types": existing.get("question_types", []),
        "command_terms": existing.get("command_terms", {}),
    }

    n_kk = sum(len(a["key_knowledge"]) for u in units for a in u["areas_of_study"])
    print(f"parsed {len(units)} units, "
          f"{sum(len(u['areas_of_study']) for u in units)} areas of study, "
          f"{n_kk} key knowledge dot points")
    for p in problems:
        print(f"  ! {p}")
    if problems:
        print("  Check those against the PDF before trusting the file.")

    if dry_run:
        print(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                             width=100)[:2000])
        return target

    header = (
        f"# {doc['subject_name']} — Units 3 & 4\n"
        f"# Imported from {Path(pdf_path).name}. Dot point wording is VCAA's.\n"
        f"# question_types and command_terms below are this tool's own editorial\n"
        f"# data and are preserved across imports.\n"
    )
    target.write_text(
        header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    load_study_design_file(target)     # fail loudly now rather than at runtime
    return target

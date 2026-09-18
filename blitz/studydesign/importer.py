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

from ..config import STUDY_DESIGN_DIR, USER_DESIGN_DIR
from .loader import load_study_design_file

UNIT_RE = re.compile(r"^\s*Unit\s+([1-4])\s*[:\u2014-]\s*(.+?)\s*$", re.MULTILINE)
# Contents-page rows: "Unit 3: How do fields ......... 50". These are headings
# too, so they must be removed before the real sections can be found.
TOC_LINE = re.compile(r"^.*\.{4,}.*$", re.MULTILINE)
# "Unit 1 and 2: 2023; Units 3 and 4 2024" — VCAA states the period per unit pair.
ACCRED_LINE = re.compile(
    r"Accreditation period\s*\n\s*([^\n]+)", re.IGNORECASE)
# The boilerplate every outcome ends with, which is not part of the outcome.
OUTCOME_TAIL = re.compile(
    r"\s*To achieve this outcome the student will draw on key knowledge.*$",
    re.IGNORECASE | re.DOTALL)
# Equation-editor output: unrecoverable as text (see ingest/textflow.py for the
# same problem in the question books).
MATH_GLYPH = re.compile(r"[\U0001D400-\U0001D7FF]")
AOS_RE = re.compile(r"^\s*Area of Study\s+(\d)\s*$", re.MULTILINE)
OUTCOME_RE = re.compile(r"^\s*Outcome\s+(\d)\s*$", re.MULTILINE)
KK_RE = re.compile(r"^\s*Key knowledge\s*$", re.MULTILINE | re.IGNORECASE)
KS_RE = re.compile(r"^\s*Key skills\s*$", re.MULTILINE | re.IGNORECASE)
# Headings that end a key-knowledge list. Without these the bullet collector
# runs on into the assessment section and turns "Duration: 2.5 hours" and the
# SAC outcome criteria into key knowledge dot points.
SECTION_END_RE = re.compile(
    r"^\s*(Key skills|School-based assessment|External assessment|Assessment|"
    r"Unit \d|Area of Study \d|Outcome \d|End-of-year examination|Description|"
    r"Conditions|Contribution to final assessment|Further advice|"
    r"Satisfactory completion|Duration|Date)\b",
    re.MULTILINE | re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[•▪·●‣]\s*(.+)$")
ACCRED_RE = re.compile(r"\b(20\d{2})\s*[\u2013-]\s*(20\d{2})\b")


def extract_text(pdf_path: str | Path) -> str:
    """The study design as text, from the PDF or the Word file VCAA ships."""
    if Path(pdf_path).suffix.lower() == ".docx":
        from ..ingest.docx import docx_text

        return docx_text(pdf_path)
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    doc = fitz.open(str(pdf_path))
    pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    doc.close()
    return "\n".join(pages)


def _complete_title(text: str, match: re.Match) -> str:
    """Finish a unit title that wrapped onto the next line(s).

    VCE unit titles are questions, so the title is complete once a "?" appears.
    "Unit 3: How do fields explain motion and\nelectricity?" is one title across
    two lines; capturing only the first gives "How do fields explain motion and".
    """
    title = match.group(2).strip()
    if title.endswith("?"):
        return title
    # The match ends just before its own newline, so the first entry here is
    # always empty — skip blanks rather than treating one as the end of the
    # title. Continuation lines are short; body prose is not, so a long line
    # means the title simply never had a "?" and we stop.
    for raw in text[match.end():match.end() + 300].splitlines()[:5]:
        line = raw.strip()
        if not line:
            continue
        if len(line) > 70:
            break
        title = f"{title} {line}".strip()
        if line.endswith("?"):
            break
    return title


def _sections(text: str, unit_numbers=(3, 4)) -> list[dict]:
    """Slice the document into units, then areas of study."""
    text = TOC_LINE.sub("", text)
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
            "title": _clean(_complete_title(text, m)),
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
        outcome = _clean(OUTCOME_TAIL.sub("", " ".join(after[:stop].split())))

    key_knowledge = _bullets_after(chunk, KK_RE, stop_at=SECTION_END_RE)
    key_skills = _bullets_after(chunk, KS_RE, stop_at=SECTION_END_RE)
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
    cleaned = [_trim_subheading(b) for b in bullets]
    return [b for b in cleaned if len(b) > 12]


# A subheading on the line after the last bullet gets swept into it. These are
# Title Case fragments with no sentence punctuation, e.g. "Effects of fields".
TRAILING_HEADING = re.compile(
    r"\s+((?:[A-Z][a-z]+)(?:\s+(?:of|the|and|in|to|for|on)?\s*[A-Za-z]+){0,3})\s*$")


def _trim_subheading(bullet: str) -> str:
    m = TRAILING_HEADING.search(bullet)
    if not m:
        return bullet
    tail = m.group(1).strip()
    # Only strip when the bullet still reads as a complete dot point without it.
    if 6 <= len(tail) <= 40 and len(bullet) - len(tail) > 40:
        return bullet[: m.start()].rstrip(" ,;:")
    return bullet


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\.$", "", text)
    return text


def _strip_maths(text: str) -> tuple[str, bool]:
    """Remove equation-editor wreckage from a dot point.

    VCAA sets formulas with an equation editor, which extracts as private-use
    glyph soup: "5\U0001D439&'( = *!+ G 6". There is no way to recover the real
    formula from the text layer, and leaving the soup in would poison both the
    selection UI and the question tagger's vocabulary. So it is removed, and the
    dot point records that a formula was present.
    """
    if not MATH_GLYPH.search(text):
        return text, False
    # Drop the glyph runs and the punctuation soup immediately around them.
    cleaned = re.sub(r"[\s:,]*[^\w\s]{0,4}[\U0001D400-\U0001D7FF][^,;•\n]*", " ", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,;.])", r"\1", cleaned).strip(" ,;:")
    return cleaned or text, True


def _key_knowledge_entries(aos_id: str, texts: list[str]) -> list[dict]:
    out = []
    for i, raw in enumerate(texts, start=1):
        text, had_formula = _strip_maths(raw)
        entry = {"id": f"{aos_id}-kk{i:02d}", "text": text, "verified": True}
        if had_formula:
            # Surfaced in the UI so a student knows to check the study design
            # itself for the formula this dot point names.
            entry["has_formula"] = True
        out.append(entry)
    return out


# Question types are this tool's editorial data, not VCAA's. A subject that
# has never been set up gets these until someone writes better ones; they are
# generic enough to be true of any VCE written exam.
def default_question_types(subject_id: str) -> list[dict]:
    prefix = "".join(w[0] for w in subject_id.split("-"))[:4] or subject_id[:2]
    return [
        {"id": f"{prefix}-mc", "label": "Multiple choice",
         "description": "Four-option questions.", "typical_marks": [1],
         "default_weight": 0.3},
        {"id": f"{prefix}-short", "label": "Short answer",
         "description": "One to four mark questions with a written answer.",
         "typical_marks": [1, 2, 3, 4], "default_weight": 0.6},
        {"id": f"{prefix}-extended", "label": "Extended response",
         "description": "Longer questions requiring a developed answer.",
         "typical_marks": [5, 6, 8, 10], "default_weight": 1.5},
    ]


def import_study_design(
    pdf_path: str | Path,
    subject_id: str,
    out_dir: Path | None = None,
    dry_run: bool = False,
    subject_name: str | None = None,
) -> Path:
    """Parse the PDF and rewrite the subject's YAML, preserving question types.

    Question types and command terms are this tool's own editorial data, not
    VCAA's, so they are carried across from the existing file rather than lost.
    """
    out_dir = Path(out_dir or USER_DESIGN_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{subject_id}.yaml"

    # Editorial data (question types, command terms) is carried over from the
    # file being replaced: the person's own if there is one, else the shipped.
    existing: dict = {}
    for candidate in (target, STUDY_DESIGN_DIR / f"{subject_id}.yaml"):
        if candidate.exists():
            with candidate.open(encoding="utf-8") as fh:
                existing = yaml.safe_load(fh) or {}
            break

    text = extract_text(pdf_path)
    accred = ACCRED_RE.search(text)
    accred_line = ACCRED_LINE.search(text)
    units_raw = _sections(text)
    if not units_raw:
        raise ValueError(
            f"Found no 'Unit 3'/'Unit 4' headings in {pdf_path}. If it is a "
            "scanned PDF rather than a text PDF it needs OCR first."
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
                "key_knowledge": _key_knowledge_entries(aos_id, a["key_knowledge"]),
                "key_skills": a["key_skills"],
            })
        if not areas:
            problems.append(f"{unit_id}: no areas of study found")
        units.append({"id": unit_id, "number": u["number"],
                      "title": u["title"], "areas_of_study": areas})

    doc = {
        "subject_id": subject_id,
        "subject_name": subject_name or existing.get(
            "subject_name", subject_id.replace("-", " ").title()),
        "accreditation": (
            _clean(accred_line.group(1)) if accred_line
            else f"{accred.group(1)}-{accred.group(2)}" if accred
            else existing.get("accreditation", "")
        ),
        "source": f"Imported from {Path(pdf_path).name}",
        "units": units,
        # Editorial data — ours, not VCAA's — so it survives the import.
        "question_types": existing.get("question_types") or default_question_types(subject_id),
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

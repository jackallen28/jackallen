"""What a subject comes with before it has a single question.

Adding a study design gives Blitz the dot points and nothing else: no book,
no questions, an empty coverage table. That is correct, but it leaves the
person holding a subject with nowhere obvious to start. So creating a
subject also creates its materials folder and writes two files into it:

    sources/<subject>/INDEXING-GUIDE.md   every dot point, and what to do next
    sources/<subject>/dot-points.json     the same, for whatever builds a pack

The guide is the briefing to hand to whoever, or whatever, prepares the
material: the exact dot point ids to tag against, the study design
fingerprint that pins them, the question types, and the rules that were
learned the hard way indexing a real 1000-page book. Both files are
rewritten whenever the study design is imported again, so they never
describe an older version of the curriculum than the index is using.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import SOURCES_DIR
from .corpus.sample import fingerprint
from .studydesign import StudyDesign, load_study_design

GUIDE_NAME = "INDEXING-GUIDE.md"
DOT_POINTS_NAME = "dot-points.json"


def dot_points_payload(design: StudyDesign) -> dict:
    """The machine-readable contract: ids, wording and the fingerprint."""
    return {
        "subject_id": design.subject_id,
        "subject_name": design.subject_name,
        "accreditation": design.accreditation,
        "study_design_fingerprint": fingerprint(design),
        "verified": design.fully_verified,
        "question_types": [
            {"id": qt.id, "label": qt.label, "description": qt.description}
            for qt in design.question_types
        ],
        "dot_points": [
            {
                "id": kk.id,
                "unit": unit.number,
                "area_of_study": area.id,
                "area_title": area.title,
                "text": kk.text,
                "short": kk.display,
            }
            for unit in design.units
            for area in unit.areas_of_study
            for kk in area.key_knowledge
        ],
    }


def _dot_point_tables(design: StudyDesign) -> str:
    out: list[str] = []
    for unit in design.units:
        out.append(f"\n### Unit {unit.number}: {unit.title}\n")
        for area in unit.areas_of_study:
            out.append(f"**Area of Study {area.number}: {area.title}**\n")
            if area.outcome:
                out.append(f"> {area.outcome}\n")
            out.append("| dot point id | key knowledge |")
            out.append("|---|---|")
            for kk in area.key_knowledge:
                text = kk.text.replace("|", "\\|")
                mark = "" if kk.verified else " *(wording not from VCAA)*"
                out.append(f"| `{kk.id}` | {text}{mark} |")
            out.append("")
    return "\n".join(out)


def _question_types(design: StudyDesign) -> str:
    if not design.question_types:
        return "_This subject has no question types defined._\n"
    rows = ["| id | label | what it means |", "|---|---|---|"]
    for qt in design.question_types:
        rows.append(f"| `{qt.id}` | {qt.label} | {qt.description or ''} |")
    return "\n".join(rows) + "\n"


def guide_text(design: StudyDesign) -> str:
    """The whole briefing, as Markdown."""
    n_kk = sum(len(a.key_knowledge) for a in design.all_areas())
    fp = fingerprint(design)
    # A real id from this design: ids carry a short subject prefix that is
    # not always the subject id ("bm-u3-aos1-kk01", not
    # "business-management-u3-aos1-kk01"), so never construct one here.
    example = next((kk.id for a in design.all_areas() for kk in a.key_knowledge),
                   f"{design.subject_id}-u3-aos1-kk01")
    unverified = "" if design.fully_verified else (
        "\n> **This study design's wording is not all VCAA's own.** Dot points\n"
        "> marked below were reconstructed, and sheets built on them carry a\n"
        "> warning. Re-import the official PDF or Word file to replace them.\n")
    return f"""# Indexing {design.subject_name}

_Written by Blitz on {date.today():%d %b %Y}. Rewritten whenever this
subject's study design is imported again._

This folder is where {design.subject_name} material goes. Right now the
subject has its study design and nothing else: **{n_kk} dot points, no
questions**. Everything below is what you need to change that.

| | |
|---|---|
| subject id | `{design.subject_id}` |
| accreditation | {design.accreditation or "not stated"} |
| dot points | {n_kk} |
| study design fingerprint | `{fp}` |
{unverified}

## 1. Put material in this folder

Drop any of these straight in here, or in a subfolder:

- **PDF or Word books, worksheets, notes, exam papers.** Blitz works out
  what kind of document each one is and extracts the questions, the
  diagrams and the worked solutions where the book prints them.
- **Question packs** — a JSON file built by someone, or something, that has
  already been through the book deciding where every question starts and
  what it assesses. A pack beats automatic extraction on every axis. Zip
  the JSON together with its figures folder if it has one.

Then press **Index** on the Index materials page (or run
`blitz index <file> --subject {design.subject_id}`). Nothing leaves the
machine and no model runs.

## 2. The dot points to tag against

These ids are the contract. They are **positional**, so `{example}` means
"the first dot point of the first area of study of Unit 3" and nothing
more: if VCAA republishes the study design and the order shifts, the same
id means something different. That is
what the fingerprint `{fp}` is for. A pack that carries it can be checked
against the design in use; one that does not can be imported into the wrong
dot points without a word of complaint.

`{DOT_POINTS_NAME}` beside this file holds the same list as JSON.
{_dot_point_tables(design)}
## 3. Question types

Every question is filed under one of these. They are Blitz's own
editorial list, not VCAA's, so they can be changed in the study design
file.

{_question_types(design)}
## 4. If you are handing this to a model

Give it this file and `{DOT_POINTS_NAME}`, and hold it to the following.
Each rule cost a real mistake on a real book; the reasoning is in
`docs/full-book-postmortem.md`.

1. **Tag each question on its own**, against the ids above. Use the chapter
   to narrow which area of study is plausible, never to decide the dot
   point for every question in it. One tag is normal; three is suspicious.
   Every id must be one of the {n_kk} listed above, exactly as written.
2. **Keep questions as text** unless the maths genuinely cannot survive
   reconstruction — stacked fractions, roots with a vinculum, matrices,
   mangled symbols. Superscripts, units and Greek letters are text. A
   diagram is a figure, not a reason to crop the words around it.
3. **Say what scale the images are.** Put `figure_zoom` (pixels per PDF
   point) in the pack's `source` block, or ship `page` + `bbox` figures and
   let Blitz crop them itself. A PNG carries no scale; guessing it wrong
   makes every crop the wrong size on the page.
4. **Crop to the content**, not to the text block, and split anything
   taller than about 250 points into one crop per part.
5. **Marks go in `marks`**, not in the question's text.
6. **Fill in `context` and `depends_on`** whenever a question does not stand
   alone — a shared scenario printed above it, or an earlier question it
   refers back to.
7. **Mark rows `approved`** unless there is a concrete doubt; `review` is for
   real problems, not for everything.
8. **Include the fingerprint** `{fp}` in the pack.
9. **Run `blitz import-pack <file> --dry-run` before shipping it.** Zero
   errors is the floor; read the warnings too.

The full schema, with field types and a worked example, is in
`docs/question-pack-schema.md`.

## 5. Check it worked

```bash
blitz coverage {design.subject_id}              # questions now behind each dot point
blitz coverage {design.subject_id} --by-source  # one column per book or pack
```

A dot point sitting at zero has nothing to draw on, and a sheet asking for
it will say so. That table is the honest picture of what this subject can
actually produce.
"""


def write_subject_guide(subject_id: str, root: Path | None = None,
                        design: StudyDesign | None = None) -> list[Path]:
    """Create the subject's materials folder and write its two files."""
    design = design or load_study_design(subject_id)
    folder = (Path(root) / "sources" / subject_id) if root else (SOURCES_DIR / subject_id)
    folder.mkdir(parents=True, exist_ok=True)
    guide = folder / GUIDE_NAME
    guide.write_text(guide_text(design), encoding="utf-8")
    payload = folder / DOT_POINTS_NAME
    payload.write_text(
        json.dumps(dot_points_payload(design), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return [guide, payload]

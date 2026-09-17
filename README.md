# VCE Blitz

Generate a **Blitz** — a two-page, study-design-anchored revision sheet — from
your own VCE textbooks and Checkpoints PDFs.

Pick the dot points you want off the VCAA study design, pick the question types,
add a note about what you keep getting wrong, hit generate. You get two pages of
questions drawn from your books (diagrams cropped straight from the source page,
not redrawn) plus worked solutions on the back.

Currently set up for **VCE Business Management** and **VCE Physics**, Units 3 & 4.

## Status

Working end to end on the sample question bank. Two things are still stubs and
both need files only you can supply:

| Thing | State |
|---|---|
| Study designs | **Draft.** Reconstructed by hand, every dot point flagged `verified: false`. `blitz import-study-design` replaces them from the VCAA PDF. |
| Question corpus | **Sample only.** 54 questions written for this repo. `blitz ingest` builds the real index from your books. |

Until you import a real study design, every sheet prints an "unverified" banner
and marks the affected dot points with `*`. That is deliberate — a revision tool
that quietly invents syllabus wording is worse than no tool.

## Quick start

```bash
pip install -e .
blitz init          # create the index, load the sample bank
blitz serve         # http://127.0.0.1:8712
```

Or from the command line:

```bash
blitz generate physics \
    --aos physics-u3-aos1 --aos physics-u3-aos3 \
    --notes "impulse sign conventions and transformer turns ratios" \
    --title "Physics U3 Blitz"
```

## Loading your own material

Everything runs on your machine. Your PDFs, the index built from them and the
sheets it produces never leave it — there is no server and no upload. `sources/`
and `data/` are gitignored so licensed material can't be committed by accident.

**1. The study design** (free from vcaa.vic.edu.au):

```bash
blitz import-study-design sources/vcaa/physics-study-design.pdf --subject physics
```

This rewrites `blitz/studydesign/data/physics.yaml` with VCAA's own wording and
sets `verified: true`. Your question types and command terms are preserved.
Check the report it prints — anything it couldn't parse is named explicitly.

**2. Your books:**

```bash
blitz ingest sources/physics-checkpoints.pdf \
    --subject physics --source-id physics-checkpoints \
    --kind checkpoints --page-offset -2

blitz coverage physics        # see which dot points are thin
```

`--page-offset` is *printed page number minus PDF page index*, so citations show
the page number you'll actually find in the book. Find it by opening the PDF,
going to any numbered page and subtracting.

Ingestion tags each question against the study design. With `ANTHROPIC_API_KEY`
set and `pip install -e '.[tag]'`, it uses Claude for that pass, which is
substantially more accurate; otherwise it falls back to keyword matching. Either
way this is the **only** step that touches a model. Once the index is built,
generating sheets is fully offline and instant.

## How a sheet gets built

```
study design (YAML)          your PDFs
      │                          │
      │                     ingest: extract → segment → crop → tag
      │                          │
      └──────────┬───────────────┘
                 ▼
          SQLite index  ──  one row per question, linked to dot points
                 │
    your selection + question types + notes
                 ▼
            picker  ── fills a measured column-millimetre budget
                 ▼
           renderer  ── builds, measures, trims to exactly two pages
                 ▼
              Blitz PDF
```

The picker fills a budget measured in millimetres of column height rather than a
question count, because a 10-mark extended response and a multiple choice are
not interchangeable. It covers as many of your selected dot points as will fit
(breadth first), then spends what's left on depth, keeping the question types
you asked for balanced.

The notes box is not decoration: dot points your notes name are ranked first, so
when you select more than fits, the ones you said you're struggling with are the
ones that make the sheet.

The renderer then builds the document, measures the real page count and drops
questions off the end until it is two pages. Estimating flowable heights up
front is unreliable once cropped figures and ragged text are involved, and
building is cheap enough to just measure.

## What's on the sheet

- Two columns, 8.4pt, ruled writing space scaled to the marks on offer.
- A **dot-point checklist** in the masthead — exactly which parts of the study
  design this sheet covers, so it's auditable against VCAA rather than vibes.
- Citations under every question (`Checkpoints Physics, p. 142, Q7`).
- Diagrams cropped from the source page at ~216dpi.
- Worked solutions on their own pages, so the sheet prints as a clean two-pager.
- `°` on anything generated to fill a coverage gap, with a footer legend.

## Commands

| | |
|---|---|
| `blitz init` | create the index, load the sample bank |
| `blitz subjects` | subjects, dot point counts, verification status |
| `blitz ingest <pdf>` | index one of your books |
| `blitz coverage <subject>` | questions held per dot point |
| `blitz generate <subject>` | build a sheet |
| `blitz import-study-design <pdf>` | rebuild a subject from the VCAA PDF |
| `blitz serve` | local web UI |

## Adding a subject

Drop a YAML file in `blitz/studydesign/data/`. The schema is in
`blitz/studydesign/schema.py`; copy `physics.yaml` as a starting point. Question
types are per-subject on purpose — Physics is assessed on calculations and
graphs, Business Management on case studies and extended responses, and a shared
enum would serve neither.

## Tests

```bash
pip install -e '.[dev]'
python -m pytest
```

The ingest and importer tests build synthetic PDFs shaped like a Checkpoints
chapter and a VCAA study design, so the pipeline is exercised without any
licensed material in the repo.

## A note on your books

This tool reads PDFs you already own and produces a private study sheet for your
own use. It doesn't redistribute anything: the index and the crops live in
gitignored directories on your machine, and the sheets it makes cite the source
page. Don't publish or share the generated sheets — the crops in them are the
publisher's artwork.

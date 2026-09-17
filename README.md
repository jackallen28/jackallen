# VCE Blitz

Generate a **Blitz** — a two-page, study-design-anchored revision sheet — from
your own VCE textbooks and Checkpoints PDFs.

Pick the dot points you want off the VCAA study design, pick the question types,
add a note about what you keep getting wrong, hit generate. You get two pages of
questions drawn from your books (diagrams cropped straight from the source page,
not redrawn) plus worked solutions on the back.

Currently set up for **VCE Business Management** and **VCE Physics**, Units 3 & 4.

## Status

| Thing | State |
|---|---|
| Physics study design | **Imported from the VCAA PDF.** 71 dot points, VCAA's own wording. |
| Business Management study design | **Draft.** Reconstructed by hand, flagged `verified: false`. Send the PDF and `blitz import-study-design` replaces it. |
| Physics questions | Tested against a real Checkpoints extract: 73 questions, figures cropped, solutions attached. |
| Business Management questions | **Sample only** — 24 questions written for this repo. |
| Tagging | **The weak link.** See below. |

A subject whose study design is still a draft prints an "unverified" banner on
every sheet and marks the affected dot points with `*`. A revision tool that
quietly invents syllabus wording is worse than no tool.

### Tagging accuracy — read this before trusting a sheet

Filing each question under the right dot point is what makes the selection UI
mean anything, and the offline keyword tagger is not good at it. Measured
against a real Checkpoints extract (`python evals/tagging_eval.py <pdf>`),
scoring whether a question lands in the right *area of study*:

| | keyword tagger |
|---|---|
| coverage | 86% of questions tagged |
| precision, Unit 4 AOS 1 (photoelectric, matter waves) | **96%** |
| precision, Unit 3 AOS 1 (motion) | **27%** |
| precision, overall | 79% |

The overall figure flatters it. Photoelectric questions say "photon",
"de Broglie", "diffraction" — words that appear in the study design. Motion
questions say "car", "ball", "motorbike", "baseball player", which appear
nowhere in it. The study design describes concepts; questions describe
scenarios, and bag-of-words cannot bridge that.

So the keyword tagger is a fallback that gets the tool running offline, not a
serious tagger. **Set `ANTHROPIC_API_KEY` and `pip install -e '.[tag]'` before
ingesting a real book.** The model reads each question in context and is the
intended path; the eval harness scores it too (`--model`), though that has not
yet been run — this environment had no API key.

The tagger is deliberately conservative: a question it cannot place is left
untagged and reported, rather than filed somewhere plausible. A question under
the wrong dot point silently corrupts every sheet built from it.

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

## Two things the real books taught us

**PyMuPDF reads superscripts out of order.** In Checkpoints, the "⁻¹" in
"10 m s⁻¹" is set about 1.3pt above the baseline, so it lands on its own y-row
and is emitted *before* the sentence it belongs to: `10 m s⁻¹ at t = 2.6 s`
comes back as `10 m s at t = −1 2.6 s`. Physics questions are full of units, so
this corrupted nearly every one. `ingest/textflow.py` regroups spans into visual
lines by baseline proximity and re-attaches scripts at the x position they
actually occupy. Word spacing is positional too — "t = 4.9" is three spans
nudged apart with no space character anywhere — so gaps, not characters, decide
where spaces go.

**Some maths cannot be turned back into text at all.** A stacked fraction
extracts as "h" on one line and "p" on the next; the bar between them is drawn,
not typed, so nothing in the characters says it was ever a fraction. `λ = h/p`
flattens to `λ = hp`, and `E_k,max = hc/λ − W` to `Ekmax = hcλ − W` — wrong, and
confidently so. These are found by detecting the fraction bar (a short drawn
rule) and flagged `needs_crop`: the sheet shows an image of the real page
instead, and the text is kept only for search and tagging. In the sample
extract that was 2 questions and 22 worked solutions — a third of the
solutions. A mangled worked solution is worse than a mangled question, so
questions and solutions are checked and cropped independently.

## How a sheet gets built

```
study design (YAML)          your PDFs
      │                          │
      │            ingest: textflow → segment → crop → tag
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
chapter and a VCAA study design — including the superscript, positional-spacing
and stacked-fraction traps found in the real files — so the pipeline is
exercised without any licensed material in the repo.

`evals/tagging_eval.py` scores tagging against a real Checkpoints PDF. Ground
truth comes from the book itself: Checkpoints prints the page each question sits
on ("Question 12/ 11") and pages cluster by chapter, so page numbers map onto
areas of study with no hand-annotation to drift.

### A note on dot point ids

Dot point ids are positional (`physics-u3-aos1-kk03`), so re-importing a study
design can leave every id valid while changing what it means. This bit once: after
the real VCAA Physics design was imported, a cricket-ball impulse question was
still "valid" but now pointed at satellite motion, and nothing raised. The
sample banks now record a fingerprint of the design they were written against
and refuse to load against a different one.

## A note on your books

This tool reads PDFs you already own and produces a private study sheet for your
own use. It doesn't redistribute anything: the index and the crops live in
gitignored directories on your machine, and the sheets it makes cite the source
page. Don't publish or share the generated sheets — the crops in them are the
publisher's artwork.

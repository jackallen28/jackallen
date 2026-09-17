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
| Physics questions | Tested against a real Checkpoints extract: 70 questions, figures cropped, solutions attached. |
| Physics concept lexicon | Written, covering all 71 dot points. |
| Business Management questions | **Sample only** — 24 questions written for this repo. |
| Tagging | **The weak link.** See below. |

A subject whose study design is still a draft prints an "unverified" banner on
every sheet and marks the affected dot points with `*`. A revision tool that
quietly invents syllabus wording is worse than no tool.

### Tagging accuracy

Filing each question under the right dot point is what makes the selection UI
mean anything. Two labelled sets, both scored by `evals/tagging_eval.py`:

| | Checkpoints sample (area level) | held-out sample bank (dot point level) |
|---|---|---|
| coverage | 94% tagged | 100% tagged |
| precision | **99%** right area | **90%** exact dot point, 97% right area |

Ground truth for the first comes from the book itself — Checkpoints prints the
page each question sits on and pages cluster by chapter, so page numbers map
onto areas of study with no hand-annotation. The second is the sample bank,
whose dot points were assigned by hand before any of this tuning existed.

It started at 79% overall and **27% on motion questions**. The study design
describes concepts ("investigate and apply Newton's three laws of motion");
questions describe scenarios ("a speeding motorbike travels past a stationary
police car"). Nothing useful overlaps, and what does overlap actively misleads:
"motion" also appears in "motion approaching the speed of light", so kinematics
questions landed under special relativity.

The fix is `blitz/studydesign/data/physics-lexicon.yaml` — a hand-written
concept lexicon giving each dot point the vocabulary a question about it
actually uses, plus `requires`/`avoid` vetoes and weights to break ties. See
`blitz/ingest/lexicon.py`. Business Management has no lexicon yet, so it falls
back on IDF-weighted word overlap, which is much weaker.

**Both sets have now informed tuning**, so neither is a clean held-out
measurement any more. The next honest number needs a book neither has seen —
worth running when the full Checkpoints is ingested.

The tagger is deliberately conservative: a question it cannot place is left
untagged and reported rather than filed somewhere plausible, because a question
under the wrong dot point silently corrupts every sheet built from it.

**A model tagger is still the intended path for a full book.** Set
`ANTHROPIC_API_KEY` and `pip install -e '.[tag]'`. It has not been measured —
this environment had no key — so no claim is made about it.

### What else was measured on the real book

| | |
|---|---|
| questions found in a 54-page sample | 70 |
| multiple choice classified correctly | 29/29, no false positives |
| questions whose figure was found | 23 of 25 that mention one |
| worked solutions needing a page crop | 23 (a third — stacked maths) |

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

## Three things the real books taught us

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

**A shared stimulus is printed above its question, not with it.** Checkpoints
puts the lead-in sentence and the figure *above* the rule that fences the
question, often with a question number of their own:

```
"The speed-time graph below describes the motion of an object."   <- stimulus
[graph]
--------------------------------------------------------------- rule
Question 10/ 11
Which one best describes the motion at t = 5 s?
```

So the stimulus arrives attached to the *previous* question, and the figure
sits in the preceding fence. Segmenting on the header alone indexed the
stimulus as an unanswerable question of its own and missed 9 of 23 figures —
every graph question in the sample. Stimulus-only blocks are now folded into
the question they introduce, and the figure search widens into the fence above.

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

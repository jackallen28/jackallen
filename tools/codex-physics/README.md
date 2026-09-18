# Codex's Physics textbook extractor

These are the scripts another model wrote, working directly against a licensed
Jacaranda-style VCE Physics textbook, before it ran out of credits. They are
kept **as received and unmodified** — they are evidence, not a supported part of
Blitz. Nothing here is imported by `blitz/`, and nothing here runs in CI.

They are worth keeping for one reason: they were written with the real book in
front of them, and every constant in them is a measurement of it. That is what
tuned `blitz/ingest/textbook.py` — the heading vocabulary ("Sample problem",
"Revision question"), the fact that a revision prompt is set in semibold while
the prose around it is not, and the page geometry of a two-column review
section.

## The pipeline

| Script | What it does |
| --- | --- |
| `cache_physics.py` | Reads the PDF once with pdfplumber and pickles every char and drawing object per page. Everything downstream works off the pickle, so the slow parse happens once. |
| `extract_physics.py` | Finds the questions. Rebuilds lines from raw chars (so superscripts and subscripts survive), groups connected drawing objects into figures, and walks the two-column review sections by their number glyphs. |
| `physics_support.py` | Pulls the answer section at the back of the book and the prompt of each worked example. |
| `physics_tags.py` | The dot-point tag chosen for each question, written out by hand after reading them. |
| `physics_edits.py` | Hand-written corrections: context a question needs, figure boxes the geometry missed, dependencies between questions. **Not in the repo** — see below. |

## Why `physics_edits.py` is missing

It holds question text transcribed from the book. Licensed material does not go
into this repository, the same rule that keeps `sources/` out. It is listed in
`.gitignore`; if you have it, drop it in this folder and the scripts will find
it.

## Running them

They were written against one machine and one book, and it shows:

* `cache_physics.py` has the book's path hardcoded at line 4. Edit it.
* `extract_physics.py` has `CHSTART` and `REVIEW` — the PDF page index each
  chapter and each review section begins on, and the constant 13 is the offset
  between PDF page and printed page number. All of it is specific to that one
  edition. A different printing moves every number.

So this is not a tool you point at a new book. **Blitz's own indexer is.** What
these scripts gave Blitz is the knowledge of what a real book looks like, and
that now lives in `blitz/ingest/textbook.py` with tests behind it.

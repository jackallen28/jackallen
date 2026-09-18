# Indexing a book

One command takes a study design and a book and builds the index Blitz draws
sheets from. No model, no network, no account. A 1000-page book takes about a
minute on a laptop.

```bash
blitz index sources/physics-textbook.pdf \
    --subject physics \
    --study-design sources/vcaa/physics-study-design.pdf \
    --title "Heinemann Physics 12"
```

Then:

```bash
blitz coverage physics     # what each dot point now has behind it
blitz serve                # http://127.0.0.1:8712
```

## What it does

1. **Imports the study design**, if you pass one. That replaces the subject's
   dot points with VCAA's own wording and records a fingerprint so nothing
   built against an older version can be mistaken for current. You only need
   to do this once per subject; leave `--study-design` off after that.

2. **Works out what kind of book it is** by sampling pages: a Checkpoints book
   ("Question 12/ 11" on every question), a textbook (chapters, section
   headings, worked examples, review questions), or an exam paper. Each needs a
   different extractor, and guessing wrong produces confident garbage, so it
   tells you what it decided and `--kind` overrides it.

3. **Extracts every question** — stem, parts, options, marks, worked solution
   where the book prints one — and crops any diagram straight from the page.
   Where the text cannot be trusted (stacked fractions, equation-editor
   glyphs) it crops the whole question instead and uses the text only for
   search.

4. **Indexes the teaching content**, section by section. A textbook is half
   prose, and a sheet that can send a student to "6.3 The photoelectric effect,
   p. 142" is worth more than one that only tests them. Sections are found by
   typography — a short line set larger than the body text — so no contents
   page is needed.

5. **Tags all of it to the study design**, questions and sections alike, using
   the subject's concept lexicon. Anything it cannot place is left untagged
   and reported, never filed somewhere plausible.

## Reading the report

```
heinemann-physics-12: 412 pages, detected as textbook (auto: textbook (92%; …))
  study design: VCE Physics (verified)
  questions: 618 found, 571 indexed, 47 untagged
             203 with figures, 84 with solutions, 61 as page crops
  content  : 96 sections found, 91 indexed, 5 untagged
  47 item(s) to review:
      · untagged question p.38: Which one of the following is closest…
```

"Untagged" means the lexicon found nothing distinctive to hang it on. Those are
the items worth a human's eye; everything indexed is selectable straight away.

## Word files

A `.docx` goes through the same command. It is rendered to a PDF first, under
`data/converted/`, with headings set larger than the body, Word's automatic
list numbering made visible ("1.", "a.", "•") and images placed inline, and
that PDF is then indexed like any other book. Superscripts set in Word come
through as text (`m s⁻¹`). Page numbers in citations are the rendered PDF's.
The study design importer reads `.docx` directly.

## Kinds of book

| kind | what it looks for | status |
|---|---|---|
| `checkpoints` | `Question N/ P` headers, `Solution` blocks, VCAA provenance tags | tuned against a real extract |
| `textbook` | section headings by font size; `Worked example`, `Questions`, `Chapter review` blocks; numbered items | **built against synthetic pages — needs a real textbook to tune** |
| `exam` | `SECTION A`, `Question 3 (4 marks)` | detected; uses the textbook extractor for now |

The textbook extractor's heading vocabulary is in `blitz/ingest/textbook.py`
(`QUESTION_BLOCK`, `WORKED_EXAMPLE`). Different publishers use different words;
that list is the first thing to extend when a real book turns out to say
"Check your learning" or "Exam-style questions".

## Options

| | |
|---|---|
| `--kind` | `auto` (default), `checkpoints`, `textbook`, `exam` |
| `--page-offset` | printed page number minus PDF index, for citations |
| `--first-page` / `--last-page` | index a range, e.g. one chapter |
| `--no-content` | questions only |
| `--source-id` | stable id; re-indexing the same id updates in place |

## Importing a pack instead

If a model has already indexed the book into a pack (`docs/question-pack-schema.md`),
`blitz import-pack` is the way in, and it does one thing a pack usually needs:
it **refines chapter-level tags**. A model tags by chapter — every question in
"Circular motion" gets the same three dot points — so the importer keeps the
chapter's area of study as given and lets the lexicon pick the dot point(s)
the question's own text names, adding a dot point from the same area only when
the pack left it empty and the evidence is strong. The report says what it did:

```
tags refined: 397 narrowed to the dot point the text names, 23 extended to a
dot point the pack left empty; 40 -> 51 dot points covered
```

`--keep-pack-tags` turns that off and files everything exactly as the pack says.

## What it is not

It is not a substitute for a curated pack. If someone has already been through
the book deciding where every question starts and what it assesses, that pack
beats this on every axis — see `docs/question-pack-schema.md`. `blitz index` is
for the case where nobody has, and you want a usable index in a minute rather
than a perfect one in a week. `blitz extract-pack` does the same work but emits
the draft as a pack for review instead of writing it straight to the index.

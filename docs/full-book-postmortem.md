# The full-book run: what went wrong, and what the next one should do

The whole Checkpoints Physics book (1000 pages) was indexed by a model into a
question pack and handed to Blitz as five zips: 841 questions, 1273 figure
crops, 838 worked solutions. The pack validated with zero errors and imported
in seconds. It then produced sheets with **one question on two pages**, half
the dot points had nothing behind them, and every crop was drawn at the wrong
size.

None of that was one bug. This is the list, ranked by how much it cost, with
what Blitz now does about each and what a future indexing run should do
instead. The last section is the checklist to hand to whatever does the next
book.

---

## 1. Tags were per chapter, not per question

**What happened.** Every question in a chapter carried the same two or three
dot points. 841 questions, **21 distinct tag sets**, one per chapter. Dot
points no chapter is named after got nothing: **31 of 71 were empty**,
including *proper time*, *proper length*, the Michelson-Morley experiment,
E = mc², DC generators, photovoltaic cells and satellite motion. Meanwhile
"Newton's three laws" carried two whole chapters (71 questions).

**Why it matters.** The dot-point picker in the UI is the product. A sheet on
"proper time" had nothing to draw on; a sheet on "impulse" got every question
in the collisions chapter, impulse or not.

**What Blitz does now.** The importer treats the pack's tags as fixing the
*area of study* (the chapter is reliable for that) and lets the concept
lexicon choose the dot point within it: it narrows the chapter's set to the
dot point(s) the question's own text names, and adds a dot point from the same
area only when the pack never used it at all and the evidence is a phrase, not
a word. Result: 397 narrowed, 23 extended, **40 → 51 dot points covered**.
Twenty are still empty — mostly ones no question in the book literally names
("proper time" questions say "measured in the muon's frame").

**Next time.** Tag each question individually, against the list from
`blitz dot-points physics --json`, with a one-line reason per tag. Use the
chapter to *constrain* the choice, not to make it. Every dot point in the
chapter's area of study is a candidate, not just the ones the chapter title
suggests. A question can have one tag; it rarely needs three.

## 2. Three-quarters of the book was marked "crop"

**What happened.** 639 of 841 questions (76%) had `render_mode: crop`,
including 67 of 68 graph questions and 160 of 208 multi-step questions. Only
202 could be printed as text.

**Why it matters.** Text reflows into two columns and a page holds ten to
twelve questions; a page crop is drawn as an image and a page holds two or
three. Crop mode is the right call when the maths cannot be reconstructed
(stacked fractions, equation-editor glyphs). It is the wrong call for a
question whose only "maths" is 10 m s⁻¹, and for a question whose figure could
have been cropped on its own and printed under reflowed text.

**What Blitz does now.** The sheet is a mixed layout: two columns of text
questions on page one, one full-width column of page crops on page two, worked
solutions after. Which questions go where is decided per sheet by measuring
each crop against the column width — a crop that would land under 62% of book
size is never put in a column. Crops are drawn at 80% of book size, which
matches the sheet's own type and fits a third question on the crop page.

**Next time.** Crop the question only when the reconstructed text is actually
unfaithful. Test: does the text contain a stacked fraction, a root sign with a
vinculum, a matrix, or a symbol the extractor mangled? Superscripts, units,
Greek letters and inline fractions with a slash are text. A diagram is a
`figure` (crop the diagram alone, `role: question`), not a reason to crop the
words around it. The pilot's line-reconstruction notes
(`docs/feedback-to-codex.md`) still apply: fix the extraction and most of
these become text.

## 3. Nobody said what size the crops were

**What happened.** The PNGs carry no DPI. The pack did not say what zoom they
were rendered at. The README did not either. They were rendered at **3 pixels
per point**; Blitz, reading them through PyMuPDF, which reports an image's size
in points at an assumed 96 dpi (pixels × 0.75), concluded the zoom was 2.25 and
that a 532-point-wide crop was 1197 points wide — wider than an A4 page. Two
errors cancelled for a while, which is worse than one.

**Why it matters.** Every layout decision — one column or two, how tall a crop
is, whether three fit on a page — starts from the crop's real width.

**What Blitz does now.** Image sizes are read as pixels, never through PyMuPDF.
The pack schema has `source.figure_zoom` (pixels per point, once per pack) and
per-figure `pt_width`; the importer warns when file figures carry neither.

**Next time.** Put `"figure_zoom": 3` in `source`. Better: keep `page` + `bbox`
figures in the pack (the non-portable variant already has them) so Blitz crops
from the PDF at import and the width is exact. The portable pack is for a
machine without the PDF; on the machine that has it, bbox wins on every axis.

## 4. Crops were full-page-width bands

**What happened.** The median question crop was 532 points wide on a 595-point
page: the text block from margin to margin, including the blank right-hand
third of every short line. Heights ran to 945 points — a whole page in one
image, sometimes as three stacked images for one question.

**Why it matters.** A crop is only legible in a column if it is narrow. A
diagram that is 200 points wide, cropped as a 532-point band, forces single
column for no reason. A whole-page crop turns one question into a page.

**Next time.** Crop to the content's bounding box, not the text block. Split a
multi-part question into one crop per part when the whole runs past about 250
points tall; Blitz stacks the `figures[]` in order. Never include the book's
own blank answer space. A crop that contains only a provenance line
("[VCAA 2018 SB Q2]") is wasted — that belongs in `provenance`.

## 5. Marks were printed inside the stem

171 stems ended in "(3 marks)" while `marks: 3` was also set, so every one of
those printed its marks twice. The importer now strips a trailing "(N marks)"
from stems and parts, and takes N as the marks if nothing else says.
**Next time:** the stem is the question; marks go in `marks`.

## 6. Everything was a draft flagged for review

All 841 questions came with `status: draft` and a `review` note, so nothing
was verified and the sheet's "unverified" marker meant nothing. **Next time:**
`approved` for rows the run is confident in, `review` only for real doubts (a
boundary it could not place, a figure it could not find). A review list of
841 is not a review list.

## 7. Context and dependencies were mostly absent

The schema has `context` (a scenario printed above a run of questions) and
`depends_on` (an earlier question this one needs). A spring question that
opens "Assuming that the spring has no mass" arrived without the scenario it
refers to. **Next time:** when a question's stem does not stand alone, copy
the shared stimulus into `context`; when it says "using your answer to
question 3", set `depends_on`.

---

## What went wrong on Blitz's side

Being honest about the other half. Every one of these was found only because a
real book arrived; the sample and the pilot were too small and too clean.

| defect | effect | fix |
|---|---|---|
| Page two of questions reserved the masthead's space and left it blank | 13% of the sheet empty | switch to the full-height template after page one |
| Multi-part questions got ruled answer space per part *and* again in full | estimates missed by 2× | share the allowance across parts |
| Heights were estimated from character counts | one question per page, or two dropped while half a page sat empty | build the question's flowables and measure them; picker and renderer use the same number |
| Column count decided on the candidate pool, sheet laid out on the chosen set | picker budgeted one column, renderer drew two: half of every page empty | decide on the chosen set; pin it on the plan |
| "Has a figure" bonus paid to crops cancelled the crop penalty | crops beat text on every dot point | a crop is a rendering mode, not a diagram |
| Image size read via PyMuPDF (pixels × 0.75) | every crop width wrong by a quarter | read pixels with PIL |
| A small crop was drawn at its pixel size | a 110-point diagram stretched across the column | never exceed the region's real width |
| `compare alternating` shortened to "Lternating" | a dot point mislabelled in the UI and on sheets | the article-stripping regex needed a word boundary |

The lesson is not any one of these. It is that a layout engine has to be
tested against the real corpus, not a fixture that fits, and that the picker
and the renderer must share one measurement. They do now: `measure_question_mm`
is the only height in the system.

## The tagger, measured honestly

The concept lexicon had never seen this book. Scored against each question's
chapter (a chapter sits in one area of study), `evals/tagging_eval.py --pack`:

| | before this run's tuning | after |
|---|---|---|
| tagged | 96% | 96% |
| right area of study | 81% | 83% |
| motion / fields / electricity / light / investigation | 91 / 67 / 89 / 83 / 53% | 91 / 74 / 90 / 84 / 53% |

A third of the misses were fields questions (satellites, charged plates,
Millikan) filed under "Newton's three laws", whose vocabulary is every
mechanics question's vocabulary. That dot point now refuses anything set in a
field. Investigation-skills questions (53%) are hard by nature: a question
about uncertainty in an EMF experiment is, by vocabulary, an EMF question.

This is why the importer trusts the pack's chapter for the area of study and
uses the lexicon only within it. The two together are better than either.

---

## Checklist for the next model run

Give this to whatever indexes the next book. Every item is checkable with
`blitz import-pack <pack> --dry-run` or by reading the report.

1. **One question, its own tags.** Tag against `blitz dot-points <subject>
   --json`. Use the chapter to constrain, never to decide. One tag is normal;
   three is suspicious. Give a one-line reason per tag in `notes`.
2. **Text unless the maths is unreconstructable.** `render_mode: crop` only
   for stacked fractions, roots with a vinculum, matrices, mangled symbols.
   Diagrams are `figures`, not a reason to crop the words.
3. **Say the scale.** `source.figure_zoom` for file figures, or ship
   `page` + `bbox` and let Blitz crop. Never leave a PNG's size to be guessed.
4. **Crop to content.** Bounding box of the ink, not the text block. Split a
   question taller than ~250 pt into per-part crops. No blank answer space, no
   provenance-only crops.
5. **Marks in `marks`, not in the stem.** Strip "(N marks)" from text.
6. **`context` and `depends_on`** whenever a stem does not stand alone.
7. **`approved` by default,** `review` only with a concrete reason. The
   report's "flagged for review" count should be the count of real doubts.
8. **Solutions as text where possible**, same rule as questions. 838 of 841
   solutions being crops means the solutions page is images.
9. **Run the dry run before shipping.** Zero errors is the floor; read the
   warnings.
10. **Include the study design fingerprint** (`blitz dot-points` prints it).
    Dot point ids are positional; a pack against last year's design imports
    into the wrong dot points without a word of complaint unless this matches.

What the run got right is worth keeping: stable ids, every figure in order
with a role, VCAA provenance on every question the book attributes, clean
JSON that validated first time, and a portable variant for a machine without
the PDF. The structure was sound. The judgement calls inside it were not.

# Question pack schema (v1)

A **question pack** is the structured index of one book. It is the preferred way
to get questions into Blitz: a curated pack beats the heuristic PDF extractor in
`blitz/ingest/`, which exists for when no pack is available.

Hand Blitz the JSON, not a rendered PDF. A pack rendered to PDF and parsed back
loses exactly what makes it valuable — `m s⁻²` flattens to `m s-2`, stacked
fractions collapse, question boundaries have to be re-guessed. If you already
have the structure, don't make the tool rediscover it.

```bash
blitz import-pack packs/physics-checkpoints.json
blitz coverage physics
```

## Top level

```jsonc
{
  "pack_version": "1.0",
  "subject_id": "physics",              // must match a study design in Blitz
  "study_design_fingerprint": "750fe79e5aba",   // optional but recommended
  "source": { ... },
  "questions": [ ... ]
}
```

`study_design_fingerprint` guards against dot point ids drifting. Dot point ids
are positional (`physics-u3-aos1-kk03`), so re-importing a study design can
leave every id valid while changing what it means. Get the current value from:

```bash
blitz dot-points physics --json    # ids, text, and the fingerprint
```

Feed that file to whatever is building the pack — it is the authoritative list
of ids to tag against.

## `source`

```jsonc
{
  "id": "physics-checkpoints-2024",    // stable; re-importing updates in place
  "kind": "checkpoints",               // checkpoints | textbook | vcaa-exam | other
  "title": "Checkpoints VCE Physics Units 3 & 4",
  "edition": "2024",
  "pdf": "sources/physics-checkpoints.pdf",  // optional: enables bbox figures
  "page_offset": 0
}
```

`pdf` is a path on the machine running the import. It is only needed if any
figure uses `page`/`bbox` (see below). It is never copied into the repo.

## `questions[]`

```jsonc
{
  "id": "CP-T001",                     // stable across re-runs; required
  "title": "Motion of connected masses",        // optional, shown in listings
  "provenance": "Adapted VCAA 2018 NHT SA Q8",  // printed on the sheet
  "printed_page": "11",                // the page number IN THE BOOK
  "source_number": "14",               // the question number in the book

  "kk_ids": ["physics-u3-aos1-kk01"],  // study design dot points, best first
  "question_type": "ph-mc",            // an id from the subject's question_types
  "marks": 1,
  "difficulty": 3,                     // 1 recall .. 5 hardest exam standard

  "stem": "A 1.0 kg mass attached to a string hangs 4.0 m from the ground...",
  "parts": [
    {"label": "a", "text": "Calculate the speed on impact.", "marks": 2}
  ],
  "options": ["2.0 m s⁻¹", "4.0 m s⁻¹", "8.0 m s⁻¹", "16 m s⁻¹"],

  "answer": {
    "text": "B. Using conservation of energy...",
    "parts": [{"label": "a", "text": "..."}]
  },

  "figures": [
    {"role": "question", "page": 41, "bbox": [72, 300, 400, 520],
     "caption": "Apparatus for the photoelectric experiment"},
    {"role": "answer", "file": "figures/CP-T002-answer.png"}
  ],

  "context": "A ball is thrown directly upwards at 25 m s\u207b\u00b9. Neglect air resistance in the following three questions.",
  "depends_on": ["CP-T001"],           // ids in THIS pack, resolved at import
  "status": "draft",                   // approved | draft | needs-review
  "review": ["curriculum tag needs subject review"],

  "render_mode": "text",               // "crop" if the text can't be trusted
  "answer_mode": "text",
  "notes": "Source answer not supplied; no answer generated."
}
```

### Shared context and dependencies

Checkpoints sets runs of questions against one scenario, and questions that
read "using your answer from part a". Both have to survive onto the sheet or
the question is unanswerable.

- **`context`** is the scenario printed above the question. Blitz stores it
  separately from `stem` and prints it above the question, so a question is
  never separated from what it is about. Repeat it on each question in the run;
  Blitz shows it once per question rather than assuming adjacency.
- **`depends_on`** lists ids of questions in this pack that must accompany this
  one. When the picker selects a question with dependencies, it pulls the
  prerequisites onto the sheet too, ahead of it. Ids that do not resolve within
  the pack are a validation error.

In crop mode the same job can be done by putting the context or the earlier
question in as an extra `question` figure, ahead of the question's own — which
works, and is what the pilot pack does. Prefer the structured fields where the
text is being used, since they let Blitz lay the sheet out rather than fixing
the arrangement into an image.

### Review state

A pack is trusted more than heuristic extraction: its rows land `verified` and
its tags are taken as given. Curated is not the same as checked, so say which
this is.

- **`status`** — `approved` (default), `draft` or `needs-review`, settable per
  question or once at the top level for the whole pack.
- **`review`** — a list of what still needs a human on this question.

Anything not `approved`, or carrying any `review` entry, lands unverified.
Marking unreviewed curriculum tags "verified" would put a confidence on the
sheet that nobody has earned.

### Required

`id`, and one of `stem` or `parts`. Everything else is optional — a pack with
only text still works, it just has less to select on.

### Notation

Use **real Unicode** in text: `m s⁻²`, `λ`, `Δ`, `×`, `≈`, `10⁻¹⁹`. Do not
flatten to `m s-2` — Blitz renders with a Unicode font and re-derives
superscripts for fallback fonts, so the correct characters survive to the page.
Never use LaTeX or MathML; nothing downstream renders it.

### Figures

Two forms, both optional, mixable:

- **`page` + `bbox`** — a rectangle in the source PDF, in PDF points, origin at
  the top-left of the page, `[x0, y0, x1, y1]`. `page` is 0-based. Blitz crops
  it at ~216dpi at import. **Prefer this**: it keeps full resolution, and the
  crop can be redone later without re-running the pack.
- **`file`** — a path to an image, relative to the pack file. Copied in at
  import.

`role` is `"question"` (default) or `"answer"`.

**A question may have as many figures as it needs, and order matters.** They are
rendered in the order given, so put a shared scenario or a required earlier
question *before* the question that depends on it, exactly as the book prints
them:

```jsonc
"figures": [
  {"role": "question", "page": 40, "bbox": [...], "caption": "Shared context"},
  {"role": "question", "page": 41, "bbox": [...], "caption": "Source question"},
  {"role": "answer",   "page": 543, "bbox": [...], "caption": "Source answer"}
]
```

Blitz stacks every `question` figure into the question and every `answer` figure
into the worked solution, and budgets the page for all of them. A question that
runs onto a second page, or that only makes sense after the scenario above it,
is carried whole — which is the point: a question whose context is dropped is
unanswerable.

### When the text cannot be trusted

Some maths cannot survive extraction at all. A stacked fraction is `h` on one
line and `p` on the next, with the bar drawn rather than typed — `λ = h/p`
flattens to `λ = hp`, which is wrong and looks right. If you cannot faithfully
represent a question or its solution as text, set `render_mode` (or
`answer_mode`) to `"crop"` and give a figure with `role` `"question"` (or
`"answer"`) covering the whole region. Blitz then prints the page image and uses
the text only for search and tagging.

This is the single most useful thing a pack can do that the extractor cannot:
decide, per question, whether the text is trustworthy.

### Honest gaps

Leave `answer` out entirely when the book supplies none. **Do not generate one.**
Blitz prints "no worked solution in the source — check the book at the citation"
and the student knows where they stand. Use `notes` to record why, as the sample
packs do ("Source answer not supplied; no answer generated"), and to record any
editorial change to the wording. `notes` is carried into the database and shown
when reviewing the index.

## Validation

```bash
blitz import-pack packs/physics.json --dry-run
```

Reports unknown dot point ids, unknown question types, duplicate ids, missing
figure files, out-of-range bboxes and fingerprint mismatches. Nothing is written
unless the pack is clean, so a bad pack can't half-load.

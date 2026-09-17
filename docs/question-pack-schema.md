# Question pack schema (v1)

A **question pack** is the structured index of one book. It is the preferred way
to get questions into Blitz: a curated pack beats the heuristic PDF extractor,
because whoever built it had the book in front of them.

- Machine-readable: **`docs/question-pack.schema.json`** (JSON Schema 2020-12)
- Working example: **`packs/example-physics.json`**
- Validate: `blitz import-pack <file> --dry-run`

Hand Blitz the JSON, not a rendered PDF of it. A pack rendered to PDF and parsed
back loses exactly what makes it valuable — `m s⁻²` flattens to `m s-2`, stacked
fractions collapse, question boundaries have to be re-guessed.

```bash
blitz dot-points physics --json > physics-dot-points.json   # ids to tag against
blitz import-pack packs/physics.json --dry-run              # validate
blitz import-pack packs/physics.json                        # load
```

---

## Top level

| field | type | required | notes |
|---|---|---|---|
| `pack_version` | string | no | `"1.0"`. Major version must match the importer. |
| `subject_id` | string | **yes** | Must match an installed study design: `physics`, `business-management`. |
| `study_design_fingerprint` | string | recommended | From `blitz dot-points`. Mismatch is a hard error; absence warns. |
| `status` | enum | no | `approved` (default) \| `draft` \| `needs-review`. Default for every question. |
| `source` | object | **yes** | See below. |
| `questions` | array | **yes** | At least one. |

Dot point ids are **positional** (`physics-u3-aos1-kk03`), so re-importing a
study design can leave every id valid while changing what it means. The
fingerprint is what catches that. Re-check it before every run.

## `source`

| field | type | required | notes |
|---|---|---|---|
| `id` | string | **yes** | Stable across re-imports. Namespaces question ids and `depends_on`. |
| `kind` | enum | no | `checkpoints` \| `textbook` \| `vcaa-exam` \| `other`. |
| `title` | string | no | Printed in the citation under every question. |
| `edition` | string | no | |
| `pdf` | string | if bbox used | Path on the importing machine. Never copied into the repo. |
| `page_offset` | integer | no | Printed page minus PDF index. Only used when a question has no `printed_page`. |
| `figure_zoom` | number | if `file` figures | Pixels per PDF point the image files were rendered at (0.5–8). Ignored for `page`+`bbox` figures. |

## `questions[]`

### Identity and provenance

| field | type | required | notes |
|---|---|---|---|
| `id` | string | **yes** | Unique in the pack, stable across re-runs. Stored as `<source.id>-<id>`. |
| `title` | string | no | Short label for listings. Not printed on sheets. |
| `provenance` | string | no | Printed in the citation in brackets: `[VCAA 2019 SA Q14]`. |
| `printed_page` | string | no | Page number **as printed in the book**, not the PDF index. |
| `source_number` | string | no | Question number as printed in the book. |

### Classification

| field | type | required | notes |
|---|---|---|---|
| `kk_ids` | string[] | strongly | Dot points assessed, best first. **Taken as given** — the tagger is not consulted. Empty imports but can never be selected. |
| `question_type` | string | no | An id from the subject's `question_types`. |
| `marks` | integer | no | Total. Summed from `parts[].marks` if omitted. |
| `difficulty` | integer 1–5 | no | 1 recall … 5 hardest. **Omit rather than guess.** |

### Content

| field | type | required | notes |
|---|---|---|---|
| `stem` | string | one of | The question, or the lead-in to its parts. |
| `parts` | object[] | one of | `{label, text, marks}`. Printed on their own lines with their own ruled space. |
| `options` | string[] | no | Multiple choice, in order, **without** the leading `A ` / `B `. |
| `answer` | string \| object | no | `{text, parts[]}`. **Omit entirely where the book has none.** |
| `context` | string | no | The scenario this question is set in. |
| `depends_on` | string[] | no | Ids in this pack this question needs. |
| `figures` | object[] | no | Every figure, in order. |

### Rendering and review

| field | type | required | notes |
|---|---|---|---|
| `render_mode` | enum | no | `text` (default) \| `crop`. `crop` needs a `question` figure. |
| `answer_mode` | enum | no | `text` (default) \| `crop`. `crop` needs an `answer` figure. Judge independently. |
| `status` | enum | no | Overrides the pack default. |
| `review` | string[] | no | What still needs a human. Any entry makes the row unverified. |
| `notes` | string | no | Editorial record. Kept with the row. |

### `figures[]`

| field | type | required | notes |
|---|---|---|---|
| `role` | enum | no | `question` (default) \| `answer`. |
| `page` | integer | with `bbox` | **0-based** index into `source.pdf`. |
| `bbox` | number[4] | with `page` | `[x0, y0, x1, y1]` in PDF points, origin **top-left**. |
| `file` | string | alternative | Path to an image, relative to the pack file. |
| `caption` | string | no | Printed under the figure when a question has more than one. |
| `pt_width` | number | no | Width of the cropped region in PDF points, for `file` figures. Overrides `source.figure_zoom`. |

Exactly one of `page`+`bbox` or `file`. Prefer `page`+`bbox`: it keeps full
resolution and the crop can be redone later without re-running the pack.

---

## Example record

Every field, on one question:

```json
{
  "pack_version": "1.0",
  "subject_id": "physics",
  "study_design_fingerprint": "750fe79e5aba",
  "status": "draft",

  "source": {
    "id": "physics-checkpoints-2024",
    "kind": "checkpoints",
    "title": "Checkpoints VCE Physics Units 3 & 4",
    "edition": "2024",
    "pdf": "/Users/jack/Documents/VCE_Physics_3_4_Checkpoints.pdf",
    "page_offset": 0
  },

  "questions": [
    {
      "id": "CP-C01-S11-Q005",
      "title": "Ball thrown upwards — initial speed",
      "printed_page": "11",
      "source_number": "5",
      "kk_ids": ["physics-u3-aos1-kk05"],
      "question_type": "ph-calculation",
      "marks": 2,
      "context": "A ball is thrown directly upwards with an initial speed of 25 m s⁻¹. Neglect air resistance in the following three questions.",
      "stem": "Calculate the speed of the ball 1.5 s after it is released.",
      "answer": { "text": "v = u − gt = 25 − 9.8 × 1.5 = 10.3 m s⁻¹ upwards." },
      "status": "draft"
    },
    {
      "id": "CP-C01-S11-Q006",
      "title": "Ball thrown vertically upwards",
      "provenance": "Adapted VCAA 2018 NHT SA Q8",
      "printed_page": "11",
      "source_number": "6",

      "kk_ids": ["physics-u3-aos1-kk05", "physics-u3-aos1-kk09"],
      "question_type": "ph-multi-step",
      "marks": 5,
      "difficulty": 4,

      "context": "A ball is thrown directly upwards with an initial speed of 25 m s⁻¹. Neglect air resistance in the following three questions.",
      "depends_on": ["CP-C01-S11-Q005"],

      "stem": "The ball is caught at the height from which it was thrown.",
      "parts": [
        { "label": "a", "text": "Calculate the maximum height reached.", "marks": 3 },
        { "label": "b", "text": "Determine the total time of flight.", "marks": 2 }
      ],

      "answer": {
        "parts": [
          { "label": "a", "text": "v² = u² − 2gh with v = 0 gives h = 25²/(2 × 9.8) = 31.9 m." },
          { "label": "b", "text": "t = 2u/g = 2 × 25/9.8 = 5.1 s." }
        ]
      },

      "figures": [
        {
          "role": "question",
          "page": 5,
          "bbox": [42.0, 526.2, 565.3, 612.8],
          "caption": "Shared context"
        },
        {
          "role": "answer",
          "page": 543,
          "bbox": [42.0, 305.8, 565.3, 330.7],
          "caption": "Source answer"
        }
      ],

      "render_mode": "text",
      "answer_mode": "crop",

      "status": "draft",
      "review": ["curriculum tag needs subject review"],
      "notes": "Source answer uses a stacked fraction, so the solution is shown as a page crop. Question wording: added missing 'to' before 'determine'."
    }
  ]
}
```

A minimal valid record is just `{"id": "...", "stem": "..."}` — everything else
is optional. It will import, and never be selected, because it has no dot points.

---

## The parts that need explaining

### Notation

Use **real Unicode**: `m s⁻²`, `10⁻¹⁹`, `λ`, `Δ`, `Φ`, `θ`, `×`, `≈`, `√`. Blitz
renders with a Unicode font and re-derives superscripts for fallback fonts, so
correct characters survive to the page. Flattened ASCII is ambiguous (`10-19` is
a range, `10⁻¹⁹` is a number) and cannot be recovered downstream. No LaTeX, no
MathML — nothing renders them.

### Shared context and dependencies

Checkpoints sets runs of questions against one scenario, and questions that read
"using your answer from part a". Both must survive onto the sheet or the
question is unanswerable.

- **`context`** is printed above the question, in its own style. Repeat it on
  every question in the run; Blitz shows it per question rather than assuming
  adjacency.
- **`depends_on`** makes the picker pull prerequisites onto the sheet, ahead of
  the question that needs them. Ids that do not resolve within the pack are a
  validation error.

In crop mode the same job can be done with an extra leading `question` figure,
which is what a page-image pack naturally does. Prefer the structured fields
where the text is used, so Blitz can lay the sheet out rather than having the
arrangement fixed into an image.

### Multiple figures, and why order matters

**A question may have as many figures as it needs.** They render in the order
given, so put a shared scenario or a required earlier question *before* the
question that depends on it, as the book prints them:

```jsonc
"figures": [
  {"role": "question", "page": 40, "bbox": [...], "caption": "Shared context"},
  {"role": "question", "page": 41, "bbox": [...], "caption": "Source question"},
  {"role": "answer",   "page": 543, "bbox": [...], "caption": "Source answer"}
]
```

Blitz stacks every `question` figure into the question and every `answer` figure
into the solution, and budgets the page for all of them.

### When the text cannot be trusted

Some maths cannot survive extraction. A stacked fraction is `h` on one line and
`p` on the next, with the bar drawn rather than typed — `λ = h/p` flattens to
`λ = hp`, which is wrong and looks right. Where you cannot represent a question
or its solution faithfully as text, set `render_mode` / `answer_mode` to `crop`
and give a figure covering the whole region. Blitz prints the page image and
keeps the text only for search and tagging.

**This is the single most valuable thing a pack can do that an extractor
cannot: decide, per question, whether the text is trustworthy.** Judge questions
and solutions separately — solutions are where the algebra lives and need it far
more often.

Crop selectively. A crop cannot reflow: Blitz sets two 90mm columns, and a
548pt full-page crop scales to 47% there, putting 10pt book text under 5pt. A
crop-heavy sheet therefore drops to a single column to stay legible, and fits
roughly **5 questions per two-page sheet where text fits 12**.

### Bounding boxes

Crop to the **content**, not the page. A crop under about 400pt wide can stay in
a two-column layout; wider forces single column. Tighter crops are also sharper
at the same output size.

### Image files and scale

A PNG carries no notion of how big it was on the page. If the pack uses `file`
figures, say what scale they were rendered at, once, in `source.figure_zoom`
(pixels per PDF point: a crop of a 400pt-wide region rendered at 3× is
1200px wide, so `figure_zoom` is `3`). Without it Blitz has to treat pixels
as points, every crop looks more than twice as wide as it is, the sheet drops
to single column and fits a fraction of the questions it should. A figure can
instead carry its own `pt_width`, which wins over the pack-level zoom. Figures
given as `page`+`bbox` need neither.

### Honest gaps

Omit `answer` where the book supplies none. **Do not generate one.** Blitz
prints "no worked solution in the source — check the book at the citation" and
the student knows where they stand. Use `notes` to record why.

### Review state

A pack is trusted more than heuristic extraction: rows land `verified` and tags
are taken as given. Curated is not the same as checked, so say which this is.
Anything not `approved`, or carrying any `review` entry, lands unverified.
Marking unreviewed curriculum tags "verified" puts a confidence on the sheet
nobody has earned.

---

## Validation

```bash
blitz import-pack packs/physics.json --dry-run
```

Checks everything the JSON Schema does, plus what a schema cannot: that dot
point ids exist in the current study design, that the fingerprint is current,
that bboxes fall inside the source PDF, that figure files exist, that
`depends_on` resolves, and that `crop` modes have the figure they need.

**All errors are reported together, and nothing is written unless the pack is
clean.** A 841-question pack surfaces all its problems in one run; a
half-loaded pack has invisible gaps.

Two checks worth running on your own side first:

1. **Grep stems for orphan lines.** Any line that is only `−1`, `2`, `RMS` or
   `0` is a torn super/subscript — see `docs/feedback-to-codex.md`. There should
   be none.
2. **Count `render_mode: "crop"`.** Over ~30% means text extraction is being
   worked around rather than fixed.

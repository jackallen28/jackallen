# Feedback on the Checkpoints pilot pack

Validated `physics-checkpoints-pilot.json` (101 questions) against the Blitz
importer. The pack is **structurally correct**: schema valid, study design
fingerprint matches, 287 figures well-formed, every question tagged, no
duplicate ids, marks on 95 of 101. It imports cleanly on the machine that holds
the source PDF.

What follows is about the extraction underneath it, in order of impact.

---

## 1. Text extraction is dropping superscripts onto their own lines

**21 of 101 questions (21%) are affected.** This is the root cause of almost
everything else, including the decision to crop the whole book.

```
"−1
25 km h is closest to which one of the following?"          <- should be 25 km h⁻¹

"D Use v = u + at and x = ut + 1at2 .
2"                                                           <- should be ½at²

"210 V is equal to
RMS
A 149 V
PEAK"                                                        <- should be 210 V_RMS, 149 V_PEAK
```

**Why it happens.** PyMuPDF (and pdfminer, and most extractors) sort text by the
y position of each span. Checkpoints raises the "⁻¹" in `m s⁻¹` about 1.3pt
above the baseline, so it lands on its own y-row and is emitted as a separate
line — before or after the sentence it belongs to. Subscripts (RMS, PEAK, ₀) do
the same downward. Stacked fractions are a related case: the numerator, the
denominator and the bar are three separate objects, and the bar is *drawn*, not
typed, so nothing in the characters says a fraction was ever there.

**The fix.** Do not trust the extractor's line order. Rebuild lines yourself:

1. Take spans with their bounding boxes (`page.get_text("dict")`).
2. Group them into visual lines by **vertical overlap with the line's dominant
   font size**, not by exact y. A span whose vertical centre is within ~0.6 ×
   the line's dominant size belongs to that line. That catches a superscript
   raised 25–35% without merging genuinely separate lines.
3. Within a line, order by **x**, not by document order.
4. A span noticeably smaller than the line's dominant size and offset from its
   baseline is a super/subscript: emit it inline at its x position, mapped to
   real Unicode (`⁻¹`, `₀`).
5. Word spacing in this PDF is **positional, not character-based** — `t = 4.9`
   is three spans nudged apart with no space glyph anywhere. Insert a space
   when the gap between spans exceeds ~0.14 × the font size, not when you see
   a space character.

Reference implementation: `blitz/ingest/textflow.py` in the Blitz repo
(~200 lines, MIT-ish, take it or reimplement).

**Stacked fractions cannot be fixed this way** — they are genuinely
unrecoverable as text. Detect them instead: a fraction bar is a drawn rule
2–40% of the page width with text above and below. Where one falls inside a
question, that question's text is untrustworthy and should be cropped. See
point 3.

---

## 2. Cropping everything costs more than half the sheet

Every question and every answer in the pilot is `render_mode: "crop"`. Measured
on the same dot points and the same book:

| | questions on a two-page sheet |
|---|---|
| all crops | **5** |
| text, cropping only where needed | **12** |

A Blitz is two pages. Cropping everything more than halves what fits, which is
the difference between a useful revision sheet and a thin one.

Crops also cannot reflow. Blitz sets questions in two 90mm columns; a 548pt
full-page crop scales to 47% there, putting the book's 10pt text under 5pt.
Blitz now detects a crop-heavy sheet and drops to a single column so the crops
stay legible — but that is the fallback that costs the second column, not the
goal.

**Target: crop 10–30% of questions, not 100%.** By the pack's own text, ~79% of
stems are already clean enough to set as text; with fix 1 applied that number
goes higher.

---

## 3. Decide per question whether the text can be trusted

This is the most valuable thing the pipeline can do that a regex cannot, and
the pilot's instinct here is right — it is just applied indiscriminately.

Set `render_mode: "crop"` (and `answer_mode` separately) **only** when one of
these holds:

- a fraction bar falls inside the question's span
- the text contains equation-editor glyphs (Unicode block `U+1D400–U+1D7FF`)
- a diagram carries labels that are part of the question's meaning
- the extraction produced an orphan fragment you could not reattach

Otherwise set text. Question and solution should be judged **independently** —
in the Blitz extraction of a 54-page sample, 3% of questions needed cropping
but 33% of worked solutions did, because solutions are where the algebra lives.

---

## 4. Emit `options[]` and `parts[]`

Currently everything is concatenated into `stem`:

```json
"stem": "Which one is closest…?\nA Final speed = 35 m s−1; distance = 61 m\nB …"
```

This loses:

- **multiple-choice formatting** — Blitz sets options as a labelled list, and
  cannot if they are inside the prose
- **per-part marks** — `parts[].marks` sums to the question total; 6 of 101
  questions currently have no marks at all
- **fit** — the layout estimates height from the stem, options and parts
  separately, so a run-together stem is mis-measured

55 of 101 questions are multiple choice, so this affects over half the pack.

```json
"stem": "Which one is closest to the final speed and distance travelled…?",
"options": ["Final speed = 35 m s⁻¹; distance = 61 m", "…"],
"parts": [{"label": "a", "text": "Calculate the impulse.", "marks": 3}]
```

Strip the leading `A `/`B `/`C `/`D ` from option text — Blitz relabels them.

One trap worth knowing: when splitting options by scanning backwards for
`A`/`B`/`C`/`D` line starts, a stem that itself begins with a capital and a
space — *"**A** dark region in a two-slit pattern happens because…"* — matches
the option pattern and corrupts the run. Take the longest suffix whose letters
are genuinely A, B, C, … in order.

---

## 5. Use real Unicode, not flattened ASCII

**0 of 101 stems use Unicode superscripts; 26 use flattened forms** like
`m s-2` and `10-19`.

Emit `m s⁻²`, `10⁻¹⁹`, `λ`, `Δ`, `Φ`, `θ`, `×`, `≈`. Blitz renders with a
Unicode font and re-derives superscripts for fallback fonts, so correct
characters survive to the page. Flattened text is ambiguous (`10-19` is a range,
`10⁻¹⁹` is a number) and cannot be recovered downstream. No LaTeX, no MathML —
nothing renders them.

---

## 6. Tighten the bounding boxes

All 287 figures are exactly 548pt wide — the full page, margin to margin.

Crop to the **actual content bounds**: the union of the text block and any
diagram, not the page. A tighter crop is sharper at the same output size, and
one under ~400pt can stay in a two-column layout instead of forcing the sheet to
single column.

---

## What to keep

- **Stable ids** (`CP-C01-S11-Q001`) and provenance strings
- **Refusing to invent answers** — "No source answer was included. No answer
  has been generated." is exactly right, and Blitz prints "no worked solution in
  the source" with the citation rather than hiding it
- **The editorial audit trail** in `notes` — "added missing 'to' before
  'determine'" is the kind of thing that makes a pack reviewable
- **The honest tagging caveat** — "deterministic pilot candidates and require
  subject review" is the correct label until a human checks
- **`printed_page` from the book's own numbering**, not the PDF index

---

## Verifying

```bash
blitz import-pack <pack>.json --dry-run     # validates, writes nothing
```

Reports unknown dot point ids, unknown question types, duplicate ids, bad
bboxes, missing figures and fingerprint mismatches — all at once, not one per
run. Nothing is written unless the pack is clean.

Two checks worth running yourselves before handing a pack over:

1. **Grep the stems for orphan lines.** Any line that is only `−1`, `2`, `RMS`,
   `0` or similar is a torn super/subscript. There should be none.
2. **Count `render_mode: "crop"`.** Over ~30% means the text extraction is
   being worked around rather than fixed.

The dot point ids and current fingerprint come from:

```bash
blitz dot-points physics --json
```

Re-check the fingerprint before each run: dot point ids are positional, so if
the study design is re-imported, a pack built earlier will carry valid-looking
ids that mean something else.

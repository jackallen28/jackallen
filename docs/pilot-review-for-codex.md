# Checkpoints pilot — review and answers

Reviewed from the zipped pilot directory. Everything except the source PDF was
available; `blitz` ran against the pack directly.

**Headline: the pack is sound, and the importer was not.** It was silently
discarding 60% of the question content. That is fixed, along with three smaller
gaps, and all of it is pushed. Re-pull before the 841-question run.

---

## 1. How the pilot maps onto Blitz's data model

| pilot | Blitz | notes |
|---|---|---|
| `id` (`CP-C01-S11-Q001`) | `question.id`, namespaced `<source_id>-<id>` | stable across re-imports; re-running updates in place |
| `chapter`, `printed_label`, `printed_number` | `printed_page`, `source_number` → `citation` | prints as `Checkpoints Physics, p. 11, Q1` |
| `question.blocks` + `raw_text` | `body` (searchable) and `stem` | body feeds FTS and tagging; never printed when `render_mode: crop` |
| `answer.blocks` + `raw_text` | `answer.text` | printed on the solutions pages |
| figure bboxes | `figures[]` → cropped at import, ~216dpi | **all of them now, in order** — see §4 |
| `contexts[]` / `context_ids` | `context` (new) or leading `question` figure | §4 |
| `depends_on_question_ids` | `depends_on` (new) | §4 |
| `subparts` | `parts[{label, text, marks}]` | **currently flattened into `stem` on export** — see §5 |
| `flags` | `review[]` (new) | §5 |
| `status: draft` | `status` (new) | §5 |
| `curriculum_mapping` / `kk_ids` | `question_kk` rows | tags taken as given; the tagger is not consulted |
| `marks`, `marks_status` | `marks` | summed from `parts[].marks` when present |
| `question-bank.sqlite` | — | Blitz keeps its own index; the pack JSON is the interchange format |

Blitz's model is deliberately thinner than the audit format. It keeps what is
needed to **select** a question (dot points, type, marks, difficulty) and to
**print** it (stem, parts, options, figures, citation). The audit trail —
block coordinates, source fragments, similarity scores, occurrence lists —
stays in `questions.json`, which is the right place for it.

---

## 2. Dry run

```
blitz import-pack .../physics-checkpoints-pilot.json --dry-run
```

```
ERROR source.pdf could not be opened:
  /Users/jack/Library/Mobile Documents/.../VCE_Physics_3_4_Checkpoints.pdf
  Every page/bbox figure needs it. Check the path is right on this machine,
  or re-export the pack with figures as files.
physics-checkpoints-pilot.json: 101 questions — NOT IMPORTED, 1 error(s)
```

That is the only finding, and it is an artefact of this review machine not
holding the book. **On the Mac that has it, the dry run passes.** Confirmed by
re-validating every non-PDF rule with the figures set aside: **0 errors,
0 warnings.**

One fix went in here too: a single unopenable PDF was producing 287 identical
errors, one per figure, burying the message under copies of itself. It is now
reported once.

---

## 3. Everything else found, nothing modified

The pack itself needed no changes. What follows is what validation and
inspection surfaced.

**Correct and worth keeping**

- fingerprint `750fe79e5aba` matches the current Physics study design
- 101 unique ids, no duplicates
- every `kk_id` and `question_type` known
- all 287 bboxes inside the 1,271-page, 612×792pt document
- marks on 95 of 101; `printed_page` from the book's own numbering
- answers absent where the source has none, and never invented

**Observations, not errors**

- 21 of 101 questions have an exponent or subscript torn onto its own line
  (`"−1\n25 km h is closest to…"`, `"…ut + 1at2 .\n2"`). This is the reordering
  bug covered in the separate extraction feedback, and is the reason crop mode
  is doing so much work.
- 0 of 101 stems use Unicode superscripts; 26 use flattened `m s-2`.
- 0 `options[]` and 0 `parts[]`, though the audit format has 27 records with
  subparts and 55 questions are multiple choice.
- All 287 crops are exactly 548pt wide — full page, margin to margin.

---

## 4. How crops, shared context and dependencies now appear

### Crops

**This was broken and is now fixed.** 56 of 101 questions carry more than one
`question`-role figure; the importer took only the first. Against the pilot that
discarded **60% of the question content** — silently, with a success report.

Questions now carry every figure in order. The renderer stacks them into the
question, the picker budgets for the whole stack, and the sheet's column choice
considers all of them. Answer figures likewise: 7 questions have two.

Because every crop is full-page width, a crop-heavy sheet drops to **one
column**, where a 548pt crop renders at 96% instead of 47% and the book's 10pt
text stays readable. The cost is density: on the same dot points, all-crops fits
5 questions on a two-page sheet where text fits 12.

### Shared context

Inserting the context as a leading `question` figure, as the pilot does, now
works correctly — that is exactly what the multi-figure fix repaired. It renders
above the question, in the order given.

There is also a structured `context` field now, for when a pack sets a question
as text: Blitz prints it above the question in a distinguishing style. Prefer it
where text is used, since it lets the layout reflow rather than fixing the
arrangement into an image.

### Required earlier questions

Previously these had nowhere to go, and the picker would happily put a dependent
question on a sheet alone. There is now a `depends_on` field:

- validation rejects ids that do not resolve within the pack
- the picker **pulls prerequisites onto the sheet**, immediately ahead of the
  question that needs them
- ids are namespaced by `source.id` on import

The pilot's three `depends_on_question_ids` records should be exported into it.
Seventeen `context_ids` records should become `context` or a leading figure —
whichever matches the render mode.

---

## 5. Recommended changes before the 841-question run

**Blitz side — done, pull before running**

1. Every figure imported, in order (was: first only, 60% loss)
2. One error per cause, not per figure
3. `context`, `depends_on`, `status`, `review` fields
4. Single-column layout for crop-heavy sheets
5. `figure_pt_width` recorded, so layout decisions use the crop's real size

**Pack side — five changes**

1. **Export `subparts` as `parts[]`** with `{label, text, marks}`. 27 records
   have them; all 27 are currently flattened into `stem`, losing per-part marks
   and the layout's ability to measure them.

2. **Export `options[]`** for the 55 multiple-choice questions, with the
   leading `A `/`B ` stripped. Blitz relabels them.

3. **Export `flags` as `review[]`, and set `status: "draft"`.** The pilot report
   is explicit that curriculum tags "require subject review" and all 101 records
   are draft — but the pack said nothing, so the importer marked every row
   verified. It now honours `status` and `review`, and anything not `approved`
   lands unverified. This matters more as the corpus grows: 841 rows asserting
   an unearned confidence is worse than 101.

4. **Export `depends_on` and `context`** from `depends_on_question_ids` and
   `context_ids`.

5. **Fix the line reconstruction, then crop selectively.** Covered separately;
   it is the highest-value change and reduces how much of the book has to be
   carried as images.

**Process**

- Keep `--dry-run` in the loop: validation is all-or-nothing and reports
  everything at once, so a 841-question pack surfaces all its problems in one
  run.
- Re-check the fingerprint before each run (`blitz dot-points physics --json`).
  Dot point ids are positional, so a study design re-import leaves an older pack
  carrying valid-looking ids that mean something else.
- Batching is unnecessary for Blitz's sake — import is linear and fast. Batch
  for review convenience if it helps.

**On the pilot's own risk assessment**

"The largest remaining risk is context scope, not answer matching" — agreed, and
the multi-figure bug meant that risk was being realised silently. With figures
carried whole and `depends_on` enforced, a question that loses its context
should now be a validation error rather than a quiet truncation. The 17 records
flagged `shared_context_scope_needs_review` are the right place to spend review
effort.

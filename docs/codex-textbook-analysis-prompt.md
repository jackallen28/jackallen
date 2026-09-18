# Prompt for Codex: indexing the Physics and Business Management textbooks

Paste the block below into Codex, with these files attached:

- the **VCE Physics** textbook PDF
- the **VCE Business Management** textbook PDF
- `docs/question-pack.schema.json` and `docs/question-pack-schema.md` (this repo)
- `docs/full-book-postmortem.md` (this repo — what went wrong last time and why)
- `physics-briefing-questions.md` and `business-management-briefing-questions.md`
  (generated already, see below — Blitz's own questionnaire for each subject)
- the VCAA study design for each subject (PDF or Word), so Codex can answer the
  briefing questions against the source of truth, not memory

Everything Codex produces comes back as plain files: no accounts, no API
calls, nothing installed into Blitz until you upload them yourself on the
**Index materials** or **Settings** page (or `blitz import-pack` /
`blitz context` from a terminal). Read what comes back before you load it —
see "Checking the result" at the end.

---

## The prompt

```
You are indexing two VCE textbooks for a tool called Blitz, which builds
two-page exam-revision sheets from real questions, anchored to the VCAA
study design. I'm giving you:

  - the VCE Physics textbook (PDF)
  - the VCE Business Management textbook (PDF)
  - the VCAA study design for each subject
  - docs/question-pack.schema.json and docs/question-pack-schema.md —
    the exact format every question must be in
  - docs/full-book-postmortem.md — a write-up of what went wrong the last
    time a model indexed a book for this tool, and the ten-point checklist
    that came out of it. Read it before you start. Every rule in it applies
    here, doubly, because a textbook is harder than the question bank that
    postmortem was about: it mixes teaching prose, worked examples and
    genuine questions, and the wrong call between them is worse than a
    slightly wrong crop.
  - physics-briefing-questions.md and business-management-briefing-
    questions.md — Blitz's own questionnaire for each subject, asking what
    a person preparing material for it needs to know

Produce three things per subject (six files total). Work through Physics
completely before starting Business Management, or vice versa — do not
interleave; the postmortem's biggest failure was inconsistency that came
from working many things at once.

## 1. A question pack (question-pack.schema.json, strictly)

Extract every genuine question the textbook contains: end-of-section
questions, chapter review questions, and exam-style questions if the book
has a dedicated bank of them. Also extract worked examples — the book's
own solved problems — but tag them distinctly (see below); they are not
the same thing as a question the student has to answer.

Follow docs/full-book-postmortem.md's checklist exactly:

  1. Tag each question on its own against the study design's dot point
     ids (get them from the study design directly — the fingerprint
     Blitz uses is printed at the top of the briefing-questions.md file
     for each subject; note it in source.study_design_fingerprint or
     pack.study_design_fingerprint). Use the chapter the question sits
     in to narrow which area of study is plausible, never to decide the
     dot point for every question in it. One dot point per question is
     normal; three is a sign you have not looked closely enough.
  2. Keep questions as text. render_mode: "crop" only when the maths
     genuinely cannot survive reconstruction as text — stacked
     fractions, roots with a vinculum, matrices, mangled symbols.
     Superscripts, units, Greek letters and inline fractions with a
     slash are text. A question that has a diagram is not cropped for
     that reason — the diagram is a figure (role: "question") alongside
     text you still write out in full.
  3. State the scale of every image. Put "figure_zoom" in the pack's
     source block if you are exporting page images as files, or — far
     better, since you have the source PDF in front of you — use
     page + bbox figures instead of files at all, so Blitz crops them
     itself at full resolution and no scale has to be declared or
     guessed. Prefer page + bbox everywhere you can.
  4. Crop to the content's bounding box, not the whole text block or
     page. Split anything taller than about 250pt into more than one
     figure. Never include blank space or a page number in a crop.
  5. Marks go in the "marks" field, never left inside the question text.
     If the book doesn't print marks (most textbooks don't), leave
     marks null rather than inventing a number.
  6. Fill in "context" for a question that depends on a shared scenario
     printed above it (a table of data, a diagram several questions
     refer to), and "depends_on" for a question that literally requires
     an earlier one's answer ("using your result from Q3...").
  7. status: "approved" by default. Only mark a row "draft" or add a
     "review" note for a concrete, specific doubt (an ambiguous
     boundary, a figure you could not confidently crop, a symbol you
     are not sure was read correctly) — not as a blanket hedge. If more
     than perhaps 15% of a chapter ends up flagged, stop and ask
     yourself whether you are being appropriately careful or just
     unsure of the format.
  8. Worked solutions as text too, same rule as question 2. Most
     textbook worked examples print full working — transcribe it.
  9. Run `blitz import-pack <file> --dry-run` yourself if you have the
     tool available; if not, hand-check the JSON against the schema's
     required fields and the example record in
     docs/question-pack-schema.md before calling it done.
 10. Include study_design_fingerprint. If you cannot compute it (it's a
     hash Blitz derives from the parsed study design), at minimum
     record which exact study design PDF/Word file and its date/version
     you tagged against, in source.title or a notes field, so a mismatch
     is at least detectable by a human.

One rule beyond the checklist, specific to a textbook: distinguish a real
question from a worked example properly. Give worked examples their own
question_type (something like "worked-example" if the study design's
question types don't already have an equivalent — note in your reply if
you had to invent one) or, if the tool prefers, leave worked examples out
of the pack entirely and note in your written report how many there were
and where, so a human can decide. Do not silently fold them in as if they
were end-of-chapter questions — that overstates how many independent
questions the book actually offers a student.

## 2. Answers to the briefing questionnaire

Open <subject>-briefing-questions.md. It is in two parts. Part A asks
about assessment style, command terms, how the study design's dot points
actually break up in practice, which are easily confused, and — this is
the part a textbook makes you uniquely well placed to answer — the real
vocabulary each dot point attracts, since you have just read hundreds of
real questions and worked examples about it. Part B asks for a single
fenced yaml block in an exact shape.

Answer every numbered question in Part A in your own words, using
concrete evidence from the textbook you just read — not generic
paraphrases of the study design's own wording. Then produce the Part B
yaml block, covering as many of the subject's dot point ids as you
genuinely have evidence for. Use the dot point ids exactly as printed in
the briefing file; do not invent, reorder or renumber them.

Save this as one Markdown file per subject: prose answers, then the
fenced yaml block at the end, exactly as the briefing file's own
instructions describe.

## 3. A short textbook-shape report (free text, one per subject)

This is not for the index — it's so a human can check whether Blitz's own
no-model textbook reader would find the same structure. In a few
paragraphs per subject, say:

  - How chapters, sections and subsections are numbered and headed
    (give 3-4 verbatim examples of real headings, with their font size
    or heading level if the PDF exposes it).
  - The exact phrase(s) the book uses to introduce a worked example
    (e.g. "Worked example 4.2", "Example 4.2", "Sample problem") and to
    introduce its solution ("Solution", "Answer", "Working").
  - The exact phrase(s) that introduce a block of practice questions
    ("Questions", "Exercise 4.2", "Check your understanding",
    "Practice problems") and a chapter/unit review
    ("Chapter review", "Exam-style questions", "Revision questions").
  - Anything in the book that looks like a question but is not one:
    "Think about it" boxes, learning-intention statements, glossary
    call-outs, self-check prompts with no real answer.
  - Roughly how many genuine questions vs. worked examples the whole
    book contains, per chapter if that's easy to count.

Be honest about coverage and uncertainty throughout — say plainly which
chapters you are confident about and which you rushed, rather than
presenting uniform confidence everywhere. A wrong dot point tag silently
corrupts every future revision sheet built from it; a "not sure, flagged"
note costs nothing and is fixable.
```

---

## Deliverables to expect back

| file | what it's for |
|---|---|
| `physics-questions-pack.json` | validate + `blitz import-pack`, adds real Physics textbook questions to the index |
| `business-management-questions-pack.json` | same, for Business Management |
| `physics-briefing-answers.md` | upload as a context document; installs a concept lexicon if the yaml block validates |
| `business-management-briefing-answers.md` | same — this is the one that matters most, since Business Management currently has **no** lexicon and falls back to weak word-overlap tagging |
| `physics-textbook-shape.md` | free text, for you/me to compare against `blitz/ingest/textbook.py`'s heading patterns |
| `business-management-textbook-shape.md` | same |

## Checking the result

Don't load any of it blind:

```bash
blitz import-pack physics-questions-pack.json --dry-run
blitz import-pack business-management-questions-pack.json --dry-run
```

Fix whatever the dry run flags, then import for real, or use the **Index
materials** page and drop the pack in as a zip (with its figures folder,
if it used file figures rather than page+bbox — page+bbox is better and
needs no folder at all).

For the briefing answers, either upload them as context documents on the
**Settings** page (which shows, per subject, how many dot points the
installed lexicon covers) or:

```bash
blitz context physics physics-briefing-answers.md
blitz context business-management business-management-briefing-answers.md
```

An id the study design doesn't recognise is dropped and named, never
silently kept — so a partial answer is still safe to load.

Bring me the two "textbook shape" reports specifically — that's the piece
I use to tune `blitz/ingest/textbook.py`'s own heading detection, which
has never been checked against a real book.

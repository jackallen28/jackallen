# The app

Double-click `mac/Blitz.command` (or run `blitz serve --open`). It opens on
four doors.

| door | what it is for |
|---|---|
| **Make a Blitz** | pick a subject and dot points, name the student or class it is for, generate the two-page sheet, open or print it |
| **Index materials** | add a study design and books, worksheets or question packs; get a folder of everything indexed |
| **Students** | every student or class, every sheet they have had, every question on it; their workbook and the master workbook |
| **Questions** | look a question up by its serial number or its words, read it and its solution, flag it if it is broken |
| **Settings** | subjects and what each one knows, context documents, backups |

## First run

A new copy of Blitz holds no questions, no index and nobody's subjects. The
first time it starts, every page sends you to a setup screen with two ways
in:

- **Restore a backup** — the zip `Create backup` made on another machine or
  an earlier install. The index, figures, study designs, students and every
  sheet come back as they were.
- **Start from scratch** — a new, empty index. The study designs that ship
  with Blitz (VCE Physics, VCE Business Management) are offered as starters;
  tick the ones you want and leave the rest. **Any other subject is added
  right there**: upload its VCAA study design, PDF or Word, and Blitz reads
  the units, areas of study and dot points out of it. Several at once is
  fine. The subject's name is guessed from the filename, so
  `2023PhysicsSD.pdf` becomes "Physics", and you can correct it before
  pressing Create. A file the parser cannot read stops the setup and names
  itself, leaving the folder as it was. Sample questions are optional, so
  you can try a sheet before indexing a book.

If the folder already holds an index from before this screen existed, a
third option appears: keep it. Starting over instead moves the old index
aside rather than deleting it.

What you pick is what you get. A person who ticks nothing has no subjects,
not somebody else's Physics: once set up, only the study designs in your own
folder count, and the shipped ones are templates setup copies from.

The same thing from a terminal:

```bash
blitz setup --restore ~/Downloads/blitz-backup-2026-09-18-0204.zip
blitz setup --subjects physics            # or --subjects with nothing after it
blitz setup --design ~/Downloads/2024LegalStudiesSD.pdf --name "Legal Studies"
blitz setup --keep                        # adopt an index already in the folder
```

A subject added this way gets generic question types (multiple choice,
short answer, extended response) until someone writes better ones for it,
and no concept lexicon, so its tagging leans on word overlap with VCAA's
own wording. Both are worth improving once the subject has books behind it.

## What a new subject comes with

Adding a study design gives Blitz the dot points and nothing else: no
books, no questions, an empty coverage table. That is the right answer, but
it is not a useful place to stop, so creating a subject also creates its
materials folder and writes two files into it:

```
sources/<subject>/INDEXING-GUIDE.md    every dot point, and what to do next
sources/<subject>/dot-points.json      the same list, machine-readable
```

The guide is the briefing to hand to whoever, or whatever, prepares the
material. It holds the subject's dot point ids with VCAA's own wording, the
study design fingerprint that pins them, the question types, what to drop
in the folder, and the rules that were learned indexing a real 1000-page
book: tag each question on its own, keep text as text, declare the figure
scale, crop to the content, marks in `marks`, run the dry run. Hand it and
the JSON to a model and it has everything it needs.

Both files are rewritten whenever the subject's study design is imported
again, so they never describe an older curriculum than the index is using.
`blitz guide <subject>` rewrites them on demand.

## Teaching Blitz a subject

Blitz decides which dot point a question belongs to by matching the words
the question uses against the words a question about that dot point tends
to use. The study design does not supply those. It says "apply the field
model to magnetic phenomena"; the exam says "a bar magnet is placed between
two current-carrying wires". Nothing useful overlaps.

The missing half is a **concept lexicon**: for each dot point, the
vocabulary a question about it actually uses, plus the terms that rule it
out. Physics has a hand-written one and files 83% of an unseen book's
questions under the right area of study. A subject without one falls back
on word overlap, which is much weaker.

Writing one by hand is a few hours. The app does it in three steps, from
Settings or the Index materials page:

1. **Download the briefing questions** for the subject. They are generated
   against its real dot point ids, and they walk through how the study
   design breaks up: which dot points are content and which are skills,
   which are routinely examined together, which are easily confused and
   what single phrase separates them, what vocabulary each one attracts,
   what wrongly attracts questions to it, and what notation the extractor
   is likely to mangle.
2. **Give that file and the study design to an AI of your choice** and ask
   it to answer every question. The last thing it is asked for is a fenced
   YAML block in the exact shape Blitz reads.
3. **Upload its answer back** as a context document. The prose is kept with
   the subject's material; the lexicon is checked against the study design
   and installed. Ids the design does not have are dropped and named, and a
   lexicon written entirely against a different version is refused.

From a terminal:

```bash
blitz briefing physics                  # writes physics-briefing-questions.md
blitz context physics answers.md        # keeps it, installs the lexicon
```

A context document with no lexicon in it is still kept: it is the subject's
notes, and whoever prepares material next should read it. Only the lexicon
changes what the tagger does. Settings shows, per subject, how many dot
points its lexicon covers and which documents it holds.

The study design is a public VCAA document. Do not paste copyrighted
textbook content into an AI as part of this.

## Where everything lives

One folder, `~/Documents/Blitz/`, shown at the bottom of the home page:

```
Blitz/
  blitz.json       written at setup; its presence is what "set up" means
  study-designs/   imported study designs (the shipped ones are the fallback)
  sources/         everything uploaded, per subject, plus each subject's
                   indexing guide, dot points and context/ documents
  index/           the question index and figure crops (rebuildable)
  exports/         "index materials" result folders and their zips
  blitzes/         every sheet ever generated
  students/        MASTER.xlsx and one workbook per student or class
  backups/         zips made by Create backup
```

`BLITZ_ROOT` in the environment moves the whole tree. Back that folder up
and you have backed up the lot.

## Backup

**Create backup** in Settings (or `blitz backup`) writes one zip into
`backups/` with everything worth keeping: the index, every figure crop, the
study designs you imported, the student record and its workbooks, and every
sheet ever made. Left out on purpose: the uploaded source books (tick
*include the source books* if you want them), the export folders and the
Word-to-PDF conversions, all of which the app can rebuild.

To move to another machine or come back after an update: install Blitz,
then `blitz restore <the zip>`, or unzip it into the Blitz folder. Restore
refuses to overwrite an index that already has questions in it unless you
pass `--replace`, and even then it moves the old one aside rather than
deleting it.

## Serial numbers

Every question gets a serial when it enters the index, `PH-0413` for the
413th Physics question, `BM-0027` for Business Management, and keeps it for
good: re-indexing the same book does not change it. It is printed under the
question on every sheet and again beside its worked solution, so a student
can say "PH-0413" and you can find it on the Questions page, check the
solution, and flag it if the book has it wrong or the crop cut it off.

## Flags

A question can be flagged **incomplete**, **corrupt** or **wrong**, with a
note. A flagged question is never put on a sheet until the flag is cleared.
The Questions page's *flagged only* box lists them; the exported
`questions.json` carries the flag too, so it survives a rebuild of the index
from the export.

## Students and classes

Name a student or class on the Make a Blitz page, or add one on the
Students page. Every sheet made for them is logged with its questions.
Next time, questions they have already had are skipped and the preview says
which; tick *allow repeats* to let them back in.

Two kinds of workbook are rewritten from the log after every sheet:

- `students/MASTER.xlsx` with three tabs: **Students** (one row each, with
  totals), **Log** (one row per question ever given, to whom, when, on which
  sheet, with its serial, source and dot points) and **Questions** (each
  question, how many times it has been given and to whom);
- `students/<Name>.xlsx` for each student or class: **Questions given** and
  **Sheets**.

They are regenerated from the database, so edits made in Excel are
overwritten next time; the app is the place to change things.

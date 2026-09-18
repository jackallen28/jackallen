# The app

Double-click `mac/Blitz.command` (or run `blitz serve --open`). It opens on
four doors.

| door | what it is for |
|---|---|
| **Make a Blitz** | pick a subject and dot points, name the student or class it is for, generate the two-page sheet, open or print it |
| **Index materials** | add a study design and books, worksheets or question packs; get a folder of everything indexed |
| **Students** | every student or class, every sheet they have had, every question on it; their workbook and the master workbook |
| **Questions** | look a question up by its serial number or its words, read it and its solution, flag it if it is broken |

## Where everything lives

One folder, `~/Documents/Blitz/`, shown at the bottom of the home page:

```
Blitz/
  study-designs/   imported study designs (the shipped ones are the fallback)
  sources/         everything uploaded, per subject
  index/           the question index and figure crops (rebuildable)
  exports/         "index materials" result folders and their zips
  blitzes/         every sheet ever generated
  students/        MASTER.xlsx and one workbook per student or class
  backups/         zips made by Create backup
```

`BLITZ_ROOT` in the environment moves the whole tree. Back that folder up
and you have backed up the lot.

## Backup

**Create backup** on the home page (or `blitz backup`) writes one zip into
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

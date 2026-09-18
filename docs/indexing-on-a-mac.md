# Indexing course materials on a Mac

Two ways in, same result. Nothing leaves the machine, no model runs, and there
is no account or key. A 1000-page book takes about a minute.

## The app

Double-click **`mac/Blitz.command`**. It starts Blitz and opens the browser
on the *Index materials* page:

1. pick the subject, or choose *New subject…* and name it;
2. add the VCAA study design (PDF or Word) the first time for a subject;
3. add the materials: PDFs, Word files, or a zip of a question pack with its
   figures folder; several at once is fine;
4. press **Index**.

The page shows the run as it goes, then the counts, the coverage table and a
button to download the whole result as a zip. The folder it names on disk
(`out/index-<subject>-<date>/`) holds the questions as a re-importable JSON,
the teaching sections, the coverage table and every figure. The live index
the sheet generator uses is updated at the same time, so *Make a Blitz →* at
the top of the page works straight away.

Leave the Terminal window it opened alone while you use it; closing it stops
the app. Everything uploaded lands under `sources/<subject>/uploads/`, which
is gitignored.

## The script

The same thing from Terminal, for a folder you already have:

```
mac/index-materials.command
```

### Once

```bash
git clone -b claude/vce-exam-prep-tool-eg2dha https://github.com/jackallen28/jackallen.git
cd jackallen
```

That is the whole install, for the app and the script alike. Either makes its
own Python environment the first time it runs (about a minute). It needs
Python 3.11 or newer; macOS ships 3.9, so if it complains:
`brew install python@3.12` and run it again.

### Each time

Put the materials for a subject in one folder:

```
sources/
  vcaa/
    physics-study-design.pdf         the VCAA study design (.pdf or .docx)
  physics/
    checkpoints-physics.pdf          a Checkpoints book
    heinemann-physics-12.pdf         a textbook
    motion-revision.docx             a worksheet or notes in Word
    checkpointscodex/
      physics-checkpoints-full.json  a question pack a model built (optional)
      figures/                       its images, any folder name
```

PDF and Word (.docx) both work, for books and for the study design. The
script looks in the folder and one level of subfolders, so a pack can keep
its own folder with its images beside it, whatever that folder is called.

`sources/` is gitignored; nothing in it is ever committed.

Then either **double-click `mac/index-materials.command` in Finder** and
answer three questions (subject, study design, folder), or from Terminal:

```bash
mac/index-materials.command physics sources/vcaa/physics-study-design.pdf sources/physics
```

Leave the study design argument empty (`""`) after the first run for a
subject; it only needs importing once, and re-importing changes nothing unless
VCAA has published a new one.

The script:

1. Imports the study design, if given. That replaces the subject's dot points
   with VCAA's own wording and records a fingerprint, so anything indexed
   against an older version is refused rather than silently misfiled.
2. Imports every question pack (`docs/question-pack-schema.md`), refining
   chapter-level tags to the dot point each question's text names. Other
   JSON files in the folder are skipped by name.
3. Indexes every `.pdf` and `.docx` as a book. It works out per file whether
   it is a Checkpoints book, a textbook, an exam paper or a worksheet and
   says so. A Word file is first rendered to a PDF (under `data/converted/`)
   so headings, numbering and images come through. Questions, figures,
   worked solutions and the teaching content itself are indexed and tagged
   to the study design.
4. Prints the coverage table: how many questions now sit behind each dot
   point.

Re-running is safe. A book or pack is identified by its filename, so running
the script again over the same folder updates in place rather than
duplicating.

Then:

```bash
.venv/bin/blitz serve        # http://127.0.0.1:8712
```

To compare two indexes of the same book, say a model's pack against
`blitz index` on the PDF, put both in the folder and run:

```bash
.venv/bin/blitz coverage physics --by-source
```

That prints one column per source for every dot point.

## Reading what it prints

For a book:

```
== Book: sources/physics/heinemann-physics-12.pdf
heinemann-physics-12: 412 pages, detected as textbook
  questions: 618 found, 571 indexed, 47 untagged
             203 with figures, 84 with solutions, 61 as page crops
  content  : 96 sections found, 91 indexed, 5 untagged
```

"Untagged" means the lexicon found nothing distinctive to file it under, so
it was left out rather than filed somewhere plausible. Those are the items
worth a look; everything indexed is selectable straight away.

For a pack:

```
== Pack: sources/physics/physics-checkpoints-full.json
  841 questions, 841 imported
    522 with figures, 838 with answers, 639 rendered as crops, 0 untagged
    tags refined: 397 narrowed to the dot point the text names, 23 extended
    to a dot point the pack left empty; 40 -> 51 dot points covered
```

A pack that fails validation is skipped with its errors listed and the rest of
the folder still runs.

## Leaving it running

The script wraps each book in `caffeinate -i`, so the Mac will not idle-sleep
mid-book with the lid open. For a shelf of books, start it and walk away; it
prints a line per file and the coverage table at the end. If you close the
lid it pauses and resumes; nothing is lost.

## Other subjects

Any subject Blitz has a study design for works the same way:
`.venv/bin/blitz subjects` lists them. The one difference is tagging quality.
Physics has a hand-written concept lexicon
(`blitz/studydesign/data/physics-lexicon.yaml`) and files 83% of an unseen
book's questions under the right area of study. A subject without a lexicon
falls back on word overlap with the study design's own wording, which is much
weaker; the index still builds, but expect more untagged items and check the
coverage table before trusting a sheet. Writing a lexicon for a subject is a
few hours with the study design open; the Physics one is the template.

Word files work for study designs too: the Business Management design
shipped with Blitz was imported from VCAA's `.docx`.

## If Finder will not run it

macOS may say the file "cannot be opened because it is from an unidentified
developer", or open it in an editor instead of running it. Either:

- right-click it, choose **Open**, then **Open** again in the dialog, or
- from Terminal, once: `chmod +x mac/index-materials.command` and
  `xattr -d com.apple.quarantine mac/index-materials.command`.

## Where things end up

| | |
|---|---|
| `sources/` | your PDFs and packs — gitignored, never committed |
| `data/blitz.sqlite3` | the index — rebuildable, gitignored |
| `data/crops/` | figure crops — rebuildable, gitignored |
| `out/` | generated sheets |

`data/` is derived. Delete it and run the script again to rebuild from
`sources/`.

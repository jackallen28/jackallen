# Running Blitz on a Mac

Everything here is plain Python and PyMuPDF. No model, no API key, no
network, nothing to leave running. Your PDFs never leave the machine.

**Start here instead if you just want to use it:** double-click
`mac/Blitz.command` and follow the first-run screen. `docs/the-app.md`
describes the app, `docs/indexing-on-a-mac.md` describes adding material.
This page is the terminal equivalent, plus the one thing the app does not
expose: building a draft question pack for review.

## Install once

```bash
git clone -b claude/vce-exam-prep-tool-eg2dha https://github.com/jackallen28/jackallen.git
cd jackallen
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

macOS ships Python 3.9, which is too old. If `python3 --version` says 3.9
or lower, `brew install python@3.12` and use `python3.12` above.
`mac/Blitz.command` does all of this by itself the first time it runs.

## Set up, once

A fresh install has no index and nobody's subjects. Either:

```bash
blitz setup --restore ~/Downloads/blitz-backup-2026-09-18-0204.zip
blitz setup --subjects physics
blitz setup --design ~/Downloads/2024LegalStudiesSD.pdf --name "Legal Studies"
```

`blitz root` prints the folder everything then lives in, which is
`~/Documents/Blitz` unless `BLITZ_ROOT` says otherwise.

## Index a book

```bash
blitz index ~/Documents/Blitz/sources/physics/checkpoints-physics.pdf \
    --subject physics
blitz coverage physics
```

PDF and Word both work, for books and for study designs. That is the same
thing the Index materials page does.

## Build a draft pack instead

`blitz index` writes straight into the index. `blitz extract-pack` does the
same extraction but emits a question pack for review first, which is worth
it for a book you intend to keep:

```bash
blitz extract-pack ~/Documents/Blitz/sources/physics/checkpoints-physics.pdf \
    --subject physics \
    --source-id physics-checkpoints \
    --title "Checkpoints VCE Physics Units 3 & 4" \
    -o packs/physics-checkpoints.json \
    --review-out packs/physics-review.json
```

**Roughly 40 seconds for 1000 pages**, measured at 40 ms/page including
cropping every figure. It prints how much of the book it is unsure about:

```
1296 questions from 1000 pages
  1128 need no review (87%)
  168 flagged:
       74  no marks and no options — may be a fragment
       46  untagged: no dot point matched
       31  text mentions a figure but none was found
       17  multiple-choice options look unsplit — check the boundary
```

`physics-review.json` holds only the flagged entries. That is the file to
hand to a person or a model, not the whole book. Fix them in the pack,
delete the `review` key as you clear each one, then:

```bash
blitz import-pack packs/physics-checkpoints.json --dry-run   # validate
blitz import-pack packs/physics-checkpoints.json             # load
blitz coverage physics
blitz serve --open
```

## Leaving it running

```bash
caffeinate -i blitz index <file> --subject physics &
```

`caffeinate -i` stops the Mac idle-sleeping mid-run. That is the whole
"background job" story; a launchd plist would be more machinery than the
task deserves.

## Where things live

Everything is under one folder, `~/Documents/Blitz` by default:

| | |
|---|---|
| `sources/` | your PDFs and packs, per subject, plus each subject's indexing guide and context documents |
| `study-designs/` | the study designs in use |
| `index/` | the SQLite index and cropped figures — rebuildable |
| `blitzes/` | generated sheets |
| `students/` | the master workbook and one per student or class |
| `backups/` | zips made by Create backup |
| `exports/` | Index materials result folders |

`index/` and `exports/` are derived. The rest is worth keeping, which is
what `blitz backup` puts in one zip.

## Speed notes

Measured on a 54-page extract and extrapolated:

| stage | rate |
|---|---|
| line reconstruction + segmentation | 20 ms/page |
| figure detection and cropping | ~20 ms/page |
| tagging | 1.3 ms/question |

The tagger is the cheap part, which is why it runs over everything rather
than being reserved for a subset. If a book ever is slow it will be the
cropping, and `--first-page`/`--last-page` will chunk it.

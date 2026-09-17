# Running Blitz on a Mac

Everything here is plain Python and PyMuPDF. No model, no API key, no network,
nothing to leave running. Your PDFs never leave the machine.

## Install once

```bash
git clone -b claude/vce-exam-prep-tool-eg2dha https://github.com/jackallen28/jackallen.git
cd jackallen
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
blitz init
```

macOS ships Python 3.9, which is too old. If `python3 --version` says 3.9 or
lower, `brew install python@3.12` and use `python3.12` above.

## Index the whole book

```bash
blitz extract-pack sources/checkpoints-physics.pdf \
    --subject physics \
    --source-id physics-checkpoints \
    --title "Checkpoints VCE Physics Units 3 & 4" \
    -o packs/physics-checkpoints.json \
    --review-out packs/physics-review.json
```

**Roughly 40 seconds for 1000 pages**, measured at 40 ms/page including
cropping every figure. There is nothing to schedule, nothing to resume and no
progress bar worth watching — it finishes before a kettle boils.

It prints how much of the book it is unsure about:

```
1296 questions from 1000 pages
  1128 need no review (87%)
  168 flagged:
       74  no marks and no options — may be a fragment
       46  untagged: no dot point matched
       31  text mentions a figure but none was found
       17  multiple-choice options look unsplit — check the boundary
```

`packs/physics-review.json` holds only those flagged entries. That is the file
to hand to a person or a model — not the whole book. Fix them in the pack,
delete the `review` key as you clear each one, then:

```bash
blitz import-pack packs/physics-checkpoints.json --dry-run   # validate
blitz import-pack packs/physics-checkpoints.json             # load
blitz coverage physics                                       # see the gaps
blitz serve                                                  # http://127.0.0.1:8712
```

## If you do want it out of the way

For a book big enough to be annoying, or to run it over several books at once:

```bash
caffeinate -i blitz extract-pack ... &        # survives the lid closing
```

`caffeinate -i` stops the Mac idle-sleeping mid-run. That is the whole of the
"background job" story — a launchd plist would be more machinery than the task
deserves.

To do a shelf of books in one go:

```bash
for pdf in sources/*.pdf; do
  name=$(basename "$pdf" .pdf)
  blitz extract-pack "$pdf" --subject physics --source-id "$name" \
      -o "packs/$name.json" --review-out "packs/$name-review.json"
done
```

## Where things live

| | |
|---|---|
| `sources/` | your PDFs — gitignored, never committed |
| `packs/` | the JSON indexes, safe to keep and edit |
| `data/` | the SQLite index and cropped figures — rebuildable, gitignored |
| `out/` | generated sheets |

`data/` is derived: delete it and re-run `blitz init` plus your imports to
rebuild. The packs are the thing worth keeping, because the review effort lives
in them.

## Speed notes

Measured on a 54-page extract and extrapolated:

| stage | rate |
|---|---|
| line reconstruction + segmentation | 20 ms/page |
| figure detection and cropping | ~20 ms/page |
| tagging | 1.3 ms/question |

The tagger is the cheap part, which is why it runs over everything rather than
being reserved for a subset. If a book ever is slow, it will be the cropping,
and `--first-page`/`--last-page` will chunk it.

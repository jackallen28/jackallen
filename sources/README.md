# sources/

Put your own PDFs here. **Nothing in this directory is committed** — see
`.gitignore` — so licensed material stays on your machine.

Suggested layout:

```
sources/
  vcaa/
    business-management-study-design.pdf
    physics-study-design.pdf
    exams/                       # VCAA past exams and reports (free to download)
  business-management-checkpoints.pdf
  business-management-textbook.pdf
  physics-checkpoints.pdf
  physics-textbook.pdf
```

Then:

```bash
blitz import-study-design sources/vcaa/physics-study-design.pdf --subject physics
blitz ingest sources/physics-checkpoints.pdf \
    --subject physics --source-id physics-checkpoints --kind checkpoints \
    --page-offset -2
blitz coverage physics
```

Scanned PDFs with no text layer need OCR first (`ocrmypdf in.pdf out.pdf`) —
both the study design importer and the question extractor read the text layer.

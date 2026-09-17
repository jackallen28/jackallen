# Deploying Blitz to Render

One private instance, reachable from your phone or a school computer, without
carrying a laptop around.

**Read this first.** A Blitz contains cropped images of a copyrighted textbook.
Putting them behind a URL anyone can reach is redistribution, whatever the
intent. So the deployed app is password-protected and **refuses to start on a
public interface without `BLITZ_PASSWORD` set** — an accidentally open instance
should be impossible, not merely discouraged. Keep the password to yourself and
anyone who owns their own copy of the book.

If you want to share the tool with classmates who do not own the book, deploy it
with the study designs and generated questions only, and leave the ingested
Checkpoints content on your own machine.

## 1. Deploy

Render reads `render.yaml` from the repo root.

1. **New → Blueprint** in the Render dashboard, point it at
   `jackallen28/jackallen`, branch `claude/vce-exam-prep-tool-eg2dha`.
2. Apply. Render builds (`pip install -e .`) and starts (`blitz serve`).
3. Once live, open the service → **Environment** and copy the generated
   `BLITZ_PASSWORD`. Any username works; that password is the whole credential.

The blueprint asks for the **Starter** plan, because a persistent disk needs a
paid instance. On the free plan the disk is dropped: the index and every crop
vanish on each deploy and after the instance sleeps, so you would re-ingest each
time. If you only want to try it, free works — just expect to re-run the import.

## 2. Get your book onto it

The licensed PDFs are gitignored and never reach the repo, so they have to be
uploaded to the disk. Two ways.

### Upload a pack built on your Mac (recommended)

Build the index locally where the PDF already is, then copy the derived data up:

```bash
# on your Mac
blitz extract-pack sources/checkpoints-physics.pdf --subject physics \
    --source-id physics-checkpoints -o packs/physics.json
blitz import-pack packs/physics.json

# then, from the Render shell (Dashboard → Shell), pull what you need
```

Render's shell has no inbound file transfer, so the practical route is to serve
the files from somewhere the instance can reach — a private object store, or a
temporary signed URL — and `curl` them into `/var/blitz/`. What has to arrive:

```
/var/blitz/data/blitz.sqlite3     the question index
/var/blitz/data/crops/            every figure crop
/var/blitz/sources/               only if you want to re-crop later
```

### Or ingest on the instance

Upload just the PDF to `/var/blitz/sources/`, then in the Render shell:

```bash
blitz init
blitz ingest /var/blitz/sources/checkpoints-physics.pdf \
    --subject physics --source-id physics-checkpoints --no-model
blitz coverage physics
```

Slower (about 40 s per 1000 pages, plus the upload) but needs nothing else.

## 3. Check it

```bash
curl https://vce-blitz-xxxx.onrender.com/healthz
# {"ok":true,"subjects":["business-management","physics"],"protected":true}
```

`/healthz` is the one route served without a password, so Render's health check
can reach it. It reports whether protection is actually on — if `protected` is
`false` on a deployed instance, something is wrong with the environment and you
should fix it before using it.

Then open the service URL. The browser asks for a username (anything) and the
password.

## How it behaves differently when deployed

| | local | Render |
|---|---|---|
| bind address | `127.0.0.1` | `0.0.0.0`, port from `$PORT` |
| password | not required | **required**, or it will not start |
| data location | `./data`, `./sources` | `$BLITZ_ROOT`, the mounted disk |
| health check | — | `/healthz` |

Everything else is identical: the same `blitz` commands work in the Render
shell as on your Mac.

## Notes

- **Sleeping.** A Starter instance stays up. Free instances sleep after
  inactivity and take ~30 s to wake, which is survivable but annoying mid-study.
- **Disk size.** 5 GB is generous: the 54-page sample produced 25 crops in a few
  MB, and a full 1000-page book with ~500 figures lands in the low hundreds of
  MB. Generated sheets accumulate in `out/` — delete them occasionally.
- **HTTPS.** Render terminates TLS, which is what makes HTTP Basic acceptable
  here. Do not run this behind plain HTTP.
- **Backups.** The disk is not backed up. The packs are the thing worth keeping,
  and they live in the repo; the index can always be rebuilt from them.

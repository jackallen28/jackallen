# CAD Quote Bot

An embeddable chat widget that turns "I need a bracket for my 90 mm torch" into a
real CAD model, a 3D preview the customer can spin around, and a quote request in
your inbox.

```
customer types one sentence
      ↓
Claude asks 3–6 targeted questions (one at a time, with tappable answers)
      ↓
build spec shown for confirmation  ──► "change something" loops back
      ↓
Claude writes OpenSCAD → server renders STL + PNG (retries on render errors)
      ↓
preview card in chat + 3D viewer in a new tab ("Return to chat" closes it)
      ↓
approve  ──► name, email, mobile, post code, quantity, lead time
      ↓
customer sees a confirmation · the request reaches you
```

**Preview mode (the default).** Nothing is emailed. The submitted request is
rendered in the browser at `/quote/<id>` — exactly the page that becomes the
email later — and the chat offers the customer a link to it. Add a mail key when
you want it delivered for real; the HTML is identical either way.

Everything the customer sees is white with orange accents, flat, no gradients or
shadows beyond a single elevation on the popup launcher. The accent is one CSS
variable (`data-accent`), so it re-skins in a second.

---

## Repo layout

| Path | What it is |
|---|---|
| `embed/cad-quote-widget.js` | The whole front end. One file, no build step, no dependencies. Renders inside a shadow root so your site's CSS and the widget's can't collide. |
| `embed/demo.html` | A sample host page — open it to see the widget in context. |
| `server/src/index.js` | HTTP API, file serving, viewer route, CORS, rate limits. |
| `server/src/flow.js` | The conversation state machine. Every message the widget shows is produced here, so the flow can't be skipped from the browser. |
| `server/src/llm.js` | All Claude calls, each returning structured JSON via `output_config.format`. |
| `server/src/openscad.js` | Sanitises generated `.scad`, runs OpenSCAD headlessly, measures the resulting mesh. |
| `server/assets/openscad-colorscheme.json` | Renders previews in the widget's palette — white ground, grey part, orange cut faces — instead of OpenSCAD's blue and orange. Installed into the image by the Dockerfile. |
| `server/src/viewer.js` | The standalone 3D viewer page (self-hosted three.js, inline STL parser and orbit controls). |
| `server/src/notify.js` | Builds the quote notification: previewed in the browser, or emailed to you + confirmed to the customer. |
| `server/src/storage.js` | Local disk or any S3-compatible bucket. |
| `test/` | Stub Claude API, stub OpenSCAD binary, and two runnable test suites. |

---

## Try it locally in five minutes

```bash
cd server
npm install
cp .env.example .env      # add ANTHROPIC_API_KEY and QUOTE_NOTIFY_EMAIL
npm start                 # http://localhost:8080
```

Then open `embed/demo.html` in a browser (it points at `localhost:8080` by default).

You need OpenSCAD on your PATH for real renders:

```bash
brew install --cask openscad      # macOS — then set OPENSCAD_XVFB=false in .env
sudo apt install openscad xvfb    # Debian/Ubuntu — leave OPENSCAD_XVFB=true
```

With no `RESEND_API_KEY` or `SMTP_HOST` set, emails are printed to the console
instead of sent — which is what you want while you're poking at it.

---

## Testing

Two suites, both offline: they run the **real** server against a stub Claude API
(`test/fake-anthropic.mjs`) and a stub OpenSCAD binary (`test/bin/openscad`), so
they cost nothing and need nothing installed.

```bash
cd server
npm run test:smoke    # 27 API-level checks, ~5 seconds
npm run test:ui       # drives the widget in headless Chromium + screenshots
npm run test:render   # real OpenSCAD: the text-to-model half (needs OpenSCAD on PATH)
```

`test:smoke` walks a whole conversation and asserts the state machine, the
generated files, the STL measurement, the viewer route, path-traversal
rejection, form validation, the honeypot, lead persistence, the quote preview
(both the copy addressed to you and the customer's), and the admin-key guard on
`/requests`.

`test:render` is the one that covers **text to model**: it renders a
representative part (plate, swept cradle, boolean cuts, countersunk holes)
through the real pipeline and asserts the mesh is genuine, its dimensions match
the source, the material volume is measured, and a preview image comes out. It
also proves the sanitiser blocks `include<>`, `use<>`, `import()` and
`surface()` before OpenSCAD ever runs. The rendered PNG and STL land in
`test/screenshots/` so you can look at them.

Both hermetic suites use the stub renderer by default. Point them at the real
one to see genuine geometry all the way through the widget:

```bash
OPENSCAD_BIN=openscad OPENSCAD_XVFB=true npm run test:ui
```

`test:ui` needs Playwright once:

```bash
npm i -D playwright && npx playwright install chromium
```

It drives the real widget from a *different origin* than the API (so CORS is
exercised the way a customer's site would), clicks through the whole flow,
opens the 3D viewer in a new tab, checks that "Return to chat" closes it, submits
the form, and fails on any JavaScript error. Screenshots land in
`test/screenshots/`.

### Testing the parts the stubs replace

The stubs deliberately don't test Claude's output quality or OpenSCAD itself.
For those:

```bash
# 1. Real model, real OpenSCAD, preview instead of email — talk to it yourself
cd server && npm start          # with a real ANTHROPIC_API_KEY

# 2. Check what Claude actually generated for a session
cat data/files/s_*/j_*/model.scad
openscad data/files/s_*/j_*/model.scad     # opens it in the GUI

# 3. Check what a submitted request looks like
#    the chat links to it, or set ADMIN_KEY and open /requests?key=...
#    Before going live, set RESEND_API_KEY + QUOTE_NOTIFY_EMAIL to your own
#    address and run one conversation to confirm delivery.
```

Worth doing by hand before launch: run ten briefs of the kind your customers
actually send, and look at the render each time. That tells you where to tighten
the prompts in `llm.js` (`SCAD_RULES` is where manufacturing constraints live).

---

## Embedding on your website

Inline, filling a container:

```html
<div id="cad-quote-bot" style="height:660px"></div>
<script src="https://quotes.yourcompany.com/embed/cad-quote-widget.js"
        data-api="https://quotes.yourcompany.com"
        data-target="#cad-quote-bot"
        data-accent="#FF6A1A"></script>
```

As a floating bubble on every page:

```html
<script src="https://quotes.yourcompany.com/embed/cad-quote-widget.js"
        data-api="https://quotes.yourcompany.com"
        data-mode="popup"></script>
```

| Attribute | Default | Notes |
|---|---|---|
| `data-api` | — | **Required.** Your server's origin. |
| `data-target` | `#cad-quote-bot` | Container selector (inline mode). |
| `data-mode` | `inline` | `inline` or `popup`. |
| `data-accent` | `#FF6A1A` | Any hex colour. |
| `data-height` | `640px` | Applied only if the container has no height. |
| `data-title` / `data-subtitle` | — | Header text. |

Works in Squarespace/Shopify/WordPress code blocks as-is. Set `ALLOWED_ORIGINS`
on the server to your site's origin(s) before you go live.

---

## Hosting: what I'd actually do

**The one constraint that decides everything: OpenSCAD is a native binary that
needs 30–60 seconds and ~1–2 GB of RAM per render.** That rules out Vercel,
Netlify Functions, and Cloudflare Workers — no arbitrary binaries, and request
timeouts shorter than a render. You need a container.

### Deploy to Render (what the prototype is set up for)

`render.yaml` at the repo root is a Blueprint, configured for Render's **free**
instance type. In Render: **New → Blueprint → pick this repo → Apply.** The only
value you supply is `ANTHROPIC_API_KEY` — Render prompts for it and generates
`ADMIN_KEY` for you.

**Render asks for payment details before applying any Blueprint**, even one that
only creates free services. If you'd rather not put a card on file, create the
service by hand instead — same result, no Blueprint:

#### No card: create the service manually

1. **New → Web Service**, connect this repo.
2. **Language:** Docker. **Root Directory:** `cad-quote-bot`
   (so the Dockerfile path is just `./Dockerfile`).
3. **Instance Type:** Free.
4. **Health Check Path:** `/healthz`
5. Add **one** environment variable: `ANTHROPIC_API_KEY`.

   Everything else already defaults correctly for a prototype — preview mode
   (no email provider needed), any origin allowed, files written inside the
   container. Optionally add `ADMIN_KEY` (any random string) if you want the
   `/requests` list.
6. **Create Web Service.** First build takes a few minutes (it installs OpenSCAD).

#### When it's live

| URL | What it is |
|---|---|
| `https://<your-app>.onrender.com/` | The demo page with the widget on it — start here |
| `…/quote/<id>` | The quote request as you'd receive it (linked from the chat) |
| `…/requests?key=<ADMIN_KEY>` | Every request received. Copy the key from Render → Environment |
| `…/embed/cad-quote-widget.js` | The script tag to drop on your real site |
| `…/healthz` | Health check |

#### What the free tier costs you

- **Nothing persists.** No disk on free, so `DATA_DIR` is `/tmp`: sessions,
  models and submitted requests are gone after a restart. Preview a request
  while the chat is still open and it's there; come back tomorrow and it isn't.
- **It sleeps after 15 minutes idle.** The next visitor waits ~50 seconds for a
  cold start — the widget will just sit on "Starting…" until it wakes.
- **512 MB of RAM.** Plenty for typical parts — a bracket like the one in the
  render test peaks at ~42 MB in OpenSCAD, with Node and Xvfb adding ~120 MB.
  Only a genuinely heavy model (hundreds of boolean operations, `$fn` in the
  hundreds) would trouble it.

**To make it persistent** (~$7/mo): in `render.yaml` set `plan: starter`,
uncomment the `disk:` block, and change `DATA_DIR` to `/data`. Or in the
dashboard: Settings → Instance Type → Starter, then add a disk mounted at
`/data` and update the variable. The container's entrypoint takes ownership of
the mounted disk before dropping to an unprivileged user; if it still can't
write there, the server logs a loud warning and falls back to temporary storage
rather than refusing to boot.

**Region** is `singapore` in the Blueprint. Change it if your customers are
elsewhere.

**`ALLOWED_ORIGINS` ships as `*`** so you can embed the widget anywhere while
testing. Tighten it to your own origins before real customers see it.

### Going live: recommended stack

| Piece | Use | Why | Cost |
|---|---|---|---|
| **App** | Render (above), or [Fly.io](https://fly.io) with the included `fly.toml` | Both run the container as-is with a persistent volume; Fly scales to zero between quotes | ~$7–15/mo |
| **Files** (STL/PNG/SCAD) | [Cloudflare R2](https://developers.cloudflare.com/r2/) | S3-compatible, **no egress fees** — STLs are the bandwidth here | ~$0.015/GB/mo, effectively pennies |
| **Notification** | Preview mode to start; [Resend](https://resend.com) or [Postmark](https://postmarkapp.com) when you want email | One API key, good transactional deliverability | Free tier covers early volume |
| **Leads** | JSONL on the volume + the email itself | Two copies from day one; add a database when you outgrow it | £0 |

Deploy:

```bash
# Fly.io, if you'd rather not use Render:
fly launch --no-deploy          # accept the included fly.toml
fly volumes create cadbot_data --size 3
fly secrets set ANTHROPIC_API_KEY=sk-ant-... \
                RESEND_API_KEY=re_... \
                QUOTE_NOTIFY_EMAIL=you@yourcompany.com \
                ALLOWED_ORIGINS=https://www.yourcompany.com
fly deploy
```

Then point `PUBLIC_URL` at your domain and add a CNAME (`quotes.yourcompany.com`).

### Alternatives, ranked

| Host | Verdict |
|---|---|
| **Render** | What this repo is configured for. Blueprint, Docker, disks, generated secrets — least setup, and the only one here with a free instance type you can use without a card (create the service manually). |
| **Fly.io** | Equally good and scales to zero between quotes, so it's cheaper when idle. `fly.toml` included. |
| **Railway** | Same shape as Render. Fine if you prefer it. |
| **Google Cloud Run** | Excellent if you're already on GCP — set concurrency to 1–2 and timeout to 300 s. Needs GCS for files (no local disk). |
| **AWS App Runner / ECS Fargate** | Works, more moving parts. Use if AWS is already your world. |
| **A $6 VPS (Hetzner/DigitalOcean) + Docker + Caddy** | Cheapest and completely under your control. You own patching and backups. |
| **Vercel / Netlify / Workers** | ❌ Can't run OpenSCAD. Only use these to host the *widget file* if you want. |

### Turning email on

Preview mode exists so you can test without a mail provider. When you want the
requests delivered:

```env
NOTIFY_MODE=resend
RESEND_API_KEY=re_...
QUOTE_NOTIFY_EMAIL=you@yourcompany.com
MAIL_FROM=Quotes <quotes@yourcompany.com>     # domain verified in Resend
```

You then get the request in your inbox and the customer gets a confirmation —
the same HTML the preview page shows, so there is nothing new to check. `/quote/<id>`
keeps working either way. Any SMTP provider works instead: set `NOTIFY_MODE=smtp`
and the `SMTP_*` variables.

### Where should the customer's files live?

Start with `STORAGE_DRIVER=local` and a mounted volume — simplest thing that
works, and STL files are small (tens to hundreds of KB).

Move to `STORAGE_DRIVER=s3` (R2) when any of these becomes true: you run more
than one app instance, you want files to survive redeploys independently of the
app, or downloads start showing up on your bandwidth bill.

```env
STORAGE_DRIVER=s3
S3_BUCKET=cad-quote-files
S3_REGION=auto
S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
# omit S3_PUBLIC_BASE_URL to hand out signed URLs that expire (default 7 days)
```

Leave `S3_PUBLIC_BASE_URL` unset unless you want the files publicly readable.
Without it the server hands out expiring signed URLs, so a leaked link stops
working. Add a bucket lifecycle rule (90 days is sensible) so old renders clean
themselves up — the quote email keeps the numbers even after the STL expires.

### Data, privacy, retention

You're collecting name, email, mobile, and post code — personal information
under the Australian Privacy Act and GDPR. Practical minimum:

- Sessions self-delete after `SESSION_TTL_HOURS` (default 72).
- Leads persist in `data/leads.jsonl` and in your inbox. Decide a retention
  period and actually apply it.
- The form carries a one-line purpose statement; link your privacy policy from
  the page hosting the widget.
- Don't put the Anthropic key anywhere near the browser — the widget never sees
  it, and it must stay that way.

### What a conversation costs

Roughly **$0.15–$0.50 in Claude tokens** per completed design (Opus 5, ~5–7
calls, the OpenSCAD generation being the expensive one; a failed render that
triggers a repair adds one more). Render compute is negligible. Set
`ANTHROPIC_MODEL=claude-sonnet-5` to cut that by about half if you'd rather
trade some modelling quality for cost — the intake questions and spec hold up
well; the OpenSCAD is where Opus earns its keep.

---

## Security notes

- **Generated OpenSCAD is untrusted input.** `openscad.js` rejects `include<>`,
  `use<>`, `import()`, `surface()` and the DXF readers before anything runs,
  clamps `$fn`, caps source length, and kills the process after
  `OPENSCAD_TIMEOUT_MS`. The container runs as a non-root user.
- **CORS is an allowlist.** `ALLOWED_ORIGINS` defaults to `*` for local
  development — set it to your real origins before launch.
- **Rate limits** are per-IP and in-memory (sessions/hour, messages/hour,
  generations/session). If you run more than one instance, put a shared limiter
  or your CDN's in front.
- **The honeypot field** silently accepts and discards bot submissions rather
  than telling them they failed.
- Sessions are addressed by a 96-bit random id and expire; the viewer only
  serves a model whose session and job id both match.

## When to move off the file store

The JSON-per-session store is deliberate: no database to run, and every lead is
also in your inbox. Swap `store.js` for Postgres (Neon or Supabase) when you
want to run multiple instances, query leads, or build an admin view. The four
functions to reimplement are `createSession`, `getSession`, `saveSession`,
`appendLead` — nothing else touches storage.

Note that sessions are held in memory as well as on disk, so **today the server
assumes one instance**. Multiple instances need either sticky sessions or that
Postgres swap.

## Configuration

Every option, with comments: [`server/.env.example`](server/.env.example).

## Known limits

- One OpenSCAD render at a time per instance is the safe assumption; heavy
  concurrency needs a queue (BullMQ + Redis) and a worker per CPU.
- OpenSCAD models parametric solids well. Organic/sculpted shapes and complex
  assemblies are outside what it — and therefore this bot — can do.
- The STL is a *starting point* for quoting, not a manufacturing-ready file.
  The email includes the `.scad` source so your engineer can adjust it.

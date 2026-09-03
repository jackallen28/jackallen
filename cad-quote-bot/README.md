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
customer sees a confirmation · you get the quote request by email
```

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
| `server/src/viewer.js` | The standalone 3D viewer page (self-hosted three.js, inline STL parser and orbit controls). |
| `server/src/mailer.js` | Quote notification to you + confirmation to the customer. |
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
npm run test:smoke   # 23 API-level checks, ~5 seconds
npm run test:ui      # drives the widget in headless Chromium + screenshots
```

`test:smoke` walks a whole conversation and asserts the state machine, the
generated files, the STL measurement, the viewer route, path-traversal
rejection, form validation, the honeypot, lead persistence, and both emails.

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
# 1. Real model, real OpenSCAD, fake email — talk to it yourself
cd server && npm start          # with a real ANTHROPIC_API_KEY, no mail keys set

# 2. Check what Claude actually generated for a session
cat data/files/s_*/j_*/model.scad
openscad data/files/s_*/j_*/model.scad     # opens it in the GUI

# 3. Check the emails render before going live
#    set RESEND_API_KEY + QUOTE_NOTIFY_EMAIL to your own address and run a
#    full conversation — you get both the owner and customer copies.
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

### Recommended stack

| Piece | Use | Why | Cost |
|---|---|---|---|
| **App** | [Fly.io](https://fly.io) — `fly launch` with the included `Dockerfile` + `fly.toml` | Runs the container as-is, gives you a persistent volume, scales to zero between quotes, region close to your customers | ~$5–15/mo |
| **Files** (STL/PNG/SCAD) | [Cloudflare R2](https://developers.cloudflare.com/r2/) | S3-compatible, **no egress fees** — STLs are the bandwidth here | ~$0.015/GB/mo, effectively pennies |
| **Email** | [Resend](https://resend.com) or [Postmark](https://postmarkapp.com) | One API key; good deliverability for transactional mail | Free tier covers early volume |
| **Leads** | JSONL on the volume + the email itself | Two copies from day one; add a database when you outgrow it | £0 |

Deploy:

```bash
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
| **Fly.io** | Best fit. Docker, volumes, scale-to-zero, cheap. |
| **Render / Railway** | Just as easy, no scale-to-zero on paid tiers. Fine if you prefer the UI. |
| **Google Cloud Run** | Excellent if you're already on GCP — set concurrency to 1–2 and timeout to 300 s. Needs GCS for files (no local disk). |
| **AWS App Runner / ECS Fargate** | Works, more moving parts. Use if AWS is already your world. |
| **A $6 VPS (Hetzner/DigitalOcean) + Docker + Caddy** | Cheapest and completely under your control. You own patching and backups. |
| **Vercel / Netlify / Workers** | ❌ Can't run OpenSCAD. Only use these to host the *widget file* if you want. |

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

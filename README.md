# Banyule Nillumbik Tech School — Program Booking System (prototype)

A booking website for BNTS programs (**Tech Samplers**, **Tech in Action**, **Extension Programs**).
Schools choose a program and a date; the site only offers days when the **rooms, shared equipment,
staff and program-combination rules** all allow it — and explains why a day is blocked.
Bookings can flow into **Microsoft 365 / Microsoft Bookings** three ways (see
[Microsoft Bookings](#microsoft-bookings--outlook)).

- Plain Node.js + SQLite, no build step. Runs on a laptop, in Docker, or on any host.
- Every rule lives in one human-editable file: [`config/catalog.yaml`](config/catalog.yaml).
- Judgement calls made from the rules document are listed in
  [`docs/OPEN-QUESTIONS.md`](docs/OPEN-QUESTIONS.md) — **please review these first.**

---

## Quick start

You need **Node.js 22 or newer** ([nodejs.org](https://nodejs.org)).

```bash
npm install
cp .env.example .env        # then edit ADMIN_PASSWORD at least
npm start
```

Open <http://localhost:3000>. The first start in demo mode loads example bookings for the next four weeks.

**Create your staff login** (in a second terminal, in the same folder):

```bash
npm run users -- add you@school.vic.edu.au --name "Your Name" --role manager
```

It asks for a password and shows a key to add to an authenticator app on your phone (Microsoft Authenticator,
Google Authenticator…). Then log in at <http://localhost:3000/admin> with email + password + the 6-digit code.

### With Docker

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app npm run users -- add you@school.vic.edu.au --role manager
```

Bookings are stored in the `bookings-data` Docker volume, so they survive restarts and upgrades.

### Useful commands

| Command | What it does |
|---|---|
| `npm start` | Run the site |
| `npm test` | Run all automated tests (clash rules, API, admin, calendar feeds, sync) |
| `npm run catalog:check` | Validate `catalog.yaml` and print every program with its rules |
| `npm run demo` | **Delete all bookings** and load the demo bookings again |
| `npm run backup` | Save a dated copy of the database to `data/backups/` |
| `npm run users` | Create / manage staff logins (the **only** way — see [Security](#security)) |
| `npm run bookings` | List, view or cancel bookings from the command line |
| `npm run graph:check` | Check Microsoft Graph credentials and list your Bookings services |
| `npm run graph:mock` | Run a pretend Microsoft Bookings locally, to try graph mode |

---

## What's in the prototype

**Public site**
- **Programs** — cards grouped by type, with filters for type, semester and number of classes.
- **Program page** — month calendar marked *Available / Unavailable* for the chosen number of classes, plus
  "next available dates" buttons. Pick a day → pick a time → fill in the form.
- **Booking form** — school, contact, email, phone, year level, notes. The server re-checks every rule when
  you press *Confirm*; if someone else just took the slot, the calendar refreshes with a friendly message.
- **Confirmation / manage page** — summary, *Add to calendar (.ics)*, a private manage link, and *Cancel*.

**Staff area (`/admin`)**
- **Day board** — rooms and shared kit (rows) × days/slots (columns), each booking a coloured block, plus
  "2/4 STEAM Comms" staff usage. Day or week view. *The showpiece for presentations.*
- **Bookings** — search, filter, view, cancel, retry sync, CSV export.
- **Rule tester** — choose program + date + classes and see the engine's full reasoning.
- **Catalog** — read-only view of every rule.
- **Calendar & sync** — Outlook feed links, Microsoft 365 sync status, recent activity, demo reset.

**How a booking is checked** (all reasons are collected and shown):
1. Program exists; date is a weekday, not a blackout, inside a semester the program runs in.
2. Number of classes is between 1 and the program's maximum.
3. Combination rules with anything else that day (`cannot_run_with`, `only_runs_with`).
4. Rooms and tracked equipment are free (e.g. "Pink Room **or** Blue Room" picks whichever is free).
5. Enough STEAM Communicators are free.
6. Appointments imported from Microsoft Bookings count too.

Two simultaneous bookings can never both win: the check and the save happen inside one locked database
transaction (tested with 20 simultaneous requests).

---

## Editing the rules (`config/catalog.yaml`)

After any change run `npm run catalog:check`, then restart the site. If the file has a mistake the site
won't start and tells you exactly which line is wrong.

**Add a program**

```yaml
  - id: 3d-robot-pets               # lowercase, dashes, unique
    name: "3D: Robot Pets"
    category: tech-in-action        # tech-samplers | tech-in-action | extension
    semesters: [S1, S2]             # or [S2] for Semester 2 only
    max_classes: 2
    staff_required: 2
    requires:
      - [systems-lab]               # needs the Systems Lab…
      - [pink-room, blue-room]      # …and the Pink Room OR the Blue Room
      - [vr-headsets]               # …and the VR headsets
    cannot_run_with: []
    only_runs_with: null
    equipment: ["3D printers"]      # shown on the website only
    software: ["Fusion"]
    notes: ["Staff-only note"]      # shown to staff only
    bookings_service_id: null
```

**Add a room or a piece of shared equipment**

```yaml
resources:
  - { id: maker-space, name: "Maker Space", type: room }
  - { id: microbits,   name: "Micro:bit class set", type: equipment }
```

Then add `[maker-space]` / `[microbits]` to the `requires:` of the programs that use it.

**Add a combination rule**

```yaml
    cannot_run_with: [clean-energy]                       # never on the same day/slot (applies both ways)
    only_runs_with: [medical-emergency, clean-energy]      # may ONLY run alongside these
```

**Other settings** (top of the file): class size, time slots, staff pool size, semester dates,
blackout days (`- { date: "2027-04-26", reason: "Public holiday" }`), and whether explicitly allowed pairs
may share rooms. To hide a program without deleting it, add `active: false`.

---

## Microsoft Bookings / Outlook

Choose what suits your school. Step-by-step instructions:
**[docs/M365-BOOKINGS-SETUP.md](docs/M365-BOOKINGS-SETUP.md)** (feeds, email, Graph) and
**[docs/POWER-AUTOMATE-SETUP.md](docs/POWER-AUTOMATE-SETUP.md)** (Power Automate).

| Level | Setting | Needs IT? | What happens |
|---|---|---|---|
| 1. Calendar feeds | always on | No | Staff subscribe in Outlook (*Add calendar → Subscribe from web*) to all bookings or one calendar per room. |
| 2. Email invites | `SYNC_MODE=email` | No (just an SMTP mailbox) | Each booking is emailed as a meeting invite to the Bookings calendar mailbox and/or staff; cancellations remove it. |
| 3. Power Automate | `SYNC_MODE=webhook` + `INBOUND_WEBHOOK_SECRET` | No (but flows need a Power Automate **Premium** licence) | Your flow puts each booking on the staff/Bookings calendars as a busy event; another flow sends appointments made in Bookings to the site, which blocks rooms/staff for them. |
| 4. Full Bookings sync | `SYNC_MODE=graph` | Yes (app registration) | Bookings are created as real Microsoft Bookings appointments, and appointments made directly in Bookings block rooms/staff here. |

Sync never blocks or undoes a booking. If Microsoft 365 can't be reached, the booking is marked
*sync failed*, shown in the admin area, and retried automatically every 15 minutes.

**Try graph mode now, without IT:** run `npm run graph:mock` in one terminal, then in another:

```bash
SYNC_MODE=graph BOOKINGS_BUSINESS_ID=bnts@example.onmicrosoft.com \
GRAPH_BASE_URL=http://localhost:4010/v1.0 npm start
```

---

## Deploying

Any host that runs Node 22 or Docker works. **All of them need a persistent disk/volume for `DATA_DIR`**
(that's where the SQLite database lives) — without one, bookings vanish on every redeploy.
Always set `CALENDAR_FEED_TOKEN`, `PUBLIC_URL`, and `DEMO_MODE=false` for real use, and create staff logins
with `npm run users` (see [Security](#security)).

| Host | Notes |
|---|---|
| **Render** | New *Web Service* from the repo (Docker). Add a *Disk* mounted at `/data`. Set env vars in the dashboard. |
| **Railway** | Deploy from the repo (uses the Dockerfile). Add a *Volume* mounted at `/data`. |
| **Fly.io** | `fly launch` (uses the Dockerfile), then `fly volumes create data` and mount it at `/data` in `fly.toml`. Keep to one machine (SQLite is a single file). |
| **Azure App Service** | *Web App for Containers* with this image, or a Node 22 Linux app with start command `npm start`. Set `DATA_DIR=/home/data` (the `/home` share is persistent) and enable *App Service storage*. Health check path: `/healthz`. |
| **Generic VPS** | Install Docker, copy `.env`, `docker compose up -d --build`. Put Caddy or nginx in front for HTTPS. |

Run **one** copy of the app (SQLite is a single file). Health check: `GET /healthz`.

**Backups:** `npm run backup` (or inside Docker: `docker compose exec app npm run backup`) writes a dated copy to
`data/backups/`. Copy those files somewhere safe, e.g. a scheduled job. Restoring = stop the app and put the
copy back as `data/bookings.sqlite`.

**Privacy:** the form only asks for what's needed to run a booking (school, contact name, email, phone, year
level) and shows a short privacy notice. Calendar feeds and invites contain contact details — keep feed links
private.

---

## Security

**Nothing about the rules can be changed on the website.** Programs, rooms, combination rules, dates and staff
numbers live only in `config/catalog.yaml`: edit it offline, check it with `npm run catalog:check`, then
deploy/restart. The site has no page that edits rules, settings or accounts.

**Staff access — choose with `ADMIN_ACCESS`:**

| `ADMIN_ACCESS` | What it means |
|---|---|
| `accounts` (default) | Each staff member has their **own login: email + password + a 6-digit code from an authenticator app** (two-factor). |
| `off` | **No admin website at all** — every `/admin` address is a plain "not found", so there is no login page to attack. Staff see bookings through the Outlook calendar feeds and make changes on the server's command line (`npm run bookings -- cancel PB-00012`). |
| `password` | One shared password. **Only allowed while `DEMO_MODE=true`** — the site refuses to start otherwise. |

**No backdoor.** Accounts can only be created, reset or removed on the server with `npm run users`, which needs
access to the server itself. The website has no sign-up, no "forgot password", no master password and no way to
create an account. A lost phone or forgotten password is fixed by the administrator running
`npm run users -- reset-2fa …` or `reset-password …`.

**Further protections built in:**
- **Roles:** `viewer` (see everything, use the rule tester) or `manager` (can also cancel bookings, retry sync,
  reset demo data). The server enforces this, not just the buttons.
- **Optional IP allow-list:** `ADMIN_ALLOWED_IPS=203.0.113.10, 10.0.0.0/8` — the admin area answers only from
  those addresses (e.g. the school network); everyone else gets "not found".
- **Lockout:** 5 wrong attempts locks that account for 15 minutes; at most 10 login attempts per IP address per
  15 minutes. Each authenticator code works only once.
- **Sessions** are stored on the server (only a hash of the cookie), `HttpOnly` + `SameSite=Strict` (+ `Secure`
  over HTTPS), and end after 60 minutes idle or 10 hours. `npm run users -- logout` ends everyone's sessions at
  once; disabling an account or resetting its password/2FA ends that person's sessions.
- **Passwords** are at least 12 characters and stored only as salted scrypt hashes.
- **Audit log:** every login, failed login, lockout, booking, cancellation and account change is recorded with
  who did it (*Calendar & sync → Recent activity*).
- **Browser protections:** strict Content-Security-Policy (only this site's own scripts), no framing, no MIME
  sniffing, HSTS over HTTPS; rate limits on the booking, manage-link, calendar-feed and Power Automate endpoints.

**Managing accounts** (in Docker, put `docker compose exec app` in front):

```bash
npm run users -- add jo@school.vic.edu.au --name "Jo Smith" --role viewer
npm run users -- list
npm run users -- role jo@school.vic.edu.au manager
npm run users -- reset-password jo@school.vic.edu.au
npm run users -- reset-2fa jo@school.vic.edu.au      # lost phone
npm run users -- unlock jo@school.vic.edu.au         # after a lockout
npm run users -- disable jo@school.vic.edu.au        # left, or on leave
npm run users -- logout                              # end every session now
```

**Still your responsibility:** run the site over **HTTPS** (Render, Railway, Fly.io and Azure do this for you);
protect the hosting account itself with MFA (whoever controls the server controls the data); keep
`CALENDAR_FEED_TOKEN`, `INBOUND_WEBHOOK_SECRET` and the Power Automate flow URL private; and store backups
safely — the database contains school contact details.

---

## Project layout

```
config/catalog.yaml     all programs, rooms, equipment and rules
docs/                   rules document, open questions, demo script, Microsoft 365 setup
public/                 website (HTML, CSS, vanilla JS) — colours, logo and name in public/theme.css
src/engine/             the clash rules (pure functions, heavily tested)
src/catalog/            loads + validates catalog.yaml
src/db/                 SQLite tables and queries
src/routes/             public API, admin API, calendar feeds
src/sync/               Microsoft 365: email invites, Power Automate webhook, Graph/Bookings, mock Graph server
src/seed.js             demo bookings
scripts/                catalog:check, demo, backup, graph:check, graph:mock
test/                   automated tests
```

**Branding:** colours, site name and logo are in [`public/theme.css`](public/theme.css). The logo at
`public/logo.svg` is a recreation of the BNTS pixel-square mark — replace it with the official file if you have one.

**Note on Node version:** the build spec said Node 20+, but Node 20 reached end-of-life in April 2026 and the
current SQLite driver needs Node 22, so the prototype targets **Node 22 LTS**.

---

## Next steps (out of scope for the prototype)

- Email confirmations to schools (currently: confirmation page + .ics + manage link).
- Sign in with Microsoft (Entra ID) for staff, if IT later allows an app registration.
- A QR code for authenticator setup (needs a small extra package — currently the key is typed in).
- Editing the catalog through the web UI.
- Rotation scheduling within a day, half-day slots, part-class bookings.
- Payments, school accounts, multi-site support, SMS.
- Moving an existing booking between Pink/Blue rooms to make space (see OPEN-QUESTIONS Q6).

# Program Booking System — Prototype Build Spec (for Claude Code)

A simple, presentable prototype of a booking website for tech-school programs (Tech Samplers,
Tech in Action, Extension Programs). Schools pick a program and a date; the system only offers
slots where **rooms, shared equipment, staff and program-combination rules** all allow it.

Goals, in priority order:
1. **Correct clash rules** — never allow a booking the rules forbid, and explain *why* a slot is blocked.
2. **Simple** — plain Node.js + SQLite, no build step, rules kept in one human-editable file.
3. **Host anywhere** — runs with `npm start` or Docker on any host (laptop, Render, Railway, Fly.io,
   Azure App Service, a VPS). No vendor-specific services.
4. **Works with Microsoft Bookings** — via a pluggable sync layer (see §8), usable today without
   IT admin access and upgradable to full Bookings sync when credentials are available.
5. **Demo-ready** — seeded example bookings, a reset button, and a scripted demo.

> **Instructions for Claude Code**
> - Build **one phase at a time** (§11). After each phase: run tests, summarise what changed,
>   commit, and **stop for review**.
> - The owner is not a full-time developer. Prefer plain, readable JavaScript with comments over
>   clever abstractions. No TypeScript, no front-end framework, no bundler.
> - Never invent rules. If the rules document is ambiguous, use the defaults in §4 and add the
>   item to `docs/OPEN-QUESTIONS.md`.
> - Ask before adding any dependency not listed in §2 or any paid service.

---

## 1. Inputs

- `docs/program-booking-rules.md` — the owner's rules document (room, staff, student, equipment,
  semester and combination rules for every program). **The owner will place this file in the
  repo before Phase 1.** It is the source for the catalog in §3.

---

## 2. Stack

| Concern | Choice |
|---|---|
| Runtime | Node.js 20+ (ES modules, plain JavaScript) |
| Web server | Express |
| Database | SQLite via `better-sqlite3` (single file in `DATA_DIR`) |
| Catalog / rules | `config/catalog.yaml` (parsed with `yaml`, validated with `zod`) |
| Front-end | Static HTML + CSS + vanilla JS in `public/`; FullCalendar installed via npm and served locally (no CDN, so it works offline at demos) |
| Email (optional) | `nodemailer` over SMTP (any provider) |
| Microsoft Graph (optional) | `@azure/msal-node` + `fetch` |
| Tests | Vitest + Supertest |
| Packaging | `Dockerfile` + `docker-compose.yml` |

Configuration via environment variables only (`.env.example` provided):

```
PORT=3000
DATA_DIR=./data
TIMEZONE=Australia/Melbourne
ADMIN_PASSWORD=change-me
CALENDAR_FEED_TOKEN=<long random string>
SYNC_MODE=none            # none | email | graph   (see §8)
DEMO_MODE=true            # shows demo banner + reset button
# email mode
SMTP_HOST= SMTP_PORT= SMTP_USER= SMTP_PASS= SMTP_FROM=
INVITE_ADDRESSES=         # comma-separated, e.g. Bookings calendar mailbox, staff
# graph mode
GRAPH_TENANT_ID= GRAPH_CLIENT_ID= GRAPH_CLIENT_SECRET= BOOKINGS_BUSINESS_ID=
```

---

## 3. Catalog file (`config/catalog.yaml`) — the single place rules live

Generate this in Phase 1 from `docs/program-booking-rules.md`. Shape:

```yaml
settings:
  class_size: 25
  slots:                      # bookable time blocks (local time)
    - { id: full, label: "Full day", start: "09:15", end: "14:45" }
  staff_pool: { name: "STEAM Communicators", size: 4 }   # ASSUMPTION — confirm
  semesters:                  # ASSUMPTION — owner to confirm dates
    S1: { from: "2027-01-28", to: "2027-06-25" }
    S2: { from: "2027-07-13", to: "2027-12-17" }
  blackouts: []               # e.g. { date: "2027-04-25", reason: "ANZAC Day" }

resources:                    # rooms + shared portable equipment
  - { id: fibre-hub, name: "Fibre Hub", type: room }
  - { id: vr-headsets, name: "VR Headsets", type: equipment }
  # ...

categories: [tech-samplers, tech-in-action, extension]

programs:
  - id: medical-emergency
    name: "Medical Emergency"
    category: tech-samplers
    semesters: [S1, S2]       # "Semester 2" section → [S2]
    max_classes: 2
    staff_required: 2
    requires:                 # each entry = one requirement; list = "any one of"
      - [drone-room]
      - [pink-room]
      - [drones]
      - [dobots]
    cannot_run_with: [clean-energy]
    only_runs_with: null      # null = no whitelist
    rotation: flexible        # display only: flexible | fixed-order
    software: ["Block coding", "MakeCode"]
    notes: ["Dobots can't go upstairs", "Drones must be upstairs"]   # staff-facing only
    bookings_service_id: null # Microsoft Bookings service ID, filled in later (§8)
  - id: creative-techstyles
    # ...
    only_runs_with: [medical-emergency, clean-energy]   # "Can run with ME, CE but no others"
```

On startup the server loads and validates the catalog and **refuses to start** with a clear error if
it references unknown resources/programs or is malformed. Add `npm run catalog:check` that
validates and prints a readable table of every program, its requirements and rules.

---

## 4. Interpreting the rules document (Phase 1)

The source document's table cells run words together (e.g. `Drone RoomPink Room`). Split them
using this dictionary of known names, and normalise to these IDs:

| ID | Matches in document |
|---|---|
| `drone-room` | Drone Room |
| `pink-room` | Pink Room, Pink |
| `blue-room` | Blue Room, Blue |
| `fibre-hub` | Fibre Hub |
| `builders-box` | Builders Box, BUILDERS BOX |
| `design-hub` | Design Hub |
| `systems-lab` | Systems Lab |
| `podcast-studio` | Podcasting Studio, Podcast Studio |
| `ce-sim-lab` | CE Simulation Lab, CE Simulation room |
| `media-room` | Media/green screen room upstairs |
| `igloo` | DS Igloo, DSIgloo, Igloo |

Interpretation rules (record every judgement call in `docs/OPEN-QUESTIONS.md`):

- `X/Y` in a room cell (e.g. `Pink/Blue Room`, `Blue Room/Design Hub`) = **either X or Y** → one
  requirement with alternatives `[x, y]`.
- **Rooms are exclusive** (one program per room per slot).
- **Tracked shared equipment** (exclusive, mobile kits that can clash across rooms): VR Headsets,
  Drones, Dobots, Podcasting kits. Other equipment (laser cutter, 3D printers, felt loom, etc.) is
  assumed to live in its room and is covered by the room rule — list it as display info only.
  "VR Headsets upstairs" in a room cell → `vr-headsets` equipment requirement.
- `Max. Students`: "1 class" → 1; "2 classes" → 2; "1 or 2" / "2-3" → the upper number; blank → 1
  and flag it.
- Programs under a "Semester 2" heading → `semesters: [S2]`; others → `[S1, S2]`.
  "(SEM 2)" in a name → S2 only.
- Combinations: "X cannot run with Y" → `cannot_run_with` (apply symmetrically).
  "Can run with A, B but no others" → `only_runs_with: [a, b]`.
  Abbreviations: ME = Medical Emergency, CE = Clean Energy (Tech Sampler).
- **Allowed pairs may share rooms.** Creative TechStyles, Wearable Tech Designer and Hype Machine
  all use Pink Room yet "can run with ME", which also uses Pink Room. Default: when a pair is
  explicitly allowed via `only_runs_with`, skip the room/equipment check *between those two
  programs* (`settings.allowed_pairs_share_rooms: true`). Flag for the owner to confirm.
- Staff: Tech Samplers say "2 STEAM Comms per booking" → `staff_required: 2`. Other programs
  don't say → default 2 and flag.
- Skip rows with no usable data (e.g. "CE: ??") and list them as open questions.
- Rotation order, software, and notes are **display/staff info only** — not scheduling logic.
- Strip lead names from program titles into `notes` (e.g. "Jordan, Edward Leads").

**Phase 1 checkpoint:** print the `catalog:check` table and stop so the owner can verify every program.

---

## 5. Clash engine (`src/engine/`) — pure functions, no DB or HTTP

```
checkBooking({ catalog, existingBookings, request }) → { ok, assignedResources, reasons[] }
availability({ catalog, existingBookings, programId, from, to, classes }) → [{ date, slotId, ok, reasons[] }]
```

`request` = `{ programId, date, slotId, classes }`. Checks, in order (collect all reasons):

1. **Program exists and is active**; date is in an allowed semester; not a weekend; not a blackout.
2. **Size:** `1 ≤ classes ≤ max_classes`.
3. For each existing, non-cancelled booking whose time overlaps (same date, overlapping slot):
   - **cannot_run_with** either direction → blocked: "Can't run alongside Clean Energy".
   - **only_runs_with**: if either program has a whitelist and the other isn't on it → blocked:
     "Creative TechStyles runs exclusively (only with Medical Emergency or Clean Energy)".
   - **Explicitly allowed pair** (on a whitelist) and `allowed_pairs_share_rooms` → skip resource check
     for this pair.
4. **Resources:** for each requirement, pick the first alternative not held by an overlapping
   booking (excluding allowed pairs). If none is free → blocked: "Pink Room and Blue Room both in
   use (Robot Lab, Smart Spaces)". Store the chosen resources as `assignedResources`.
5. **Staff:** sum of `staff_required` across overlapping bookings + this one ≤ `staff_pool.size`.
6. **External busy blocks** (imported from Microsoft Bookings in graph mode, §8) block the
   resources/staff they map to.

Reasons are human-readable. The public UI shows a generic "Unavailable" plus the rule type;
the admin UI shows full reasons including which booking caused the block.

---

## 6. Data (SQLite)

```
bookings        id, program_id, date, slot_id, classes, students, assigned_resources (JSON),
                school, contact_name, email, phone, year_level, notes,
                status (confirmed|cancelled), manage_token, created_at,
                external_id NULL, sync_status (none|pending|synced|failed), sync_error NULL
external_busy   id, source, external_id, date, start, end, resource_ids (JSON), label, imported_at
audit_log       id, at, action, booking_id, detail
```

The catalog stays in YAML (not the DB) so rules are edited in one place.

**Atomic booking:** inside a `better-sqlite3` `db.transaction()` (`BEGIN IMMEDIATE`), reload the
overlapping bookings, run `checkBooking`, then insert. Because the check and insert happen in one
serialised transaction, two simultaneous requests can't both win. Run migrations automatically
on start.

---

## 7. Website

**Public**
1. **Programs** — cards grouped by category with filter chips (category, semester,
   max classes). Each card: name, rooms, max students (classes × 25), semester badge.
2. **Program page + availability** — month calendar (FullCalendar) with each day marked
   Available / Unavailable for the chosen number of classes. Clicking a day shows slots.
3. **Booking form** — school, contact, email, phone, year level, number of classes (limited to the
   program's max), notes. Server re-checks on submit; if the slot was just taken, show a friendly
   message and the calendar again.
4. **Confirmation** — summary, "Add to calendar" (.ics download), manage link.
5. **Manage booking** (`/manage/:token`) — view and cancel.

**Admin** (`/admin`, password from `ADMIN_PASSWORD`, signed cookie session)
1. **Day board** — the showpiece for presentations: grid of rooms/equipment (rows) × slots
   (columns) for a chosen day, each booking a coloured block; staff usage shown as "3/4 STEAM Comms".
2. **Bookings list** — search, filter, cancel, CSV export; shows sync status per booking.
3. **Rule tester** — choose program + date + classes, see the engine's full reasons (great for
   explaining the rules live).
4. **Catalog view** — read-only table of `catalog.yaml`.
5. **Demo controls** (when `DEMO_MODE=true`) — "Reset demo data" reloads the seed bookings.

Design: clean, accessible (WCAG AA contrast, keyboard navigation, labelled form fields),
mobile-friendly; all colours and logo set in `public/theme.css`.

---

## 8. Microsoft Bookings integration — pluggable sync

All sync code lives behind one interface in `src/sync/`:

```js
// each adapter implements:
onBookingCreated(booking, program)   // → { externalId? }
onBookingCancelled(booking, program)
importBusy(fromDate, toDate)         // → external busy blocks (optional)
```

Sync never blocks or rolls back a booking. Failures set `sync_status=failed`, are logged, and are
retried by a background job every 15 minutes (and shown in admin).

**Always on — calendar feeds (no admin access needed)**
- `GET /calendar/:token/all.ics` and `GET /calendar/:token/room/:resourceId.ics`.
- Subscribe in Outlook via *Add calendar → Subscribe from web*. Stable event UIDs; cancelled
  bookings are removed from the feed.

**`SYNC_MODE=email` — invites (no admin access needed)**
- Sends an iCalendar invite (`METHOD:REQUEST`, stable UID) via SMTP to `INVITE_ADDRESSES`, e.g.
  the Microsoft Bookings calendar's mailbox and/or staff, and `METHOD:CANCEL` on cancellation.
- This places bookings on those Outlook/Bookings calendars. Document in the README that whether
  they then block availability on the Bookings page depends on the Bookings setting for staff
  calendar availability. The owner should test this.
- For demos without SMTP, write the invites to `data/outbox/` as `.eml` files instead.

**`SYNC_MODE=graph` — full Microsoft Bookings sync (needs IT to grant an app registration)**
- MSAL client-credentials token; `POST /solutions/bookingBusinesses/{id}/appointments` using the
  program's `bookings_service_id`, school contact as customer, local times in
  "AUS Eastern Standard Time"; store the returned ID in `external_id`.
- Cancel via `POST .../appointments/{id}/cancel`.
- `importBusy`: read `.../calendarView` for the next 120 days, map each appointment's service to a
  program, and store it in `external_busy` so bookings made directly in Bookings are respected by
  the clash engine.
- Ship with a **mock Graph server** used in tests, so this mode is fully tested before real
  credentials exist. Add `npm run graph:check` to verify credentials and list Bookings services
  (to fill in `bookings_service_id`).

---

## 9. Seed / demo data

`npm run demo` resets the database and loads bookings across the next four weeks that create
visible clashes, e.g.:
- Medical Emergency (2 classes) on a Tuesday → Clean Energy and Creative TechStyles + Merch Lab show
  as blocked that day, but Creative TechStyles + Medical Emergency is allowed.
- MFF: Circular Fashion on a Wednesday → anything else needing Fibre Hub is blocked.
- Robot Lab + Smart Spaces on a Thursday → Pink and Blue rooms both used, so a third Pink/Blue
  program is blocked.
- Enough bookings on a Friday to hit the staff pool limit.

---

## 10. Tests (must pass before each phase is accepted)

Engine unit tests using the real catalog:
1. Two programs needing Fibre Hub in the same slot → second blocked (reason names Fibre Hub).
2. Medical Emergency + Clean Energy same slot → blocked (both orders).
3. Creative TechStyles + Medical Emergency → allowed (allowed pair shares Pink Room).
4. Creative TechStyles + Merch Lab → blocked by whitelist.
5. Robot Lab + Smart Spaces → allowed (Pink/Blue alternatives assigned to different rooms); a third
   Pink/Blue program → blocked.
6. Two programs needing VR Headsets in different rooms → second blocked.
7. A Semester 2-only program on a Semester 1 date → unavailable.
8. Classes > max → rejected; classes = max → allowed.
9. Staff pool exceeded → blocked.
10. Cancelled bookings never block.
11. Blackout dates and weekends unavailable.
12. External busy block (graph import) blocks its resource.

API tests: create/cancel flow; **20 simultaneous POSTs for the same clashing slot → exactly 1
succeeds**; manage token works; admin routes reject without login; .ics feed validates; catalog
with an unknown room fails startup with a clear message; email mode writes `.eml` files;
graph mode against the mock server creates, cancels and imports.

---

## 11. Build phases

| Phase | Deliverable | Stop for review when |
|---|---|---|
| 0 | Scaffold: Express app, folder structure, `.env.example`, health check `GET /healthz`, Vitest | Server runs and test runs green |
| 1 | `catalog.yaml` from the rules doc + loader/validation + `catalog:check` + `OPEN-QUESTIONS.md` | Owner has checked the catalog table |
| 2 | Clash engine + all engine tests | Tests 1–12 pass |
| 3 | SQLite, migrations, booking/availability/manage API, concurrency test | API tests pass |
| 4 | Public pages | Owner can book end-to-end in a browser |
| 5 | Admin (day board, list, rule tester, catalog view) + demo seed/reset | Demo script works |
| 6 | Sync layer: .ics feeds, email adapter, graph adapter + mock + retry job | Sync tests pass |
| 7 | Packaging and docs (§12) | Fresh clone → running via Docker in under 5 minutes |

Folder layout:

```
config/catalog.yaml      docs/        public/        src/engine/   src/sync/
src/routes/  src/db/      scripts/     test/          data/ (gitignored)
```

---

## 12. Hosting and handover (Phase 7)

- `Dockerfile` (Node 20 slim, non-root user, `DATA_DIR=/data` volume) and `docker-compose.yml`.
- Works without Docker: `npm install && npm start`.
- `README.md` with: quick start; editing `catalog.yaml` (with examples of adding a program, room,
  or combination rule); deployment notes for Render, Railway, Fly.io, Azure App Service and a
  generic VPS (all need a **persistent disk/volume** for the SQLite file); subscribing in Outlook;
  enabling email or graph sync; backups (copy the SQLite file — add `npm run backup` that writes a
  dated copy); privacy note (collect only what's needed; add a short notice to the booking form).
- `docs/DEMO-SCRIPT.md`: a 5-minute presentation walkthrough —
  1. browse programs,
  2. book Medical Emergency,
  3. try Clean Energy the same day and show the reason,
  4. show the allowed Creative TechStyles pairing,
  5. open the admin day board and rule tester,
  6. show the booking in the subscribed Outlook calendar.
- `docs/OPEN-QUESTIONS.md` kept current.

---

## 13. Out of scope for the prototype

Payments, customer accounts/logins, multi-site support, rotation scheduling within a day,
editing the catalog through the web UI, and SMS. Note any of these as "next steps" in the README.

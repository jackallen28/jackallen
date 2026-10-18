# Connecting the booking site to Microsoft 365 / Microsoft Bookings

The site works on its own. These steps make its bookings show up in Outlook and Microsoft Bookings.
Do them in order — each level works without the next one.

| Level | You need | Time |
|---|---|---|
| [1. Outlook calendar feeds](#level-1--outlook-calendar-feeds-no-it-needed) | The site online at a public address | 5 min |
| [2. Email invites](#level-2--email-invites-sync_modeemail-no-it-admin-needed) | A mailbox that can send via SMTP | 15 min |
| [3. Full Microsoft Bookings sync](#level-3--full-microsoft-bookings-sync-sync_modegraph) | IT to create an app registration | 30 min with IT |

> **Before you start:** put the site online (see README → Deploying) and set `PUBLIC_URL`, e.g.
> `PUBLIC_URL=https://bookings.bnts.vic.edu.au`. Outlook fetches feeds from Microsoft's servers, so a site that
> only runs on your laptop (`localhost`) can't be subscribed to.

---

## Level 1 — Outlook calendar feeds (no IT needed)

1. Set `CALENDAR_FEED_TOKEN` to a long random value and restart. Generate one with
   `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`.
2. Log in to `/admin` → **Calendar & sync**. Copy the **All bookings** link (or a single room's link).
3. In Outlook on the web: **Calendar → Add calendar → Subscribe from web** → paste the link → name it
   (e.g. "Program bookings") → **Import**. In classic Outlook: *Add Calendar → From Internet*.
4. Outlook refreshes subscribed calendars on its own schedule (usually every few hours). New bookings appear
   after the next refresh; cancelled bookings disappear.

Anyone with the link can see bookings (including contact details), so share it only with staff. To revoke
access, change `CALENDAR_FEED_TOKEN` and re-subscribe.

---

## Level 2 — Email invites (`SYNC_MODE=email`, no IT admin needed)

Each new booking is emailed as a **meeting invite** (iCalendar `METHOD:REQUEST`), and a cancellation sends
`METHOD:CANCEL` for the same event, which removes it from the calendar.

1. Choose who receives the invites — set `INVITE_ADDRESSES` (comma-separated):
   - the **Microsoft Bookings business mailbox** (the address shown in Bookings → *Business information*,
     e.g. `BNTSPrograms@yourschool.onmicrosoft.com`), and/or
   - the **staff** (STEAM Communicators) who are Bookings staff members.
2. Set the SMTP account that sends them:
   ```
   SYNC_MODE=email
   SMTP_HOST=smtp.office365.com
   SMTP_PORT=587
   SMTP_USER=bookings-robot@yourschool.vic.edu.au
   SMTP_PASS=…
   SMTP_FROM=bookings-robot@yourschool.vic.edu.au
   INVITE_ADDRESSES=BNTSPrograms@yourschool.onmicrosoft.com
   ```
   (Microsoft 365 requires *Authenticated SMTP* to be enabled for that mailbox — your IT team can switch it on,
   or use any other SMTP provider.)
3. Restart, make a test booking, and check the recipient's calendar.

**Try it without SMTP:** leave `SMTP_HOST` empty. Invites are written to `data/outbox/*.eml` — double-click one
to open it in Outlook and see exactly what would be sent.

**Will it block times on the Bookings page?** That depends on a Bookings setting, so please test it:
in Microsoft Bookings → **Staff** → each staff member → turn on **"Events on Office 365 calendar affect
availability"**. With that on, an invite accepted onto a staff member's calendar makes them busy in Bookings.
Invites sent only to the Bookings business mailbox appear on its calendar but may not block staff availability.

---

## Level 3 — Full Microsoft Bookings sync (`SYNC_MODE=graph`)

What it does:
- **New booking** → creates an appointment in Microsoft Bookings (for the matching service), with the school
  contact as the customer and all booking details in the service notes. The appointment id is stored.
- **Cancelled booking** → cancels that appointment in Bookings.
- **Every 15 minutes** → reads the next 120 days of Bookings appointments. Anything booked **directly in
  Bookings** (e.g. a phone booking) holds that program's rooms, equipment and staff here, and its combination
  rules apply — so the website never double-books it.
- If Microsoft 365 is unreachable, bookings are marked *sync failed* (shown in `/admin`) and retried.
- Bookings' own customer email is turned off for these appointments (`optOutOfCustomerEmail`), because the
  school already gets the website's confirmation.

### Step 1 — IT creates an app registration (Microsoft Entra admin center)

Send this section to IT.

1. <https://entra.microsoft.com> → **Identity → Applications → App registrations → New registration**.
   - Name: `BNTS Program Booking Website`
   - Supported account types: *Accounts in this organizational directory only* → **Register**.
2. On the app's **Overview** page, copy the **Application (client) ID** and **Directory (tenant) ID**.
3. **Certificates & secrets → New client secret** → copy the secret **Value** (shown once). Note its expiry date
   and set a reminder to renew it.
4. **API permissions → Add a permission → Microsoft Graph → Application permissions**, add:
   - `BookingsAppointment.ReadWrite.All` — create/cancel appointments and read the calendar
   - `Bookings.Read.All` — list the Bookings business and its services
   Then click **Grant admin consent**.
   *Note for IT:* application permissions apply to every Bookings business in the tenant.

### Step 2 — Configure the site

```
SYNC_MODE=graph
GRAPH_TENANT_ID=<Directory (tenant) ID>
GRAPH_CLIENT_ID=<Application (client) ID>
GRAPH_CLIENT_SECRET=<secret value>
BOOKINGS_BUSINESS_ID=        # filled in by the next step
```

Run `npm run graph:check`. It signs in, lists the Bookings businesses the app can see (copy the right
`BOOKINGS_BUSINESS_ID` into `.env`), then run it again to list that business's **services**.

### Step 3 — Link programs to Bookings services

Each program needs a matching **service** in Microsoft Bookings. Either:

- **Easiest:** create the services in Bookings with **exactly the same names** as the programs
  (e.g. "Medical Emergency", "R&A: Robot Lab"). They link automatically; or
- copy each service id printed by `npm run graph:check` into the program in `config/catalog.yaml`:
  ```yaml
  bookings_service_id: "a1b2c3d4-…"
  ```

Run `npm run graph:check` again — it shows ✔ for every linked program. A booking for an unlinked program is
still saved; it shows *sync failed* with a message explaining what to link, and syncs once linked.

### Step 4 — Test

1. Restart the site and make a booking → it appears in Bookings (and on the staff calendar).
2. Cancel it from the manage link → it's cancelled in Bookings.
3. Create an appointment directly in Bookings for a program → within 15 minutes (or click **Sync now** in
   `/admin → Calendar & sync`) it appears on the day board as a striped "From Microsoft Bookings" block, and
   clashing programs show as unavailable on the website.

### Try it before IT is ready

`npm run graph:mock` runs a pretend Bookings API on `http://localhost:4010`. Start the site against it:

```bash
SYNC_MODE=graph BOOKINGS_BUSINESS_ID=bnts@example.onmicrosoft.com \
GRAPH_BASE_URL=http://localhost:4010/v1.0 npm start
```

See what the site sent: `curl -H "Authorization: Bearer x" http://localhost:4010/mock/appointments`.
Pretend someone booked in Bookings:

```bash
curl -X POST http://localhost:4010/mock/direct -H "Authorization: Bearer x" -H "Content-Type: application/json" \
  -d '{"programId":"medical-emergency","date":"2026-11-10","customerName":"Phone booking"}'
```

The same mock server is used by the automated tests (`npm test`), so graph mode is tested end-to-end.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `graph:check` can't sign in | Check tenant id, client id and secret (secret **value**, not its id); has the secret expired? |
| `403` / `Forbidden` | Admin consent hasn't been granted for the application permissions. |
| "isn't linked to a Microsoft Bookings service" | Create a Bookings service with the program's exact name, or set `bookings_service_id`. |
| Bookings show *sync failed* | Read the error in `/admin → Bookings → View`; fix it and press **Retry sync** (or wait 15 minutes). |
| Times are an hour out | Check `TIMEZONE` (default `Australia/Melbourne`). |
| Feed link gives "Not found" | `CALENDAR_FEED_TOKEN` changed or is still the placeholder. |

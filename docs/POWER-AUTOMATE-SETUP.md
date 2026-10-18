# Connecting to Microsoft Bookings with Power Automate (no IT app registration)

Use this if IT won't create an app registration for the full Graph sync. You build the flows
yourself in Power Automate, signed in with your normal school account.

```
 Website ──(booking / cancellation)──► Flow A ──► busy event on the staff / Bookings calendars
 Microsoft Bookings ──(appointment created / updated / cancelled)──► Flow B ──► Website
```

- **Flow A (website → Microsoft 365):** every booking made on the website becomes a busy Outlook event,
  and is removed again if it's cancelled. If the staff are Bookings staff members with
  *"Events on Office 365 calendar affect availability"* switched on, those events block the Bookings page.
- **Flow B (Microsoft Bookings → website):** anything booked directly in Microsoft Bookings (e.g. a phone
  booking) is sent to the website straight away. The website then holds that program's rooms, equipment and
  staff, and its combination rules apply (e.g. a Medical Emergency booked in Bookings blocks Clean Energy).

There's no loop: Flow A creates *Outlook events*, not Bookings appointments, so it doesn't trigger Flow B.

---

## Before you start — check these in your tenant

1. **Licence.** Flow A starts with *When an HTTP request is received* and Flow B uses the *HTTP* action.
   Both are **Premium** in Power Automate. You (the flow owner) need a **Power Automate Premium** licence (or
   your school may already include it). Open Power Automate, start a new flow, search for the trigger: if it
   shows a **Premium** badge and lets you save, you're fine. *No Premium?* See [Without Premium](#without-premium).
2. **Microsoft Bookings connector.** In Power Automate search for **Microsoft Bookings**. It provides
   *triggers* ("When an appointment is created / updated / cancelled") for a Bookings page you manage. As far
   as we know it has **no action to create appointments**, which is why Flow A creates calendar events
   instead. If your tenant shows such an action, tell us and we can use it.
3. **The website is online** at a public address (Flow B needs to reach it). Flow A works even while
   you test the website on your own laptop.

---

## Flow A — website → Outlook / Bookings calendars

### A1. Create the flow
1. Power Automate → **Create → Instant cloud flow** (or *Automated → skip*) → name it
   `BNTS website bookings → calendars`.
2. Trigger: **When an HTTP request is received** (Request connector).
   - *Who can trigger the flow:* **Anyone**. The URL itself contains a secret signature, so keep it private.
   - *Request Body JSON Schema:* click **Use sample payload to generate schema** and paste the sample JSON.
     Get it from the website: `/admin → Calendar & sync → Power Automate → Sample JSON`. A shortened example:
     ```json
     {
       "event": "booking.created",
       "reference": "PB-00012",
       "externalId": null,
       "programName": "Medical Emergency",
       "date": "2026-11-10",
       "startLocal": "2026-11-10T09:15:00",
       "endLocal": "2026-11-10T14:45:00",
       "startUtc": "2026-11-09T22:15:00.000Z",
       "endUtc": "2026-11-10T03:45:00.000Z",
       "school": "Riverbend Primary School",
       "contactName": "Sam Teacher",
       "email": "sam@example.com",
       "phone": "03 9000 0000",
       "classes": 2,
       "students": 50,
       "yearLevel": "Year 6",
       "roomsText": "Drone Room, Pink Room, Drones, Dobots",
       "staffRequired": 2,
       "subject": "Medical Emergency – Riverbend Primary School (2 classes) [PB-00012]",
       "description": "Booking reference: PB-00012\nProgram: Medical Emergency\n…",
       "manageUrl": "https://bookings.example.org/manage/…"
     }
     ```
     After you generate the schema, edit it and change `"externalId": { "type": "null" }` to
     `"externalId": { "type": ["string", "null"] }` (it's empty on new bookings and filled in on cancellations).
3. **Save**. The trigger now shows an **HTTP POST URL** — copy it.

### A2. Handle each event with a Switch
Add a **Switch** control. *On:* `event` (dynamic content from the trigger).

**Case `booking.created`:**
1. **Office 365 Outlook → Create event (V4)**
   - *Calendar id:* the calendar to block — e.g. a shared **"Program bookings"** calendar, or a staff member's
     calendar you can edit. Adding staff as attendees is usually the most reliable way to block their time.
   - *Subject:* `subject` · *Start time:* `startLocal` · *End time:* `endLocal`
   - *Time zone:* **(UTC+10:00) Canberra, Melbourne, Sydney**
   - *Location:* `roomsText` · *Body:* `description` · *Show as:* **Busy**
   - *Required attendees (optional):* the STEAM Communicators' addresses, separated by `;`
2. **Response** (Request connector): *Status code* `200`, *Body*:
   ```json
   { "externalId": "@{outputs('Create_event_(V4)')?['body/id']}" }
   ```
   (Pick **Id** from the *Create event* dynamic content if the expression name differs.) The website stores
   this id and sends it back when the booking is cancelled.

**Case `booking.cancelled`:**
1. **Office 365 Outlook → Delete event (V2)** — *Calendar id:* the same calendar, *Id:* `externalId`.
2. **Response**: status `200`.

**Case `booking.test`:** **Response** with status `200` (the admin page's *Send test* button uses this).

**Default:** **Response** with status `200`.

### A3. Connect the website
In the website's settings (`.env` or the host's environment variables):
```
SYNC_MODE=webhook
POWER_AUTOMATE_WEBHOOK_URL=<the HTTP POST URL from A1>
```
Restart, then `/admin → Calendar & sync → Send test to flow`, and check the flow's **run history**. Then make
a real booking on the website — the event should appear on the calendar. Cancel it — the event disappears.

If the flow fails or Power Automate is unavailable, the booking is still saved. It's marked *sync failed* in
the admin area and re-sent automatically every 15 minutes (or click **Retry sync**).

---

## Flow B — Microsoft Bookings → website

### B1. Turn on the website endpoint
Choose a long random secret, e.g. from `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`:
```
INBOUND_WEBHOOK_SECRET=<your secret>
```
Restart. The endpoint is shown in `/admin → Calendar & sync`:
`https://<your site>/api/integrations/power-automate`

### B2. Build the flow
1. **Create → Automated cloud flow** → name it `BNTS Bookings → website (created)` → trigger
   **Microsoft Bookings → When an appointment is created** → choose your BNTS Bookings page.
2. Add **HTTP** action:
   - *Method:* `POST`
   - *URI:* `https://<your site>/api/integrations/power-automate`
   - *Headers:* `Authorization` = `Bearer <your secret>` and `Content-Type` = `application/json`
   - *Body* — type this, and insert the dynamic content from the Bookings trigger where shown in `<…>`:
     ```json
     {
       "action": "created",
       "appointmentId": "<Id>",
       "serviceName": "<Service Name>",
       "serviceId": "<Service Id>",
       "start": "<Start Time>",
       "end": "<End Time>",
       "timeZone": "UTC",
       "customerName": "<Customer Name>"
     }
     ```
3. **Save**, then **Save As** twice to make copies for the other two triggers:
   - *When an appointment is updated* → `"action": "updated"`
   - *When an appointment is cancelled* → `"action": "cancelled"` (only `appointmentId` is needed)

### B3. Link services to programs
The website matches each appointment to a program by the **service name**, so name each Bookings service
**exactly** like the program on the website (e.g. "Medical Emergency", "R&A: Robot Lab"). Alternatively put
the Bookings service id in that program's `bookings_service_id` in `config/catalog.yaml`. Appointments for
services that don't match a program are recorded but block nothing.

### B4. Test
1. In Microsoft Bookings, book a program for a test date.
2. In `/admin → Calendar & sync`, **Last received** shows exactly what the flow sent.
3. Open the **Day board** for that date: a striped *From Microsoft Bookings* block shows the rooms it holds.
   **Check the time is right.** The Bookings trigger usually gives times in UTC; `"timeZone": "UTC"` covers
   that. If the block is out by 10–11 hours, change `"timeZone"` to `"AUS Eastern Standard Time"` (or remove
   it). Times that end in `Z` or `+10:00` are always read correctly.
4. On the public site, programs that clash with it are now unavailable that day.
5. Cancel it in Bookings: the block disappears and the day frees up.

---

## Without Premium

- **Website → calendars:** you don't need a flow. Use `SYNC_MODE=email` (see `docs/M365-BOOKINGS-SETUP.md`):
  the website emails each booking as a meeting invite to the staff / Bookings mailbox, using a normal mailbox
  that can send email. Or staff subscribe to the website's Outlook calendar feed.
- **Bookings → website:** the standard (non-Premium) connectors can't call a website. Options: a single
  Premium licence for the account that owns Flow B, the full Graph sync (needs IT), or — if your tenant
  allows publishing calendars — we can add an option for the website to read a published Bookings/staff
  calendar link (ask if you'd like this).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Admin shows *sync failed: Power Automate flow returned 4xx/5xx* | Open the flow's run history to see which action failed; fix it, then **Retry sync**. |
| *POWER_AUTOMATE_WEBHOOK_URL is not set* | Paste the trigger's HTTP POST URL into the setting and restart. |
| Cancelled bookings stay in Outlook | The *Response* action in `booking.created` must return `{"externalId": <event Id>}`, and the delete step must use the same calendar. |
| Flow B gets `401` | The `Authorization` header must be exactly `Bearer ` + `INBOUND_WEBHOOK_SECRET`. |
| Flow B gets `404` | `INBOUND_WEBHOOK_SECRET` isn't set on the website (or wrong URL). |
| Flow B response says *No program matches service* | Rename the Bookings service to exactly match the program name, or set `bookings_service_id`. |
| Bookings blocks are at the wrong time | Adjust `"timeZone"` in Flow B's body (see B4). |

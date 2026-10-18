# 5-minute demo script

**Before the demo**
- `npm run demo` (or *Reset demo data* in `/admin`) — loads example bookings starting next Monday.
- Open two tabs: the public site `/` and the admin site `/admin`, logged in with your staff account (create it
  once with `npm run users -- add you@school.vic.edu.au --role manager`). For a quick throwaway demo you can
  instead set `ADMIN_ACCESS=password`, which is only allowed with `DEMO_MODE=true`.
- The demo bookings use the week starting next Monday. Below, **Mon/Tue/Wed/Thu/Fri** mean that week.
  (`npm run demo` prints the exact dates.)
- Optional for step 6: an Outlook calendar already subscribed to the feed (see `docs/M365-BOOKINGS-SETUP.md`).

---

### 1. Browse programs (30 s)
Public site home page. "Every BNTS program in one place." Click the filter chips: **Tech Samplers**,
**Semester 2**, **2 classes (50)** — the list narrows instantly. Clear the filters.

### 2. Book Medical Emergency (1 min)
Open **Medical Emergency**. Choose **2 classes**. "The calendar only offers days when the Drone Room, Pink Room,
drones, Dobots and two STEAM Communicators are all free." Note **Tue** is already *Unavailable* (it's booked).
Click a free day → the form appears → fill in a school and submit → **Booking confirmed** with reference,
*Add to calendar* and a private manage link.

### 3. Try Clean Energy on a clashing day and show the reason (45 s)
Back to programs → **Clean Energy** (Semester 2). **Tue** is *Unavailable* — click it:
"Unavailable — clashes with another program that day". "Medical Emergency and Clean Energy share drones and
can never run together — the rules document says *ME cannot run with CE*, and the site enforces it."

### 4. Show the allowed Creative TechStyles pairing (45 s)
Open **Creative TechStyles** → **Tue** is *Available* even though Medical Emergency is using the Pink Room:
"These two are an explicitly allowed pair." Then show **next Mon** (Creative TechStyles is booked): open
**2D: Merch Lab** → that Monday is *Unavailable* — "Creative TechStyles runs exclusively".

### 5. Admin day board and rule tester (1.5 min)
Admin → **Day board** → **Week** view of the demo week:
- **Tue** — Medical Emergency holds the Drone Room, Pink Room, Drones and Dobots; 2/4 STEAM Comms.
- **Wed** — MFF: Circular Fashion holds the Fibre Hub → anything else needing Fibre Hub is blocked.
- **Thu** — Robot Lab in the Pink Room, Smart Spaces in the Blue Room → a third Pink/Blue program is blocked;
  staff 4/4 shown in red.
- **Fri** — two bookings use all four STEAM Communicators.
Click a block for full booking details.

**Rule tester** → *Introduction to Entrepreneurship*, **Thu**, 1 class → **Blocked**, with the exact reasons:
"Pink Room and Blue Room both in use (R&A: Robot Lab – booking #3 …; R&A: Smart Spaces – booking #4 …)" and
"Not enough STEAM Communicators: 4 of 4 already booked". "Schools only see the generic wording; staff see why."

### 6. Show it in Outlook (30 s)
Open the Outlook calendar subscribed to the feed — the bookings are there, with rooms as the location and
the school's details in the description. "With `SYNC_MODE=graph` they become real Microsoft Bookings
appointments, and anything booked directly in Bookings blocks the website too."

---

**If something goes wrong:** *Reset demo data* in `/admin` restores the starting point in one click.

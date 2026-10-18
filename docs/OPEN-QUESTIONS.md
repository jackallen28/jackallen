# Open questions for the owner

These are the judgement calls made when turning `docs/program-booking-rules.md` into
`config/catalog.yaml`. Each one has a working default so the prototype runs today.
**Please confirm or correct each item.** Most answers are a one-line change in `catalog.yaml`.

The **Q number** matches the `# ASSUMPTION (Qn)` comments in `catalog.yaml`.

---

## A. General settings

| # | Question | Current default | Where to change |
|---|---|---|---|
| Q1 | How many STEAM Communicators are available on a normal day? | **4**. Every program needs 2, so **at most 2 bookings can run on one day**. | `settings.staff_pool.size` |
| Q2 | What are the real semester dates? Can programs be booked during school holidays? | S2 2026: 13 Jul – 18 Dec 2026 · S1 2027: 28 Jan – 25 Jun 2027 · S2 2027: 13 Jul – 17 Dec 2027. Holidays inside these ranges **are** bookable. | `settings.semesters` (add holidays as blackouts) |
| Q3 | Which days are closed (public holidays, school holidays, staff PD days)? | Only **Melbourne Cup Day, Tue 3 Nov 2026** has been added, as an example. Weekends are always closed. | `settings.blackouts` |
| Q4 | Are all programs full-day? Do any run as AM/PM half days? | One slot: **Full day 09:15–14:45**. | `settings.slots` |
| Q5 | Creative TechStyles, Wearable Tech Designer and Hype Machine all use the **Pink Room** and "can run with ME" — but Medical Emergency also uses the Pink Room. How do they share it? | When two programs are an **explicitly allowed pair**, they are allowed to **share rooms and equipment** for that day (`allowed_pairs_share_rooms: true`). Staff are still counted for both. | `settings.allowed_pairs_share_rooms` |
| Q6 | Room assignment is first-come. If *Smart Spaces* is booked first and takes the Pink Room, a later program that can **only** use the Pink Room is blocked, even though Smart Spaces could have moved to the Blue Room. OK for now? | First-come (the system never moves an existing booking). The admin day board shows exactly which room each booking was given. | (code change if needed) |

## B. Staff

| # | Question | Current default |
|---|---|---|
| Q7 | The doc only says "2 STEAM Comms per booking" for **Tech Samplers**. How many staff do Tech in Action and Extension programs need? | **2** for every program. |
| Q8 | Medical Emergency's *Staff* column says **"All"**. What does that mean? | Read as "any STEAM Communicator can deliver it" → **2**. (If it meant *every* staff member, nothing could run alongside ME, which contradicts "Creative TechStyles can run with ME".) |
| Q9 | Do more classes need more staff (e.g. a 3-class R&A booking)? | No — staff is **per booking**, regardless of classes. |

## C. Combination rules

| # | Question | Current default |
|---|---|---|
| Q10 | "ME cannot run with CE" — does it also apply to the **Tech in Action CE programs** (Anywhereville VR, Gridlock, Drones)? | Applied to **Clean Energy (Tech Sampler) only**. Note *CE: Drones* already clashes with ME because both need the Drone Room and Drones. |
| Q11 | Creative TechStyles, Wearable Tech Designer and Hype Machine "can run with ME, CE but no others" — does that mean they can't run with **each other** either? | Yes — each only runs alongside Medical Emergency or Clean Energy. |
| Q12 | The *Combinations* column is blank for all Tech in Action and Extension programs. | They can run alongside anything, as long as rooms, equipment and staff are free (and the other program's rules allow it). |

## D. Rooms and equipment

| # | Program | Question | Current default |
|---|---|---|---|
| Q13 | Creative TechStyles | Five rooms are listed (Fibre Hub, Pink Room, Builders Box, Design Hub, Systems Lab). Does it need **all five** for the whole day? | Yes, all five. |
| Q14 | Hype Machine | Needs all four rooms (Fibre Hub, Builders Box, Podcasting Studio, Pink Room)? Is the "Podcasting deck" the kit in the studio, or the portable Podcasting Kits? | All four rooms; podcasting deck treated as part of the Podcast Studio (not the portable kits). |
| Q15 | Wearable Tech Designer | Room cell says "Pink Room – Felt loom". | Needs Fibre Hub + Pink Room; felt loom assumed to be in the Pink Room. |
| Q16 | Biodiverse Cities | "Podcasting studio" is listed under *Equipment*, not *Rooms*. | Treated as needing the **Podcast Studio room** (so it can't double-book the studio). |
| Q17 | Media: Podcast Production | "If 2 classes, must have 2nd space for recording." Which space? | **Not enforced yet** (shown as a staff note). Could be added as a rule that 2-class bookings also need a second room. |
| Q18 | 2D: Wearable Worlds | "VR Headsets (CE Simulation Lab)" — is the CE Simulation Lab room needed, or just the headsets kept there? Also "do we need Fibre Hub?" | Needs the **VR Headsets only** (not the CE Sim Lab room) and **no** Fibre Hub. |
| Q19 | All | Only **VR Headsets, Drones, Dobots and Podcasting Kits** are tracked as shared kit that can clash across rooms. Is there enough of everything else to run two programs at once — especially **Micro:bits** (ME, Wearable Tech, R&A, STEAMCode Arcade), **DJI cameras** (Hype Machine, Media), **Grove kits**, **3D printers** and **laser cutters**? | Everything else is assumed to live in its room (covered by the room rule). Adding a tracked item is a one-line change. |
| Q20 | All | Is there **one set** of each tracked kit (e.g. could two programs each use half the VR headsets)? | One set: a kit is used by one program per slot. |
| Q21 | R&A: Smart Spaces / Smart Devices | 3 classes (75 students) in **one** room (Pink *or* Blue)? Or do 3 classes need both rooms? | One room, Pink or Blue. |
| Q22 | STEAMCode Arcade | Needs Pink Room **and** Blue Room **and** Design Hub **and** Builders Box? | All four. |
| Q23 | 3D programs | "Systems lab · Blue Room/Design Hub" read as Systems Lab **plus** (Blue Room **or** Design Hub). | As stated. |
| Q24 | Media: Virtual Worlds | "VR Headsets upstairs" — the headsets only, used upstairs? | Needs Design Hub + VR Headsets. |

## E. Class sizes

| # | Program | Question | Current default |
|---|---|---|---|
| Q25 | 2D: Glow Up | "1 or 2 classes" (note: *need to gauge time to determine student numbers*). | Max **2**. |
| Q26 | R&A: Smart Spaces, R&A: Smart Devices | "2-3 classes". | Max **3**. |
| Q27 | 3D: Project Mars Challenge | *Max Students* is blank. | Max **1** class. |
| Q28 | All | Can a school book part of a class (e.g. 15 students)? Is there a minimum? | Bookings are in **whole classes** (1 class = 25 students). |

## F. Semesters

| # | Question | Current default |
|---|---|---|
| Q29 | Programs under a "Semester 2" heading, or with "(SEM 2)" in the name, are Semester 2 only: Clean Energy, 3D Worlds in Blender, CE: Anywhereville VR, CE: Gridlock, CE: Drones, 3D: Medical Aids, R&A: Escape Room, 2D: Made to Last, 3D: Project Mars Challenge. Correct? | As listed. Everything else runs all year. |

## G. Missing or unclear items in the rules document

| # | Item | What happened |
|---|---|---|
| Q30 | Extension program **"CE: ??"** | **Skipped** — no details. Add it to `catalog.yaml` when known. |
| Q31 | Creative TechStyles: "Can Fusion run on laptops/Z Books? AK" | A question for AK, not a scheduling rule. Not included. |
| Q32 | 3D programs: "Check that Z Books can cope" | Kept as a staff note. |
| Q33 | Media: Exquisite Animation: "Igloo to show?" | Kept in the equipment list as written. |
| Q34 | STEAMCode Arcade: "Games can focus on science, education, etc – teachers can choose?" | Kept as a staff note. Should the booking form ask teachers to choose a focus? |
| Q35 | 3D Worlds in Blender: "Jordan, Edward Leads" | Moved out of the title into a note: "Leads: Jordan, Edward". |
| Q36 | Spelling | Fixed: "Footorints" → Footprints, "Radio add" → Radio ad, "out together" → put together. Kept as written: Hype Machine software "Pp" (Premiere Pro?). |

## H. Microsoft Bookings integration

| # | Question | Current default |
|---|---|---|
| Q37 | Appointments made **directly in Microsoft Bookings** for a service that is linked to a program (via `bookings_service_id`). | Imported every 15 minutes (graph mode). They hold that program's rooms, equipment and staff **and** its combination rules apply (e.g. an ME booked in Bookings blocks Clean Energy here). |
| Q38 | Appointments in Bookings for a service **not** linked to any program (e.g. a meeting). | Shown on the admin day board but **block nothing**. Should they block staff? |
| Q39 | Does the school get an email confirmation? | Not yet — the confirmation page offers an .ics download and the manage link. Email to schools is a "next step". |

# CircuitPath: Arduino and ESP coding tutor (BNTS)

> The brief for Claude Code. Read it fully before building anything. It records every decision
> the teacher has made: what CircuitPath is, the rules, the architecture, the wiring wizard,
> the simulator, the boards, the projects and what to build first.
>
> **This is a separate project from PiPath** (the school's Raspberry Pi Python tutor). Nothing is
> shared: no code, no files, no submodules. The ideas below carry over; the code is written fresh.

---

## 1. What CircuitPath is

CircuitPath teaches Arduino C++ on real boards (Arduino Uno, Arduino Nano, NodeMCU, other ESP8266 /
ESP32 boards) like a tutor sitting beside the student. It is a **web app served by a Raspberry Pi 5
on the school network**: the teacher flashes a ready-made **CircuitPath SD card image**, puts it in
the Pi, plugs in power and a network cable, and that's it. **No screen, no keyboard**, no setup on
the Pi. Students open `https://circuitpath.local` (or the address IT gives it) in **Edge or Chrome**
on their Windows laptops: nothing to install, no admin rights needed. Their work is saved on the
Pi, so they can log in from any laptop. The teacher manages it from a **Teacher page** in their own
browser. Everything works without the internet.

Audience: secondary students (Years 7–10), new to text-based coding and electronics. Content links
to the **Victorian Curriculum Digital Technologies (Levels 7–10)**. Made for the **Banyule
Nillumbik Tech School (BNTS)**.

### The student journey

1. **Login:** welcome → pick your class → pick your name, or create a profile: **first name(s) +
   school only** (up to 4 names when students share a laptop and kit), plus a **picture password**
   (tap 3 of 9 pictures: easy for Year 7s, and it stops classmates opening each other's work on a
   shared server; the teacher can reset it) → step 2: **how much help** and **which board they
   have** (Uno, Nano, NodeMCU, ESP32...) → the **project picker**. A **Settings** button on
   every screen changes these at any time.
2. **Free choice:** every project is open from day one, in any order. Tiers are a guide only (a
   colour badge, a filter, "Good to try first" tips). Nothing is locked.
3. **Free Play is the first box** on the picker ("Free Play: build anything you like! ...or pick
   one of these projects for step-by-step help"). See §9.
4. **Every project starts with the Wiring Wizard** (§5): meet the parts → wire it step by step with
   a Fritzing-style breadboard view and schematic → **Test** (a forced test sketch made for that
   project's parts) → the student confirms each part works → only then the programming screen opens.
5. **Programming, one part at a time:** each step has instructions, starter code (may contain `___`
   blanks), a **checklist** checked automatically when the student presses Run / Upload (plus "I saw
   it happen" ticks for hardware), and a **Coach** that explains compiler and runtime errors in
   plain English with tiered hints.
6. **Simulator or Real board (MakeCode-style):** every project runs on the on-screen board
   (Simulator) or the real board over USB (Upload). **Watch the goal** plays the step's model answer
   in the simulator so students see what should happen before trying it on hardware.

### Things the teacher asked for (keep all of these)

- **No AI.** All help comes from a hand-written database of common errors and per-step hints.
  The About box says: developed by BNTS and reviewed by teachers, not hosted on AI, runs locally,
  and aims to open up programming to every student by adapting to each student's needs.
- **Help level is the student's choice:** **Beginner** (full explanations, hints any time),
  **Moderate** (each project's own gradual release) or **Advanced** (Years 9–10, "tutorial off":
  goal first, real compiler messages plus a technical explanation, fewer hints, steps can be
  skipped, **Jump to the challenge**, **Level up** challenges at the end, a code review after each
  step: magic numbers, repeated code, `delay()`-blocking loops, names, global state).
- **Adaptive scaffolding** on top of the level: stuck (same error twice, a check that keeps
  failing, 4+ failed runs, a quiet spell, no Run after a few minutes) → a gentle nudge with "Show me
  a hint" / "Watch the goal" / "Show the full explanation", hints unlock early. Flying (3 steps first
  try, no hints) → "try a harder level?". Struggling → "want a bit more help?". Each nudge once per
  step; level suggestions wait 4 steps; students can switch it off in Settings.
- **Gradual release:** guided → scaffolded → brief within each project. **Independence stars**
  count hints (not speed), framed positively.
- **One part at a time:** each project adds one new part, tests it on its own, then joins it up.
- **Curriculum links live in Settings > Curriculum** (a list of projects; opened from a project, it
  starts on that one). Not on the project intro.
- **Students run their own learning; the teacher only looks after the server.** Students never see
  teacher tools. Because the server is shared by the whole school, the things that affect everyone
  (Save a copy of all work, **Wipe session** for the next group, resetting a picture password) are
  on the **Teacher page** (§4), behind the teacher's password. Students' Settings keep **Save my
  work** (a `.circuit` file of their own work) and **Open my work**.
- **Autosave:** code saves to the Pi about a second after typing stops, and progress saves at every
  step, so students pick up where they left off, on any laptop.
- **Scrolling works like a website:** the wheel / trackpad scrolls the panel under the mouse, and
  anywhere else scrolls the page's main panel. (Free in a browser; don't break it with custom
  scroll handling.)
- **Student-facing text:** plain English, short sentences, about Year 7 reading level, Australian
  spelling (colour, favourite, organise, recognise). Encouraging, never sarcastic. Errors are
  "clues", not "failures".
- **Hardware safety text** on every wiring screen: unplug the USB cable before changing wires, plug
  it back in after; never connect 5V to an ESP pin (ESP boards are 3.3V); resistors with LEDs.

---

## 2. Look: Windows Vista, skeuomorphic

The whole interface looks like **Windows Vista (Aero)**, in the BNTS colours (teal `#19C1CA` /
`#04BBC1`, purple `#704988`, light purple `#CFC2E0`; the school logo's pixel squares in the corner):

- **Aero glass** window frames and title bars: translucent gradient, soft inner glow, rounded top
  corners, a big drop shadow; caption buttons (minimise style ✕ in a red glossy pill on dialogs).
- **Glossy "orb" and pill buttons** with a top highlight band, a hover glow and a pressed state; the
  default button pulses gently, like Vista.
- **Toolbars and the menu bar**: soft blue-grey vertical gradients, hairline separators with a white
  highlight, icons with reflections.
- **Panels**: white content areas inside light gradient frames; group boxes with etched borders;
  tabs like Vista's property sheets.
- **Font**: Segoe UI (on every Windows laptop), 9–11 pt equivalent, ClearType-friendly; code in
  Consolas.
- The **code editor** looks like a white Vista-era IDE (line numbers in a soft grey gutter, a glassy
  current-line highlight); the **Serial Monitor** looks like a Vista console window.
- **Balloon tips** (Vista's rounded yellow-white notification balloons) for the tour and the Coach's
  nudges.
- All of this is **CSS** (gradients, box-shadows, backdrop-filter) plus a few small PNG/SVG icons.
  No images of whole windows. It must stay fast on modest school laptops.

Keep every new screen in this style. Put colours, gradients and fonts in one stylesheet of CSS
variables (`ui/theme.css`).

---

## 3. Architecture (decided): a Raspberry Pi 5 server on the school network

```
Raspberry Pi 5 (8 GB), headless           student laptops (Windows, Edge / Chrome)
┌──────────────────────────────────┐      ┌────────────────────────────────────────┐
│ CircuitPath server (Go, systemd) │ https│ the web app: projects, Wiring Wizard,  │
│  - serves the web app            │◀────▶│ simulator (runs in the browser),       │
│  - accounts + saves (SQLite)     │      │ editor, Serial Monitor                 │
│  - compile queue (arduino-cli)   │      │                                        │
│  - Teacher page                  │      │ Upload: the compiled file goes to the  │
│ arduino-cli + cores + libraries  │      │ board over USB with Web Serial         │
└──────────────────────────────────┘      └────────────────────────────────────────┘
```

- **Server: one Go program** (`circuitpath-server`, a single static binary for linux/arm64), run by
  systemd, started at boot, restarted if it stops. It:
  - serves the web app (`ui/`) and a JSON API over **HTTPS** (port 443; port 80 redirects)
  - stores profiles, progress, sketches and settings in **SQLite** (one file, WAL mode, nightly
    backups, §4)
  - compiles with the bundled **arduino-cli** (cores and libraries pre-installed in the image, no
    internet needed), through a **queue**: at most 3–4 compiles at once (one per CPU core), others
    see "You're 3rd in line"; a **shared build cache** per board so each core is compiled once
  - returns the compiled `.hex` / `.bin` to the browser, which uploads it (below)
  - has a **Teacher page** (§4)
  - **updates itself every time it starts** (§4: signed GitHub releases; no internet → starts as it is)
- **The simulator runs entirely in the student's browser** (§6), so the Pi only works when a student
  presses **Upload** or **Check my code** (a real compile, for the Coach to explain real errors).
- **Uploading to a real board happens in the browser** with **Web Serial** (Edge / Chrome on Windows
  10/11, Chromebooks too): STK500v1 (Optiboot) for Uno / Nano, STK500v2 for Mega, `esptool-js`
  (Apache-2.0, vendored) for ESP8266 / ESP32, the Uno R4's bootloader protocol if R4s are used. The
  Serial Monitor and the Wiring Wizard's test also use Web Serial. Firefox and Safari can use the
  simulator but not Upload (the app says so kindly).
- **The web app** is plain HTML / CSS / ES modules, no build step needed to serve it; third-party code
  is vendored with its licence (CodeMirror, esptool-js), never loaded from a CDN.
- **Performance target on a Pi 5:** Uno compile (cached core) ≤ 5 s, ESP32 ≤ 30 s, a class of 25
  using it at once, the web app loads in under 2 s on the school network.

### What IT needs to do (once)

1. **A network port and a name.** Plug the Pi into a wired network port. It announces itself as
   `circuitpath.local` (mDNS). If the school network blocks mDNS, ask IT for a **DHCP reservation**
   and a DNS name (e.g. `circuitpath.<school domain>`). The Teacher page shows the address to use.
2. **HTTPS that browsers trust** (Web Serial, and so Upload, only works on secure sites). On first
   boot the Pi makes its own small certificate authority. The Teacher page has **Download
   certificate**: IT pushes it to the laptops as a trusted root (Intune / Group Policy), and
   `https://circuitpath.local` then shows a padlock. Or IT installs a certificate from the school's
   own certificate system on the Teacher page. (Fallback IT can choose instead: the Edge / Chrome
   policy that treats `http://circuitpath.local` as secure.)
3. **USB drivers on the laptops** for clone boards (CH340, CP2102): push them once with Intune, or
   choose boards with built-in USB that need no driver (genuine Uno R3, Uno R4 Minima / WiFi, Nano
   ESP32, ESP32-C3 / S3). Test one laptop first: plug a board in and check Device Manager for a COM
   port.

---

## 3a. The SD card image (no screen, no keyboard)

The teacher's whole set-up is: **flash, insert, power on**.

- **Built by CI** (GitHub Actions) with Raspberry Pi's image builder (`rpi-image-gen`, or `pi-gen` if
  needed), on **Raspberry Pi OS Lite (64-bit, Trixie)**. Published as a GitHub Release:
  `circuitpath-<version>.img.xz`, with its SHA-256.
- **Flash it with Raspberry Pi Imager** ("Use custom"). Imager's own settings (hostname, Wi-Fi,
  SSH key, password) still work and are optional. Use a 32 GB+ A2 card (or flash an SSD for a Pi 5
  with an NVMe HAT: faster, longer-lasting).
- **Already inside the image:** CircuitPath server, the web app, arduino-cli with the AVR, ESP8266
  and ESP32 cores and every library the projects use (pre-compiled build cache for each board),
  avahi (mDNS name `circuitpath`), a firewall allowing only 22 / 80 / 443, **automatic updates for
  everything** (Raspberry Pi OS: every update daily with `unattended-upgrades`, restarting at 03:30
  when one needs it; CircuitPath and its board cores / libraries: §4), log rotation, and a
  read-mostly setup that survives sudden power loss (data on its own partition, SQLite WAL, `fsync`
  on save). The image runs the same installer as a manual install (`deploy/install.sh`; how to try
  it on a Pi before the image exists: `docs/try-it-on-a-pi.md`).
- **First boot (automatic, about 2 minutes):** expands the filesystem, makes the HTTPS certificate,
  creates a random first **teacher password** and writes it to `circuitpath-first-login.txt` on the
  card's boot partition (readable on any computer), then starts serving. The teacher must change it
  on first login (and the file is deleted).
- **Optional settings file:** before first boot the teacher can put `circuitpath.toml` on the boot
  partition (any computer can open it): `school`, `hostname`, `teacher_password`, Wi-Fi network and
  password (Ethernet is recommended), `timezone`, static IP. Read once at first boot, then removed.
- **SSH** is off by default and only for emergencies: turned on from the Teacher page, or by Imager's
  settings, or an `ssh` file on the boot partition.
- **No screen ever needed.** The Pi's green LED shows status: steady = ready, slow blink = starting /
  updating, fast blink = a problem (the Teacher page or the boot partition's `circuitpath-status.txt`
  explains it).

---

## 4. The Teacher page (`https://circuitpath.local/teacher`)

Only for looking after the server. Behind a teacher password (hashed with Argon2 / bcrypt; locked
for a minute after 5 wrong tries). Plain, Vista-styled, works on the teacher's laptop or phone.

- **Status:** address(es), uptime, CPU temperature, disk space, compile queue, students online,
  version.
- **Classes:** create classes (e.g. "9D Tuesday") so students pick their class at login; see each
  student's progress (projects, steps, stars, hints, last seen); reset a student's picture password;
  move or delete a student (with a confirm).
- **Save a copy:** download everything (all students' work + `progress.csv`) as a zip. **Automatic
  backups** every night to the data partition (keep 14) and to a USB stick if one is plugged into the
  Pi.
- **Wipe session:** for the next school or group: type `WIPE`; deletes every student and class
  (offers Save a copy first). The server's settings stay.
- **Restore** from a Save a copy zip (e.g. after reflashing).
- **Updates are automatic, at every startup and every night (03:00).** Each time the Pi starts,
  and every night, if it can reach the internet, it checks GitHub Releases for a newer version;
  if there is one it downloads it,
  verifies its signature, backs up the database, installs it and restarts (students who open the
  page meanwhile see "CircuitPath is getting ready"). If the new version can't start, the Pi goes
  back to the old one by itself and skips that version. No internet: it just starts as it is.
  Each release pins exact, tested versions of arduino-cli, the board cores and the libraries
  (`internal/arduino/requirements.json`); after an update the Pi installs any that changed.
  The Teacher page can also **Check for updates** now, or **Upload an update file** (downloaded on
  another computer). Student work is backed up before every update and never lost to one.
  Reflashing a new image is also fine: Save a copy first, then Restore. (How it works and how to
  publish a release: `docs/updates.md`.)
- **Settings:** school name, change the teacher password, HTTPS certificate (download the Pi's CA /
  upload the school's own certificate), network (hostname, Wi-Fi), SSH on/off, which boards and
  projects are shown, the class kit list (`kit.json`), automatic updates on / off, shut down /
  restart (shut down before unplugging when possible).

---

## 4b. Boards

Students pick their board at setup (changeable in Settings and in the toolbar). Each board is a data
file (`content/boards/*.json`): its picture (Fritzing breadboard SVG), pin names and positions, which
pins do PWM / analog / I²C / SPI, voltage (5V or 3.3V), the arduino-cli FQBN and upload settings.

| Board | FQBN | Logic | Notes |
|---|---|---|---|
| Arduino Uno R3 | `arduino:avr:uno` | 5V | the default |
| Arduino Nano (ATmega328P, old bootloader option) | `arduino:avr:nano` | 5V | clones often need `:cpu=atmega328old` |
| Arduino Mega 2560 (optional) | `arduino:avr:mega` | 5V | |
| NodeMCU 1.0 (ESP-12E, ESP8266) | `esp8266:esp8266:nodemcuv2` | 3.3V | WiFi; pins labelled D0–D8 |
| Wemos / LOLIN D1 mini (ESP8266) | `esp8266:esp8266:d1_mini` | 3.3V | WiFi |
| ESP32 DevKit V1 (ESP32-WROOM-32) | `esp32:esp32:esp32` | 3.3V | WiFi + Bluetooth (ESP32 pack) |
| ESP32-C3 SuperMini (optional) | `esp32:esp32:esp32c3` | 3.3V | small, cheap (ESP32 pack) |

- **Projects say which boards they suit** (WiFi projects need an ESP). The picker shows "works with
  your board" or "needs an ESP board".
- **Wiring adapts to the board:** each project's parts connect to *roles* (`LED_PIN`, `BUTTON_PIN`,
  `I2C_SDA`...), and each board file maps roles to its pins (a standard pin plan per board, so one
  breadboard build carries between projects on that board). The wizard, the simulator, the test
  sketch and the starter code all use the same mapping, written as `#define`s at the top of the code.
- **3.3V boards:** parts that need 5V (HC-SR04 echo, some relays) get a level shifter or divider step
  in the wizard automatically, with a ⚠ safety note.

---

## 5. The Wiring Wizard (the big change from PiPath)

When a student opens a project (and before programming), a **Wiring Wizard** window opens over the
workspace (a Vista-style wizard: a glass frame, a title, step dots, Back / Next buttons):

1. **Meet the parts:** one card per component, with its Fritzing picture, what it does in one or two
   sentences, how to tell which leg is which (long leg = +, the flat side, the stripe), and a
   "Did you know?". The student presses **Next** for each part, or **Skip the introductions**.
2. **Wire it, step by step:** one connection or a small group per screen. Each screen shows:
   - the **breadboard view** (Fritzing style) with the new wire(s) highlighted and earlier ones faded
   - the **schematic view** (a toggle, or side by side on wide screens)
   - plain-English instructions ("Connect the LED's long leg to pin 13 through a 220Ω resistor")
   - a safety reminder (unplug USB while wiring)
   - **Back / Next**, and "Show the whole circuit"
3. **Test it (required):** the student plugs the board in and presses **Test**. The Pi compiles a
   **test sketch generated for this project's parts** and the browser uploads it over USB, then
   listens on the Serial port (or it runs in the simulator in Simulator mode):
   - LEDs blink one at a time; RGB LEDs cycle red, green, blue; buzzers beep; servos sweep;
     NeoPixels run a rainbow; displays show "Hello!"
   - buttons, switches, PIR, sensors: "Press the button now" and the screen ticks ✓ when the press
     arrives over serial; pots and LDRs show a live bar; HC-SR04 / DHT show live readings
   - each part has a row with ✓ / ✗ and **"I saw it work"** confirm boxes for outputs
4. **Fix it** (when a row fails): the wizard jumps back to that part's wiring screen with the most
   likely causes for that part (LED backwards, wrong row, missing GND, resistor in the wrong place),
   then **Test again**.
5. **All parts confirmed → "Start programming"** unlocks and the programming workspace opens. The
   wiring is saved as done for that project; **Wiring** in the toolbar reopens the wizard any time
   (and adding a part later in Free Play opens a mini wizard for just that part).

Test sketches are **generated from the parts list** (each part type has a test snippet with
`{pin}` placeholders and a serial protocol: `TEST:<part-id>:OK` / `READ:<part-id>:<value>`), so a
new project gets its test for free. Every generated test must compile for every board the project
supports (tested in CI, §12).

---

## 6. Simulator and diagrams: one uniform Fritzing look

- **Parts art comes from the official Fritzing parts library** (`github.com/fritzing/fritzing-parts`,
  **CC BY-SA 3.0**). The teacher has the standard library, so nothing needs sending: a script
  (`tools/import_fritzing.py` or `.go`) pulls just the parts CircuitPath uses (about 40) from the
  public repository: their **breadboard SVG**, **schematic SVG** and **connector positions** (from the
  `.fzp` file). Keep the attribution and licence in `content/parts/LICENSE-fritzing.md` and the About
  box (share-alike applies to these SVGs, not to CircuitPath's own code).
- **One renderer for everything:** the wizard, the simulator, Free Play's wiring and the project
  cards all draw from the same part SVGs and the same connector data, on the same breadboard
  (Fritzing's half+ breadboard), with wires drawn as Fritzing-style bendable wires in standard
  colours (red = 5V/3.3V, black = GND, others by signal). Schematics use the Fritzing schematic
  symbols and a tidy auto-layout.
- **Simulated behaviour** is drawn on top of the same SVGs: LEDs glow (colour from the part), RGB
  LEDs mix, NeoPixels light per pixel, servos rotate their horn, the OLED / LCD show real pixels /
  characters, 7-segment digits light, the buzzer shows sound waves and plays a tone (Web Audio).
  Students click buttons, drag pots / sliders (LDR light level, distance, temperature, humidity,
  soil moisture), wave at the PIR.
- **How the simulator runs code:** ESP boards can't be emulated at chip level in a browser with free
  tools, so CircuitPath has its own **Arduino interpreter in JavaScript** (the MakeCode approach): it
  parses the Arduino C++ subset students write (types, functions, `if`/`for`/`while`/`switch`,
  arrays, `String`, `#define`, `const`) and runs `setup()` / `loop()` in a Web Worker with a
  simulated clock, calling a **simulated Arduino API**: `pinMode`, `digitalWrite/Read`,
  `analogWrite/Read`, `delay`, `millis`, `tone`, `Serial`, `map`, `random`, and the libraries the
  projects use (Servo, Adafruit_NeoPixel, DHT, Adafruit_SSD1306 / GFX, LiquidCrystal_I2C, TM1637,
  Keypad, MFRC522, ESP8266WiFi / WiFi, WebServer / ESP8266WebServer, ESP-NOW).
  - Unsupported C++ (pointers to pointers, templates, inline asm) gives a friendly "the simulator
    can't run this part, but the real board can: press Upload" message, never a crash.
  - **WiFi in the simulator:** `WiFi.begin()` "connects" to a pretend network; a sketch's web server
    pages appear in a **phone panel** next to the board (an iframe served from the worker), so
    "control the LED from your phone" projects work fully in the simulator.
  - The real compiler is still the judge: **Upload** and **Check my code** compile on the Pi with
    arduino-cli for the chosen board, so students see real compile errors explained by the Coach.
    **Run** in the simulator is instant and doesn't need the Pi.
- **Serial Monitor + Serial Plotter** (Vista console look): shared by the simulator and real boards.

---

## 7. Saving

- **Autosave to the Pi:** code saves about a second after typing stops (and on Run / Upload / leaving
  a project); progress saves at every step. If the network blips, unsaved changes wait in the
  browser (IndexedDB) and are sent when it's back, with a small "Saved ✓ / Saving... / Offline,
  will save when you're back" note.
- **Log in anywhere:** work lives on the Pi, so a student can change laptops between lessons.
- **Save files** (students' Settings): **Save my work** downloads
  `<Name>_CircuitPath_<date>.circuit` (a zip: profile, progress, sketches; versioned), to take home
  or keep. **Open my work** loads one (merging by project, newest wins, asking before replacing).
- **Per-sketch export:** download the current sketch as `.ino` for the normal Arduino IDE.
- **Everyone's work** (Save a copy, Wipe session, Restore, nightly backups) is on the Teacher page.
- Never break the save format: the database has a schema version and migrations.

## 8. Content is data

Projects, parts, boards, errors and Free Play ideas are data files a teacher can edit without
touching code (JSON or TOML; pick one and validate it with a schema). For each project:
`id, title, tier, boards, parts, minutes, concepts, curriculum, stretch, intro, outro, steps[]`;
each step: `title, support (guided | scaffolded | brief), starter_mode, starter, text` (with a
`**Your task:**` / `**Goal:**` line for Advanced), `hints` (max 3), `error_hints`, `checks[]`,
`success`, **`demo`** (the model answer: required, played by Watch the goal and tested), and
`sim_events` (button presses, slider moves, pretend WiFi requests for the demo).

Check types (as PiPath): code contains / regex / uses a function, serial output contains / regex,
pin state seen in the simulator (`pin 13 went HIGH`, `servo reached 90°`), runs / compiles OK, run
count, "I saw it happen" confirm.

**Errors database** (`content/errors.json`): regexes over **avr-gcc / xtensa-gcc compiler messages**
and arduino-cli / upload errors, each with a plain-English title, explanation, up to 3 tiered
hints and a `tech` explanation for Advanced. Start with the classics: missing `;`, `'x' was not
declared in this scope`, missing `}` / `expected '}' at end of input`, misspelt `digitalwrite`,
`void setup` missing, `=` vs `==`, wrong library name (`No such file or directory`), upload
"port not found / busy / access denied", `avrdude: stk500_recv(): programmer is not responding`
(wrong board / old bootloader), ESP "Failed to connect to ESP8266: Timed out" (hold BOOT / FLASH),
"Sketch too big". A catch-all last. Every entry has a test with a real broken sketch.

---

## 9. Free Play (the sandbox)

The first box on the picker, always open. No steps or checklists. **Guide me** (the Coach explains
errors, nudges when stuck, suggests a tidy-up after a working run) or **On my own** (errors are
explained, nothing else). The left panel:
- **Add a part:** LED, button, buzzer, pot, servo, NeoPixel, OLED, DHT, HC-SR04... Inserts working
  code at the cursor (includes and `#define`s at the top, setup lines into `setup()`), picks free
  pins from the board's pin plan, and opens a **mini Wiring Wizard** for that part (meet it → wire it
  → test it).
- **My wiring:** the breadboard + schematic built from the parts in the sketch, with pin clashes
  flagged.
- **Need an idea?** starter projects (some screen-only with the Serial Monitor, some hardware, some
  WiFi), plus My projects and a cheat sheet.

---

## 10. Projects (first set)

Tiers: **Getting Started** (green), **Sensors & Sound**, **Displays & Lights**, **Games**,
**WiFi & IoT** (ESP boards), **Challenge**. Each project follows "one part at a time".

| Tier | Project | Parts | Boards |
|---|---|---|---|
| Getting Started | Blink & Traffic Lights | 3 LEDs, resistors | all |
| Getting Started | Button Night Light | LED, button | all |
| Getting Started | Serial Chatbot (screen only, Serial Monitor) | none | all |
| Sensors & Sound | Light Theremin | LDR, piezo buzzer | all |
| Sensors & Sound | Servo Dial | potentiometer, servo | all |
| Sensors & Sound | Parking Sensor | HC-SR04, 3 LEDs, buzzer | all (divider on 3.3V) |
| Sensors & Sound | Motion Alarm | PIR, buzzer, LED | all |
| Displays & Lights | Weather Station | DHT11/22, OLED SSD1306 | all |
| Displays & Lights | NeoPixel Mood Lamp | WS2812 ring, pot, button | all |
| Displays & Lights | Digital Dice | TM1637 4-digit display (or 7-segment), button | all |
| Displays & Lights | Plant Buddy | soil moisture sensor, OLED, LED | all |
| Games | Reaction Race (2 players) | 2 buttons, LEDs, buzzer | all |
| Games | Simon Says | 4 LEDs, 4 buttons, buzzer | all |
| Games | Joystick Snake | joystick, 8×8 LED matrix (MAX7219) | all |
| Challenge | Keypad Safe | 4×4 keypad, servo, LCD 16×2 I2C | Uno / Mega |
| Challenge | RFID Door | RC522 RFID, servo, LEDs | all |
| WiFi & IoT | Phone-controlled LED (web server) | LED | ESP |
| WiFi & IoT | Weather Web Page | DHT, ESP web server, phone panel | ESP |
| WiFi & IoT | NeoPixel Remote (sliders on a web page) | WS2812 strip | ESP |
| WiFi & IoT | Internet Clock (NTP time on the OLED) | OLED | ESP (needs internet) |
| WiFi & IoT | ESP-NOW Messenger (two boards, no router) | button, LED, buzzer (×2) | ESP ×2 |
| WiFi & IoT | WiFi Scanner Radar | OLED | ESP |

Each project lists its Victorian Curriculum DT (Levels 7–10) links and three Level up challenges.
Classroom kits differ: keep a `content/kit.json` of what the school owns, so the picker can say
"needs a part not in your kit".

---

## 11. Rules for Claude Code

1. **On the school network, private.** No calls to the internet from the web app or the server,
   except checking for and downloading CircuitPath updates from GitHub Releases (at every startup,
   and when the teacher chooses "Check for updates"); nothing about students is ever sent. No
   telemetry, no cloud accounts, no CDN fonts or scripts. Student data stays on the Pi (and in save
   files students and the teacher download).
2. **No AI**, anywhere.
3. **Nothing to install on student laptops**, ever: just Edge / Chrome. **Nothing to do on the Pi**
   but flash, insert and power on; everything else is on the Teacher page. Never require a screen,
   keyboard or SSH for normal use.
4. **Content is data** (§8). A teacher can add a project without touching code.
5. **Every project step has a `demo`** that passes its own checks in the simulator, and compiles
   with arduino-cli for every board the project lists (CI, §12). Every step has a goal for Advanced.
6. **One part at a time**, and the **Wiring Wizard + Test** before programming in every project.
7. **The simulator never freezes the page:** student code runs in a Web Worker with an instruction
   budget; `while(1)` without `delay()` gets a Coach tip, not a hung tab.
8. **Student-facing text:** Year 7 reading level, Australian spelling, encouraging.
9. **Vista look** (§2) on every screen, in one theme stylesheet.
10. **Keep it quick:** first screen in under 2 s, a project opens in under 0.5 s, the simulator runs
    smoothly at 60 fps with a dozen parts on a school laptop; the Pi 5 compiles an Uno sketch in
    ≤ 5 s and serves a class of 25.
13. **Security basics:** HTTPS only; teacher password hashed; picture passwords rate-limited;
    students can only read and write their own work; every API input validated; compiles run in a
    sandboxed temporary folder with a time and memory limit (a student's sketch can't touch the
    server); uploads of save files are size-limited and checked.
11. **Keep the tests green** after every change.
12. **Fritzing attribution** stays with the part files (CC BY-SA 3.0).

---

## 12. Testing

- **Server (Go):** unit tests for the API, accounts and picture passwords, saves (migrations), the
  compile queue and sandbox, backups, Wipe / Restore, the Teacher page's auth, and updates
  (signatures, install, rollback, plus a test where a real 1.0.0 server updates itself to 1.1.0).
- **Image (CI):** build the image, boot it in QEMU (arm64), check the server answers on 443, the
  first-login file appears, and a sketch compiles for each board. Until the image exists, the
  **Pi simulation** (`tests/pi/simulate.sh`, arm64 runner) runs `deploy/install.sh` on the real
  Raspberry Pi OS Lite userland and checks install, every board, OS updates, firewall,
  self-update and restart.
- **Interpreter + simulated API (JS):** unit tests run in headless Chromium (Playwright) or Node
  (dev-only tooling is fine; nothing runtime). Every project's every `demo` runs in the simulator
  with its `sim_events` and must pass the step's checks.
- **Compile matrix (CI):** every demo and every generated test sketch compiles with arduino-cli for
  every board it lists (GitHub Actions, caching the cores).
- **Errors database:** each entry has a real broken sketch whose compiler output must map to it.
- **GUI smoke test:** Playwright drives login → picker → a project → the Wiring Wizard (meet parts,
  wire, Test in simulator, confirm) → programming → Watch the goal → Free Play → Save my work /
  Open my work, and saves screenshots at 1366×768 and 1920×1080.
- **Real hardware checklist** (`docs/hardware-test-checklist.md`): a Pi 5 flashed from the release
  image (no screen), a no-admin Windows laptop in Edge, a genuine Uno, a CH340 Nano clone, a NodeMCU
  and an ESP32 with the kit's parts; 25 simultaneous compiles (a load-test script).

---

## 13. Build order

1. **Skeleton:** the Go server (HTTPS with its own CA, SQLite, accounts + picture passwords, autosave,
   save files), the Vista theme and window chrome, login → picker. Runs on any Linux / Mac / Windows
   for development (`go run`), with a dev certificate.
2. **Fritzing import** of the first parts (Uno, Nano, NodeMCU, ESP32, breadboard, LED, resistor,
   button, buzzer, pot, servo) and the **renderer** (breadboard + schematic, wires).
3. **Interpreter + simulated API** for the Getting Started projects; Serial Monitor (simulated).
4. **Wiring Wizard** with generated test sketches in the simulator.
5. **Compile queue** (arduino-cli, shared cache, sandbox) + the Coach on real compiler errors; then
   **Web Serial upload** (Uno / Nano first, then ESP via esptool-js) and the real Serial Monitor; the
   wizard's Test on real boards.
6. **The SD card image** (CI build, first boot, boot-partition files, LED status) and the **Teacher
   page** (status, classes, Save a copy, Wipe, Restore, updates, certificate).
7. Getting Started projects, then Free Play, then the other tiers, then WiFi & IoT (phone panel).
8. Adaptive coach, help levels, code review, curriculum in Settings.
9. Hardware checklist on a real Pi 5 + laptops, then a classroom trial.

## 14. Decisions already made (don't relitigate without reason)

- **A web app served by a headless Raspberry Pi 5** on the school network, from a **ready-made SD card
  image**: flash, insert, power on. No screen, keyboard or SSH needed; a **Teacher page** in the
  browser for everything else. (Chosen over a portable Windows app: students have no admin rights,
  unsigned exes may be blocked, and work must follow students across laptops.)
- **Upload from the browser** with Web Serial (Edge / Chrome); the Pi compiles. HTTPS is required,
  so IT trusts the Pi's certificate once.
- **USB drivers** for clone boards are IT's job (or buy driver-free boards); a server can't avoid them.
- **Work saved on the Pi** (log in anywhere) plus `.circuit` save files; nightly backups.
- **Automatic updates for everything:** CircuitPath at every startup and every night from signed
  GitHub releases (database backup first, automatic rollback if the new version won't start);
  board cores and libraries pinned per release; every Raspberry Pi OS update daily.
- **Standard Fritzing parts library** for all part art (pulled from the public repository).
- **Windows Vista skeuomorphic look** in the BNTS colours.
- **Wiring Wizard with a forced, project-specific Test** before programming.
- **Own Arduino interpreter for the simulator** (works the same for AVR and ESP boards); the simulator
  runs in the browser, so the Pi only compiles for Upload / Check my code.
- **Separate from PiPath:** different repository, no shared code.
- First name(s) + school (+ a picture password, because the server is shared). Free choice of
  projects. Stars measure independence. Help level is the student's choice. Teacher tools only for
  looking after the server; students never see them.


# PiPath: Python coding tutor for Raspberry Pi

> This file is the brief for Claude Code. Read it fully before changing anything.
> It describes what PiPath is, what already exists, the rules to follow, the data
> formats, the full curriculum, and what's left to build.

---

## 1. What PiPath is

PiPath is a desktop app that runs on a student's Raspberry Pi. It works like a
tutor sitting beside them:

1. **Login:** welcome → pick your name, or create a profile with **first name + school only**
   → straight to the **activity picker**. The workspace tour is *offered* (not forced) the
   first time a student reaches a step.
2. **Free choice:** every activity is open from day one. Tiers (Simple, Moderate,
   Advanced, Electronics Lab, Camera & AI) are a **guide**: a colour badge, a filter chip,
   and optional "Good to try first" tips. Nothing is locked, and **Free Build** is always open.
3. **Guided steps inside each activity:** instructions, starter code, a **checklist** that
   is checked automatically when the student presses Run (plus "I saw it happen" tick
   boxes for hardware), and a **Coach** that explains errors in plain English with tiered hints.
4. **Gradual release of responsibility:** early steps are *guided* (fill in the blanks,
   hints straight away). Later steps are *scaffolded*, then *brief* (just a goal, hints only
   after trying).
5. **Simulator or Real Pi (MakeCode-style):** GPIO and camera activities run on an on-screen
   board (the **Simulator**) or on the real pins and breadboard (**Real Pi**). **Watch the
   goal** plays the step's model answer on the board, so students see what *should* happen
   before they try it on real hardware.

**There is NO AI service in PiPath.** All help comes from a hand-written database of common
errors (`data/errors.toml`) and per-step hints written by the teacher. (The *Teachable
Machine* activity is machine learning the students write themselves: a nearest-neighbour
classifier over tiny greyscale grids. No model, library or internet.)

Audience: secondary students (roughly Years 7–10) who are new to text-based coding.
The author is a teacher; content is aligned to Victorian Curriculum Digital
Technologies (general-purpose programming, algorithms, data, digital systems).

---

## 2. Target platform (design for this, test on this)

| Item | Target |
|---|---|
| Hardware | **Raspberry Pi 3 Model B**: 1 GB RAM, 4-core 1.2 GHz Cortex-A53 |
| OS | Latest **Raspberry Pi OS (Desktop)**: Trixie-based, Wayland (labwc) with XWayland |
| Python | System **Python 3.13** (code must also run on 3.11+) |
| GUI | **Tkinter / Tk 8.6** (preinstalled on Pi OS Desktop as `python3-tk`) |
| GPIO | **gpiozero** (preinstalled), using the **lgpio** pin factory; mock pins in the Simulator |
| Camera | **USB webcam** (UVC, e.g. DFRobot 720p) or **ribbon** (CSI) camera; optional |
| Screen | Usually 1920×1080 monitor or 1366×768 projector; min supported 1024×640 |
| Network | Assume **none**. Everything works offline. |

Performance budget on a Pi 3B: app start < 4 s; screen switch < 400 ms; Run
button to first output < 1 s; idle CPU ~0%. Never re-highlight or re-render the
whole UI on every keystroke (the editor already debounces highlighting by 150 ms).
The board repaints only changed items; the shim reports pin states only when they change.

---

## 3. Rules for Claude Code

1. **Standard library only** (plus `gpiozero`, which ships with Pi OS). No pip installs,
   no PyQt, no web frameworks, no Electron. `tomllib` reads data files.
   The camera helper may *use* `picamera2`, `numpy` and `PIL` **when present** (they ship
   with Pi OS Desktop) but must always work without them (Simulator, V4L2, pure-Python PNG).
2. **Content is data, not code.** Lessons, the catalogue, hints, error messages, wiring and
   demos live in `data/*.toml`. A teacher must be able to add a lesson without touching Python.
3. **No AI, no network calls, no telemetry.** Student data stays on the Pi.
4. **Student-facing text:** plain English, short sentences, about Year 7 reading level,
   Australian spelling (colour, favourite, organise, recognise). Encouraging, never
   sarcastic. Errors are "clues", not "failures".
5. **No emoji in Tk widgets.** Tk 8.6 on Pi OS can't render colour emoji. Use BMP symbols
   that DejaVu Sans has: ✓ ✗ ○ ● ▶ ■ ◂ ▸ ▾ ★ ☆ ⚠ •
6. **No floating windows for UI.** Overlays (tour, tour offer, teacher panel) are frames
   drawn with `place()` inside the main window, so they behave the same on X11 and Wayland.
7. **Student code always runs in a separate process** (`pipath/runner.py`, through
   `pipath/gpio_shim.py` for GPIO/camera activities and Free Build), never `exec()` inside
   the app. The app must survive any student program.
8. **Every lesson step must have a model answer in tests**: Simple steps in
   `tests/test_hints.py`, GPIO/camera steps as the step's `demo` (run by
   `tests/test_activities.py` in the Simulator with its `demo_events`).
9. Keep `python3 -m unittest discover -s tests` green after every change.
10. Don't break the save format in `~/PiPath/`. If it must change, migrate old files.
    (Old profiles with a `class_code` still load and show it.)

---

## 4. What exists (v0.2)

Run it: `python3 main.py` (add `--scale 1.25` for big screens). Test: `python3 -m unittest discover -s tests`.

```
repo root
├── main.py                  entry point (checks Python ≥ 3.11)
├── CLAUDE.md                this file
├── README.md                teacher setup guide
├── install.sh               installs menu + desktop shortcut on a Pi
├── docs/pi-test-checklist.md  hardware test plan for a real Pi + breadboard + camera
├── data/
│   ├── config.toml          app name, teacher PIN, runaway limits, star thresholds
│   ├── catalog.toml         tiers + all activities (status ready | planned, try_first, gpio, camera)
│   ├── errors.toml          the Coach's knowledge (61 entries incl. GPIO + camera)
│   ├── demo_files/c2/examples.json   sample training data for Teachable Machine demos
│   └── lessons/
│       ├── s1_hello, s2_pibot, s3_guess        Simple (screen only)
│       ├── a1_traffic, a2_reaction, a3_alarm   Advanced GPIO
│       ├── e1_lightswitch, e2_moodlamp, e3_simon, e4_dice   Electronics Lab
│       └── c1_photobooth, c2_teachable          Camera & AI
├── pipath/
│   ├── app.py               main window, routing, activity states, teacher panel
│   ├── content.py           loads config / catalogue / lessons / errors
│   ├── storage.py           profiles, progress, code files, app state, CSV export (atomic writes)
│   ├── hints.py             Coach engine: precheck, gpio_lint, traceback parsing, matching, checks
│   ├── runner.py            runs student code: live output, stdin, runaway detection, shim pipes
│   ├── gpio.py              app-side GPIO: Pi detection, Simulator env, wiring parts, header map,
│   │                        demo event expansion, wiring-check program, camera guess
│   ├── gpio_shim.py         runs INSIDE the student process: mock/real pins, state + commands
│   ├── student_lib/
│   │   └── pipath_camera.py the students' camera helper (Simulated / USB via V4L2 / ribbon)
│   └── ui/
│       ├── theme.py         colours + named fonts (DejaVu fallbacks), tier colours
│       ├── widgets.py       PButton, RichText (mini-markdown), ScrollFrame, card, chip
│       ├── editor.py        code editor
│       ├── console.py       Output box + "type your answer" input row
│       ├── tour.py          coach-mark tour (place()-based overlay)
│       ├── onboarding.py    Welcome / profile picker, Create profile (name + school)
│       ├── home.py          activity picker (filter chips, cards, tips, stars, Free Build)
│       ├── board.py         VirtualBoard: LEDs, RGB LEDs, buttons, buzzers, PIR, camera panel
│       ├── wiring.py        Wiring + Safety card with 40-pin header map and "Check my wiring"
│       └── workspace.py     LessonWorkspace and FreeBuildWorkspace
└── tests/
    ├── test_hints.py        real broken programs → Coach entry; Simple model answers
    ├── test_storage.py      profiles: name + school, duplicates, old profiles
    ├── test_gpio.py         shim, simulated presses, GPIO errors, lint, confirm checks, wiring check
    ├── test_camera.py       V4L2 layouts + ioctl numbers, MJPEG fix-up, PNG, Simulator camera
    ├── test_activities.py   every GPIO/camera step's demo passes its checks; lesson lint
    ├── shimrun.py           helper: run code through the shim with timed presses
    └── gui_smoke.py         drives the real app under Xvfb and saves screenshots (not unittest)
```

### How a Run works (data flow)

```
Run pressed
  → precheck(code, step.starter)   blanks (___) from the starter still there? → Coach, stop
  → gpio_lint(code)                GPIO activities: warnings in the Output ("⚠ Coach tip"), never blocks
  → save file, Runner.start()      python3 -u <file>, or python3 -u pipath/gpio_shim.py <file>
                                   for GPIO/camera activities and Free Build; own process group
                                   Simulator: GPIOZERO_PIN_FACTORY=mock, MOCK_PIN_CLASS=mockpwmpin
                                   Camera: PIPATH_CAMERA=sim|usb|ribbon, PIPATH_CAMERA_OBJECT
  → poll every 40 ms               stdout → Output; student types → stdin
                                   shim state pipe → ("gpio", {...}) → board (devices, values, photos)
                                   board clicks → runner.send_command("press 23")
                                   runaway: >3000 lines, or CPU-busy + silent for 8 s → kill
  → on exit (exit code + both pipes closed)
      Stop pressed on a run_mode="until_stopped" step → treated as a normal finish
      crashed? parse_traceback() → ErrorInfo → HintEngine.diagnose() → Coach card, red line
      evaluate_checks(checks, code, stdout, crashed, runs, confirmed, folder, since)
      all pass → step done; only "confirm" boxes left → "Did you see it happen?"
```

### The shim (`pipath/gpio_shim.py`)
- Runs the student's file with `runpy` (`sys.path[0]` = the student's folder; `student_lib/` appended).
- Patches gpiozero **only when the student imports it** (import hook), recording every
  `GPIODevice` and `RGBLED`. A 50 ms thread sends `devices` / `pins` messages (JSON lines,
  fd in `PIPATH_STATE_FD`) only when something changed. Values: outputs = brightness 0–1,
  inputs = 1 when active.
- Commands (fd in `PIPATH_CMD_FD`): `press N` / `release N` (Simulator only; pull-up inputs
  are driven low), `show <object>` (simulated camera).
- Tracebacks are trimmed to start in the student's file. A crash inside an event handler
  (e.g. `when_pressed`) is reported and ends the program. SIGTERM (Stop) → `SystemExit(0)`
  so gpiozero closes devices and real LEDs switch off.
- **Real Pi mode** uses the same shim with the real pin factory: the board mirrors what the
  code tells the pins to do, so students can compare it with their breadboard.

### Storage layout (`~/PiPath`, override with `PIPATH_HOME`)

```
~/PiPath/app.json                        last_student, gpio_mode (sim|real), camera (sim|usb|ribbon)
~/PiPath/students/<slug>/profile.json    first_name, school, created, last_seen, tour_done
                                          (older profiles may also have class_code)
~/PiPath/students/<slug>/progress.json   lessons.<id>: status, step, steps_done, steps_started,
                                          hints_used, runs, errors, started, completed
~/PiPath/students/<slug>/lessons/*.py    lesson code (one file per activity, built up step by step)
~/PiPath/students/<slug>/lessons/*.jpg|csv|json   photos, logs, examples.json written by programs
~/PiPath/students/<slug>/lessons/backups/  code saved before a "replace" step overwrote it
~/PiPath/students/<slug>/projects/*.py   Free Build projects
~/PiPath/exports/progress_<date>.csv     teacher export
```

---

## 5. Data formats

### 5.1 `catalog.toml`

```toml
[[tier]]          # id, title, tagline, description. Order = order on the activity picker
[[project]]
id = "a1_traffic"         # also the lesson file name: data/lessons/a1_traffic.toml
tier = "advanced"
title, subtitle, concepts = [..], minutes, support = "scaffolded"
status = "ready"          # ready | planned ("Coming soon" card)
try_first = ["s3_guess"]  # optional tip "Good to try first: ...", hidden once those are done
gpio = true               # optional: card says "needs GPIO kit"
camera = true             # optional: card says "needs camera"
parts = [..]              # optional: shopping list, shown in the Wiring card
```

Nothing is locked; `unlock_after` and `free_build_unlock` are gone.

### 5.2 Lesson file (`data/lessons/<id>.toml`)

```toml
id = "a1_traffic"
title = "Traffic Lights"
file_name = "traffic_lights.py"     # what the student's file is called
intro = """markdown"""              # shown before step 1
outro = """markdown"""              # shown on completion with stars + extension ideas
requires_gpio = true                # Wiring card, Simulator / Real Pi switch, board
requires_camera = true              # camera panel on the board (click its title to switch camera)

[[wiring]]                          # one row per part (rows without kind are tips)
part = "Red LED"                    # name in the card and on the board
kind = "led"                        # led | rgbled | button | switch | buzzer | pir
pin = 17                            # GPIO (BCM) number; rgbled uses pins = [r, g, b]
colour = "red"                      # led colour on the board: red amber yellow orange green blue white
connect = "GPIO17 (pin 11) → 330Ω → long leg; short leg → GND"

[[steps]]
title = "Keep guessing with a loop"
support = "guided" | "scaffolded" | "brief"
starter_mode = "replace" | "append" | "keep"   # applied the FIRST time a step is entered
starter = '''code'''                # may contain ___ blanks
run_mode = "until_stopped"          # program runs until Stop; checks evaluated when Stop is pressed
text = """markdown instructions"""
hints = ["nudge", "more specific", "almost the answer"]   # max 3
error_hints = { TypeError = "step-specific hint shown first for this error type" }
success = "message when every check passes"
demo = '''model answer'''           # played by "Watch the goal" (Simulator), tested in tests/
demo_events = ["2 tap 23", "1.5 press 4", "3 release 4", "0.5 show ball",
               "1 tap 23 every 0.8 until 30"]   # timed presses / camera objects during the demo
demo_seconds = 10                   # stop the demo after this long (until_stopped programs)
demo_input = "5\n"                  # typed into input() during the demo
demo_files = ["c2/examples.json"]   # copied from data/demo_files/ into the demo's folder

[[steps.checks]]
type = "output_contains"
value = "You got it"
label = "You played until you won"      # shown in the checklist
fail = "shown in the Coach if this is the first failing check"
ignore_case = true                       # optional
```

In TOML `'''literal'''` strings backslashes are literal: write `\n` (not `\\n`) in `demo`
code, and `\\n` in `"""basic"""` strings such as `text`.

Mini-markdown supported by `RichText`: `## heading`, `**bold**`, `*italic*`, `` `code` ``,
`- bullets`, `1. numbered`, fenced ``` code blocks ```.

### 5.3 Check types

| type | passes when | extra keys |
|---|---|---|
| `runs_ok` | the program didn't crash | |
| `output_contains` | stdout contains `value` (case-insensitive by default) | `ignore_case` |
| `output_regex` | regex `value` matches stdout | `ignore_case` |
| `output_lines_min` | at least `min` non-blank output lines | `min` |
| `code_contains` | source contains `value` | |
| `code_regex` | regex `value` matches source (multiline) | `ignore_case` |
| `code_uses` | AST feature present (see below) | |
| `code_count` | AST feature appears at least `min` times | `min` |
| `run_count_min` | student pressed Run at least `min` times this step | `min` |
| `confirm` | student ticked "I saw it happen" (only allowed after a run) | |
| `file_exists` | at least `min` files matching glob `value` were written **this run** | `min` |
| `file_contains` | a file matching glob `file`, written this run, matches regex `value` | `file`, `ignore_case` |

AST features from `hints.code_features()`: `call:print`, `call:randint` (function or
method name), `import:random`, `import:LED` (names from `from x import y`),
`attr:upper`, `attr:when_pressed`, `node:While` / `node:For` / `node:If` /
`node:FunctionDef` / `node:Return` / `node:Break` / `node:List` / `node:Dict` / `node:Try`
(any `ast` node class), `fstring`, `elif`.

**Unknown check types pass**, so a lesson written for a newer PiPath never blocks a student.

### 5.4 `errors.toml`

```toml
[[error]]
id = "concat_str_number"            # unique, used in tests
type = "TypeError"                  # last segment of the exception name; "*" = catch-all
message = '''regex with (?P<named>groups)'''   # optional, searched in the message
code = '''regex'''                  # optional, searched in the broken line of code
title = "Can't join text and a number with +"
explain = "markdown. {line}, {code_line}, {type}, {message} and named groups are filled in"
hints = ["up to 3, nudge → near-answer"]
```

First match wins, so **specific entries go above general ones**. The file ends with a
`*` catch-all. Internal types: `PiPathBlanks` (blanks left), `PiPathRunaway` with
message `output`, `busy_gpio` (a busy loop that polls `is_pressed` etc.) or `busy`.
Camera types: `CameraNotFound`, `CameraBusy` (raised by `pipath_camera`). Write `{{` `}}`
for literal braces.

**When adding an entry, add a test case** (`tests/test_hints.py`, or `tests/test_gpio.py`
for GPIO errors with mock pins) with a real broken program.

---

## 6. Gradual release model

| support | badge | step hints unlock | error hints shown | typical use |
|---|---|---|---|---|
| `guided` | GUIDED (green) | immediately | all 3 tiers | blanks to fill, code given |
| `scaffolded` | SOME HELP (blue) | after 1 failed run | all 3 tiers | instructions + examples, student writes code |
| `brief` | ON YOUR OWN (red) | after 2 failed runs | first 2 tiers only (no near-answer) | goal + checklist only |

- Error **explanations** are always shown. Understanding errors is a learning goal.
- Every hint revealed adds to `hints_used`. **Independence stars:** ≤2 hints ★★★,
  ≤6 ★★, else ★ (thresholds in `config.toml`). Stars are framed positively.
- Within an activity, support should fade: at least one `brief` step per activity from S3 on.
- Because students choose freely, the first step of each activity can drop back a level.

---

## 7. Curriculum: all activities

Legend: ✅ written, playable and tested in the Simulator · 🔲 outline only (write the TOML)

Standard pin plan for **all** GPIO activities (Pi 3B, BCM numbers), so one breadboard build
carries between activities:

| Part | GPIO | Physical pin |
|---|---|---|
| Red LED / LED 1 | 17 | 11 |
| Amber/Green LED / LED 2 | 27 | 13 |
| Green/Blue LED / LED 3 | 22 | 15 |
| LED 4, 5, 6 | 5, 6, 13 | 29, 31, 33 |
| Button 1 / 2 / 3 | 23 / 24 / 25 | 16 / 18 / 22 |
| Buzzer (active) | 18 | 12 |
| PIR motion sensor OUT | 4 | 7 (VCC → 5V pin 2, GND → pin 6) |
| GND | | 6, 9, 14, 20, 25, 30, 34, 39 |

Avoid GPIO 2/3 (I²C, fixed pull-ups) and 14/15 (serial console).

| Tier | Activity | Status | Steps (support) |
|---|---|---|---|
| Simple | S1 Hello, Pi! | ✅ | run · name blank · 3 prints · bug hunt (G) · ASCII art (S) |
| Simple | S2 Meet PiBot | ✅ | variables · input + f-string (G) · `input()+1` bug · `.upper()` (S) · own question (B) |
| Simple | S3 Guess My Number | ✅ | randint · if/else · elif · while (S) · counter 1–100 (B) |
| Moderate | M1 Quiz Master | 🔲 | see outline below |
| Moderate | M2 Turtle Art Studio | 🔲 | see outline below |
| Moderate | M3 Tuckshop Till | 🔲 | see outline below |
| Advanced | A1 Traffic Lights | ✅ | flash one LED (G) · green→amber→red (S) · `def cycle()` + `while True` (S) · pedestrian `wait_for_press` (S) · beeper + flashing red (B) |
| Advanced | A2 Reaction Timer | ✅ | random wait (S) · `monotonic()` stopwatch (S) · false start with `wait_for_press(timeout=)` (S) · 2-player `when_pressed` race (B) · best of 5 + `highscore.txt` with try/except (B) |
| Advanced | A3 Motion Alarm & Logger | ✅ | `when_motion` / `when_no_motion` (S) · LED + `buzzer.beep` (S) · armed state + button (B) · CSV log with `datetime` (B) · 10 s cooldown + report by hour (B) |
| Lab | E1 Light Switch Lab | ✅ | LED · `wait_for_press` (G) · hold-to-light · toggle (S) · PWM dimmer (B) |
| Lab | E2 RGB Mood Lamp | ✅ | tuples · rainbow nested loop · `%` wrap, planted IndexError (S) · party mode `when_held` · own lamp (B) |
| Lab | E3 Simon Says | ✅ | lists of LEDs · `zip()` · random pattern · `get_press()` returns (S) · full game (B) |
| Lab | E4 Bar Graph & Digital Dice | ✅ | LEDBoard · scanner · counter with limits (S) · dice roll · shake to roll (B) |
| Camera & AI | C1 Photo Booth | ✅ | `take_photo` (G) · button to snap (G) · LED 3-2-1 + beep (S) · `datetime` names + loop (S) · 4-photo strip + `glob` count (B) |
| Camera & AI | C2 Teachable Machine | ✅ | `capture_grid` as `#`/`.` art (S) · collect labelled examples → `examples.json` (S) · `distance()` with `abs()` (S) · nearest-neighbour `classify()` lights the matching LED (S) · accuracy test (B) |

Camera activities use the students' helper `from pipath_camera import Camera`
(`take_photo(name)`, `capture_grid(rows, cols)`). The Simulator's pretend camera shows a
face, ball, box or nothing (picked on the board); a nearest-neighbour classifier gets
about 90% on its ball/box pictures.

### Moderate outlines (still to write; set `status = "ready"` when done)

**M1 Quiz Master** (scaffolded → brief, ~40 min)
1. (S) One question with `input()` + `if` + `score = 0 / score += 1`.
2. (S) Questions and answers in two **lists**; loop with `for q, a in zip(questions, answers)`.
3. (S) Accept "Canberra", " canberra " etc: `.strip().lower()`. Planted bug: comparing without normalising.
4. (S) Write `def ask(question, answer):` that **returns** True/False; loop calls it.
5. (B) Final score as a percentage with a message band (`if pct >= 80`), `random.shuffle` the questions.

**M2 Turtle Art Studio** (scaffolded → brief, ~40 min). Square with `forward()`/`left(90)` ×4
(G) · `for i in range(4)` (S) · `def polygon(sides, size)` (S) · rotating pattern with
`colours[i % len(colours)]` (S) · own art (B). Use `run_mode = "until_stopped"` and
`confirm` checks; `speed(0)` on the Pi 3B; friendly entry for `turtle.Terminator`.

**M3 Tuckshop Till** (brief, ~50 min). Menu dictionary + `f"${price:.2f}"` · order loop with
`if item in menu` · total + GST (total ÷ 11) receipt · save receipt with `datetime` ·
append to `sales.csv` and read back the day's takings.

### Free Build
Always open. Projects list, new project (names that shadow modules like `random.py` are
refused), cheat sheet, Coach without checklists. Runs through the shim, so the Simulator
board (and camera panel) appears as soon as a program makes an LED, Button or photo.

---

## 8. GPIO + camera design (as built)

- **Simulator / Real Pi** switch in the workspace toolbar (`Run on:`). Real Pi is disabled
  off a Pi (`/proc/device-tree/model`; `PIPATH_FORCE_SIM=1` pretends). Saved per Pi in app.json.
- **Board** (`ui/board.py`): parts from the lesson's `[[wiring]]` rows (in order), plus any
  device the program makes. Click and hold buttons; click the PIR to "wave" (3 s). The
  board switches everything off when a program ends, like real hardware.
- **Watch the goal**: runs the step's `demo` in a temp folder on the Simulator with its
  `demo_events`; the student's code isn't touched and the run isn't counted.
- **Wiring + Safety card** (`ui/wiring.py`): safety list, parts, connect rows, 40-pin header
  map with the activity's pins highlighted, and **Check my wiring** (a generated program
  that blinks each LED, beeps the buzzer and waits for each button / the PIR; ✓/✗ ticks).
- **Lint** (`hints.gpio_lint`): `when_pressed = f()` brackets, `while True` that never
  waits, a pin used twice, pins outside 2–27 or special pins.
- **Camera** (`student_lib/pipath_camera.py`): `sim` (pure Python, PNG), `usb` (V4L2 via
  ctypes/ioctl/mmap: MJPEG for photos with standard Huffman tables added if missing, YUYV
  for grids; Picamera2 fallback), `ribbon` (Picamera2, or `rpicam-still`). Photos and grid
  previews are sent to the board's camera panel; click its title to switch camera
  (saved per Pi).
- Safety panel text lives in `gpio.SAFETY` (also in the README).

---

## 9. Teacher features

Present now: Ctrl+Shift+T → PIN (config.toml `teacher_pin`) → teacher mode (Next step
always enabled for this session) and **Export progress CSV**.

To build:
- Change the PIN from the panel (store a hash in `~/PiPath/app.json`, not in plain text).
- Per-class view: table of students × activities (status, stars, runs, errors, hints).
- Reset a student's activity; delete a student (with confirm); "end of term" archive to a zip.
- Import lessons from a USB stick (`/media/*/PiPath-lessons/*.toml`) after validating them.
- "Lesson lint" command: `python3 -m pipath.lint data/lessons/x.toml` (the checks in
  `tests/test_activities.py::TestLessonFiles` are a starting point).

---

## 10. Deployment

- `install.sh`: adds a menu entry (Programming → PiPath) and a desktop icon; optional `--autostart`.
- Classroom roll-out: set up one Pi fully, then clone the SD card (Raspberry Pi
  **SD Card Copier** or Imager) for the class set.
- Updates: `git pull`, or copy a new `data/` folder from USB. Student work in `~/PiPath`
  is never touched by updates.
- Pi OS Desktop already has `python3-tk`, `python3-gpiozero`, `python3-lgpio`,
  `python3-picamera2`. On Lite images:
  `sudo apt install python3-tk python3-gpiozero python3-lgpio python3-picamera2`.

---

## 11. What's next

Built and passing in the Simulator: the GPIO foundation, A1–A3, the Electronics Lab and the
Camera & AI tier. Still to do, roughly in this order:

1. **Real hardware check** (docs/pi-test-checklist.md): Pi 3B on Trixie with a breadboard
   kit, a USB webcam and a ribbon camera. Record timings in `docs/perf.md`.
2. **Moderate tier**: write M1–M3 from §7 with model answers; M2 needs `confirm` +
   `until_stopped` (both built).
3. **Phase 1 polish**: undo/redo buttons, "Reset step code", underline the exact word from
   the `^^^^` markers, `--scale` per student, high-contrast theme, 80+ errors.toml entries,
   a hidden log of entry ids hit per student.
4. **Teacher tools** (§9).
5. **Classroom trial**: export CSVs; rewrite the steps with the most runs, errors and hints.

---

## 12. Testing

- `tests/test_hints.py` runs **real broken programs** with the current interpreter and
  asserts the Coach entry id; holds Simple model answers.
- `tests/test_activities.py` runs **every GPIO/camera step's `demo`** through the shim on
  mock pins with its `demo_events` (in parallel) and checks it passes the step's checks;
  starters must start cleanly; every lesson file is linted.
- `tests/test_gpio.py`, `tests/test_camera.py`, `tests/test_storage.py` cover the engine.
  GPIO tests skip if gpiozero isn't installed.
- GUI smoke test: `xvfb-run -s "-screen 0 1366x768x24" python3 tests/gui_smoke.py shots/`
  drives login → activities → lessons → Simulator → Watch the goal → camera and saves
  screenshots (needs Tk, Xvfb, ImageMagick `import`).
- Manual Pi checklist: `docs/pi-test-checklist.md`.

---

## 13. Decisions already made (don't relitigate without reason)

- **Tkinter over a Thonny plugin.** Full control of onboarding, the guide panel and gradual
  release; light enough for a Pi 3B.
- **TOML for content**: readable, comments allowed, multi-line literal strings for code.
- **First name + school only.** No class, surnames, emails or photos of students in profiles.
  Duplicate name + school → suggest adding a surname initial.
- **Free choice.** Every activity is open; tiers are a guide (badge, filter, try_first tips).
- **Simulator first, then real hardware**, MakeCode-style, with Watch the goal.
- **One camera helper for students** (`pipath_camera`) so the same code works with a USB
  webcam, a ribbon camera or the Simulator; the outro shows the real Picamera2 code.
- **Blanks are `___`** (3+ underscores), detected only on lines copied from the step's
  starter, so students' own ASCII art with underscores still runs.
- **Stars measure independence (hints), not speed.**

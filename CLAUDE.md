# PiPath: Python coding tutor for Raspberry Pi

> This file is the brief for Claude Code. Read it fully before changing anything.
> It describes what PiPath is, what already exists, the rules to follow, the data
> formats, the full curriculum, and the build plan, phase by phase.

---

## 1. What PiPath is

PiPath is a desktop app that runs on a student's Raspberry Pi. It works like a
tutor sitting beside them:

1. **Onboarding:** welcome → create a profile (first name, school, class) → 4 intro
   slides → a guided tour of the workspace.
2. **Guided projects:** a step-by-step walkthrough. Each step has instructions,
   starter code, a **checklist** that is checked automatically when the student
   presses Run, and a **Coach** that explains errors in plain English with tiered hints.
3. **Gradual release of responsibility:** early steps are *guided* (fill in the
   blanks, hints straight away). Later steps are *scaffolded*, then *brief* (just a
   goal, hints only after trying).
4. **Progression:** 3 Simple → 3 Moderate → 3 Advanced (GPIO) projects, plus an
   optional 4-project **Electronics Lab**. Then **Free Build** unlocks: a blank space
   where the Coach still explains errors.

**There is NO AI in PiPath.** All help comes from a hand-written database of common
errors (`data/errors.toml`) and per-step hints written by the teacher.

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
| GPIO | **gpiozero** (preinstalled), using the **lgpio** pin factory |
| Screen | Usually 1920×1080 monitor or 1366×768 projector; min supported 1024×640 |
| Network | Assume **none**. Everything works offline. |

Performance budget on a Pi 3B: app start < 4 s; screen switch < 400 ms; Run
button to first output < 1 s; idle CPU ~0%. Never re-highlight or re-render the
whole UI on every keystroke (the editor already debounces highlighting by 150 ms).

---

## 3. Rules for Claude Code

1. **Standard library only** (plus `gpiozero`, which ships with Pi OS). No pip installs,
   no PyQt, no web frameworks, no Electron. `tomllib` reads data files.
2. **Content is data, not code.** Lessons, the catalogue, hints and error messages live in
   `data/*.toml`. A teacher must be able to add a lesson without touching Python.
3. **No AI, no network calls, no telemetry.** Student data stays on the Pi.
4. **Student-facing text:** plain English, short sentences, about Year 7 reading level,
   Australian spelling (colour, favourite, organise). Encouraging, never sarcastic.
   Errors are "clues", not "failures".
5. **No emoji in Tk widgets.** Tk 8.6 on Pi OS can't render colour emoji. Use BMP symbols
   that DejaVu Sans has: ✓ ✗ ○ ● ▶ ■ ◂ ▸ ★ ☆ ⚠ •
6. **No floating windows for UI.** Overlays (tour, teacher panel, dialogs) are frames
   drawn with `place()` inside the main window, so they behave the same on X11 and Wayland.
7. **Student code always runs in a separate process** (`pipath/runner.py`), never `exec()`
   inside the app. The app must survive any student program.
8. **Every lesson step must have a model answer in `tests/`** that passes its checks.
9. Keep `python3 -m unittest discover -s tests` green after every change.
10. Don't break the save format in `~/PiPath/`. If it must change, migrate old files.

---

## 4. What already exists (prototype v0.1)

Run it: `python3 main.py` (add `--scale 1.25` for big screens). Test: `python3 -m unittest discover -s tests`.

```
pipath/                      repo root
├── main.py                  entry point (checks Python ≥ 3.11)
├── CLAUDE.md                this file
├── README.md                teacher setup guide
├── install.sh               installs menu + desktop shortcut on a Pi
├── data/
│   ├── config.toml          app name, teacher PIN, unlock rule, runaway limits, star thresholds
│   ├── catalog.toml         tiers + all 13 projects (status ready | planned)
│   ├── errors.toml          ~60 common-error entries (the Coach's knowledge)
│   └── lessons/
│       ├── s1_hello.toml    READY   print, strings, comments, bug hunt
│       ├── s2_pibot.toml    READY   variables, input(), f-strings, int()
│       ├── s3_guess.toml    READY   random, if/elif/else, while, counters
│       ├── e1_lightswitch.toml  WRITTEN, needs GPIO support (Phase 3)
│       ├── e2_moodlamp.toml     WRITTEN, needs GPIO support
│       ├── e3_simon.toml        WRITTEN, needs GPIO support
│       └── e4_dice.toml         WRITTEN, needs GPIO support
├── pipath/
│   ├── app.py               main window, screen routing, unlock rules, teacher panel
│   ├── content.py           loads config / catalogue / lessons / errors
│   ├── storage.py           profiles, progress, code files, CSV export (atomic writes)
│   ├── hints.py             the Coach engine: precheck, traceback parsing, matching, checks
│   ├── runner.py            runs student code: live output, stdin, runaway detection
│   └── ui/
│       ├── theme.py         colours + named fonts (DejaVu fallbacks)
│       ├── widgets.py       PButton, RichText (mini-markdown), ScrollFrame, card, chip
│       ├── editor.py        code editor: line numbers, syntax colours, 4-space tabs, auto-indent,
│       │                    error-line highlight, curly-quote fixing on paste, zoom
│       ├── console.py       Output box + "type your answer" input row
│       ├── tour.py          coach-mark tour (place()-based overlay)
│       ├── onboarding.py    Welcome / profile picker, Create profile, Intro slides
│       ├── home.py          project map (tiers, cards, stars, Free Build)
│       └── workspace.py     LessonWorkspace (guide + checklist + Coach) and FreeBuildWorkspace
└── tests/test_hints.py      29 real broken programs → expected Coach entry; model answers for
                             every Simple step; blank-detection tests
```

### How a Run works (data flow)

```
Run pressed
  → precheck(code, step.starter)   blanks (___) from the starter still there? → Coach, stop
  → save file, Runner.start()      python3 -u <file> in the student's folder, own process group
  → poll every 40 ms               stdout → Output box; student types → stdin
                                   runaway: >3000 lines, or CPU-busy + silent for 8 s → kill
  → on exit (exit code + both pipes closed)
      crashed? parse_traceback() → ErrorInfo(type, message, line, code_line)
               HintEngine.diagnose() → first matching errors.toml entry (+ step error_hints first)
               → Coach card (title, explanation, "Line N" + code, tiered hints), red editor line
      evaluate_checks(step.checks, code, stdout, crashed, runs_this_step)
      all pass → step done, Next unlocked, Coach "Step complete"
      some fail → Coach "Almost there" with the first failing check's `fail` message
```

### Storage layout (`~/PiPath`, override with `PIPATH_HOME`)

```
~/PiPath/app.json                        last student
~/PiPath/students/<slug>/profile.json    first_name, school, class_code, created, last_seen, tour_done
~/PiPath/students/<slug>/progress.json   lessons.<id>: status, step, steps_done, steps_started,
                                          hints_used, runs, errors, started, completed
~/PiPath/students/<slug>/lessons/*.py    lesson code (one file per lesson, built up step by step)
~/PiPath/students/<slug>/lessons/backups/  code saved before a "replace" step overwrote it
~/PiPath/students/<slug>/projects/*.py   Free Build projects
~/PiPath/exports/progress_<date>.csv     teacher export
```

---

## 5. Data formats

### 5.1 `catalog.toml`

```toml
[[tier]]          # id, title, tagline, description. Order = order on the map
[[project]]
id = "s1_hello"           # also the lesson file name: data/lessons/s1_hello.toml
tier = "simple"
title, subtitle, concepts = [..], minutes, support = "guided → scaffolded"
status = "ready"          # ready | planned ("Coming soon" card)
gpio = true               # optional: shows "needs GPIO kit"
parts = [..]              # optional: shopping list for the kit
unlock_after = "a1_traffic"  # optional: unlock when that project is complete (default: previous project)
```

### 5.2 Lesson file (`data/lessons/<id>.toml`)

```toml
id = "s3_guess"
title = "Guess My Number"
file_name = "guess_my_number.py"   # what the student's file is called
intro = """markdown"""              # shown before step 1
outro = """markdown"""              # shown on completion with stars + extension ideas
requires_gpio = true                # (Phase 3) wiring card + Practice mode

[[wiring]]                          # (Phase 3) one row per part
part = "LED"
connect = "GPIO17 (pin 11) → 330Ω → long leg; short leg → GND (pin 9)"

[[steps]]
title = "Keep guessing with a loop"
support = "guided" | "scaffolded" | "brief"
starter_mode = "replace" | "append" | "keep"   # applied the FIRST time a step is entered
starter = '''code'''                # may contain ___ blanks
run_mode = "until_stopped"          # (Phase 3) evaluate checks when the student presses Stop
text = """markdown instructions"""
hints = ["nudge", "more specific", "almost the answer"]   # max 3
error_hints = { TypeError = "step-specific hint shown first for this error type" }
success = "message when every check passes"

[[steps.checks]]
type = "output_contains"
value = "You got it"
label = "You played until you won"      # shown in the checklist
fail = "shown in the Coach if this is the first failing check"
ignore_case = true                       # optional
```

Mini-markdown supported by `RichText`: `## heading`, `**bold**`, `*italic*`, `` `code` ``,
`- bullets`, `1. numbered`, fenced ``` code blocks ```. In TOML, use `'''literal'''` strings
for code and regexes (no escaping needed).

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
| `confirm` | **(to build, Phase 3)** student ticks "I saw it happen" in the checklist | |

AST features from `hints.code_features()`: `call:print`, `call:randint` (function or
method name), `import:random`, `import:LED` (names from `from x import y`),
`attr:upper`, `attr:when_pressed`, `node:While` / `node:For` / `node:If` /
`node:FunctionDef` / `node:Return` / `node:Break` / `node:List` (any `ast` node class),
`fstring`, `elif`.

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
message `output` or `busy`. Write `{{` `}}` for literal braces.

**When adding an entry, add a test case to `tests/test_hints.py`** with a real broken
program, so the regex is checked against real Python 3.13 messages.

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
- Within a lesson, support should fade: at least one `brief` step per lesson from S3 on.
- Across the course, the first step of each lesson can drop back one level (new concept).

---

## 7. Curriculum: all projects

Legend: ✅ written & playable · 📝 lesson file written, needs GPIO support · 🔲 outline only (write the TOML)

### SIMPLE: Python on the screen (✅ all three)

| | Project | Steps (support) | Key concepts |
|---|---|---|---|
| S1 | **Hello, Pi!** | run first program (G) · fill name blank (G) · 3 print lines (G) · **bug hunt**: 2 planted bugs (G) · ASCII art (S) | print, strings, comments, reading errors |
| S2 | **Meet PiBot** | variables (G) · input + f-string blank (G) · **the famous bug** `input()+1` (S) · `.upper()` (S) · own question (B) | variables, input, f-strings, int(), types |
| S3 | **Guess My Number** | randint, run twice (S) · if/else with `==` blank (S) · elif too high/low (S) · while loop with `!=` blank (S) · counter + 1–100 (B) | random, conditions, loops, counters |

### MODERATE: bigger programs (🔲 write these lesson files in Phase 2)

**M1 Quiz Master** (scaffolded → brief, ~40 min)
1. (S) One question with `input()` + `if` + `score = 0 / score += 1`.
2. (S) Questions and answers in two **lists**; loop with `for q, a in zip(questions, answers)`.
3. (S) Accept "Canberra", " canberra " etc: `.strip().lower()`. Planted bug: comparing without normalising.
4. (S) Write `def ask(question, answer):` that **returns** True/False; loop calls it.
5. (B) Final score as a percentage with a message band (`if pct >= 80`), `random.shuffle` the questions.
Checks: `node:FunctionDef`, `node:Return`, `call:lower`, `output_regex` for a % score.
Errors to add: `IndexError` when lists are different lengths (step-specific hint).

**M2 Turtle Art Studio** (scaffolded → brief, ~40 min)
1. (G) Draw a square with `forward()` / `left(90)` ×4, ending with `turtle.done()`.
2. (S) Replace repetition with `for i in range(4)`.
3. (S) `def polygon(sides, size)`: turn angle `360 / sides`; draw a triangle, hexagon, octagon.
4. (S) Pattern: rotate a polygon 36 times with a list of colours (`colours[i % len(colours)]`).
5. (B) Draw your initials, a scene or random "modern art".
Notes: turtle opens its own window **in the student process**, so it's fine. Use
`run_mode = "until_stopped"` (window closes = program ends) and `confirm` checks
("I can see my shape"). Turtle speed: `speed(0)` on the Pi 3B.
Errors: `turtle.Terminator` when the window is closed mid-draw (friendly "you closed the
window"), shadowed module if a project is named `turtle.py` (already handled).

**M3 Tuckshop Till** (brief, ~50 min, links to Business Management)
1. (S) Menu **dictionary** `{"sausage roll": 4.50, ...}`; print it with `f"${price:.2f}"`.
2. (S) Order loop: `while True`, type an item or `done`; check `if item in menu` (planted KeyError).
3. (S) Running total and **GST**: Australian prices include GST, so GST = total ÷ 11. Print a receipt.
4. (B) Save the receipt to `receipt_<time>.txt` with `open(..., "w")` and `datetime`.
5. (B) Append each sale to `sales.csv` and print the day's takings by reading it back.
Checks: `node:Dict`, `call:open`, `output_regex '\$\d+\.\d{2}'`.

### ADVANCED: electronics with GPIO (🔲 write in Phases 3–4)

Standard pin plan for **all** GPIO lessons (Pi 3B, BCM numbers). Keep it consistent so
one breadboard build carries between projects:

| Part | GPIO | Physical pin |
|---|---|---|
| Red LED / LED 1 | 17 | 11 |
| Amber/Green LED / LED 2 | 27 | 13 |
| Green/Blue LED / LED 3 | 22 | 15 |
| LED 4, 5, 6 | 5, 6, 13 | 29, 31, 33 |
| Button 1 / 2 / 3 | 23 / 24 / 25 | 16 / 18 / 22 |
| Buzzer | 18 | 12 |
| PIR motion sensor OUT | 4 | 7 (VCC → 5V pin 2, GND → pin 6) |
| GND | | 6, 9, 14, 20, 25, 30, 34, 39 |

Avoid GPIO 2/3 (I²C, fixed pull-ups) and 14/15 (serial console).

**A1 Traffic Lights** (scaffolded, ~45 min). Parts: 3 LEDs, 3 × 330Ω, 1 button.
1. (G) Blink one LED: `LED(17)`, `on()`, `sleep()`, `off()`.
2. (S) Three LEDs in the **Australian** sequence: green → amber (~3 s) → red (no red+amber phase).
3. (S) `def cycle():` and `while True: cycle()` (`until_stopped`).
4. (S) Pedestrian button: green stays on until `button.wait_for_press()`, then cycle.
5. (B) Add a "walk" beeper with `Buzzer(18)` or a flashing red "don't walk" phase. Bonus: `gpiozero.TrafficLights`.

**A2 Reaction Timer** (scaffolded → brief, ~50 min). Parts: LED, 2 buttons, optional buzzer.
1. (S) Random delay `sleep(random.uniform(2, 5))`, then LED on.
2. (S) Time one player: `start = time.monotonic()`, `wait_for_press()`, print reaction in ms.
3. (S) False start: if the button is already pressed before the LED, "Too soon!".
4. (B) Two players: `when_pressed` callbacks; the first to press wins (a `winner = None` variable).
5. (B) Best of 5 and a **high score file** (`open("highscore.txt")`, handle FileNotFoundError).

**A3 Motion Alarm & Logger** (brief, ~60 min). Parts: PIR HC-SR501, buzzer, LED, button.
1. (S) `MotionSensor(4)`: print "Motion!" with `when_motion` (allow 30–60 s for the PIR to settle).
2. (S) Alarm: LED + `buzzer.beep(0.1, 0.1, n=5)`.
3. (B) Arm/disarm with the button: an `armed` **state** variable plus LED status.
4. (B) Log each event to `motion_log.csv` with `datetime.now().isoformat()`.
5. (B) Report: read the CSV back and print events per hour; add a 10 s cooldown.
Safety note in the lesson: the HC-SR501's OUT pin is 3.3 V, safe for GPIO; never wire a 5 V output straight to a GPIO pin.

### ELECTRONICS LAB: extra lights & inputs (📝 lesson files written; enable in Phase 4)

Optional, any order, unlock after A1 (`unlock_after = "a1_traffic"`). Every starter in
these files has been run against gpiozero's **mock pins** and starts cleanly.

| | Project | Steps | New ideas |
|---|---|---|---|
| E1 | **Light Switch Lab** | LED on/off (G) · `wait_for_press` (G) · hold-to-light with `when_pressed/when_released` (S) · toggle switch (S) · **dimmer**: PWMLED brightness levels with list + function + `%` (B) | events, methods as values (no brackets), `pause()`, PWM |
| E2 | **RGB Mood Lamp** | mix colours with tuples (S) · rainbow list + nested loop (S) · button cycles colours, planted **IndexError** → fix with `%` (S) · party mode with `when_held` + random (B) · design your own lamp (B) | RGBLED, tuples, modulo wrap-around, long press |
| E3 | **Simon Says** | lists of LEDs (S) · `zip()` buttons to LEDs (S) · random pattern + `flash()` function (S) · `get_press()` that **returns** (S) · full game loop with growing pattern + score (B) | lists of objects, zip, return values, game loop |
| E4 | **Bar Graph & Digital Dice** | LEDBoard patterns (S) · scanner animation (S) · up/down counter, planted out-of-range bug → **limits** (S) · roll animation + randint(1,6) (B) · **shake to roll** with a tilt switch (B) | LEDBoard, LEDBarGraph, limits, any switch is a button |

E1–E4 use these new lesson keys, which Phase 3 must implement: `requires_gpio`,
`[[wiring]]`, `run_mode = "until_stopped"`, and check type `confirm`.

### FREE BUILD (✅)
Unlocks when every *ready* project in the tier named by `free_build_unlock` is done
(default `"simple"`). Projects list, new project (name validated; names that shadow
modules like `random.py` are refused), cheat sheet, Coach without checklists.
Phase 3 adds GPIO Practice mode here too.

---

## 8. GPIO support: design (Phase 3)

### 8.1 Real Pi vs Practice mode
- Detect a real Pi: `/proc/device-tree/model` contains "Raspberry Pi".
- **Practice mode** (toggle in the workspace toolbar; forced on when not on a Pi) runs the
  student program with:
  `GPIOZERO_PIN_FACTORY=mock` and `GPIOZERO_MOCK_PIN_CLASS=mockpwmpin`
  (PWM is required for PWMLED/RGBLED, as tested). Pass these through `Workspace.extra_env()`.

### 8.2 Virtual board (Practice mode only)
Mock pins live **inside the student's process**, so the app can't see them directly.
Run the student file through a small shim instead:

```
python3 -u pipath/gpio_shim.py <student_file>
```

`gpio_shim.py`:
1. sets the mock factory, then `runpy.run_path(student_file, run_name="__main__")`,
   with the traceback still pointing at the student's file and line;
2. starts a daemon thread that every 50 ms writes pin states as JSON lines to **fd 3**
   (`{"17": 1, "27": 0.4, ...}`), using `Device.pin_factory.pins`;
3. reads commands on **fd 4** (`press 23` / `release 23`) and calls
   `pin.drive_low()` / `drive_high()` (buttons are pulled up, so pressed = low).

The Runner gains `pass_fds` for those two pipes. The GUI shows a **Virtual board**
panel (Canvas) under the editor tab: LEDs drawn at their brightness and colour (combine
R/G/B pins for an RGBLED), and clickable buttons (hold = mouse down). Lay it out from the
lesson's `[[wiring]]` rows, or from the pins actually used.

### 8.3 Wiring card
For `requires_gpio` lessons, show a collapsible **Wiring** card at the top of the guide:
the parts list (from catalog `parts`), the `[[wiring]]` rows, and a simple Canvas
diagram of the 40-pin header with used pins highlighted. Add a "Check my wiring"
button that runs a tiny test (blink each LED in turn; "press each button now", reading
`is_pressed`) and ticks each part.

### 8.4 Long-running programs
- `run_mode = "until_stopped"`: the checklist evaluates when the program ends **or** the
  student presses Stop (treat a user Stop as a normal finish, `crashed = False`).
- `confirm` checks render as clickable tick-boxes and pass once ticked.
- The busy-loop detector must not kill `pause()` / `sleep()` programs. That's already the
  case, because they use no CPU. A tight `while True: if button.is_pressed:` loop **will**
  be stopped, and should get a specific Coach entry: "add `sleep(0.01)` inside the loop, or use
  `when_pressed`".

### 8.5 GPIO-specific Coach additions
- **Static lint** before Run (new precheck rules, warnings not blockers):
  `x.when_pressed = something()` (brackets: the method runs immediately), `while True`
  without `sleep` or `pause`, the same pin number used twice, pins outside 2–27.
- errors.toml already has: `GPIOPinInUse`, `BadPinFactory`, `PinInvalidPin`,
  `PinPWMUnsupported`, `ModuleNotFoundError gpiozero`. Add tests with mock pins.
- Safety panel (first GPIO lesson, and in the README): power off before rewiring,
  always use a resistor with an LED, never connect 5 V to a GPIO pin, no motors straight
  from GPIO.

---

## 9. Teacher features (Phase 5)

Present now: Ctrl+Shift+T → PIN (config.toml `teacher_pin`) → teacher mode (unlock
all for this session, Next always enabled) and **Export progress CSV**.

To build:
- Change the PIN from the panel (store a hash in `~/PiPath/app.json`, not in plain text).
- Per-class view: table of students × projects (status, stars, runs, errors, hints).
- Reset a student's lesson; delete a student (with confirm); "end of term" archive to a zip.
- Unlock rule override per Pi (e.g. jump straight to GPIO for an elective).
- Import lessons from a USB stick (`/media/*/PiPath-lessons/*.toml`) after validating them.
- "Lesson lint" command: `python3 -m pipath.lint data/lessons/x.toml` checks schema,
  regexes, hint counts, and that the model answer in `tests/` passes.

---

## 10. Deployment

- `install.sh` (exists): copies to `/opt/pipath` or runs in place, adds a menu entry
  (Programming → PiPath) and a desktop icon; optional `--autostart`.
- Classroom roll-out: set up one Pi fully, then clone the SD card (Raspberry Pi
  **SD Card Copier** or Imager) for the class set.
- Updates: `git pull` in `/opt/pipath`, or copy a new `data/` folder from USB. Student
  work in `~/PiPath` is never touched by updates.
- Pi OS Desktop already has `python3-tk`, `python3-gpiozero` and `python3-lgpio`. On
  Lite images run `sudo apt install python3-tk python3-gpiozero python3-lgpio`.

---

## 11. Build plan for Claude Code

Work one phase at a time. At the end of each phase: tests green, screenshots of new
screens under Xvfb, and a manual check on a real Pi 3B.

### Phase 0: Prove the prototype on a Pi 3B
- Run `main.py` on Pi OS (Wayland). Check fonts, window size, tour placement, editor
  speed with a 150-line file, Run latency, `input()` handling, Stop, runaway detection.
- Fix anything Pi-specific. Record timings in `docs/perf.md`.
- **Done when** a student can go from first launch to finishing S3 with no crashes.

### Phase 1: Polish the Simple tier
- Undo/redo buttons (Ctrl+Z already works in the editor; add Ctrl+Y for redo). Add "Reset step code" (restores the step's
  starter, with confirm).
- Coach: show *which word* on the line is the problem using the `^^^^` markers from the
  traceback (underline that range in the editor).
- Accessibility: `--scale` saved per student; high-contrast theme option; full keyboard use.
- Expand errors.toml (target 80+ entries) from real student errors. Add a hidden log of
  `entry_id`s hit per student, to see which errors are common.

### Phase 2: Moderate tier
- Write `m1_quiz.toml`, `m2_turtle.toml`, `m3_tuckshop.toml` from the outlines in §7,
  each with model answers in tests. Set `status = "ready"`.
- Add the `confirm` check type and `run_mode = "until_stopped"` (needed by turtle).

### Phase 3: GPIO foundation + A1
- Practice mode, `gpio_shim.py`, Virtual board, Wiring card, GPIO lint (§8).
- Write `a1_traffic.toml`. Test on a real Pi with a breadboard **and** in Practice mode.

### Phase 4: A2, A3 and the Electronics Lab
- Write `a2_reaction.toml`, `a3_alarm.toml`.
- Flip E1–E4 to `status = "ready"`; add model answers (run with mock pins in tests, using
  the shim to simulate presses).

### Phase 5: Teacher tools + deployment (§9, §10)

### Phase 6: Classroom trial
- Pilot with one class. Export CSVs; look at which steps have the most runs, errors and
  hints, and rewrite those steps and hints.

---

## 12. Testing

- `tests/test_hints.py` runs **real broken programs** with the current interpreter and
  asserts the Coach entry id. Add one per new errors.toml entry.
- `TestLessonsSolvable` holds a **model answer for every step**; add them for each new lesson.
- GUI smoke test: drive the app under `xvfb-run` (see `tests/README` once written):
  onboarding → tour → each step, screenshot with ImageMagick `import -window root`.
- Manual Pi checklist per release: first-run flow, a full lesson, input(), Stop, a runaway
  loop, Free Build create/open, teacher export, GPIO lesson on real hardware.

---

## 13. Decisions already made (don't relitigate without reason)

- **Tkinter over a Thonny plugin.** It gives full control of onboarding, the guide panel
  and gradual release; it's light enough for a Pi 3B. Students meet Thonny afterwards; the
  cheat sheet and Free Build bridge to it.
- **TOML for content**: readable, comments allowed, multi-line literal strings for code.
- **First name + school + optional class only.** No surnames, emails or photos.
- **Blanks are `___`** (3+ underscores), detected only on lines copied from the step's
  starter, so students' own ASCII art with underscores still runs.
- **Stars measure independence (hints), not speed.**

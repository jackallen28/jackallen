# PiPath

A Python coding tutor for Raspberry Pi. Students log in with their **first name and school**,
then choose any activity: screen-only Python, electronics with the GPIO pins, or the camera.
A built-in **Coach** explains errors in plain English and gives tiered hints from a
common-errors database. No AI service and no internet needed.

GPIO and camera activities work like MakeCode: students try their code on an on-screen
**Simulator** board first (and can **Watch the goal** to see what should happen), then
switch to **Real Pi** and run the same code on their breadboard.

## Quick start (on the Pi)

```
git clone -b claude/gallant-ride-1ublon https://github.com/jackallen28/jackallen.git pipath
cd pipath
python3 main.py              # add --scale 1.25 for larger text
```

Install a menu entry and desktop icon:

```
./install.sh                 # or: ./install.sh --autostart   (opens PiPath at login)
```

Needs Raspberry Pi OS Desktop (Bookworm or newer, Python 3.11+). Tkinter, gpiozero, lgpio and
Picamera2 are already installed on the Desktop image. PiPath also runs on any Linux computer
with Python 3.11+ and Tkinter, in Simulator mode (`pip install gpiozero` for GPIO activities).

## How students use it

1. **Log in:** type first name and school (or pick their name if they've been before).
2. **Pick an activity.** Everything is open. The coloured tiers are a guide: *Simple*,
   *Moderate*, *Advanced*, *Electronics Lab*, *Camera & AI*. Cards show "Good to try first" tips.
3. **Work through the steps.** Each step has instructions, a checklist and the Coach. The first
   time, PiPath offers a 30-second tour (**? Tour** shows it again).
4. **GPIO and camera activities** have:
   - **Run on: Simulator | Real Pi** next to the Run button (Real Pi only appears on a Pi)
   - the **board**, beside the Output. In the Simulator it *is* the hardware: click and hold
     buttons, click the motion sensor to "wave". In Real Pi mode it shows what the code is doing.
   - **Watch the goal ▶**: plays the finished step on the board
   - a **Wiring + Safety** card with a pin map and **Check my wiring**
   - "I saw it happen" boxes in the checklist, ticked by the student after a run
   - for camera activities, a **camera panel**: click its title to switch
     **Simulated / USB / Ribbon** (remembered on that Pi)
5. **Free Build** is always open for their own projects. The board appears as soon as their
   code makes an LED or a Button.

## Activities

| Tier | Activity | Students build | Kit |
|---|---|---|---|
| Simple | Hello, Pi! · Meet PiBot · Guess My Number | print, variables, input, if, loops | none |
| Moderate | Quiz Master · Turtle Art Studio · Tuckshop Till | *coming soon* | none |
| Advanced | **Traffic Lights** | Australian light sequence, `def cycle()`, pedestrian button, walk beeper | 3 LEDs, button, buzzer |
| Advanced | **Reaction Timer** | random waits, ms stopwatch, false starts, 2-player race, high-score file | LED, 2 buttons |
| Advanced | **Motion Alarm & Logger** | PIR events, alarm, arm/disarm state, CSV log, cooldown + report | PIR, LED, buzzer, button |
| Electronics Lab | Light Switch · RGB Mood Lamp · Simon Says · Bar Graph & Dice | events, PWM, colours, lists, games | see each Wiring card |
| Camera & AI | **Photo Booth** | button + LED 3-2-1 countdown, timestamped photos, photo strip | camera, 3 LEDs, button, buzzer |
| Camera & AI | **Teachable Machine** | images as numbers, training data, a nearest-neighbour classifier, accuracy, bias | camera, 2 LEDs, button |

### Kit per Pi (covers every activity)

- Breadboard and male-to-female jumper wires
- LEDs: red, amber (yellow), green, plus 3 more for the Bar Graph; **330Ω resistor for every LED**
- 3 push buttons (4-leg tactile)
- 1 **active** buzzer (beeps when powered; a passive buzzer won't work with `Buzzer`)
- 1 HC-SR501 PIR motion sensor
- Optional: 1 common-cathode RGB LED (Mood Lamp), 1 tilt switch (Dice)
- A camera: a **USB webcam** (any UVC webcam, e.g. DFRobot 720p wide-angle) or a
  **Raspberry Pi Camera Module** on the ribbon cable

### Standard pin plan (every activity uses it, so one build carries over)

| Part | GPIO | Physical pin |
|---|---|---|
| Red LED / LED 1 | 17 | 11 |
| Amber LED / LED 2 | 27 | 13 |
| Green LED / LED 3 | 22 | 15 |
| LED 4, 5, 6 | 5, 6, 13 | 29, 31, 33 |
| Button 1 / 2 / 3 | 23 / 24 / 25 | 16 / 18 / 22 |
| Buzzer (+) | 18 | 12 |
| PIR OUT | 4 | 7 (VCC → 5V pin 2, GND → pin 6) |

## Cameras

- **USB webcam:** plug it in. PiPath reads it directly (no extra software). Check it with
  `python3 pipath/student_lib/pipath_camera.py usb`
- **Ribbon camera:** turn the Pi off, connect the ribbon (blue side towards the USB ports), turn
  on. Check it with `rpicam-hello --list-cameras`, then `python3 pipath/student_lib/pipath_camera.py ribbon`
- **Simulated:** no camera needed. The board makes pretend photos (a face, a ball, a box).

Students write the same code for all three: `from pipath_camera import Camera`,
`cam.take_photo("me.jpg")`, `cam.capture_grid(16, 16)`.

## GPIO safety (read before the GPIO activities)

Turn the Pi off before changing wiring. Always put a 330Ω resistor in series with an LED.
Never connect 5V to a GPIO pin (the PIR's OUT pin is 3.3V, which is fine). Don't power motors
straight from GPIO pins. The Wiring card in each activity repeats this.

## For teachers

- **Teacher panel:** press **Ctrl+Shift+T** and enter the PIN (default `2468`, **change it** in
  `data/config.toml`). Teacher mode lets you skip steps for the session, and you can export
  everyone's progress to CSV.
- **Student work** is saved in `~/PiPath/students/<name>/` (code, photos, logs). Updating PiPath
  never touches it.
- **Edit content** without coding:
  - `data/lessons/*.toml`: steps, starter code, checklists, hints, wiring, and `demo` (the model
    answer that **Watch the goal** plays, with `demo_events` for simulated button presses)
  - `data/errors.toml`: the Coach's explanations for common errors
  - `data/catalog.toml`: which activities appear, their tier, and "Good to try first" tips
  - `data/config.toml`: PIN, runaway-loop limits, star thresholds
- **Class set:** set up one Pi, then clone its SD card with *SD Card Copier*.
- **Testing on real hardware:** follow `docs/pi-test-checklist.md`.

## Developers

See `CLAUDE.md` for the architecture, data formats and what's next. Run the tests with:

```
python3 -m unittest discover -s tests
```

Every GPIO and camera step's model answer is run in the Simulator with its button presses,
and must pass that step's own checklist. Screenshots of every main screen:
`xvfb-run -s "-screen 0 1366x768x24" python3 tests/gui_smoke.py shots/`

# PiPath

A Python coding tutor for Raspberry Pi. Students create a profile, take a short tour, then
work through guided projects. A built-in **Coach** explains errors in plain English and
gives tiered hints from a common-errors database. No AI and no internet needed.

## Quick start (on the Pi)

```
cd pipath
python3 main.py              # add --scale 1.25 for larger text
```

Install a menu entry and desktop icon:

```
./install.sh                 # or: ./install.sh --autostart   (opens PiPath at login)
```

Needs Raspberry Pi OS Desktop (Bookworm or newer, Python 3.11+). Tkinter and gpiozero
are already installed on the Desktop image.

## For teachers

- **Teacher panel:** press **Ctrl+Shift+T** and enter the PIN (default `2468`, change it in
  `data/config.toml`). It can unlock all projects for a session and export everyone's progress to CSV.
- **Student work** is saved in `~/PiPath/students/<name>/`. Updating PiPath never touches it.
- **Edit content** without coding:
  - `data/lessons/*.toml`: steps, starter code, checklists, hints
  - `data/errors.toml`: the Coach's explanations for common errors
  - `data/catalog.toml`: which projects appear on the map, and in what order
  - `data/config.toml`: PIN, when Free Build unlocks, runaway-loop limits, star thresholds
- **Class set:** set up one Pi, then clone its SD card with *SD Card Copier*.

## Projects

| Tier | Projects | Status |
|---|---|---|
| Simple | Hello Pi! · Meet PiBot · Guess My Number | playable |
| Moderate | Quiz Master · Turtle Art Studio · Tuckshop Till | planned |
| Advanced (GPIO) | Traffic Lights · Reaction Timer · Motion Alarm & Logger | planned |
| Electronics Lab | Light Switch Lab · RGB Mood Lamp · Simon Says · Bar Graph & Digital Dice | lessons written, need GPIO support |

## GPIO safety (read before the Advanced projects)

Turn the Pi off before changing wiring. Always put a 330Ω resistor in series with an LED.
Never connect 5V to a GPIO pin. Don't power motors straight from GPIO pins.

## Developers

See `CLAUDE.md` for the architecture, data formats and build plan. Run tests with:

```
python3 -m unittest discover -s tests
```

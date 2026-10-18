# PiPath performance on a Raspberry Pi 3B

Targets (from CLAUDE.md): app start < 4 s, screen change < 400 ms, Run to first output < 1 s,
idle CPU about 0%.

## How to measure

On the Pi desktop, open a terminal in the PiPath folder and run:

```
python3 tests/perf_probe.py
```

It uses a throw-away student folder, so it never touches real student work. It prints the
milliseconds for each main interaction. Copy the numbers into the **Pi 3B** column below.
(On a PC without a screen: `xvfb-run -s "-screen 0 1366x768x24" python3 tests/perf_probe.py`.)

## Results

Medians of 9 runs on a desktop PC under Xvfb, same machine before and after. A Pi 3B is very
roughly 10 times slower, so divide the 400 ms target by 10: anything under ~40 ms here should
feel quick on a Pi.

| Interaction | Before (v0.2) | Now | Pi 3B (fill in) |
|---|---|---|---|
| Open an activity (first time this session) | 136 ms | 110–145 ms | |
| Open an activity (any time after that) | 136 ms | 30 ms | |
| Start step 1 | 92 ms | 24 ms | |
| Next step | 65 ms | 8.5 ms | |
| Back to activities | 160–185 ms | 13–17 ms | |
| Open Free Play (again) | 88 ms | 17 ms | |
| Free Play: add a part (wiring card follows 60 ms later) | | 12 ms | |
| Free Play: rebuild the wiring card | | 16–20 ms | |
| Settings > Save data tab | | 14 ms | |
| Run pressed → first output (GPIO program) | 121 ms | 5 ms | |
| Idle CPU (activities, an activity, Free Play) | | 0.1–0.2 % | |
| Memory: app + spare runner, after 5 screens | | 35 + 20 MB | |

The first activity of a session still builds the whole workspace once. Every activity after
that re-uses it. Free Play's wiring card is only rebuilt when the parts in the code change (checked
1.5 s after typing stops, with `compile` + `ast`: about 0.3 ms), not when the screen is reopened,
and half-typed code that doesn't parse leaves it alone. The probe also measures idle CPU (the app
should use none while nobody touches it).

## What made it slow, and what changed

Most of the time on a Pi goes into making Tk widgets (each is a window the desktop has to
manage) and laying the screen out. Python itself is rarely the problem. So:

1. **Screens are kept, not rebuilt.** The activity picker, one activity workspace and Free
   Build are made once per student and hidden when not in use. Opening another activity only
   swaps in that activity's own parts: the title, the wiring card, the step plan, the code.
   (`app.py`: `_swap`, `forget_screens`; `workspace.py`: `LessonWorkspace.load`, `park`, `hide`.)
2. **The activity picker is drawn on one Canvas** instead of about 200 widgets.
3. **The step panel is made once.** Each step only changes its text. Checklist rows are kept
   and re-used, and the step dots are drawn on a small canvas.
4. **One layout pass for all text.** Every `RichText` waits for one shared measuring pass
   instead of forcing its own (`widgets.py`: `fit_height`, `_fit_waiting`).
5. **Lazy building.** The wiring card's pin map is only made when the card is first opened;
   lessons load when first opened; the Coach's error database loads when the first program
   needs explaining.
6. **Warm start for GPIO programs.** A spare runner process starts in the background with
   gpiozero already imported, and waits. Pressing Run hands it the program, so there is no
   wait for Python and gpiozero to load (about a second on a Pi 3B). A new spare starts after
   each run. (`runner.py`: `warm_up`; `gpio_shim.py`: `--wait`.)
7. **No package scan for the Simulator.** Asking gpiozero for the mock pins by name makes it
   scan every installed Python package, which is slow on Pi OS with its hundreds of packages.
   The shim makes the mock pin factory directly instead.
8. **The board only repaints what changed**, draws only the newest pin states, and swaps a
   new photo in place.
9. **Small things:** Output text is written once per 40 ms poll, the runaway check reads
   `/proc` twice a second instead of 25 times, and `install.sh` pre-compiles the Python files.

## Rules for new code

- Don't make widgets in a loop that runs on every step or every Run. Re-use them, or draw on
  a Canvas.
- Never call `update_idletasks()` per widget. Use `RichText.fit_height()` (it batches).
- Don't rebuild a whole screen to change one label. Configure the label.
- Anything slow to import goes in the spare runner's preload list (`Workspace.preload`).

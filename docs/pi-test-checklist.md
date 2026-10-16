# Testing PiPath on a real Raspberry Pi

Everything below has passed in the Simulator and in automated tests. These checks cover
what only real hardware can show: timings, wiring, the USB webcam and the ribbon camera.
It takes about an hour. Tick each box, and note anything odd (with a photo of the screen if
you can).

**You need:** a Pi 3B with Raspberry Pi OS Desktop (Trixie), a breadboard kit wired to the
standard pin plan (see README), a USB webcam (e.g. the DFRobot 720p), and a ribbon camera if
you have one.

## 1. Install and run the tests (10 min)

```
git clone -b claude/gallant-ride-1ublon https://github.com/jackallen28/jackallen.git pipath
cd pipath
python3 -m unittest discover -s tests
```

- [ ] Tests finish with `OK` (expect 1 to 3 minutes on a Pi 3B). If any fail, copy the output.
- [ ] `./install.sh` adds PiPath to the menu (Programming) and the desktop.

## 2. First launch (5 min)

- [ ] PiPath opens in under about 4 seconds (time it from the menu click).
- [ ] Create a profile with a first name and school. It goes straight to the activities.
- [ ] Creating the same name + school again shows the "already a ... from this school" message.
- [ ] Filter chips (Simple, Advanced, Camera & AI...) show the right cards. Nothing is locked.
- [ ] Open **Hello, Pi!**, start step 1: the "First time here?" box appears. Try **Show me around**.
- [ ] Press **Watch the goal ▶** (next to Run) on Meet PiBot step 2: the answers are typed into
      the Output, one at a time.
- [ ] Text is readable on your projector (try `python3 main.py --scale 1.25` if not).
- [ ] Choose **Advanced** under "How much help do you want?". In an activity, a step shows just
      its goal with **▸ Show the full explanation**, and a **Skip** button is next to Next step.
      **Help:** in the top bar switches level, and the activity picker remembers it.
- [ ] Going back and forth between the activity picker and an activity feels quick (well under
      half a second, apart from the very first activity you open).

## 3. Simulator (5 min)

Open **Traffic Lights**.

- [ ] The toolbar shows **Run on: Simulator | Real Pi**, and both can be chosen.
- [ ] With **Simulator** chosen, step 2's **Watch the goal ▶** lights green, amber, red on the board.
- [ ] The Wiring card opens and shows the pin map with GPIO17/27/22/23/18 highlighted.

## 4. Real Pi: GPIO (20 min)

Wire the standard pin plan. Choose **Real Pi**.

- [ ] **Check my wiring** (in the Wiring card) blinks each LED in turn, beeps the buzzer, and
      ticks the button when you press it.
- [ ] Traffic Lights step 1 (fill in `2`): the real red LED flashes short then long. The board
      shows the same thing at the same time.
- [ ] Step 4 (test the button): each press of the real button prints `Pressed!`.
- [ ] Step 5: lights wait on green until you press the real button, then change and print `Walk!`.
- [ ] Press **Run** a second time on a GPIO step: output appears in well under a second
      (PiPath keeps a spare runner ready with gpiozero loaded).
- [ ] Press **Stop** while an LED is on: **the real LED turns off**.
- [ ] Reaction Timer step 4: the printed reaction time looks believable (about 200-400 ms).
- [ ] Motion Alarm step 1: the LED lights, then the buzzer beeps 3 times.
- [ ] Motion Alarm step 2: after the PIR warms up (30-60 s), waving prints `Motion!` and later
      `All quiet`. Step 5 writes `motion_log.csv` in `~/PiPath/students/<name>/lessons/`.
- [ ] Light Switch Lab step 5 (dimmer): the real LED gets brighter with each press.
- [ ] In Free Build, a loop with no `sleep` is stopped after about 8 seconds and the Coach
      suggests `sleep(0.01)`. Try `while True:` then `if button.is_pressed: print("hi")`, and
      don't press the button.
- [ ] Idle CPU with PiPath open and nothing running is near 0% (`top`).

## 5. USB webcam (10 min)

Plug in the webcam.

- [ ] In a terminal: `python3 pipath/student_lib/pipath_camera.py usb` prints
      `Camera kind: usb`, saves `pipath_camera_test.jpg` (open it: is it a clear photo?), and
      prints an 8 × 8 grid of numbers. **If this fails, copy the whole message.**
- [ ] Open **Photo Booth**. Click the camera panel's title until it says **USB CAMERA**.
- [ ] Step 1: the photo appears on the board within a few seconds.
- [ ] Step 3 on Real Pi: the 3-2-1 LEDs and the beep. Step 4: press, countdown, then the photo.
- [ ] **Teachable Machine** step 1: the board shows a blocky grey version of what the camera sees,
      and the `#`/`.` picture roughly matches an object held in front of a plain background.
- [ ] Steps 2 to 5: collect 5 photos each of two things, check the guess (step 4), then the right
      LED lights for each most of the time (step 5).

## 6. Ribbon camera (if you have one, 10 min)

- [ ] `rpicam-hello --list-cameras` lists the camera.
- [ ] `python3 pipath/student_lib/pipath_camera.py ribbon` saves a photo and prints a grid.
- [ ] In Photo Booth, switch the camera panel to **RIBBON CAMERA**; step 1 shows the photo.

## 7. Timings to record (for docs/perf.md)

First run `python3 tests/perf_probe.py` in a terminal on the Pi desktop and copy its table
into the **Pi 3B** column of `docs/perf.md`. Then time these by hand:

| What | Time |
|---|---|
| Menu click → welcome screen | |
| Activity card → workspace (first activity) | |
| Activity card → workspace (another activity) | |
| Back to activities | |
| Next step | |
| Run → first output (Hello, Pi!) | |
| Run → first output (Traffic Lights, Real Pi, second run) | |
| USB `take_photo` → photo on board | |
| `capture_grid(16, 16)` (USB) | |

## Reporting back

Send the failed boxes, any error text, and the timings. Most fixes will be small changes
to the camera helper or the lesson text.

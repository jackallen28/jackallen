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
- [ ] Text is readable on your projector (try `python3 main.py --scale 1.25` if not).

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
- [ ] Step 4: lights wait on green until you press the real button, then change and print `Walk!`.
- [ ] Press **Stop** while an LED is on: **the real LED turns off**.
- [ ] Reaction Timer step 2: the printed reaction time looks believable (about 200-400 ms).
- [ ] Motion Alarm step 1: after the PIR warms up (30-60 s), waving prints `Motion!` and later
      `All quiet`. Step 4 writes `motion_log.csv` in `~/PiPath/students/<name>/lessons/`.
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
- [ ] Step 3 on Real Pi: the 3-2-1 LEDs, beep, then the photo.
- [ ] **Teachable Machine** step 1: the board shows a blocky grey version of what the camera sees,
      and the `#`/`.` picture roughly matches an object held in front of a plain background.
- [ ] Step 2 → 4: collect 5 photos each of two things, then the right LED lights for each
      most of the time.

## 6. Ribbon camera (if you have one, 10 min)

- [ ] `rpicam-hello --list-cameras` lists the camera.
- [ ] `python3 pipath/student_lib/pipath_camera.py ribbon` saves a photo and prints a grid.
- [ ] In Photo Booth, switch the camera panel to **RIBBON CAMERA**; step 1 shows the photo.

## 7. Timings to record (for docs/perf.md)

| What | Time |
|---|---|
| Menu click → welcome screen | |
| Activity card → workspace | |
| Run → first output (Hello, Pi!) | |
| Run → first output (Traffic Lights, Real Pi) | |
| USB `take_photo` → photo on board | |
| `capture_grid(16, 16)` (USB) | |

## Reporting back

Send the failed boxes, any error text, and the timings. Most fixes will be small changes
to the camera helper or the lesson text.

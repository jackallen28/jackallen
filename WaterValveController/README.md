# Water Valve Controller (Arduino Nano)

Counts the water going through a YF-G1 flow sensor and warns the user when a
chosen amount has been used by briefly pulsing the solenoid valve shut.

- Choose **25 L**, **50 L**, **100 L** or **FREE FLOW** with the push button or the 433 MHz remote
  (button A = 25 L, B = 50 L, C = 100 L, D = FREE FLOW; the valve clicks twice to confirm).
  The three volumes can be changed on the Aqua Tracka web page or in the sketch (see [Changing the limit volumes](#changing-the-limit-volumes)).
- When the limit is reached, the valve shuts and opens 4 times (0.5 s shut, 0.5 s open),
  then water keeps flowing and the count starts again at 0 L.
- A press of the push button resets the count to 0 L. On the remote, hold any button
  for 2 s to reset the count; the valve clicks twice to confirm.
- Hold the push button, or remote button D (FREE FLOW), for 20 s to calibrate with a
  7 L bucket. The calibration is saved and survives power cuts. The water count always
  starts at 0 L after power-up.
- Flow rate, limit and count are printed to the Serial Monitor and sent to an ESP32-C3 board
  (Waveshare ESP32-C3-Zero) running **Aqua Tracka**: its own Wi-Fi network, **VAT_Aqua_Tracka**,
  with a phone dashboard at http://192.168.4.1 for the live readings, calibration, all the
  settings, diagnostics and instructions. See [`esp32/README.md`](esp32/README.md). The
  controller works the same without it.

## Parts

| Part | Notes |
|------|-------|
| Arduino Nano (ATmega328P) | |
| YF-G1 flow sensor (2–100 L/min, F = 1.08 × Q) | 64.8 pulses per litre by default (spec sheet, ±3%) |
| 12 V DC solenoid valve | Switched by a MOSFET on the controller PCB (a relay module works for a hand-built version) |
| Panel momentary push button | MODE / CAL |
| 3 × panel LED | 25 L, 50 L, 100 L. Plain LEDs: the resistors are on the PCB |
| Illuminated rocker switch (12 V lamp) + 2 A ATO blade fuse | Main power switch and fuse (PCB version) |
| 433 MHz RX480E-4 receiver module + 4-button remote (A–D) | 5 V logic outputs |
| Waveshare ESP32-C3-Zero (optional) | Powered from 5 V; its data pins are 3.3 V only, so it needs a divider |

## Wiring

The controller PCB in [`hardware/`](hardware/) has screw terminals and JST-XH connectors for
everything, plus the filtering and protection parts. Its connector pinouts are in the
[hardware README](hardware/README.md#board-connectors). The table below is the minimum wiring for a
hand-built version.

| Arduino Nano pin | Connects to |
|------------------|-------------|
| **D2** | Flow sensor signal (yellow). Red → **5 V**, black → GND |
| **D4** | Push button; other side of the button → GND |
| **D5** | 220 Ω → LED "25 L" → GND |
| **D6** | 220 Ω → LED "50 L" → GND |
| **D7** | 220 Ω → LED "100 L" → GND |
| **D8** | Valve driver. Hand-built: relay module IN (relay VCC → 5 V, GND → GND); set `VALVE_DRIVE_ACTIVE_LOW = true` for most relay modules |
| **A0** | Receiver D0 (remote button D = FREE FLOW on the tested board) |
| **A1** | Receiver D1 (button C = 100 L) |
| **A2** | Receiver D2 (button B = 50 L) |
| **A3** | Receiver D3 (button A = 25 L) |
| **5V / GND** | Receiver +V and GND (VT is not used) |
| **D11** | Data out to the ESP, through a 1 kΩ / 2 kΩ divider (see below) |
| **D12** | Commands from the ESP (ESP GPIO21), through 1 kΩ |

**Solenoid:** on the PCB, the valve goes to terminal J3: pin 1 = valve +, pin 2 = valve −. A
MOSFET switches the 12 V to the valve and the flyback diode is on the board. In a hand-built
version, wire the solenoid supply through the relay's **COM** and **NO** terminals and fit a
flyback diode (e.g. 1N4007) across the coil, with the stripe towards +. Without it, the voltage
spike when the coil switches off can reset the Nano or add false flow pulses. The sketch handles
both valve types and is set for a **normally open** valve: water flows while the valve is unpowered,
and the controller powers it only to stop the water (see `VALVE_NORMALLY_CLOSED` below).

**Power:** a 12 V supply feeds the solenoid and a 5 V regulator into the Nano's **5V** pin. On the
PCB the 12 V goes through the blade fuse first, then out to the illuminated rocker switch (J2) and
back. All grounds must be connected together.

**Flow sensor power:** power the sensor from the Nano's **5 V** pin, not the 12 V supply.
The sensor accepts 3.5–24 V, but its spec sheet gives its output levels for a 5 V
supply (high about 4.7 V, low under 0.5 V). That suggests the signal swings up to the
supply voltage, and 12 V on D2 would damage the Nano.

**Remote receiver (RX480E-4):** a small 433 MHz module with a learn button and a 7-pin
header (GND, +V, D0, D1, D2, D3, VT from the learn-button end; the labels are on the back). Power it from **5 V
only**, never 12 V. Each D output goes HIGH while its remote button is held: 4.9 V on the
tested RX480R_4CH V4, but some boards only reach about 3 V, right at the Nano's minimum for
a reliable digital HIGH. The sketch therefore reads A0–A3 with the analog converter and
treats anything above 1.5 V as pressed (`REMOTE_HIGH_THRESHOLD`). A press counts after
20 ms, so even a 0.1 s pulse is caught. A release needs 150 ms of silence, so brief radio
drop-outs during a hold are ignored.

Pair the remote in **momentary mode**, because the 2 s and 20 s holds are timed from the
output. On most RX480E modules:

1. Press the learn button 8 times to clear any stored remotes (the LED flashes).
2. Press the learn button **once** (once = momentary, twice = toggle, three times = latched).
3. Press any button on the remote. The LED flashes 3 times when it has learned it.

Check the leaflet that came with your module in case its sequence differs. In toggle or
latched mode an output stays on, which would reset the count after 2 s and, on button D,
start calibration after 20 s.

The tested RX480R_4CH V4 drives D3 for button A and D0 for button D, so `PIN_REMOTE` at the
top of the sketch is set to `{ A3, A2, A1, A0 }`. Other boards may differ: press each button
and watch the Serial Monitor, and if a button selects the wrong limit, change that order.

Keep the receiver's coiled antenna away from the valve wires, the regulator and any metal, and
don't mount it inside a metal box.

### Checking the receiver on its own

**With a multimeter:** power the module from 5 V and GND, put the meter between D0 and GND,
and press remote button A.

| What you see | Meaning |
|---|---|
| About 3 V while you hold the button, back to 0 V within a fraction of a second after you let go | **Momentary mode**: correct |
| Stays at 3 V after you let go, and only goes off on the next press of the same button | **Toggle mode**: re-pair |
| Stays at 3 V until you press a different button | **Latched mode**: re-pair |
| Never changes | The remote isn't paired, or the button is mapped to another output: try D1–D3 |

An LED with a 330 Ω resistor from D0 to GND works too: it lights (dimly) while the output is on.

**With the test sketch:** [`RemoteTest`](../RemoteTest/RemoteTest.ino) runs on a bare Nano with
only the receiver connected (GND → GND, +V → 5V, D0–D3 → A0–A3). Open the Serial Monitor at
115200 baud and press each button. For each press it shows:

- the output voltage
- how long the output stayed on
- signal drop-outs during a long hold, which would make a 2 s hold read as two short presses
- a warning if an output stays on after you let go (toggle or latched mode)

**ESP32-C3-Zero:** power it from 5 V into its **5V** pin (it has its own 3.3 V regulator) and
connect GND. On the PCB it plugs into the 4-pin JST-XH connector J4: **5V**, **GND**, **RX** (to
ESP GPIO20) and **TX** (from ESP GPIO21). The board already drops the Nano's 5 V data to 3.2 V for
the ESP, and the ESP's 3.3 V output reads as HIGH on the Nano (D12, through 1 kΩ). In a hand-built
version, its GPIO pins are **3.3 V only**, so drop the Nano's 5 V data signal with a divider into a
free GPIO such as GPIO20:

```
Nano D11 ──[1 kΩ]──┬── ESP GPIO20
                   │
                 [2 kΩ]
                   │
                  GND (shared with the ESP)
```

Avoid GPIO2, 8 and 9 (boot strapping pins) and 18/19 (USB). Its Wi-Fi draws peaks of about
350 mA from 5 V, so use a regulator rated 1 A for the 5 V supply.

## Settings to check before uploading

These are at the top of `WaterValveController.ino`.

| Setting | Default | Change it when |
|---------|---------|----------------|
| `VALVE_NORMALLY_CLOSED` | `false` | Set for a normally **open** valve (water flows with no power). If your valve needs power to let water through (normally closed) → set `true` |
| `VALVE_DRIVE_ACTIVE_LOW` | `false` | Right for the PCB's MOSFET driver. A hand-built version with a relay module that switches on when IN is LOW (most of them) → set `true` |
| `REMOTE_ACTIVE_LOW` | `false` | Your receiver has relay outputs (COM/NO) instead of logic outputs → set `true` |
| `REMOTE_SELECT_RESETS_COUNT` | `false` | You want choosing a limit on the remote to also reset the count → set `true` |
| `REMEMBER_LIMIT` | `true` | You want it to start in FREE FLOW after every power-up → set `false` |

**Quick check:** power it up in FREE FLOW (all LEDs off) with the water on. Water
should flow. If it doesn't, flip `VALVE_NORMALLY_CLOSED`. If the valve output is in the
wrong state, flip `VALVE_DRIVE_ACTIVE_LOW`.

Upload with the Arduino IDE: **Tools → Board → Arduino Nano**. If the upload fails,
try **Tools → Processor → ATmega328P (Old Bootloader)**. No extra libraries are
needed (`EEPROM` and `SoftwareSerial` are built in).

## How to use it

### Choosing a limit

**Push button:** each short press (under 2 s) steps to the next limit
(25 L → 50 L → 100 L → FREE FLOW → 25 L …) and resets the count to 0 L.

**Remote:** a short press (under 2 s) chooses a limit directly, and the valve clicks twice
(0.25 s shut, 0.25 s open, twice) to confirm. The count is **kept**, so if more water has
already been used than the new limit, the limit warning starts once the clicks finish.

| Remote button | Limit (default) | LED |
|---------------|-----------------|-----|
| A | Limit 1 (25 L) | D5 LED on |
| B | Limit 2 (50 L) | D6 LED on |
| C | Limit 3 (100 L) | D7 LED on |
| D | FREE FLOW | All off (counts, never pulses) |

### Changing the limit volumes

The three volumes are at the very top of `WaterValveController.ino`:

```cpp
const uint16_t LIMIT_1_LITRES = 25;
const uint16_t LIMIT_2_LITRES = 50;
const uint16_t LIMIT_3_LITRES = 100;
```

Change the numbers (whole litres) and upload again, or change them on the Aqua Tracka page
(Settings), which needs no upload. (See [Settings from the web page](#settings-from-the-web-page).) The LEDs, remote buttons, Serial
Monitor and ESP data all follow these values.

### Resetting the count

- **Remote:** hold **any** button for 2 seconds. The count goes to 0 L and the valve
  clicks twice (0.25 s shut, 0.25 s open, twice) to confirm. The limit does not change.
- **Push button:** any short press resets the count (and moves to the next limit).

### When the limit is reached

The valve shuts for 0.5 s and opens for 0.5 s, four times (4 seconds in total). The
selected LED blinks along with it. When the pulses finish, the count starts again from
0 L, so the next warning comes after another full limit's worth of water (water that ran
during the warning isn't counted towards it, but is still in the session total). The
warning repeats every limit until the count is reset. The number of pulses and their
timing are `ALERT_PULSES` and `ALERT_PHASE_MS` in the sketch, or Settings on the web page. A push-button press
or a 2 s remote hold during the warning stops it straight away.

### Calibration (7 L bucket)

1. Turn the water off and put a 7 L bucket under the outlet.
2. Hold the push button **or remote button D (FREE FLOW)** for **20 seconds** until
   all three LEDs start flashing, then let go.
   - Push button: presses between 2 s and 20 s are ignored, so you can let go early to cancel.
   - Remote button D: the valve clicks twice at 2 s (that is the count reset); keep holding.
   - Remote buttons A–C cannot start or finish calibration.
3. Turn the water on and fill the bucket to exactly 7 L, then turn the water off.
4. Short-press the push button or remote button D.
   - **All LEDs on for 2 s:** calibration saved.
   - **All LEDs flash quickly for 2 s:** the result was not sensible (for example
     no water ran), so the previous calibration is kept. Pressing straight away
     without running water is how you cancel calibration mode.

The limit is not enforced during calibration, so the valve stays open. The count is
reset to 0 L afterwards.

Out of the box the sketch uses the YF-G1 spec sheet value: F (Hz) = 1.08 × Q (L/min),
which is 1.08 × 60 = **64.8 pulses per litre**. The sheet quotes ±3% accuracy, so
calibrating with the bucket is still worthwhile.

A calibration saved earlier is kept when you upload a new version of the sketch. To go
back to the spec sheet value, just calibrate again. A saved calibration replaces it permanently, including after
power cuts, until you calibrate again.

### After a power cut

- Calibration: kept (stored in EEPROM).
- Selected limit: kept (unless `REMEMBER_LIMIT = false`).
- Water count: starts again at 0 L.
- Valve: a normally open valve lets water through while the power is off, so a limit that
  was reached before the power cut no longer holds the water back.

## Serial Monitor

Open the Serial Monitor at **115200 baud**. One status line is printed every second,
plus a message whenever something happens:

```
=== Water Valve Controller ===
Calibration: 64.80 pulses/L (datasheet default)
Limit: 25L
Limits: A = 25L, B = 50L, C = 100L, D = FREE FLOW
Button: short press = next limit + reset count | hold 20 s = calibrate
Remote: press = choose limit (2 clicks) | hold any 2 s = reset count (2 clicks)
        hold D for 20 s = calibrate

Flow: 10.00 L/min | Limit: 25L | Count: 24.83 L | Session: 24.83 L | Valve: OPEN | NORMAL
>> Limit of 25L reached - pulsing valve, count restarted at 0 L
Flow: 10.00 L/min | Limit: 25L | Count: 0.15 L | Session: 25.15 L | Valve: SHUT | LIMIT REACHED
```

- **Count:** litres counted towards the current limit. Goes back to 0 when the limit is reached.
- **Session:** total litres since power-up or the last count reset.
  This is not reset when the limit is reached.

## ESP data link (D11 out, D12 in)

D11 sends the Nano's status (every second) and settings (every 10 s) as JSON lines at
**9600 baud** (8N1, 5 V logic: the PCB divides it to 3.2 V; in a hand-built version use the
divider above), and D12 receives commands from the ESP: choose the limit, reset the count,
calibrate, change the settings, restore the defaults and test the valve. The line formats and
commands are in [`esp32/README.md`](esp32/README.md#how-it-works).

### Settings from the web page

The limits, warning pulses, clicks, hold times, calibration bucket and hardware options at the top
of the sketch are the **defaults**. Settings changed on the Aqua Tracka page are saved in the
Nano's EEPROM and used instead, also after a power cut and without the ESP. **Reset to defaults**
on the page brings back the values in the sketch; **Factory reset** also clears the calibration.
After you change a default in the sketch and upload it, press **Reset to defaults** on the page
for the new value to take effect (or it keeps the value saved from the page).

The page can also make the valve **stay shut after the limit** (until the count is reset with the
button, the remote or the page) instead of letting the water flow on. While it is held shut, the
selected light blinks slowly.

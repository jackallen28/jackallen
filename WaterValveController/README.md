# Water Valve Controller (Arduino Nano)

Counts the water going through a YF-G1 flow sensor and warns the user when a
chosen amount has been used by briefly pulsing the solenoid valve shut.

- Choose **25 L**, **50 L**, **100 L** or **FREE FLOW** with the push button or the 433 MHz remote
  (remote button 1 = 25 L, 2 = 50 L, 3 = 100 L, 4 = FREE FLOW).
- When the limit is reached, the valve shuts and opens 6 times (0.5 s shut, 0.5 s open),
  then water keeps flowing and the count starts again at 0 L.
- A press of the push button resets the count to 0 L. On the remote, hold any button
  for 2 s to reset the count; the valve clicks twice to confirm.
- Hold the push button, or remote button 4 (FREE FLOW), for 20 s to calibrate with a
  7 L bucket. The calibration is saved and survives power cuts. The water count always
  starts at 0 L after power-up.
- Flow rate, limit and count are printed to the Serial Monitor and sent to a spare
  pin for a future ESP8266/ESP32.

## Parts

| Part | Notes |
|------|-------|
| Arduino Nano (ATmega328P) | |
| YF-G1 flow sensor (2–100 L/min, F = 1.08 × Q) | 64.8 pulses per litre by default (spec sheet, ±3%) |
| Solenoid valve + 1-channel relay module | |
| Momentary push button | |
| 3 × LED + 3 × 220 Ω resistor | 25 L, 50 L, 100 L |
| 433 MHz RX480E-4 receiver module + 4-button remote (A–D) | 5 V logic outputs |
| ESP8266 / ESP32 (optional, later) | 3.3 V logic, needs a voltage divider |

## Wiring

A full schematic, with extra filtering and protection parts and KiCad files for making a PCB,
is in [`hardware/`](hardware/). The table below is the minimum wiring for a hand-built version.

| Arduino Nano pin | Connects to |
|------------------|-------------|
| **D2** | Flow sensor signal (yellow). Red → **5 V**, black → GND |
| **D4** | Push button; other side of the button → GND |
| **D5** | 220 Ω → LED "25 L" → GND |
| **D6** | 220 Ω → LED "50 L" → GND |
| **D7** | 220 Ω → LED "100 L" → GND |
| **D8** | Relay module IN (relay VCC → 5 V, GND → GND) |
| **A0** | Receiver D0 (remote button A = 25 L) |
| **A1** | Receiver D1 (remote button B = 50 L) |
| **A2** | Receiver D2 (remote button C = 100 L) |
| **A3** | Receiver D3 (remote button D = FREE FLOW) |
| **5V / GND** | Receiver +V and GND (VT is not used) |
| **D11** | Data out to ESP RX, through a 1 kΩ / 2 kΩ divider (see below) |
| **D12** | Reserved for ESP TX → Nano (not used yet) |

**Solenoid:** wire the solenoid supply through the relay's **COM** and **NO**
terminals. The sketch handles both normally-closed and normally-open valves (see
`VALVE_NORMALLY_CLOSED` below). If the valve is a DC solenoid, fit a flyback diode
(e.g. 1N4007) across the coil, with the stripe towards +. Without it, the voltage
spike when the coil switches off can reset the Nano or add false flow pulses.

**Power:** a 12 V supply can feed the solenoid and the Nano's **VIN** pin (or a separate
5 V regulator into the Nano's **5V** pin). All grounds must be connected together.

**Flow sensor power:** power the sensor from the Nano's **5 V** pin, not the 12 V supply.
The sensor accepts 3.5–24 V, but its spec sheet gives its output levels for a 5 V
supply (high about 4.7 V, low under 0.5 V). That suggests the signal swings up to the
supply voltage, and 12 V on D2 would damage the Nano.

**Remote receiver (RX480E-4):** a small 433 MHz module with a learn button and a 7-pin
header (GND, +V, D0, D1, D2, D3, VT from the learn-button end; the labels are on the back). Power it from **5 V
only**, never 12 V. Each D output goes HIGH (5 V) while its remote button is held.

Pair the remote in **momentary mode**, because the 2 s and 20 s holds are timed from the
output. On most RX480E modules:

1. Press the learn button 8 times to clear any stored remotes (the LED flashes).
2. Press the learn button **once** (once = momentary, twice = toggle, three times = latched).
3. Press any button on the remote. The LED flashes 3 times when it has learned it.

Check the leaflet that came with your module in case its sequence differs. In toggle or
latched mode an output stays on, which would reset the count after 2 s and, on button D,
start calibration after 20 s.

Some modules map the remote buttons to D0–D3 in a different order. Press each button and
watch the Serial Monitor: if a button selects the wrong limit, swap the pins in
`PIN_REMOTE` at the top of the sketch.

Keep the receiver's coiled antenna away from the relay, the valve wires and any metal, and
don't mount it inside a metal box.

**ESP8266/ESP32:** these run on 3.3 V, so drop the Nano's 5 V signal with a divider:

```
Nano D11 ──[1 kΩ]──┬── ESP RX
                   │
                 [2 kΩ]
                   │
                  GND (shared with the ESP)
```

Power the ESP from its own 3.3 V regulator; the Nano's 3.3 V pin cannot supply enough current.

## Settings to check before uploading

These are at the top of `WaterValveController.ino`.

| Setting | Default | Change it when |
|---------|---------|----------------|
| `VALVE_NORMALLY_CLOSED` | `true` | Your valve lets water through with **no** power (normally open) → set `false` |
| `RELAY_ACTIVE_LOW` | `true` | Your relay clicks on when IN is HIGH → set `false` |
| `REMOTE_ACTIVE_LOW` | `false` | Your receiver has relay outputs (COM/NO) instead of logic outputs → set `true` |
| `REMOTE_SELECT_RESETS_COUNT` | `false` | You want choosing a limit on the remote to also reset the count → set `true` |
| `REMEMBER_LIMIT` | `true` | You want it to start in FREE FLOW after every power-up → set `false` |

**Quick check:** power it up in FREE FLOW (all LEDs off) with the water on. Water
should flow. If it doesn't, flip `VALVE_NORMALLY_CLOSED`. If the relay is in the
wrong state, flip `RELAY_ACTIVE_LOW`.

Upload with the Arduino IDE: **Tools → Board → Arduino Nano**. If the upload fails,
try **Tools → Processor → ATmega328P (Old Bootloader)**. No extra libraries are
needed (`EEPROM` and `SoftwareSerial` are built in).

## How to use it

### Choosing a limit

**Push button:** each short press (under 2 s) steps to the next limit
(25 L → 50 L → 100 L → FREE FLOW → 25 L …) and resets the count to 0 L.

**Remote:** a short press (under 2 s) chooses a limit directly. The count is **kept**,
so if more water has already been used than the new limit, the limit warning starts
straight away.

| Remote button | Limit |
|---------------|-------|
| 1 | 25 L |
| 2 | 50 L |
| 3 | 100 L |
| 4 | FREE FLOW |

| LEDs | Limit |
|------|-------|
| 25 L LED on | 25 L |
| 50 L LED on | 50 L |
| 100 L LED on | 100 L |
| All off | FREE FLOW (counts, never pulses) |

### Resetting the count

- **Remote:** hold **any** button for 2 seconds. The count goes to 0 L and the valve
  clicks twice (0.25 s shut, 0.25 s open, twice) to confirm. The limit does not change.
- **Push button:** any short press resets the count (and moves to the next limit).

### When the limit is reached

The valve shuts for 0.5 s and opens for 0.5 s, six times (6 seconds in total). The
selected LED blinks along with it. The count goes back to 0 L and keeps counting, so
the warning repeats every 25/50/100 L until the count is reset. A push-button press
or a 2 s remote hold during the warning stops it straight away.

### Calibration (7 L bucket)

1. Turn the water off and put a 7 L bucket under the outlet.
2. Hold the push button **or remote button 4 (FREE FLOW)** for **20 seconds** until
   all three LEDs start flashing, then let go.
   - Push button: presses between 2 s and 20 s are ignored, so you can let go early to cancel.
   - Remote button 4: the valve clicks twice at 2 s (that is the count reset); keep holding.
   - Remote buttons 1–3 cannot start or finish calibration.
3. Turn the water on and fill the bucket to exactly 7 L, then turn the water off.
4. Short-press the push button or remote button 4.
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

## Serial Monitor

Open the Serial Monitor at **115200 baud**. One status line is printed every second,
plus a message whenever something happens:

```
=== Water Valve Controller ===
Calibration: 64.80 pulses/L (datasheet default)
Limit: 25L
Button: short press = next limit + reset count | hold 20 s = calibrate
Remote: 1 = 25L, 2 = 50L, 3 = 100L, 4 = FREE FLOW | hold any 2 s = reset count
        hold 4 for 20 s = calibrate

Flow: 10.00 L/min | Limit: 25L | Count: 24.83 L | Session: 24.83 L | Valve: OPEN | NORMAL
>> Limit of 25L reached - pulsing valve, count restarted at 0 L
Flow: 10.00 L/min | Limit: 25L | Count: 0.15 L | Session: 25.15 L | Valve: SHUT | LIMIT REACHED
```

- **Count:** litres counted towards the current limit. Goes back to 0 when the limit is reached.
- **Session:** total litres since power-up or the last count reset.
  This is not reset when the limit is reached.

## ESP data output (D11)

D11 sends one JSON line every second at **9600 baud** (8N1, 5 V logic, so use the divider above):

```json
{"flow_lpm":10.00,"limit":"25L","limit_l":25,"count_l":0.15,"session_l":25.15,"valve":"SHUT","state":"LIMIT REACHED","ppl":64.80,"calibrated":false}
```

| Field | Meaning |
|-------|---------|
| `flow_lpm` | Current flow rate, L/min |
| `limit` | `"25L"`, `"50L"`, `"100L"` or `"FREE FLOW"` |
| `limit_l` | Limit in litres (`0` = free flow) |
| `count_l` | Current count towards the limit, L |
| `session_l` | Total since power-up or last count reset, L |
| `valve` | `"OPEN"` or `"SHUT"` |
| `state` | `"NORMAL"`, `"LIMIT REACHED"`, `"COUNT RESET"` (during the 2 clicks) or `"CALIBRATING"` |
| `ppl` | Calibration in pulses per litre |
| `calibrated` | `false` = datasheet default, `true` = user calibration |

On the ESP, read lines from its RX (`Serial` or `SoftwareSerial` at 9600) and parse
them with ArduinoJson.

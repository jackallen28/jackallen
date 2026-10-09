# Water Valve Controller (Arduino Nano)

Counts the water going through a YF-G1 flow sensor and warns the user when a
chosen amount has been used by briefly pulsing the solenoid valve shut.

- Choose **25 L**, **50 L**, **100 L** or **FREE FLOW** with the push button or the 433 MHz remote.
- When the limit is reached, the valve shuts and opens 6 times (0.5 s shut, 0.5 s open),
  then water keeps flowing and the count starts again at 0 L.
- Any press of the button or the remote resets the count to 0 L.
- Hold the button for 20 s to calibrate with a 7 L bucket. The calibration is saved
  and survives power cuts. The water count always starts at 0 L after power-up.
- Flow rate, limit and count are printed to the Serial Monitor and sent to a spare
  pin for a future ESP8266/ESP32.

## Parts

| Part | Notes |
|------|-------|
| Arduino Nano (ATmega328P) | |
| YF-G1 flow sensor (1–100 L/min, F = 1 × Q) | 60 pulses per litre by default |
| Solenoid valve + 1-channel relay module | |
| Momentary push button | |
| 3 × LED + 3 × 220 Ω resistor | 25 L, 50 L, 100 L |
| 433 MHz 4-channel relay receiver + remote | |
| ESP8266 / ESP32 (optional, later) | 3.3 V logic, needs a voltage divider |

## Wiring

| Arduino Nano pin | Connects to |
|------------------|-------------|
| **D2** | Flow sensor signal (yellow). Red → 5 V, black → GND |
| **D4** | Push button; other side of the button → GND |
| **D5** | 220 Ω → LED "25 L" → GND |
| **D6** | 220 Ω → LED "50 L" → GND |
| **D7** | 220 Ω → LED "100 L" → GND |
| **D8** | Relay module IN (relay VCC → 5 V, GND → GND) |
| **A0** | Remote receiver channel A: NO terminal (COM terminal → GND) |
| **A1** | Remote receiver channel B: NO terminal (COM terminal → GND) |
| **A2**, **A3** | Remote channels C and D (not used by default, see settings) |
| **D11** | Data out to ESP RX, through a 1 kΩ / 2 kΩ divider (see below) |
| **D12** | Reserved for ESP TX → Nano (not used yet) |

**Solenoid:** wire the solenoid supply through the relay's **COM** and **NO**
terminals. The sketch handles both normally-closed and normally-open valves (see
`VALVE_NORMALLY_CLOSED` below). If the valve is a DC solenoid, fit a flyback diode
(e.g. 1N4007) across the coil, with the stripe towards +. Without it, the voltage
spike when the coil switches off can reset the Nano or add false flow pulses.

**Power:** a 12 V supply can feed the solenoid, the remote receiver (if it is a 12 V
board) and the Nano's **VIN** pin. All grounds must be connected together.

**Remote receiver:** these boards switch a small relay per channel, so they act like
extra push buttons. Put the receiver in **momentary** mode (output on only while the
remote button is held). The receiver's instructions explain how; on most boards it
is a jumper or a learn-button sequence. If yours can only latch/toggle, set
`REMOTE_TOGGLE_MODE = true`.

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
| `REMOTE_ACTIVE_LOW` | `true` | Your receiver has logic outputs that go HIGH when pressed (no relays) → set `false` |
| `REMOTE_TOGGLE_MODE` | `false` | Your receiver can only latch/toggle → set `true` |
| `REMOTE_ACTIONS` | A = next limit, B = reset count | You want other remote buttons to do something (options: next limit, reset count, select 25 L / 50 L / 100 L / free flow) |
| `REMEMBER_LIMIT` | `true` | You want it to start in FREE FLOW after every power-up → set `false` |

**Quick check:** power it up in FREE FLOW (all LEDs off) with the water on. Water
should flow. If it doesn't, flip `VALVE_NORMALLY_CLOSED`. If the relay is in the
wrong state, flip `RELAY_ACTIVE_LOW`.

Upload with the Arduino IDE: **Tools → Board → Arduino Nano**. If the upload fails,
try **Tools → Processor → ATmega328P (Old Bootloader)**. No extra libraries are
needed (`EEPROM` and `SoftwareSerial` are built in).

## How to use it

### Choosing a limit

Short-press the button (or remote button A) to step through the limits. Every press
also resets the count to 0 L.

| LEDs | Limit |
|------|-------|
| 25 L LED on | 25 L |
| 50 L LED on | 50 L |
| 100 L LED on | 100 L |
| All off | FREE FLOW (counts, never pulses) |

Remote button B resets the count to 0 L without changing the limit.

### When the limit is reached

The valve shuts for 0.5 s and opens for 0.5 s, six times (6 seconds in total). The
selected LED blinks along with it. The count goes back to 0 L and keeps counting, so
the warning repeats every 25/50/100 L until someone presses the button or remote.
A press during the warning stops it straight away.

### Calibration (7 L bucket)

1. Turn the water off and put a 7 L bucket under the outlet.
2. Hold the button down for **20 seconds** until all three LEDs start flashing, then let go.
   Presses between 2 s and 20 s are ignored, so you can let go early to cancel.
3. Turn the water on and fill the bucket to exactly 7 L, then turn the water off.
4. Short-press the button (remote button A works too).
   - **All LEDs on for 2 s:** calibration saved.
   - **All LEDs flash quickly for 2 s:** the result was not sensible (for example
     no water ran), so the previous calibration is kept. Pressing straight away
     without running water is how you cancel calibration mode.

The limit is not enforced during calibration, so the valve stays open. The count is
reset to 0 L afterwards.

Out of the box the sketch uses the YF-G1 datasheet value (F = 1 × Q, which is
60 pulses per litre). A saved calibration replaces it permanently, including after
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
Calibration: 60.00 pulses/L (datasheet default)
Limit: 25L
Short press: next limit + reset count | Hold 20 s: calibrate

Flow: 10.00 L/min | Limit: 25L | Count: 24.83 L | Session: 24.83 L | Valve: OPEN | NORMAL
>> Limit of 25L reached - pulsing valve, count restarted at 0 L
Flow: 10.00 L/min | Limit: 25L | Count: 0.15 L | Session: 25.15 L | Valve: SHUT | LIMIT REACHED
```

- **Count:** litres counted towards the current limit. Goes back to 0 when the limit is reached.
- **Session:** total litres since power-up or the last button/remote press.
  This is not reset when the limit is reached.

## ESP data output (D11)

D11 sends one JSON line every second at **9600 baud** (8N1, 5 V logic, so use the divider above):

```json
{"flow_lpm":10.00,"limit":"25L","limit_l":25,"count_l":0.15,"session_l":25.15,"valve":"SHUT","state":"LIMIT REACHED","ppl":60.00,"calibrated":false}
```

| Field | Meaning |
|-------|---------|
| `flow_lpm` | Current flow rate, L/min |
| `limit` | `"25L"`, `"50L"`, `"100L"` or `"FREE FLOW"` |
| `limit_l` | Limit in litres (`0` = free flow) |
| `count_l` | Current count towards the limit, L |
| `session_l` | Total since power-up or last press, L |
| `valve` | `"OPEN"` or `"SHUT"` |
| `state` | `"NORMAL"`, `"LIMIT REACHED"` or `"CALIBRATING"` |
| `ppl` | Calibration in pulses per litre |
| `calibrated` | `false` = datasheet default, `true` = user calibration |

On the ESP, read lines from its RX (`Serial` or `SoftwareSerial` at 9600) and parse
them with ArduinoJson.

/*
  Water Valve Controller
  ======================
  Arduino Nano + YF-G1 hall-effect flow sensor + relay-driven solenoid valve.

  - Pick one of three limits (25 L, 50 L, 100 L by default, see LIMIT VOLUMES
    below) or FREE FLOW with the push button (each press steps to the next
    limit) or the 433 MHz remote (button A = limit 1, B = limit 2, C = limit 3,
    D = FREE FLOW; the valve clicks twice to confirm). Three LEDs show the
    limit; all LEDs off = FREE FLOW.
  - When the limit is reached the valve is pulsed shut 4 times (0.5 s shut,
    0.5 s open) as a warning. Water then keeps flowing and the count starts
    again from 0 L towards the next warning once the pulses have finished.
  - A press of the push button resets the count to 0 L. On the remote, hold any
    button for 2 s to reset the count; the valve clicks twice to confirm.
  - Hold the push button, or remote button D (FREE FLOW), for 20 s to calibrate
    with a 7 L bucket. The calibration is saved to EEPROM and survives power
    loss; the water count always starts at 0 L after power-up.
  - Status (flow rate, limit, count) is printed to the Serial Monitor and sent
    as one JSON line per second on a spare pin for an ESP32 board.

  See README.md for wiring and full instructions.
*/

#include <EEPROM.h>
#include <SoftwareSerial.h>

// ===========================================================================
// LIMIT VOLUMES - change these numbers to set the three limits, in litres.
//   Limit 1: LED on D5, remote button A
//   Limit 2: LED on D6, remote button B
//   Limit 3: LED on D7, remote button C
//   FREE FLOW (all LEDs off): remote button D
// ===========================================================================
const uint16_t LIMIT_1_LITRES = 25;
const uint16_t LIMIT_2_LITRES = 50;
const uint16_t LIMIT_3_LITRES = 100;

// ---------------------------------------------------------------------------
// Pin assignments (Arduino Nano)
// ---------------------------------------------------------------------------
const uint8_t PIN_FLOW_SENSOR = 2;   // must be D2 or D3 (external interrupt pins)
const uint8_t PIN_BUTTON      = 4;   // momentary push button to GND
const uint8_t PIN_LED_LIMIT_1 = 5;
const uint8_t PIN_LED_LIMIT_2 = 6;
const uint8_t PIN_LED_LIMIT_3 = 7;
const uint8_t PIN_RELAY       = 8;   // relay module IN (switches the solenoid)
const uint8_t PIN_ESP_TX      = 11;  // data out to the ESP (through a 5 V -> 3.3 V divider)
const uint8_t PIN_ESP_RX      = 12;  // reserved for data back from the ESP (not used yet)
// Receiver outputs for remote buttons A, B, C, D. On the RX480R_4CH V4 that was
// tested, button A drives D3 (wired to A3) and button D drives D0 (A0). If a
// button picks the wrong limit, change the order here.
const uint8_t PIN_REMOTE[4]   = { A3, A2, A1, A0 };

// ---------------------------------------------------------------------------
// Hardware options - change these to suit your parts
// ---------------------------------------------------------------------------

// Solenoid valve type.
//   true  = normally CLOSED valve (the most common 12 V type): it must be
//           powered to let water through, so the relay is ON while water flows.
//   false = normally OPEN valve: it is powered to stop the water, so the relay
//           is OFF while water flows.
const bool VALVE_NORMALLY_CLOSED = true;

// Most cheap relay modules switch ON when their IN pin is pulled LOW.
// Set to false if your relay module switches ON when IN is HIGH.
const bool RELAY_ACTIVE_LOW = true;

// 433 MHz receiver outputs. The remote must be paired in MOMENTARY mode (output
// on only while the remote button is held) so that 2 s and 20 s holds can be timed.
//   false = logic-output receiver such as the RX480E: D0-D3 go HIGH while a
//           button is pressed. The board's 100k pull-downs keep them LOW otherwise.
//   true  = relay-output receiver: wire each channel's COM to GND and NO to the
//           Arduino pin. The internal pull-up is used, so pressed = LOW.
const bool REMOTE_ACTIVE_LOW = false;

// Some RX480E boards only drive their outputs to about 3 V, right at the Nano's
// minimum for a guaranteed digital HIGH (the tested board gave 4.9 V). Logic-output
// receivers are therefore read with the analog converter, and anything above this
// level counts as pressed.
const int REMOTE_HIGH_THRESHOLD = 307;  // 0-1023 scale: 307 = 1.5 V on a 5 V supply

// Set to true if choosing a limit on the remote should also reset the count.
// When false, the count is kept and only a 2 s hold resets it.
const bool REMOTE_SELECT_RESETS_COUNT = false;

// ---------------------------------------------------------------------------
// Flow sensor and calibration
// ---------------------------------------------------------------------------

// YF-G1 spec sheet: F (Hz) = 1.08 x Q (L/min), "about 64.8 P/L"
//   -> 1.08 pulses/s per L/min x 60 s = 64.8 pulses per litre (+/- 3%).
const float DEFAULT_PULSES_PER_LITRE = 64.8;
const float CAL_BUCKET_LITRES        = 7.0;
const float MIN_PULSES_PER_LITRE     = 5.0;     // calibration results outside this
const float MAX_PULSES_PER_LITRE     = 1000.0;  // range are rejected as mistakes

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
const unsigned long DEBOUNCE_MS          = 50;
const unsigned long REMOTE_PRESS_MS      = 20;     // remote output ON this long = pressed (catches 0.1 s pulses)
const unsigned long REMOTE_RELEASE_MS    = 150;    // OFF this long = released (rides out brief RF drop-outs)
const unsigned long SHORT_PRESS_MAX_MS   = 2000;   // push button presses between this and CAL_HOLD_MS do nothing
const unsigned long REMOTE_RESET_HOLD_MS = 2000;   // hold any remote button this long to reset the count
const unsigned long CAL_HOLD_MS          = 20000;  // hold the push button / remote button D this long to calibrate
const uint8_t       ALERT_PULSES         = 4;      // valve shut/open cycles when the limit is reached
const unsigned long ALERT_PHASE_MS       = 500;    // 0.5 s shut, then 0.5 s open
const uint8_t       CONFIRM_CLICKS       = 2;      // valve shut/open cycles to confirm a remote limit choice or reset
const unsigned long CONFIRM_CLICK_MS     = 250;    // 0.25 s shut, then 0.25 s open
const unsigned long CAL_FLASH_MS       = 500;    // LED flash rate in calibration mode
const unsigned long FEEDBACK_MS        = 2000;   // LED pattern after a calibration attempt
const unsigned long REPORT_INTERVAL_MS = 1000;   // serial / ESP status rate
const unsigned long FLOW_TIMEOUT_MS    = 3000;   // no pulses for this long = 0 L/min
const unsigned long PULSE_GLITCH_US    = 2000;   // pulses closer than this are noise (> 500 Hz)

const long SERIAL_BAUD = 115200;
const long ESP_BAUD    = 9600;

// Remember the selected limit after a power cut (the count is always reset).
const bool REMEMBER_LIMIT = true;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
enum LimitMode : uint8_t { MODE_LIMIT_1, MODE_LIMIT_2, MODE_LIMIT_3, MODE_FREE, MODE_COUNT };
const uint16_t LIMIT_LITRES[MODE_COUNT] = { LIMIT_1_LITRES, LIMIT_2_LITRES, LIMIT_3_LITRES, 0 };

// Limit chosen by remote buttons A-D. The FREE FLOW button is also the only
// remote button that can start and finish calibration.
const LimitMode REMOTE_MODES[4] = { MODE_LIMIT_1, MODE_LIMIT_2, MODE_LIMIT_3, MODE_FREE };

enum SystemState : uint8_t { STATE_NORMAL, STATE_LIMIT_ALERT, STATE_CONFIRM_CLICKS, STATE_CALIBRATING };

enum LedFeedback : uint8_t { FEEDBACK_NONE, FEEDBACK_CAL_OK, FEEDBACK_CAL_FAILED };

struct DebouncedInput {
  bool stable;               // debounced level (true = active/pressed)
  bool lastRaw;
  unsigned long changedAt;
};

struct RemoteButton {
  DebouncedInput input;
  unsigned long pressedAt;
  bool holdHandled;          // 2 s hold already acted on, so releasing does nothing
  bool calHoldHandled;       // 20 s hold already acted on
};

struct CalibrationRecord {
  uint16_t magic;
  float pulsesPerLitre;
  uint16_t checksum;
};

// The ESP status line is built here, then sent one character per loop. Sending
// it in one go at 9600 baud would stall the sketch for about 0.14 s, long
// enough to miss a short remote press.
char espLine[200];
uint8_t espLength = 0;
uint8_t espSent = 0;

class EspLineBuffer : public Print {
 public:
  size_t write(uint8_t c) override {
    if (espLength >= sizeof(espLine)) return 0;
    espLine[espLength++] = c;
    return 1;
  }
};

const int      EEPROM_CAL_ADDR  = 0;
const int      EEPROM_MODE_ADDR = 16;  // mode byte followed by its inverse
const uint16_t EEPROM_MAGIC     = 0xA57C;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
SoftwareSerial espSerial(PIN_ESP_RX, PIN_ESP_TX);

volatile uint32_t isrPulseCount  = 0;
volatile uint32_t isrLastPulseUs = 0;

float pulsesPerLitre = DEFAULT_PULSES_PER_LITRE;
bool isCalibrated = false;              // true when loaded from EEPROM / user calibration
LimitMode limitMode = MODE_FREE;
SystemState state = STATE_NORMAL;
bool valveOpen = true;

uint32_t lastPulseCount = 0;  // isrPulseCount value already added to the counters below
uint32_t countPulses = 0;     // towards the limit: back to 0 at the limit and on a reset
uint32_t sessionPulses = 0;   // since power-up or the last reset (not reset at the limit)
uint32_t calPulses = 0;       // since calibration mode started

float flowHz = 0;
uint32_t rateRefPulses = 0;
uint32_t rateRefUs = 0;
bool rateRefValid = false;

DebouncedInput button = { false, false, 0 };
unsigned long buttonPressedAt = 0;
bool buttonHoldHandled = false;
RemoteButton remote[4];

// Valve pulse sequence used by the limit alert and the confirmation clicks.
uint8_t pulsePhase = 0;       // even = valve shut, odd = valve open
uint8_t pulsePhases = 0;
unsigned long pulsePhaseMs = 0;
unsigned long pulsePhaseStart = 0;
unsigned long calStartedAt = 0;
LedFeedback ledFeedback = FEEDBACK_NONE;
unsigned long ledFeedbackStart = 0;
unsigned long lastReportAt = 0;

// ---------------------------------------------------------------------------
// Flow sensor interrupt
// ---------------------------------------------------------------------------
void onFlowPulse() {
  uint32_t nowUs = micros();
  if (nowUs - isrLastPulseUs < PULSE_GLITCH_US) return;
  isrLastPulseUs = nowUs;
  isrPulseCount++;
}

// Adds pulses received since the last call to every counter.
void collectPulses() {
  noInterrupts();
  uint32_t pulses = isrPulseCount;
  interrupts();

  uint32_t delta = pulses - lastPulseCount;
  lastPulseCount = pulses;
  countPulses += delta;
  sessionPulses += delta;
  if (state == STATE_CALIBRATING) calPulses += delta;
}

// Flow rate from the time between the last pulse of the previous update and
// the last pulse of this one, which stays accurate at low flow rates.
void updateFlowRate() {
  noInterrupts();
  uint32_t pulses = isrPulseCount;
  uint32_t lastUs = isrLastPulseUs;
  interrupts();

  uint32_t newPulses = pulses - rateRefPulses;
  if (newPulses > 0) {
    if (rateRefValid && lastUs != rateRefUs) {
      flowHz = newPulses * 1000000.0 / (uint32_t)(lastUs - rateRefUs);
    }
    rateRefPulses = pulses;
    rateRefUs = lastUs;
    rateRefValid = true;
  } else if (rateRefValid && micros() - lastUs > FLOW_TIMEOUT_MS * 1000UL) {
    flowHz = 0;
    rateRefValid = false;
  }
}

float flowLitresPerMinute() {
  return flowHz * 60.0 / pulsesPerLitre;
}

float pulsesToLitres(uint32_t pulses) {
  return pulses / pulsesPerLitre;
}

// ---------------------------------------------------------------------------
// Valve
// ---------------------------------------------------------------------------
void setValveOpen(bool open) {
  valveOpen = open;
  bool relayOn = VALVE_NORMALLY_CLOSED ? open : !open;
  digitalWrite(PIN_RELAY, (relayOn != RELAY_ACTIVE_LOW) ? HIGH : LOW);
}

// ---------------------------------------------------------------------------
// EEPROM
// ---------------------------------------------------------------------------
bool isValidPulsesPerLitre(float ppl) {
  return ppl >= MIN_PULSES_PER_LITRE && ppl <= MAX_PULSES_PER_LITRE;  // also false for NaN
}

uint16_t calibrationChecksum(const CalibrationRecord &record) {
  const uint8_t *bytes = (const uint8_t *)&record.pulsesPerLitre;
  uint16_t sum = record.magic;
  for (uint8_t i = 0; i < sizeof(record.pulsesPerLitre); i++) {
    sum = sum * 31 + bytes[i];
  }
  return sum;
}

void loadCalibration() {
  CalibrationRecord record;
  EEPROM.get(EEPROM_CAL_ADDR, record);
  if (record.magic == EEPROM_MAGIC && record.checksum == calibrationChecksum(record) &&
      isValidPulsesPerLitre(record.pulsesPerLitre)) {
    pulsesPerLitre = record.pulsesPerLitre;
    isCalibrated = true;
  } else {
    pulsesPerLitre = DEFAULT_PULSES_PER_LITRE;
    isCalibrated = false;
  }
}

void saveCalibration() {
  CalibrationRecord record;
  record.magic = EEPROM_MAGIC;
  record.pulsesPerLitre = pulsesPerLitre;
  record.checksum = calibrationChecksum(record);
  EEPROM.put(EEPROM_CAL_ADDR, record);
}

void loadMode() {
  uint8_t mode = EEPROM.read(EEPROM_MODE_ADDR);
  uint8_t inverse = EEPROM.read(EEPROM_MODE_ADDR + 1);
  if (REMEMBER_LIMIT && mode < MODE_COUNT && (uint8_t)~mode == inverse) {
    limitMode = (LimitMode)mode;
  } else {
    limitMode = MODE_FREE;
  }
}

void saveMode() {
  EEPROM.update(EEPROM_MODE_ADDR, limitMode);
  EEPROM.update(EEPROM_MODE_ADDR + 1, (uint8_t)~limitMode);
}

// ---------------------------------------------------------------------------
// Text helpers
// ---------------------------------------------------------------------------
// Prints a limit as "25L" (using the LIMIT VOLUMES settings) or "FREE FLOW".
void printLimit(Print &out, LimitMode mode) {
  if (mode == MODE_FREE) {
    out.print(F("FREE FLOW"));
  } else {
    out.print(LIMIT_LITRES[mode]);
    out.print('L');
  }
}

const char *stateName() {
  switch (state) {
    case STATE_LIMIT_ALERT:  return "LIMIT REACHED";
    case STATE_CONFIRM_CLICKS: return "CONFIRM CLICKS";
    case STATE_CALIBRATING:  return "CALIBRATING";
    default:                return "NORMAL";
  }
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
bool valvePulsing() {
  return state == STATE_LIMIT_ALERT || state == STATE_CONFIRM_CLICKS;
}

// Shuts the valve, then alternates open/shut every phaseMs for the given
// number of shut/open cycles, ending with the valve open.
void startValvePulses(SystemState pulseState, uint8_t pulses, unsigned long phaseMs, unsigned long now) {
  state = pulseState;
  pulsePhase = 0;
  pulsePhases = pulses * 2;
  pulsePhaseMs = phaseMs;
  pulsePhaseStart = now;
  setValveOpen(false);
}

void endValvePulses() {
  if (valvePulsing()) state = STATE_NORMAL;
  setValveOpen(true);
}

void updateValvePulses(unsigned long now) {
  if (!valvePulsing() || now - pulsePhaseStart < pulsePhaseMs) return;
  pulsePhaseStart += pulsePhaseMs;
  pulsePhase++;
  if (pulsePhase >= pulsePhases) {
    if (state == STATE_LIMIT_ALERT) {
      // Water that ran during the warning doesn't count towards the next limit,
      // otherwise a small limit can be used up before the warning even ends.
      collectPulses();
      countPulses = 0;
    }
    endValvePulses();
  } else {
    setValveOpen(pulsePhase % 2 == 1);
  }
}

void resetCount() {
  collectPulses();  // pulses before the reset must not appear after it
  countPulses = 0;
  sessionPulses = 0;
  endValvePulses();
  Serial.println(F(">> Count reset to 0 L"));
}

// Two quick valve clicks, so a remote press can be heard from a distance.
void confirmWithClicks(unsigned long now) {
  startValvePulses(STATE_CONFIRM_CLICKS, CONFIRM_CLICKS, CONFIRM_CLICK_MS, now);
}

// Remote 2 s hold: reset, then click the valve to confirm.
void resetCountWithClicks(unsigned long now) {
  resetCount();
  confirmWithClicks(now);
}

void selectMode(LimitMode mode, bool resetCounter) {
  limitMode = mode;
  if (REMEMBER_LIMIT) saveMode();
  Serial.print(F(">> Limit set to "));
  printLimit(Serial, limitMode);
  Serial.println();
  if (resetCounter) resetCount();
}

void checkLimit(unsigned long now) {
  if (state != STATE_NORMAL || limitMode == MODE_FREE) return;
  uint32_t limitPulses = (uint32_t)(LIMIT_LITRES[limitMode] * pulsesPerLitre + 0.5);
  if (countPulses >= limitPulses) {
    countPulses = 0;
    startValvePulses(STATE_LIMIT_ALERT, ALERT_PULSES, ALERT_PHASE_MS, now);
    Serial.print(F(">> Limit of "));
    printLimit(Serial, limitMode);
    Serial.println(F(" reached - pulsing valve, count restarted at 0 L"));
  }
}

void startCalibration(unsigned long now) {
  collectPulses();  // pulses before calibration starts are not part of the bucket
  endValvePulses();
  state = STATE_CALIBRATING;
  calPulses = 0;
  calStartedAt = now;
  Serial.println(F(""));
  Serial.println(F(">> CALIBRATION MODE"));
  Serial.print(F("   Fill a "));
  Serial.print(CAL_BUCKET_LITRES, 1);
  Serial.println(F(" L bucket, turn the water off, then press the button (or remote button D)."));
  Serial.println(F("   (Pressing without running any water cancels calibration.)"));
}

void finishCalibration(unsigned long now) {
  collectPulses();
  float measured = calPulses / CAL_BUCKET_LITRES;

  Serial.print(F(">> Calibration: "));
  Serial.print(calPulses);
  Serial.print(F(" pulses for "));
  Serial.print(CAL_BUCKET_LITRES, 1);
  Serial.print(F(" L = "));
  Serial.print(measured, 2);
  Serial.println(F(" pulses/L"));

  if (isValidPulsesPerLitre(measured)) {
    pulsesPerLitre = measured;
    isCalibrated = true;
    saveCalibration();
    ledFeedback = FEEDBACK_CAL_OK;
    Serial.println(F(">> Calibration saved"));
  } else {
    ledFeedback = FEEDBACK_CAL_FAILED;
    Serial.print(F(">> Calibration rejected, keeping "));
    Serial.print(pulsesPerLitre, 2);
    Serial.println(F(" pulses/L"));
  }
  ledFeedbackStart = now;
  state = STATE_NORMAL;
  resetCount();
}

// Short press of the push button: next limit and reset the count.
void onButtonShortPress(unsigned long now) {
  if (state == STATE_CALIBRATING) {
    finishCalibration(now);
  } else {
    selectMode((LimitMode)((limitMode + 1) % MODE_COUNT), true);
  }
}

// Remote button released within 2 s: choose that button's limit, then click
// the valve twice to confirm.
void onRemoteShortPress(uint8_t channel, unsigned long now) {
  LimitMode mode = REMOTE_MODES[channel];
  if (state == STATE_CALIBRATING) {
    if (mode == MODE_FREE) finishCalibration(now);  // other remote buttons are ignored
  } else {
    selectMode(mode, REMOTE_SELECT_RESETS_COUNT);
    confirmWithClicks(now);
  }
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

// Returns true when the debounced level changes. onMs is how long the input must
// stay active to count as pressed, offMs how long inactive to count as released.
bool debounce(DebouncedInput &input, bool raw, unsigned long now, unsigned long onMs, unsigned long offMs) {
  if (raw != input.lastRaw) {
    input.lastRaw = raw;
    input.changedAt = now;
  }
  if (raw != input.stable && now - input.changedAt >= (raw ? onMs : offMs)) {
    input.stable = raw;
    return true;
  }
  return false;
}

bool readRemote(uint8_t channel) {
  if (REMOTE_ACTIVE_LOW) return digitalRead(PIN_REMOTE[channel]) == LOW;
  return analogRead(PIN_REMOTE[channel]) > REMOTE_HIGH_THRESHOLD;
}

void handleButton(unsigned long now) {
  bool pressed = digitalRead(PIN_BUTTON) == LOW;

  if (debounce(button, pressed, now, DEBOUNCE_MS, DEBOUNCE_MS)) {
    if (button.stable) {
      buttonPressedAt = now;
      buttonHoldHandled = false;
    } else if (!buttonHoldHandled && now - buttonPressedAt <= SHORT_PRESS_MAX_MS) {
      onButtonShortPress(now);
    }
  }

  if (button.stable && !buttonHoldHandled && now - buttonPressedAt >= CAL_HOLD_MS) {
    buttonHoldHandled = true;  // releasing after the hold does nothing
    if (state != STATE_CALIBRATING) startCalibration(now);
  }
}

// Remote buttons: release within 2 s = choose that limit, hold any button 2 s =
// reset the count, hold the FREE FLOW button 20 s = calibration.
void handleRemote(unsigned long now) {
  for (uint8_t i = 0; i < 4; i++) {
    RemoteButton &b = remote[i];

    if (debounce(b.input, readRemote(i), now, REMOTE_PRESS_MS, REMOTE_RELEASE_MS)) {
      if (b.input.stable) {
        b.pressedAt = now;
        b.holdHandled = false;
        b.calHoldHandled = false;
      } else if (!b.holdHandled) {
        onRemoteShortPress(i, now);
      }
    }
    if (!b.input.stable) continue;

    unsigned long heldMs = now - b.pressedAt;
    if (!b.holdHandled && heldMs >= REMOTE_RESET_HOLD_MS) {
      b.holdHandled = true;
      if (state != STATE_CALIBRATING) resetCountWithClicks(now);
    }
    if (REMOTE_MODES[i] == MODE_FREE && !b.calHoldHandled && heldMs >= CAL_HOLD_MS) {
      b.calHoldHandled = true;
      if (state != STATE_CALIBRATING) startCalibration(now);
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
void updateLeds(unsigned long now) {
  bool led1 = false, led2 = false, led3 = false;

  if (ledFeedback != FEEDBACK_NONE && now - ledFeedbackStart >= FEEDBACK_MS) {
    ledFeedback = FEEDBACK_NONE;
  }

  if (ledFeedback == FEEDBACK_CAL_OK) {
    led1 = led2 = led3 = true;                                   // solid = saved
  } else if (ledFeedback == FEEDBACK_CAL_FAILED) {
    led1 = led2 = led3 = ((now - ledFeedbackStart) / 100) % 2 == 0;  // fast flash = rejected
  } else if (state == STATE_CALIBRATING) {
    led1 = led2 = led3 = ((now - calStartedAt) / CAL_FLASH_MS) % 2 == 0;
  } else {
    // The selected LED blinks in time with the valve while it is being pulsed.
    bool on = !valvePulsing() || valveOpen;
    led1 = on && limitMode == MODE_LIMIT_1;
    led2 = on && limitMode == MODE_LIMIT_2;
    led3 = on && limitMode == MODE_LIMIT_3;
  }

  digitalWrite(PIN_LED_LIMIT_1, led1 ? HIGH : LOW);
  digitalWrite(PIN_LED_LIMIT_2, led2 ? HIGH : LOW);
  digitalWrite(PIN_LED_LIMIT_3, led3 ? HIGH : LOW);
}

// Human-readable line for the Serial Monitor.
void reportSerial() {
  Serial.print(F("Flow: "));
  Serial.print(flowLitresPerMinute(), 2);
  Serial.print(F(" L/min | Limit: "));
  printLimit(Serial, limitMode);
  Serial.print(F(" | Count: "));
  Serial.print(pulsesToLitres(countPulses), 2);
  Serial.print(F(" L | Session: "));
  Serial.print(pulsesToLitres(sessionPulses), 2);
  Serial.print(F(" L | Valve: "));
  Serial.print(valveOpen ? F("OPEN") : F("SHUT"));
  Serial.print(F(" | "));
  Serial.print(stateName());
  if (state == STATE_CALIBRATING) {
    Serial.print(F(" | Cal pulses: "));
    Serial.print(calPulses);
  }
  Serial.println();
}

// One JSON object per line for the ESP, e.g.
// {"flow_lpm":12.34,"limit":"50L","limit_l":50,"count_l":23.45,"session_l":73.45,
//  "valve":"OPEN","state":"NORMAL","ppl":64.80,"calibrated":false}
// The line is only built here; sendEspCharacter() sends it.
void buildEspLine() {
  espLength = 0;
  espSent = 0;
  EspLineBuffer out;
  out.print(F("{\"flow_lpm\":"));
  out.print(flowLitresPerMinute(), 2);
  out.print(F(",\"limit\":\""));
  printLimit(out, limitMode);
  out.print(F("\",\"limit_l\":"));
  out.print(LIMIT_LITRES[limitMode]);
  out.print(F(",\"count_l\":"));
  out.print(pulsesToLitres(countPulses), 2);
  out.print(F(",\"session_l\":"));
  out.print(pulsesToLitres(sessionPulses), 2);
  out.print(F(",\"valve\":\""));
  out.print(valveOpen ? F("OPEN") : F("SHUT"));
  out.print(F("\",\"state\":\""));
  out.print(stateName());
  out.print(F("\",\"ppl\":"));
  out.print(pulsesPerLitre, 2);
  out.print(F(",\"calibrated\":"));
  out.print(isCalibrated ? F("true") : F("false"));
  out.println(F("}"));
}

void sendEspCharacter() {
  if (espSent < espLength) espSerial.write(espLine[espSent++]);
}

void report(unsigned long now) {
  if (now - lastReportAt < REPORT_INTERVAL_MS) return;
  lastReportAt = now;
  updateFlowRate();
  reportSerial();
  if (espSent >= espLength) buildEspLine();  // skip a line if the last one is still going out
}

// ---------------------------------------------------------------------------
// Setup and main loop
// ---------------------------------------------------------------------------
void setup() {
  // Set the relay level before enabling the output so the valve does not glitch.
  setValveOpen(true);
  pinMode(PIN_RELAY, OUTPUT);
  setValveOpen(true);

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_FLOW_SENSOR, INPUT_PULLUP);
  pinMode(PIN_LED_LIMIT_1, OUTPUT);
  pinMode(PIN_LED_LIMIT_2, OUTPUT);
  pinMode(PIN_LED_LIMIT_3, OUTPUT);
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(PIN_REMOTE[i], REMOTE_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  }

  Serial.begin(SERIAL_BAUD);
  espSerial.begin(ESP_BAUD);

  loadCalibration();
  loadMode();

  // LED self-test so a wiring fault is obvious at power-up.
  const uint8_t leds[3] = { PIN_LED_LIMIT_1, PIN_LED_LIMIT_2, PIN_LED_LIMIT_3 };
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(leds[i], HIGH);
    delay(200);
    digitalWrite(leds[i], LOW);
  }

  // A remote output that is already on at power-up (stuck, latched or wrongly
  // configured) is ignored until it has been released.
  unsigned long now = millis();
  for (uint8_t i = 0; i < 4; i++) {
    bool level = readRemote(i);
    remote[i] = { { level, level, now }, now, level, level };
  }

  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_SENSOR), onFlowPulse, FALLING);

  Serial.println(F(""));
  Serial.println(F("=== Water Valve Controller ==="));
  Serial.print(F("Calibration: "));
  Serial.print(pulsesPerLitre, 2);
  Serial.println(isCalibrated ? F(" pulses/L (saved)") : F(" pulses/L (datasheet default)"));
  Serial.print(F("Limit: "));
  printLimit(Serial, limitMode);
  Serial.println();
  Serial.print(F("Limits: A = "));
  printLimit(Serial, MODE_LIMIT_1);
  Serial.print(F(", B = "));
  printLimit(Serial, MODE_LIMIT_2);
  Serial.print(F(", C = "));
  printLimit(Serial, MODE_LIMIT_3);
  Serial.println(F(", D = FREE FLOW"));
  Serial.println(F("Button: short press = next limit + reset count | hold 20 s = calibrate"));
  Serial.println(F("Remote: press = choose limit (2 clicks) | hold any 2 s = reset count (2 clicks)"));
  Serial.println(F("        hold D for 20 s = calibrate"));
  Serial.println(F(""));
}

void loop() {
  unsigned long now = millis();

  collectPulses();
  handleButton(now);
  handleRemote(now);
  checkLimit(now);
  updateValvePulses(now);
  updateLeds(now);
  report(now);
  sendEspCharacter();
}

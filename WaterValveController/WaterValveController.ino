/*
  Water Valve Controller
  ======================
  Arduino Nano + YF-G1 hall-effect flow sensor + relay-driven solenoid valve.

  - Pick a limit of 25 L, 50 L, 100 L or FREE FLOW with the push button (or the
    433 MHz remote). Three LEDs show the limit; all LEDs off = FREE FLOW.
  - When the limit is reached the valve is pulsed shut 6 times (0.5 s shut,
    0.5 s open) as a warning. Water then keeps flowing and the count starts
    again from 0 L towards the next warning.
  - Every press of the button or the remote resets the count to 0 L.
  - Hold the button for 20 s to calibrate with a 7 L bucket. The calibration is
    saved to EEPROM and survives power loss; the water count always starts at
    0 L after power-up.
  - Status (flow rate, limit, count) is printed to the Serial Monitor and sent
    as one JSON line per second on a spare pin for a future ESP8266/ESP32.

  See README.md for wiring and full instructions.
*/

#include <EEPROM.h>
#include <SoftwareSerial.h>

// ---------------------------------------------------------------------------
// Pin assignments (Arduino Nano)
// ---------------------------------------------------------------------------
const uint8_t PIN_FLOW_SENSOR = 2;   // must be D2 or D3 (external interrupt pins)
const uint8_t PIN_BUTTON      = 4;   // momentary push button to GND
const uint8_t PIN_LED_25L     = 5;
const uint8_t PIN_LED_50L     = 6;
const uint8_t PIN_LED_100L    = 7;
const uint8_t PIN_RELAY       = 8;   // relay module IN (switches the solenoid)
const uint8_t PIN_ESP_TX      = 11;  // data out to the ESP (through a 5 V -> 3.3 V divider)
const uint8_t PIN_ESP_RX      = 12;  // reserved for data back from the ESP (not used yet)
const uint8_t PIN_REMOTE[4]   = { A0, A1, A2, A3 };  // 433 MHz receiver channels A, B, C, D

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

// 433 MHz receiver outputs.
//   true  = relay-output receiver: wire each channel's COM to GND and NO to the
//           Arduino pin. The internal pull-up is used, so pressed = LOW.
//   false = logic-output receiver whose D0-D3 pins go HIGH while pressed.
const bool REMOTE_ACTIVE_LOW = true;

// Set to true if the receiver is in toggle/latching mode (its output flips on
// every press) instead of momentary mode. Every change is then one press.
const bool REMOTE_TOGGLE_MODE = false;

// What each remote button does.
enum RemoteAction : uint8_t {
  REMOTE_NONE,         // channel not wired / not used
  REMOTE_NEXT_MODE,    // exactly the same as a short press of the push button
  REMOTE_RESET_COUNT,  // reset the count to 0 L but keep the current limit
  REMOTE_SELECT_25L,
  REMOTE_SELECT_50L,
  REMOTE_SELECT_100L,
  REMOTE_SELECT_FREE
};

const RemoteAction REMOTE_ACTIONS[4] = {
  REMOTE_NEXT_MODE,    // button A
  REMOTE_RESET_COUNT,  // button B
  REMOTE_NONE,         // button C
  REMOTE_NONE          // button D
};

// ---------------------------------------------------------------------------
// Flow sensor and calibration
// ---------------------------------------------------------------------------

// YF-G1 datasheet: F (Hz) = 1 x Q (L/min)  ->  1 pulse/s per L/min = 60 pulses per litre.
const float DEFAULT_PULSES_PER_LITRE = 60.0;
const float CAL_BUCKET_LITRES        = 7.0;
const float MIN_PULSES_PER_LITRE     = 5.0;     // calibration results outside this
const float MAX_PULSES_PER_LITRE     = 1000.0;  // range are rejected as mistakes

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
const unsigned long DEBOUNCE_MS        = 50;
const unsigned long SHORT_PRESS_MAX_MS = 2000;   // presses between this and CAL_HOLD_MS do nothing
const unsigned long CAL_HOLD_MS        = 20000;  // hold the button this long to calibrate
const uint8_t       ALERT_PULSES       = 6;      // valve shut/open cycles when the limit is reached
const unsigned long ALERT_PHASE_MS     = 500;    // 0.5 s shut, then 0.5 s open
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
enum LimitMode : uint8_t { MODE_25L, MODE_50L, MODE_100L, MODE_FREE, MODE_COUNT };
const uint8_t LIMIT_LITRES[MODE_COUNT] = { 25, 50, 100, 0 };

enum SystemState : uint8_t { STATE_NORMAL, STATE_LIMIT_ALERT, STATE_CALIBRATING };

enum LedFeedback : uint8_t { FEEDBACK_NONE, FEEDBACK_CAL_OK, FEEDBACK_CAL_FAILED };

struct DebouncedInput {
  bool stable;               // debounced level (true = active/pressed)
  bool lastRaw;
  unsigned long changedAt;
};

struct CalibrationRecord {
  uint16_t magic;
  float pulsesPerLitre;
  uint16_t checksum;
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
uint32_t countPulses = 0;     // towards the limit: back to 0 at the limit and on any press
uint32_t sessionPulses = 0;   // since power-up or the last press (not reset at the limit)
uint32_t calPulses = 0;       // since calibration mode started

float flowHz = 0;
uint32_t rateRefPulses = 0;
uint32_t rateRefUs = 0;
bool rateRefValid = false;

DebouncedInput button = { false, false, 0 };
unsigned long buttonPressedAt = 0;
bool buttonHoldHandled = false;
DebouncedInput remote[4];

uint8_t alertPhase = 0;       // even = valve shut, odd = valve open
unsigned long alertPhaseStart = 0;
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
const char *limitName(LimitMode mode) {
  switch (mode) {
    case MODE_25L:  return "25L";
    case MODE_50L:  return "50L";
    case MODE_100L: return "100L";
    default:        return "FREE FLOW";
  }
}

const char *stateName() {
  switch (state) {
    case STATE_LIMIT_ALERT: return "LIMIT REACHED";
    case STATE_CALIBRATING: return "CALIBRATING";
    default:                return "NORMAL";
  }
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
void endAlert() {
  if (state == STATE_LIMIT_ALERT) state = STATE_NORMAL;
  setValveOpen(true);
}

void resetCount() {
  collectPulses();  // pulses before the reset must not appear after it
  countPulses = 0;
  sessionPulses = 0;
  endAlert();
  Serial.println(F(">> Count reset to 0 L"));
}

void selectMode(LimitMode mode) {
  limitMode = mode;
  if (REMEMBER_LIMIT) saveMode();
  Serial.print(F(">> Limit set to "));
  Serial.println(limitName(limitMode));
  resetCount();
}

void startAlert(unsigned long now) {
  state = STATE_LIMIT_ALERT;
  alertPhase = 0;
  alertPhaseStart = now;
  setValveOpen(false);
  Serial.print(F(">> Limit of "));
  Serial.print(limitName(limitMode));
  Serial.println(F(" reached - pulsing valve, count restarted at 0 L"));
}

void updateAlert(unsigned long now) {
  if (state != STATE_LIMIT_ALERT || now - alertPhaseStart < ALERT_PHASE_MS) return;
  alertPhaseStart += ALERT_PHASE_MS;
  alertPhase++;
  if (alertPhase >= ALERT_PULSES * 2) {
    endAlert();
  } else {
    setValveOpen(alertPhase % 2 == 1);
  }
}

void checkLimit(unsigned long now) {
  if (state != STATE_NORMAL || limitMode == MODE_FREE) return;
  uint32_t limitPulses = (uint32_t)(LIMIT_LITRES[limitMode] * pulsesPerLitre + 0.5);
  if (countPulses >= limitPulses) {
    countPulses -= limitPulses;  // keep any overshoot so repeated limits stay accurate
    startAlert(now);
  }
}

void startCalibration(unsigned long now) {
  collectPulses();  // pulses before calibration starts are not part of the bucket
  endAlert();
  state = STATE_CALIBRATING;
  calPulses = 0;
  calStartedAt = now;
  Serial.println(F(""));
  Serial.println(F(">> CALIBRATION MODE"));
  Serial.print(F("   Fill a "));
  Serial.print(CAL_BUCKET_LITRES, 1);
  Serial.println(F(" L bucket, turn the water off, then press the button."));
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

// Short press of the push button (or a remote button set to REMOTE_NEXT_MODE).
void onShortPress(unsigned long now) {
  if (state == STATE_CALIBRATING) {
    finishCalibration(now);
  } else {
    selectMode((LimitMode)((limitMode + 1) % MODE_COUNT));
  }
}

void onRemoteAction(RemoteAction action, unsigned long now) {
  if (action == REMOTE_NEXT_MODE) {
    onShortPress(now);
    return;
  }
  if (state == STATE_CALIBRATING) return;  // only the push button action ends calibration

  switch (action) {
    case REMOTE_RESET_COUNT:  resetCount(); break;
    case REMOTE_SELECT_25L:   selectMode(MODE_25L); break;
    case REMOTE_SELECT_50L:   selectMode(MODE_50L); break;
    case REMOTE_SELECT_100L:  selectMode(MODE_100L); break;
    case REMOTE_SELECT_FREE:  selectMode(MODE_FREE); break;
    default: break;
  }
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

// Returns true when the debounced level changes.
bool debounce(DebouncedInput &input, bool raw, unsigned long now) {
  if (raw != input.lastRaw) {
    input.lastRaw = raw;
    input.changedAt = now;
  }
  if (raw != input.stable && now - input.changedAt >= DEBOUNCE_MS) {
    input.stable = raw;
    return true;
  }
  return false;
}

bool readRemote(uint8_t channel) {
  return (digitalRead(PIN_REMOTE[channel]) == LOW) == REMOTE_ACTIVE_LOW;
}

void handleButton(unsigned long now) {
  bool pressed = digitalRead(PIN_BUTTON) == LOW;

  if (debounce(button, pressed, now)) {
    if (button.stable) {
      buttonPressedAt = now;
      buttonHoldHandled = false;
    } else if (!buttonHoldHandled && now - buttonPressedAt <= SHORT_PRESS_MAX_MS) {
      onShortPress(now);
    }
  }

  if (button.stable && !buttonHoldHandled && now - buttonPressedAt >= CAL_HOLD_MS) {
    buttonHoldHandled = true;  // releasing after the hold does nothing
    if (state != STATE_CALIBRATING) startCalibration(now);
  }
}

void handleRemote(unsigned long now) {
  for (uint8_t i = 0; i < 4; i++) {
    if (REMOTE_ACTIONS[i] == REMOTE_NONE) continue;
    if (debounce(remote[i], readRemote(i), now) && (remote[i].stable || REMOTE_TOGGLE_MODE)) {
      onRemoteAction(REMOTE_ACTIONS[i], now);
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
void updateLeds(unsigned long now) {
  bool led25 = false, led50 = false, led100 = false;

  if (ledFeedback != FEEDBACK_NONE && now - ledFeedbackStart >= FEEDBACK_MS) {
    ledFeedback = FEEDBACK_NONE;
  }

  if (ledFeedback == FEEDBACK_CAL_OK) {
    led25 = led50 = led100 = true;                                   // solid = saved
  } else if (ledFeedback == FEEDBACK_CAL_FAILED) {
    led25 = led50 = led100 = ((now - ledFeedbackStart) / 100) % 2 == 0;  // fast flash = rejected
  } else if (state == STATE_CALIBRATING) {
    led25 = led50 = led100 = ((now - calStartedAt) / CAL_FLASH_MS) % 2 == 0;
  } else {
    // The selected LED blinks in time with the valve while the limit alert runs.
    bool on = state != STATE_LIMIT_ALERT || valveOpen;
    led25  = on && limitMode == MODE_25L;
    led50  = on && limitMode == MODE_50L;
    led100 = on && limitMode == MODE_100L;
  }

  digitalWrite(PIN_LED_25L, led25 ? HIGH : LOW);
  digitalWrite(PIN_LED_50L, led50 ? HIGH : LOW);
  digitalWrite(PIN_LED_100L, led100 ? HIGH : LOW);
}

// Human-readable line for the Serial Monitor.
void reportSerial() {
  Serial.print(F("Flow: "));
  Serial.print(flowLitresPerMinute(), 2);
  Serial.print(F(" L/min | Limit: "));
  Serial.print(limitName(limitMode));
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
//  "valve":"OPEN","state":"NORMAL","ppl":60.00,"calibrated":false}
void reportEsp() {
  espSerial.print(F("{\"flow_lpm\":"));
  espSerial.print(flowLitresPerMinute(), 2);
  espSerial.print(F(",\"limit\":\""));
  espSerial.print(limitName(limitMode));
  espSerial.print(F("\",\"limit_l\":"));
  espSerial.print(LIMIT_LITRES[limitMode]);
  espSerial.print(F(",\"count_l\":"));
  espSerial.print(pulsesToLitres(countPulses), 2);
  espSerial.print(F(",\"session_l\":"));
  espSerial.print(pulsesToLitres(sessionPulses), 2);
  espSerial.print(F(",\"valve\":\""));
  espSerial.print(valveOpen ? F("OPEN") : F("SHUT"));
  espSerial.print(F("\",\"state\":\""));
  espSerial.print(stateName());
  espSerial.print(F("\",\"ppl\":"));
  espSerial.print(pulsesPerLitre, 2);
  espSerial.print(F(",\"calibrated\":"));
  espSerial.print(isCalibrated ? F("true") : F("false"));
  espSerial.println(F("}"));
}

void report(unsigned long now) {
  if (now - lastReportAt < REPORT_INTERVAL_MS) return;
  lastReportAt = now;
  updateFlowRate();
  reportSerial();
  reportEsp();
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
  pinMode(PIN_LED_25L, OUTPUT);
  pinMode(PIN_LED_50L, OUTPUT);
  pinMode(PIN_LED_100L, OUTPUT);
  for (uint8_t i = 0; i < 4; i++) {
    if (REMOTE_ACTIONS[i] == REMOTE_NONE) continue;
    pinMode(PIN_REMOTE[i], REMOTE_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  }

  Serial.begin(SERIAL_BAUD);
  espSerial.begin(ESP_BAUD);

  loadCalibration();
  loadMode();

  // LED self-test so a wiring fault is obvious at power-up.
  const uint8_t leds[3] = { PIN_LED_25L, PIN_LED_50L, PIN_LED_100L };
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(leds[i], HIGH);
    delay(200);
    digitalWrite(leds[i], LOW);
  }

  // Start the remote inputs at their current level so a latched receiver
  // output does not count as a press at power-up.
  unsigned long now = millis();
  for (uint8_t i = 0; i < 4; i++) {
    bool level = REMOTE_ACTIONS[i] != REMOTE_NONE && readRemote(i);
    remote[i] = { level, level, now };
  }

  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_SENSOR), onFlowPulse, FALLING);

  Serial.println(F(""));
  Serial.println(F("=== Water Valve Controller ==="));
  Serial.print(F("Calibration: "));
  Serial.print(pulsesPerLitre, 2);
  Serial.println(isCalibrated ? F(" pulses/L (saved)") : F(" pulses/L (datasheet default)"));
  Serial.print(F("Limit: "));
  Serial.println(limitName(limitMode));
  Serial.println(F("Short press: next limit + reset count | Hold 20 s: calibrate"));
  Serial.println(F(""));
}

void loop() {
  unsigned long now = millis();

  collectPulses();
  handleButton(now);
  handleRemote(now);
  checkLimit(now);
  updateAlert(now);
  updateLeds(now);
  report(now);
}

/*
  Water Valve Controller
  ======================
  Arduino Nano + YF-G1 hall-effect flow sensor + MOSFET-switched 12 V solenoid valve.

  - Pick one of three limits (25 L, 50 L, 100 L by default, see LIMIT VOLUMES
    below) or FREE FLOW with the push button (each press steps to the next
    limit) or the 433 MHz remote (button A = limit 1, B = limit 2, C = limit 3,
    D = FREE FLOW; the valve clicks twice to confirm). Three LEDs show the
    limit; all LEDs off = FREE FLOW.
  - When the limit is reached the valve is pulsed shut 4 times (0.5 s shut,
    0.5 s open) as a warning. Water then keeps flowing and the count starts
    again from 0 L towards the next warning once the pulses have finished.
    (The settings page can make the valve stay shut until the count is reset.)
  - A press of the push button resets the count to 0 L. On the remote, hold any
    button for 2 s to reset the count; the valve clicks twice to confirm.
  - Hold the push button, or remote button D (FREE FLOW), for 20 s to calibrate
    with a 7 L bucket. The calibration is saved to EEPROM and survives power
    loss; the water count always starts at 0 L after power-up.
  - Status (flow rate, limit, count) is printed to the Serial Monitor and sent
    on D11 to the ESP32-C3 "Aqua Tracka" web dashboard, which can send
    commands back on D12: choose the limit, reset the count, calibrate, and
    change the settings below (saved in EEPROM).

  See README.md for wiring and full instructions.
*/

#include <EEPROM.h>
#include <SoftwareSerial.h>
#include <stddef.h>
#include <stdlib.h>

// ===========================================================================
// LIMIT VOLUMES - change these numbers to set the three limits, in litres.
//   Limit 1: LED on D5, remote button A
//   Limit 2: LED on D6, remote button B
//   Limit 3: LED on D7, remote button C
//   FREE FLOW (all LEDs off): remote button D
// These, and the options marked "web setting" below, are the defaults: the
// Aqua Tracka web page can change them, and its "Reset to defaults" button
// brings these values back.
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
const uint8_t PIN_VALVE       = 8;   // valve driver: the PCB's MOSFET switch (or a relay module's IN)
const uint8_t PIN_ESP_TX      = 11;  // data out to the ESP (through a 5 V -> 3.3 V divider)
const uint8_t PIN_ESP_RX      = 12;  // commands from the ESP (PCB connector J4 pin 4)
// Receiver outputs for remote buttons A, B, C, D. On the RX480R_4CH V4 that was
// tested, button A drives D3 (wired to A3) and button D drives D0 (A0). If a
// button picks the wrong limit, change the order here.
const uint8_t PIN_REMOTE[4]   = { A3, A2, A1, A0 };

// ---------------------------------------------------------------------------
// Hardware options - change these to suit your parts (all web settings)
// ---------------------------------------------------------------------------

// Solenoid valve type.
//   false = normally OPEN valve (the one this controller is built for): water flows
//           with the valve unpowered, so D8 powers it only to stop the water.
//   true  = normally CLOSED valve: it must be powered to let water through, so it
//           is powered while water flows.
const bool VALVE_NORMALLY_CLOSED = false;

// How D8 switches the valve on.
//   false = the controller PCB's MOSFET driver: D8 HIGH powers the valve. Also right for
//           relay modules that switch ON when IN is HIGH.
//   true  = a relay module that switches ON when IN is pulled LOW (most cheap ones,
//           as used in the hand-wired version).
const bool VALVE_DRIVE_ACTIVE_LOW = false;

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
// When false, the count is kept and only a 2 s hold resets it. (Web setting.)
const bool REMOTE_SELECT_RESETS_COUNT = false;

// What happens once the limit's warning pulses have finished. (Web setting.)
//   false = water keeps flowing and the count starts again from 0 L
//   true  = the valve stays shut until the count is reset (button, remote or web page)
const bool STAY_SHUT_AFTER_LIMIT = false;

// ---------------------------------------------------------------------------
// Flow sensor and calibration
// ---------------------------------------------------------------------------

// YF-G1 spec sheet: F (Hz) = 1.08 x Q (L/min), "about 64.8 P/L"
//   -> 1.08 pulses/s per L/min x 60 s = 64.8 pulses per litre (+/- 3%).
const float DEFAULT_PULSES_PER_LITRE = 64.8;
const float CAL_BUCKET_LITRES        = 7.0;     // web setting
const float MIN_PULSES_PER_LITRE     = 5.0;     // calibration results outside this
const float MAX_PULSES_PER_LITRE     = 1000.0;  // range are rejected as mistakes

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
const unsigned long DEBOUNCE_MS          = 50;
const unsigned long REMOTE_PRESS_MS      = 20;     // remote output ON this long = pressed (catches 0.1 s pulses)
const unsigned long REMOTE_RELEASE_MS    = 150;    // OFF this long = released (rides out brief RF drop-outs)
const unsigned long SHORT_PRESS_MAX_MS   = 2000;   // push button presses between this and CAL_HOLD_MS do nothing
const unsigned long REMOTE_RESET_HOLD_MS = 2000;   // hold any remote button this long to reset the count (web setting)
const unsigned long CAL_HOLD_MS          = 20000;  // hold the push button / remote button D this long to calibrate (web setting)
const uint8_t       ALERT_PULSES         = 4;      // valve shut/open cycles when the limit is reached (web setting)
const unsigned long ALERT_PHASE_MS       = 500;    // 0.5 s shut, then 0.5 s open (web setting)
const uint8_t       CONFIRM_CLICKS       = 2;      // valve shut/open cycles to confirm a remote limit choice or reset (web setting)
const unsigned long CONFIRM_CLICK_MS     = 250;    // 0.25 s shut, then 0.25 s open (web setting)
const unsigned long CAL_FLASH_MS       = 500;    // LED flash rate in calibration mode
const unsigned long HOLD_FLASH_MS      = 1000;   // LED flash rate while the valve is held shut at the limit
const unsigned long FEEDBACK_MS        = 2000;   // LED pattern after a calibration attempt
const unsigned long REPORT_INTERVAL_MS = 1000;   // serial / ESP status rate
const unsigned long CONFIG_INTERVAL_MS = 10000;  // the settings are sent to the ESP this often
const unsigned long ESP_LINE_GAP_MS    = 150;    // quiet time after each line, when the ESP may send a command
const unsigned long FLOW_TIMEOUT_MS    = 3000;   // no pulses for this long = 0 L/min
const unsigned long PULSE_GLITCH_US    = 2000;   // pulses closer than this are noise (> 500 Hz)

const long SERIAL_BAUD = 115200;
const long ESP_BAUD    = 9600;

// Remember the selected limit after a power cut (the count is always reset). (Web setting.)
const bool REMEMBER_LIMIT = true;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
enum LimitMode : uint8_t { MODE_LIMIT_1, MODE_LIMIT_2, MODE_LIMIT_3, MODE_FREE, MODE_COUNT };

// Limit chosen by remote buttons A-D. The FREE FLOW button is also the only
// remote button that can start and finish calibration.
const LimitMode REMOTE_MODES[4] = { MODE_LIMIT_1, MODE_LIMIT_2, MODE_LIMIT_3, MODE_FREE };

// The numbers are sent to the ESP, so new states go at the end.
enum SystemState : uint8_t { STATE_NORMAL, STATE_LIMIT_ALERT, STATE_CONFIRM_CLICKS, STATE_CALIBRATING, STATE_LIMIT_HOLD };

enum LedFeedback : uint8_t { FEEDBACK_NONE, FEEDBACK_CAL_OK, FEEDBACK_CAL_FAILED };

// Events reported to the ESP for its log (code, extra value, source).
enum EventCode : uint8_t {
  EV_BOOT = 1, EV_LIMIT, EV_RESET, EV_MODE, EV_CAL_START, EV_CAL_SAVED, EV_CAL_REJECTED,
  EV_CAL_CANCELLED, EV_SETTINGS, EV_DEFAULTS, EV_VALVE_TEST, EV_HOLD, EV_PPL_SET
};
enum EventSource : uint8_t { SRC_BUTTON, SRC_REMOTE, SRC_WEB, SRC_AUTO };

// Command results, sent back to the ESP with the command's number.
enum CommandResult : uint8_t { CMD_REJECTED, CMD_DONE, CMD_BUSY, CMD_UNKNOWN };

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

// Everything the web page can change, saved in EEPROM.
struct Settings {
  uint16_t magic;
  uint16_t limitLitres[3];
  uint8_t  alertPulses;
  uint16_t alertPhaseMs;
  uint8_t  stayShutAfterLimit;
  uint8_t  confirmClicks;
  uint16_t confirmClickMs;
  uint8_t  remoteSelectResets;
  uint8_t  rememberLimit;
  uint16_t remoteResetHoldMs;
  uint8_t  calHoldSeconds;
  uint16_t bucketDecilitres;
  uint8_t  valveNormallyClosed;
  uint8_t  valveDriveActiveLow;
  uint8_t  remoteActiveLow;
  uint16_t checksum;
};

// The settings' short names on the ESP link, and their allowed ranges.
struct SettingInfo {
  char key[3];
  uint8_t offset;
  uint8_t size;
  uint16_t minValue;
  uint16_t maxValue;
};

const SettingInfo SETTING_INFO[] PROGMEM = {
  { "l1", offsetof(Settings, limitLitres[0]),      2, 1,   9999 },
  { "l2", offsetof(Settings, limitLitres[1]),      2, 1,   9999 },
  { "l3", offsetof(Settings, limitLitres[2]),      2, 1,   9999 },
  { "ap", offsetof(Settings, alertPulses),         1, 0,   20 },
  { "am", offsetof(Settings, alertPhaseMs),        2, 100, 5000 },
  { "ah", offsetof(Settings, stayShutAfterLimit),  1, 0,   1 },
  { "cc", offsetof(Settings, confirmClicks),       1, 0,   10 },
  { "cm", offsetof(Settings, confirmClickMs),      2, 50,  2000 },
  { "rs", offsetof(Settings, remoteSelectResets),  1, 0,   1 },
  { "rl", offsetof(Settings, rememberLimit),       1, 0,   1 },
  { "rh", offsetof(Settings, remoteResetHoldMs),   2, 500, 10000 },
  { "ch", offsetof(Settings, calHoldSeconds),      1, 5,   120 },
  { "bk", offsetof(Settings, bucketDecilitres),    2, 5,   1000 },
  { "vn", offsetof(Settings, valveNormallyClosed), 1, 0,   1 },
  { "va", offsetof(Settings, valveDriveActiveLow), 1, 0,   1 },
  { "ra", offsetof(Settings, remoteActiveLow),     1, 0,   1 },
};
const uint8_t SETTING_COUNT = sizeof(SETTING_INFO) / sizeof(SETTING_INFO[0]);

// The ESP lines are built here, then sent one character per loop. Sending a
// line in one go at 9600 baud would stall the sketch for about 0.2 s, long
// enough to miss a short remote press.
char espLine[240];
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

const int      EEPROM_CAL_ADDR      = 0;
const int      EEPROM_MODE_ADDR     = 16;  // mode byte followed by its inverse
const int      EEPROM_SETTINGS_ADDR = 32;
const uint16_t EEPROM_MAGIC         = 0xA57C;
const uint16_t SETTINGS_MAGIC       = 0x5E71;
const uint8_t  FIRMWARE_VERSION     = 2;   // sent to the ESP; version 1 had no command link

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
SoftwareSerial espSerial(PIN_ESP_RX, PIN_ESP_TX);

volatile uint32_t isrPulseCount  = 0;
volatile uint32_t isrLastPulseUs = 0;
volatile uint16_t isrGlitches    = 0;

Settings settings;
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
unsigned long holdStartedAt = 0;
LedFeedback ledFeedback = FEEDBACK_NONE;
unsigned long ledFeedbackStart = 0;
unsigned long lastReportAt = 0;

// ESP link
char cmdLine[100];            // command being received from the ESP
uint8_t cmdLength = 0;
bool cmdStarted = false;
unsigned long cmdCharAt = 0;
uint16_t lastCommandSeq = 0;  // a repeated number is the ESP retrying: answered, not run again
uint8_t lastCommandResult = CMD_DONE;
uint16_t badCommands = 0;
bool statusDue = false;
bool configDue = true;
unsigned long lastConfigAt = 0;
unsigned long espLineEndAt = 0;
bool lastLineWasStatus = false;

struct Event {
  uint16_t number;
  uint8_t code;
  uint8_t source;
  int32_t extra;
};
Event events[6];              // waiting to be sent, oldest first
uint8_t eventCount = 0;
Event lastEvent = { 0, 0, 0, 0 };
uint16_t eventNumber = 0;

// ---------------------------------------------------------------------------
// Flow sensor interrupt
// ---------------------------------------------------------------------------
void onFlowPulse() {
  uint32_t nowUs = micros();
  if (nowUs - isrLastPulseUs < PULSE_GLITCH_US) {
    isrGlitches++;
    return;
  }
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

uint16_t limitLitres(LimitMode mode) {
  return mode == MODE_FREE ? 0 : settings.limitLitres[mode];
}

float bucketLitres() {
  return settings.bucketDecilitres / 10.0;
}

// ---------------------------------------------------------------------------
// Events for the ESP's log
// ---------------------------------------------------------------------------
void logEvent(EventCode code, EventSource source, int32_t extra) {
  Event e = { ++eventNumber, code, source, extra };
  if (eventNumber == 0) e.number = eventNumber = 1;
  if (eventCount == sizeof(events) / sizeof(events[0])) {
    memmove(events, events + 1, sizeof(events) - sizeof(events[0]));  // drop the oldest
    eventCount--;
  }
  events[eventCount++] = e;
  statusDue = true;
}

// ---------------------------------------------------------------------------
// Valve
// ---------------------------------------------------------------------------
void setValveOpen(bool open) {
  valveOpen = open;
  bool powered = settings.valveNormallyClosed ? open : !open;
  digitalWrite(PIN_VALVE, (powered != (bool)settings.valveDriveActiveLow) ? HIGH : LOW);
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

// Back to the spec sheet value: the saved record is made invalid.
void clearCalibration() {
  EEPROM.put(EEPROM_CAL_ADDR, (uint16_t)0xFFFF);
  pulsesPerLitre = DEFAULT_PULSES_PER_LITRE;
  isCalibrated = false;
}

void loadMode() {
  uint8_t mode = EEPROM.read(EEPROM_MODE_ADDR);
  uint8_t inverse = EEPROM.read(EEPROM_MODE_ADDR + 1);
  if (settings.rememberLimit && mode < MODE_COUNT && (uint8_t)~mode == inverse) {
    limitMode = (LimitMode)mode;
  } else {
    limitMode = MODE_FREE;
  }
}

void saveMode() {
  EEPROM.update(EEPROM_MODE_ADDR, limitMode);
  EEPROM.update(EEPROM_MODE_ADDR + 1, (uint8_t)~limitMode);
}

void defaultSettings(Settings &s) {
  s.magic = SETTINGS_MAGIC;
  s.limitLitres[0] = LIMIT_1_LITRES;
  s.limitLitres[1] = LIMIT_2_LITRES;
  s.limitLitres[2] = LIMIT_3_LITRES;
  s.alertPulses = ALERT_PULSES;
  s.alertPhaseMs = ALERT_PHASE_MS;
  s.stayShutAfterLimit = STAY_SHUT_AFTER_LIMIT;
  s.confirmClicks = CONFIRM_CLICKS;
  s.confirmClickMs = CONFIRM_CLICK_MS;
  s.remoteSelectResets = REMOTE_SELECT_RESETS_COUNT;
  s.rememberLimit = REMEMBER_LIMIT;
  s.remoteResetHoldMs = REMOTE_RESET_HOLD_MS;
  s.calHoldSeconds = CAL_HOLD_MS / 1000;
  s.bucketDecilitres = (uint16_t)(CAL_BUCKET_LITRES * 10 + 0.5);
  s.valveNormallyClosed = VALVE_NORMALLY_CLOSED;
  s.valveDriveActiveLow = VALVE_DRIVE_ACTIVE_LOW;
  s.remoteActiveLow = REMOTE_ACTIVE_LOW;
}

uint16_t settingsChecksum(const Settings &s) {
  const uint8_t *bytes = (const uint8_t *)&s;
  uint16_t sum = 0;
  for (uint8_t i = 0; i < offsetof(Settings, checksum); i++) {
    sum = sum * 31 + bytes[i];
  }
  return sum;
}

SettingInfo settingInfo(uint8_t i) {
  SettingInfo info;
  memcpy_P(&info, &SETTING_INFO[i], sizeof(info));
  return info;
}

uint16_t getSetting(const Settings &s, const SettingInfo &info) {
  const uint8_t *p = (const uint8_t *)&s + info.offset;
  uint16_t value = p[0];
  if (info.size == 2) memcpy(&value, p, 2);
  return value;
}

void setSetting(Settings &s, const SettingInfo &info, uint16_t value) {
  uint8_t *p = (uint8_t *)&s + info.offset;
  if (info.size == 2) {
    memcpy(p, &value, 2);
  } else {
    *p = (uint8_t)value;
  }
}

bool settingsInRange(const Settings &s) {
  for (uint8_t i = 0; i < SETTING_COUNT; i++) {
    SettingInfo info = settingInfo(i);
    uint16_t value = getSetting(s, info);
    if (value < info.minValue || value > info.maxValue) return false;
  }
  return true;
}

// The defaults at the top of the sketch are used until the web page saves
// settings; after that the saved ones are used.
void loadSettings() {
  Settings saved;
  EEPROM.get(EEPROM_SETTINGS_ADDR, saved);
  if (saved.magic == SETTINGS_MAGIC && saved.checksum == settingsChecksum(saved) && settingsInRange(saved)) {
    settings = saved;
  } else {
    defaultSettings(settings);
  }
}

void saveSettings() {
  settings.magic = SETTINGS_MAGIC;
  settings.checksum = settingsChecksum(settings);
  EEPROM.put(EEPROM_SETTINGS_ADDR, settings);
}

// ---------------------------------------------------------------------------
// Text helpers
// ---------------------------------------------------------------------------
// Prints a limit as "25L" (using the current settings) or "FREE FLOW".
void printLimit(Print &out, LimitMode mode) {
  if (mode == MODE_FREE) {
    out.print(F("FREE FLOW"));
  } else {
    out.print(limitLitres(mode));
    out.print('L');
  }
}

const __FlashStringHelper *stateName() {
  switch (state) {
    case STATE_LIMIT_ALERT:    return F("LIMIT REACHED");
    case STATE_CONFIRM_CLICKS: return F("CONFIRM CLICKS");
    case STATE_CALIBRATING:    return F("CALIBRATING");
    case STATE_LIMIT_HOLD:     return F("LIMIT - VALVE HELD SHUT");
    default:                   return F("NORMAL");
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
  if (pulses == 0) return;
  state = pulseState;
  pulsePhase = 0;
  pulsePhases = pulses * 2;
  pulsePhaseMs = phaseMs;
  pulsePhaseStart = now;
  setValveOpen(false);
}

// Ends the valve pulses, or the hold after a limit, and opens the valve.
void endValvePulses() {
  if (valvePulsing() || state == STATE_LIMIT_HOLD) state = STATE_NORMAL;
  setValveOpen(true);
}

// "Stay shut after the limit": the valve stays shut until the count is reset.
void holdValveShut(unsigned long now) {
  state = STATE_LIMIT_HOLD;
  holdStartedAt = now;
  setValveOpen(false);
  logEvent(EV_HOLD, SRC_AUTO, limitLitres(limitMode));
  Serial.println(F(">> Valve held shut: reset the count to let water through"));
}

void updateValvePulses(unsigned long now) {
  if (!valvePulsing() || now - pulsePhaseStart < pulsePhaseMs) return;
  pulsePhaseStart += pulsePhaseMs;
  pulsePhase++;
  // With "stay shut after the limit" the last open phase is skipped.
  bool holdNext = state == STATE_LIMIT_ALERT && settings.stayShutAfterLimit && pulsePhase == pulsePhases - 1;
  if (pulsePhase >= pulsePhases || holdNext) {
    if (state == STATE_LIMIT_ALERT) {
      // Water that ran during the warning doesn't count towards the next limit,
      // otherwise a small limit can be used up before the warning even ends.
      collectPulses();
      countPulses = 0;
      if (settings.stayShutAfterLimit) {
        holdValveShut(now);
        return;
      }
    }
    endValvePulses();
  } else {
    setValveOpen(pulsePhase % 2 == 1);
  }
}

void resetCount(EventSource source) {
  collectPulses();  // pulses before the reset must not appear after it
  countPulses = 0;
  sessionPulses = 0;
  endValvePulses();
  if (source != SRC_AUTO) logEvent(EV_RESET, source, 0);
  Serial.println(F(">> Count reset to 0 L"));
}

// Quick valve clicks, so a remote press can be heard from a distance.
void confirmWithClicks(unsigned long now) {
  startValvePulses(STATE_CONFIRM_CLICKS, settings.confirmClicks, settings.confirmClickMs, now);
}

// Remote 2 s hold: reset, then click the valve to confirm.
void resetCountWithClicks(unsigned long now) {
  resetCount(SRC_REMOTE);
  confirmWithClicks(now);
}

void selectMode(LimitMode mode, bool resetCounter, EventSource source) {
  limitMode = mode;
  if (settings.rememberLimit) saveMode();
  logEvent(EV_MODE, source, mode);
  Serial.print(F(">> Limit set to "));
  printLimit(Serial, limitMode);
  Serial.println();
  if (resetCounter) resetCount(source);
}

void checkLimit(unsigned long now) {
  if (state != STATE_NORMAL || limitMode == MODE_FREE) return;
  uint32_t limitPulses = (uint32_t)(limitLitres(limitMode) * pulsesPerLitre + 0.5);
  if (countPulses >= limitPulses) {
    countPulses = 0;
    logEvent(EV_LIMIT, SRC_AUTO, limitLitres(limitMode));
    Serial.print(F(">> Limit of "));
    printLimit(Serial, limitMode);
    Serial.println(F(" reached - pulsing valve, count restarted at 0 L"));
    if (settings.alertPulses > 0) {
      startValvePulses(STATE_LIMIT_ALERT, settings.alertPulses, settings.alertPhaseMs, now);
    } else if (settings.stayShutAfterLimit) {
      holdValveShut(now);
    }
  }
}

void startCalibration(unsigned long now, EventSource source) {
  collectPulses();  // pulses before calibration starts are not part of the bucket
  endValvePulses();
  state = STATE_CALIBRATING;
  calPulses = 0;
  calStartedAt = now;
  logEvent(EV_CAL_START, source, 0);
  Serial.println(F(""));
  Serial.println(F(">> CALIBRATION MODE"));
  Serial.print(F("   Fill a "));
  Serial.print(bucketLitres(), 1);
  Serial.println(F(" L bucket, turn the water off, then press the button (or remote button D)."));
  Serial.println(F("   (Pressing without running any water cancels calibration.)"));
}

// Calibration result: the pulses counted for this many litres.
void finishCalibration(unsigned long now, float litres, EventSource source) {
  collectPulses();
  float measured = calPulses / litres;

  Serial.print(F(">> Calibration: "));
  Serial.print(calPulses);
  Serial.print(F(" pulses for "));
  Serial.print(litres, 2);
  Serial.print(F(" L = "));
  Serial.print(measured, 2);
  Serial.println(F(" pulses/L"));

  if (isValidPulsesPerLitre(measured)) {
    pulsesPerLitre = measured;
    isCalibrated = true;
    saveCalibration();
    ledFeedback = FEEDBACK_CAL_OK;
    logEvent(EV_CAL_SAVED, source, (int32_t)(measured * 100 + 0.5));
    Serial.println(F(">> Calibration saved"));
  } else {
    ledFeedback = FEEDBACK_CAL_FAILED;
    logEvent(EV_CAL_REJECTED, source, calPulses);
    Serial.print(F(">> Calibration rejected, keeping "));
    Serial.print(pulsesPerLitre, 2);
    Serial.println(F(" pulses/L"));
  }
  ledFeedbackStart = now;
  state = STATE_NORMAL;
  resetCount(SRC_AUTO);
}

void cancelCalibration(EventSource source) {
  state = STATE_NORMAL;
  logEvent(EV_CAL_CANCELLED, source, calPulses);
  Serial.println(F(">> Calibration cancelled"));
  resetCount(SRC_AUTO);
}

// Short press of the push button: next limit and reset the count.
void onButtonShortPress(unsigned long now) {
  if (state == STATE_CALIBRATING) {
    finishCalibration(now, bucketLitres(), SRC_BUTTON);
  } else {
    selectMode((LimitMode)((limitMode + 1) % MODE_COUNT), true, SRC_BUTTON);
  }
}

// Remote button released within 2 s: choose that button's limit, then click
// the valve twice to confirm.
void onRemoteShortPress(uint8_t channel, unsigned long now) {
  LimitMode mode = REMOTE_MODES[channel];
  if (state == STATE_CALIBRATING) {
    if (mode == MODE_FREE) finishCalibration(now, bucketLitres(), SRC_REMOTE);  // other remote buttons are ignored
  } else {
    selectMode(mode, settings.remoteSelectResets, SRC_REMOTE);
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
  if (settings.remoteActiveLow) return digitalRead(PIN_REMOTE[channel]) == LOW;
  return analogRead(PIN_REMOTE[channel]) > REMOTE_HIGH_THRESHOLD;
}

// A remote output that is already on (stuck, latched or wrongly configured) is
// ignored until it has been released.
void setupRemote(unsigned long now) {
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(PIN_REMOTE[i], settings.remoteActiveLow ? INPUT_PULLUP : INPUT);
  }
  for (uint8_t i = 0; i < 4; i++) {
    bool level = readRemote(i);
    remote[i] = { { level, level, now }, now, level, level };
  }
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

  if (button.stable && !buttonHoldHandled && now - buttonPressedAt >= settings.calHoldSeconds * 1000UL) {
    buttonHoldHandled = true;  // releasing after the hold does nothing
    if (state != STATE_CALIBRATING) startCalibration(now, SRC_BUTTON);
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
    if (!b.holdHandled && heldMs >= settings.remoteResetHoldMs) {
      b.holdHandled = true;
      if (state != STATE_CALIBRATING) resetCountWithClicks(now);
    }
    if (REMOTE_MODES[i] == MODE_FREE && !b.calHoldHandled && heldMs >= settings.calHoldSeconds * 1000UL) {
      b.calHoldHandled = true;
      if (state != STATE_CALIBRATING) startCalibration(now, SRC_REMOTE);
    }
  }
}

// ---------------------------------------------------------------------------
// Commands from the ESP (D12)
// ---------------------------------------------------------------------------
// Each command is one line:  $<number>,<command>[,<arguments>]*<checksum>
// The checksum is the XOR of the characters between '$' and '*', as two hex
// digits. The ESP only sends straight after a line from the Nano has ended, so
// the two never talk at once (SoftwareSerial can't send and receive together).
//
//   M,<0-3>          choose limit 1-3 or FREE FLOW (the count is kept)
//   R                reset the count (and end a "stay shut" hold)
//   CS / CX          start / cancel calibration
//   CF,<litres*100>  finish calibration: this much water ran
//   P,<ppl*100>      set the pulses per litre by hand
//   S,<key>=<value>,...   change settings (keys in SETTING_INFO), all or none
//   D,<0|1>          settings back to the defaults; 1 also clears the
//                    calibration and the saved limit
//   T                test the valve (two clicks)
//   Q                send the settings now

bool parseNumber(const char *text, long &value) {
  if (text == NULL || *text == '\0') return false;
  char *end;
  value = strtol(text, &end, 10);
  return *end == '\0';
}

uint8_t applySettings(char *args) {
  Settings changed = settings;
  for (char *item = strtok(args, ","); item != NULL; item = strtok(NULL, ",")) {
    char *equals = strchr(item, '=');
    if (equals == NULL) return CMD_REJECTED;
    *equals = '\0';
    long value;
    if (!parseNumber(equals + 1, value)) return CMD_REJECTED;
    uint8_t i = 0;
    SettingInfo info;
    for (; i < SETTING_COUNT; i++) {
      info = settingInfo(i);
      if (strcmp(item, info.key) == 0) break;
    }
    if (i == SETTING_COUNT || value < info.minValue || value > info.maxValue) return CMD_REJECTED;
    setSetting(changed, info, (uint16_t)value);
  }
  bool remoteChanged = changed.remoteActiveLow != settings.remoteActiveLow;
  settings = changed;
  saveSettings();
  setValveOpen(valveOpen);                // the valve options may have changed
  if (remoteChanged) setupRemote(millis());
  if (settings.rememberLimit) saveMode();
  logEvent(EV_SETTINGS, SRC_WEB, 0);
  configDue = true;
  Serial.println(F(">> Settings changed from the web page"));
  return CMD_DONE;
}

uint8_t runCommand(char *command, char *args, unsigned long now) {
  long value = 0;
  bool calibrating = state == STATE_CALIBRATING;
  if (strcmp(command, "M") == 0) {
    if (!parseNumber(args, value) || value < 0 || value >= MODE_COUNT) return CMD_REJECTED;
    if (calibrating) return CMD_BUSY;
    selectMode((LimitMode)value, false, SRC_WEB);
  } else if (strcmp(command, "R") == 0) {
    if (calibrating) return CMD_BUSY;
    resetCount(SRC_WEB);
  } else if (strcmp(command, "CS") == 0) {
    if (!calibrating) startCalibration(now, SRC_WEB);
  } else if (strcmp(command, "CX") == 0) {
    if (!calibrating) return CMD_BUSY;
    cancelCalibration(SRC_WEB);
  } else if (strcmp(command, "CF") == 0) {
    if (!parseNumber(args, value) || value < 10 || value > 100000) return CMD_REJECTED;
    if (!calibrating) return CMD_BUSY;
    finishCalibration(now, value / 100.0, SRC_WEB);
    if (ledFeedback != FEEDBACK_CAL_OK) return CMD_REJECTED;
  } else if (strcmp(command, "P") == 0) {
    if (!parseNumber(args, value) || !isValidPulsesPerLitre(value / 100.0)) return CMD_REJECTED;
    pulsesPerLitre = value / 100.0;
    isCalibrated = true;
    saveCalibration();
    logEvent(EV_PPL_SET, SRC_WEB, value);
    configDue = true;
  } else if (strcmp(command, "S") == 0) {
    if (args == NULL) return CMD_REJECTED;
    return applySettings(args);
  } else if (strcmp(command, "D") == 0) {
    if (!parseNumber(args, value) || value < 0 || value > 1) return CMD_REJECTED;
    if (calibrating) return CMD_BUSY;
    bool remoteWasActiveLow = settings.remoteActiveLow;
    defaultSettings(settings);
    saveSettings();
    if (value == 1) {
      clearCalibration();
      limitMode = MODE_FREE;
    }
    saveMode();
    resetCount(SRC_AUTO);              // also opens the valve with the default valve options
    if (remoteWasActiveLow != (bool)settings.remoteActiveLow) setupRemote(now);
    logEvent(EV_DEFAULTS, SRC_WEB, value);
    configDue = true;
    Serial.println(value == 1 ? F(">> Factory reset: default settings, calibration cleared")
                              : F(">> Settings back to the defaults"));
  } else if (strcmp(command, "T") == 0) {
    if (state != STATE_NORMAL) return CMD_BUSY;
    startValvePulses(STATE_CONFIRM_CLICKS, 2, settings.confirmClickMs, now);
    logEvent(EV_VALVE_TEST, SRC_WEB, 0);
  } else if (strcmp(command, "Q") == 0) {
    configDue = true;
  } else {
    return CMD_UNKNOWN;
  }
  return CMD_DONE;
}

uint8_t hexDigit(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return 0xFF;
}

void handleCommandLine(unsigned long now) {
  char *star = strrchr(cmdLine, '*');
  if (star == NULL || star[1] == '\0' || star[2] == '\0') {
    badCommands++;
    return;
  }
  uint8_t sum = 0;
  for (char *c = cmdLine; c < star; c++) sum ^= (uint8_t)*c;
  uint8_t high = hexDigit(star[1]), low = hexDigit(star[2]);
  if (high > 15 || low > 15 || ((high << 4) | low) != sum) {
    badCommands++;
    return;
  }
  *star = '\0';

  char *comma = strchr(cmdLine, ',');
  if (comma == NULL) {
    badCommands++;
    return;
  }
  *comma = '\0';
  long seq;
  if (!parseNumber(cmdLine, seq) || seq <= 0 || seq > 65535) {
    badCommands++;
    return;
  }
  char *command = comma + 1;
  char *args = strchr(command, ',');
  if (args != NULL) *args++ = '\0';

  if ((uint16_t)seq != lastCommandSeq) {
    lastCommandSeq = seq;
    lastCommandResult = runCommand(command, args, now);
  }
  statusDue = true;  // the answer goes in the next status line
}

void receiveCommands(unsigned long now) {
  while (espSerial.available()) {
    char c = espSerial.read();
    cmdCharAt = now;
    if (c == '$') {
      cmdStarted = true;
      cmdLength = 0;
    } else if (!cmdStarted) {
      // ignore anything before the '$'
    } else if (c == '\n' || c == '\r') {
      cmdLine[cmdLength] = '\0';
      cmdStarted = false;
      handleCommandLine(now);
    } else if (cmdLength < sizeof(cmdLine) - 1) {
      cmdLine[cmdLength++] = c;
    } else {
      cmdStarted = false;  // too long: dropped
      badCommands++;
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
    // The selected LED blinks in time with the valve while it is being pulsed,
    // and slowly while the valve is held shut at the limit.
    bool on = !valvePulsing() || valveOpen;
    if (state == STATE_LIMIT_HOLD) on = ((now - holdStartedAt) / HOLD_FLASH_MS) % 2 == 1;
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

void printField(Print &out, const __FlashStringHelper *name, long value) {
  out.print(F(",\""));
  out.print(name);
  out.print(F("\":"));
  out.print(value);
}

uint8_t inputBits() {
  uint8_t bits = button.stable ? 1 : 0;
  for (uint8_t i = 0; i < 4; i++) {
    if (remote[i].input.stable) bits |= 2 << i;
  }
  return bits;
}

// Status line for the ESP, one per second and straight after a command (see
// README.md for the fields). Counts are in pulses: the ESP divides by "ppl".
void buildStatusLine(unsigned long now) {
  noInterrupts();
  uint32_t totalPulses = isrPulseCount;
  uint16_t glitches = isrGlitches;
  interrupts();
  if (eventCount > 0) {
    lastEvent = events[0];
    memmove(events, events + 1, (eventCount - 1) * sizeof(events[0]));
    eventCount--;
  }

  espLength = 0;
  espSent = 0;
  EspLineBuffer out;
  out.print(F("{\"t\":\"s\""));
  printField(out, F("n"), totalPulses);
  printField(out, F("c"), countPulses);
  printField(out, F("s"), sessionPulses);
  printField(out, F("hz"), (long)(flowHz * 100 + 0.5));
  printField(out, F("m"), limitMode);
  printField(out, F("st"), state);
  printField(out, F("v"), valveOpen);
  printField(out, F("cp"), calPulses);
  printField(out, F("in"), inputBits());
  printField(out, F("ppl"), (long)(pulsesPerLitre * 100 + 0.5));
  printField(out, F("cal"), isCalibrated);
  printField(out, F("ack"), lastCommandSeq);
  printField(out, F("ok"), lastCommandResult);
  printField(out, F("ev"), lastEvent.number);
  printField(out, F("ec"), lastEvent.code);
  printField(out, F("es"), lastEvent.source);
  printField(out, F("ex"), lastEvent.extra);
  printField(out, F("g"), glitches);
  printField(out, F("bad"), badCommands);
  printField(out, F("up"), now / 1000);
  out.print(F("}\n"));
}

// Settings line for the ESP: every 10 s, and after a change.
void buildConfigLine() {
  espLength = 0;
  espSent = 0;
  EspLineBuffer out;
  out.print(F("{\"t\":\"cfg\""));
  for (uint8_t i = 0; i < SETTING_COUNT; i++) {
    SettingInfo info = settingInfo(i);
    out.print(F(",\""));
    out.print(info.key);
    out.print(F("\":"));
    out.print(getSetting(settings, info));
  }
  printField(out, F("ppl"), (long)(pulsesPerLitre * 100 + 0.5));
  printField(out, F("cal"), isCalibrated);
  printField(out, F("fw"), FIRMWARE_VERSION);
  out.print(F("}\n"));
}

// Sends one character per loop. A new line starts only after a quiet gap, in
// which the ESP sends its commands, and never while a command is arriving.
void sendEspLines(unsigned long now) {
  if (espSent < espLength) {
    espSerial.write(espLine[espSent++]);
    if (espSent == espLength) espLineEndAt = now;
    return;
  }
  if (now - espLineEndAt < ESP_LINE_GAP_MS) return;
  if (cmdStarted && now - cmdCharAt < 50) return;
  // Status lines come first, but a waiting settings line goes after at most one.
  bool configNow = configDue || now - lastConfigAt >= CONFIG_INTERVAL_MS;
  if (configNow && (!statusDue || lastLineWasStatus)) {
    configDue = false;
    lastConfigAt = now;
    lastLineWasStatus = false;
    buildConfigLine();
  } else if (statusDue) {
    statusDue = false;
    lastLineWasStatus = true;
    buildStatusLine(now);
  }
}

void report(unsigned long now) {
  if (now - lastReportAt < REPORT_INTERVAL_MS) return;
  lastReportAt = now;
  updateFlowRate();
  reportSerial();
  statusDue = true;
}

// ---------------------------------------------------------------------------
// Setup and main loop
// ---------------------------------------------------------------------------
void setup() {
  loadSettings();

  // Set the valve level before enabling the output so the valve does not glitch.
  setValveOpen(true);
  pinMode(PIN_VALVE, OUTPUT);
  setValveOpen(true);

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_FLOW_SENSOR, INPUT_PULLUP);
  pinMode(PIN_LED_LIMIT_1, OUTPUT);
  pinMode(PIN_LED_LIMIT_2, OUTPUT);
  pinMode(PIN_LED_LIMIT_3, OUTPUT);

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

  setupRemote(millis());

  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_SENSOR), onFlowPulse, FALLING);
  logEvent(EV_BOOT, SRC_AUTO, FIRMWARE_VERSION);

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
  Serial.print(F("Button: short press = next limit + reset count | hold "));
  Serial.print(settings.calHoldSeconds);
  Serial.println(F(" s = calibrate"));
  Serial.println(F("Remote: press = choose limit (clicks) | hold any = reset count (clicks)"));
  Serial.println(F("        hold D = calibrate"));
  Serial.println(F("Web: join Wi-Fi VAT_Aqua_Tracka, open http://192.168.4.1"));
  Serial.println(F(""));
}

void loop() {
  unsigned long now = millis();

  collectPulses();
  receiveCommands(now);
  handleButton(now);
  handleRemote(now);
  checkLimit(now);
  updateValvePulses(now);
  updateLeds(now);
  report(now);
  sendEspLines(now);
}

/*
  RemoteTest
  ==========
  Checks the RX480E / RX480R 433 MHz receiver on its own, before it goes into
  the Water Valve Controller.

  Wiring (nothing else is needed):
    Receiver GND -> Nano GND
    Receiver +V  -> Nano 5V
    Receiver D0  -> A0   (remote button D on the tested RX480R_4CH V4)
    Receiver D1  -> A1   (button C)
    Receiver D2  -> A2   (button B)
    Receiver D3  -> A3   (button A)
    Receiver VT  -> A4   (optional, set WATCH_VT to true)

  Open the Serial Monitor at 115200 baud. Press each remote button once, then
  hold one for about 3 seconds and let go. The sketch reports the voltage,
  how long each output stayed on, and anything that would upset the main sketch.
*/

const bool WATCH_VT = false;                  // true if VT is wired to A4

const uint8_t PINS[5] = { A0, A1, A2, A3, A4 };
// Button letters are for the tested board, which drives D3 for button A. If
// yours differs, the D numbers are still right.
const char *const NAMES[5] = { "D0 / button D", "D1 / button C", "D2 / button B",
                               "D3 / button A", "VT / any button" };
const uint8_t FREE_FLOW_CHANNEL = 0;          // D0 = button D = FREE FLOW in the main sketch

const int HIGH_THRESHOLD = 307;               // 1.5 V, the same level the main sketch uses
const int WEAK_HIGH = 512;                    // below 2.5 V counts as a weak signal
const unsigned long PRESS_GAP_MS = 300;       // LOW for longer than this = the press has ended
const unsigned long MAIN_RELEASE_MS = 150;    // gaps this long would split a hold in the main sketch
const unsigned long STUCK_MS = 5000;          // HIGH for this long = probably not momentary mode
const unsigned long IDLE_REPORT_MS = 10000;

struct Channel {
  bool high;
  bool pressing;
  bool warned;
  unsigned long pressStart;
  unsigned long lowSince;
  unsigned long longestGap;
  uint16_t dropouts;
  int peak;
};

Channel ch[5];
unsigned long lastIdleReport = 0;

uint8_t channelCount() {
  return WATCH_VT ? 5 : 4;
}

float toVolts(int counts) {
  return counts * 5.0 / 1023.0;
}

void printVolts(int counts) {
  Serial.print(toVolts(counts), 2);
  Serial.print(F(" V"));
}

void printIdleLine() {
  Serial.print(F("Idle:"));
  for (uint8_t i = 0; i < channelCount(); i++) {
    Serial.print(F("  "));
    Serial.print(NAMES[i]);
    Serial.print(F(" "));
    printVolts(analogRead(PINS[i]));
  }
  Serial.println();
}

void reportPress(uint8_t i, const Channel &c) {
  unsigned long held = c.lowSince - c.pressStart;
  Serial.print(NAMES[i]);
  Serial.print(F(" released after "));
  Serial.print(held / 1000.0, 2);
  Serial.print(F(" s, peak "));
  printVolts(c.peak);
  if (c.dropouts > 0) {
    Serial.print(F(", "));
    Serial.print(c.dropouts);
    Serial.print(F(" drop-out(s), longest "));
    Serial.print(c.longestGap);
    Serial.print(F(" ms"));
  }
  Serial.println();

  if (c.peak < WEAK_HIGH) {
    Serial.println(F("   Weak signal: check the receiver is powered from 5 V and GND is shared."));
  }
  if (c.longestGap >= MAIN_RELEASE_MS) {
    Serial.println(F("   Gaps of 0.15 s or more would split a long hold in the main sketch."));
    Serial.println(F("   Check the antenna is straight and clear of metal, and test closer."));
  }
  if (i < 4) {
    Serial.print(F("   In the main sketch this is "));
    if (held >= 20000 && i == FREE_FLOW_CHANNEL) {
      Serial.println(F("a 20 s hold: calibration."));
    } else if (held >= 2000) {
      Serial.println(F("a 2 s hold: count reset."));
    } else {
      Serial.println(F("a short press: choose a limit."));
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 5; i++) pinMode(PINS[i], INPUT);
  delay(300);

  Serial.println();
  Serial.println(F("=== RX480E receiver test ==="));
  Serial.println(F("Press each remote button, then hold one for about 3 s and let go."));
  Serial.println();

  unsigned long now = millis();
  for (uint8_t i = 0; i < channelCount(); i++) {
    int v = analogRead(PINS[i]);
    Channel &c = ch[i];
    c.high = v > HIGH_THRESHOLD;
    c.pressing = c.high;
    c.warned = false;
    c.pressStart = now;
    c.lowSince = now;
    c.longestGap = 0;
    c.dropouts = 0;
    c.peak = v;
    Serial.print(NAMES[i]);
    Serial.print(F(" at rest: "));
    printVolts(v);
    if (c.high) Serial.print(F("  <- already ON: the receiver may be in toggle or latched mode"));
    Serial.println();
  }
  Serial.println();
  lastIdleReport = now;
}

void loop() {
  unsigned long now = millis();
  bool anyPressing = false;

  for (uint8_t i = 0; i < channelCount(); i++) {
    Channel &c = ch[i];
    int v = analogRead(PINS[i]);
    bool high = v > HIGH_THRESHOLD;

    if (high) {
      if (!c.pressing) {
        c.pressing = true;
        c.warned = false;
        c.pressStart = now;
        c.longestGap = 0;
        c.dropouts = 0;
        c.peak = v;
        Serial.print(NAMES[i]);
        Serial.print(F(" ON  "));
        printVolts(v);
        Serial.println();
      } else if (!c.high) {
        // Back on after a short gap: the receiver briefly lost the signal.
        unsigned long gap = now - c.lowSince;
        c.dropouts++;
        if (gap > c.longestGap) c.longestGap = gap;
      }
      if (v > c.peak) c.peak = v;
      if (!c.warned && now - c.pressStart >= STUCK_MS) {
        c.warned = true;
        Serial.print(NAMES[i]);
        Serial.println(F(" has been ON for 5 s."));
        Serial.println(F("   If you have let go of the remote, the receiver is in toggle or latched"));
        Serial.println(F("   mode. Re-pair it in momentary mode (see the README)."));
      }
    } else {
      if (c.high) c.lowSince = now;
      if (c.pressing && now - c.lowSince >= PRESS_GAP_MS) {
        c.pressing = false;
        reportPress(i, c);
      }
    }
    c.high = high;
    if (c.pressing) anyPressing = true;
  }

  if (!anyPressing && now - lastIdleReport >= IDLE_REPORT_MS) {
    lastIdleReport = now;
    printIdleLine();
  }
}

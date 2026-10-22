/*
  UltrasonicTest - diagnose an ultrasonic ranger that always reads -1

  Wiring for this test (jumper wires straight to the Uno):
    GND        -> GND
    VCC        -> 5V
    SIG (yellow, or the pin labelled SIG / ECHO)          -> D7
    NC  (white,  or the pin labelled NC  / TRIG)          -> D8

  Open the Serial Monitor at 9600 baud and hold your hand ~20 cm in front of
  the sensor. Each line tries a different way of talking to the sensor:

    1-pin on D7          -> genuine Seeed Grove Ultrasonic Ranger (SIG only)
    trig D8, echo D7     -> clone with separate Trig/Echo pins
    trig D7, echo D8     -> clone with separate Trig/Echo pins, other way round

  Whichever line shows a distance tells us how the sensor needs to be driven.
  "no echo" on every line means the sensor isn't answering at all: try another
  jumper for each wire, check 5V with a multimeter, or try another sensor.
*/

const int PIN_A = 7;
const int PIN_B = 8;
const unsigned long TIMEOUT_US = 100000UL;  // 100 ms, generous

void pulse(int pin) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delayMicroseconds(2);
  digitalWrite(pin, HIGH);
  delayMicroseconds(10);
  digitalWrite(pin, LOW);
}

// Single-pin sensor: trigger and echo on the same pin
long readOnePin(int pin) {
  pulse(pin);
  pinMode(pin, INPUT);
  return pulseIn(pin, HIGH, TIMEOUT_US);
}

// Two-pin sensor: separate trigger and echo pins
long readTwoPin(int trigPin, int echoPin) {
  pinMode(echoPin, INPUT);
  pulse(trigPin);
  long us = pulseIn(echoPin, HIGH, TIMEOUT_US);
  pinMode(trigPin, INPUT);  // release the pin so the next test isn't disturbed
  return us;
}

void printResult(const char *label, long us) {
  Serial.print(label);
  if (us == 0) {
    Serial.println("no echo");
  } else {
    Serial.print(us / 29 / 2);
    Serial.print(" cm  (");
    Serial.print(us);
    Serial.println(" us)");
  }
  delay(60);  // let echoes die out before the next test
}

void setup() {
  Serial.begin(9600);
  pinMode(PIN_A, INPUT);
  pinMode(PIN_B, INPUT);
  Serial.println("Ultrasonic test - hold your hand ~20 cm away");
}

void loop() {
  printResult("1-pin on D7       : ", readOnePin(PIN_A));
  printResult("trig D8, echo D7  : ", readTwoPin(PIN_B, PIN_A));
  printResult("trig D7, echo D8  : ", readTwoPin(PIN_A, PIN_B));
  Serial.println("---");
  delay(500);
}

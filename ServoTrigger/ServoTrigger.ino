/*
  ServoTrigger - Grove ultrasonic ranger + push button + continuous servo + LED

  Behaviour:
    - If an object is within 50 cm of the ultrasonic sensor, OR the button is
      pressed, the servo "opens" 90 degrees and the LED on pin 13 turns on.
    - Once the object is gone AND the button is released, everything stays
      active for 5 more seconds, then the servo "closes" and the LED turns off.

  Wiring (Grove Base Shield on an Arduino Uno):
    Ultrasonic Ranger  -> D7  (single SIG pin is used for trigger and echo)
    Push Button        -> D2  (10K pull-up to 5V, button to GND: LOW = pressed)
    Servo (signal)     -> D3
    LED                -> D13 (on-board LED, or external LED + 220R resistor)

  About the continuous (360 degree) servo:
    A continuous servo can't be told "go to 90 degrees". servo.write() sets its
    SPEED and DIRECTION instead:
        90        = stop
        0..89     = spin one way (0 = full speed)
        91..180   = spin the other way (180 = full speed)
    So "open 90 degrees" is done by spinning for a set time and then stopping.
    Tune TURN_TIME_MS until one move is a quarter turn on your servo.
    If the servo creeps while it should be stopped, tune SERVO_STOP (try 88-92)
    or adjust the trim screw on the servo, if it has one.
*/

#include <Servo.h>

// ---- Pins ----
const int ULTRASONIC_PIN = 7;
const int BUTTON_PIN     = 2;
const int SERVO_PIN      = 3;
const int LED_PIN        = 13;

// ---- Settings ----
const int           DETECT_DISTANCE_CM = 50;    // trigger if object is closer than this
const unsigned long HOLD_TIME_MS       = 5000;  // stay open this long after trigger ends

const int           SERVO_STOP   = 90;   // "stop" value for the continuous servo
const int           SERVO_OPEN   = 120;  // speed/direction used to open
const int           SERVO_CLOSE  = 60;   // speed/direction used to close (opposite way)
const unsigned long TURN_TIME_MS = 350;  // how long to spin for ~90 degrees (tune this!)

Servo servo;
bool isOpen = false;
unsigned long lastTriggerTime = 0;

// Reads the Grove Ultrasonic Ranger. Returns distance in cm, or -1 if nothing seen.
long readDistanceCm() {
  // Send a short trigger pulse on the SIG pin
  pinMode(ULTRASONIC_PIN, OUTPUT);
  digitalWrite(ULTRASONIC_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_PIN, HIGH);
  delayMicroseconds(5);
  digitalWrite(ULTRASONIC_PIN, LOW);

  // Listen for the echo on the same pin (30 ms timeout ~ 5 m)
  pinMode(ULTRASONIC_PIN, INPUT);
  long duration = pulseIn(ULTRASONIC_PIN, HIGH, 30000UL);
  if (duration == 0) {
    return -1;  // no echo - nothing in range
  }
  return duration / 29 / 2;  // speed of sound: ~29 us per cm, there and back
}

// Spin the continuous servo for TURN_TIME_MS, then stop it.
void turnServo(int speed) {
  servo.attach(SERVO_PIN);
  servo.write(speed);
  delay(TURN_TIME_MS);
  servo.write(SERVO_STOP);
  delay(50);
  servo.detach();  // detaching guarantees the servo doesn't creep while idle
}

void openGate() {
  Serial.println("OPEN");
  digitalWrite(LED_PIN, HIGH);
  turnServo(SERVO_OPEN);
  isOpen = true;
}

void closeGate() {
  Serial.println("CLOSE");
  turnServo(SERVO_CLOSE);
  digitalWrite(LED_PIN, LOW);
  isOpen = false;
}

void setup() {
  Serial.begin(9600);
  pinMode(BUTTON_PIN, INPUT);  // external 10K pull-up: reads HIGH idle, LOW when pressed
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.println("Ready");
}

void loop() {
  long distance = readDistanceCm();
  bool objectNear    = (distance > 0 && distance <= DETECT_DISTANCE_CM);
  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.print(" cm   Button: ");
  Serial.println(buttonPressed ? "PRESSED" : "released");

  if (objectNear || buttonPressed) {
    lastTriggerTime = millis();  // keep restarting the 5 s countdown while triggered
    if (!isOpen) {
      openGate();
    }
  } else if (isOpen && millis() - lastTriggerTime >= HOLD_TIME_MS) {
    closeGate();
  }

  delay(60);  // let ultrasonic echoes die out between readings
}

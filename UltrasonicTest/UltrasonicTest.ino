/*
  UltrasonicTest - diagnose a Grove Ultrasonic Ranger that always reads -1

  Upload this on its own (nothing else needs to be connected), open the
  Serial Monitor at 9600 baud and hold your hand ~20 cm in front of the sensor.

  For each of pins D7 and D8 it prints the raw echo time in microseconds,
  measured with a short (30 ms) and a long (1 s) timeout:
    - "no echo" on everything      -> wiring/power problem (see checks below)
    - numbers on D8 but not D7     -> cable is in the wrong port; use that pin
    - numbers only with long timeout -> increase the timeout in ServoTrigger

  Checks if you see no echo anywhere:
    - Grove Base Shield VCC switch set to 5V (not 3.3V)
    - Shield pushed fully onto the Uno, cable clicked in at both ends
    - Try a different Grove cable / port (change the pins below to match)
*/

const int PINS[] = {7, 8};

long readEcho(int pin, unsigned long timeoutUs) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delayMicroseconds(2);
  digitalWrite(pin, HIGH);
  delayMicroseconds(10);
  digitalWrite(pin, LOW);
  pinMode(pin, INPUT);
  return pulseIn(pin, HIGH, timeoutUs);
}

void printResult(long us) {
  if (us == 0) {
    Serial.print("no echo     ");
  } else {
    Serial.print(us);
    Serial.print(" us = ");
    Serial.print(us / 29 / 2);
    Serial.print(" cm   ");
  }
}

void setup() {
  Serial.begin(9600);
  Serial.println("Ultrasonic test - hold your hand ~20 cm away");
}

void loop() {
  for (int pin : PINS) {
    Serial.print("D");
    Serial.print(pin);
    Serial.print("  30ms: ");
    printResult(readEcho(pin, 30000UL));
    delay(60);
    Serial.print(" 1s: ");
    printResult(readEcho(pin, 1000000UL));
    Serial.println();
    delay(60);
  }
  Serial.println("---");
  delay(500);
}

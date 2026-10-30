// CircuitPath keychain: buzzer test.  UNTESTED on hardware.  Board: "Arduino Micro".
// The piezo sits between pin 9 and pin 10.  tone(9, ...) alone works; making pin 10 do the
// opposite of pin 9 (bridged drive) roughly doubles the voltage across the piezo, so it is louder.
const uint8_t BUZZ_A = 9, BUZZ_B = 10;

void beep(unsigned int hz, unsigned int ms) {
  unsigned long half = 500000UL / hz;                 // microseconds per half cycle
  unsigned long end = millis() + ms;
  while (millis() < end) {
    digitalWrite(BUZZ_A, HIGH); digitalWrite(BUZZ_B, LOW);  delayMicroseconds(half);
    digitalWrite(BUZZ_A, LOW);  digitalWrite(BUZZ_B, HIGH); delayMicroseconds(half);
  }
  digitalWrite(BUZZ_A, LOW); digitalWrite(BUZZ_B, LOW);
}
void setup() { pinMode(BUZZ_A, OUTPUT); pinMode(BUZZ_B, OUTPUT); }
void loop() { beep(2000, 150); delay(400); beep(3000, 150); delay(400); beep(4000, 150); delay(1200); }

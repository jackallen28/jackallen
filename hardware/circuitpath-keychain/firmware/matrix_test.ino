// CircuitPath keychain: LED matrix test.  UNTESTED on hardware: first thing to run on a real board.
// Board in Arduino IDE: "Arduino Micro" (after the one-off bootloader burn, see README).
// Two MAX7219 chips share CLK/LOAD and are chained: MCU -> U2 (columns 1-6) -> U3 (columns 7-11).
#include <SPI.h>
const uint8_t LOAD_PIN = SS;        // PB0, the chip-select / LOAD line
uint8_t frame[11];                  // one byte per column, bit 6 = top row ... bit 0 = bottom row

void send2(uint8_t reg, uint8_t farData, uint8_t nearData) {   // far chip (U3) is shifted first
  digitalWrite(LOAD_PIN, LOW);
  SPI.transfer(reg); SPI.transfer(farData);
  SPI.transfer(reg); SPI.transfer(nearData);
  digitalWrite(LOAD_PIN, HIGH);
}
void show() {
  for (uint8_t d = 0; d < 8; d++)   // digit d of each chip is one LED column
    send2(1 + d, d < 5 ? frame[6 + d] : 0, d < 6 ? frame[d] : 0);
}
void setup() {
  pinMode(LOAD_PIN, OUTPUT); digitalWrite(LOAD_PIN, HIGH);
  SPI.begin();
  send2(0x0F, 0, 0);                // display test off
  send2(0x09, 0, 0);                // no BCD decode
  send2(0x0B, 4, 5);                // scan limit: U3 has 5 columns, U2 has 6
  send2(0x0A, 4, 4);                // brightness 0-15
  send2(0x0C, 1, 1);                // wake up
}
void loop() {                       // a single lit column sweeps across, then a single lit row
  for (uint8_t c = 0; c < 11; c++) { for (uint8_t i = 0; i < 11; i++) frame[i] = (i == c) ? 0x7F : 0; show(); delay(150); }
  for (uint8_t r = 0; r < 7; r++)  { for (uint8_t i = 0; i < 11; i++) frame[i] = 1 << (6 - r); show(); delay(150); }
}

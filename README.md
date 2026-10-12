# jackallen

- [WaterValveController](WaterValveController/) – Arduino Nano water flow limiter: YF-G1 flow sensor,
  MOSFET-switched solenoid valve, push button + 433 MHz remote, 25/50/100 L/free-flow limits,
  bucket calibration saved to EEPROM, and serial/ESP status output. Includes the KiCad schematic and
  two 2-layer PCBs (through-hole and mixed SMD/THT) with JLCPCB order files (gerbers, BOM, CPL).
  [`hardware-atmega/`](WaterValveController/hardware-atmega/) is a separate, smaller board with the
  ATmega328P built in (no Nano module), for review.
- [RemoteTest](RemoteTest/) – stand-alone test sketch for the RX480E 433 MHz receiver: shows each
  output's voltage, press length and drop-outs, and warns if it isn't in momentary mode.

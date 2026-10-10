# Water Valve Controller: schematic and PCB files

A carrier board for the Arduino Nano that brings every connection out to screw terminals or headers,
with the filtering and protection parts that keep the flow count reliable next to a switching solenoid.
The 433 MHz receiver module plugs straight into the board.

| File | What it is |
|------|------------|
| `WaterValveController-schematic.pdf` / `.svg` | The schematic, ready to print or view |
| `WaterValveController.kicad_pro`, `.kicad_sch` | The KiCad 7 project |
| `WaterValveController-KiCad.zip` | The same project in one zip, for downloading |
| `WaterValve.kicad_sym`, `sym-lib-table` | Symbols for the receiver module and the off-board parts |
| `WaterValveController.net` | KiCad netlist |
| `WaterValveController-BOM.csv` | Parts list |
| `tools/` | Scripts that generate all of the above (see the end of this file) |

## Opening the design

Open `WaterValveController.kicad_pro` in KiCad 7 or newer (free). For the PCB, open the PCB editor and
run Tools → Update PCB from Schematic. The off-board parts (K1, SV1, D2, FS1) are marked "exclude from
board", so only the carrier-board parts are placed. All footprints come from KiCad's standard library.

## Receiver orientation

U2, the RX480E-4 / RX480R_4CH receiver, stands upright in a 7-pin socket wired as **1 GND, 2 +V, 3 D0,
4 D1, 5 D2, 6 D3, 7 VT**. On the module, GND is the pin at the learn-button end and VT is the pin at the
antenna end (checked against the labels on the back of the V4 board).

The header is straight, so the module would also fit the socket backwards, which puts 5 V onto an output.
Mark **GND / button end** and **VT / antenna end** on the PCB silkscreen next to the socket.

## Board connectors

| Ref | Connector | Pins |
|-----|-----------|------|
| J1 | 12 V DC IN (2-way screw) | 1 = +12 V, 2 = GND |
| J2 | VALVE POWER (2-way screw) | 1 = +12 V (fused) → relay COM, 2 = GND ← valve − |
| J3 | RELAY MODULE (3-pin header) | 1 = VCC (+5 V), 2 = IN (D8), 3 = GND |
| J4 | FLOW SENSOR (3-way screw) | 1 = +5 V (red), 2 = SIG (yellow), 3 = GND (black) |
| J5 | ESP (3-pin header) | 1 = +5 V → ESP32-C3-Zero 5V pin, 2 = DATA (3.3 V level) → GPIO20, 3 = GND |
| U2 | RX480E-4 receiver (7-pin socket) | 1 GND, 2 +V (filtered 5 V), 3–6 D0–D3 → A0–A3, 7 VT (unused) |

The sketch uses the same Nano pins. Its `REMOTE_ACTIVE_LOW` setting must be `false` for this receiver
(the default).

## How the board reduces interference

The numbers match the notes on the schematic sheet.

1. **Flyback diode at the valve (D2).** A 1N5408 (or 1N4007) across the valve's own terminals, stripe on +.
   It stops the switch-off spike at its source.
2. **Separate valve current path.** The valve's +12 V and return run on their own pair (J2) straight back
   to the supply input (J1). The large valve current never flows through the Nano's ground wiring.
3. **Decoupling.** C1 470 µF + C2 100 nF on 12 V, C3 100 nF + C4 100 µF on 5 V, C10 100 µF at the relay
   header (the relay coil pulls current each time it switches), C11 100 nF at the Nano and C6 100 nF at the
   flow sensor connector.
4. **Flow input filter.** R1 10 kΩ pull-up gives clean edges. R2 1 kΩ + C5 10 nF filter out short spikes
   (10 µs time constant, far faster than the sensor's maximum ~108 Hz), and R2 also protects the pin.
   The firmware also ignores pulses less than 2 ms apart.
5. **Button and remote inputs.** The button has a 10 kΩ pull-up and 100 nF filter. Each receiver output
   goes through a 1 kΩ series resistor (R7–R10) with a 100 kΩ pull-down (R13–R16), so the Nano's inputs
   never float. The receiver's supply is filtered by R17 10 Ω + C8 47 µF + C9 100 nF, which keeps relay
   and regulator noise from reducing its range. The firmware debounces both.
6. **Supply protection.** F1 (2 A slow-blow) and D1. If the supply is connected backwards, D1 conducts and
   blows the fuse instead of damaging the board.
7. **ESP level shifting.** The ESP32-C3-Zero runs from 5 V, but its GPIO pins are 3.3 V only.
   R11 1.8 kΩ / R12 3.3 kΩ turn the Nano's 5 V data into 3.24 V before it reaches J5.
8. **Cable routing.** Twist the flow sensor's signal wire with its GND wire and keep it away from the valve
   and 12 V wires. For a long sensor run, use shielded cable with the shield connected to GND at the
   controller end only.
9. **PCB layout.** See below.

**Regulator.** U1 is a TO-220 7805 footprint. With the ESP32-C3 fitted, its Wi-Fi peaks (about 350 mA)
take the 5 V load to roughly 0.5 A. Use a pin-compatible switching regulator such as the R-78E5.0-1.0
(1 A, same footprint, runs cool), or wire a 5 V buck module to the IN / GND / OUT pads. An L7805 also
works but needs a heatsink.

### PCB layout rules

1. **Zones.** Power and valve parts along one edge (J1, F1, D1, C1, U1, J2, J3, C10). The flow sensor
   input (J4, R1, R2, C5) and the ESP header (J5) on the opposite side. The Nano in between.
2. **J1 and J2 side by side.** The valve current then only travels a few centimetres. Make the 12 V valve
   tracks (J1 → F1 → J2) at least 1.5 mm wide, and run a direct wide track from J2 GND to J1 GND.
3. **Ground plane** on the bottom layer, connected to J1 GND.
4. **Receiver at a board edge,** standing upright with its antenna end facing away from the relay and J2.
   Keep tall parts (the relay module, C1, U1's heatsink) and the 12 V wiring clear of the antenna coil,
   and leave about 25 mm of headroom above the socket for the module and antenna.
5. **Capacitors next to the pins they protect:** C2 at U1 IN, C3 at U1 OUT, C11 at the Nano's 5V pin,
   C5 at D2, C8/C9 at the receiver's +V pin, C10 at J3, C6 at J4.
6. **Signal tracks away from 12 V.** Cross at right angles if they must meet; never run the flow track
   alongside a 12 V track.
7. **Heat.** Keep U1 away from the electrolytic capacitors and leave room for a heatsink.
8. **Silkscreen.** Label every connector pin and mark the polarity of C1, C4, C8, C10, the diodes and the LEDs.
9. **Mounting.** Four M3 holes (H1–H4) at the corners. Mount the board in a sealed box with cable glands,
   above the valve, with drip loops in the cables.

## Regenerating the files

The schematic is generated by a script so the wiring can be checked automatically.
With KiCad 7 installed (for `kicad-cli` and its symbol libraries):

```sh
cd hardware
python3 tools/gen_schematic.py .
python3 tools/make_outputs.py          # PDF, SVG, netlist, BOM, zip
kicad-cli sch export netlist --format kicadxml -o /tmp/net.xml WaterValveController.kicad_sch
python3 tools/check_netlist.py /tmp/net.xml   # compares every net against the intended design
```

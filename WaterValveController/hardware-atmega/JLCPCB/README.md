# JLCPCB order files: standalone ATmega328P board

Upload these three files on jlcpcb.com:

1. **`WaterValveController-ATmega-gerbers.zip`**: the PCB. Options: 2 layers, 1.6 mm, 1 oz copper (the defaults).
2. **`WaterValveController-ATmega-BOM-JLCPCB.csv`** (or the same list as `.xlsx`, laid out like JLCPCB's sample BOM).
3. **`WaterValveController-ATmega-CPL-JLCPCB.csv`**: Designator, Mid X, Mid Y, Rotation, Layer (mm).

Turn on **PCB Assembly**, top side. All 75 parts are on the top: 66 SMD and 9 through-hole (terminals, JST headers, receiver socket). JLCPCB machine-places the SMD parts; the through-hole ones cost extra per joint, so you can untick them and solder them yourself.

## Check in the placement preview

- **U4 (ATmega328P) and U3 (CH340N):** the pin-1 dot matches the silkscreen dot.
- **Q1, Q3 (AO4407A) and U1 (TPS54202H):** pin 1 matches the silkscreen mark.
- **D2, D3, D4:** the cathode band at the end with the silkscreen bar.
- **C1:** the + side at the + mark. **D5:** the green LED's cathode at the bar.

The CPL already has the usual corrections for JLCPCB's reels (SOIC/SOP and TQFP +270, SOT-23 and SMD electrolytics +180), the same ones the KiCad JLCPCB plugins apply.

## Not on the JLCPCB order

- **J10 ICSP:** the 6 holes take a 2 x 3 pin header, needed only once to burn the bootloader (see the board README).
- **Off-board parts:** valve, flow sensor, rocker switch, panel button and LEDs, JST housings and leads, the receiver and ESP32 modules, M4 bolts.

## Part numbers

| Designator | Part | JLCPCB / LCSC |
|---|---|---|
| C1 | 100uF 25V electrolytic SMD 6.3 x 7.7 mm | C22383804 |
| C2 | 10uF 25V X5R 0805 | C15850 |
| C3, C4, C7, C8, C9, C12, C13, C14, C15, C16, C18, C20 | 100nF 50V X7R 0603 | C14663 |
| C5, C6, C19 | 22uF X5R 0805 | C45783 |
| C10, C11 | 22pF 50V C0G 0603 | C1653 |
| C17 | 10nF 50V X7R 0603 | C57112 |
| D2 | SS34 | C8678 |
| D3 | B5819W | C8598 |
| D4 | 1N4148W | C81598 |
| D5 | LED green 0603 | C72043 |
| F1 | Resettable fuse 3 A hold, 30 V, 2920 | C22446884 |
| J1 | Screw terminal 2P 5.08 mm (KF128L-5.08-2P) | C474940 |
| J2 | Screw terminal 3P 5.08 mm (KF128L-5.08-3P) | C474941 |
| J3 | Screw terminal 4P 5.08 mm (DB128L-5.08-4P) | C2827883 |
| J4 | JST XH 4-pin header B4B-XH-A | C144395 |
| J5, J6, J7, J8 | JST XH 2-pin header B2B-XH-A | C158012 |
| J9 | USB-C socket 16P (HRO TYPE-C-31-M-12) | C165948 |
| L1 | 10 uH power inductor 4 x 4 x 2 mm | C135263 |
| Q1, Q3 | AO4407A P-MOSFET | C16072 |
| Q2 | 2N7002 N-MOSFET | C8545 |
| R1, R3, R18, R20, R39 | 10k 1% 0603 | C25804 |
| R2, R7, R8, R9, R10, R21, R37, R38, R40 | 1k 1% 0603 | C21190 |
| R4, R5, R6 | 330R 1% 0603 | C23138 |
| R11 | 1.8k 1% 0603 | C4177 |
| R12 | 3.3k 1% 0603 | C22978 |
| R13, R14, R15, R16, R30, R31 | 100k 1% 0603 | C25803 |
| R17 | 10R 1% 0603 | C22859 |
| R19 | 100R 1% 0603 | C22775 |
| R32 | 20k 1% 0603 | C4184 |
| R33 | 15k 1% 0603 | C22809 |
| R34 | 2k 1% 0603 | C22975 |
| R35, R36 | 5.1k 1% 0603 | C23186 |
| U1 | TPS54202H | C527684 |
| U2 | 7-pin female header 2.54 mm (receiver socket) | C6684533 |
| U3 | CH340N | C2977777 |
| U4 | ATmega328P-AU | C14877 |
| Y1 | 16 MHz crystal 3225, 20 pF | C13738 |

The resistor and capacitor numbers, the crystal, the diodes and the LED come from JLCPCB's basic-parts list; JLCPCB's BOM step shows each matched part's value, so check them there. Stock changes daily: if a part is out of stock, the BOM step offers alternatives.

# JLCPCB order files: mixed SMD + through-hole board

Upload these three files on jlcpcb.com:

1. **`WaterValveController-SMD-gerbers.zip`**: the PCB itself (copper, solder mask, silkscreen, outline, drill files).
   PCB options: 2 layers, 1.6 mm, 1 oz copper (the defaults), any colour, HASL or ENIG.
2. **`WaterValveController-SMD-BOM-JLCPCB.csv`** (or the same list as `.xlsx`, laid out like JLCPCB's sample
   BOM): the parts list (Comment, Designator, Footprint, JLCPCB Part #).
3. **`WaterValveController-SMD-CPL-JLCPCB.csv`**: where each part goes (Designator, Mid X, Mid Y, Rotation,
   Layer; millimetres and degrees).

Turn on **PCB Assembly**, assemble the **top side**, then upload the BOM and CPL files when asked.
All 46 parts are on the top side: 32 SMD and 14 through-hole.

JLCPCB machine-places the SMD parts. The through-hole parts (terminals, JST headers, fuse
holder, regulator, electrolytic capacitors, receiver socket) are soldered by hand or wave
soldering at an extra cost per joint, shown on the order page. To keep the cost down, untick
them in the BOM step and solder them yourself: they are all large and easy to solder.

## Check in the placement preview

JLCPCB shows each part on the board before you order. Rotate any part that does not sit
on its pads, and check these in particular:

- **D1 and D2 (S3M):** the cathode band goes on pad 1, at the closed end of the
  silkscreen outline. A reversed D1 or D2 shorts the 12 V supply and blows the fuse.
- **Q1 (IRFR5305, DPAK):** the large tab goes on the large pad, towards the top edge.
- **Q2 (2N7002, SOT-23):** one pin on one side, two on the other, matching the pads.
  The CPL already adds JLCPCB's usual 180° correction for SOT-23.
- **C1, C4, C8:** the + lead goes to the square pad (+ mark).

## Making these files again in KiCad

Every part carries its number in an **LCSC Part #** field (on the schematic symbol and on
the footprint). After changing the design in KiCad 8, 9 or 10, the free **Fabrication
Toolkit** plugin (KiCad Plugin and Content Manager) makes the gerbers, `bom.csv` and
`positions.csv` in this same format in one click, applying the same rotation corrections.
Exclude A1 and the mounting holes from its BOM, as here.

## Not on the JLCPCB order

- **A1:** two 15-pin 2.54 mm female headers for the Nano (LCSC C2897378), solder them yourself.
- **F1 fuse:** the holder is fitted; push in a 3 A ATO/ATC blade fuse.
- **Off-board parts:** valve, flow sensor, rocker switch, panel button and LEDs, their JST
  housings and crimped leads, and the M4 bolts (see the main BOM in the board folder).

## Part numbers

| Designator | Part | JLCPCB / LCSC |
|---|---|---|
| C1 | 470uF 25V electrolytic, 10 x 12.5 mm | C368591 |
| C2, C3, C6, C7, C9, C10 | 100nF 50V X7R 0805 | C49678 |
| C4 | 100uF 16V electrolytic, 6.3 x 11 mm | C911212 |
| C5 | 10nF 50V X7R 0805 | C1710 |
| C8 | 47uF 16V electrolytic, 5 x 11 mm | C134586 |
| D1, D2 | S3M 3A 1000V diode | C388240 |
| F1 | Keystone 3557-2 ATO blade fuse holder | C352820 |
| J1 | Screw terminal 2P 5.08 mm (KF128L-5.08-2P) | C474940 |
| J2 | Screw terminal 3P 5.08 mm (KF128L-5.08-3P) | C474941 |
| J3 | Screw terminal 4P 5.08 mm (DB128L-5.08-4P) | C2827883 |
| J4 | JST XH 4-pin header B4B-XH-A | C144395 |
| J5, J6, J7, J8 | JST XH 2-pin header B2B-XH-A | C158012 |
| Q1 | IRFR5305 P-MOSFET | C2624 |
| Q2 | 2N7002 N-MOSFET | C8545 |
| R1, R3, R18, R20 | 10k 1% 0805 | C17414 |
| R2, R7, R8, R9, R10, R21 | 1k 1% 0805 | C17513 |
| R4, R5, R6 | 330R 1% 0805 | C17630 |
| R11 | 1.8k 1% 0805 | C17398 |
| R12 | 3.3k 1% 0805 | C114531 |
| R13, R14, R15, R16 | 100k 1% 0805 | C149504 |
| R17 | 10R 1% 0805 | C17415 |
| R19 | 100R 1% 0805 | C17408 |
| U1 | RECOM R-78E5.0-1.0 5 V switching regulator | C3033024 |
| U2 | 7-pin female header 2.54 mm (receiver socket) | C6684533 |

U2 is a gold-plated Samtec socket, the only 7-pin one found in JLCPCB's library; any 7-pin
2.54 mm female header does the same job if you would rather fit a cheaper one yourself.
Stock changes daily: if a part is out of stock, JLCPCB's BOM step offers alternatives.

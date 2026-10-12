# JLCPCB order files: through-hole board

Upload these three files on jlcpcb.com:

1. **`WaterValveController-gerbers.zip`**: the PCB itself (copper, solder mask, silkscreen, outline, drill files).
   PCB options: 2 layers, 1.6 mm, 1 oz copper (the defaults), any colour, HASL or ENIG.
2. **`WaterValveController-BOM-JLCPCB.csv`** (or the same list as `.xlsx`, laid out like JLCPCB's sample
   BOM): the parts list (Comment, Designator, Footprint, JLCPCB Part #).
3. **`WaterValveController-CPL-JLCPCB.csv`**: where each part goes (Designator, Mid X, Mid Y, Rotation,
   Layer; millimetres and degrees).

Turn on **PCB Assembly**, assemble the **top side**, then upload the BOM and CPL files when asked.
All 46 parts are on the top side: 0 SMD and 46 through-hole.

Almost every part on this board is through-hole, and JLCPCB charges extra per through-hole
solder joint. For a board assembled by JLCPCB, the mixed SMD + THT board in `smd/JLCPCB/`
is usually much cheaper. You can also order this board bare (gerbers only) and solder it.

## Check in the placement preview

JLCPCB shows each part on the board before you order. Rotate any part that does not sit
on its pads, and check these in particular:

- **D1 and D2 (1N5408):** the band (cathode) goes to the pad marked **K**. A reversed D1
  or D2 shorts the 12 V supply and blows the fuse.
- **Q1 (IRF9540N) and U1 (TO-220):** pin 1 on the square pad, metal tab towards the
  outline's tab line.
- **Q2 (2N7000):** the flat face matches the flat side of the outline.
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

## Parts without a part number

No JLCPCB part number was confirmed for: C5, R11, R12. In the BOM step,
search JLCPCB's library for the value in the Comment column (any part with the same
value and lead spacing fits), or untick them and solder them yourself.

## Part numbers

| Designator | Part | JLCPCB / LCSC |
|---|---|---|
| C1 | 470uF 25V electrolytic, 10 x 12.5 mm | C368591 |
| C2, C3, C6, C7, C9, C10 | 100nF 50V X7R ceramic, 5.08 mm lead spacing | C84772 |
| C4 | 100uF 16V electrolytic, 6.3 x 11 mm | C911212 |
| C5 | 10nF 50V X7R ceramic, 5.08 mm lead spacing | (choose) |
| C8 | 47uF 16V electrolytic, 5 x 11 mm | C134586 |
| D1, D2 | 1N5408 3A 1000V diode | C2460 |
| F1 | Keystone 3557-2 ATO blade fuse holder | C352820 |
| J1 | Screw terminal 2P 5.08 mm (KF128L-5.08-2P) | C474940 |
| J2 | Screw terminal 3P 5.08 mm (KF128L-5.08-3P) | C474941 |
| J3 | Screw terminal 4P 5.08 mm (DB128L-5.08-4P) | C2827883 |
| J4 | JST XH 4-pin header B4B-XH-A | C144395 |
| J5, J6, J7, J8 | JST XH 2-pin header B2B-XH-A | C158012 |
| Q1 | IRF9540NPBF P-MOSFET | C2575 |
| Q2 | 2N7000 N-MOSFET | C232838 |
| R1, R3, R18, R20 | 10k 1% 1/4W metal film | C57436 |
| R2, R7, R8, R9, R10, R21 | 1k 1% 1/4W metal film | C57435 |
| R4, R5, R6 | 330R 1% 1/4W metal film | C58608 |
| R11 | 1.8k 1% 1/4W metal film | (choose) |
| R12 | 3.3k 1% 1/4W metal film | (choose) |
| R13, R14, R15, R16 | 100k 1% 1/4W metal film | C58597 |
| R17 | 10R 1% 1/4W metal film | C57437 |
| R19 | 100R 1% 1/4W metal film | C57438 |
| U1 | RECOM R-78E5.0-1.0 5 V switching regulator | C3033024 |
| U2 | 7-pin female header 2.54 mm (receiver socket) | C6684533 |

U2 is a gold-plated Samtec socket, the only 7-pin one found in JLCPCB's library; any 7-pin
2.54 mm female header does the same job if you would rather fit a cheaper one yourself.
Stock changes daily: if a part is out of stock, JLCPCB's BOM step offers alternatives.

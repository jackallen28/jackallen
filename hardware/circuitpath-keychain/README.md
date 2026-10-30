# CircuitPath Keychain (BNTS launch badge)

A programmable USB keychain for the CircuitPath launch. It is an **Arduino-compatible board**
(ATmega32U4, the chip on the Arduino Leonardo / Micro) that plugs straight into a laptop through
its **USB-A plug**, or connects with a cable to its **USB-C socket**. Either one powers it and
programs it from the Arduino IDE. The layout follows the sketch: USB-A tab, USB-C, three 5 mm
LEDs (red / amber / green), two buttons, the circuits, a 7 x 11 SMD LED array, and the BNTS area.

## Status: read this first

| Item | State |
|---|---|
| Schematic (`kicad/circuitpath-keychain.kicad_sch`) | Done. Nets are drawn as labels, so it reads as a netlist, not a tidy drawing. |
| PCB placement (`kicad/circuitpath-keychain.kicad_pcb`) | Done: outline, all 116 parts placed, silkscreen. |
| Schematic vs PCB | Checked: all 345 pads have identical nets (`tools/check_netlists.py`). |
| **PCB routing (copper tracks)** | **NOT done yet.** The board is placed but unrouted, so there are no Gerbers. See "Next step". |
| BOM + placement file for JLCPCB | Done (`fab/`). Placement file is final because routing does not move parts. |
| Tested on hardware | No. Nothing here has been built or powered. |

**Next step:** the board needs routing. I tried to autoroute it with Freerouting (an open-source
tool I would have downloaded from GitHub), but the session's safety check blocked running
downloaded code, so I stopped there. Options: (a) say it is OK and I run Freerouting, (b) route it
yourself in KiCad (Route > Autoroute is not built in; use the interactive router, or export a DSN
to Freerouting on your own machine), or (c) I write a custom router for the LED grid. For a
**quote** you do not need routing: JLCPCB prices PCB and assembly from board size, layer count,
thickness and the BOM.

## What is on the board

| Block | Part | Why |
|---|---|---|
| MCU | ATmega32U4-AU, 16 MHz | Native USB, so no separate USB chip. Shows up as an Arduino Micro / Leonardo. |
| USB-A | Edge fingers on the board tongue | No part to buy. 2.0 mm board. |
| USB-C | G-Switch GT-USB-7051A, vertical | Opening faces up, like the pill in the sketch. 5.1 k resistors on CC1/CC2 so chargers and laptops give 5 V. |
| Power | 2 x 1N5819WS Schottky diodes | Whichever port has power feeds the 5 V rail. Neither port can back-feed the other. |
| ESD | USBLC6-2SC6 | Protects the shared D+ / D- lines. |
| LED array | 77 x 0603 blue LEDs, 2 x MAX7219 | 7 rows x 11 columns. Each MAX7219 sets LED current itself, so no LED resistors. 3 MCU pins (SPI) drive both. |
| Indicators | 3 x 5 mm LED (red, amber, green) + 330 ohm | Amber is pin 13, so `LED_BUILTIN` works. |
| Buttons | 2 x TS-1187A | Pins 3 and 2 (`INPUT_PULLUP`). |
| Buzzer | Murata PKMCS0909E4000-R1 piezo, 9 x 9 x 1 mm | On the back. No driver parts: wired straight to pins 9 and 10, so `tone(9, 440)` plays a note. Drive pin 10 the opposite way too and it is about twice as loud. |
| Programming | 6 bare pads (Tag-Connect TC2030-IDC-NL footprint) | One-off bootloader burn. Shorting pads 5 and 6 with tweezers is a RESET. |

Both USB ports share D+ / D-, so **plug in only one at a time**.

Size: about **118 x 24 mm**. That is longer than the sketch because real 5 mm LEDs, the USB-C and
the MCU are bigger than drawn. The USB-A / USB-C / LEDs / buttons / MCU sit on the left, then the
LED array, then a clear **logo and text zone** (about 16 x 22 mm) before the keyring hole. The zone
has an 8.5 mm silkscreen box for the BNTS logo and two vertical 3 mm text lines ("BNTS" and
"CircuitPath"). The MCU's small support parts, the two MAX7219 chips and the buzzer are on the
**back** (so assembly is both-sided).

## Arduino pin map (board: "Arduino Micro")

| Function | MCU pin | Arduino pin |
|---|---|---|
| Red LED | PC6 | 5 |
| Amber LED | PC7 | 13 (`LED_BUILTIN`) |
| Green LED | PB7 | 11 |
| Button A / B | PD0 / PD1 | 3 / 2 |
| LED array LOAD / CLK / DIN | PB0 / PB1 / PB2 | `SS` / `SCK` / `MOSI` (hardware SPI) |
| Buzzer | PB5 / PB6 | 9 / 10 |
| Spare (not connected) | PD2-5, PD6-7, PB4, PF0-1, PF4-7, PE6 | broken out nowhere |

LED array: columns 1-6 are U2 digits 0-5, columns 7-11 are U3 digits 0-4. Rows are segments A-G
(A is the top row, data bit 6; G is the bottom row, bit 0). `firmware/matrix_test.ino` sweeps a
column then a row (untested on hardware).

## First power-up (once per board)

JLCPCB does not load firmware. A new ATmega32U4 has the Atmel DFU bootloader, and HWB is pulled
low on this board, so it appears as a DFU device at first. Load the Arduino Micro (Caterina)
bootloader once: either flash it over USB with `dfu-programmer`, or use the 6 pads with an Arduino
as ISP and Tools > Burn Bootloader. After that the Arduino IDE uploads over either USB port.
Ask JLCPCB if they can program the chip for you. Try a single board before a batch.

## Ordering at JLCPCB: settings for the quote

* **PCB:** 2 layers, **2.0 mm** thickness, **ENIG** (the USB-A fingers want gold), 1 oz copper,
  min track/space 0.127 mm, min via 0.3 mm. Choose **gold-finger bevel 30 degrees** on the tab if
  offered (otherwise the board edge is a plain cut). Colour is free to choose (purple fits).
* **Panelisation:** the outline is not rectangular, so use "by JLCPCB" with rails, or a custom panel.
* **Assembly:** both sides. Upload `fab/BOM-JLCPCB.csv` and `fab/CPL-JLCPCB.csv`.
* **Not assembled by SMT, solder by hand:** the three 5 mm LEDs (D3-D5). A 5 mm red, amber and
  green LED are about 2 cents each. JLCPCB also has a manual through-hole service if you prefer.
* **Extended-library parts** add a feeder fee each: the ATmega32U4, MAX7219, USB-C, USBLC6, and
  probably the 22 k resistor. Basic parts are cheaper.

## Verify before you order (honest list)

1. **USB-A finger order.** I could not confirm the finger order against a real socket from here.
   I used pin order VBUS, D-, D+, GND with VBUS on the bottom edge when the tip points left, as
   seen from the top. If it is mirrored the board will not enumerate. Check one against a USB-A
   extension cable or socket with a multimeter, and if it is wrong set `USB_A_MIRROR = True` in
   `tools/design.py` and run `./build.sh`. A mirrored plug cannot damage the host (it just
   connects the host's 5 V to this board's ground, with nothing powering the board).
2. **LCSC numbers.** `fab/BOM-full.csv` marks each one. Verified on live LCSC / JLCPCB pages:
   ATmega32U4-AU C44854, MAX7219CWG+T C9964, crystal C13738, USBLC6-2SC6 C7519, TS-1187A C318884,
   blue 0603 LED C2288, 22 ohm C23345, 330 ohm C23138, 1N5819WS C191023, USB-C C2843970, 15 pF C1644.
   **From memory, check in JLCPCB's BOM upload:** 5.1 k (C23186), 10 k (C25804), 22 k (C31850),
   100 nF (C14663), 1 uF (C15849), 10 uF 0805 (C15850). The upload screen flags a wrong match.
3. **Crystal load capacitance.** The C13738 listing is inconsistent (9, 12 or 20 pF in different
   places). I used 15 pF caps. Check the datasheet, since a mismatch only shifts the frequency a
   little, but USB needs about 0.25 percent.
4. **LED colour and brightness.** Blue LEDs drop about 3 V, and the 5 V rail is about 4.7 V after
   the Schottky, which leaves the MAX7219 little headroom. The 22 k ISET resistor targets about
   10-15 mA peak. If it is dim, try red / green LEDs (lower voltage) or a smaller ISET resistor.
   Purple LEDs behave like blue. I did not find a stocked purple 0603 in the checks I could do.
5. **Placement rotation.** JLCPCB's viewer often needs rotation fixes on the TQFP, SOIC, SOT-23,
   crystal and USB-C. Check every part in their preview before paying.
6. **The BNTS logo** is an empty outlined box. Add the real logo in KiCad with Image Converter
   (File > Bitmap to Component Converter, silkscreen layer) and place it in the box.
7. **Buzzer loudness and sound path.** I could not check the PKMCS0909 sound level from here
   (the data I found for Murata's other piezo, the 12 mm PKLCS1212, was inconsistent). It sits on
   the back, so a board lying face-down will muffle it. If you want it louder, the 5 x 5 mm
   MLT-5020 magnetic buzzer (C94598) is the usual alternative but needs a transistor.

## Rebuild

`./build.sh` regenerates everything from `tools/design.py` (needs KiCad 7+ and `pip install kiutils`).
Edit parts, nets and positions in `design.py`, not in the generated files.

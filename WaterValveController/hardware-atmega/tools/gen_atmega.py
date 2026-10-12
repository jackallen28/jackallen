"""Water Valve Controller, standalone ATmega328P board (no Arduino Nano module).

Generates the KiCad 7 project in the folder above this one, using the schematic and board tools of
the Nano carrier boards in ../../hardware/tools:

    python3 tools/gen_atmega.py sch                     # schematic + project, checks the netlist
    python3 tools/gen_atmega.py pcb --jar freerouting-1.9.0.jar [--place-only]
    python3 tools/gen_atmega.py outputs                 # PDF/SVG, BOM, JLCPCB files, images, zip

Run it from the hardware-atmega folder. The circuit is described once, in PARTS below; the
schematic is drawn from it (each pin gets a net label) and the netlist check compares KiCad's
netlist against it.
"""
import csv
import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.abspath(os.path.join(HERE, '..'))
HW_TOOLS = os.path.abspath(os.path.join(HERE, '..', '..', 'hardware', 'tools'))
sys.path.insert(0, HW_TOOLS)
import gen_schematic as gs  # noqa: E402

PROJECT = 'WaterValveController-ATmega'
gs.PROJECT = PROJECT
gs.VARIANT = 'atmega'          # no footprint swaps from the Nano boards' variants

# ---------------------------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------------------------
R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
TB2 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
TB3 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal'
TB4 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal'
XH2 = 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'
XH4 = 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'
SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'

# JLCPCB / LCSC part numbers. The ones marked * come from JLCPCB's basic-parts list rather than a
# page checked for this design; JLCPCB's BOM step shows each part's value, so check those there.
LCSC = {
    'R10k': 'C25804*', 'R1k': 'C21190*', 'R100k': 'C25803*', 'R330': 'C23138*', 'R100': 'C22775*',
    'R1.8k': 'C4177*', 'R3.3k': 'C22978*', 'R10': 'C22859*', 'R5.1k': 'C23186*', 'R15k': 'C22809*',
    'R2k': 'C22975*', 'R20k': 'C4184*',
    'C100n': 'C14663', 'C10n': 'C57112*', 'C22p': 'C1653*', 'C10u': 'C15850*', 'C22u': 'C45783*',
}

# ---------------------------------------------------------------------------------------------
# The circuit: ref -> (symbol, value, footprint, {pin: net or None for not connected}, description,
# LCSC part, x, y, rotation on the schematic). Nets named GND, +5V and +12V get power symbols.
# ---------------------------------------------------------------------------------------------
PARTS = {}


def part(ref, sym, value, fp, pins, desc, lcsc, at, rot=0, in_bom=True):
    PARTS[ref] = dict(sym=sym, value=value, fp=fp, pins=pins, desc=desc, lcsc=lcsc, at=at, rot=rot,
                      in_bom=in_bom)


def R(ref, value, a, b, desc, at, rot=0):
    part(ref, 'Device:R', value, R0603, {'1': a, '2': b}, desc, LCSC['R' + value], at, rot)


def C(ref, value, a, b, desc, at, rot=0, fp=C0603):
    part(ref, 'Device:C', value, fp, {'1': a, '2': b}, desc, LCSC['C' + value.replace('F', '')], at, rot)


# ---- power in: terminal, resettable fuse, main switch, reverse-polarity MOSFET, bulk capacitor
part('J1', 'Connector:Screw_Terminal_01x02', '12V DC IN', TB2, {'1': '12V_IN', '2': 'GND'},
     '12 V DC supply input: 1 = +12 V, 2 = GND. 2-way 5.08 mm screw terminal', 'C474940', (30.48, 50.8))
part('F1', 'Device:Polyfuse', '3A PTC', 'Fuse:Fuse_2920_7451Metric', {'1': '12V_IN', '2': '12V_FUSED'},
     'Resettable fuse, 3 A hold, 5 A trip, 30 V (2920). Resets itself once the fault is cleared',
     'C22446884', (50.8, 40.64), 90)
part('J2', 'Connector:Screw_Terminal_01x03', 'MAIN SWITCH', TB3, {'1': '12V_FUSED', '2': '12V_SW', '3': 'GND'},
     'Main (rocker) switch: 1 = fused 12 V to the switch, 2 = switched 12 V back, 3 = GND for the switch lamp',
     'C474941', (71.12, 53.34))
part('Q3', 'Transistor_FET:IRF7404', 'AO4407A', SOIC8, {'1': '+12V', '2': '+12V', '3': '+12V', '4': 'REV_G',
                                                         '5': '12V_SW', '6': '12V_SW', '7': '12V_SW', '8': '12V_SW'},
     'Reverse-polarity protection: P-MOSFET in the supply, off if the supply is connected backwards '
     '(-30 V, 14 mOhm, SOIC-8)', 'C16072', (101.6, 50.8))
R('R30', '100k', 'REV_G', 'GND', 'Q3 gate to GND: turns Q3 on with the supply the right way round', (101.6, 66.04))
part('C1', 'Device:C_Polarized', '100uF 25V', 'Capacitor_SMD:CP_Elec_6.3x7.7', {'1': '+12V', '2': 'GND'},
     'Bulk capacitor, 12 V rail (damps ringing of the supply leads), SMD electrolytic 6.3 x 7.7 mm',
     'C22383804', (124.46, 50.8))

# ---- 5 V buck regulator (TPS54202H, 500 kHz, 2 A)
part('U1', 'Regulator_Switching:TPS54202DDC', 'TPS54202H', 'Package_TO_SOT_SMD:SOT-23-6',
     {'1': 'GND', '2': 'SW', '3': '+12V', '4': 'FB', '5': 'EN', '6': 'BOOT'},
     '5 V buck regulator, 4.5-28 V in, 2 A, 500 kHz (TPS54202H, SOT-23-6)', 'C527684', (177.8, 50.8))
C('C2', '10uF', '+12V', 'GND', 'U1 input capacitor, 25 V X5R', (144.78, 50.8), fp=C0805)
C('C3', '100nF', '+12V', 'GND', 'U1 input, high-frequency', (154.94, 50.8))
R('R31', '100k', '+12V', 'EN', 'U1 enable divider (top): U1 starts above about 7 V', (147.32, 71.12))
R('R32', '20k', 'EN', 'GND', 'U1 enable divider (bottom)', (154.94, 71.12))
C('C4', '100nF', 'BOOT', 'SW', 'U1 bootstrap capacitor', (200.66, 43.18), 90)
part('L1', 'Device:L', '10uH', 'Inductor_SMD:L_Sunlord_SWPA4020S', {'1': 'SW', '2': '+5V'},
     'U1 inductor, 10 uH, 1.6 A, 4 x 4 x 2 mm shielded', 'C135263', (210.82, 50.8), 90)
R('R33', '15k', '+5V', 'FB', 'U1 feedback (top): 0.596 V x (1 + 15k / 2k) = 5.07 V', (195.58, 68.58))
R('R34', '2k', 'FB', 'GND', 'U1 feedback (bottom)', (203.2, 68.58))
C('C5', '22uF', '+5V', 'GND', 'U1 output capacitor, X5R', (223.52, 58.42), fp=C0805)
C('C6', '22uF', '+5V', 'GND', 'U1 output capacitor, X5R', (233.68, 58.42), fp=C0805)

# ---- USB-C and USB-serial (CH340N), as on an Arduino Nano
part('J9', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
     {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
      'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM',
      'A8': None, 'B8': None, 'S1': 'GND'},
     'USB-C socket for uploading sketches and the serial monitor (USB 2.0)', 'C165948', (264.16, 55.88))
R('R35', '5.1k', 'CC1', 'GND', 'USB-C CC1 pull-down: identifies the board as a USB device', (284.48, 71.12))
R('R36', '5.1k', 'CC2', 'GND', 'USB-C CC2 pull-down', (292.1, 71.12))
part('D3', 'Device:D_Schottky', 'B5819W', 'Diode_SMD:D_SOD-123', {'1': '+5V', '2': 'VBUS'},
     'USB power to the 5 V rail (the board runs from USB alone for programming); blocks 5 V back into '
     'the computer', 'C8598*', (299.72, 40.64), 180)
part('U3', 'Interface_USB:CH340N', 'CH340N', 'Package_SO:SOP-8_3.9x4.9mm_P1.27mm',
     {'1': 'USB_DP', '2': 'USB_DM', '3': 'GND', '4': 'RTS', '5': '+5V', '6': 'CH_TXD', '7': 'CH_RXD', '8': 'V3'},
     'USB to serial converter (as on an Arduino Nano), internal clock', 'C2977777', (325.12, 55.88))
C('C7', '100nF', '+5V', 'GND', 'U3 supply decoupling', (309.88, 76.2))
C('C8', '100nF', 'V3', 'GND', 'U3 internal 3.3 V regulator', (317.5, 76.2))
R('R37', '1k', 'CH_TXD', 'RXD', 'Serial from USB to the ATmega RXD (D0); lets the ESP or a shield drive D0 too',
  (350.52, 50.8), 90)
R('R38', '1k', 'TXD', 'CH_RXD', 'Serial from the ATmega TXD (D1) to USB', (350.52, 60.96), 90)
C('C9', '100nF', 'RTS', 'RESET', 'Auto-reset: the IDE resets the ATmega to start the bootloader', (350.52, 71.12), 90)

# ---- ATmega328P with crystal, reset, decoupling, ICSP, LED on D13
part('U4', 'MCU_Microchip_ATmega:ATmega328P-A', 'ATmega328P-AU', 'Package_QFP:TQFP-32_7x7mm_P0.8mm',
     {'1': None, '2': 'BTN', '3': 'GND', '4': '+5V', '5': 'GND', '6': '+5V', '7': 'XTAL1', '8': 'XTAL2',
      '9': 'LED25', '10': 'LED50', '11': 'LED100', '12': 'VALVE', '13': None, '14': None, '15': 'TX_5V',
      '16': 'ESP_IN', '17': 'SCK', '18': '+5V', '19': None, '20': 'AREF', '21': 'GND', '22': None,
      '23': 'RF1', '24': 'RF2', '25': 'RF3', '26': 'RF4', '27': None, '28': None, '29': 'RESET',
      '30': 'RXD', '31': 'TXD', '32': 'FLOW'},
     'ATmega328P microcontroller (as on an Arduino Uno / Nano), 16 MHz, TQFP-32', 'C14877', (190.5, 142.24))
part('Y1', 'Device:Crystal_GND24', '16MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
     {'1': 'XTAL1', '2': 'GND', '3': 'XTAL2', '4': 'GND'}, '16 MHz crystal, 3.2 x 2.5 mm, 20 pF load',
     'C13738*', (137.16, 147.32), 90)
C('C10', '22pF', 'XTAL1', 'GND', 'Crystal load capacitor', (127.0, 160.02))
C('C11', '22pF', 'XTAL2', 'GND', 'Crystal load capacitor', (147.32, 160.02))
C('C12', '100nF', '+5V', 'GND', 'U4 VCC decoupling (pin 4)', (132.08, 106.68))
C('C13', '100nF', '+5V', 'GND', 'U4 VCC decoupling (pin 6)', (142.24, 106.68))
C('C14', '100nF', '+5V', 'GND', 'U4 AVCC decoupling (pin 18)', (152.4, 106.68))
C('C15', '100nF', 'AREF', 'GND', 'U4 AREF decoupling', (162.56, 106.68))
R('R39', '10k', '+5V', 'RESET', 'Reset pull-up', (236.22, 106.68))
part('D4', 'Diode:1N4148W', '1N4148W', 'Diode_SMD:D_SOD-123', {'1': '+5V', '2': 'RESET'},
     'Reset clamp, as on the Arduino Uno', 'C81598*', (248.92, 106.68), 90)
part('J10', 'Connector_Generic:Conn_02x03_Odd_Even', 'ICSP', 'Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical',
     {'1': 'ESP_IN', '2': '+5V', '3': 'SCK', '4': 'TX_5V', '5': 'RESET', '6': 'GND'},
     'ICSP header for burning the bootloader once (MISO, +5V, SCK, MOSI, RESET, GND). Not fitted: plug a '
     '2 x 3 header in only while programming', '', (269.24, 152.4), in_bom=False)
R('R40', '1k', 'SCK', 'LED_L', 'D13 LED resistor', (236.22, 172.72))
part('D5', 'Device:LED', 'green', 'LED_SMD:LED_0603_1608Metric', {'1': 'GND', '2': 'LED_L'},
     'D13 "L" LED, as on an Arduino: blinks when the bootloader starts', 'C72043*', (248.92, 172.72), 90)

# ---- valve driver (same circuit as the Nano boards)
part('Q1', 'Transistor_FET:IRF7404', 'AO4407A', SOIC8, {'1': '+12V', '2': '+12V', '3': '+12V', '4': 'GATE',
                                                         '5': 'SOL_OUT', '6': 'SOL_OUT', '7': 'SOL_OUT', '8': 'SOL_OUT'},
     'High-side P-MOSFET valve switch (-30 V, -12 A, 14 mOhm, SOIC-8): 0.13 W at 3 A, no heatsink',
     'C16072', (45.72, 116.84))
R('R18', '10k', '+12V', 'GATE', 'Q1 gate pull-up: holds the valve off', (27.94, 116.84))
part('Q2', 'Transistor_FET:2N7002', '2N7002', 'Package_TO_SOT_SMD:SOT-23', {'1': 'DRV', '2': 'GND', '3': 'GATE'},
     'Gate driver for Q1: D8 HIGH switches the valve on', 'C8545', (45.72, 139.7))
R('R19', '100', 'VALVE', 'DRV', 'Q2 gate resistor', (25.4, 139.7), 90)
R('R20', '10k', 'DRV', 'GND', 'Q2 gate pull-down: valve off while the ATmega starts', (33.02, 152.4))
part('D2', 'Diode:SS34', 'SS34', 'Diode_SMD:D_SMA', {'1': 'SOL_OUT', '2': 'GND'},
     'Flyback diode across the valve output (3 A 40 V Schottky)', 'C8678*', (71.12, 124.46), 90)
part('J3', 'Connector:Screw_Terminal_01x04', 'VALVE / FLOW', TB4,
     {'1': 'SOL_OUT', '2': 'GND', '3': '+5V', '4': 'FLOW_IN'},
     'Valve and flow sensor: 1 = valve +, 2 = GND (valve - and sensor black), 3 = +5 V (sensor red), '
     '4 = flow signal (sensor yellow)', 'C2827883', (99.06, 124.46))
C('C16', '100nF', '+5V', 'GND', 'Flow sensor supply decoupling at J3', (83.82, 144.78))
R('R1', '10k', '+5V', 'FLOW_IN', 'Flow signal pull-up (open-collector sensor)', (55.88, 172.72))
R('R2', '1k', 'FLOW_IN', 'FLOW', 'Flow signal series resistor: filter and pin protection', (66.04, 172.72), 90)
C('C17', '10nF', 'FLOW', 'GND', 'Flow signal filter (10 us with R2)', (78.74, 177.8))

# ---- panel: button and LEDs on JST-XH leads
part('J5', 'Connector_Generic:Conn_01x02', 'BUTTON', XH2, {'1': 'BTN', '2': 'GND'},
     'Panel push button (normally open): JST-XH 2-pin', 'C158012', (22.86, 205.74))
R('R3', '10k', '+5V', 'BTN', 'Button pull-up', (40.64, 200.66))
C('C18', '100nF', 'BTN', 'GND', 'Button filter', (48.26, 215.9))
for i, (n, j, r) in enumerate((('25', 'J6', 'R4'), ('50', 'J7', 'R5'), ('100', 'J8', 'R6'))):
    y = 236.22 + i * 15.24
    part(j, 'Connector_Generic:Conn_01x02', f'LED {n}L', XH2, {'1': f'LED{n}_A', '2': 'GND'},
         f'{n} L panel LED: JST-XH 2-pin, 1 = LED + (anode), 2 = LED - (cathode)', 'C158012', (22.86, y))
    R(r, '330', f'LED{n}', f'LED{n}_A', 'LED current limit, about 9 mA', (48.26, y - 2.54), 90)

# ---- ESP32 link
part('J4', 'Connector_Generic:Conn_01x04', 'ESP32', XH4, {'1': '+5V', '2': 'GND', '3': 'TO_ESP', '4': 'FROM_ESP'},
     'ESP32 link: 1 = 5 V, 2 = GND, 3 = data to the ESP (3.3 V), 4 = data from the ESP. JST-XH 4-pin',
     'C144395', (320.04, 210.82))
R('R11', '1.8k', 'TX_5V', 'TO_ESP', 'Divider to the ESP (top): 5 V data to 3.24 V', (289.56, 205.74), 90)
R('R12', '3.3k', 'TO_ESP', 'GND', 'Divider to the ESP (bottom)', (302.26, 220.98))
R('R21', '1k', 'FROM_ESP', 'ESP_IN', 'Series resistor from the ESP into D12', (289.56, 218.44), 90)

# ---- 433 MHz receiver
part('U2', 'WaterValve:RX480E', 'RX480E-4', 'Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical',
     {'1': 'GND', '2': 'RF_5V', '3': 'RX_D0', '4': 'RX_D1', '5': 'RX_D2', '6': 'RX_D3', '7': None},
     'RX480E-4 433 MHz receiver module (learning code), plugged into a 7-pin socket', 'C6684533',
     (373.38, 162.56))
R('R17', '10', '+5V', 'RF_5V', 'Receiver supply filter', (373.38, 127.0), 90)
C('C19', '22uF', 'RF_5V', 'GND', 'Receiver supply filter', (386.08, 134.62), fp=C0805)
C('C20', '100nF', 'RF_5V', 'GND', 'Receiver supply filter', (393.7, 134.62))
for i in range(4):
    y = 152.4 + i * 7.62
    R(f'R{7 + i}', '1k', f'RX_D{i}', f'RF{i + 1}', f'Series resistor, receiver D{i} to A{i}', (337.82, y), 90)
    R(f'R{13 + i}', '100k', f'RF{i + 1}', 'GND', f'Pull-down on A{i}: no floating input', (314.96 - i * 7.62, 187.96))

# ---- mounting holes
for i in range(4):
    part(f'H{i + 1}', 'Mechanical:MountingHole', 'M4', 'MountingHole:MountingHole_4.3mm_M4', {},
         'M4 mounting hole', '', (284.48 + i * 10.16, 243.84), in_bom=False)

POWER = {'GND', '+5V', '+12V'}


# ---------------------------------------------------------------------------------------------
# Schematic
# ---------------------------------------------------------------------------------------------
def pin_dirs(sym):
    """pin number -> list of (x, y, angle) in symbol coordinates (y up)."""
    out = {}

    def walk(node):
        for it in node:
            if isinstance(it, list):
                if it[0] == 'symbol':
                    walk(it)
                elif it[0] == 'pin':
                    at = next(i for i in it if isinstance(i, list) and i[0] == 'at')
                    nb = next(i for i in it if isinstance(i, list) and i[0] == 'number')
                    out.setdefault(nb[1].strip('"'), []).append((float(at[1]), float(at[2]), float(at[3])))
    walk(sym)
    return out


def power_rot(net, d):
    """Rotation of a power symbol whose pin is reached from direction d (unit vector, y down)."""
    dx, dy = d
    if net == 'GND':
        return {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[(dx, dy)]
    return {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[(dx, dy)]


def body_rect(sym):
    """The symbol's body rectangle (x1, y1, x2, y2) in symbol coordinates, or None."""
    found = []

    def walk(node):
        for it in node:
            if isinstance(it, list):
                if it[0] == 'rectangle':
                    st = next(i for i in it if isinstance(i, list) and i[0] == 'start')
                    en = next(i for i in it if isinstance(i, list) and i[0] == 'end')
                    found.append((float(st[1]), float(st[2]), float(en[1]), float(en[2])))
                walk(it)
    walk(sym)
    return max(found, key=lambda r: abs(r[2] - r[0]) * abs(r[3] - r[1])) if found else None


def text_spots(sym, sym_pins, x, y, rot):
    """Positions for the reference and value text that keep clear of the pin labels."""
    pins = [gs.Sch.xform(px, py, x, y, rot, False) for lst in sym_pins.values() for px, py, _a in lst]
    if len(sym_pins) == 2:
        (ax, ay), (bx, by) = pins[0], pins[-1]
        if abs(ax - bx) < 0.01:                     # vertical part: text to the right
            return (x + 2.54, y - 1.27), (x + 2.54, y + 1.27), 'left', 'left'
        return (x, y - 2.54), (x, y + 2.54), 'center', 'center'
    rect = body_rect(sym)
    if rect and rot == 0 and len(sym_pins) > 4:      # ICs and connectors: above the body's corners
        x1, x2 = x + min(rect[0], rect[2]), x + max(rect[0], rect[2])
        top = y - max(rect[1], rect[3])
        return (x1, top - 1.27), (x2, top - 1.27), 'left', 'right'
    return (x + 5.08, y - 1.27), (x + 5.08, y + 1.27), 'left', 'left'


def build_schematic():
    s = gs.Sch()
    for ref, p in PARTS.items():
        if p['sym'] is None:
            continue
        x, y = p['at']
        fields = {'LCSC Part #': p['lcsc'].rstrip('*')} if p['lcsc'] else {}
        sym = s.libsym(p['sym'])
        sym_pins = pin_dirs(sym)
        rot = p['rot']
        ref_at, val_at, rj, vj = text_spots(sym, sym_pins, x, y, rot)
        s.add(p['sym'], ref, p['value'], x, y, rot=rot, fp=p['fp'], ref_at=ref_at, val_at=val_at,
              ref_just=rj, val_just=vj, fields=fields, desc=p['desc'], in_bom=p['in_bom'])
        done = set()
        for num, lst in sym_pins.items():
            for px, py, ang in lst:
                at = gs.Sch.xform(px, py, x, y, rot, False)
                if at in done:
                    continue                          # stacked pins: one stub is enough
                done.add(at)
                net = p['pins'][num]
                if net is None:
                    s.nc(at)
                    continue
                a = math.radians(ang)
                end = gs.Sch.xform(px - 2.54 * math.cos(a), py - 2.54 * math.sin(a), x, y, rot, False)
                d = (round((end[0] - at[0]) / 2.54), round((end[1] - at[1]) / 2.54))
                s.wire(at, end)
                if net in POWER:
                    s.power(net, end, power_rot(net, d))
                else:
                    s.label(net, end, {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d])
    # power flags: these nets are driven only by passive pins
    for net, at in (('+12V', (330.2, 22.86)), ('GND', (345.44, 22.86)), ('+5V', (360.68, 22.86)),
                    ('VBUS', (375.92, 22.86))):
        if net in POWER:
            s.power(net, at, 0 if net != 'GND' else 180)
        else:
            s.label(net, at, 180)
        flag_at = (at[0] + 5.08, at[1])
        s.wire(at, flag_at)
        s.flag(flag_at)

    s.text('POWER IN: RESETTABLE FUSE, MAIN SWITCH, REVERSE-POLARITY MOSFET', (20.32, 30.48), 2, True)
    s.text('5 V BUCK REGULATOR', (142.24, 30.48), 2, True)
    s.text('USB-C AND USB-SERIAL (CH340N)', (254.0, 30.48), 2, True)
    s.text('ATMEGA328P (ARDUINO UNO / NANO PINOUT)', (127.0, 93.98), 2, True)
    s.text('VALVE DRIVER AND FLOW SENSOR', (20.32, 101.6), 2, True)
    s.text('PANEL BUTTON AND LEDS', (20.32, 190.5), 2, True)
    s.text('433 MHZ RECEIVER AND ESP32 LINK', (284.48, 101.6), 2, True)
    s.text('Arduino pins: D0/D1 serial (USB), D2 flow, D4 button, D5-D7 LEDs, D8 valve,\n'
           'D11 data to the ESP, D12 data from the ESP, D13 LED, A0-A3 remote.\n'
           'Same pins as the Nano boards, so WaterValveController.ino runs unchanged.\n'
           'Burn the bootloader once through J10 (ICSP) as "Arduino Uno", then upload over USB.',
           (127.0, 213.36))
    s.text('Off-board wiring: J1 12 V supply; J2 illuminated rocker switch (1 power, 2 load,\n'
           '3 lamp GND); J3 valve (+ to 1, - to 2) and YF-G1 sensor (black 2, red 3, yellow 4);\n'
           'J5 button; J6-J8 plain panel LEDs; J4 ESP32-C3 (GPIO20 RX, GPIO21 TX).',
           (127.0, 241.3))
    title = [
        '(title "Water Valve Controller - standalone ATmega328P")',
        '(date "2026-10-12")',
        '(rev "A1")',
        '(company "Single board, no Arduino Nano module")',
        '(comment 1 "ATmega328P-AU 16 MHz, CH340N USB-C, TPS54202H 5 V buck, AO4407A valve switch")',
        '(comment 2 "Firmware: WaterValveController.ino (unchanged)")',
        '(comment 3 "Pins: D2 flow, D4 button, D5-D7 LEDs, D8 valve, D11/D12 ESP, A0-A3 remote")',
    ]
    return s, title


def write_project():
    s, title = build_schematic()
    with open(os.path.join(PROJ_DIR, PROJECT + '.kicad_sch'), 'w') as f:
        f.write(s.render(title))
    pro_path = os.path.join(PROJ_DIR, PROJECT + '.kicad_pro')
    if not os.path.exists(pro_path):              # keep the board's rules once they are written
        pro = json.load(open('/usr/share/kicad/template/kicad.kicad_pro'))
        pro['meta']['filename'] = PROJECT + '.kicad_pro'
        pro['sheets'] = [[gs.ROOT_UUID, '']]
        with open(pro_path, 'w') as f:
            json.dump(pro, f, indent=2)
    lib = '(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n'
    sym = [x for x in gs.CUSTOM['RX480E']]
    sym[1] = gs.q('RX480E')
    lib += '  ' + gs.dump(sym, 1) + '\n)\n'
    with open(os.path.join(PROJ_DIR, 'WaterValve.kicad_sym'), 'w') as f:
        f.write(lib)
    with open(os.path.join(PROJ_DIR, 'sym-lib-table'), 'w') as f:
        f.write('(sym_lib_table\n  (lib (name "WaterValve")(type "KiCad")(uri "${KIPRJMOD}/WaterValve.kicad_sym")'
                '(options "")(descr "RX480E receiver module"))\n)\n')


def check_netlist():
    """Compares KiCad's netlist of the generated schematic with PARTS."""
    with tempfile.TemporaryDirectory() as d:
        xml = os.path.join(d, 'net.xml')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml,
                        os.path.join(PROJ_DIR, PROJECT + '.kicad_sch')], check=True, capture_output=True)
        root = ET.parse(xml).getroot()
    got = {}
    for n in root.find('nets'):
        nodes = frozenset((x.get('ref'), x.get('pin')) for x in n.findall('node') if not x.get('ref').startswith('#'))
        if nodes:
            got[n.get('name').lstrip('/')] = nodes
    want = {}
    for ref, p in PARTS.items():
        for num, net in (p.get('pins') or {}).items():
            if net is not None:
                want.setdefault(net, set()).add((ref, num))
    bad = 0
    for net, nodes in sorted(want.items()):
        if got.get(net) != frozenset(nodes):
            bad += 1
            print(f'FAIL {net}: want {sorted(nodes)}\n     got  {sorted(got.get(net, []))}')
    for net, nodes in got.items():
        if net not in want and not net.startswith('unconnected-'):
            bad += 1
            print('UNEXPECTED NET', net, sorted(nodes))
    print(f'netlist: {len(want)} nets checked,', 'PASS' if not bad else f'{bad} problems')
    return bad == 0


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'sch'
    if cmd == 'sch':
        write_project()
        sys.exit(0 if check_netlist() else 1)
    import atmega_board                                     # noqa: E402  (board, outputs)
    atmega_board.main(cmd, sys.argv[2:])

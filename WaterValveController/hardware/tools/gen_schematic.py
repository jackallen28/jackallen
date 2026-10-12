"""Generates the Water Valve Controller KiCad 7 project.

Usage: python3 gen_schematic.py OUT_DIR [tht|smd]

The schematic is the same for both boards; the variant only changes footprints and part values.
"""
import json
import math
import os
import sys
import uuid as uuidlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, dump  # noqa: E402

PROJECT = "WaterValveController"
VARIANT = 'tht'
LIBDIR = "/usr/share/kicad/symbols/"
NS = uuidlib.UUID("6b1d8f9e-3c0a-4c55-9e2e-5a7d2b9c1f00")
_uuid_counter = [0]


def uid(tag=None):
    """Deterministic UUIDs so regenerating gives a stable file."""
    _uuid_counter[0] += 1
    return str(uuidlib.uuid5(NS, f"{tag or ''}#{_uuid_counter[0]}"))


ROOT_UUID = str(uuidlib.uuid5(NS, "root-sheet"))


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def fmt(v):
    v = round(v, 4)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ('%.4f' % v).rstrip('0').rstrip('.')


# ---------------------------------------------------------------------------
# Library symbols
# ---------------------------------------------------------------------------
def load_lib_symbol(lib, name):
    tree = parse(open(LIBDIR + lib + '.kicad_sym').read())[0]
    syms = {it[1].strip('"'): it for it in tree if isinstance(it, list) and it[0] == 'symbol'}
    sym = syms[name]
    ext = [i for i in sym if isinstance(i, list) and i[0] == 'extends']
    if ext:
        # Flatten a derived symbol: parent graphics/pins + child properties.
        parent = syms[ext[0][1].strip('"')]
        pname = parent[1].strip('"')
        child_props = [i for i in sym if isinstance(i, list) and i[0] == 'property']
        flat = [parent[0], parent[1]]
        for it in parent[2:]:
            if isinstance(it, list) and it[0] == 'property':
                continue
            flat.append(it)
        # insert child properties after the header flags
        idx = next(i for i, it in enumerate(flat) if isinstance(it, list) and it[0] == 'symbol')
        flat[idx:idx] = child_props
        # rename unit sub-symbols
        for it in flat:
            if isinstance(it, list) and it[0] == 'symbol':
                it[1] = it[1].replace(pname, name)
        sym = flat
    sym = [x for x in sym]
    sym[1] = q(f"{lib}:{name}")
    return sym


def custom_symbol(name, ref, value, body, pins, pin_names_hide=False, extra_graphics=(), pin_numbers_hide=True):
    """body: (x1, y1, x2, y2) rectangle in lib coords (y up).
    pins: list of (number, name, type, x, y, angle, length)."""
    s = [f'(symbol {q("WaterValve:" + name)}']
    s.append('(pin_numbers hide)' if pin_numbers_hide else '')
    s.append(f'(pin_names (offset 0.762){" hide" if pin_names_hide else ""})')
    s.append('(in_bom yes) (on_board yes)')
    x1, y1, x2, y2 = body
    s.append(f'(property "Reference" {q(ref)} (at {fmt(x1)} {fmt(y1 + 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))')
    s.append(f'(property "Value" {q(value)} (at {fmt(x1)} {fmt(y2 - 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left top)))')
    s.append('(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    s.append('(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    s.append(f'(symbol {q(name + "_0_1")}')
    s.append(f'(rectangle (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) (stroke (width 0.254) (type default)) (fill (type background)))')
    for g in extra_graphics:
        s.append(g)
    s.append(')')
    s.append(f'(symbol {q(name + "_1_1")}')
    for num, pname, ptype, x, y, ang, ln in pins:
        s.append(f'(pin {ptype} line (at {fmt(x)} {fmt(y)} {fmt(ang)}) (length {fmt(ln)}) '
                 f'(name {q(pname)} (effects (font (size 1.27 1.27)))) '
                 f'(number {q(num)} (effects (font (size 1.27 1.27)))))')
    s.append(')')
    s.append(')')
    return parse(' '.join(s))[0]


CUSTOM = {
    'Solenoid_Valve': custom_symbol(
        'Solenoid_Valve', 'SV', 'Solenoid_Valve', (-2.54, 2.54, 2.54, -2.54),
        [('1', '+', 'passive', 0, 5.08, 270, 2.54),
         ('2', '-', 'passive', 0, -5.08, 90, 2.54)],
        pin_names_hide=True,
        extra_graphics=[
            '(arc (start 0 2.54) (mid 0.635 1.905) (end 0 1.27) (stroke (width 0.254) (type default)) (fill (type none)))',
            '(arc (start 0 1.27) (mid 0.635 0.635) (end 0 0) (stroke (width 0.254) (type default)) (fill (type none)))',
            '(arc (start 0 0) (mid 0.635 -0.635) (end 0 -1.27) (stroke (width 0.254) (type default)) (fill (type none)))',
            '(arc (start 0 -1.27) (mid 0.635 -1.905) (end 0 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))',
            '(text "+" (at -1.524 3.81 0) (effects (font (size 1.27 1.27))))',
            '(text "-" (at -1.524 -3.81 0) (effects (font (size 1.27 1.27))))',
        ]),
    'YF-G1_Flow_Sensor': custom_symbol(
        'YF-G1_Flow_Sensor', 'FS', 'YF-G1', (-10.16, 5.08, 7.62, -5.08),
        [('1', 'VCC-red', 'power_in', 10.16, 2.54, 180, 2.54),
         ('2', 'SIG-yellow', 'open_collector', 10.16, 0, 180, 2.54),
         ('3', 'GND-black', 'power_in', 10.16, -2.54, 180, 2.54)]),
    'Rocker_Switch_LED': custom_symbol(
        'Rocker_Switch_LED', 'SW', 'Rocker_Switch_LED', (-10.16, 5.08, 7.62, -5.08),
        [('1', 'POWER', 'passive', 10.16, 2.54, 180, 2.54),
         ('2', 'LOAD', 'passive', 10.16, 0, 180, 2.54),
         ('3', 'LAMP-GND', 'passive', 10.16, -2.54, 180, 2.54)],
        extra_graphics=['(text "rocker + lamp" (at -8.255 0 900) (effects (font (size 1 1))))']),
    'RX480E': custom_symbol(
        'RX480E', 'U', 'RX480E', (-7.62, 7.62, 7.62, -7.62),
        [('1', 'GND', 'power_in', 0, -10.16, 90, 2.54),
         ('2', '+V', 'power_in', 0, 10.16, 270, 2.54),
         ('3', 'D0', 'output', -10.16, 5.08, 0, 2.54),
         ('4', 'D1', 'output', -10.16, 2.54, 0, 2.54),
         ('5', 'D2', 'output', -10.16, 0, 0, 2.54),
         ('6', 'D3', 'output', -10.16, -2.54, 0, 2.54),
         ('7', 'VT', 'output', -10.16, -5.08, 0, 2.54)],
        pin_numbers_hide=False,
        extra_graphics=['(text "433 MHz" (at 2.794 0 900) (effects (font (size 1 1))))']),
}


def pins_of(sym):
    out = {}

    def walk(node):
        for it in node:
            if isinstance(it, list):
                if it[0] == 'symbol':
                    walk(it)
                elif it[0] == 'pin':
                    at = next(i for i in it if isinstance(i, list) and i[0] == 'at')
                    nb = next(i for i in it if isinstance(i, list) and i[0] == 'number')
                    nm = next(i for i in it if isinstance(i, list) and i[0] == 'name')
                    out.setdefault(nb[1].strip('"'), []).append(
                        (float(at[1]), float(at[2]), nm[1].strip('"'), it[1]))
    walk(sym)
    return out


# ---------------------------------------------------------------------------
# Schematic builder
# ---------------------------------------------------------------------------
class Sch:
    def __init__(self):
        self.lib = {}       # lib_id -> sexp list
        self.items = []     # text chunks
        self.parts = []     # dicts for BOM / checks
        self.pwr_n = 0
        self.flag_n = 0

    def libsym(self, lib_id):
        if lib_id not in self.lib:
            lib, name = lib_id.split(':')
            if lib == 'WaterValve':
                self.lib[lib_id] = CUSTOM[name]
            else:
                self.lib[lib_id] = load_lib_symbol(lib, name)
        return self.lib[lib_id]

    @staticmethod
    def xform(px, py, X, Y, rot, mirror):
        sx, sy = px, -py
        if mirror:
            sx = -sx
        t = math.radians(rot)
        c, s = round(math.cos(t)), round(math.sin(t))
        return (round(X + sx * c + sy * s, 4), round(Y - sx * s + sy * c, 4))

    def add(self, lib_id, ref, value, x, y, rot=0, mirror=False, fp='', ref_at=None, val_at=None,
            ref_just='left', val_just='left', hide_value=False, on_board=True, in_bom=True,
            fields=None, desc=''):
        if VARIANT == 'tht' and ref in THT_UPRIGHT:
            fp = FP_R_UPRIGHT
        if VARIANT == 'smd':
            lib_id = SMD_SYMBOL.get(ref, lib_id)
            fp = SMD_FP.get(fp, fp)
            if ref in SMD_PART:
                fp, value, desc = SMD_PART[ref]
            desc = SMD_DESC.get(desc, desc)
        sym = self.libsym(lib_id)
        pins = pins_of(sym)
        u = uid(ref)
        if ref_at is None:
            ref_at = (x + 2.54, y - 1.27)
        if val_at is None:
            val_at = (x + 2.54, y + 1.27)
        is_power = ref.startswith('#')

        fang = 90 if rot in (90, 270) else 0
        if rot == 90 or (rot == 180 and not mirror):
            # KiCad flips text that would read upside down, which mirrors its justification
            swap = {'left': 'right', 'right': 'left'}
            ref_just, val_just = swap.get(ref_just, ref_just), swap.get(val_just, val_just)

        def prop(name, val, at, just, hide=False):
            j = '' if just == 'center' else f' (justify {just})'
            h = ' hide' if hide else ''
            return (f'    (property {q(name)} {q(val)} (at {fmt(at[0])} {fmt(at[1])} {fang})\n'
                    f'      (effects (font (size 1.27 1.27)){j}{h})\n    )\n')

        mir = ' (mirror y)' if mirror else ''
        out = (f'  (symbol (lib_id {q(lib_id)}) (at {fmt(x)} {fmt(y)} {fmt(rot)}){mir} (unit 1)\n'
               f'    (in_bom {"yes" if in_bom else "no"}) (on_board {"yes" if on_board else "no"}) (dnp no)\n'
               f'    (uuid {u})\n')
        out += prop('Reference', ref, ref_at, ref_just, hide=is_power)
        out += prop('Value', value, val_at, val_just, hide=hide_value)
        out += prop('Footprint', fp, (x, y), 'center', hide=True)
        out += prop('Datasheet', '~' if not is_power else '', (x, y), 'center', hide=True)
        for k, v in (fields or {}).items():
            out += prop(k, v, (x, y), 'center', hide=True)
        for num in pins:
            out += f'    (pin {q(num)} (uuid {uid(ref + num)}))\n'
        out += (f'    (instances\n      (project {q(PROJECT)}\n        (path {q("/" + ROOT_UUID)}\n'
                f'          (reference {q(ref)}) (unit 1)\n        )\n      )\n    )\n  )\n')
        self.items.append(out)
        pinpos = {}
        for num, lst in pins.items():
            px, py, pname, ptype = lst[0]
            pinpos[num] = self.xform(px, py, x, y, rot, mirror)
            pinpos.setdefault(pname, pinpos[num])
        part = dict(ref=ref, value=value, lib_id=lib_id, fp=fp, pins=pinpos, on_board=on_board,
                    in_bom=in_bom, desc=desc, fields=fields or {})
        self.parts.append(part)
        return part

    def power(self, name, at, rot=0, show=True):
        self.pwr_n += 1
        x, y = at
        off = 3.81 if name != 'GND' else 3.81
        if rot == 0:
            val_at, just = ((x, y - off) if name != 'GND' else (x, y + off)), 'center'
        elif rot == 90:   # pointing left
            val_at, just = (x - off, y), 'right'
        elif rot == 270:  # pointing right (or left for GND)
            val_at, just = (x + off, y), 'left'
        else:
            val_at, just = (x, y + off), 'center'
        if name == 'GND' and rot == 270:
            val_at, just = (x - off - 0.5, y), 'right'
        if name == 'GND' and rot == 90:
            val_at, just = (x + off + 0.5, y), 'left'
        return self.add(f'power:{name}', f'#PWR{self.pwr_n:02d}', name, x, y, rot,
                        ref_at=(x, y), val_at=val_at, val_just=just,
                        hide_value=(name == 'GND' and not show))

    def flag(self, at, rot=0):
        self.flag_n += 1
        x, y = at
        val_at = (x, y - 3.81) if rot == 0 else ((x - 3.81, y) if rot == 90 else (x + 3.81, y))
        just = 'center' if rot == 0 else ('right' if rot == 90 else 'left')
        return self.add('power:PWR_FLAG', f'#FLG{self.flag_n:02d}', 'PWR_FLAG', x, y, rot,
                        ref_at=(x, y), val_at=val_at, val_just=just)

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            self.items.append(
                f'  (wire (pts (xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])}))\n'
                f'    (stroke (width 0) (type default))\n    (uuid {uid("w")})\n  )\n')

    def junction(self, at):
        self.items.append(f'  (junction (at {fmt(at[0])} {fmt(at[1])}) (diameter 0) (color 0 0 0 0)\n'
                          f'    (uuid {uid("j")})\n  )\n')

    def nc(self, at):
        self.items.append(f'  (no_connect (at {fmt(at[0])} {fmt(at[1])}) (uuid {uid("nc")}))\n')

    def label(self, name, at, angle=0):
        just = {0: 'left bottom', 180: 'right bottom', 90: 'left bottom', 270: 'right bottom'}[angle]
        self.items.append(f'  (label {q(name)} (at {fmt(at[0])} {fmt(at[1])} {angle}) (fields_autoplaced)\n'
                          f'    (effects (font (size 1.27 1.27)) (justify {just}))\n'
                          f'    (uuid {uid("l")})\n  )\n')

    def text(self, s, at, size=1.27, bold=False):
        b = ' bold' if bold else ''
        v = 'top' if '\n' in s else 'bottom'
        self.items.append(f'  (text {q(s)} (at {fmt(at[0])} {fmt(at[1])} 0)\n'
                          f'    (effects (font (size {size} {size}){b}) (justify left {v}))\n'
                          f'    (uuid {uid("t")})\n  )\n')

    def dashed_box(self, x1, y1, x2, y2):
        self.items.append(
            f'  (polyline (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}) '
            f'(xy {fmt(x1)} {fmt(y2)}) (xy {fmt(x1)} {fmt(y1)}))\n'
            f'    (stroke (width 0) (type dash))\n    (uuid {uid("pl")})\n  )\n')

    def render(self, title_block):
        libs = '\n'.join('    ' + dump(v, 2) for v in self.lib.values())
        tb = ''.join(f'    {line}\n' for line in title_block)
        return (f'(kicad_sch (version 20230121) (generator eeschema)\n\n'
                f'  (uuid {ROOT_UUID})\n\n  (paper "A3")\n\n'
                f'  (title_block\n{tb}  )\n\n'
                f'  (lib_symbols\n{libs}\n  )\n\n'
                + ''.join(self.items) +
                '\n  (sheet_instances\n    (path "/" (page "1"))\n  )\n)\n')


# ---------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------
# Through-hole board. Resistors lie flat (7.62 mm pitch) so most of them fit under the Nano, which
# stands on female headers; the rest stand upright.
FP_R = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'
FP_R_UPRIGHT = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'
THT_UPRIGHT = ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R17', 'R18', 'R19', 'R20')
FP_C = 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm'
FP_CP10 = 'Capacitor_THT:CP_Radial_D10.0mm_P5.00mm'
FP_CP6 = 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
FP_CP5 = 'Capacitor_THT:CP_Radial_D5.0mm_P2.00mm'
FP_D = 'Diode_THT:D_DO-201AD_P5.08mm_Vertical_KathodeUp'
FP_TB2 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
FP_TB3 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal'
FP_TB4 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal'
FP_XH2 = 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'
FP_XH4 = 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'
# Keystone 3557-2 "2 in 1" holder for standard ATO/ATC blade fuses (made by gen_pcb.py)
FP_FUSE = 'WaterValve:Fuseholder_Blade_ATO_Keystone_3557-2'
FP_TO220 = 'Package_TO_SOT_THT:TO-220-3_Vertical'
FP_TO92 = 'Package_TO_SOT_THT:TO-92_Inline_Wide'
# Arduino_Nano with a courtyard round the pin rows only: low parts fit under a socketed Nano.
FP_NANO = 'WaterValve:Arduino_Nano_Socketed'
FP_SOCK7 = 'Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical'
FP_HOLE = 'MountingHole:MountingHole_4.3mm_M4'

# Mixed SMD + THT board: SMD wherever it is smaller and just as robust (resistors, ceramic capacitors,
# diodes, MOSFETs). Parts that take mechanical load, or are no smaller in SMD, stay through-hole: screw
# terminals, JST connectors, the receiver socket, the regulator (TO-220 / R-78E SIP), the fuse holder,
# the electrolytic capacitors (radial cans are smaller than SMD ones) and the Nano.
SMD_FP = {
    FP_R: 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder',
    FP_R_UPRIGHT: 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder',
    FP_C: 'Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder',
}
SMD_PART = {
    'D1': ('Diode_SMD:D_SMC', 'S3M', 'Reverse-polarity crowbar (3 A 1000 V, SMD 1N5408): conducts and blows F1 '
                                    'if the supply is reversed'),
    'D2': ('Diode_SMD:D_SMC', 'S3M', 'Flyback diode across the valve output (3 A 1000 V, SMD 1N5408)'),
    'Q1': ('Package_TO_SOT_SMD:TO-252-2', 'IRFR5305', 'High-side P-MOSFET valve switch (DPAK, -55 V, -31 A, 65 mOhm)'),
    'Q2': ('Package_TO_SOT_SMD:SOT-23', '2N7002', 'Logic-level N-MOSFET that drives the Q1 gate'),
}
SMD_SYMBOL = {'Q2': 'Transistor_FET:2N7002'}   # IRFR5305 (DPAK) has the IRF9540N pin order: G, D, S
SMD_DESC = {}


def build():
    s = Sch()

    # ======================= POWER ==========================================
    s.text('POWER IN: BLADE FUSE, MAIN SWITCH, REVERSE-POLARITY CROWBAR, 5 V REGULATOR', (20.32, 33.02), 2, True)
    j1 = s.add('Connector:Screw_Terminal_01x02', 'J1', '12V DC IN', 30.48, 50.8, mirror=True, fp=FP_TB2,
               ref_at=(27.94, 45.72), val_at=(27.94, 58.42), ref_just='center', val_just='center',
               desc='12 V DC supply input: 1 = +12 V, 2 = GND. 2-way 5.08 mm screw terminal')
    f1 = s.add('Device:Fuse', 'F1', '2A blade (ATO)', 50.8, 50.8, rot=90, fp=FP_FUSE,
               ref_at=(50.8, 46.99), val_at=(50.8, 54.61), ref_just='center', val_just='center',
               desc='PCB holder for standard ATO/ATC blade fuses (Keystone 3557-2) + 2 A blade fuse')
    s.wire(j1['pins']['1'], (40.64, 50.8), f1['pins']['1'])
    s.label('12V_IN', (40.64, 50.8))
    # GND return from J1 pin 2
    gx = 38.1
    s.wire(j1['pins']['2'], (gx, 53.34), (gx, 60.96))
    s.wire((gx, 60.96), (gx, 66.04))
    s.power('GND', (gx, 66.04), show=False)
    s.flag((gx, 60.96), rot=270)
    # Fused 12 V: crowbar diode, then out to the main switch
    s.wire(f1['pins']['2'], (58.42, 50.8), (71.12, 50.8), (76.2, 50.8), (81.28, 50.8))
    s.label('12V_FUSED', (58.42, 50.8))
    s.flag((76.2, 50.8))
    d1 = s.add('Device:D', 'D1', '1N5408', 71.12, 57.15, rot=270, fp=FP_D,
               ref_at=(68.58, 55.88), val_at=(68.58, 58.42), ref_just='right', val_just='right',
               desc='Reverse-polarity crowbar: conducts and blows F1 if the supply is reversed')
    s.junction((71.12, 50.8))
    s.junction((76.2, 50.8))
    s.wire((71.12, 50.8), d1['pins']['K'])
    s.wire(d1['pins']['A'], (71.12, 66.04))
    s.power('GND', (71.12, 66.04), show=False)
    j2 = s.add('Connector:Screw_Terminal_01x03', 'J2', 'MAIN SWITCH', 86.36, 53.34, fp=FP_TB3,
               ref_at=(88.9, 46.99), val_at=(88.9, 59.69), ref_just='center', val_just='center',
               desc='Main (rocker) switch: 1 = fused 12 V to the switch, 2 = switched 12 V back, 3 = GND for '
                    'the switch lamp')
    Q = j2['pins']
    s.wire(Q['2'], (76.2, Q['2'][1]), (76.2, 71.12), (76.2, 81.28))
    s.flag((76.2, 71.12), rot=90)
    s.junction((76.2, 71.12))
    s.wire(Q['3'], (78.74, Q['3'][1]), (78.74, 66.04))
    s.power('GND', (78.74, 66.04), show=False)
    # Switched 12 V: bulk capacitor, regulator
    bus = 81.28
    xs = dict(p12=81.28, c1=86.36, c2=101.6, u1=116.84, c3=132.08, c4=144.78, p5=154.94)
    u1 = s.add('Regulator_Linear:L7805', 'U1', 'R-78E5.0-1.0 or L7805', xs['u1'], bus, fp=FP_TO220,
               ref_at=(xs['u1'], 74.93), val_at=(xs['u1'], 77.47), ref_just='center', val_just='center',
               desc='5 V regulator, TO-220 pinout IN-GND-OUT: R-78E5.0-1.0 switcher (recommended, runs cool), '
                    'or L7805 with a heatsink')
    c1 = s.add('Device:C_Polarized', 'C1', '470uF 25V', xs['c1'], 87.63, fp=FP_CP10,
               desc='Bulk capacitor, 12 V rail, 105 C electrolytic')
    c2 = s.add('Device:C', 'C2', '100nF', xs['c2'], 87.63, fp=FP_C, desc='Ceramic, 12 V rail at U1 input')
    c3 = s.add('Device:C', 'C3', '100nF', xs['c3'], 87.63, fp=FP_C, desc='Ceramic, 5 V rail at U1 output')
    c4 = s.add('Device:C_Polarized', 'C4', '100uF 16V', xs['c4'], 87.63, fp=FP_CP6, desc='Electrolytic, 5 V rail')
    s.wire((76.2, bus), (xs['p12'], bus), (xs['c1'], bus), (xs['c2'], bus), u1['pins']['IN'])
    s.power('+12V', (xs['p12'], bus))
    s.wire(u1['pins']['OUT'], (xs['c3'], bus), (xs['c4'], bus), (xs['p5'], bus))
    s.power('+5V', (xs['p5'], bus))
    for k, c in (('c1', c1), ('c2', c2), ('c3', c3), ('c4', c4)):
        s.junction((xs[k], bus))
        s.wire((xs[k], bus), c['pins']['1'])
    for p in (c1['pins']['2'], c2['pins']['2'], c3['pins']['2'], c4['pins']['2'], u1['pins']['GND']):
        s.wire(p, (p[0], 96.52))
        s.power('GND', (p[0], 96.52), show=False)
    s.junction((xs['p12'], bus))
    s.text('F1 + D1: if the supply is connected backwards, D1 conducts and blows F1 (the fuse comes before\n'
           'the main switch, so this works with the switch off too). J2 goes to the illuminated rocker switch;\n'
           'without a switch, link J2 pins 1 and 2. U1: the ESP32-C3 Wi-Fi peaks take the 5 V load to about\n'
           '0.5 A. Use a pin-compatible switching regulator (R-78E5.0-1.0), or an L7805 on a heatsink.',
           (20.32, 102.87))

    # ======================= VALVE DRIVER + VALVE/FLOW TERMINAL ==============
    s.text('VALVE DRIVER (high-side P-MOSFET) AND VALVE / FLOW SENSOR TERMINAL', (20.32, 119.38), 2, True)
    q1 = s.add('Transistor_FET:IRF9540N', 'Q1', 'IRF9540N', 68.58, 134.62, rot=180, mirror=True, fp=FP_TO220,
               ref_at=(74.93, 133.35), val_at=(74.93, 135.89),
               desc='High-side P-MOSFET valve switch (-100 V, -23 A, TO-220; no heatsink needed below 3 A)')
    G, S_, D_ = q1['pins']['G'], q1['pins']['S'], q1['pins']['D']
    s.wire(S_, (S_[0], 124.46))
    s.power('+12V', (S_[0], 124.46))
    r18 = s.add('Device:R', 'R18', '10k', 58.42, 130.81, fp=FP_R,
                desc='Q1 gate pull-up: the valve is off unless Q2 pulls the gate down')
    s.wire(r18['pins']['1'], (58.42, 124.46), (S_[0], 124.46))
    s.junction((S_[0], 124.46))
    gate = r18['pins']['2']
    s.wire(gate, G)
    q2 = s.add('Transistor_FET:2N7000', 'Q2', '2N7000', 55.88, 147.32, fp=FP_TO92,
               ref_at=(60.96, 146.05), val_at=(60.96, 148.59),
               desc='Logic-level N-MOSFET that drives the Q1 gate from D8')
    s.wire(q2['pins']['D'], gate)
    s.junction(gate)
    s.wire(q2['pins']['S'], (q2['pins']['S'][0], 157.48))
    s.power('GND', (q2['pins']['S'][0], 157.48), show=False)
    r19 = s.add('Device:R', 'R19', '100', 45.72, 147.32, rot=90, fp=FP_R,
                ref_at=(45.72, 144.78), val_at=(45.72, 149.86), ref_just='center', val_just='center',
                desc='Q2 gate resistor')
    s.wire(r19['pins']['2'], q2['pins']['G'])
    r20 = s.add('Device:R', 'R20', '10k', 49.53, 151.13, fp=FP_R, ref_at=(50.8, 152.4), val_at=(50.8, 154.94),
                desc='Q2 gate pull-down: the valve stays off while the Nano starts')
    s.junction(r19['pins']['2'])
    s.wire(r20['pins']['2'], (49.53, 157.48))
    s.power('GND', (49.53, 157.48), show=False)
    s.wire(r19['pins']['1'], (36.83, 147.32))
    s.label('VALVE', (36.83, 147.32), 180)
    d2 = s.add('Device:D', 'D2', '1N5408', 78.74, 146.05, rot=270, fp=FP_D,
               ref_at=(76.2, 144.78), val_at=(76.2, 147.32), ref_just='right', val_just='right',
               desc='Flyback diode across the valve output: clamps the switch-off spike')
    s.wire(D_, (D_[0], 142.24), (78.74, 142.24), (86.36, 142.24), (96.52, 142.24))
    s.junction((78.74, 142.24))
    s.wire((78.74, 142.24), d2['pins']['K'])
    s.label('SOL_OUT', (86.36, 142.24))
    s.wire(d2['pins']['A'], (78.74, 157.48))
    s.power('GND', (78.74, 157.48), show=False)
    j3 = s.add('Connector:Screw_Terminal_01x04', 'J3', 'VALVE / FLOW', 101.6, 144.78, fp=FP_TB4,
               ref_at=(104.14, 137.16), val_at=(104.14, 153.67), ref_just='center', val_just='center',
               desc='1 = valve + (switched 12 V), 2 = GND (valve - and sensor black), 3 = +5V (sensor red), '
                    '4 = sensor signal (yellow). 4-way 5.08 mm screw terminal')
    Q = j3['pins']
    s.wire(Q['2'], (88.9, Q['2'][1]))
    s.power('GND', (88.9, Q['2'][1]), rot=270, show=False)
    s.wire(Q['3'], (88.9, Q['3'][1]))
    s.power('+5V', (88.9, Q['3'][1]), rot=90)
    s.wire(Q['4'], (91.44, Q['4'][1]))
    s.label('FLOW_IN', (91.44, Q['4'][1]), 180)
    c6 = s.add('Device:C', 'C6', '100nF', 116.84, 146.05, fp=FP_C, desc='Sensor supply decoupling, at J3')
    s.power('+5V', c6['pins']['1'])
    s.power('GND', c6['pins']['2'], show=False)
    s.text('D8 HIGH: Q2 pulls the Q1 gate low and the valve gets 12 V.\n'
           'R20 keeps the valve off while the Nano starts. D2 clamps the\n'
           'switch-off spike right at the terminal.', (121.92, 128.27))

    # ======================= FLOW SENSOR INPUT ===============================
    s.text('FLOW SENSOR INPUT (YF-G1, NPN open collector)', (20.32, 165.1), 2, True)
    node_in = (30.48, 180.34)
    s.wire((22.86, node_in[1]), node_in)
    s.label('FLOW_IN', (22.86, node_in[1]), 180)
    r1 = s.add('Device:R', 'R1', '10k', 30.48, 175.26, fp=FP_R, desc='Flow signal pull-up')
    s.power('+5V', r1['pins']['1'])
    s.wire(r1['pins']['2'], node_in)
    r2 = s.add('Device:R', 'R2', '1k', 39.37, node_in[1], rot=90, fp=FP_R,
               ref_at=(39.37, node_in[1] - 2.54), val_at=(39.37, node_in[1] + 2.54), ref_just='center',
               val_just='center', desc='Flow signal series resistor (RC filter / pin protection)')
    s.wire(node_in, r2['pins']['1'])
    s.junction(node_in)
    node_f = (48.26, node_in[1])
    c5 = s.add('Device:C', 'C5', '10nF', 48.26, 184.15, fp=FP_C, desc='Flow signal filter capacitor')
    s.wire(r2['pins']['2'], node_f, (55.88, node_f[1]))
    s.junction(node_f)
    s.wire(c5['pins']['2'], (48.26, 189.23))
    s.power('GND', (48.26, 189.23), show=False)
    s.label('FLOW', (55.88, node_f[1]), 0)
    s.text('R2 + C5 filter fast spikes (time constant 10 us);\nthe firmware also ignores pulses < 2 ms apart.',
           (66.04, 177.8))

    # ======================= ARDUINO NANO ====================================
    s.text('CONTROLLER', (190.5, 91.44), 2, True)
    NX, NY = 215.9, 127
    a1 = s.add('MCU_Module:Arduino_Nano_v3.x', 'A1', 'Arduino Nano', NX, NY, fp=FP_NANO,
               ref_at=(NX - 10.16, NY - 23.495), val_at=(NX + 5.08, NY + 24.13),
               desc='Arduino Nano v3 (ATmega328P), on 2 x 15 female headers')
    P = a1['pins']
    used_left = {'D2': 'FLOW', 'D4': 'BTN', 'D5': 'LED25', 'D6': 'LED50', 'D7': 'LED100',
                 'D8': 'VALVE', 'D11': 'TX_5V', 'D12': 'ESP_IN'}
    used_right = {'A0': 'RF1', 'A1': 'RF2', 'A2': 'RF3', 'A3': 'RF4'}
    for pin, net in used_left.items():
        p = P[pin]
        s.wire(p, (p[0] - 5.08, p[1]))
        s.label(net, (p[0] - 5.08, p[1]), 180)
    for pin, net in used_right.items():
        p = P[pin]
        s.wire(p, (p[0] + 5.08, p[1]))
        s.label(net, (p[0] + 5.08, p[1]), 0)
    for num in ('1', '2', '6', '12', '13', '16', '3', '28', '18', '23', '24', '25', '26', '17', '30'):
        s.nc(P[num])
    s.wire(P['27'], (P['27'][0], NY - 30.48))
    s.power('+5V', (P['27'][0], NY - 30.48))
    g1, g2 = P['4'], P['29']
    gy = NY + 30.48
    s.wire(g1, (g1[0], gy))
    s.wire(g2, (g2[0], gy))
    s.wire((g1[0], gy), (g2[0], gy))
    s.power('GND', (g1[0], gy), show=False)
    c10 = s.add('Device:C', 'C10', '100nF', 238.76, 101.6, fp=FP_C, desc='Decoupling at the Nano 5V pin')
    s.power('+5V', c10['pins']['1'])
    s.power('GND', c10['pins']['2'], show=False)
    s.text('D11 sends status to the ESP; D12 receives from it\n(ESP control, for later). Nano is powered through\nits 5V pin (VIN unused).', (190.5, 163.83))

    # ======================= REMOTE RECEIVER =================================
    s.text('REMOTE RECEIVER (RX480E 433 MHz module, plugs into the board)', (279.4, 30.48), 2, True)
    u2 = s.add('WaterValve:RX480E', 'U2', 'RX480E-4', 398.78, 63.5, fp=FP_SOCK7,
               ref_at=(397.51, 52.07), val_at=(391.16, 76.2), ref_just='right', val_just='right',
               desc='RX480E-4 receiver module on a 1x7 female header. Pins: 1 GND, 2 +V, 3-6 D0-D3, 7 VT')
    U = u2['pins']
    # Supply filter: 10 R + 47 uF + 100 nF keeps valve and regulator noise off the receiver
    s.power('+5V', (358.14, 40.64))
    r17 = s.add('Device:R', 'R17', '10R', 365.76, 40.64, rot=90, fp=FP_R,
                ref_at=(365.76, 38.1), val_at=(365.76, 43.18), ref_just='center', val_just='center',
                desc='Receiver supply filter resistor')
    s.wire((358.14, 40.64), r17['pins']['1'])
    c8 = s.add('Device:C_Polarized', 'C8', '47uF 16V', 375.92, 46.99, fp=FP_CP5,
               ref_at=(373.38, 45.72), val_at=(373.38, 48.26), ref_just='right', val_just='right',
               desc='Receiver supply filter, electrolytic')
    c9 = s.add('Device:C', 'C9', '100nF', 386.08, 46.99, fp=FP_C, desc='Receiver supply decoupling')
    s.wire(r17['pins']['2'], (375.92, 40.64), (386.08, 40.64), (398.78, 40.64), U['+V'])
    for c in (c8, c9):
        s.wire(c['pins']['1'], (c['pins']['1'][0], 40.64))
        s.junction((c['pins']['1'][0], 40.64))
        s.power('GND', c['pins']['2'], show=False)
    s.power('GND', U['GND'], show=False)
    s.nc(U['VT'])
    for i, pin in enumerate(('D0', 'D1', 'D2', 'D3')):
        s.wire(U[pin], (381, U[pin][1]))
        s.label(f'RX_{pin}', (381, U[pin][1]), 180)
    # Series 1k (pin protection, slows edges) + 100k pull-down (no floating input without the module)
    for i in range(4):
        x = 289.56 + i * 17.78
        node = (x, 53.34)
        s.wire((x, 40.64), (x, 43.18))
        s.label(f'RX_D{i}', (x, 40.64), 90)
        r = s.add('Device:R', f'R{7 + i}', '1k', x, 46.99, fp=FP_R, desc='Remote channel series resistor')
        rp = s.add('Device:R', f'R{13 + i}', '100k', x, 59.69, fp=FP_R, desc='Remote channel pull-down')
        s.wire(r['pins']['2'], node, rp['pins']['1'])
        s.wire(rp['pins']['2'], (x, 66.04))
        s.power('GND', (x, 66.04), show=False)
        s.wire(node, (x + 5.08, node[1]))
        s.label(f'RF{i + 1}', (x + 5.08, node[1]), 0)
        s.junction(node)
    s.text('U2 stands upright in a 7-pin socket: pin 1 GND at the learn-button end, pin 7 VT at the\n'
           'antenna end (checked against the RX480R_4CH V4 labels). Mark both ends on the silkscreen:\n'
           'plugged in backwards it puts 5 V on an output. Pair the remote in MOMENTARY mode.', (279.4, 70.0))

    # ======================= PANEL BUTTON + LEDS ============================
    s.text('PANEL BUTTON AND LIMIT LEDS (JST-XH 2-pin connectors)', (279.4, 81.28), 2, True)
    nb = (289.56, 96.52)
    r3 = s.add('Device:R', 'R3', '10k', nb[0], 92.71, fp=FP_R, ref_at=(287.02, 91.44), val_at=(287.02, 93.98),
               ref_just='right', val_just='right', desc='Button pull-up')
    c7 = s.add('Device:C', 'C7', '100nF', nb[0], 100.33, fp=FP_C, ref_at=(287.02, 99.06), val_at=(287.02, 101.6),
               ref_just='right', val_just='right', desc='Button filter capacitor')
    s.power('+5V', r3['pins']['1'])
    s.wire(c7['pins']['2'], (nb[0], 105.41))
    s.power('GND', (nb[0], 105.41), show=False)
    j5 = s.add('Connector_Generic:Conn_01x02', 'J5', 'BUTTON', 314.96, nb[1], fp=FP_XH2,
               ref_at=(314.96, 92.71), val_at=(322.58, 97.79), ref_just='center',
               desc='Panel push button (MODE / CAL): 1 = button, 2 = GND. JST-XH 2-pin')
    s.wire((281.94, nb[1]), nb, j5['pins']['1'])
    s.junction(nb)
    s.label('BTN', (281.94, nb[1]), 180)
    s.wire(j5['pins']['2'], (307.34, j5['pins']['2'][1]))
    s.power('GND', (307.34, j5['pins']['2'][1]), rot=270, show=False)
    for i, (lbl, jref, rref) in enumerate((('LED25', 'J6', 'R4'), ('LED50', 'J7', 'R5'), ('LED100', 'J8', 'R6'))):
        y = 116.84 + i * 10.16
        r = s.add('Device:R', rref, '330', 289.56, y, rot=90, fp=FP_R,
                  ref_at=(289.56, y - 2.54), val_at=(289.56, y + 2.54), ref_just='center', val_just='center',
                  desc=f'{lbl} current limit (~9 mA)')
        j = s.add('Connector_Generic:Conn_01x02', jref, f'LED {lbl[3:]}L', 314.96, y, fp=FP_XH2,
                  ref_at=(314.96, y - 3.81), val_at=(322.58, y + 1.27), ref_just='center',
                  desc=f'Panel LED for the {lbl[3:]} L limit: 1 = LED + (anode), 2 = LED - (cathode). JST-XH 2-pin')
        s.wire((281.94, y), r['pins']['1'])
        s.label(lbl, (281.94, y), 180)
        s.wire(r['pins']['2'], (295.91, y), j['pins']['1'])
        s.label(f'{lbl}_A', (295.91, y))
        s.wire(j['pins']['2'], (307.34, j['pins']['2'][1]))
        s.power('GND', (307.34, j['pins']['2'][1]), rot=270, show=False)

    # ======================= ESP LINK ========================================
    s.text('ESP32 LINK (JST-XH 4-pin)', (279.4, 147.32), 2, True)
    r11 = s.add('Device:R', 'R11', '1.8k', 299.72, 160.02, fp=FP_R, ref_at=(297.18, 158.75), val_at=(297.18, 161.29),
                ref_just='right', val_just='right', desc='Data to ESP divider (top)')
    s.wire((299.72, 153.67), r11['pins']['1'])
    s.label('TX_5V', (299.72, 153.67), 90)
    node_e = r11['pins']['2']
    r12 = s.add('Device:R', 'R12', '3.3k', 299.72, 167.64, fp=FP_R, ref_at=(297.18, 166.37), val_at=(297.18, 168.91),
                ref_just='right', val_just='right', desc='Data to ESP divider (bottom), 5 V -> 3.24 V')
    s.wire(r12['pins']['2'], (299.72, 173.99))
    s.power('GND', (299.72, 173.99), show=False)
    j4 = s.add('Connector_Generic:Conn_01x04', 'J4', 'ESP32', 340.36, 161.29, fp=FP_XH4,
               ref_at=(340.36, 154.94), val_at=(340.36, 170.18), ref_just='center', val_just='center',
               desc='ESP32-C3-Zero link: 1 = +5V (ESP 5V pin), 2 = GND, 3 = data to ESP (3.3 V, ESP RX, GPIO20), '
                    '4 = data from ESP (ESP TX, GPIO21). JST-XH 4-pin')
    Q = j4['pins']
    s.wire(Q['1'], (330.2, Q['1'][1]))
    s.power('+5V', (330.2, Q['1'][1]), rot=90)
    s.wire(Q['2'], (332.74, Q['2'][1]))
    s.power('GND', (332.74, Q['2'][1]), rot=270, show=False)
    s.wire(node_e, (312.42, node_e[1]), (Q['3'][0], node_e[1]))
    s.label('TO_ESP', (312.42, node_e[1]))
    s.junction(node_e)
    r21 = s.add('Device:R', 'R21', '1k', 326.39, Q['4'][1], rot=90, fp=FP_R,
                ref_at=(326.39, Q['4'][1] + 2.54), val_at=(326.39, Q['4'][1] + 5.08), ref_just='center',
                val_just='center', desc='Data from ESP: series resistor (pin protection)')
    s.wire(Q['4'], r21['pins']['2'])
    s.wire(r21['pins']['1'], (314.96, Q['4'][1]))
    s.label('ESP_IN', (314.96, Q['4'][1]), 180)

    s.text('MOUNTING HOLES (M4)', (358.14, 147.32), 2, True)
    for i in range(4):
        s.add('Mechanical:MountingHole', f'H{i + 1}', 'M4', 363.22 + i * 11.43, 162.56, fp=FP_HOLE,
              ref_at=(363.22 + i * 11.43, 157.48), val_at=(363.22 + i * 11.43, 167.64),
              ref_just='center', val_just='center', in_bom=False, desc='M4 mounting hole')

    # ======================= OFF-BOARD =======================================
    s.dashed_box(15.24, 193.04, 185.42, 266.7)
    s.text('OFF-BOARD PARTS (wired to J2, J3, J5-J8; not placed on the PCB)', (19.05, 199.39), 2, True)
    sw2 = s.add('WaterValve:Rocker_Switch_LED', 'SW2', 'Rocker switch, 12 V lamp', 38.1, 215.9,
                on_board=False, ref_at=(30.48, 208.28), val_at=(30.48, 223.52),
                desc='Illuminated SPST rocker switch, 12 V lamp, rated 5 A or more (panel mount)')
    W = sw2['pins']
    s.wire(W['1'], (55.88, W['1'][1]))
    s.label('12V_FUSED', (55.88, W['1'][1]))
    s.wire(W['2'], (53.34, W['2'][1]))
    s.power('+12V', (53.34, W['2'][1]), rot=270)
    s.wire(W['3'], (53.34, W['3'][1]))
    s.power('GND', (53.34, W['3'][1]), rot=90, show=False)
    sv = s.add('WaterValve:Solenoid_Valve', 'SV1', '12 V DC solenoid valve', 91.44, 215.9,
               on_board=False, in_bom=False, ref_at=(95.25, 214.63), val_at=(95.25, 217.17),
               desc='Existing 12 V DC normally-closed solenoid valve')
    s.wire(sv['pins']['1'], (91.44, 205.74), (83.82, 205.74))
    s.label('SOL_OUT', (83.82, 205.74), 180)
    s.wire(sv['pins']['2'], (91.44, 226.06))
    s.power('GND', (91.44, 226.06), show=False)
    fs = s.add('WaterValve:YF-G1_Flow_Sensor', 'FS1', 'YF-G1 (64.8 pulses/L)', 137.16, 215.9,
               on_board=False, in_bom=False, ref_at=(127, 209.55), val_at=(127, 222.25),
               desc='Existing YF-G1 flow sensor, powered from 5 V (via J3)')
    F = fs['pins']
    s.wire(F['1'], (152.4, F['1'][1]), (152.4, 210.82))
    s.power('+5V', (152.4, 210.82))
    s.wire(F['2'], (154.94, F['2'][1]))
    s.label('FLOW_IN', (154.94, F['2'][1]), 0)
    s.wire(F['3'], (152.4, F['3'][1]), (152.4, 223.52))
    s.power('GND', (152.4, 223.52), show=False)
    sw1 = s.add('Switch:SW_Push', 'SW1', 'MODE / CAL', 38.1, 243.84, on_board=False,
                ref_at=(38.1, 236.22), val_at=(38.1, 238.76), ref_just='center', val_just='center',
                desc='Panel momentary push button (normally open), with a JST-XH 2-pin lead to J5')
    s.wire(sw1['pins']['1'], (27.94, 243.84))
    s.label('BTN', (27.94, 243.84), 180)
    s.wire(sw1['pins']['2'], (48.26, 243.84), (48.26, 248.92))
    s.power('GND', (48.26, 248.92), show=False)
    for i, (lbl, ref, colour) in enumerate((('LED25', 'D3', 'green'), ('LED50', 'D4', 'yellow'),
                                            ('LED100', 'D5', 'red'))):
        y = 236.22 + i * 8.89
        led = s.add('Device:LED', ref, f'{lbl[3:]}L {colour}', 91.44, y, rot=180, on_board=False,
                    ref_at=(91.44, y - 3.81), val_at=(101.6, y), ref_just='center', val_just='left',
                    desc=f'{lbl[3:]} L limit indicator: panel LED (plain, no built-in resistor), JST-XH 2-pin lead')
        s.wire(led['pins']['A'], (81.28, y))
        s.label(f'{lbl}_A', (81.28, y), 180)
        s.wire(led['pins']['K'], (99.06, y), (99.06, y + 2.54))
        s.power('GND', (99.06, y + 2.54), show=False)
    s.text('J2 -> SW2: 1 = 12 V in (switch power terminal),\n2 = 12 V out (switch load terminal), 3 = lamp GND.\n'
           'J3 -> valve: 1 = valve +, 2 = valve -. Valve flyback\ndiode D2 is on the board.', (115.57, 238.76))

    # ======================= NOTES ===========================================
    s.text('INTERFERENCE AND RELIABILITY MEASURES', (279.4, 182.88), 2, True)
    s.text('1. D2 flyback diode at the valve output; Q1 switches the valve + (high side), valve - goes to GND.\n'
           '2. 2 mm tracks for the 12 V and valve current; GND poured on both layers.\n'
           '3. Decoupling: C1 + C2 on 12 V, C3 + C4 at U1, C10 at the Nano, C6 at J3.\n'
           '4. Flow input: R1 10k pull-up, R2 1k + C5 10nF filter, firmware glitch filter.\n'
           '5. Button: R3 10k + C7 100nF. Remote: R7-R10 1k series, R13-R16 100k pull-downs,\n'
           '   receiver supply filtered by R17 + C8 + C9. Firmware debounces both.\n'
           '6. F1 fuse (before the main switch) + D1 crowbar protect against shorts and a reversed supply.\n'
           '7. R11 / R12 divide the 5 V data line to 3.2 V for the ESP; R21 protects D12 from the ESP.\n'
           '8. Twist the flow sensor signal with its GND; route it away from the valve and 12 V wires.\n'
           '9. Receiver antenna end at a board edge, away from the valve driver and the regulator.',
           (279.4, 186.69))

    title = [
        '(title "Water Valve Controller")',
        '(date "2026-10-12")',
        '(rev "1.2")',
        '(company "Arduino Nano carrier board")',
        '(comment 1 "YF-G1 flow sensor, MOSFET valve driver, RX480E 433 MHz receiver, ESP link")',
        '(comment 2 "Firmware: WaterValveController.ino")',
        '(comment 3 "Pins: D2 flow, D4 button, D5-D7 LEDs, D8 valve, D11/D12 ESP, A0-A3 remote")',
    ]
    return s, title


def main(out, variant='tht'):
    global VARIANT, PROJECT
    VARIANT = variant
    if variant == 'smd':
        PROJECT = 'WaterValveController-SMD'
    os.makedirs(out, exist_ok=True)
    s, title = build()
    with open(os.path.join(out, PROJECT + '.kicad_sch'), 'w') as f:
        f.write(s.render(title))
    pro = json.load(open('/usr/share/kicad/template/kicad.kicad_pro'))
    pro['meta']['filename'] = PROJECT + '.kicad_pro'
    pro['sheets'] = [[ROOT_UUID, '']]
    with open(os.path.join(out, PROJECT + '.kicad_pro'), 'w') as f:
        json.dump(pro, f, indent=2)
    # Project symbol library with the custom (off-board) symbols
    lib = '(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n'
    for name, sym in CUSTOM.items():
        sym = [x for x in sym]
        sym[1] = q(name)
        lib += '  ' + dump(sym, 1) + '\n'
    lib += ')\n'
    with open(os.path.join(out, 'WaterValve.kicad_sym'), 'w') as f:
        f.write(lib)
    with open(os.path.join(out, 'sym-lib-table'), 'w') as f:
        f.write('(sym_lib_table\n  (lib (name "WaterValve")(type "KiCad")(uri "${KIPRJMOD}/WaterValve.kicad_sym")'
                '(options "")(descr "Off-board parts for the Water Valve Controller"))\n)\n')
    # One footprint library (made by gen_pcb.py) shared by both boards
    pretty = '${KIPRJMOD}/WaterValve.pretty' if variant == 'tht' else '${KIPRJMOD}/../WaterValve.pretty'
    with open(os.path.join(out, 'fp-lib-table'), 'w') as f:
        f.write(f'(fp_lib_table\n  (lib (name "WaterValve")(type "KiCad")(uri "{pretty}")'
                '(options "")(descr "Arduino Nano footprint for a socketed Nano"))\n)\n')
    json.dump([{k: v for k, v in p.items() if k != 'pins'} | {'pins': {k: list(v) for k, v in p['pins'].items()}}
               for p in s.parts], open(os.path.join(out, '.parts.json'), 'w'))


if __name__ == '__main__':
    main(sys.argv[1], *sys.argv[2:3])

"""Generates the Water Valve Controller KiCad 7 project.

Usage: python3 gen.py OUT_DIR
"""
import json
import math
import os
import sys
import uuid as uuidlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, dump  # noqa: E402

PROJECT = "WaterValveController"
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
    'Relay_Module': custom_symbol(
        'Relay_Module', 'K', 'Relay_Module', (-7.62, 5.08, 7.62, -5.08),
        [('1', 'VCC', 'power_in', -10.16, 2.54, 0, 2.54),
         ('2', 'IN', 'input', -10.16, 0, 0, 2.54),
         ('3', 'GND', 'power_in', -10.16, -2.54, 0, 2.54),
         ('4', 'COM', 'passive', 10.16, 2.54, 180, 2.54),
         ('5', 'NO', 'passive', 10.16, 0, 180, 2.54),
         ('6', 'NC', 'passive', 10.16, -2.54, 180, 2.54)]),
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
        sym = self.libsym(lib_id)
        pins = pins_of(sym)
        u = uid(ref)
        if ref_at is None:
            ref_at = (x + 2.54, y - 1.27)
        if val_at is None:
            val_at = (x + 2.54, y + 1.27)
        is_power = ref.startswith('#')

        fang = 90 if rot in (90, 270) else 0
        if rot == 90:
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
FP_R = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal'
FP_C = 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm'
FP_CP10 = 'Capacitor_THT:CP_Radial_D10.0mm_P5.00mm'
FP_CP6 = 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
FP_D = 'Diode_THT:D_DO-201AD_P15.24mm_Horizontal'
FP_LED = 'LED_THT:LED_D5.0mm'
FP_TB2 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
FP_TB3 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal'
FP_TB6 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal'
FP_HDR3 = 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
FP_FUSE = 'Fuse:Fuseholder_Cylinder-5x20mm_Stelvio-Kontek_PTF78_Horizontal_Open'
FP_TO220 = 'Package_TO_SOT_THT:TO-220-3_Vertical'
FP_NANO = 'Module:Arduino_Nano'
FP_SW = 'Button_Switch_THT:SW_PUSH_6mm'
FP_SOCK7 = 'Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical'
FP_CP5 = 'Capacitor_THT:CP_Radial_D5.0mm_P2.00mm'
FP_HOLE = 'MountingHole:MountingHole_3.2mm_M3'


def build():
    s = Sch()
    G = 2.54

    # ======================= POWER ==========================================
    s.text('POWER: 12 V IN, FUSE, REVERSE-POLARITY CROWBAR, 5 V REGULATOR', (20.32, 33.02), 2, True)
    j1 = s.add('Connector:Screw_Terminal_01x02', 'J1', '12V DC IN', 30.48, 50.8, mirror=True, fp=FP_TB2,
               ref_at=(27.94, 45.72), val_at=(27.94, 58.42), ref_just='center', val_just='center',
               desc='12 V DC supply input, 2-way 5.08 mm screw terminal')
    f1 = s.add('Device:Fuse', 'F1', '2A slow', 50.8, 50.8, rot=90, fp=FP_FUSE,
               ref_at=(50.8, 46.99), val_at=(50.8, 54.61), ref_just='center', val_just='center',
               desc='5x20 mm fuse holder + 2 A slow-blow fuse')
    s.wire(j1['pins']['1'], f1['pins']['1'])
    # GND return from J1 pin 2 (star point for the valve return is J1)
    gx = 38.1
    s.wire(j1['pins']['2'], (gx, 53.34), (gx, 60.96))
    s.wire((gx, 60.96), (gx, 66.04))
    s.power('GND', (gx, 66.04), show=False)
    s.flag((gx, 60.96), rot=270)

    bus_y = 50.8
    xs = dict(flag=58.42, d1=66.04, c1=81.28, c2=96.52)
    u1 = s.add('Regulator_Linear:L7805', 'U1', 'R-78E5.0-1.0 or L7805', 109.22, bus_y, fp=FP_TO220,
               ref_at=(109.22, 44.45), val_at=(109.22, 46.99), ref_just='center', val_just='center',
               desc='5 V regulator, TO-220 pinout IN-GND-OUT: R-78E5.0-1.0 switcher (recommended with the ESP), or L7805 + heatsink')
    d1 = s.add('Device:D', 'D1', '1N5408', xs['d1'], 57.15, rot=270, fp=FP_D,
               ref_at=(xs['d1'] + 2.54, 55.88), val_at=(xs['d1'] + 2.54, 58.42),
               desc='Reverse-polarity crowbar: conducts and blows F1 if the supply is reversed')
    c1 = s.add('Device:C_Polarized', 'C1', '470uF 25V', xs['c1'], 57.15, fp=FP_CP10,
               desc='Bulk capacitor, 12 V rail, 105 C electrolytic')
    c2 = s.add('Device:C', 'C2', '100nF', xs['c2'], 57.15, fp=FP_C, desc='Ceramic, 12 V rail at U1 input')
    pts = [f1['pins']['2'], (xs['flag'], bus_y), (xs['d1'], bus_y), (xs['c1'], bus_y), (xs['c2'], bus_y), u1['pins']['IN']]
    s.wire(*pts)
    s.flag((xs['flag'], bus_y))
    for k in ('d1', 'c1', 'c2'):
        s.junction((xs[k], bus_y))
    s.power('+12V', (xs['d1'], bus_y))
    s.wire((xs['d1'], bus_y), d1['pins']['K'])
    s.wire((xs['c1'], bus_y), c1['pins']['1'])
    s.wire((xs['c2'], bus_y), c2['pins']['1'])
    for p in (d1['pins']['A'], c1['pins']['2'], c2['pins']['2'], u1['pins']['GND']):
        s.wire(p, (p[0], 66.04))
        s.power('GND', (p[0], 66.04), show=False)
    c3x, c4x, p5x = 124.46, 137.16, 147.32
    c3 = s.add('Device:C', 'C3', '100nF', c3x, 57.15, fp=FP_C, desc='Ceramic, 5 V rail at U1 output')
    c4 = s.add('Device:C_Polarized', 'C4', '100uF 16V', c4x, 57.15, fp=FP_CP6, desc='Electrolytic, 5 V rail')
    s.wire(u1['pins']['OUT'], (c3x, bus_y), (c4x, bus_y), (p5x, bus_y))
    s.junction((c3x, bus_y))
    s.junction((c4x, bus_y))
    s.power('+5V', (p5x, bus_y))
    s.wire((c3x, bus_y), c3['pins']['1'])
    s.wire((c4x, bus_y), c4['pins']['1'])
    for p in (c3['pins']['2'], c4['pins']['2']):
        s.wire(p, (p[0], 66.04))
        s.power('GND', (p[0], 66.04), show=False)
    s.text('F1 + D1: if the supply is connected backwards, D1 conducts and blows F1.\n'
           'U1: the ESP32-C3 Wi-Fi peaks take the 5 V load to about 0.5 A. Use a pin-compatible switching\n'
           'regulator (e.g. R-78E5.0-1.0) or a 5 V buck module wired to IN / GND / OUT. An L7805 needs a heatsink.',
           (20.32, 72.39))

    # ======================= FLOW SENSOR INPUT ===============================
    s.text('FLOW SENSOR INPUT (YF-G1, NPN open collector)', (20.32, 91.44), 2, True)
    j4 = s.add('Connector:Screw_Terminal_01x03', 'J4', 'FLOW SENSOR', 27.94, 109.22, mirror=True, fp=FP_TB3,
               ref_at=(26.67, 102.87), val_at=(26.67, 119.38), ref_just='center', val_just='center',
               desc='Flow sensor: 1 = +5V (red), 2 = SIG (yellow), 3 = GND (black)')
    p1, p2, p3 = j4['pins']['1'], j4['pins']['2'], j4['pins']['3']
    s.wire(p1, (35.56, p1[1]), (35.56, 101.6))
    s.power('+5V', (35.56, 101.6))
    s.wire(p3, (35.56, p3[1]), (35.56, 116.84))
    s.power('GND', (35.56, 116.84), show=False)
    node_in = (48.26, p2[1])
    s.wire(p2, (43.18, p2[1]), node_in)
    s.label('FLOW_IN', (43.18, p2[1]), 180)
    r1 = s.add('Device:R', 'R1', '10k', 48.26, 102.87, fp=FP_R, desc='Flow signal pull-up')
    s.wire(r1['pins']['2'], node_in)
    s.power('+5V', r1['pins']['1'])
    r2 = s.add('Device:R', 'R2', '1k', 55.88, p2[1], rot=90, fp=FP_R,
               ref_at=(55.88, p2[1] - 2.54), val_at=(55.88, p2[1] + 2.54), ref_just='center', val_just='center',
               desc='Flow signal series resistor (RC filter / pin protection)')
    s.wire(node_in, r2['pins']['1'])
    s.junction(node_in)
    node_f = (66.04, p2[1])
    c5 = s.add('Device:C', 'C5', '10nF', 66.04, 115.57, fp=FP_C, desc='Flow signal filter capacitor')
    s.wire(r2['pins']['2'], node_f, (73.66, p2[1]))
    s.wire(node_f, c5['pins']['1'])
    s.junction(node_f)
    s.wire(c5['pins']['2'], (66.04, 121.92))
    s.power('GND', (66.04, 121.92), show=False)
    s.label('FLOW', (73.66, p2[1]), 0)
    c6 = s.add('Device:C', 'C6', '100nF', 91.44, 109.22, fp=FP_C, desc='Sensor supply decoupling, at J4')
    s.power('+5V', c6['pins']['1'])
    s.power('GND', c6['pins']['2'], show=False)
    s.text('R2 + C5 filter fast spikes (time constant 10 us);\nthe firmware also ignores pulses < 2 ms apart.\nC6 sits right at J4.', (20.32, 125.73))

    # ======================= BUTTON + LEDS ===================================
    s.text('BUTTON AND LIMIT LEDS', (20.32, 144.78), 2, True)
    nb = (45.72, 165.1)
    r3 = s.add('Device:R', 'R3', '10k', 45.72, 158.75, fp=FP_R, desc='Button pull-up')
    c7 = s.add('Device:C', 'C7', '100nF', 45.72, 171.45, fp=FP_C, desc='Button filter capacitor')
    s.power('+5V', r3['pins']['1'])
    s.wire(r3['pins']['2'], nb, c7['pins']['1'])
    s.wire(c7['pins']['2'], (45.72, 177.8))
    s.power('GND', (45.72, 177.8), show=False)
    s.wire(nb, (38.1, nb[1]))
    s.label('BTN', (38.1, nb[1]), 180)
    sw1 = s.add('Switch:SW_Push', 'SW1', 'MODE / CAL', 60.96, nb[1], fp=FP_SW,
                ref_at=(60.96, nb[1] - 5.08), val_at=(60.96, nb[1] - 3.175), ref_just='center', val_just='center',
                desc='Momentary push button (or panel button wired to these pads)')
    s.wire(nb, sw1['pins']['1'])
    s.junction(nb)
    s.wire(sw1['pins']['2'], (71.12, nb[1]), (71.12, 170.18))
    s.power('GND', (71.12, 170.18), show=False)
    for i, (lbl, ref, rref, x, colour) in enumerate([
            ('LED25', 'D3', 'R4', 86.36, 'green'), ('LED50', 'D4', 'R5', 101.6, 'yellow'),
            ('LED100', 'D5', 'R6', 116.84, 'red')]):
        s.wire((x, 151.13), (x, 153.67))
        s.label(lbl, (x, 151.13), 90)
        r = s.add('Device:R', rref, '330', x, 157.48, fp=FP_R, desc=f'{lbl} current limit (~9 mA)')
        s.wire((x, 153.67), r['pins']['1'])
        led = s.add('Device:LED', ref, f'{lbl[3:]}L {colour}', x, 167.64, rot=90, fp=FP_LED,
                    desc=f'{lbl[3:]} L limit indicator, 5 mm')
        s.wire(r['pins']['2'], led['pins']['A'])
        s.wire(led['pins']['K'], (x, 175.26))
        s.power('GND', (x, 175.26), show=False)

    # ======================= ARDUINO NANO ====================================
    s.text('CONTROLLER', (190.5, 91.44), 2, True)
    NX, NY = 215.9, 127
    a1 = s.add('MCU_Module:Arduino_Nano_v3.x', 'A1', 'Arduino Nano', NX, NY, fp=FP_NANO,
               ref_at=(NX - 10.16, NY - 23.495), val_at=(NX + 5.08, NY + 24.13),
               desc='Arduino Nano v3 (ATmega328P), on 2 x 15 female headers')
    P = a1['pins']
    used_left = {'D2': 'FLOW', 'D4': 'BTN', 'D5': 'LED25', 'D6': 'LED50', 'D7': 'LED100',
                 'D8': 'RELAY', 'D11': 'TX_5V'}
    used_right = {'A0': 'RF1', 'A1': 'RF2', 'A2': 'RF3', 'A3': 'RF4'}
    for pin, net in used_left.items():
        p = P[pin]
        s.wire(p, (p[0] - 5.08, p[1]))
        s.label(net, (p[0] - 5.08, p[1]), 180)
    for pin, net in used_right.items():
        p = P[pin]
        s.wire(p, (p[0] + 5.08, p[1]))
        s.label(net, (p[0] + 5.08, p[1]), 0)
    for num in ('1', '2', '6', '12', '13', '15', '16', '3', '28', '18', '23', '24', '25', '26', '17', '30'):
        s.nc(P[num])
    s.wire(P['27'], (P['27'][0], NY - 30.48))
    s.power('+5V', (P['27'][0], NY - 30.48))
    g1, g2 = P['4'], P['29']
    gy = NY + 30.48
    s.wire(g1, (g1[0], gy))
    s.wire(g2, (g2[0], gy))
    s.wire((g1[0], gy), (g2[0], gy))
    s.power('GND', (g1[0], gy), show=False)
    c11 = s.add('Device:C', 'C11', '100nF', 238.76, 101.6, fp=FP_C, desc='Decoupling at the Nano 5V pin')
    s.power('+5V', c11['pins']['1'])
    s.power('GND', c11['pins']['2'], show=False)
    s.text('D12 is reserved for a future ESP -> Nano link.\nNano is powered through its 5V pin (VIN unused).', (190.5, 163.83))

    # ======================= REMOTE RECEIVER =================================
    s.text('REMOTE RECEIVER (RX480E 433 MHz module, plugs into the board)', (279.4, 30.48), 2, True)
    u2 = s.add('WaterValve:RX480E', 'U2', 'RX480E-4', 398.78, 63.5, fp=FP_SOCK7,
               ref_at=(397.51, 52.07), val_at=(391.16, 76.2), ref_just='right', val_just='right',
               desc='RX480E-4 receiver module on a 1x7 female header. Pins: 1 GND, 2 +V, 3-6 D0-D3, 7 VT')
    U = u2['pins']
    # Supply filter: 10 R + 47 uF + 100 nF keeps relay and regulator noise off the receiver
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

    # ======================= RELAY + VALVE CONNECTORS ========================
    s.text('RELAY MODULE AND VALVE POWER', (279.4, 81.28), 2, True)
    j3 = s.add('Connector_Generic:Conn_01x03', 'J3', 'RELAY MODULE', 401.32, 93.98, fp=FP_HDR3,
               ref_at=(401.32, 88.9), val_at=(401.32, 99.06), ref_just='center', val_just='center',
               desc='Relay module header: 1 = VCC (+5V), 2 = IN (D8), 3 = GND')
    Q = j3['pins']
    s.wire(Q['1'], (391.16, Q['1'][1]), (391.16, Q['1'][1] - 2.54))
    s.power('+5V', (391.16, Q['1'][1] - 2.54))
    s.wire(Q['2'], (386.08, Q['2'][1]))
    s.label('RELAY', (386.08, Q['2'][1]), 180)
    s.wire(Q['3'], (391.16, Q['3'][1]), (391.16, Q['3'][1] + 2.54))
    s.power('GND', (391.16, Q['3'][1] + 2.54), show=False)
    c10 = s.add('Device:C_Polarized', 'C10', '100uF 16V', 365.76, 93.98, fp=FP_CP6,
                ref_at=(363.22, 92.71), val_at=(363.22, 95.25), ref_just='right', val_just='right',
                desc='Bulk capacitor at the relay header (relay coil switching)')
    s.power('+5V', c10['pins']['1'])
    s.power('GND', c10['pins']['2'], show=False)
    j2 = s.add('Connector:Screw_Terminal_01x02', 'J2', 'VALVE POWER', 401.32, 114.3, fp=FP_TB2,
               ref_at=(401.32, 109.22), val_at=(401.32, 120.65), ref_just='center', val_just='center',
               desc='Valve power out: 1 = +12V (fused) to relay COM, 2 = GND from valve -')
    Q = j2['pins']
    s.wire(Q['1'], (391.16, Q['1'][1]), (391.16, Q['1'][1] - 2.54))
    s.power('+12V', (391.16, Q['1'][1] - 2.54))
    s.wire(Q['2'], (391.16, Q['2'][1]), (391.16, Q['2'][1] + 2.54))
    s.power('GND', (391.16, Q['2'][1] + 2.54), show=False)
    s.text('J2: run the valve +12 V and return as their own pair, and keep them away\nfrom the sensor cable. Place J1 and J2 side by side.\nC10 sits at J3 to steady 5 V when the relay coil switches.', (279.4, 106.68))

    # ======================= ESP DATA OUT ====================================
    s.text('ESP DATA OUT (9600 baud, 3.3 V level)', (279.4, 129.54), 2, True)
    s.text('ESP32-C3-Zero: J5 5V -> 5V pin, DATA -> GPIO20 (RX),\n'
           'GND -> GND. Its GPIOs are 3.3 V only, so R11 / R12\n'
           'drop the Nano\'s 5 V data to 3.2 V.', (279.4, 134.62))
    rx = 370.84
    s.wire((rx, 138.43), (rx, 140.97))
    s.label('TX_5V', (rx, 138.43), 90)
    r11 = s.add('Device:R', 'R11', '1.8k', rx, 144.78, fp=FP_R, desc='ESP data divider (top)')
    s.wire((rx, 140.97), r11['pins']['1'])
    node_e = (rx, 151.13)
    r12 = s.add('Device:R', 'R12', '3.3k', rx, 157.48, fp=FP_R, desc='ESP data divider (bottom), 5 V -> 3.24 V')
    s.wire(r11['pins']['2'], node_e, r12['pins']['1'])
    s.wire(r12['pins']['2'], (rx, 163.83))
    s.power('GND', (rx, 163.83), show=False)
    j5 = s.add('Connector_Generic:Conn_01x03', 'J5', 'ESP32-C3', 401.32, 151.13, fp=FP_HDR3,
               ref_at=(401.32, 146.05), val_at=(401.32, 156.21), ref_just='center', val_just='center',
               desc='ESP header: 1 = +5V (to the ESP board 5V pin), 2 = DATA (3.3 V level, to an ESP GPIO), 3 = GND')
    Q = j5['pins']
    s.wire(node_e, (381, node_e[1]), Q['2'])
    s.label('ESP_DATA', (381, node_e[1]), 0)
    s.junction(node_e)
    s.wire(Q['1'], (391.16, Q['1'][1]), (391.16, Q['1'][1] - 2.54))
    s.power('+5V', (391.16, Q['1'][1] - 2.54))
    s.wire(Q['3'], (391.16, Q['3'][1]), (391.16, Q['3'][1] + 2.54))
    s.power('GND', (391.16, Q['3'][1] + 2.54), show=False)

    s.text('MOUNTING HOLES (M3)', (279.4, 152.4), 2, True)
    for i in range(4):
        s.add('Mechanical:MountingHole', f'H{i + 1}', 'M3', 284.48 + i * 15.24, 165.1, fp=FP_HOLE,
              ref_at=(284.48 + i * 15.24, 160.02), val_at=(284.48 + i * 15.24, 170.18),
              ref_just='center', val_just='center', in_bom=False, desc='M3 mounting hole')

    # ======================= OFF-BOARD =======================================
    s.dashed_box(15.24, 190.5, 185.42, 248.92)
    s.text('OFF-BOARD WIRING (connects to J2-J4; not placed on the PCB)', (19.05, 196.85), 2, True)
    k1 = s.add('WaterValve:Relay_Module', 'K1', 'Relay module', 45.72, 215.9,
               on_board=False, in_bom=False, ref_at=(38.1, 209.55), val_at=(38.1, 223.52),
               desc='Existing 1-channel 5 V relay module (via J3, and J2 for COM)')
    K = k1['pins']
    s.wire(K['VCC'], (30.48, K['VCC'][1]), (30.48, K['VCC'][1] - 2.54))
    s.power('+5V', (30.48, K['VCC'][1] - 2.54))
    s.wire(K['IN'], (25.4, K['IN'][1]))
    s.label('RELAY', (25.4, K['IN'][1]), 180)
    s.wire(K['GND'], (30.48, K['GND'][1]), (30.48, K['GND'][1] + 2.54))
    s.power('GND', (30.48, K['GND'][1] + 2.54), show=False)
    s.nc(K['NC'])
    s.wire(K['COM'], (60.96, K['COM'][1]))
    s.power('+12V', (60.96, K['COM'][1]))
    sv = s.add('WaterValve:Solenoid_Valve', 'SV1', '12 V DC solenoid valve', 91.44, 220.98,
               on_board=False, in_bom=False, ref_at=(95.25, 219.71), val_at=(95.25, 222.25),
               desc='Existing 12 V DC normally-closed solenoid valve')
    d2 = s.add('Device:D', 'D2', '1N5408', 78.74, 220.98, rot=270, fp='', on_board=False,
               ref_at=(72.39, 219.71), val_at=(68.58, 222.25),
               desc='Flyback diode across the valve terminals, stripe (K) to valve +')
    top = sv['pins']['1']
    s.wire(K['NO'], (78.74, K['NO'][1]))
    s.wire((78.74, K['NO'][1]), d2['pins']['K'])
    s.wire((78.74, K['NO'][1]), (91.44, K['NO'][1]), top)
    s.junction((78.74, K['NO'][1]))
    bot = sv['pins']['2']
    s.wire(d2['pins']['A'], (78.74, bot[1] + 2.54), (91.44, bot[1] + 2.54))
    s.wire(bot, (91.44, bot[1] + 2.54), (91.44, 233.68))
    s.junction((91.44, bot[1] + 2.54))
    s.power('GND', (91.44, 233.68), show=False)
    s.text('Valve circuit: relay COM <- J2 pin 1 (+12 V), valve - -> J2 pin 2.\nD2 sits on the valve terminals.', (22.86, 238.76))

    fs = s.add('WaterValve:YF-G1_Flow_Sensor', 'FS1', 'YF-G1 (64.8 pulses/L)', 137.16, 215.9,
               on_board=False, in_bom=False, ref_at=(127, 209.55), val_at=(127, 222.25),
               desc='Existing YF-G1 flow sensor, powered from 5 V (via J4)')
    F = fs['pins']
    s.wire(F['1'], (152.4, F['1'][1]), (152.4, 210.82))
    s.power('+5V', (152.4, 210.82))
    s.wire(F['2'], (154.94, F['2'][1]))
    s.label('FLOW_IN', (154.94, F['2'][1]), 0)
    s.wire(F['3'], (152.4, F['3'][1]), (152.4, 223.52))
    s.power('GND', (152.4, 223.52), show=False)

    # ======================= NOTES ===========================================
    s.text('INTERFERENCE AND RELIABILITY MEASURES', (279.4, 177.8), 2, True)
    s.text('1. D2 flyback diode right at the valve terminals (stripe to +).\n'
           '2. Valve current has its own pair (J2) back to J1: star ground at J1.\n'
           '3. Decoupling: C1 + C2 on 12 V, C3 + C4 at U1, C10 at J3, C11 at the Nano, C6 at J4.\n'
           '4. Flow input: R1 10k pull-up, R2 1k + C5 10nF filter, firmware glitch filter.\n'
           '5. Button: R3 10k + C7 100nF. Remote: R7-R10 1k series, R13-R16 100k pull-downs,\n'
           '   receiver supply filtered by R17 + C8 + C9. Firmware debounces both.\n'
           '6. F1 fuse + D1 crowbar protect against shorts and a reversed supply.\n'
           '7. R11 / R12 divide the 5 V data line down to 3.2 V for the ESP.\n'
           '8. Twist the flow sensor signal with its GND; route it away from the valve wires.\n'
           '9. Ground plane on the bottom layer; short, wide 12 V tracks; antenna away from relay and J2.',
           (279.4, 181.61))

    title = [
        '(title "Water Valve Controller")',
        '(date "2026-10-10")',
        '(rev "1.1")',
        '(company "Arduino Nano carrier board")',
        '(comment 1 "YF-G1 flow sensor, relay-switched 12 V DC solenoid valve, RX480E 433 MHz receiver, ESP data out")',
        '(comment 2 "Firmware: WaterValveController.ino")',
        '(comment 3 "Pins: D2 flow, D4 button, D5-D7 LEDs, D8 relay, D11 ESP, A0-A3 remote")',
    ]
    return s, title


def main(out):
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
    json.dump([{k: v for k, v in p.items() if k != 'pins'} | {'pins': {k: list(v) for k, v in p['pins'].items()}}
               for p in s.parts], open(os.path.join(out, '.parts.json'), 'w'))


if __name__ == '__main__':
    main(sys.argv[1])

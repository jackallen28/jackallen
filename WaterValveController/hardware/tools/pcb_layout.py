"""Part placement for the two boards, used by gen_pcb.py.

Coordinates are in mm from the board's top-left corner, y pointing down. Each entry is
    ref: (x, y, rotation)          footprint origin (pad 1 for most THT parts)
    ref: (x, y, rotation, 'tl')    top-left corner of the part's courtyard
Rotation is in degrees, anticlockwise, as in KiCad.

Both boards (portrait) use the same plan:
  * Top edge (narrow): J3, the 4-way VALVE / FLOW terminal, and J4, the ESP32 JST-XH connector.
    The valve driver (Q1, Q2, D2) sits right next to J3's valve pin.
  * JST-XH connectors for the panel button and the three LEDs in a row below them.
  * Arduino Nano across the middle on female headers, USB connector at the left edge. Low parts
    (flat resistors, SMD parts) sit underneath it, between the two pin rows.
  * 433 MHz receiver U2 below the Nano, antenna end at the left edge, away from the valve
    driver and the regulator.
  * Bottom edge (narrow): J1 12 V in and J2 main switch, with the blade fuse holder F1 and the
    crowbar diode D1 just above them. The regulator U1 has a clear area for a heatsink above its tab.
  * M4 holes in the corners; heavy parts (terminal blocks, C1, U1) sit near them.
"""

_V = dict(size=0.8, rot=90)            # small vertical label
_L = dict(size=0.8)

# ----------------------------------------------------------------------------------------------
# Through-hole board
# ----------------------------------------------------------------------------------------------
_NX, _NY = 42.46, 29.03                # Nano pad 1 (rotated 270: pad 1 at the right, USB at the left)
_col = [3.2 + 3.81 * k for k in range(12)]   # flat resistors under the Nano, standing across it
_RT, _RB = _NY + 3.81, _NY + 11.43     # their top and bottom pads


def _down(x):        # pin 1 at the top
    return (x, _RT, 270)


def _up(x):          # pin 1 at the bottom
    return (x, _RB, 90)


THT = dict(
    size=(66, 76),
    logo=(39.0, 66.6, 55.8, 75.4),
    keepouts=[(47.0, 27.4, 65.4, 46.6, 'U1 HEATSINK (L7805 only)')],
    labelled=('J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8'),
    refs={'R1': (22.75, 23.0, 0)},          # beside R1: the J7 label takes the space above it
    place={
        'A1': (_NX, _NY, 270),
        'H1': (5, 5, 0), 'H2': (61, 5, 0), 'H3': (5, 71, 0), 'H4': (61, 71, 0),
        # top edge: ESP connector, valve / flow terminal, Q1 gate pull-up, J3 decoupling
        'J4': (10.4, 1.0, 0, 'tl'), 'J3': (25.4, 0.4, 180, 'tl'),
        'R18': (48.0, 1.0, 90, 'tl'), 'C6': (52.0, 1.0, 90, 'tl'),
        # panel connectors, valve driver
        'J5': (0.6, 13.4, 0, 'tl'), 'J6': (10.0, 13.4, 0, 'tl'), 'J7': (19.4, 13.4, 0, 'tl'),
        'J8': (28.8, 13.4, 0, 'tl'),
        'D2': (38.4, 13.4, 0, 'tl'), 'Q1': (49.0, 13.4, 0, 'tl'),
        # small parts above the Nano
        'R3': (0.6, 21.9, 90, 'tl'), 'C7': (4.2, 22.4, 0, 'tl'),
        'R4': (11.9, 21.9, 90, 'tl'), 'R5': (15.5, 21.9, 90, 'tl'), 'R6': (19.1, 21.9, 90, 'tl'),
        'R1': (22.7, 21.9, 90, 'tl'), 'R2': (26.3, 21.9, 90, 'tl'), 'C5': (29.9, 22.4, 0, 'tl'),
        'Q2': (37.6, 22.2, 0, 'tl'), 'R19': (45.2, 21.9, 90, 'tl'), 'R20': (48.8, 21.9, 90, 'tl'),
        # under the Nano, lying flat
        'R12': _down(_col[0]), 'R21': _down(_col[1]), 'R11': _down(_col[2]),
        'R7': _up(_col[3]), 'R8': _up(_col[4]), 'R9': _up(_col[5]), 'R10': _up(_col[6]),
        'R13': _up(_col[7]), 'R14': _up(_col[8]), 'R15': _up(_col[9]), 'R16': _up(_col[10]),
        # receiver below the Nano, antenna end at the left edge
        'U2': (0.6, 47.0, 270, 'tl'),
        'C8': (20.0, 47.0, 0, 'tl'), 'C9': (26.0, 47.0, 0, 'tl'), 'R17': (26.0, 50.6, 0, 'tl'),
        'C10': (33.6, 47.0, 0, 'tl'),
        # regulator (tab and heatsink space upwards) and its capacitors
        'U1': (51.0, 47.0, 0, 'tl'), 'C2': (47.4, 47.0, 90, 'tl'), 'C3': (62.0, 47.0, 90, 'tl'),
        'C4': (55.0, 55.0, 0, 'tl'), 'C1': (41.5, 55.0, 0, 'tl'),
        # bottom edge: fuse, crowbar diode, 12 V in, main switch
        'F1': (10.0, 54.6, 0, 'tl'), 'D1': (31.0, 54.6, 0, 'tl'),
        'J1': (10.0, 64.8, 0, 'tl'), 'J2': (21.6, 64.8, 0, 'tl'),
    },
    texts=[
        # J4 ESP32 (pins left to right: +5V, GND, ESP RX, ESP TX)
        ('5V', 13.35, 8.65, _L), ('GND', 15.85, 8.65, _L), ('RX', 18.35, 8.65, _L),
        ('TX', 20.85, 8.65, _L), ('J4 ESP32', 17.1, 10.1, _L),
        # J3 valve / flow (pins right to left: valve +, GND, +5V, flow signal)
        ('VALVE+', 43.68, 12.0, _L), ('GND', 38.6, 12.0, _L), ('+5V', 33.52, 12.0, _L), ('FLOW', 28.44, 12.0, _L),
        # panel connectors (pin 1 = button / LED +)
        ('J5 BUTTON', 4.8, 21.0, _L), ('J6 25L', 14.2, 21.0, _L), ('J7 50L', 23.6, 21.0, _L),
        ('J8 100L', 33.0, 21.0, _L),
        # U2 receiver: GND pin at the learn-button end, VT at the antenna end
        ('VT / ANT END', 0.8, 51.45, dict(size=0.8, just='left')), ('GND END', 19.2, 51.45, dict(size=0.8, just='right')),
        # J1 12 V in, J2 main switch
        ('12V+', 13.04, 64.0, _L), ('GND', 18.12, 64.0, _L),
        ('SW IN', 24.64, 64.0, _L), ('SW OUT', 29.72, 64.0, _L), ('LAMP-', 34.8, 64.0, _L),
        ('FUSE 3A', 20.25, 53.8, _L), ('USB', 0.95, _NY + 7.62, _V),
        ('WATER VALVE CONTROLLER', 47.4, 69.6, dict(size=1.0, bottom=True)),
        ('THROUGH-HOLE  rev 1.3', 47.4, 72.2, dict(size=1.0, bottom=True)),
    ],
)

# ----------------------------------------------------------------------------------------------
# Mixed SMD + THT board
# ----------------------------------------------------------------------------------------------
_SX, _SY = 42.46, 23.43                    # Nano pad 1 (rotated 270, USB at the left)
_sx = [2.6 + 4.6 * k for k in range(10)]   # 0805 columns under the Nano (centres)
_sy = [26.5, 31.05, 35.6]                  # and rows


def _u(c, r, rot=0):
    """0805 under the Nano at column c, row r."""
    return (_sx[c] - 1.88, _sy[r] - 0.98, rot, 'tl')


def _c(x, y, rot=0):
    """0805 centred at (x, y)."""
    return (x - 1.88, y - 0.98, rot, 'tl')


SMD = dict(
    size=(66, 69.2),
    logo=(38.6, 60.4, 55.8, 68.8),
    keepouts=[(47.0, 21.9, 65.6, 41.0, 'U1 HEATSINK (L7805 only)')],
    labelled=('J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8'),
    refs={'C10': (36.1, 31.05, 0)},          # leaves the space below R2 for its label
    # 12 V feed from C1 past the regulator and up the right edge to the valve switch Q1 (source pad).
    # It passes beside U1 and C2 rather than through their pads, so the valve current has the full
    # track width all the way.
    preroute=[('+12V', 2.5, 'F.Cu', [(44.24, 53.64), (44.24, 47.6), (51.1, 47.6), (51.1, 38.0), (60.5, 28.6),
                                     (60.5, 13.5), (57.25, 10.25), (53.38, 10.25)])],
    place={
        'A1': (_SX, _SY, 270),
        'H1': (5, 5, 0), 'H2': (61, 5, 0), 'H3': (5, 64.2, 0), 'H4': (61, 64.2, 0),
        # top edge: ESP connector, valve / flow terminal, valve switch Q1
        'J4': (10.4, 1.0, 0, 'tl'), 'J3': (25.4, 0.4, 180, 'tl'),
        'Q1': (47.6, 0.5, 90, 'tl'),
        # panel connectors and the flyback diode
        'J5': (0.6, 13.4, 0, 'tl'), 'J6': (10.0, 13.4, 0, 'tl'), 'J7': (19.4, 13.4, 0, 'tl'),
        'J8': (28.8, 13.4, 0, 'tl'), 'D2': (38.4, 13.4, 0, 'tl'),
        # Q1 gate pull-up right below Q1, gate driver Q2 below that
        'R18': _c(51.0, 13.4, 180), 'Q2': (49.3, 15.07, 90, 'tl'), 'R19': _c(56.0, 16.0), 'R20': _c(56.0, 18.8),
        # under the Nano
        'R12': _u(0, 0), 'R21': _u(1, 0), 'R11': _u(2, 0), 'R3': _u(3, 0), 'C7': _u(4, 0),
        'R4': _u(5, 0), 'R5': _u(6, 0), 'R6': _u(7, 0), 'R2': _u(8, 0), 'C5': _u(9, 0),
        'R1': _u(9, 1), 'C10': _u(8, 1), 'C6': _u(9, 2),
        'R7': _u(1, 2), 'R13': _u(2, 2), 'R8': _u(3, 2), 'R14': _u(4, 2),
        'R9': _u(5, 2), 'R15': _u(6, 2), 'R10': _u(7, 2), 'R16': _u(8, 2),
        # receiver below the Nano, antenna end at the left edge
        'U2': (0.6, 41.0, 270, 'tl'), 'C8': (20.0, 40.8, 0, 'tl'),
        'C9': _c(28.0, 42.0), 'R17': _c(28.0, 44.6),
        # regulator (tab and heatsink space upwards)
        'U1': (51.0, 41.4, 0, 'tl'), 'C2': _c(48.4, 43.3, 90), 'C3': _c(64.0, 43.3, 90),
        'C1': (41.5, 48.4, 0, 'tl'), 'C4': (55.0, 48.4, 0, 'tl'),
        # bottom edge: fuse, crowbar diode, 12 V in, main switch
        'F1': (10.0, 48.0, 0, 'tl'), 'D1': (31.0, 48.0, 0, 'tl'),
        'J1': (10.0, 58.0, 0, 'tl'), 'J2': (21.6, 58.0, 0, 'tl'),
    },
    texts=[
        ('5V', 13.35, 8.65, _L), ('GND', 15.85, 8.65, _L), ('RX', 18.35, 8.65, _L),
        ('TX', 20.85, 8.65, _L), ('J4 ESP32', 17.1, 10.1, _L),
        ('VALVE+', 43.68, 12.0, _L), ('GND', 38.6, 12.0, _L), ('+5V', 33.52, 12.0, _L), ('FLOW', 28.44, 12.0, _L),
        ('J5 BUTTON', 4.8, 21.0, _L), ('J6 25L', 14.2, 21.0, _L), ('J7 50L', 23.6, 21.0, _L),
        ('J8 100L', 33.0, 21.0, _L),
        ('VT / ANT END', 0.8, 45.45, dict(size=0.8, just='left')), ('GND END', 19.2, 45.45, dict(size=0.8, just='right')),
        ('12V+', 13.04, 57.2, _L), ('GND', 18.12, 57.2, _L),
        ('SW IN', 24.64, 57.2, _L), ('SW OUT', 29.72, 57.2, _L), ('LAMP-', 34.8, 57.2, _L),
        ('FUSE 3A', 20.25, 47.2, _L), ('USB', _sx[0], _sy[1], _L),
        ('WATER VALVE CONTROLLER', 47.2, 63.2, dict(size=1.0, bottom=True)),
        ('MIXED SMD + THT  rev 1.3', 47.2, 65.8, dict(size=1.0, bottom=True)),
    ],
)

LAYOUTS = {'tht': THT, 'smd': SMD}

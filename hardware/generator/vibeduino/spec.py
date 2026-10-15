"""VIBEDUINO system specification.

Single source of truth for the hex module geometry, the module bus pinout,
the Arduino Uno R3 shield geometry and the slot -> Arduino pin map.  Every
board generator imports its numbers from here so the shield and all modules
stay mechanically and electrically compatible.

Coordinate conventions
----------------------
* Module-local coordinates are KiCad style: millimetres, origin at the hex
  centre, +x to the right, +y DOWN (towards the Uno's power/analog header when
  the module sits on the shield).
* "Arduino coordinates" are the classic Uno drawing coordinates: millimetres,
  origin at the board's lower-left corner (USB/DC-jack edge, power-header
  edge), +x to the right, +y UP (towards the digital header).  They are viewed
  from the TOP of the board.  Use ``uno_to_kicad`` to convert.

NOTE: KiCad's stock ``Module:Arduino_UNO_R3`` footprint is drawn as a bottom
(mirrored) view, so the shield deliberately does not use it.  Header positions
below come from the official Uno R3 dimensions (mils, converted to mm).
"""

import math

# ---------------------------------------------------------------------------
# Hex module
# ---------------------------------------------------------------------------
HEX_FLATS = 25.4                     # across flats (1.000")
HEX_R = HEX_FLATS / math.sqrt(3)     # centre-to-vertex (29.33 mm corner-to-corner)
HEX_CORNER_RADIUS = 1.0              # board-outline fillet at each vertex
HEX_GAP = 1.0                        # gap between neighbouring modules on the shield
HEX_PITCH = HEX_FLATS + HEX_GAP      # centre-to-centre of neighbours (26.4 mm)
ROW_PITCH = HEX_PITCH * math.sqrt(3) / 2   # honeycomb row spacing (22.86 mm)


def hex_vertices(r=HEX_R):
    """Pointy-top hexagon vertices (module-local, y down), clockwise from top."""
    return [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
            for a in (-90, -30, 30, 90, 150, 210)]


def inside_hex(x, y, margin=0.0):
    """True if (x, y) lies inside the hex shrunk by ``margin`` (mm)."""
    apothem = HEX_FLATS / 2 - margin
    for a in (0, 60, 120):
        nx, ny = math.cos(math.radians(a)), math.sin(math.radians(a))
        if abs(x * nx + y * ny) > apothem:
            return False
    return True


# ---------------------------------------------------------------------------
# Module bus: two keyed 1x5 2.54 mm headers
# ---------------------------------------------------------------------------
# Male headers on the module underside, female sockets on the shield.  Both
# rows are shifted +0.635 mm (a quarter pitch) in x, so a module rotated
# 180 degrees lands every pin 1.27 mm (half a pitch) away from the socket
# contacts and physically cannot be inserted.
BUS_ROW_Y = 9.9                      # J1 at y=-9.9 (top), J2 at y=+9.9 (bottom)
BUS_KEY_SHIFT = 0.635
BUS_PITCH = 2.54
BUS_PIN_X = [BUS_KEY_SHIFT + BUS_PITCH * (i - 2) for i in range(5)]   # pin 1 = left

BUS_J1 = ["GND", "+5V", "+3V3", "SDA", "SCL"]      # power + shared I2C (3.3 V logic)
BUS_J2 = ["GND", "AN", "PWM", "IO1", "IO2"]        # per-slot signals

BUS_LABELS = {"GND": "GND", "+5V": "5V", "+3V3": "3V3", "SDA": "SDA", "SCL": "SCL",
              "AN": "AN", "PWM": "PWM", "IO1": "IO1", "IO2": "IO2"}


def bus_pins():
    """[(header, pin_number, net, x, y)] for all 10 bus contacts, module-local."""
    out = []
    for hdr, y, nets in (("J1", -BUS_ROW_Y, BUS_J1), ("J2", BUS_ROW_Y, BUS_J2)):
        for i, net in enumerate(nets):
            out.append((hdr, i + 1, net, BUS_PIN_X[i], y))
    return out


# ---------------------------------------------------------------------------
# Arduino Uno R3 shield
# ---------------------------------------------------------------------------
UNO_W = 68.58
UNO_H = 53.34
MIL = 0.0254

# Board outline, Arduino coordinates (y up), from the Uno R3 drawing.
UNO_OUTLINE = [(0, 0), (66.04, 0), (66.04, 2.54), (68.58, 5.08), (68.58, 37.85),
               (66.04, 40.39), (66.04, 51.82), (64.52, 53.34), (0, 53.34)]

# Header rows (Arduino coordinates).  Each entry: (name, y, [(x, signal), ...])
UNO_HEADERS = [
    ("POWER", 2.54, list(zip([1100 * MIL + 2.54 * i for i in range(8)],
                             ["NC", "IOREF", "RESET", "+3V3", "+5V", "GND", "GND", "VIN"]))),
    ("ANALOG", 2.54, list(zip([2000 * MIL + 2.54 * i for i in range(6)],
                              ["A0", "A1", "A2", "A3", "A4", "A5"]))),
    ("DIGITAL_HI", 50.8, list(zip([740 * MIL + 2.54 * i for i in range(10)],
                                  ["SCL", "SDA", "AREF", "GND", "D13", "D12", "D11",
                                   "D10", "D9", "D8"]))),
    ("DIGITAL_LO", 50.8, list(zip([1800 * MIL + 2.54 * i for i in range(8)],
                                  ["D7", "D6", "D5", "D4", "D3", "D2", "D1", "D0"]))),
]

# Mounting holes kept on the shield (the 4th Uno hole at (15.24, 50.8) sits under
# slot 1's J1 socket and is omitted).
UNO_HOLES = [(550 * MIL, 100 * MIL), (2600 * MIL, 300 * MIL), (2600 * MIL, 1400 * MIL)]

# Tall parts on the Uno underneath the shield (Arduino coordinates, x0,y0,x1,y1).
# The shield rests ~11 mm above the Uno and sits on the USB jack, so no
# through-hole lead may protrude above these.
UNO_KEEPOUTS = {
    "USB-B jack": (-6.35, 32.38, 9.53, 43.81),
    "DC jack": (-1.90, 3.18, 11.43, 12.07),
    "ICSP header": (61.5, 22.0, 68.58, 31.5),
}

# Slot centres in Arduino coordinates: 2 + 2 honeycomb, gaps at bottom-left
# (over the DC jack) and top-right.
SLOT_X0 = 14.0
SLOT_ROW_BOTTOM = 15.24
SLOT_ROW_TOP = SLOT_ROW_BOTTOM + ROW_PITCH
SLOTS = {
    1: (SLOT_X0, SLOT_ROW_TOP),
    2: (SLOT_X0 + HEX_PITCH, SLOT_ROW_TOP),
    3: (SLOT_X0 + HEX_PITCH / 2, SLOT_ROW_BOTTOM),
    4: (SLOT_X0 + 1.5 * HEX_PITCH, SLOT_ROW_BOTTOM),
}

# Slot -> Arduino pin map.  D0/D1 stay free for USB programming/Serial; I2C is
# taken from the dedicated R3 SDA/SCL pins (A4/A5 on the Uno).
SLOT_PINS = {
    1: {"AN": "A0", "PWM": "D3", "IO1": "D2", "IO2": "D4"},
    2: {"AN": "A1", "PWM": "D5", "IO1": "D6", "IO2": "D7"},
    3: {"AN": "A2", "PWM": "D9", "IO1": "D10", "IO2": "D8"},
    4: {"AN": "A3", "PWM": "D11", "IO1": "D12", "IO2": "D13"},
}

# KiCad page placement: the shield's top-left corner lands here.
SHIELD_ORIGIN = (100.0, 100.0)
MODULE_ORIGIN = (100.0, 100.0)       # hex centre of every module board


def uno_to_kicad(x, y):
    """Arduino coordinates (y up) -> absolute KiCad coordinates (y down)."""
    return SHIELD_ORIGIN[0] + x, SHIELD_ORIGIN[1] + (UNO_H - y)

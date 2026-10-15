"""VIBEDUINO Arduino Uno R3 shield: four keyed hex-module slots."""

import os

import pcbnew

from . import art
from . import spec
from .kicad import PCB

SOCKET = ("Connector_PinSocket_2.54mm", "PinSocket_1x05_P2.54mm_Vertical")
PINHDR = "Connector_PinHeader_2.54mm"
WEBSITE = "www.allentronics.com.au"


def U(x, y):
    """Arduino coordinates (y up) -> shield-local KiCad coordinates (y down)."""
    return x, spec.UNO_H - y


def slot_centre(s):
    return U(*spec.SLOTS[s])


def build(out_dir):
    p = PCB("VIBEDUINO Shield for Arduino Uno R3", spec.SHIELD_ORIGIN)

    # ---- outline & holes ---------------------------------------------------
    p.polyline("Edge.Cuts", [U(x, y) for x, y in spec.UNO_OUTLINE], 0.05, closed=True)
    for i, (x, y) in enumerate(spec.UNO_HOLES):
        p.npth(f"H{i + 1}", *U(x, y), 3.2)

    # ---- Arduino headers (male, underside, pins into the Uno) ---------------
    refs = {"POWER": "J1", "ANALOG": "J2", "DIGITAL_HI": "J3", "DIGITAL_LO": "J4"}
    netname = {"SDA": "SDA_5V", "SCL": "SCL_5V", "RESET": "RESET"}
    for name, y, pins in spec.UNO_HEADERS:
        nets = [netname.get(sig, sig) if sig not in ("NC",) else None for _, sig in pins]
        nets = [n if n else f"unconnected-{name}-{i}" for i, n in enumerate(nets)]
        x0 = pins[0][0]
        n = len(pins)
        p.header_row(PINHDR, f"PinHeader_1x{n:02d}_P2.54mm_Vertical", refs[name],
                     f"Arduino {name}", x0, U(0, y)[1], nets, side="B")

    # ---- module slots --------------------------------------------------------
    for s in range(1, 5):
        cx, cy = slot_centre(s)
        x0 = cx + spec.BUS_PIN_X[0]
        j2 = ["GND"] + [spec.SLOT_PINS[s][k] for k in ("AN", "PWM", "IO1", "IO2")]
        for ref, val, yy, nets in ((f"J{s}01", f"SLOT{s} PWR/I2C", cy - spec.BUS_ROW_Y, spec.BUS_J1),
                                   (f"J{s}02", f"SLOT{s} SIGNALS", cy + spec.BUS_ROW_Y, j2)):
            fp = p.header_row(*SOCKET, ref, val, x0, yy, nets)
            # Neighbouring slots' sockets sit 0.72 mm apart (see assembly.verify_fit);
            # replace the library's generous courtyard with body + 0.25 mm.
            for g in list(fp.GraphicalItems()):
                if g.GetLayer() == pcbnew.F_CrtYd:
                    fp.Remove(g)
            p._fp_rect(fp, (-1.52, -1.52, 1.52, 11.68), pcbnew.F_CrtYd, 0.05)
        _slot_art(p, s, cx, cy)

    # ---- I2C level shifter (Uno 5 V <-> 3.3 V module bus) --------------------
    # BSS138 bidirectional shifter: gate=3V3, source=3V3 side, drain=5V side.
    # Lives in the open top-right gap so students can see it.
    sot = ("Package_TO_SOT_SMD", "SOT-23")
    r06 = ("Resistor_SMD", "R_0603_1608Metric")
    c06 = ("Capacitor_SMD", "C_0603_1608Metric")
    p.footprint(*r06, "R1", "4.7k", 57.7, 5.6, 0, pads={"1": "+3V3", "2": "SDA"})
    p.footprint(*r06, "R3", "10k", 61.5, 5.6, 0, pads={"1": "+5V", "2": "SDA_5V"})
    p.footprint(*sot, "Q1", "BSS138", 59.6, 8.7, 0, pads={"1": "+3V3", "2": "SDA", "3": "SDA_5V"})
    p.footprint(*sot, "Q2", "BSS138", 59.6, 12.7, 0, pads={"1": "+3V3", "2": "SCL", "3": "SCL_5V"})
    p.footprint(*r06, "R2", "4.7k", 57.7, 15.9, 0, pads={"1": "+3V3", "2": "SCL"})
    p.footprint(*r06, "R4", "10k", 61.5, 15.9, 0, pads={"1": "+5V", "2": "SCL_5V"})
    p.footprint(*c06, "C2", "100nF", 57.7, 18.2, 0, pads={"1": "+3V3", "2": "GND"})
    p.footprint(*c06, "C3", "100nF", 61.5, 18.2, 0, pads={"1": "+5V", "2": "GND"})

    # ---- Qwiic / STEMMA QT expansion port (3.3 V I2C), top entry in the open gap
    p.footprint("Connector_JST", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", "J5",
                "QWIIC", 60.0, 22.2, 0,
                pads={"1": "GND", "2": "+3V3", "3": "SDA", "4": "SCL", "MP": "GND"})

    # ---- Allentronics mark, reset button, power LED, bulk cap (bottom-left gap) --
    p.footprint("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", "SW1", "RESET", 7.0, 34.4, 0,
                pads={"1": "RESET", "2": "GND"})
    p.footprint("LED_SMD", "LED_0603_1608Metric", "D1", "GREEN", 3.6, 40.4, 0,
                pads={"1": "GND", "2": "PWR_LED"})
    p.footprint(*r06, "R5", "1k", 7.6, 40.4, 0, pads={"1": "+5V", "2": "PWR_LED"})
    p.footprint("Capacitor_SMD", "CP_Elec_6.3x5.4", "C1", "100uF 10V", 7.0, 46.6, 0,
                pads={"1": "+5V", "2": "GND"})

    _branding(p)
    path = os.path.join(out_dir, "vibeduino-shield.kicad_pcb")
    p.save(path)
    return path


def _slot_art(p, s, cx, cy):
    """Silkscreen: slot outline, number and the slot's Arduino pin map."""
    verts = [(cx + x, cy + y) for x, y in spec.hex_vertices(spec.HEX_R - 0.15)]
    p.polyline("F.SilkS", verts, 0.15, closed=True)
    p.text(str(s), cx - 6.6, cy, "F.SilkS", 4.0, thick=0.6)
    m = spec.SLOT_PINS[s]
    rows = [("AN", m["AN"]), ("PWM", m["PWM"] + "~"), ("IO1", m["IO1"] + ("~" if m["IO1"] in ("D6", "D10") else "")),
            ("IO2", m["IO2"])]
    for i, (k, v) in enumerate(rows):
        yy = cy - 3.3 + i * 2.2
        p.text(k, cx - 0.4, yy, "F.SilkS", 1.0, h="right", thick=0.15)
        p.text(v, cx + 0.4, yy, "F.SilkS", 1.0, h="left", thick=0.2, bold=True)
    # Pin labels just inside each socket row.
    j2 = ["GND", m["AN"], m["PWM"], m["IO1"], m["IO2"]]
    for i, x in enumerate(spec.BUS_PIN_X):
        p.text(spec.BUS_LABELS[spec.BUS_J1[i]], cx + x, cy - spec.BUS_ROW_Y + 2.3, "F.SilkS", 0.8,
               thick=0.15)
        p.text(j2[i], cx + x, cy + spec.BUS_ROW_Y - 2.3, "F.SilkS", 0.8, thick=0.15)


def _branding(p):
    # Top-right gap: VIBEDUINO wordmark running up beside the level shifter.
    art.place(p, art.wordmark("VIBEDUINO", width=16.0), 54.9, 12.0, "F.SilkS", rot=90)
    p.text("QWIIC", 64.4, 22.2, "F.SilkS", 0.8, thick=0.15, rot=90)
    # Bottom-left gap: Allentronics mark + reset / power.
    art.place(p, art.logo("icon", height=5.0), 4.8, 28.4, "F.SilkS")
    p.text("RESET", 7.0, 38.0, "F.SilkS", 0.8, thick=0.15)
    p.text("PWR", 3.6, 41.9, "F.SilkS", 0.8, thick=0.15)

    # Underside, between the socket pin rows (y 5.3/25.1 and 28.2/48.0):
    # band 1 = logo lock-up, band 2 = slot map + website.
    art.place(p, art.logo("full", width=44.0, min_line=0.18), 34.3, 10.6, "B.SilkS")
    art.place(p, art.wordmark("VIBEDUINO", width=28.0), 34.3, 18.0, "B.SilkS")
    p.text("SHIELD FOR ARDUINO UNO R3", 34.3, 22.2, "B.SilkS", 1.2, bold=True)
    p.text("SLOT  AN   PWM   IO1   IO2", 34.3, 31.0, "B.SilkS", 1.0, thick=0.18)
    for s in range(1, 5):
        m = spec.SLOT_PINS[s]
        p.text(f" {s}    {m['AN']:>3s}  {m['PWM']:>4s}  {m['IO1']:>4s}  {m['IO2']:>4s}", 34.3,
               31.0 + 1.7 * s, "B.SilkS", 1.0, thick=0.15)
    p.text("I2C SDA/SCL shared, 3.3 V logic. D0/D1 free for USB.", 34.3, 40.6,
           "B.SilkS", 0.8, thick=0.15)
    p.text(WEBSITE, 34.3, 43.2, "B.SilkS", 1.0, thick=0.18)
    p.text("REV A", 58.0, 45.0, "B.SilkS", 0.8, thick=0.15)
    # Fab overlay: tall Uno parts the shield sits over.
    for label, (x0, y0, x1, y1) in spec.UNO_KEEPOUTS.items():
        a, b = U(x0, y1), U(x1, y0)
        p.polyline("B.Fab", [a, (b[0], a[1]), b, (a[0], b[1])], 0.1, closed=True)
        p.text(f"UNO {label}: no THT leads", (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "B.Fab", 0.6)


def pours(p):
    pts = [U(x, y) for x, y in spec.UNO_OUTLINE]
    for layer in ("F.Cu", "B.Cu"):
        p.zone("GND", layer, pts)


def check_keepouts(path):
    """No plated through-hole lead may sit above the Uno's USB/DC jacks or ICSP header."""
    board = pcbnew.LoadBoard(path)
    ox, oy = spec.SHIELD_ORIGIN
    bad = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                continue
            x = pcbnew.ToMM(pad.GetPosition().x) - ox
            y = spec.UNO_H - (pcbnew.ToMM(pad.GetPosition().y) - oy)
            r = pcbnew.ToMM(max(pad.GetSize().x, pad.GetSize().y)) / 2
            for label, (x0, y0, x1, y1) in spec.UNO_KEEPOUTS.items():
                if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
                    bad.append((fp.GetReference(), pad.GetNumber(), label))
    return bad

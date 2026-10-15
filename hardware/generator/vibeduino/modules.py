"""VIBEDUINO hex modules.

Every module shares the same outline (1" hex), the same keyed 10-pin bus
(J1 + J2 male headers on the underside) and the same branding.  Each module
function below only adds its own circuit and top-side labels.
"""

import math

import pcbnew

from . import art
from . import spec
from .kicad import PCB

R0603 = ("Resistor_SMD", "R_0603_1608Metric")
C0603 = ("Capacitor_SMD", "C_0603_1608Metric")
C0805 = ("Capacitor_SMD", "C_0805_2012Metric")
LED0603 = ("LED_SMD", "LED_0603_1608Metric")
HDR = ("Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical")
WEBSITE = "www.allentronics.com.au"


def _no_silk(fp):
    """Small passives carry no silkscreen (dense boards; refs live on the fab layer)."""
    for g in list(fp.GraphicalItems()):
        if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.GetClass() != "MTEXT":
            fp.Remove(g)
    return fp


class Module:
    def __init__(self, key, name, title, desc, signals):
        self.key, self.name, self.title, self.desc = key, name, title, desc
        self.signals = signals            # bus signal -> what the module does with it
        self.pcb = PCB(f"VIBEDUINO {title} module", spec.MODULE_ORIGIN)
        self.bom = []

    # ------------------------------------------------------------ primitives
    def part(self, lib_name, ref, value, x, y, rot=0, side="F", pads=None, note=""):
        lib, name = lib_name
        pads = {k: v for k, v in (pads or {}).items() if v}
        fp = self.pcb.footprint(lib, name, ref, value, x, y, rot, side, pads)
        self.bom.append(dict(ref=ref, value=value, footprint=f"{lib}:{name}", side=side, note=note))
        return fp

    def R(self, ref, value, x, y, a, b, rot=0, side="F", fp=R0603):
        return _no_silk(self.part(fp, ref, value, x, y, rot, side, {"1": a, "2": b}))

    def C(self, ref, value, x, y, a, b, rot=0, side="F", fp=C0603):
        return _no_silk(self.part(fp, ref, value, x, y, rot, side, {"1": a, "2": b}))

    def silk(self, s, x, y, size=0.8, **kw):
        return self.pcb.text(s, x, y, "F.SilkS", size, **kw)

    def wordmark(self, x, y, width, layer="F.SilkS", rot=0, text="VIBEDUINO"):
        art.place(self.pcb, art.wordmark(text, width=width), x, y, layer, rot)

    def icon(self, x, y, size, layer="F.SilkS"):
        art.place(self.pcb, art.logo("icon", height=size), x, y, layer)

    # ---------------------------------------------------------- common parts
    def common(self, bus_labels=True):
        p = self.pcb
        # Board outline: pointy-top hexagon with filleted corners.
        r, rc = spec.HEX_R, spec.HEX_CORNER_RADIUS
        verts = spec.hex_vertices(r)
        d = rc / math.tan(math.radians(60))     # tangent distance for a 120deg corner
        for i, v in enumerate(verts):
            nxt = verts[(i + 1) % 6]
            ux, uy = (nxt[0] - v[0]) / r, (nxt[1] - v[1]) / r
            a = (v[0] + ux * d, v[1] + uy * d)
            b = (nxt[0] - ux * d, nxt[1] - uy * d)
            p.line("Edge.Cuts", a, b, 0.05)
            # fillet at nxt
            nn = verts[(i + 2) % 6]
            wx, wy = (nn[0] - nxt[0]) / r, (nn[1] - nxt[1]) / r
            c = (nxt[0] + wx * d, nxt[1] + wy * d)
            mx, my = nxt[0], nxt[1]
            k = rc / math.sin(math.radians(60))    # vertex -> fillet centre
            dist = math.hypot(mx, my)
            cxr, cyr = mx - mx / dist * k, my - my / dist * k
            mid = (cxr + mx / dist * rc, cyr + my / dist * rc)
            p.arc("Edge.Cuts", b, mid, c, 0.05)
        # Keyed bus headers, mounted on the underside, pins pointing down.
        p.header_row(*HDR, "J1", "BUS PWR/I2C", spec.BUS_PIN_X[0], -spec.BUS_ROW_Y,
                     spec.BUS_J1, side="B")
        p.header_row(*HDR, "J2", "BUS SIGNALS", spec.BUS_PIN_X[0], spec.BUS_ROW_Y,
                     spec.BUS_J2, side="B")
        self.bom.append(dict(ref="J1,J2", value="1x05 2.54mm male header",
                             footprint="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
                             side="B", note="mount on underside, pins down"))
        # The header plastic overhangs the hex near the vertices; drop the library
        # silk outline (it would be clipped by the board edge) and mark pin 1.
        for fp in p.board.GetFootprints():
            if fp.GetReference() in ("J1", "J2"):
                for g in list(fp.GraphicalItems()):
                    if g.GetLayer() == pcbnew.B_SilkS and g.GetClass() != "MTEXT":
                        fp.Remove(g)
        for yy in (-spec.BUS_ROW_Y, spec.BUS_ROW_Y):
            x = spec.BUS_PIN_X[0] - 1.45
            p.poly("B.SilkS", [(x - 0.75, yy - 0.55), (x, yy), (x - 0.75, yy + 0.55)])
        # Bus labels on the underside, next to each header.
        for hdr, num, net, x, y in spec.bus_pins() if bus_labels else []:
            p.text(spec.BUS_LABELS[net], x, y * 0.80, "B.SilkS", 0.8, thick=0.15)

    def reserve_brand(self, x0, y0, x1, y1):
        """Keep the autorouter's vias out of the area where the underside logo goes."""
        self.pcb.keepout([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], tracks=False, vias=True,
                         pour=False, name="logo")

    def finalize(self):
        """Freerouting will not start a route on bus pin 5 (0.4 mm from the board
        edge); give a used pin-5 net a short locked stub towards the centre."""
        board = self.pcb.board
        counts = {}
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                counts[pad.GetNetname()] = counts.get(pad.GetNetname(), 0) + 1
        ends = set()
        for t in board.GetTracks():
            ends.add((t.GetStart().x, t.GetStart().y))
            ends.add((t.GetEnd().x, t.GetEnd().y))
        x = spec.BUS_PIN_X[4]
        for y, net in ((-spec.BUS_ROW_Y, spec.BUS_J1[4]), (spec.BUS_ROW_Y, spec.BUS_J2[4])):
            pos = self.pcb.p(x, y)
            if counts.get(net, 0) > 1 and (pos.x, pos.y) not in ends:
                self.pcb.track([(x, y), (x, y * 0.83)], net, "F.Cu", width=0.25)

    # ----------------------------------------------------- underside branding
    def _bottom_obstacles(self):
        obs = []
        ox, oy = spec.MODULE_ORIGIN

        def rect(bb, m):
            return (pcbnew.ToMM(bb.GetLeft()) - ox - m, pcbnew.ToMM(bb.GetTop()) - oy - m,
                    pcbnew.ToMM(bb.GetRight()) - ox + m, pcbnew.ToMM(bb.GetBottom()) - oy + m)
        for fp in self.pcb.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetDrillSize().x > 0 or pad.IsOnLayer(pcbnew.B_Cu):
                    obs.append(rect(pad.GetBoundingBox(), 0.3))
            if fp.GetReference() not in ("J1", "J2"):
                cy = fp.GetCourtyard(pcbnew.B_CrtYd)
                if cy.OutlineCount():
                    obs.append(rect(cy.BBox(), 0.15))
        for t in self.pcb.board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                obs.append(rect(t.GetBoundingBox(), 0.3))
        for d in self.pcb.board.GetDrawings():
            if d.GetLayer() == pcbnew.B_SilkS and d.GetClass() == "PCB_TEXT" and \
                    abs(pcbnew.ToMM(d.GetPosition().y) - oy) < 7.5:
                obs.append(rect(d.GetBoundingBox(), 0.3))
        return obs

    def _text_size(self, s, size, bold=False, thick=0.15):
        t = pcbnew.PCB_TEXT(self.pcb.board)
        t.SetText(s)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        t.SetTextThickness(pcbnew.FromMM(size * 0.2 if bold else thick))
        bb = t.GetBoundingBox()
        return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())

    def bottom_branding(self):
        """Auto-place the Allentronics lock-up, website, VIBEDUINO mark and module
        name on the underside, steering around through-hole pads and bottom parts."""
        p = self.pcb
        obstacles = self._bottom_obstacles()

        def fits(r):
            x0, y0, x1, y1 = r
            if y0 < -7.1 or y1 > 7.1:
                return False
            if not all(spec.inside_hex(x, y, 0.7) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))):
                return False
            return not any(x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1 for b in obstacles)

        def find(w, h, px, py):
            cands = sorted(((i / 4, j / 4) for i in range(-48, 49) for j in range(-29, 30)),
                           key=lambda c: (c[0] - px) ** 2 + 2.5 * (c[1] - py) ** 2)
            for cx, cy in cands:
                if fits((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)):
                    obstacles.append((cx - w / 2 - .35, cy - h / 2 - .35, cx + w / 2 + .35, cy + h / 2 + .35))
                    return cx, cy
            return None

        # 1) logo lock-up: icon + ALLENTRONICS + EDUCATION SERVICES
        edu_w, edu_h = self._text_size("EDUCATION SERVICES", 0.8)
        done = False
        for s in (1.0, 0.92):
            ih, ww = 4.6 * s, 14.6 * s
            wm = art.logo("wordmark", width=ww)
            wh = art.size_of(wm)[1]
            colw = max(ww, edu_w)
            w, h = ih + 0.6 + colw, ih
            at = find(w, h, 0, -0.6)
            if at:
                cx, cy = at
                # Underside: lay the lock-up out mirrored so it reads icon-first from below.
                x1 = cx + w / 2
                art.place(p, art.logo("icon", height=ih), x1 - ih / 2, cy, "B.SilkS")
                tx = x1 - ih - 0.6 - colw / 2
                art.place(p, wm, tx, cy - h / 2 + wh / 2 + 0.35, "B.SilkS")
                p.text("EDUCATION SERVICES", tx, cy + h / 2 - edu_h / 2 - 0.2, "B.SilkS", 0.8, thick=0.15)
                done = True
                break
        if not done:     # compact one-line: small icon, wordmark over EDUCATION SERVICES
            ih, ww = 2.5, 11.0
            wm = art.logo("wordmark", width=ww)
            wh = art.size_of(wm)[1]
            colw = max(ww, edu_w)
            w, h = ih + 0.5 + colw, max(ih, wh + 0.25 + edu_h)
            at = find(w, h, 0, -0.6)
            if at:
                cx, cy = at
                x1 = cx + w / 2
                art.place(p, art.logo("icon", height=ih), x1 - ih / 2, cy, "B.SilkS")
                tx = x1 - ih - 0.5 - colw / 2
                art.place(p, wm, tx, cy - h / 2 + wh / 2, "B.SilkS")
                p.text("EDUCATION SERVICES", tx, cy + h / 2 - edu_h / 2, "B.SilkS", 0.8, thick=0.15)
                done = True
        for ih, ww in ((4.0, 9.4), (3.4, 8.0)):
            if done:
                break
            wm = art.logo("wordmark", width=ww)
            wh = art.size_of(wm)[1]
            e1w, e1h = self._text_size("EDUCATION", 0.8)
            w, h = max(ww, e1w), ih + 0.5 + wh + 0.45 + 2 * e1h + 0.3
            at = find(w, h, 0, 0)
            if at:
                cx, cy = at
                y = cy - h / 2
                art.place(p, art.logo("icon", height=ih), cx, y + ih / 2, "B.SilkS")
                y += ih + 0.5
                art.place(p, wm, cx, y + wh / 2, "B.SilkS")
                y += wh + 0.45
                p.text("EDUCATION", cx, y + e1h / 2, "B.SilkS", 0.8, thick=0.15)
                p.text("SERVICES", cx, y + 1.5 * e1h + 0.3, "B.SilkS", 0.8, thick=0.15)
                done = True
        if not done:
            raise RuntimeError(f"{self.name}: no room for the Allentronics logo on the underside")
        # 2) website
        ww_, wh_ = self._text_size(WEBSITE, 0.8)
        at = find(ww_, wh_, 0, 5.0)
        if at:
            p.text(WEBSITE, at[0], at[1], "B.SilkS", 0.8, thick=0.15)
        else:
            at = find(wh_, ww_, 9.5, 0)
            if at:
                p.text(WEBSITE, at[0], at[1], "B.SilkS", 0.8, thick=0.15, rot=90)
        # 3) VIBEDUINO + module name
        for width in (11.0, 8.0):
            vb = art.wordmark("VIBEDUINO", width=width)
            vw, vh = art.size_of(vb)
            at = find(vw, vh, 0, -4.6)
            if at:
                art.place(p, vb, at[0], at[1], "B.SilkS")
                break
        label = f"{self.name} MODULE"
        nw, nh = self._text_size(label, 0.9, bold=True)
        at = find(nw, nh, 0, 3.3)
        if at:
            p.text(label, at[0], at[1], "B.SilkS", 0.9, bold=True)


# ---------------------------------------------------------------------------
# Module definitions
# ---------------------------------------------------------------------------

def pot():
    m = Module("pot", "POT", "Potentiometer",
               "10k rotary potentiometer (Alps RK09K) - wiper on AN, 0..5 V.",
               {"AN": "wiper voltage 0-5 V (analogRead)"})
    m.common()
    m.part(("Potentiometer_THT", "Potentiometer_Alps_RK09K_Single_Vertical"), "RV1",
           "10k lin", -7.5, -2.5, pads={"1": "GND", "2": "AN", "3": "+5V", "MP": "GND"},
           note="Alps RK09K1110A0J or equiv, 9 mm, vertical shaft")
    m.C("C1", "100nF", -10.6, 0.0, "AN", "GND", rot=90)
    m.silk("POTENTIOMETER", 0, -7.85, 1.0, bold=True)
    m.wordmark(0, 7.85, 11.0)
    m.icon(9.1, 0.4, 5.2)
    return m


def oled():
    m = Module("oled", "OLED", "OLED Display",
               "0.66\" 64x48 SSD1306 OLED (I2C 0x3C, 3.3 V). Portrait mounting.",
               {"SDA": "I2C data", "SCL": "I2C clock"})
    m.common()
    # Panel footprint derived from SparkFun's Qwiic Micro OLED (CC BY-SA 4.0)
    # "OLED-0.66-64X48" package, rotated so the FPC fold sits on the left.
    # FPC pad n (module coords): x=-4.2, y = 8.775 - 0.65*(n-1); 0.35 x 2.0 mm.
    net = {1: "GND", 2: "C2P", 3: "C2N", 4: "C1P", 5: "C1N", 6: "+3V3", 7: "GND", 8: "+3V3",
           9: "+3V3", 10: "GND", 12: "OLED_RES", 13: "OLED_SA0", 16: "SCL", 17: "SDA",
           18: "SDA", 24: "IREF", 25: "VCOMH", 26: "VCC", 27: "GND", 28: "GND"}
    pads = [dict(num=n, x=0.0, y=8.775 - 0.65 * (n - 1), w=2.0, h=0.35, net=net.get(n))
            for n in range(1, 29)]
    pads += [dict(num="", x=-3.4, y=s * 8.375, w=0.8, h=0.8, kind="npth", shape="circle",
                  drill=0.8) for s in (-1, 1)]
    # glass (folded over the pads), FPC fold tab and active area, footprint-local
    gx0, gx1, gy = -4.8, 13.2, 9.25
    fab = [("F.Fab", [(gx0, -gy), (gx1, -gy), (gx1, gy), (gx0, gy), (gx0, -gy)]),
           ("F.Fab", [(gx0, -5.65), (gx0 - 2.3, -5.65), (gx0 - 2.3, 5.65), (gx0, 5.65)]),
           ("F.Fab", [(1.04, -6.62), (11.1, -6.62), (11.1, 6.8), (1.04, 6.8), (1.04, -6.62)])]
    c = 0.05
    crt = [(gx0 - c, -gy - c), (gx1 + c, -gy - c), (gx1 + c, gy + c), (gx0 - c, gy + c),
           (gx0 - c, 5.65 + c), (gx0 - 2.3 - c, 5.65 + c), (gx0 - 2.3 - c, -5.65 - c),
           (gx0 - c, -5.65 - c)]
    m.pcb.custom_footprint("DS1", "OLED 0.66in 64x48 SSD1306", -4.2, 0.0, pads=pads,
                           courtyard=crt, fab=fab,
                           fpid="VIBEDUINO:OLED_0.66in_64x48_FPC28")
    # Pre-routed fan-out: a stub east from every used pad to a via, vias staggered
    # over two columns (the 0.3 mm gaps between FPC pads cannot pass a track).
    for n, nn in net.items():
        if n in (1, 28):                 # outer GND pads touch the bus GND pins directly
            continue
        y = 8.775 - 0.65 * (n - 1)
        vx = -2.55 if n % 2 else -1.7
        m.pcb.track([(-3.4, y), (vx, y)], nn)
        m.pcb.via(vx, y, nn)
    m.bom.append(dict(ref="DS1", value="0.66in 64x48 OLED, SSD1306, 28-pin FPC",
                      footprint="VIBEDUINO:OLED_0.66in_64x48_FPC28", side="F",
                      note="same panel as SparkFun LCD-22495; glass folds over pads"))
    # Support circuit on the underside (values from the SparkFun reference design),
    # ordered top-to-bottom like the FPC nets they serve so the routing stays planar.
    B = "B"
    m.R("R3", "10k", 2.6, 0.9, "OLED_SA0", "GND", side=B)
    m.part(("Jumper", "SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"), "JP1", "ADDR 0x3D",
           5.8, 0.45, side=B, pads={"1": "OLED_SA0", "2": "+3V3"}, note="bridge for I2C 0x3D")
    m.R("R2", "10k", 2.6, 2.45, "+3V3", "OLED_RES", side=B)
    m.C("C7", "1uF", 5.8, 2.45, "OLED_RES", "GND", side=B)
    m.C("C4", "1uF", 2.6, 4.0, "+3V3", "GND", side=B)
    m.C("C6", "100nF", 5.8, 4.0, "+3V3", "GND", side=B)
    m.C("C2", "1uF", 2.6, 5.55, "C1P", "C1N", side=B)
    m.C("C3", "1uF", 2.6, 7.1, "C2P", "C2N", side=B)
    m.R("R1", "390k", 2.6, -3.6, "IREF", "GND", side=B)
    m.C("C5", "4.7uF", 2.6, -5.15, "VCOMH", "GND", side=B)
    m.C("C1", "2.2uF 16V", 2.6, -6.7, "VCC", "GND", side=B)
    m.pcb.text("0x3D", 8.0, 0.45, "B.SilkS", 0.8, thick=0.15, rot=90)
    # Pre-routed long nets: SDA/SCL loop round the parts on B.Cu to J1 pins 4/5,
    # 3V3 drops from J1 pin 3 on F.Cu (under the glass) to a via in the 3V3 cluster.
    j4, j5, j3 = spec.BUS_PIN_X[3], spec.BUS_PIN_X[4], spec.BUS_PIN_X[2]
    yj = -spec.BUS_ROW_Y
    m.pcb.track([(-2.55, -1.625), (-1.7, -2.275)], "SDA", "B.Cu")
    m.pcb.track([(-1.7, -2.275), (8.3, -2.275), (8.3, -7.6), (j4, -7.6), (j4, yj)], "SDA", "B.Cu")
    m.pcb.track([(-1.7, -0.975), (9.3, -0.975), (9.3, -8.4), (j5, -8.4), (j5, yj)], "SCL", "B.Cu")
    m.pcb.track([(j3, yj), (j3, 0.0), (0.4, 0.4), (0.4, 3.5)], "+3V3", "F.Cu", width=0.3)
    m.pcb.via(0.4, 3.5, "+3V3")
    m.pcb.track([(-2.55, 3.575), (-1.7, 4.225), (-1.7, 5.525)], "+3V3", "B.Cu", width=0.3)
    m.pcb.track([(-1.7, 4.225), (-0.6, 4.225), (0.4, 3.5)], "+3V3", "B.Cu", width=0.3)
    # Top: only a slim strip right of the glass is visible.
    m.silk("OLED", 10.85, 2.4, 1.0, rot=90, bold=True)
    m.icon(10.85, -4.0, 2.9)
    return m


def dpad():
    m = Module("dpad", "D-PAD", "Push Button D-Pad",
               "4-way D-pad on AN (resistor ladder) + centre 'A' button on IO1 (active low).",
               {"AN": "UP 0 / RIGHT ~93 / DOWN ~254 / LEFT ~512 / none 1023 (analogRead)",
                "IO1": "A button, LOW when pressed"})
    m.common()
    sw = ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A")
    note = "XKB TS-1187A-B-A-B 5.1x5.1 mm tactile"
    m.part(sw, "SW1", "UP", 0, -5.8, pads={"1": "AN", "2": "GND"}, note=note)
    m.part(sw, "SW2", "RIGHT", 7.8, 0, pads={"1": "DP_R", "2": "GND"}, note=note)
    m.part(sw, "SW3", "DOWN", 0, 5.8, pads={"1": "DP_D", "2": "GND"}, note=note)
    m.part(sw, "SW4", "LEFT", -7.8, 0, pads={"1": "DP_L", "2": "GND"}, note=note)
    m.part(sw, "SW5", "A", 0, 0, pads={"1": "IO1", "2": "GND"}, note=note)
    # ladder + pull-ups, standing vertically in the two left quadrants
    for ref, val, x, y, n1, n2 in (("R1", "10k", -10.4, -5.0, "+5V", "AN"),
                                   ("R2", "1k", -8.8, -5.0, "AN", "DP_R"),
                                   ("R3", "3.3k", -7.2, -5.0, "AN", "DP_D"),
                                   ("R4", "10k", -5.6, -5.0, "AN", "DP_L"),
                                   ("R5", "10k", -9.6, 5.0, "+5V", "IO1")):
        m.R(ref, val, x, y, n1, n2, rot=90)
    m.C("C1", "100nF", -7.6, 5.0, "AN", "GND", rot=90)
    m.wordmark(7.7, -7.4, 6.4)
    m.icon(7.7, -4.7, 3.2)
    m.reserve_brand(-10.1, -2.9, 10.1, 1.9)
    m.silk("D-PAD", 7.6, 4.4, 1.0, bold=True)
    m.silk("AN: arrows", 7.6, 5.9, 0.8, thick=0.15)
    m.silk("IO1: A (ctr)", 7.6, 7.2, 0.8, thick=0.15)
    return m


def led():
    m = Module("led", "LED", "LED (traffic light)",
               "Red / yellow / green 5 mm LEDs in a row on PWM / IO1 / IO2 (HIGH = on).",
               {"PWM": "red LED", "IO1": "yellow LED", "IO2": "green LED"})
    m.common()
    t5 = ("LED_THT", "LED_D5.0mm")
    for ref, col, x, sig, rref in (("D1", "RED", -7.3, "PWM", "R1"), ("D2", "YELLOW", 0.0, "IO1", "R2"),
                                   ("D3", "GREEN", 7.3, "IO2", "R3")):
        m.part(t5, ref, f"5mm {col} diffused", x - 1.27, -0.6, pads={"1": "GND", "2": f"LED_{col[0]}"},
               note="5 mm diffused THT LED")
        m.R(rref, "470R", x, 4.1, sig, f"LED_{col[0]}")
        m.silk(col[0], x, -5.1, 1.2, bold=True)
        m.silk(sig, x, 5.7, 0.8, thick=0.15)
    m.silk("LED", 0, -7.85, 1.0, bold=True)
    m.wordmark(0, 7.85, 9.5)
    return m


def servo():
    m = Module("servo", "SERVO", "Servo Motor",
               "Two 3-pin servo headers: A on PWM, B on IO1 (220R series), 100uF bulk cap.",
               {"PWM": "servo A signal", "IO1": "servo B signal"})
    m.common()
    h3 = ("Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical")
    m.part(h3, "J3", "SERVO A", -8.2, -2.54, pads={"1": "SRV_A", "2": "+5V", "3": "GND"},
           note="1x03 2.54mm male header")
    m.part(h3, "J4", "SERVO B", -2.9, -2.54, pads={"1": "SRV_B", "2": "+5V", "3": "GND"},
           note="1x03 2.54mm male header")
    m.R("R1", "220R", -8.2, -5.7, "PWM", "SRV_A")
    m.R("R2", "220R", -2.9, -5.7, "IO1", "SRV_B")
    m.part(("Capacitor_SMD", "CP_Elec_5x5.4"), "C1", "100uF 10V", 6.4, 0.3,
           pads={"1": "+5V", "2": "GND"}, note="SMD electrolytic 5x5.4 mm")
    m.C("C2", "100nF", 6.4, 4.4, "+5V", "GND")
    for x in (-10.4, -5.55):
        m.silk("S", x, -2.54, 0.8, bold=True)
        m.silk("+", x, 0.0, 0.8, bold=True)
        m.silk("-", x, 2.54, 0.8, bold=True)
    m.silk("A", -8.2, 5.0, 1.0, bold=True)
    m.silk("B", -2.9, 5.0, 1.0, bold=True)
    m.silk("SERVO", 6.4, -4.6, 1.0, bold=True)
    m.wordmark(-1.0, 7.9, 9.5)
    return m


def temp():
    m = Module("temp", "TEMP", "Temperature Sensor",
               "MCP9700A analog sensor on AN (500 mV @ 0 C, 10 mV/C, same maths as TMP36) "
               "+ red alert LED on PWM.",
               {"AN": "temperature: C = (mV - 500) / 10", "PWM": "alert LED"})
    m.common()
    m.part(("Package_TO_SOT_SMD", "SOT-23"), "U1", "MCP9700A-E/TT", 0.0, -5.6,
           pads={"1": "+5V", "2": "AN", "3": "GND"}, note="Microchip MCP9700A, SOT-23")
    m.C("C1", "100nF", -3.6, -5.6, "+5V", "GND", rot=90)
    m.part(LED0603, "D1", "RED", 6.2, 5.6, pads={"1": "GND", "2": "LED_A"})
    m.R("R1", "1k", 6.2, 3.6, "PWM", "LED_A", rot=180)
    m.silk("ALERT", 8.6, 4.6, 0.8, thick=0.15, rot=90)
    # thermometer pictogram
    p = m.pcb
    p.circle("F.SilkS", (-6.5, 3.6), 1.3, 0.2, filled=True)
    p.polyline("F.SilkS", [(-7.2, 2.6), (-7.2, -3.4)], 0.2)
    p.polyline("F.SilkS", [(-5.8, 2.6), (-5.8, -3.4)], 0.2)
    p.arc("F.SilkS", (-7.2, -3.4), (-6.5, -4.1), (-5.8, -3.4), 0.2)
    p.line("F.SilkS", (-6.5, 2.4), (-6.5, -1.0), 0.45)
    for i, yy in enumerate((-2.8, -1.6, -0.4, 0.8, 2.0)):
        p.line("F.SilkS", (-5.4, yy), (-4.6 if i % 2 else -4.9, yy), 0.15)
    m.silk("TEMP", 2.2, -1.5, 1.4, bold=True)
    m.silk("°C", 2.2, 0.8, 1.0, bold=True)
    m.wordmark(0, 7.9, 9.5)
    m.icon(9.3, -2.3, 3.6)
    return m


def buzzer():
    m = Module("buzzer", "BUZZER", "Buzzer",
               "12 mm passive magnetic buzzer driven by an NPN from PWM - use tone().",
               {"PWM": "tone() output"})
    m.common()
    m.part(("Buzzer_Beeper", "Buzzer_12x9.5RM7.6"), "BZ1", "12mm passive 5V", -6.3, 0.0,
           pads={"1": "+5V", "2": "BZ_N"}, note="passive magnetic transducer, 12x9.5 mm, 7.6 mm pitch")
    m.part(("Package_TO_SOT_SMD", "SOT-23"), "Q1", "MMBT3904", 7.6, 0.0,
           pads={"1": "BZ_B", "2": "GND", "3": "BZ_N"})
    m.part(("Diode_SMD", "D_SOD-323"), "D1", "1N4148WS", 7.6, -3.6,
           pads={"1": "+5V", "2": "BZ_N"}, note="flyback diode")
    m.R("R1", "1k", 7.6, 3.2, "PWM", "BZ_B")
    m.R("R2", "10k", 7.6, 5.1, "BZ_B", "GND")
    m.silk("BUZZER", -2.5, -7.85, 1.0, bold=True)
    m.wordmark(-1.5, 7.9, 9.5)
    m.silk("+", -6.3, -2.4, 1.0, bold=True)
    return m


def light():
    m = Module("light", "LIGHT", "Light Sensor",
               "LDR + 10k divider on AN: brighter light = higher reading.",
               {"AN": "light level (analogRead, bright = high)"})
    m.common()
    m.part(("OptoDevice", "R_LDR_5.1x4.3mm_P3.4mm_Vertical"), "R1", "GL5528 LDR", -1.7, -1.0,
           pads={"1": "+5V", "2": "AN"}, note="5 mm CdS LDR (GL5528); see RoHS note")
    m.R("R2", "10k", 6.6, 2.6, "AN", "GND", rot=90)
    m.C("C1", "100nF", 8.4, 2.6, "AN", "GND", rot=90)
    p = m.pcb
    # sun pictogram around the sensor
    p.circle("F.SilkS", (0, -1.0), 3.6, 0.2)
    for k in range(12):
        a = math.radians(k * 30)
        r0, r1 = 4.3, 5.4 if k % 2 == 0 else 4.9
        p.line("F.SilkS", (r0 * math.cos(a), -1.0 + r0 * math.sin(a)),
               (r1 * math.cos(a), -1.0 + r1 * math.sin(a)), 0.2)
    m.silk("LIGHT", -6.8, 5.6, 1.0, bold=True)
    m.wordmark(0, 7.9, 9.5)
    m.icon(9.2, -3.0, 3.6)
    return m


def rgb():
    m = Module("rgb", "RGB", "RGB LEDs",
               "3x WS2812B addressable RGB LEDs, data in on PWM (Adafruit NeoPixel / FastLED).",
               {"PWM": "NeoPixel data in"})
    m.common()
    ws = ("LED_SMD", "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm")
    chain = ["RGB_DIN", "RGB_D1", "RGB_D2", None]
    for i, x in enumerate((-7.5, 0.0, 7.5)):
        m.part(ws, f"D{i + 1}", "WS2812B", x, -0.3, rot=180,
               pads={"1": "+5V", "2": chain[i + 1], "3": "GND", "4": chain[i]},
               note="WS2812B-5050")
        m.C(f"C{i + 1}", "100nF", x, 4.0, "+5V", "GND")
        m.silk(str(i), x, -4.2, 1.0, bold=True)
    m.R("R1", "330R", -7.5, 5.9, "PWM", "RGB_DIN")
    m.C("C4", "10uF", 7.5, 5.9, "+5V", "GND", fp=C0805)
    m.silk("RGB", 0, -7.85, 1.0, bold=True)
    m.wordmark(0, 7.85, 7.5)
    return m


def proto():
    m = Module("proto", "PROTO", "Prototyping",
               "Every bus pin broken out to a labelled pad + a 2.54 mm hole grid.",
               {s: "breakout pad" for s in ("AN", "PWM", "IO1", "IO2", "SDA", "SCL")})
    m.common(bus_labels=False)       # breakout pads are labelled on top
    pads = []
    for hdr, num, net, x, y in spec.bus_pins():
        yy = -7.4 if hdr == "J1" else 7.4
        pads.append(dict(num=f"{hdr}{num}", x=x, y=yy, w=1.6, h=1.6, kind="pth",
                         shape="circle", drill=0.9, net=net))
        m.silk(spec.BUS_LABELS[net], x, yy + (1.55 if hdr == "J1" else -1.55), 0.8, thick=0.15)
        m.pcb.track([(x, y), (x, yy)], net, "F.Cu", width=0.4)
    m.pcb.custom_footprint("TP1", "BUS BREAKOUT", 0, 0, pads=pads, fpid="VIBEDUINO:BusBreakout")
    grid = []
    k = 1
    for row in range(3):
        for col in range(8):
            grid.append(dict(num=f"G{k}", x=-8.89 + 2.54 * col, y=-2.54 + 2.54 * row, w=1.6,
                             h=1.6, kind="pth", shape="circle", drill=0.9))
            k += 1
    m.pcb.custom_footprint("PF1", "2.54 GRID", 0, 0, pads=grid, fpid="VIBEDUINO:ProtoGrid")
    m.silk("PROTO", -11.15, 0, 0.9, bold=True, rot=90)
    m.wordmark(11.15, 0, 7.5, rot=90)
    return m


ALL = [pot, oled, dpad, led, servo, temp, buzzer, light, rgb, proto]

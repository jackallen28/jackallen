"""Build kicad/circuitpath-keychain.kicad_pcb (unrouted) from design.py.

Run with the system python that ships pcbnew:  python3 build_pcb.py <out.kicad_pcb>
"""
import math
import os
import sys

sys.path.append("/usr/lib/python3/dist-packages")
sys.path.insert(0, os.path.dirname(__file__))
import pcbnew  # noqa: E402
import design as D  # noqa: E402

MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def load_fp(spec):
    lib, name = spec.split(":")
    fp = pcbnew.FootprintLoad("%s/%s.pretty" % (D.FP_LIB, lib), name)
    if fp is None:
        raise SystemExit("footprint not found: " + spec)
    return fp


def usb_a_plug():
    """4 gold fingers on the top face of the board tongue (see docs for the order and the mirror switch)."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetReference("J1")
    fp.SetValue("USB-A plug (PCB fingers)")
    fp.SetFPID(pcbnew.LIB_ID("CircuitPath", "USB_A_PCB_Plug"))
    # pin order across the plug width, VBUS D- D+ GND, centred on the board's centre line
    ys = [3.5, 1.0, -1.0, -3.5]
    widths = [2.0, 1.0, 1.0, 2.0]
    if D.USB_A_MIRROR:
        ys = [-y for y in ys]
    for n, (y, w) in enumerate(zip(ys, widths), 1):
        pad = pcbnew.PAD(fp)
        pad.SetNumber(str(n))
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.F_Mask)
        pad.SetLayerSet(ls)
        pad.SetSize(pcbnew.VECTOR2I(MM(7.5), MM(w)))
        fp.Add(pad)
        pad.SetPos0(P(4.75, y))
        pad.SetPosition(P(4.75, y))
    return fp


def isp_pads():
    """Six round 0.9 mm pads on a 1.27 mm grid (Tag-Connect TC2030 layout, but no alignment holes)."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetReference("J3")
    fp.SetValue("ISP pads")
    fp.SetFPID(pcbnew.LIB_ID("CircuitPath", "ISP_Pads_2x3"))
    for n, (x, y) in enumerate(((-1.27, 0.635), (-1.27, -0.635), (0, 0.635), (0, -0.635), (1.27, 0.635), (1.27, -0.635)), 1):
        pad = pcbnew.PAD(fp)
        pad.SetNumber(str(n))
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.F_Mask)
        pad.SetLayerSet(ls)
        pad.SetSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9)))
        fp.Add(pad)
        pad.SetPos0(P(x, y))
        pad.SetPosition(P(x, y))
    return fp


def rounded_outline():
    """Edge.Cuts outline: USB-A tab on the left, rounded body."""
    t, h, tl, r, er, L, tr = D.TAB_W / 2, D.BODY_H / 2, D.TAB_L, D.CORNER_R, D.END_R, D.BODY_END, D.TIP_R
    segs = []

    def line(a, b):
        segs.append(("L", a, b))

    def arc(c, a, b):
        segs.append(("A", c, a, b))

    line((tr, -t), (tl, -t))
    # the plug meets the body exactly where the body's corner arc starts
    arc((tl + r, -h + r), (tl, -h + r), (tl + r, -h))
    line((tl + r, -h), (L - er, -h))
    arc((L - er, -h + er), (L - er, -h), (L, -h + er))
    line((L, -h + er), (L, h - er))
    arc((L - er, h - er), (L, h - er), (L - er, h))
    line((L - er, h), (tl + r, h))
    arc((tl + r, h - r), (tl + r, h), (tl, h - r))
    line((tl, h - r), (tl, t))
    line((tl, t), (tr, t))
    arc((tr, t - tr), (tr, t), (0, t - tr))
    line((0, t - tr), (0, -t + tr))
    arc((tr, -t + tr), (0, -t + tr), (tr, -t))
    return segs


def add_outline(board):
    layer = pcbnew.Edge_Cuts
    for s in rounded_outline():
        if s[0] == "L":
            if s[1] == s[2]:
                continue
            sh = pcbnew.PCB_SHAPE(board)
            sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
            sh.SetStart(P(*s[1]))
            sh.SetEnd(P(*s[2]))
        else:
            c, a, b = s[1], s[2], s[3]
            sh = pcbnew.PCB_SHAPE(board)
            sh.SetShape(pcbnew.SHAPE_T_ARC)
            # quarter arcs: pick the middle point so KiCad gets the right sweep
            a0 = math.atan2(a[1] - c[1], a[0] - c[0])
            b0 = math.atan2(b[1] - c[1], b[0] - c[0])
            d = (b0 - a0 + math.pi) % (2 * math.pi) - math.pi
            m0 = a0 + d / 2
            rr = math.hypot(a[0] - c[0], a[1] - c[1])
            mid = (c[0] + rr * math.cos(m0), c[1] + rr * math.sin(m0))
            sh.SetArcGeometry(P(*a), P(*mid), P(*b))
        sh.SetLayer(layer)
        sh.SetWidth(MM(0.1))
        board.Add(sh)
    # keyring hole
    x, y, d = D.KEYRING_HOLE
    c = pcbnew.PCB_SHAPE(board)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(P(x, y))
    c.SetEnd(P(x + d / 2, y))
    c.SetLayer(layer)
    c.SetWidth(MM(0.1))
    board.Add(c)


def add_text(board, text, x, y, rot, size, layer):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def usbc_data_ties(board):
    """The USB-C connector's D+ pins (A6, B6) and D- pins (A7, B7) are interleaved, so each pair must be joined by hand:
    D+ by a short diagonal across the gap between the two pad rows on the top, D- by vias just beyond the pad ends and a
    track on the back, so the two ties do not cross on the same layer."""
    j2 = board.FindFootprintByReference("J2")
    pad = {p.GetNumber(): p for p in j2.Pads() if p.GetNumber() in ("A6", "B6", "A7", "B7")}

    def pos(p):
        return pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), pcbnew.ToMM(p.GetSize().x) / 2

    def seg(a, b, layer, net):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(MM(0.2)); t.SetLayer(layer); t.SetNet(net)
        board.Add(t)

    def via(at, net):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(*at)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net)
        board.Add(v)

    for a, b in (("A6", "B6"), ("A7", "B7")):
        xa, ya, ha = pos(pad[a]); xb, yb, hb = pos(pad[b])
        left, right = ((xa, ya, ha), (xb, yb, hb)) if xa < xb else ((xb, yb, hb), (xa, ya, ha))
        net = pad[a].GetNet()
        if a == "A6":      # D+: inner ends of the two pads, across the gap, on the top layer; escape via past the right end
            seg((left[0] + left[2], left[1]), (right[0] - right[2], right[1]), pcbnew.F_Cu, net)
            lv = (left[0] - 0.72, left[1] + 0.05)              # escape via just short of the connector's peg keep-out
            seg((left[0], left[1]), lv, pcbnew.F_Cu, net); via(lv, net)
        else:              # D-: out past the outer ends, down to the back layer and across
            lo, ro = (left[0] - left[2], left[1]), (right[0] + right[2], right[1])
            lv, rv = (lo[0] - 0.55, lo[1]), (ro[0] + 0.55, ro[1])
            seg(lo, lv, pcbnew.F_Cu, net); seg(ro, rv, pcbnew.F_Cu, net)
            via(lv, net); via(rv, net)
            seg(lv, rv, pcbnew.B_Cu, net)


def edge_keepout(board, inset=0.35):
    """Copper keep-out band just inside the board outline (and around the keyring hole) so tracks, vias and pours stay clear of the edge."""
    from shapely.geometry import Polygon, Point, box
    pts = []
    for sgm in rounded_outline():
        if sgm[0] == "L":
            if sgm[1] != sgm[2]:
                pts.append(sgm[1])
        else:
            c, a, e = sgm[1], sgm[2], sgm[3]
            a0 = math.atan2(a[1] - c[1], a[0] - c[0]); b0 = math.atan2(e[1] - c[1], e[0] - c[0])
            d = (b0 - a0 + math.pi) % (2 * math.pi) - math.pi
            r = math.hypot(a[0] - c[0], a[1] - c[1])
            pts += [(c[0] + r * math.cos(a0 + d * k / 16), c[1] + r * math.sin(a0 + d * k / 16)) for k in range(17)]
    shape = Polygon(pts).buffer(0)
    hx, hy, hd = D.KEYRING_HOLE
    inner = shape.buffer(-inset).difference(Point(hx, hy).buffer(hd / 2 + inset))
    ring = box(-5, -20, 130, 20).difference(inner)
    parts = list(ring.geoms) if hasattr(ring, "geoms") else [ring]
    for poly in parts:
        z = pcbnew.ZONE(board)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowCopperPour(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetZoneName("edge keep-out")
        ol = z.Outline()
        ol.NewOutline()
        for x, y in list(poly.exterior.coords)[:-1]:
            ol.Append(MM(x), MM(y))
        for i, hole in enumerate(poly.interiors):
            ol.NewHole(0)
            for x, y in list(hole.coords)[:-1]:
                ol.Append(MM(x), MM(y), 0, i)
        board.Add(z)


def main(out):
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(D.BOARD_THICKNESS))
    ds.m_TrackMinWidth = MM(0.127)
    ds.m_MinClearance = MM(0.127)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(MM(0.15))
    nc.SetTrackWidth(MM(0.2))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))

    nets = {}

    def net(name):
        if name is None:
            return None
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    for p in D.PARTS:
        if p["fp"] == "CircuitPath:USB_A_PCB_Plug":
            fp = usb_a_plug()
        elif p["fp"] == "CircuitPath:ISP_Pads_2x3":
            fp = isp_pads()
        else:
            fp = load_fp(p["fp"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPosition(P(p["x"], p["y"]))
        if p["rot"]:
            fp.SetOrientationDegrees(p["rot"])
        board.Add(fp)
        if p["side"] == "B":
            fp.Flip(fp.GetPosition(), False)
        # hide silkscreen references on the many tiny parts so the board stays readable
        if p["fp"].startswith("LED_SMD") or p["ref"].startswith(("C", "R", "J")):
            fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        # attributes JLCPCB / pick-and-place reads
        if p["lcsc"] == "" or p["ref"] in ("J1",) or p["fp"].startswith(("CircuitPath:ISP", "LED_THT")):
            fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if (p["ref"], num) in D.PCB_NC:
                continue
            if num in p["pins"]:
                n = p["pins"][num]
                if n:
                    pad.SetNet(net(n))
            elif p["ref"] == "J2" and num == "":
                pad.SetNet(net("GND"))
        # LCSC part number as a field, so it travels with the board
        fp.SetProperties({"LCSC": p["lcsc"]})

    usbc_data_ties(board)
    edge_keepout(board)
    # USB-C: the shell/mount pads are all named S1 (already handled); NP holes need no net
    add_outline(board)
    for text, x, y, rot, size in D.SILK_TOP:
        add_text(board, text, x, y, rot, size, pcbnew.F_SilkS)
    for text, x, y, rot, size in D.SILK_BOT:
        add_text(board, text, x, y, rot, size, pcbnew.B_SilkS)
    add_text(board, "USB-C", 17.0, 7.0, 0, 1.0, pcbnew.F_SilkS)
    # BNTS logo from art/bnts-logo.svg as silkscreen (strong squares solid, pale squares outlined), turned to read bottom-to-top
    squares, lines = D.logo_shapes()
    for x0, y0, x1, y1, filled in squares:
        r = pcbnew.PCB_SHAPE(board)
        r.SetShape(pcbnew.SHAPE_T_RECT)
        r.SetStart(P(x0, y0)); r.SetEnd(P(x1, y1))
        r.SetLayer(pcbnew.F_SilkS)
        r.SetWidth(MM(0.0 if filled else 0.12))
        r.SetFilled(filled)
        board.Add(r)
    for text, x, y, h, w in lines:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetPosition(P(x, y)); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(w), MM(h))); t.SetTextThickness(MM(0.15))
        t.SetTextAngleDegrees(90); t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        board.Add(t)
    for text, x in D.LOGO_TEXT:
        add_text(board, text, x, 0.0, 90, 3.0, pcbnew.F_SilkS)

    pcbnew.SaveBoard(out, board)
    # purple mask / white silk / ENIG, written as a KiCad stackup so the 3D viewer and exports use it
    stack = """
    (stackup
      (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (color "Purple") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "core") (thickness 1.86) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "Bottom Solder Mask") (color "Purple") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
      (copper_finish "ENIG")
      (dielectric_constraints no)
    )"""
    txt = open(out).read()
    i = txt.index("(setup") + len("(setup")
    open(out, "w").write(txt[:i] + stack + txt[i:])
    print("wrote", out, "with", len(board.GetFootprints()), "footprints and", len(nets), "nets")


if __name__ == "__main__":
    main(sys.argv[1])

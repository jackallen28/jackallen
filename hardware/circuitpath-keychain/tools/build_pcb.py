"""Build kicad/circuitpath-keychain.kicad_pcb (unrouted) from design.py.

Run with the system python that ships pcbnew:  python3 build_pcb.py <out.kicad_pcb>
"""
import math
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
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
        if p["fp"].startswith("CircuitPath:"):
            fp = usb_a_plug()
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
        if p["lcsc"] == "" or p["ref"] in ("J1",) or p["fp"].startswith(("Connector:Tag", "LED_THT")):
            fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in p["pins"]:
                n = p["pins"][num]
                if n:
                    pad.SetNet(net(n))
            elif p["ref"] == "J2" and num == "":
                pad.SetNet(net("GND"))
        # LCSC part number as a field, so it travels with the board
        fp.SetProperties({"LCSC": p["lcsc"]})

    # USB-C: the shell/mount pads are all named S1 (already handled); NP holes need no net
    add_outline(board)
    for text, x, y, rot, size in D.SILK_TOP:
        add_text(board, text, x, y, rot, size, pcbnew.F_SilkS)
    for text, x, y, rot, size in D.SILK_BOT:
        add_text(board, text, x, y, rot, size, pcbnew.B_SilkS)
    add_text(board, "USB-A", 6.0, -9.2, 0, 1.0, pcbnew.F_SilkS)
    add_text(board, "USB-C", 18.0, 7.0, 0, 1.0, pcbnew.F_SilkS)
    add_text(board, "RESET: short pads 5-6", D.MCU_XY[0] + 10.0, 11.6, 0, 0.7, pcbnew.F_SilkS)

    pcbnew.SaveBoard(out, board)
    print("wrote", out, "with", len(board.GetFootprints()), "footprints and", len(nets), "nets")


if __name__ == "__main__":
    main(sys.argv[1])

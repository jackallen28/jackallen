"""Thin helpers around the KiCad 7 ``pcbnew`` Python API.

All coordinates passed to ``PCB`` methods are *local* millimetres relative to
the board origin given at construction time (KiCad orientation, y down).
"""

import datetime
import json
import math
import os

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

FPLIB = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

LAYER = {
    "F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
    "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS,
    "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab,
    "F.CrtYd": pcbnew.F_CrtYd, "B.CrtYd": pcbnew.B_CrtYd,
    "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask,
    "Edge.Cuts": pcbnew.Edge_Cuts, "Dwgs.User": pcbnew.Dwgs_User,
    "Cmts.User": pcbnew.Cmts_User,
}

# JLCPCB-friendly 2-layer rules (1.6 mm FR4, 1 oz).
RULES = dict(clearance=0.15, track=0.2, power_track=0.4, via_d=0.6, via_drill=0.3,
             min_track=0.15, min_via_d=0.5, min_drill=0.3, edge_clearance=0.3,
             hole_clearance=0.25, hole_to_hole=0.25, min_annular=0.13)
POWER_NETS = ["GND", "+5V", "+3V3", "VCC", "VBUS"]


def V(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def angle(deg):
    return pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T)


class PCB:
    def __init__(self, title, origin, rev="A"):
        self.board = pcbnew.BOARD()
        self.ox, self.oy = origin
        self.nets = {}
        self.title = title
        tb = self.board.GetTitleBlock()
        tb.SetTitle(title)
        tb.SetCompany("Allentronics Education Services - www.allentronics.com.au")
        tb.SetRevision(rev)
        tb.SetDate(datetime.date.today().isoformat())
        self._setup_rules()

    # ------------------------------------------------------------------ basics
    def p(self, x, y):
        return V(self.ox + x, self.oy + y)

    def local(self, vec):
        return ToMM(vec.x) - self.ox, ToMM(vec.y) - self.oy

    def net(self, name):
        if name is None:
            return None
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def _setup_rules(self):
        ds = self.board.GetDesignSettings()
        ds.m_MinClearance = FromMM(RULES["clearance"])
        ds.m_TrackMinWidth = FromMM(RULES["min_track"])
        ds.m_ViasMinSize = FromMM(RULES["min_via_d"])
        ds.m_MinThroughDrill = FromMM(RULES["min_drill"])
        ds.m_CopperEdgeClearance = FromMM(RULES["edge_clearance"])
        ds.m_HoleClearance = FromMM(RULES["hole_clearance"])
        ds.m_HoleToHoleMin = FromMM(RULES["hole_to_hole"])
        ds.m_ViasMinAnnularWidth = FromMM(RULES["min_annular"])
        ds.m_MinSilkTextHeight = FromMM(0.8)
        if hasattr(ds, "m_MinResolvedSpokes"):
            ds.m_MinResolvedSpokes = 1
        ns = ds.m_NetSettings
        d = ns.m_DefaultNetClass
        d.SetClearance(FromMM(RULES["clearance"]))
        d.SetTrackWidth(FromMM(RULES["track"]))
        d.SetViaDiameter(FromMM(RULES["via_d"]))
        d.SetViaDrill(FromMM(RULES["via_drill"]))
        pw = pcbnew.NETCLASS("Power")
        pw.SetClearance(FromMM(RULES["clearance"]))
        pw.SetTrackWidth(FromMM(RULES["power_track"]))
        pw.SetViaDiameter(FromMM(0.8))
        pw.SetViaDrill(FromMM(0.4))
        ns.m_NetClasses["Power"] = pw

    # ------------------------------------------------------------- footprints
    def footprint(self, lib, name, ref, value, x, y, rot=0, side="F", pads=None,
                  show_value=False):
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
        if fp is None:
            raise RuntimeError(f"footprint {lib}:{name} not found")
        fp.SetFPIDAsString(f"{lib}:{name}")
        return self._place(fp, ref, value, x, y, rot, side, pads, show_value)

    def _place(self, fp, ref, value, x, y, rot, side, pads, show_value):
        fp.SetReference(ref)
        fp.SetValue(value)
        self.board.Add(fp)
        fp.SetPosition(self.p(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), False)
        # Reference designators live on the fab layer: the silkscreen is kept for
        # branding and user-facing labels.
        fab = pcbnew.B_Fab if side == "B" else pcbnew.F_Fab
        fp.Reference().SetLayer(fab)
        fp.Reference().SetTextSize(V(0.5, 0.5))
        fp.Reference().SetTextThickness(FromMM(0.08))
        fp.Value().SetLayer(fab)
        fp.Value().SetVisible(show_value)
        for item in fp.GraphicalItems():
            if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and \
                    item.GetClass() == "MTEXT":
                item.SetVisible(False)
        if pads:
            for pad in fp.Pads():
                n = pad.GetNumber()
                if n in pads:
                    pad.SetNet(self.net(pads[n]))
        return fp

    def pad_xy(self, fp, number):
        for pad in fp.Pads():
            if pad.GetNumber() == str(number):
                return self.local(pad.GetPosition())
        raise KeyError(number)

    def header_row(self, lib, name, ref, value, x0, y, nets, side="F", step=2.54):
        """Place a 1xN header so pin i sits at (x0 + i*step, y)."""
        for rot in (90, -90, 0, 180):
            fp = self.footprint(lib, name, ref, value, x0, y, rot, side,
                                pads={str(i + 1): n for i, n in enumerate(nets)})
            x1, y1 = self.pad_xy(fp, 1)
            x2, y2 = self.pad_xy(fp, 2)
            if abs(x1 - x0) < 1e-3 and abs(y1 - y) < 1e-3 and \
                    abs(x2 - (x0 + step)) < 1e-3 and abs(y2 - y) < 1e-3:
                return fp
            self.board.Remove(fp)
        raise RuntimeError("could not orient header")

    def custom_footprint(self, ref, value, x, y, rot=0, side="F", pads=(), courtyard=None,
                         fab=(), silk=(), fpid="VIBEDUINO:custom"):
        """pads: dicts(num, x, y, w, h, kind smd|npth|pth, shape rect|circle|roundrect, drill, net).
        courtyard: (x0, y0, x1, y1) local to the footprint.  fab/silk: polylines."""
        fp = pcbnew.FOOTPRINT(self.board)
        fp.SetFPIDAsString(fpid)
        for pd in pads:
            pad = pcbnew.PAD(fp)
            pad.SetNumber(str(pd.get("num", "")))
            shape = {"rect": pcbnew.PAD_SHAPE_RECT, "circle": pcbnew.PAD_SHAPE_CIRCLE,
                     "roundrect": pcbnew.PAD_SHAPE_ROUNDRECT,
                     "oval": pcbnew.PAD_SHAPE_OVAL}[pd.get("shape", "rect")]
            pad.SetShape(shape)
            kind = pd.get("kind", "smd")
            if kind == "smd":
                pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
                pad.SetLayerSet(pad.SMDMask())
            elif kind == "npth":
                pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
                pad.SetLayerSet(pad.UnplatedHoleMask())
                pad.SetDrillSize(V(pd["drill"], pd["drill"]))
            else:
                pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
                pad.SetLayerSet(pad.PTHMask())
                pad.SetDrillSize(V(pd["drill"], pd["drill"]))
            pad.SetSize(V(pd["w"], pd["h"]))
            if shape == pcbnew.PAD_SHAPE_ROUNDRECT:
                pad.SetRoundRectRadiusRatio(0.25)
            pad.SetPosition(V(pd["x"], pd["y"]))
            pad.SetPos0(V(pd["x"], pd["y"]))
            fp.Add(pad)
        if courtyard and len(courtyard) == 4 and not isinstance(courtyard[0], tuple):
            self._fp_rect(fp, courtyard, pcbnew.F_CrtYd, 0.05)
        elif courtyard:
            self._fp_poly(fp, list(courtyard) + [courtyard[0]], pcbnew.F_CrtYd, 0.05)
        for layer, pts in fab:
            self._fp_poly(fp, pts, LAYER[layer], 0.1)
        for layer, pts in silk:
            self._fp_poly(fp, pts, LAYER[layer], 0.15)
        fp = self._place(fp, ref, value, x, y, rot, side,
                         {str(pd.get("num")): pd["net"] for pd in pads if pd.get("net")}, False)
        return fp

    def _fp_rect(self, fp, r, layer, w):
        x0, y0, x1, y1 = r
        self._fp_poly(fp, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], layer, w)

    def _fp_poly(self, fp, pts, layer, w):
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            s = pcbnew.FP_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(layer)
            s.SetWidth(FromMM(w))
            s.SetStart0(V(xa, ya))
            s.SetEnd0(V(xb, yb))
            s.SetDrawCoord()
            fp.Add(s)

    def npth(self, ref, x, y, drill):
        return self.custom_footprint(ref, "NPTH", x, y, pads=[dict(num="", x=0, y=0, w=drill, h=drill,
                                                                  kind="npth", shape="circle",
                                                                  drill=drill)],
                                     courtyard=(-drill / 2 - .25, -drill / 2 - .25,
                                                drill / 2 + .25, drill / 2 + .25),
                                     fpid="VIBEDUINO:NPTH")

    # --------------------------------------------------------------- graphics
    def _shape(self, kind, layer, width):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(kind)
        s.SetLayer(LAYER[layer] if isinstance(layer, str) else layer)
        s.SetWidth(FromMM(width))
        self.board.Add(s)
        return s

    def line(self, layer, a, b, width=0.15):
        s = self._shape(pcbnew.SHAPE_T_SEGMENT, layer, width)
        s.SetStart(self.p(*a))
        s.SetEnd(self.p(*b))
        return s

    def polyline(self, layer, pts, width=0.15, closed=False):
        pts = list(pts) + ([pts[0]] if closed else [])
        for a, b in zip(pts, pts[1:]):
            self.line(layer, a, b, width)

    def arc(self, layer, start, mid, end, width=0.15):
        s = self._shape(pcbnew.SHAPE_T_ARC, layer, width)
        s.SetArcGeometry(self.p(*start), self.p(*mid), self.p(*end))
        return s

    def circle(self, layer, c, r, width=0.15, filled=False):
        s = self._shape(pcbnew.SHAPE_T_CIRCLE, layer, width)
        s.SetCenter(self.p(*c))
        s.SetEnd(self.p(c[0] + r, c[1]))
        s.SetFilled(filled)
        return s

    def poly(self, layer, pts, filled=True, width=0.0):
        s = self._shape(pcbnew.SHAPE_T_POLY, layer, width)
        s.SetPolyPoints([self.p(x, y) for x, y in pts])
        s.SetFilled(filled)
        return s

    def polyset(self, layer, polys):
        """polys: [(outer_pts, [hole_pts, ...])] in local mm.  Holes are supported
        by fracturing into keyhole outlines (silkscreen artwork)."""
        sps = pcbnew.SHAPE_POLY_SET()
        for outer, holes in polys:
            idx = sps.NewOutline()
            for x, y in outer:
                sps.Append(FromMM(self.ox + x), FromMM(self.oy + y), idx)
            for h in holes:
                hidx = sps.NewHole(idx)
                for x, y in h:
                    sps.Append(FromMM(self.ox + x), FromMM(self.oy + y), idx, hidx)
        sps.Simplify(pcbnew.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
        sps.Fracture(pcbnew.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
        for i in range(sps.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(sps.Outline(i))
            s = self._shape(pcbnew.SHAPE_T_POLY, layer, 0)
            s.SetPolyShape(one)
            s.SetFilled(True)

    def text(self, s, x, y, layer="F.SilkS", size=1.0, thick=None, rot=0, h="center",
             v="center", bold=False, mirror=None):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetLayer(LAYER[layer])
        t.SetTextSize(V(size, size))
        t.SetTextThickness(FromMM(thick if thick else max(0.15, size * (0.2 if bold else 0.15))))
        t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "center": pcbnew.GR_TEXT_H_ALIGN_CENTER,
                           "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}[h])
        t.SetVertJustify({"top": pcbnew.GR_TEXT_V_ALIGN_TOP, "center": pcbnew.GR_TEXT_V_ALIGN_CENTER,
                          "bottom": pcbnew.GR_TEXT_V_ALIGN_BOTTOM}[v])
        t.SetPosition(self.p(x, y))
        t.SetTextAngle(angle(rot))
        if mirror is None:
            mirror = layer.startswith("B.")
        t.SetMirrored(mirror)
        self.board.Add(t)
        return t

    # ----------------------------------------------------------------- copper
    def track(self, pts, net, layer="F.Cu", width=0.2, locked=True):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(self.p(*a))
            t.SetEnd(self.p(*b))
            t.SetWidth(FromMM(width))
            t.SetLayer(LAYER[layer])
            t.SetNet(self.net(net))
            t.SetLocked(locked)
            self.board.Add(t)

    def via(self, x, y, net, d=0.6, drill=0.3, locked=True):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(self.p(x, y))
        v.SetWidth(FromMM(d))
        v.SetDrill(FromMM(drill))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(net))
        v.SetLocked(locked)
        self.board.Add(v)

    # ------------------------------------------------------------------ zones
    def zone(self, net, layer, pts, priority=0, clearance=0.3, min_width=0.2,
             thermal_gap=0.3, spoke=0.4):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(LAYER[layer])
        if net:
            z.SetNet(self.net(net))
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(FromMM(self.ox + x), FromMM(self.oy + y))
        z.SetAssignedPriority(priority)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetLocalClearance(FromMM(clearance))
        z.SetMinThickness(FromMM(min_width))
        z.SetThermalReliefGap(FromMM(thermal_gap))
        z.SetThermalReliefSpokeWidth(FromMM(spoke))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        self.board.Add(z)
        return z

    def keepout(self, pts, layers=("F.Cu", "B.Cu"), tracks=True, vias=True, pour=True,
                footprints=False, name=""):
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(LAYER[l])
        z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(tracks)
        z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowCopperPour(pour)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(footprints)
        if name:
            z.SetZoneName(name)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(FromMM(self.ox + x), FromMM(self.oy + y))
        self.board.Add(z)
        return z

    # ------------------------------------------------------------------- save
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pcbnew.SaveBoard(path, self.board)
        write_netclass_patterns(path.replace(".kicad_pcb", ".kicad_pro"))
        prl = path.replace(".kicad_pcb", ".kicad_prl")
        if os.path.exists(prl):
            os.remove(prl)


def write_netclass_patterns(pro_path):
    """KiCad 7 assigns net classes by pattern in the project file."""
    with open(pro_path) as f:
        pro = json.load(f)
    pats = [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
    pro["net_settings"]["netclass_patterns"] = pats
    rs = pro["board"]["design_settings"]["rule_severities"]
    for k in ("lib_footprint_issues", "lib_footprint_mismatch"):
        rs[k] = "ignore"
    rules = pro["board"]["design_settings"]["rules"]
    rules["min_copper_edge_clearance"] = RULES["edge_clearance"]
    rules["min_silk_clearance"] = 0.0
    rules["min_text_height"] = 0.8
    rules["min_text_thickness"] = 0.12
    rules["min_resolved_spokes"] = 1
    with open(pro_path, "w") as f:
        json.dump(pro, f, indent=2)


def wrap(board, origin):
    """PCB helper bound to an already-loaded board (e.g. after autorouting)."""
    p = PCB.__new__(PCB)
    p.board = board
    p.ox, p.oy = origin
    p.nets = {n.GetNetname(): n for n in board.GetNetsByName().values()} \
        if hasattr(board, "GetNetsByName") else {}
    p.title = board.GetTitleBlock().GetTitle()
    return p

"""Places and autoroutes the Water Valve Controller boards (2 layers).

Run from the hardware folder after tools/gen_schematic.py:
    python3 tools/gen_pcb.py tht      # through-hole board  -> WaterValveController.kicad_pcb
    python3 tools/gen_pcb.py smd      # surface-mount board -> smd/WaterValveController-SMD.kicad_pcb

Options:
    --place-only        place the parts and stop (no routing), for checking a layout
    --jar PATH          Freerouting jar, 1.9 or 2.x (default: $FREEROUTING_JAR)
    --passes N          Freerouting optimisation passes (default 100)

Needs KiCad 7 (the pcbnew Python module and kicad-cli) and Java 17+ for Freerouting.
The placement for each board is in tools/pcb_layout.py.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

os.environ.setdefault('KICAD7_FOOTPRINT_DIR', '/usr/share/kicad/footprints')
import pcbnew  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_layout  # noqa: E402
from sexp import parse  # noqa: E402

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
KICAD_FP = '/usr/share/kicad/footprints'
OX, OY = 100.0, 60.0           # board top-left corner on the KiCad page (mm)
VARIANTS = {
    'tht': dict(dir=HW, project='WaterValveController'),
    'smd': dict(dir=os.path.join(HW, 'smd'), project='WaterValveController-SMD'),
}

# Design rules: fine for any low-cost 2-layer service (JLCPCB, PCBWay, OSH Park ...)
RULES = dict(clearance=0.2, track=0.25, via=0.6, via_drill=0.3, edge=0.3)
NETCLASSES = {
    # name: (track width mm, clearance mm, nets). Widths are for 1 oz (35 um) copper and a 10 C rise
    # (IPC-2221, outer layer): 2.0 mm carries about 4 A and 1.0 mm about 2.4 A. The fuse is 2 A.
    'Power12V': (2.0, 0.3, ['+12V', '/12V_IN', '/12V_FUSED', '/SOL_OUT']),   # supply and valve current
    'Power5V': (1.0, 0.25, ['+5V']),                     # Nano, ESP32, sensor (about 0.6 A peak)
    'Ground': (1.0, 0.25, ['GND']),                      # plus a GND pour on both layers
}

F = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(F(OX + x), F(OY + y))


# ---------------------------------------------------------------------------
# Netlist
# ---------------------------------------------------------------------------
def read_netlist(sch):
    with tempfile.TemporaryDirectory() as d:
        xml = os.path.join(d, 'net.xml')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, sch],
                       check=True, capture_output=True)
        root = ET.parse(xml).getroot()
    comps = {}
    for c in root.find('components'):
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        if 'exclude_from_board' in props:
            continue
        comps[c.get('ref')] = dict(
            value=c.findtext('value'), footprint=c.findtext('footprint'),
            path=c.find('sheetpath').get('tstamps') + c.findtext('tstamps'),
            in_bom='exclude_from_bom' not in props)
    nets = {}
    for n in root.find('nets'):
        nodes = [(x.get('ref'), x.get('pin')) for x in n.findall('node') if x.get('ref') in comps]
        if nodes:
            nets[n.get('name')] = nodes
    return comps, nets


# ---------------------------------------------------------------------------
# Custom footprint: Arduino Nano on female headers
# ---------------------------------------------------------------------------
def make_nano_footprint():
    """Module:Arduino_Nano with its courtyard round the two pin rows only, so low parts
    (flat resistors, 0805s) can sit underneath a socketed Nano."""
    src = open(os.path.join(KICAD_FP, 'Module.pretty', 'Arduino_Nano.kicad_mod')).read()
    pads = '\n'.join(line for line in src.splitlines() if line.strip().startswith('(pad '))
    fab = '\n'.join(line for line in src.splitlines() if '"F.Fab"' in line and line.strip().startswith('(fp_line'))
    model = src[src.index('  (model'):src.rindex(')')]

    def rect(x1, y1, x2, y2, layer, w):
        return ''.join(f'  (fp_line (start {a} {b}) (end {c} {d}) (layer "{layer}") (width {w}))\n'
                       for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)))

    out = ('(footprint "Arduino_Nano_Socketed" (version 20221018) (generator pcbnew)\n'
           '  (layer "F.Cu")\n'
           '  (descr "Arduino Nano on 2 x 15 female headers. Courtyard covers the pin rows only: parts under '
           'the Nano must be low (flat resistors, SMD), see the Fab outline for the module body")\n'
           '  (tags "Arduino Nano socket")\n  (attr through_hole)\n'
           '  (fp_text reference "REF**" (at 7.62 -2.6) (layer "F.SilkS")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n'
           '  (fp_text value "Arduino_Nano_Socketed" (at 8.89 19.05 90) (layer "F.Fab")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n'
           '  (fp_text user "${REFERENCE}" (at 6.35 19.05 90) (layer "F.Fab")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n'
           '  (fp_text user "USB" (at 7.62 40.4) (layer "F.Fab")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n')
    out += rect(-1.4, -1.4, 1.4, 36.96, 'F.SilkS', 0.12)
    out += rect(13.84, -1.4, 16.64, 36.96, 'F.SilkS', 0.12)
    out += '  (fp_line (start -1.9 -1.4) (end -1.9 1.4) (layer "F.SilkS") (width 0.12))\n'   # pin 1 mark
    out += rect(-1.55, -1.55, 1.55, 37.11, 'F.CrtYd', 0.05)
    out += rect(13.69, -1.55, 16.79, 37.11, 'F.CrtYd', 0.05)
    out += fab.replace('(width 0.1)', '(width 0.1)') + '\n' + pads + '\n' + model + ')\n'
    d = os.path.join(HW, 'WaterValve.pretty')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'Arduino_Nano_Socketed.kicad_mod'), 'w') as f:
        f.write(out)


def make_fuse_footprint():
    """Keystone 3557-2 holder for standard ATO/ATC blade fuses (catalogue page M47): four legs on a
    13.5 x 3.4 mm pattern, 1.6 mm holes; the body is 19.8 x 7.4 mm."""
    pads = ''.join(f'  (pad "{n}" thru_hole circle (at {x} {y}) (size 3 3) (drill 1.7) (layers "*.Cu" "*.Mask"))\n'
                   for n, x, y in (('1', 0, 0), ('1', 0, 3.4), ('2', 13.5, 0), ('2', 13.5, 3.4)))

    def rect(x1, y1, x2, y2, layer, w):
        return ''.join(f'  (fp_line (start {a} {b}) (end {c} {d}) (layer "{layer}") (width {w}))\n'
                       for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)))

    out = ('(footprint "Fuseholder_Blade_ATO_Keystone_3557-2" (version 20221018) (generator pcbnew)\n'
           '  (layer "F.Cu")\n'
           '  (descr "Keystone 3557-2 2-in-1 holder for standard ATO/ATC (and low-profile mini) blade fuses, '
           'https://www.keyelco.com/userAssets/file/M65p47.pdf")\n'
           '  (tags "fuse holder blade ATO ATC automotive")\n  (attr through_hole)\n'
           '  (fp_text reference "REF**" (at 6.75 -3.2) (layer "F.SilkS")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n'
           '  (fp_text value "Fuseholder_Blade_ATO_Keystone_3557-2" (at 6.75 6.6) (layer "F.Fab")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n'
           '  (fp_text user "${REFERENCE}" (at 6.75 1.7) (layer "F.Fab")\n'
           '    (effects (font (size 1 1) (thickness 0.15)))\n  )\n')
    out += rect(-3.15, -2.0, 16.65, 5.4, 'F.Fab', 0.1)
    out += rect(-3.27, -2.12, 16.77, 5.52, 'F.SilkS', 0.12)
    out += rect(-3.5, -2.35, 17.0, 5.75, 'F.CrtYd', 0.05)
    out += pads + ')\n'
    with open(os.path.join(HW, 'WaterValve.pretty', 'Fuseholder_Blade_ATO_Keystone_3557-2.kicad_mod'), 'w') as f:
        f.write(out)


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(HW, 'WaterValve.pretty') if lib == 'WaterValve' else os.path.join(KICAD_FP, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f'footprint not found: {fpid}')
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


# ---------------------------------------------------------------------------
# Board construction
# ---------------------------------------------------------------------------
EMPTY_BOARD = '(kicad_pcb (version 20221018) (generator pcbnew)\n  (general (thickness 1.6))\n  (paper "A4")\n)\n'


def new_board(path):
    # The net class patterns live in the project file; write them first so that pcbnew (and the
    # Specctra export) assign the power classes when the board is loaded.
    write_project_rules(path[:-len('.kicad_pcb')] + '.kicad_pro')
    with open(path, 'w') as f:
        f.write(EMPTY_BOARD)
    board = pcbnew.LoadBoard(path)
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_MinClearance = F(RULES['clearance'])
    ds.m_TrackMinWidth = F(0.2)
    ds.m_ViasMinSize = F(RULES['via'])
    ds.m_MinThroughDrill = F(RULES['via_drill'])
    ds.m_CopperEdgeClearance = F(RULES['edge'])
    ds.m_HoleClearance = F(0.25)
    ds.m_HoleToHoleMin = F(0.25)
    ds.m_SolderMaskMinWidth = 0
    ds.m_SolderMaskExpansion = F(0.05)
    ns = ds.m_NetSettings
    dflt = ns.m_DefaultNetClass
    dflt.SetTrackWidth(F(RULES['track']))
    dflt.SetClearance(F(RULES['clearance']))
    dflt.SetViaDiameter(F(RULES['via']))
    dflt.SetViaDrill(F(RULES['via_drill']))
    for name, (width, clear, _nets) in NETCLASSES.items():
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(F(width))
        nc.SetClearance(F(clear))
        nc.SetViaDiameter(F(0.8))
        nc.SetViaDrill(F(0.4))
        ns.m_NetClasses[name] = nc
    return board


def netclass_of(name):
    for cls, (_w, _c, nets) in NETCLASSES.items():
        if name in nets:
            return cls
    return None


def add_nets(board, nets):
    ns = board.GetDesignSettings().m_NetSettings
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        cls = netclass_of(name)
        if cls:
            ni.SetNetClass(ns.m_NetClasses[cls])


def add_footprints(board, comps, nets, place, project):
    pin_net = {node: name for name, nodes in nets.items() for node in nodes}
    missing = [r for r in comps if r not in place]
    if missing:
        raise SystemExit('no placement for: ' + ', '.join(sorted(missing)))
    for ref, c in sorted(comps.items()):
        x, y, rot = place[ref][:3]
        fp = load_fp(c['footprint'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.SetPath(pcbnew.KIID_PATH(c['path']))
        fp.SetProperty('Sheetname', '')
        fp.SetProperty('Sheetfile', project + '.kicad_sch')
        if not c['in_bom']:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
        board.Add(fp)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        if len(place[ref]) > 3 and place[ref][3] == 'tl':
            # (x, y) is the top-left corner of the courtyard rather than the footprint origin
            fp.BuildCourtyardCaches()
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            fp.Move(P(x, y) - pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
        for pad in fp.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(board.FindNet(name))
        for item in (fp.Reference(), fp.Value()):
            item.SetTextSize(pcbnew.VECTOR2I(F(0.8), F(0.8)))
            item.SetTextThickness(F(0.12))
        fp.Value().SetVisible(False)


def place_refs(board, w, h, avoid, labelled=()):
    """Puts each reference designator where it touches no pad, no other part's silkscreen and no
    other text: inside the part's own outline if it fits there, otherwise just outside it."""
    def box(x1, y1, x2, y2):
        return pcbnew.BOX2I(P(x1, y1), pcbnew.VECTOR2I(F(x2 - x1), F(y2 - y1)))

    def grown(bb, mm):
        bb = pcbnew.BOX2I(bb.GetOrigin(), bb.GetSize())
        bb.Inflate(F(mm))
        return bb

    fps = list(board.GetFootprints())
    pads = [(fp.GetReference(), grown(pad.GetBoundingBox(), 0.2)) for fp in fps for pad in fp.Pads()]
    silk = [(fp.GetReference(), grown(g.GetBoundingBox(), 0.05)) for fp in fps for g in fp.GraphicalItems()
            if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != 'FP_TEXT']
    taken = [grown(d.GetBoundingBox(), 0.25) for d in board.GetDrawings()
             if d.GetLayer() == pcbnew.F_SilkS and d.GetClass() == 'PCB_TEXT']
    taken += [box(*a) for a in avoid]
    inside = box(0.35, 0.35, w - 0.35, h - 0.35)
    hidden = []
    order = sorted(fps, key=lambda fp: -fp.GetArea() if hasattr(fp, 'GetArea') else 0)
    for fp in order:
        ref, t = fp.GetReference(), fp.Reference()
        if ref.startswith('H') or ref in labelled or not t.IsVisible():
            t.SetVisible(False)
            continue
        fp.BuildCourtyardCaches()
        cb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        cx, cy = cb.GetCenter().x, cb.GetCenter().y
        l, r, tp, bt = cb.GetLeft(), cb.GetRight(), cb.GetTop(), cb.GetBottom()
        done = False
        for size in (0.8,):
            t.SetTextSize(pcbnew.VECTOR2I(F(size), F(size)))
            t.SetTextThickness(F(size * 0.15))
            t.SetTextAngleDegrees(0)
            t.SetPosition(pcbnew.VECTOR2I(int(cx), int(cy)))
            t.ClearBoundingBoxCache()
            tw, th = t.GetBoundingBox().GetWidth() // 2, t.GetBoundingBox().GetHeight() // 2
            g = F(0.1)
            xs = [cx, l + tw, r - tw]
            ys = [cy, tp + tw, bt - tw]
            ys0 = [cy, tp + th, bt - th]
            cands = [(cx, cy, 0), (cx, cy, 90)]
            cands += [(x, tp - th - g, 0) for x in xs] + [(x, bt + th + g, 0) for x in xs]
            cands += [(l - th - g, y, 90) for y in ys] + [(r + th + g, y, 90) for y in ys]
            cands += [(l - tw - g, y, 0) for y in ys0] + [(r + tw + g, y, 0) for y in ys0]
            cands += [(x, tp + th + g, 0) for x in xs] + [(x, bt - th - g, 0) for x in xs]
            for x, y, ang in cands:
                t.SetTextAngleDegrees(ang)
                t.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                t.ClearBoundingBoxCache()
                bb = t.GetBoundingBox()
                if not inside.Contains(bb):
                    continue
                if any(bb.Intersects(p) for _r, p in pads):
                    continue
                if any(bb.Intersects(sb) for _o, sb in silk):
                    continue
                if any(bb.Intersects(tb) for tb in taken):
                    continue
                taken.append(grown(bb, 0.1))
                done = True
                break
            if done:
                break
        if not done:
            t.SetVisible(False)
            hidden.append(ref)
    return hidden


def seg(board, a, b, layer, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(F(width))
    board.Add(s)


def arc(board, start, mid, end, layer, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*start), P(*mid), P(*end))
    s.SetLayer(layer)
    s.SetWidth(F(width))
    board.Add(s)


def outline(board, w, h, r):
    e = pcbnew.Edge_Cuts
    seg(board, (r, 0), (w - r, 0), e)
    seg(board, (w, r), (w, h - r), e)
    seg(board, (w - r, h), (r, h), e)
    seg(board, (0, h - r), (0, r), e)
    k = r * (1 - math.sqrt(0.5))
    arc(board, (w - r, 0), (w - k, k), (w, r), e)
    arc(board, (w, h - r), (w - k, h - k), (w - r, h), e)
    arc(board, (r, h), (k, h - k), (0, h - r), e)
    arc(board, (0, r), (k, k), (r, 0), e)


def text(board, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, just='center', bold=False, bottom=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    if bottom:
        layer = pcbnew.B_SilkS
        t.SetMirrored(True)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(F(size), F(size)))
    t.SetTextThickness(F(size * (0.2 if bold else 0.15)))
    t.SetHorizJustify({'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                       'center': pcbnew.GR_TEXT_H_ALIGN_CENTER}[just])
    t.SetPosition(P(x, y))
    t.SetTextAngleDegrees(rot)
    board.Add(t)


def poly_zone(board, pts, layers):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    z.SetLayerSet(ls)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(F(OX + x), F(OY + y))
    board.Add(z)
    return z


def logo_area(board, x1, y1, x2, y2):
    """Keep tracks, vias and parts out of the logo area. The GND pour still fills it, so a
    silkscreen logo or text printed there sits on a flat surface."""
    z = poly_zone(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], [pcbnew.F_Cu, pcbnew.B_Cu])
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(True)
    z.SetDoNotAllowFootprints(True)
    z.SetDoNotAllowCopperPour(False)
    z.SetZoneName('LOGO')
    d = pcbnew.Dwgs_User
    for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        seg(board, a, b, d, 0.15)
    text(board, f'LOGO / TEXT AREA\n{x2 - x1:g} x {y2 - y1:g} mm', (x1 + x2) / 2, (y1 + y2) / 2, 1.0, d)


def keepout(board, x1, y1, x2, y2, label):
    """Area kept free of other parts, e.g. for a regulator heatsink. Tracks may pass underneath."""
    z = poly_zone(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], [pcbnew.F_Cu])
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowCopperPour(False)
    z.SetDoNotAllowFootprints(True)
    z.SetZoneName(label)
    for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        seg(board, a, b, pcbnew.F_Fab, 0.1)
    text(board, label, (x1 + x2) / 2, (y1 + y2) / 2, 0.8, pcbnew.F_Fab)


def gnd_pours(board, w, h):
    gnd = board.FindNet('GND')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = poly_zone(board, [(0, 0), (w, 0), (w, h), (0, h)], [layer])
        z.SetNet(gnd)
        z.SetZoneName('GND')
        z.SetLocalClearance(F(0.3))
        z.SetMinThickness(F(0.25))
        z.SetThermalReliefGap(F(0.4))
        z.SetThermalReliefSpokeWidth(F(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)


def fill(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def stitch(board, w, h, pitch=4.5):
    """GND vias wherever both pours have room, tying the two ground layers together."""
    gnd = board.FindNet('GND')
    zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == 'GND']
    keep = [z for z in board.Zones() if z.GetIsRuleArea()]
    holes = [fp for fp in board.GetFootprints() if fp.GetReference().startswith('H')]
    added = 0
    ring = [(math.cos(a) * 0.8, math.sin(a) * 0.8) for a in [i * math.pi / 4 for i in range(8)]]
    y = 1.5
    while y < h - 1.4:
        x = 1.5
        while x < w - 1.4:
            pts = [P(x, y)] + [P(x + dx, y + dy) for dx, dy in ring]
            ok = all(all(z.GetFilledPolysList(z.GetLayer()).Contains(p) for p in pts) for z in zones)
            ok = ok and not any(k.GetDoNotAllowVias() and k.Outline().Contains(p) for k in keep for p in pts)
            ok = ok and all((fp.GetPosition() - P(x, y)).EuclideanNorm() > F(4.2) for fp in holes)
            if ok:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(P(x, y))
                v.SetWidth(F(RULES['via']))
                v.SetDrill(F(RULES['via_drill']))
                v.SetNet(gnd)
                board.Add(v)
                added += 1
            x += pitch
        y += pitch
    return added


def drc(board, path):
    pcbnew.WriteDRCReport(board, path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    rep = open(path).read()
    viol = int(re.search(r'\*\* Found (\d+) DRC violations', rep).group(1))
    unc = int(re.search(r'\*\* Found (\d+) unconnected pads', rep).group(1))
    errors = len(re.findall(r'Severity: error', rep))
    warnings = len(re.findall(r'Severity: warning', rep))
    return viol, unc, errors, warnings, rep


# ---------------------------------------------------------------------------
# Autorouting
# ---------------------------------------------------------------------------
def autoroute(board, work, jar, passes):
    dsn = os.path.join(work, 'board.dsn')
    ses = os.path.join(work, 'board.ses')
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise SystemExit('DSN export failed')
    cmd = ['java', '-jar', os.path.abspath(jar), '-de', dsn, '-do', ses, '-mp', str(passes)]
    if re.search(r'freerouting-2\.', os.path.basename(jar)):
        cmd += ['-mt', '1', '--gui.enabled=false']
    elif not os.environ.get('DISPLAY') and shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd          # Freerouting 1.x opens a window even in batch mode
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, cwd=work)
    log = r.stdout + r.stderr
    with open(os.path.join(work, 'freerouting.log'), 'w') as f:
        f.write(log)
    if not os.path.exists(ses):
        raise SystemExit('Freerouting failed, see ' + os.path.join(work, 'freerouting.log'))
    import_ses(board, ses)


def import_ses(board, path):
    """Adds the tracks and vias from a Specctra session file. (pcbnew's own ImportSpecctraSES
    only works on the board open in the editor.)"""
    def find(node, key):
        return [x for x in node if isinstance(x, list) and x and x[0] == key]

    routes = find(parse(open(path).read())[0], 'routes')[0]
    res = find(routes, 'resolution')[0]
    unit = {'um': 0.001, 'mm': 1.0, 'mil': 0.0254, 'inch': 25.4}[res[1]] / float(res[2])
    vias = {}
    for lib in find(routes, 'library_out'):
        for ps in find(lib, 'padstack'):
            name = ps[1].strip('"')
            m = re.search(r'_(\d+):(\d+)_um', name)
            vias[name] = (float(m.group(1)) / 1000, float(m.group(2)) / 1000)
    n_tracks = n_vias = 0
    for out in find(routes, 'network_out'):
        for net in find(out, 'net'):
            ni = board.FindNet(net[1].strip('"'))
            for w in find(net, 'wire'):
                path_ = find(w, 'path')[0]
                layer = board.GetLayerID(path_[1].strip('"'))
                width = F(float(path_[2]) * unit)
                pts = [pcbnew.VECTOR2I(F(float(path_[i]) * unit), F(-float(path_[i + 1]) * unit))
                       for i in range(3, len(path_) - 1, 2)]
                for a, b in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(a)
                    t.SetEnd(b)
                    t.SetWidth(width)
                    t.SetLayer(layer)
                    t.SetNet(ni)
                    board.Add(t)
                    n_tracks += 1
            for v in find(net, 'via'):
                dia, drill = vias[v[1].strip('"')]
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(F(float(v[2]) * unit), F(-float(v[3]) * unit)))
                via.SetWidth(F(dia))
                via.SetDrill(F(drill))
                via.SetNet(ni)
                board.Add(via)
                n_vias += 1
    print(f'imported {n_tracks} track segments, {n_vias} vias')


# ---------------------------------------------------------------------------
# Project file: keep the net classes and rules when the board is opened in KiCad
# ---------------------------------------------------------------------------
def write_project_rules(pro_path):
    pro = json.load(open(pro_path))
    ns = pro.setdefault('net_settings', {})
    base = dict(bus_width=12, clearance=RULES['clearance'], diff_pair_gap=0.25, diff_pair_via_gap=0.25,
                diff_pair_width=0.2, line_style=0, microvia_diameter=0.3, microvia_drill=0.1,
                pcb_color='rgba(0, 0, 0, 0.000)', schematic_color='rgba(0, 0, 0, 0.000)',
                track_width=RULES['track'], via_diameter=RULES['via'], via_drill=RULES['via_drill'],
                wire_width=6)
    classes = [dict(base, name='Default')]
    for name, (width, clear, _nets) in NETCLASSES.items():
        classes.append(dict(base, name=name, track_width=width, clearance=clear, via_diameter=0.8, via_drill=0.4))
    ns['classes'] = classes
    ns['netclass_patterns'] = [dict(netclass=name, pattern=n) for name, (_w, _c, nets) in NETCLASSES.items()
                               for n in nets]
    ns.setdefault('meta', {'version': 3})
    bd = pro.setdefault('board', {}).setdefault('design_settings', {})
    rules = bd.setdefault('rules', {})
    rules.update(min_clearance=RULES['clearance'], min_track_width=0.2, min_via_diameter=RULES['via'],
                 min_through_hole_diameter=RULES['via_drill'], min_copper_edge_clearance=RULES['edge'],
                 min_hole_clearance=0.25, min_hole_to_hole=0.25)
    bd['track_widths'] = [0.0, 0.25, 0.5, 1.0, 1.5]
    bd['via_dimensions'] = [dict(diameter=0.0, drill=0.0), dict(diameter=0.6, drill=0.3), dict(diameter=0.8, drill=0.4)]
    with open(pro_path, 'w') as f:
        json.dump(pro, f, indent=2)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def kicad_cli(*args):
    r = subprocess.run(['kicad-cli', *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f'kicad-cli {" ".join(args)} failed:\n{r.stdout}{r.stderr}')


def exports(pcb, outdir, name):
    gdir = tempfile.mkdtemp()
    layers = 'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
    kicad_cli('pcb', 'export', 'gerbers', '--layers', layers, '--subtract-soldermask', '--no-x2',
              '-o', gdir + '/', pcb)
    kicad_cli('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
              '--generate-map', '--map-format', 'gerberx2', '-o', gdir + '/', pcb)
    zpath = os.path.join(outdir, f'{name}-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    shutil.rmtree(gdir)
    kicad_cli('pcb', 'export', 'pdf', '--layers', 'F.Cu,F.SilkS,Edge.Cuts,Dwgs.User', '-o',
              os.path.join(outdir, f'{name}-PCB-top.pdf'), pcb)
    kicad_cli('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front', '-o',
              os.path.join(outdir, f'{name}-positions.csv'), pcb)
    return zpath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('variant', choices=VARIANTS)
    ap.add_argument('--place-only', action='store_true')
    ap.add_argument('--jar', default=os.environ.get('FREEROUTING_JAR', ''))
    ap.add_argument('--passes', type=int, default=100)
    ap.add_argument('--work', default='')
    a = ap.parse_args()

    v = VARIANTS[a.variant]
    lay = pcb_layout.LAYOUTS[a.variant]
    make_nano_footprint()
    make_fuse_footprint()
    sch = os.path.join(v['dir'], v['project'] + '.kicad_sch')
    pcb = os.path.join(v['dir'], v['project'] + '.kicad_pcb')
    work = a.work or tempfile.mkdtemp(prefix='wvc-pcb-')
    os.makedirs(work, exist_ok=True)

    comps, nets = read_netlist(sch)
    board = new_board(pcb)
    add_nets(board, nets)
    add_footprints(board, comps, nets, lay['place'], v['project'])
    w, h = lay['size']
    outline(board, w, h, lay.get('corner', 1.0))
    logo_area(board, *lay['logo'])
    for k in lay.get('keepouts', []):
        keepout(board, *k)
    for t in lay.get('texts', []):
        text(board, *t[:3], **(t[3] if len(t) > 3 else {}))
    hidden = place_refs(board, w, h, [lay['logo']], lay.get('labelled', ()))
    if hidden:
        print('no room on the silkscreen for:', ', '.join(hidden))

    for net, width, layer, pts in lay.get('preroute', []):
        # Fixed tracks laid before autorouting; Freerouting leaves locked tracks alone
        for p0, p1 in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*p0))
            t.SetEnd(P(*p1))
            t.SetWidth(F(width))
            t.SetLayer(board.GetLayerID(layer))
            t.SetNet(board.FindNet(net))
            t.SetLocked(True)
            board.Add(t)

    if not a.place_only:
        if not a.jar:
            raise SystemExit('give the Freerouting jar with --jar or $FREEROUTING_JAR')
        autoroute(board, work, a.jar, a.passes)
        gnd_pours(board, w, h)
        fill(board)
        n = stitch(board, w, h)
        fill(board)
        print(f'stitching vias: {n}')
    pcbnew.SaveBoard(pcb, board)
    write_project_rules(os.path.join(v['dir'], v['project'] + '.kicad_pro'))

    board = pcbnew.LoadBoard(pcb)
    viol, unc, errors, warnings, rep = drc(board, os.path.join(work, 'drc.rpt'))
    print(f'{a.variant}: {w} x {h} mm = {w * h:.0f} mm2; DRC {viol} violations '
          f'({errors} errors, {warnings} warnings), {unc} unconnected; report {work}/drc.rpt')
    if not a.place_only:
        print('gerbers:', exports(pcb, v['dir'], v['project']))


if __name__ == '__main__':
    main()

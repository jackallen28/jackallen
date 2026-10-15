#!/usr/bin/env python3
"""Production panel: all ten VIBEDUINO modules on one JLCPCB-ready panel.

    python3 panel.py

Builds hardware/panel/ from the routed module boards in hardware/kicad/modules:
a 5 x 2 grid of hex modules in a 5 mm frame, joined by mouse-bite tabs, with
fiducials on both sides, JLCPCB tooling holes and a JLCJLCJLCJLC order-number
marker on the rail.  Then writes the panel's Gerber zip, BOM, JLCPCB BOM + CPL,
previews, and checks the panel with DRC.  Needs KiKit 1.6 (pip install "kikit==1.6.0"); KiKit 1.8 expects KiCad 9's layer
numbering and does not work with KiCad 7.
"""

import itertools
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402
from kikit import panelize, panelize_ui_impl as ki  # noqa: E402
from kikit.annotations import TabAnnotation  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from vibeduino import bom, fab, render, route  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
MODULES = os.path.join(ROOT, "kicad", "modules")
OUT = os.path.join(ROOT, "panel")
NAME = "vibeduino-modules-panel"

# Panel order: two rows of five (left to right, top to bottom).
ORDER = [["pot", "oled", "dpad", "led", "servo"],
         ["temp", "buzzer", "light", "rgb", "proto"]]
GAP = 2.0          # mm milled gap between boards and between boards and the frame
FRAME = 5.0        # mm frame (JLCPCB wants >= 5 mm rails for assembly)

TAB_W = 3.0        # mm tab width
BITE_CLEAR = 0.55  # mm copper-to-cut distance: 0.25 mm hole radius + 0.25 mm hole clearance
PRESET = dict(
    cuts={"type": "mousebites", "drill": "0.5mm", "spacing": "0.8mm", "offset": "0mm",
          "prolong": "0.5mm"},
    framing={"type": "frame", "width": f"{FRAME}mm", "hspace": f"{GAP}mm", "vspace": f"{GAP}mm",
             "cuts": "none"},
    tooling={"type": "3hole", "hoffset": "2.5mm", "voffset": "2.5mm", "size": "1.152mm",
             "soldermaskmargin": "1.3mm"},
    fiducials={"type": "3fid", "hoffset": "10mm", "voffset": "2.5mm", "coppersize": "1mm",
               "opening": "2mm"},
    text={"type": "simple", "text": "VIBEDUINO modules rev A - Allentronics Education - "
          "www.allentronics.com.au", "anchor": "mt", "voffset": "2.5mm", "width": "1.4mm",
          "height": "1.4mm", "thickness": "0.25mm"},
    text2={"type": "simple", "text": "JLCJLCJLCJLC", "anchor": "mb", "voffset": "-2.5mm",
           "width": "1.2mm", "height": "1.2mm", "thickness": "0.2mm"},
    post={"millradius": "1mm", "origin": "bl"},
    page={"type": "inherit"},
)


def module_path(key):
    return os.path.join(MODULES, key, f"vibeduino-{key}.kicad_pcb")


def board_size(path):
    b = pcbnew.LoadBoard(path)
    box = b.GetBoardEdgesBoundingBox()
    return pcbnew.ToMM(box.GetWidth()), pcbnew.ToMM(box.GetHeight())


def module_geometry(path):
    """(outline polygon, copper geometry) of a module in mm, centred on its bounding box."""
    board = pcbnew.LoadBoard(path)
    bb = board.GetBoardEdgesBoundingBox()
    cx, cy = pcbnew.ToMM(bb.GetCenter().x), pcbnew.ToMM(bb.GetCenter().y)
    mm = lambda p: (pcbnew.ToMM(p.x) - cx, pcbnew.ToMM(p.y) - cy)
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps)
    ol = ps.Outline(0)
    outline = Polygon([mm(ol.CPoint(i)) for i in range(ol.PointCount())])
    cu = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            cu.append(Point(mm(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth()) / 2))
        else:
            cu.append(LineString([mm(t.GetStart()), mm(t.GetEnd())]).buffer(
                pcbnew.ToMM(t.GetWidth()) / 2))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            (x0, y0), (x1, y1) = mm(b.GetOrigin()), mm(b.GetEnd())
            cu.append(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return outline, unary_union(cu)


def cut_clearance(geom, side, pos):
    """Copper clearance of the mouse-bite cut for a tab centred at `pos` along `side`."""
    outline, copper = geom
    x0, y0, x1, y1 = outline.bounds
    half = TAB_W / 2 + 0.5                      # tab plus the bite prolongation
    region = {"left": box(x0 - 1, pos - half, x0 + 3, pos + half),
              "right": box(x1 - 3, pos - half, x1 + 1, pos + half),
              "top": box(pos - half, y0 - 1, pos + half, y0 + 4),
              "bottom": box(pos - half, y1 - 4, pos + half, y1 + 1)}[side]
    cut = outline.exterior.intersection(region)
    return cut.distance(copper)


def best_spot(scored, limit):
    """Pick the position with the most clearance (nearest the middle on ties), or None when
    copper runs along the whole edge (that joint then gets no tab)."""
    ok = [(round(c, 2), -abs(p), p) for p, c in scored if c >= limit]
    return max(ok)[2] if ok else None


def place_tabs(panel, paths, w, h):
    """Tab annotations shared by both boards of every joint, at spots clear of copper."""
    geoms = {p: module_geometry(p) for row in paths for p in row}
    side_span = [y / 4 for y in range(-18, 19)]           # +-4.5 mm along the vertical edges
    tip_span = [x / 4 for x in range(-8, 9)]              # +-2 mm around the hex tips
    sub = iter(panel.substrates)
    subs = [[next(sub) for _ in row] for row in paths]
    rows, cols = len(paths), len(paths[0])
    nm = pcbnew.FromMM
    name = {id(g): os.path.basename(p) for p, g in geoms.items()}
    joint = lambda a, b: " and ".join(name[id(g)] if g else "frame" for g in (a, b))

    def add(r, c, side, pos):
        cx, cy = c * (w + GAP), r * (h + GAP)
        origin, d = {"left": ((cx - w / 2, cy + pos), (1, 0)),
                     "right": ((cx + w / 2, cy + pos), (-1, 0)),
                     "top": ((cx + pos, cy - h / 2), (0, 1)),
                     "bottom": ((cx + pos, cy + h / 2), (0, -1))}[side]
        subs[r][c].annotations.append(
            TabAnnotation(None, (nm(origin[0]), nm(origin[1])), d, nm(TAB_W)))

    for r in range(rows):
        for c in range(cols + 1):           # vertical joints: frame | b | b | ... | frame
            left = geoms[paths[r][c - 1]] if c > 0 else None
            right = geoms[paths[r][c]] if c < cols else None
            scored = [(y, min(cut_clearance(left, "right", y) if left else 99,
                              cut_clearance(right, "left", y) if right else 99)) for y in side_span]
            y = best_spot(scored, BITE_CLEAR)
            if y is None:
                print(f"  no tab between {joint(left, right)}: copper along the edge")
                continue
            if left:
                add(r, c - 1, "right", y)
            if right:
                add(r, c, "left", y)
    for c in range(cols):
        for r in range(rows + 1):           # tip joints: frame / row 0 / row 1 / frame
            upper = geoms[paths[r - 1][c]] if r > 0 else None
            lower = geoms[paths[r][c]] if r < rows else None
            scored = [(x, min(cut_clearance(upper, "bottom", x) if upper else 99,
                              cut_clearance(lower, "top", x) if lower else 99)) for x in tip_span]
            x = best_spot(scored, BITE_CLEAR)
            if x is None:
                print(f"  no tab between {joint(upper, lower)}: copper near the tip")
                continue
            if upper:
                add(r - 1, c, "bottom", x)
            if lower:
                add(r, c, "top", x)
    for row, srow in zip(paths, subs):
        for p, s in zip(row, srow):
            assert len(s.annotations) >= 3, (p, len(s.annotations))


def build_panel(pcb_out):
    preset = ki.obtainPreset([], **PRESET)
    first = pcbnew.LoadBoard(module_path(ORDER[0][0]))
    panel = panelize.Panel(pcb_out)
    panel.inheritDesignSettings(first)
    panel.inheritProperties(first)
    panel.inheritTitleBlock(first)
    panel.inheritLayerNames(first)

    w, h = board_size(module_path(ORDER[0][0]))
    for r, row in enumerate(ORDER):
        for c, key in enumerate(row):
            assert board_size(module_path(key)) == (w, h), key   # every module is the same hex
            centre = pcbnew.VECTOR2I(pcbnew.FromMM(c * (w + GAP)), pcbnew.FromMM(r * (h + GAP)))
            tag = key.upper()
            panel.appendBoard(module_path(key), centre, origin=panelize.Origin.Center,
                              tolerance=pcbnew.FromMM(2),
                              netRenamer=lambda n, orig, tag=tag: f"{tag}-{orig}",
                              refRenamer=lambda n, orig, tag=tag: f"{orig}_{tag}",
                              inheritDrc=False)
    substrates = panel.substrates
    framing = ki.dummyFramingSubstrate(substrates, preset)
    panel.buildPartitionLineFromBB(framing)
    panel.clearTabsAnnotations()
    place_tabs(panel, [[module_path(k) for k in row] for row in ORDER], w, h)
    tab_cuts = panel.buildTabsFromAnnotations(0)
    frame_cuts = ki.buildFraming(preset, panel)
    ki.buildTooling(preset, panel)
    ki.buildFiducials(preset, panel)
    for section in ("text", "text2", "text3", "text4"):
        ki.buildText(preset[section], panel)
    ki.buildPostprocessing(preset["post"], panel)
    ki.makeTabCuts(preset, panel, tab_cuts)
    ki.makeOtherCuts(preset, panel, itertools.chain(frame_cuts))
    ki.setStackup(preset["source"], panel)
    ki.setPageSize(preset["page"], panel, first)
    ki.positionPanel(preset["page"], panel)
    panel.save(reconstructArcs=False, refillAllZones=True)
    if panel.hasErrors():
        raise RuntimeError(panel.errors)


def main():
    kdir = os.path.join(OUT, "kicad")
    fab_dir = os.path.join(OUT, "fab")
    prev_dir = os.path.join(OUT, "previews")
    for d in (kdir, fab_dir, prev_dir):
        os.makedirs(d, exist_ok=True)
    pcb = os.path.join(kdir, f"{NAME}.kicad_pcb")
    build_panel(pcb)
    # keep the modules' rules (clearances, netclasses) with the panel
    shutil.copy(module_path("pot").replace(".kicad_pcb", ".kicad_pro"),
                pcb.replace(".kicad_pcb", ".kicad_pro"))

    e, wn, u, _ = route.drc(pcb)
    lines = bom.write_board_bom(pcb, fab_dir, NAME)
    n_smt = bom.write_cpl(pcb, fab_dir, NAME)
    zpath, files = fab.gerbers(pcb, fab_dir, NAME)

    board = pcbnew.LoadBoard(pcb)
    box = board.GetBoardEdgesBoundingBox()
    size = (round(pcbnew.ToMM(box.GetWidth()), 2), round(pcbnew.ToMM(box.GetHeight()), 2))
    sides = sorted({g["side"] for g in lines if g["part"].process == "SMT"})
    summary = dict(panel=NAME, size_mm=size, boards=sum(ORDER, []), drc_errors=e,
                   drc_warnings=wn, unconnected=u, smt_placements=n_smt, smt_sides=sides,
                   tht_parts=sum(len(g["refs"]) for g in lines if g["part"].process == "THT"),
                   lines=len(lines), gerber_files=files)
    with open(os.path.join(fab_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    render.photo(pcb, os.path.join(prev_dir, f"{NAME}-top.png"), side="F")
    render.photo(pcb, os.path.join(prev_dir, f"{NAME}-bottom.png"), side="B")
    print(json.dumps({k: v for k, v in summary.items() if k != "gerber_files"}, indent=1))
    print("gerbers ->", os.path.relpath(zpath, ROOT))
    return 0 if e == 0 and u == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

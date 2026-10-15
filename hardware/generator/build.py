#!/usr/bin/env python3
"""Build every VIBEDUINO board: generate -> autoroute -> pour -> DRC -> previews.

Usage:
    FREEROUTING_JAR=/path/freerouting-2.x-executable.jar VIBEDUINO_JAVA=/usr/lib/jvm/java-25/bin/java \
        python3 build.py [shield] [pot oled ...] [--no-route]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402

from vibeduino import assembly, kicad, modules, render, route, shield, spec  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
KICAD_DIR = os.path.join(ROOT, "kicad")
PREVIEW_DIR = os.path.join(ROOT, "previews")


def check_inside_hex(path):
    """Every component courtyard (except the bus headers) must sit inside the hex."""
    board = pcbnew.LoadBoard(path)
    ox, oy = spec.MODULE_ORIGIN
    bad = []
    for fp in board.GetFootprints():
        if fp.GetReference() in ("J1", "J2"):
            continue
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            cy = fp.GetCourtyard(layer)
            for i in range(cy.OutlineCount()):
                ol = cy.Outline(i)
                for k in range(ol.PointCount()):
                    pt = ol.CPoint(k)
                    x, y = pcbnew.ToMM(pt.x) - ox, pcbnew.ToMM(pt.y) - oy
                    if not spec.inside_hex(x, y, margin=0.1):
                        bad.append((fp.GetReference(), round(x, 2), round(y, 2)))
    return sorted(set(bad))


def finish(path, origin, pour, do_route, passes, post_route=None):
    if do_route:
        route.autoroute(path, passes=passes)
        route.widen_power(path)
    board = pcbnew.LoadBoard(path)
    p = kicad.wrap(board, origin)
    if post_route:
        post_route(p)
    pour(p)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    kicad.write_netclass_patterns(path.replace(".kicad_pcb", ".kicad_pro"))
    prl = path.replace(".kicad_pcb", ".kicad_prl")
    if os.path.exists(prl):
        os.remove(prl)
    errors, warnings, unconnected, txt = route.drc(path)
    return errors, warnings, unconnected


def previews(path, name):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    render.photo(path, os.path.join(PREVIEW_DIR, f"{name}-top.png"), "F")
    render.photo(path, os.path.join(PREVIEW_DIR, f"{name}-bottom.png"), "B")
    render.layout(path, os.path.join(PREVIEW_DIR, f"{name}-layout.png"))


def build_module(fn, do_route=True, passes=40):
    m = fn()
    m.finalize()
    name = f"vibeduino-{m.key}"
    path = os.path.join(KICAD_DIR, "modules", m.key, name + ".kicad_pcb")
    m.pcb.save(path)
    with open(os.path.join(os.path.dirname(path), "module.json"), "w") as f:
        json.dump(dict(name=m.name, title=m.title, description=m.desc, signals=m.signals,
                       parts=m.bom), f, indent=2)
    def brand(p):            # underside artwork is placed around the finished vias
        m.pcb = p
        m.bottom_branding()
    res = finish(path, spec.MODULE_ORIGIN, _module_pours, do_route, passes, brand)
    outside = check_inside_hex(path)
    previews(path, name)
    return name, res, outside


def _module_pours(p):
    verts = spec.hex_vertices(spec.HEX_R + 0.5)
    for layer in ("F.Cu", "B.Cu"):
        p.zone("GND", layer, verts)


ASSEMBLIES = {
    "vibeduino-assembly.png": {1: "oled", 2: "dpad", 3: "pot", 4: "servo"},
    "vibeduino-assembly-2.png": {1: "led", 2: "rgb", 3: "temp", 4: "buzzer"},
}


def sheets():
    """Fit check, populated-shield renders and module contact sheets."""
    for line in assembly.verify_fit():
        print("fit:", line)
    pv = lambda n, s: os.path.join(PREVIEW_DIR, f"vibeduino-{n}-{s}.png")  # noqa: E731
    shield_pcb = os.path.join(KICAD_DIR, "shield", "vibeduino-shield.kicad_pcb")
    for out, slots in ASSEMBLIES.items():
        if os.path.exists(pv("shield", "top")) and all(os.path.exists(pv(m, "top")) for m in slots.values()):
            assembly.render_assembly(shield_pcb, pv("shield", "top"),
                                     {s: pv(m, "top") for s, m in slots.items()},
                                     os.path.join(PREVIEW_DIR, out))
    keys = [f.__name__ for f in modules.ALL]
    for side in ("top", "bottom", "layout"):
        files = [pv(k, side) for k in keys if os.path.exists(pv(k, side))]
        if files:
            assembly.contact_sheet(files, os.path.join(PREVIEW_DIR, f"modules-{side}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("boards", nargs="*", help="shield and/or module keys (default: all)")
    ap.add_argument("--no-route", action="store_true")
    ap.add_argument("--passes", type=int, default=40)
    a = ap.parse_args()
    keys = a.boards or ["shield"] + [f.__name__ for f in modules.ALL]
    results = []
    for k in keys:
        if k == "shield":
            path = shield.build(os.path.join(KICAD_DIR, "shield"))
            res = finish(path, spec.SHIELD_ORIGIN, shield.pours, not a.no_route, a.passes)
            bad = shield.check_keepouts(path)
            previews(path, "vibeduino-shield")
            results.append(("vibeduino-shield", res, bad))
        else:
            fn = getattr(modules, k)
            results.append(build_module(fn, not a.no_route, a.passes))
        name, (e, w, u), extra = results[-1]
        print(f"{name:24s} DRC errors={e:3d} warnings={w:3d} unconnected={u:3d} "
              f"geometry_issues={len(extra)} {extra[:4] if extra else ''}", flush=True)
    sheets()
    return 0 if all(r[1][0] == 0 and r[1][2] == 0 and not r[2] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

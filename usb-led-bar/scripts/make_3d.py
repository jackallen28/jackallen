#!/usr/bin/env python3
"""Build a coloured STEP model (and a GLB for rendering) of a USB LED Bar variant.

usage: python3 scripts/make_3d.py [variant-dir]        (default: usb-c)

Writes <variant>/3d/<name>.step and <name>.glb, and refreshes the custom part models in
usb-led-bar.3dshapes/. The model has the FR-4 core, green solder mask, copper visible through
the mask, tin (HASL) pads and plated holes, white silkscreen including the logo, and 3D models
of every part.

Needs KiCad 7+ (its `pcbnew` Python module) and cadquery (`pip install cadquery`). The two use
different OpenCascade builds, so the board is read by a child process that only imports pcbnew.
"""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHAPES = ROOT / "usb-led-bar.3dshapes"

THK = 1.6  # board thickness
MASK_T, CU_T, PAD_T, SILK_T = 0.02, 0.035, 0.04, 0.02
PART_Z = THK + PAD_T  # parts sit on the pads

# One distinct colour per material; render_blender.py maps them to PBR materials.
COLORS = {
    "fr4": (0.72, 0.64, 0.42),
    "mask": (0.05, 0.33, 0.13),
    "mask_cu": (0.12, 0.45, 0.18),
    "hasl": (0.80, 0.80, 0.78),
    "silk": (0.97, 0.97, 0.97),
    "res_body": (0.10, 0.10, 0.10),
    "res_term": (0.86, 0.86, 0.84),
    "led_body": (0.95, 0.95, 0.92),
    "led_phosphor": (1.00, 0.80, 0.40),
    "usb_shell": (0.70, 0.70, 0.73),
    "plastic_black": (0.06, 0.06, 0.06),
    "gold": (0.85, 0.65, 0.20),
}


# --------------------------------------------------------------------------- board extraction
def extract(pcb_path):
    """Runs in a child process: read the board with pcbnew and dump geometry as JSON."""
    import pcbnew

    b = pcbnew.LoadBoard(pcb_path)
    org = b.GetDesignSettings().GetAuxOrigin()  # bottom-left board corner
    ox, oy = pcbnew.ToMM(org.x), pcbnew.ToMM(org.y)

    def xy(p):
        return [round(pcbnew.ToMM(p.x) - ox, 5), round(oy - pcbnew.ToMM(p.y), 5)]

    def layer(lid):
        ps = pcbnew.SHAPE_POLY_SET()
        b.ConvertBrdLayerToPolygonalContours(lid, ps)
        ps.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST)
        return ps

    def dump(ps):
        out = []
        for i in range(ps.OutlineCount()):
            chain = lambda c: [xy(c.CPoint(j)) for j in range(c.PointCount())]
            out.append({"outer": chain(ps.Outline(i)), "holes": [chain(ps.Hole(i, h)) for h in range(ps.HoleCount(i))]})
        return out

    def op(a, b_, kind):
        r = pcbnew.SHAPE_POLY_SET(a)
        getattr(r, kind)(b_, pcbnew.SHAPE_POLY_SET.PM_FAST)
        return r

    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline)
    layers = {}
    for side, cu, mask, silk in (("top", pcbnew.F_Cu, pcbnew.F_Mask, pcbnew.F_SilkS), ("bot", pcbnew.B_Cu, pcbnew.B_Mask, pcbnew.B_SilkS)):
        c, m, s = layer(cu), layer(mask), layer(silk)
        layers[f"mask_{side}"] = dump(op(outline, m, "BooleanSubtract"))
        layers[f"mask_cu_{side}"] = dump(op(c, m, "BooleanSubtract"))
        layers[f"pads_{side}"] = dump(op(c, m, "BooleanIntersection"))
        layers[f"silk_{side}"] = dump(op(s, m, "BooleanSubtract"))

    holes = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            d = pad.GetDrillSize()
            if d.x <= 0:
                continue
            holes.append(
                dict(
                    pos=xy(pad.GetPosition()),
                    w=pcbnew.ToMM(d.x),
                    h=pcbnew.ToMM(d.y),
                    angle=pad.GetOrientationDegrees(),
                    plated=pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
                )
            )
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            dr = pcbnew.ToMM(t.GetDrillValue())
            holes.append(dict(pos=xy(t.GetPosition()), w=dr, h=dr, angle=0, plated=True))

    parts = []
    for fp in b.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            continue
        parts.append(
            dict(
                ref=fp.GetReference(),
                fp=str(fp.GetFPID().GetLibItemName()),
                pos=xy(fp.GetPosition()),
                rot=fp.GetOrientationDegrees(),
                side="top" if fp.GetLayer() == pcbnew.F_Cu else "bot",
            )
        )
    json.dump(dict(outline=dump(outline), layers=layers, holes=holes, parts=parts), sys.stdout)


# --------------------------------------------------------------------------- part models
def part_models():
    import cadquery as cq

    def col(name):
        return cq.Color(*COLORS[name])

    def resistor_0805():
        a = cq.Assembly(name="R_0805")
        a.add(cq.Workplane().box(1.3, 1.2, 0.45, centered=(True, True, False)), name="body", color=col("res_body"))
        for sx in (-1, 1):
            term = cq.Workplane().box(0.35, 1.25, 0.5, centered=(True, True, False)).translate((sx * 0.825, 0, 0))
            a.add(term, name=f"term{'L' if sx < 0 else 'R'}", color=col("res_term"))
        return a

    def led_2835():
        # 3.5 x 2.8 x 0.8 mm PLCC body, phosphor-filled cup; chamfered cup corner marks the cathode (-X)
        a = cq.Assembly(name="LED_2835")
        cup = (
            cq.Workplane()
            .rect(3.0, 2.3)
            .extrude(0.3)
            .edges("|Z")
            .fillet(0.25)
            .translate((0, 0, 0.5))
        )
        notch = cq.Workplane().polyline([(-1.5, 1.15), (-0.95, 1.15), (-1.5, 0.6)]).close().extrude(0.3).translate((0, 0, 0.5))
        cup = cup.cut(notch)
        body = cq.Workplane().box(3.5, 2.8, 0.8, centered=(True, True, False)).cut(cup)
        a.add(body, name="body", color=col("led_body"))
        a.add(cup.translate((0, 0, -0.06)).intersect(cq.Workplane().box(4, 4, 0.74, centered=(True, True, False))), name="phosphor", color=col("led_phosphor"))
        for sx in (-1, 1):
            a.add(
                cq.Workplane().box(0.25, 2.0, 0.12, centered=(True, True, False)).translate((sx * 1.66, 0, 0)),
                name=f"lead{'K' if sx < 0 else 'A'}",
                color=col("hasl"),
            )
        return a

    def usb_c_hro_31_m_12():
        # HRO TYPE-C-31-M-12: shell 8.94 x 3.26 x 7.35 mm; KiCad footprint frame, mouth towards -Y
        a = cq.Assembly(name="USB_C_HRO_TYPE-C-31-M-12")
        L, W, Hh = 7.3, 8.94, 3.26
        zc = Hh / 2
        outer = cq.Workplane("XZ", origin=(0, -L / 2, zc)).slot2D(W, Hh).extrude(-L)
        cavity = cq.Workplane("XZ", origin=(0, -L / 2 - 0.01, zc)).slot2D(W - 0.6, Hh - 0.6).extrude(-(L - 0.75))
        shell = outer.cut(cavity)
        legs = []
        for sx in (-1, 1):
            for yc, ln in ((-1.05, 1.0), (3.13, 1.5)):
                # through-hole shell tabs, from the shell's widest point down through the board
                legs.append(cq.Workplane().box(0.3, ln, 4.1).translate((sx * 4.32, yc, zc - 2.05)))
        for leg in legs:
            shell = shell.union(leg)
        a.add(shell, name="shell", color=col("usb_shell"))
        tongue = cq.Workplane().box(6.69, 5.6, 0.7).translate((0, (-L / 2 + 0.95 + L / 2 - 0.7) / 2, zc))
        rear = cq.Workplane().box(7.6, 0.7, 2.6).translate((0, L / 2 - 0.35, zc))
        pegs = [cq.Workplane().circle(0.25).extrude(-1.2).translate((sx * 2.89, 2.6, 0)) for sx in (-1, 1)]
        plastic = tongue.union(rear)
        for p in pegs:
            plastic = plastic.union(p)
        a.add(plastic, name="insulator", color=col("plastic_black"))
        contacts = None
        for i in range(12):
            x = -2.75 + 0.5 * i
            for z in (zc + 0.36, zc - 0.36):
                c = cq.Workplane().box(0.25, 2.4, 0.02).translate((x, -L / 2 + 2.3, z))
                contacts = c if contacts is None else contacts.union(c)
        a.add(contacts, name="contacts", color=col("gold"))
        leads = None
        for x, w in ((-3.25, 0.6), (-2.45, 0.6), (-1.75, 0.3), (-1.25, 0.3), (-0.75, 0.3), (-0.25, 0.3),
                     (0.25, 0.3), (0.75, 0.3), (1.25, 0.3), (1.75, 0.3), (2.45, 0.6), (3.25, 0.6)):
            ld = cq.Workplane().box(w * 0.8, 1.1, 0.12, centered=(True, True, False)).translate((x, L / 2 + 0.5, 0))
            leads = ld if leads is None else leads.union(ld)
        a.add(leads, name="leads", color=col("hasl"))
        return a

    return {
        "R_0805_2012Metric": resistor_0805,
        "LED_2835_PolarityTolerant": led_2835,
        "USB_C_Receptacle_HRO_TYPE-C-31-M-12": usb_c_hro_31_m_12,
    }


# --------------------------------------------------------------------------- board build
def build(vdir):
    import cadquery as cq

    pcb = next(vdir.glob("*.kicad_pcb"))
    name = pcb.stem
    geo = json.loads(
        subprocess.run([sys.executable, __file__, "--extract", str(pcb)], check=True, capture_output=True, text=True).stdout
    )

    def simplify(pts, tol=0.01):
        """Douglas-Peucker on a closed ring; 10 um is far below silkscreen/etch resolution."""

        def dp(seg):
            if len(seg) < 3:
                return seg
            (x1, y1), (x2, y2) = seg[0], seg[-1]
            dx, dy = x2 - x1, y2 - y1
            n = (dx * dx + dy * dy) ** 0.5 or 1e-12
            dists = [abs(dy * (x - x1) - dx * (y - y1)) / n for x, y in seg[1:-1]]
            i = max(range(len(dists)), key=dists.__getitem__)
            if dists[i] <= tol:
                return [seg[0], seg[-1]]
            return dp(seg[: i + 2])[:-1] + dp(seg[i + 1 :])

        if len(pts) < 8:
            return pts
        half = len(pts) // 2
        out = dp(pts[: half + 1])[:-1] + dp(pts[half:] + pts[:1])[:-1]
        return out if len(out) >= 3 else pts

    def solid(polys, z0, h):
        solids = []
        for p in polys:
            outer = cq.Wire.makePolygon([cq.Vector(x, y, 0) for x, y in simplify(p["outer"])], close=True)
            inner = [cq.Wire.makePolygon([cq.Vector(x, y, 0) for x, y in simplify(hl)], close=True) for hl in p["holes"]]
            face = cq.Face.makeFromWires(outer, inner)
            solids.append(cq.Solid.extrudeLinear(face, cq.Vector(0, 0, h)).translate(cq.Vector(0, 0, z0)))
        return cq.Compound.makeCompound(solids) if solids else None

    def hole_solid(hl, grow=0.0, z0=-1.0, h=THK + 2.0):
        w, hh = hl["w"] + 2 * grow, hl["h"] + 2 * grow
        if abs(w - hh) < 1e-6:
            s = cq.Workplane().circle(w / 2).extrude(h)
        else:
            s = cq.Workplane().slot2D(max(w, hh), min(w, hh), 0 if w > hh else 90).extrude(h)
            s = s.rotate((0, 0, 0), (0, 0, 1), hl["angle"])
        return s.translate((hl["pos"][0], hl["pos"][1], z0)).val()

    drills = cq.Compound.makeCompound([hole_solid(h) for h in geo["holes"]])

    def cut(shape):
        return shape.cut(drills) if shape is not None else None

    assy = cq.Assembly(name=name)
    board = cq.Assembly(name="board")
    board.add(cut(solid(geo["outline"], 0, THK)), name="core", color=cq.Color(*COLORS["fr4"]))
    L = geo["layers"]
    for side, z, sgn in (("top", THK, 1), ("bot", 0, -1)):
        stack = [
            ("mask", f"mask_{side}", MASK_T, "mask"),
            ("mask_cu", f"mask_cu_{side}", CU_T, "mask_cu"),
            ("pads", f"pads_{side}", PAD_T, "hasl"),
        ]
        for label, key, t, c in stack:
            s = solid(L[key], z if sgn > 0 else z - t, t)
            if s is not None:
                board.add(cut(s), name=f"{label}_{side}", color=cq.Color(*COLORS[c]))
        s = solid(L[f"silk_{side}"], z + 0.005 if sgn > 0 else z - 0.005 - (SILK_T + MASK_T), SILK_T + MASK_T)
        if s is not None:
            board.add(cut(s), name=f"silk_{side}", color=cq.Color(*COLORS["silk"]))
    barrels = [
        hole_solid(h, 0, -PAD_T, THK + 2 * PAD_T).cut(hole_solid(h, -0.03))
        for h in geo["holes"]
        if h["plated"]
    ]
    if barrels:
        board.add(cq.Compound.makeCompound(barrels), name="plating", color=cq.Color(*COLORS["hasl"]))
    assy.add(board)

    makers = part_models()
    cache = {}
    for p in geo["parts"]:
        if p["fp"] not in makers:
            print(f"  no 3D model for {p['ref']} ({p['fp']}), skipped")
            continue
        if p["fp"] not in cache:
            cache[p["fp"]] = makers[p["fp"]]()
        x, y = p["pos"]
        loc = cq.Location(cq.Vector(x, y, PART_Z), cq.Vector(0, 0, 1), p["rot"])
        assy.add(cache[p["fp"]], name=p["ref"], loc=loc)

    out = vdir / "3d"
    out.mkdir(exist_ok=True)
    step = out / f"{name}.step"
    assy.save(str(step), exportType="STEP")
    assy.save(str(out / f"{name}.glb"), exportType="GLTF", tolerance=0.01, angularTolerance=0.1)
    # the plain STEP is ~30 MB (mostly silkscreen lettering); the zip is what goes in git
    with zipfile.ZipFile(out / f"{name}-step.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(step, step.name)
    print(step)

    SHAPES.mkdir(exist_ok=True)
    for fpname, fname in (
        ("LED_2835_PolarityTolerant", "LED_2835_WarmWhite.step"),
        ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB_C_Receptacle_HRO_TYPE-C-31-M-12.step"),
    ):
        makers[fpname]().save(str(SHAPES / fname), exportType="STEP")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--extract":
        extract(sys.argv[2])
    else:
        build((ROOT / (sys.argv[1] if len(sys.argv) > 1 else "usb-c")).resolve())

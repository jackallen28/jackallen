"""3D: STEP models for the parts KiCad's library lacks, board STEP export, and the
board-to-GLB conversion used for the 3D renders.

* write_custom_models() builds simple, dimensioned STEP models (with colours) for the
  four parts that have no model in KiCad's 3D library: the Alps RK09K pot, the XKB
  TS-1187A switch, the JST SH Qwiic socket and the 0.66" OLED glass.
* assign_models() points those footprints at kicad/lib/VIBEDUINO.3dshapes.
* export_step() runs kicad-cli with KiCad's 3D library, swapping WRL for STEP models.
* step_to_glb() tessellates the board STEP (keeping each face's colour), swaps KiCad's
  plain board body for one textured with the photo renders (mask, copper, silk, logo),
  and writes a GLB for render3d.mjs.
"""

import contextlib
import os
import subprocess

import numpy as np
import pcbnew

SYS_MODELS = os.environ.get("KICAD7_3DMODEL_DIR", "/usr/share/kicad/3dmodels")

COLOURS = {
    "black": (0.07, 0.07, 0.08), "body": (0.16, 0.16, 0.17), "metal": (0.80, 0.80, 0.82),
    "gold": (0.86, 0.70, 0.34), "natural": (0.93, 0.91, 0.84), "glass": (0.10, 0.11, 0.13),
    "screen": (0.015, 0.015, 0.02), "fpc": (0.86, 0.47, 0.13), "shaft": (0.88, 0.88, 0.86),
    "uno": (0.0, 0.55, 0.58),
}


# ------------------------------------------------------------------ geometry
# Footprint coordinates (mm, +Y down), z up from the board surface.  KiCad models use +Y up.
def _box(x0, y0, z0, x1, y1, z1):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeBox(gp_Pnt(min(x0, x1), -max(y0, y1), min(z0, z1)),
                               gp_Pnt(max(x0, x1), -min(y0, y1), max(z0, z1))).Shape()


def _cyl(cx, cy, r, z0, z1):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cx, -cy, z0), gp_Dir(0, 0, 1)), r, z1 - z0).Shape()


def _cut(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    return BRepAlgoAPI_Cut(a, b).Shape()


def tact_switch():
    """XKB TS-1187A-B-A-B: 5.1 x 5.1 mm, 1.5 mm tall SMD tact switch."""
    parts = [("black", _box(-2.55, -2.55, 0, 2.55, 2.55, 0.75)),
             ("metal", _box(-2.55, -2.55, 0.75, 2.55, 2.55, 0.85)),
             ("black", _cyl(0, 0, 1.05, 0.85, 1.5))]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(("metal", _box(sx * 2.4, sy * 1.55, 0, sx * 3.35, sy * 2.15, 0.2)))
    return parts


def jst_sh_vertical():
    """JST BM04B-SRSS-TB: 4-way 1.0 mm SH vertical socket (Qwiic)."""
    shell = _cut(_box(-3.0, -1.9, 0, 3.0, 1.0, 4.25), _box(-2.1, -1.4, 1.0, 2.1, 0.5, 4.5))
    parts = [("natural", shell)]
    for i in range(4):
        x = -1.5 + i
        parts.append(("gold", _box(x - 0.16, -0.61, 1.0, x + 0.16, -0.29, 3.6)))
        parts.append(("metal", _box(x - 0.15, 0.9, 0, x + 0.15, 2.0, 0.2)))
    for sx in (-1, 1):
        parts.append(("metal", _box(sx * 2.45, -2.05, 0, sx * 3.25, -0.35, 1.3)))
    return parts


def rk09k_vertical():
    """Alps RK09K single vertical pot, 9.8 mm body, 6 mm D-shaft."""
    body = _box(1.0, -2.4, 0.5, 13.0, 7.4, 5.5)
    shaft = _cyl(7.5, 2.5, 3.0, 6.0, 18.0)
    shaft = _cut(shaft, _box(9.0, -1.0, 11.0, 11.0, 6.0, 18.5))       # D flat
    parts = [("body", body), ("metal", _box(1.0, -2.4, 5.5, 13.0, 7.4, 6.0)),
             ("metal", _cyl(7.5, 2.5, 3.6, 6.0, 7.0)), ("shaft", shaft)]
    for y in (0.0, 2.5, 5.0):
        parts.append(("metal", _box(-0.4, y - 0.4, -3.0, 0.4, y + 0.4, 1.0)))
        parts.append(("metal", _box(-0.4, y - 0.4, 0.6, 1.0, y + 0.4, 1.0)))
    for y in (-1.9, 6.9):
        parts.append(("metal", _box(6.3, y - 0.25, -3.0, 7.7, y + 0.25, 0.6)))
    return parts


def oled_066():
    """0.66" 64x48 OLED: glass folded over the 28-pin FPC pads (see the footprint's Fab
    layer: glass x -4.8..13.2, active area x 1.04..11.1)."""
    return [("fpc", _box(-1.4, -9.0, 0, 1.4, 9.0, 0.12)),            # FPC tail on the pads
            ("fpc", _box(-5.15, -5.6, 0, -4.8, 5.6, 1.5)),           # fold around the edge
            ("fpc", _box(-4.8, -5.6, 0.12, 13.2, 5.6, 0.25)),        # FPC under the glass
            ("glass", _box(-4.8, -9.25, 0.25, 13.2, 9.25, 1.45)),
            ("screen", _box(1.04, -6.62, 1.45, 11.1, 6.8, 1.47))]


def _abox(x0, y0, z0, x1, y1, z1):
    """Box in Arduino coordinates (+Y up), as used by the shield STEP."""
    return _box(x0, -y1, z0, x1, -y0, z1)


def uno_standin():
    """Simplified Arduino Uno R3 for fit checks: outline, holes, headers, USB-B and DC
    jacks, ATmega328P and ICSP header (dimensions from the Uno R3 drawing; Arduino
    coordinates, origin at the board's lower-left corner)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec
    from . import spec
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in spec.UNO_OUTLINE:
        poly.Add(gp_Pnt(x, y, 0))
    poly.Close()
    pcb = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(), gp_Vec(0, 0, 1.6)).Shape()
    for x, y in [(13.97, 2.54), (15.24, 50.8), (66.04, 7.62), (66.04, 35.56)]:
        hole = _cyl(x, -y, 1.6, -1, 3)                     # _cyl takes footprint (+Y down) coords
        pcb = _cut(pcb, hole)
    parts = [("uno", pcb)]
    for _, y, pins in spec.UNO_HEADERS:
        xs = [x for x, _ in pins]
        body = _abox(min(xs) - 1.27, y - 1.27, 1.6, max(xs) + 1.27, y + 1.27, 10.1)
        for x in xs:
            body = _cut(body, _abox(x - 0.5, y - 0.5, 4.0, x + 0.5, y + 0.5, 10.5))
        parts.append(("black", body))
    x0, y0, x1, y1 = spec.UNO_KEEPOUTS["USB-B jack"]
    parts.append(("metal", _abox(x0, y0, 1.6, x1, y1, 12.5)))
    x0, y0, x1, y1 = spec.UNO_KEEPOUTS["DC jack"]
    parts.append(("black", _abox(x0, y0, 1.6, x1, y1, 12.6)))
    parts.append(("black", _abox(29.0, 12.0, 1.6, 66.5, 21.5, 4.6)))      # DIP-28 socket
    parts.append(("body", _abox(30.0, 13.0, 4.6, 65.5, 20.5, 8.0)))       # ATmega328P
    parts.append(("black", _abox(63.3, 23.5, 1.6, 68.4, 31.1, 4.1)))      # ICSP 2x3
    for i in range(2):
        for j in range(3):
            x, y = 64.6 + 2.54 * i, 24.75 + 2.54 * j
            parts.append(("gold", _abox(x - 0.32, y - 0.32, 4.1, x + 0.32, y + 0.32, 10.0)))
    return parts


CUSTOM = {
    # footprint name: (model file, builder)
    "SW_Push_1P1T_XKB_TS-1187A": ("SW_Push_1P1T_XKB_TS-1187A.step", tact_switch),
    "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical": ("JST_SH_BM04B-SRSS-TB_Vertical.step",
                                                       jst_sh_vertical),
    "Potentiometer_Alps_RK09K_Single_Vertical": ("Potentiometer_Alps_RK09K_Single_Vertical.step",
                                                 rk09k_vertical),
    "OLED_0.66in_64x48_FPC28": ("OLED_0.66in_64x48_FPC28.step", oled_066),
}


@contextlib.contextmanager
def _quiet():
    """OpenCASCADE prints transfer statistics straight to fd 1."""
    import sys
    sys.stdout.flush()
    saved = os.dup(1)
    with open(os.devnull, "w") as null:
        os.dup2(null.fileno(), 1)
        try:
            yield
        finally:
            os.dup2(saved, 1)
            os.close(saved)


def write_step(parts, path, name):
    """Write [(colour, solid)] as one compound with per-face colours (the layout KiCad's own
    library models use, so KiCad keeps the colours when it builds the board STEP)."""
    from OCP.BRep import BRep_Builder
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Compound
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for _, solid in parts:
        builder.Add(comp, solid)
    top = st.AddShape(comp, False)
    TDataStd_Name.Set_s(top, TCollection_ExtendedString(name))
    for colour, solid in parts:
        col = Quantity_Color(*COLOURS[colour], Quantity_TOC_RGB)
        exp = TopExp_Explorer(solid, TopAbs_FACE)
        while exp.More():
            sub = st.AddSubShape(top, exp.Current())
            if not sub.IsNull():
                ct.SetColor(sub, col, XCAFDoc_ColorType.XCAFDoc_ColorSurf)
            exp.Next()
    w = STEPCAFControl_Writer()
    w.SetColorMode(True)
    w.SetNameMode(True)
    with _quiet():
        w.Transfer(doc, STEPControl_AsIs)
        status = w.Write(path)
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {path}")


def write_custom_models(model_dir):
    os.makedirs(model_dir, exist_ok=True)
    out = []
    for fp_name, (fname, builder) in CUSTOM.items():
        path = os.path.join(model_dir, fname)
        write_step(builder(), path, os.path.splitext(fname)[0])
        _strip_step_timestamp(path)
        out.append(fname)
    return out


def _strip_step_timestamp(path):
    """Fixed FILE_NAME timestamp so regenerated models do not churn in git."""
    import re
    txt = open(path).read()
    txt = re.sub(r"(FILE_NAME\('[^']*',)'[^']*'", r"\1'2026-01-01T00:00:00'", txt, count=1)
    open(path, "w").write(txt)


def assign_models(pcb_path, model_dir):
    """Point the custom footprints at kicad/lib/VIBEDUINO.3dshapes (project-relative)."""
    rel = os.path.relpath(model_dir, os.path.dirname(pcb_path)).replace(os.sep, "/")
    board = pcbnew.LoadBoard(pcb_path)
    changed = 0
    for fp in board.GetFootprints():
        name = str(fp.GetFPID().GetLibItemName())
        if name not in CUSTOM:
            continue
        target = f"${{KIPRJMOD}}/{rel}/{CUSTOM[name][0]}"
        models = fp.Models()
        if models.size() == 1 and models[0].m_Filename == target:
            continue
        models.clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = target
        models.push_back(m)
        changed += 1
    if changed:
        pcbnew.SaveBoard(pcb_path, board)
    return changed


def export_step(pcb_path, out_path, origin_mm):
    env = dict(os.environ, KICAD6_3DMODEL_DIR=SYS_MODELS, KICAD7_3DMODEL_DIR=SYS_MODELS)
    r = subprocess.run(["kicad-cli", "pcb", "export", "step", "--subst-models", "-f",
                        "--user-origin", f"{origin_mm[0]}x{origin_mm[1]}mm", "-o", out_path,
                        pcb_path], capture_output=True, text=True, env=env)
    missing = [ln for ln in (r.stdout + r.stderr).splitlines() if "Could not add 3D model" in ln
               or "cannot find" in ln.lower() or "not found" in ln.lower()]
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(r.stdout + r.stderr)
    _strip_step_timestamp(out_path)
    return missing


# ------------------------------------------------------------ STEP -> GLB
def _read_step(path):
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.SetNameMode(True)
    with _quiet():
        r.ReadFile(path)
        r.Transfer(doc)
    return doc


def _colour_of(ct, label_or_shape):
    from OCP.Quantity import Quantity_Color
    from OCP.TDF import TDF_Label
    from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_ColorType
    c = Quantity_Color()
    for t in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
        if isinstance(label_or_shape, TDF_Label):
            ok = XCAFDoc_ColorTool.GetColor_s(label_or_shape, t, c)
        else:
            ok = ct.GetColor(label_or_shape, t, c)
        if ok:
            return (c.Red(), c.Green(), c.Blue())
    return None


def step_meshes(step_path, skip_name_suffix=" PCB", deflection=0.02):
    """[(rgb, vertices Nx3, faces Mx3)] for every coloured face in the STEP, in mm,
    leaving out the board body (named '<board> PCB' by KiCad)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.collections import Sequence_TDF_Label
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    doc = _read_step(step_path)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    out = {}
    meshed = set()

    def name(lab):
        n = TDataStd_Name()
        return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else ""

    def emit(shape, loc, colour):
        key = id(shape)
        if key not in meshed:
            BRepMesh_IncrementalMesh(shape, deflection, False, 0.35, True)
            meshed.add(key)
        trsf = loc.Transformation()
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        while exp.More():
            face = TopoDS.Face(exp.Current())
            fc = _colour_of(ct, face) or colour or (0.6, 0.6, 0.6)
            floc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, floc)
            if tri is not None:
                t2 = trsf.Multiplied(floc.Transformation())
                pts = []
                for i in range(1, tri.NbNodes() + 1):
                    p = tri.Node(i).Transformed(t2)
                    pts.append((p.X(), p.Y(), p.Z()))
                rev = face.Orientation() == TopAbs_REVERSED
                tris = []
                for i in range(1, tri.NbTriangles() + 1):
                    a, b, c = tri.Triangle(i).Get()
                    tris.append((a - 1, c - 1, b - 1) if rev else (a - 1, b - 1, c - 1))
                k = tuple(round(v, 3) for v in fc)
                vs, fs = out.setdefault(k, ([], []))
                base = sum(len(v) for v in vs)
                vs.append(np.array(pts))
                fs.append(np.array(tris) + base)
            exp.Next()

    def walk(lab, loc, colour):
        if name(lab).endswith(skip_name_suffix):
            return
        colour = _colour_of(ct, lab) or colour
        if st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(lab)), colour)
            return
        comps = Sequence_TDF_Label()
        if st.IsAssembly_s(lab) and st.GetComponents_s(lab, comps):
            for i in range(1, comps.Length() + 1):
                walk(comps.Value(i), loc, colour)
            return
        emit(st.GetShape_s(lab), loc, colour)

    free = Sequence_TDF_Label()
    st.GetFreeShapes(free)
    for i in range(1, free.Length() + 1):
        walk(free.Value(i), TopLoc_Location(), None)
    return [(np.array(k), np.vstack(v), np.vstack(f)) for k, (v, f) in out.items()]


def board_mesh(pcb_path, origin_mm, top_png, bottom_png, crop, thickness=1.6):
    """Board body: Edge.Cuts outline with drilled holes, extruded, with the photo renders
    as top/bottom textures.  Coordinates match the STEP export (origin, +Y up)."""
    import trimesh
    from PIL import Image
    from shapely.geometry import Point, Polygon
    board = pcbnew.LoadBoard(pcb_path)
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps)
    ox, oy = origin_mm
    to = lambda p: (pcbnew.ToMM(p.x) - ox, -(pcbnew.ToMM(p.y) - oy))
    ol = ps.Outline(0)
    outline = Polygon([to(ol.CPoint(i)) for i in range(ol.PointCount())])
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = pad.GetDrillSize()
            if d.x > 0:
                holes.append(Point(to(pad.GetPosition())).buffer(pcbnew.ToMM(min(d.x, d.y)) / 2, 12))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            holes.append(Point(to(t.GetPosition())).buffer(pcbnew.ToMM(t.GetDrillValue()) / 2, 8))
    poly = outline
    for h in holes:
        poly = poly.difference(h)
    body = trimesh.creation.extrude_polygon(poly, thickness)
    x0, y0, x1, y1 = crop                      # photo-render crop, KiCad coordinates

    def uv(v, flip):
        X, Y = v[:, 0] + ox, -v[:, 1] + oy
        u = (X - x0) / (x1 - x0)
        if flip:
            u = 1 - u
        return np.column_stack([u, 1 - (Y - y0) / (y1 - y0)])

    meshes = []
    n = body.face_normals
    for sel, png, flip in ((n[:, 2] > 0.9, top_png, False), (n[:, 2] < -0.9, bottom_png, True)):
        m = body.submesh([np.nonzero(sel)[0]], append=True)
        img = Image.open(png).convert("RGBA")
        bg = Image.new("RGBA", img.size, (40, 36, 30, 255))     # holes: board core colour
        img = Image.alpha_composite(bg, img).convert("RGB")
        m.visual = trimesh.visual.TextureVisuals(
            uv=uv(m.vertices, flip),
            material=trimesh.visual.material.PBRMaterial(baseColorTexture=img, metallicFactor=0.0,
                                                         roughnessFactor=0.55))
        meshes.append(m)
    side = body.submesh([np.nonzero(np.abs(n[:, 2]) <= 0.9)[0]], append=True)
    side.visual = trimesh.visual.TextureVisuals(material=_material((0.19, 0.17, 0.13)))
    meshes.append(side)
    return meshes


def _material(rgb):
    """PBR material for a STEP colour (sRGB); glTF colour factors are linear."""
    import trimesh
    r, g, b = rgb
    metal = (min(rgb) > 0.6 and max(rgb) - min(rgb) < 0.08) or (r > 0.7 and g > 0.5 and b < 0.45)
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b)]
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=lin + [1.0], metallicFactor=0.85 if metal else 0.0,
        roughnessFactor=0.35 if metal else 0.6)


def board_items(step_path, pcb_path, origin_mm, top_png, bottom_png, crop):
    """Trimesh meshes for one board: textured body + every part from its STEP."""
    items = board_mesh(pcb_path, origin_mm, top_png, bottom_png, crop)
    items += step_items(step_path)
    return items


def step_items(step_path):
    import trimesh
    items = []
    for rgb, v, f in step_meshes(step_path):
        m = trimesh.Trimesh(v, f, process=False)
        m.visual = trimesh.visual.TextureVisuals(material=_material(rgb))
        items.append(m)
    return items


def write_glb(step_path, pcb_path, origin_mm, top_png, bottom_png, crop, glb_path):
    import trimesh
    scene = trimesh.Scene()
    for i, m in enumerate(board_items(step_path, pcb_path, origin_mm, top_png, bottom_png, crop)):
        scene.add_geometry(m, node_name=f"item_{i}")
    scene.export(glb_path)
    return scene.bounds


def write_scene_glb(groups, glb_path):
    """groups: [(meshes, (dx, dy, dz))] -> one GLB (for the stacked assembly render)."""
    import trimesh
    scene = trimesh.Scene()
    n = 0
    for meshes, (dx, dy, dz) in groups:
        T = np.eye(4)
        T[:3, 3] = (dx, dy, dz)
        for m in meshes:
            scene.add_geometry(m, node_name=f"item_{n}", transform=T)
            n += 1
    scene.export(glb_path)


def write_assembly_step(entries, out_path, name):
    """entries: [(step file, (dx, dy, dz))] -> one STEP assembly (colours kept)."""
    from OCP.collections import Sequence_TDF_Label
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    top = st.NewShape()
    TDataStd_Name.Set_s(top, TCollection_ExtendedString(name))
    seen = {top.Tag()}
    for path, (dx, dy, dz) in entries:
        r = STEPCAFControl_Reader()
        r.SetColorMode(True)
        r.SetNameMode(True)
        with _quiet():
            r.ReadFile(path)
            r.Transfer(doc)
        free = Sequence_TDF_Label()
        st.GetFreeShapes(free)
        for i in range(1, free.Length() + 1):
            lab = free.Value(i)
            if lab.Tag() in seen:
                continue
            seen.add(lab.Tag())
            t = gp_Trsf()
            t.SetTranslation(gp_Vec(dx, dy, dz))
            st.AddComponent(top, lab, TopLoc_Location(t))
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetColorMode(True)
    w.SetNameMode(True)
    with _quiet():
        w.Transfer(doc, STEPControl_AsIs)
        status = w.Write(out_path)
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {out_path}")
    _strip_step_timestamp(out_path)

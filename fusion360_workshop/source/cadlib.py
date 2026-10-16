"""Shared helpers for the Fusion 360 animation workshop assemblies.

* Part / Asm  - a tiny product-structure model (unique parts, nested assemblies,
                instances with rigid placements).
* export_step - writes the structure to an AP214 STEP file with real assembly
                structure, part names and colours (what Fusion 360 turns into
                components on import).
* geometry helpers - involute spur gears, fasteners, sectors, cylinders ...

All units are millimetres, Z is up.
"""
import math
from math import sin, cos, tan, pi, sqrt, radians

import cadquery as cq
from OCP.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
from OCP.TDataStd import TDataStd_Name
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

# --------------------------------------------------------------------------
# Product structure
# --------------------------------------------------------------------------

COLOURS = {
    # name: sRGB 0-255
    "steel": (170, 174, 180),
    "dark_steel": (95, 100, 108),
    "black_oxide": (38, 38, 42),
    "aluminium": (200, 205, 212),
    "cast_iron": (78, 82, 88),
    "brass": (201, 160, 72),
    "blue": (40, 96, 190),
    "red": (200, 30, 35),
    "orange": (230, 120, 30),
    "green": (40, 150, 80),
    "yellow": (235, 190, 40),
    "rubber": (30, 30, 32),
    "white": (235, 235, 230),
    "copper": (184, 115, 51),
    "gunmetal": (60, 64, 72),
    "silver_paint": (185, 188, 192),
    "purple": (120, 70, 170),
    "teal": (30, 140, 140),
    "gold": (212, 175, 55),
    "ceramic": (245, 245, 240),
}


class Part:
    """A unique piece of geometry (becomes one Fusion component)."""

    def __init__(self, name, shape, colour="steel"):
        if isinstance(shape, cq.Workplane):
            shape = shape.val() if len(shape.vals()) == 1 else cq.Compound.makeCompound(shape.vals())
        if isinstance(shape, cq.Compound):
            solids = shape.Solids()
            if len(solids) == 1:
                shape = solids[0]
        self.name = name
        self.shape = shape
        self.colour = colour


class Asm:
    """An assembly node; children are (Part|Asm, gp_Trsf) instances."""

    def __init__(self, name):
        self.name = name
        self.children = []

    def add(self, child, trsf=None):
        self.children.append((child, trsf if trsf is not None else gp_Trsf()))
        return self

    # walk leaves with accumulated transforms --------------------------------
    def leaves(self, parent=None, path=()):
        parent = parent if parent is not None else gp_Trsf()
        counters = {}
        for child, t in self.children:
            total = parent.Multiplied(t)
            counters[child.name] = counters.get(child.name, 0) + 1
            label = f"{child.name}:{counters[child.name]}"
            if isinstance(child, Part):
                yield path + (label,), child, total
            else:
                yield from child.leaves(total, path + (label,))


def place(t=(0, 0, 0), rots=()):
    """Rigid transform: apply rotations (axis, deg) in order, then translate."""
    tr = gp_Trsf()
    for axis, deg in rots:
        r = gp_Trsf()
        if isinstance(axis, str):
            d = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
        else:
            d = axis
        r.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(*d)), radians(deg))
        tr = r.Multiplied(tr)
    m = gp_Trsf()
    m.SetTranslation(gp_Vec(*t))
    return m.Multiplied(tr)


def compose(a, b):
    """a * b  (apply b first, then a)."""
    return a.Multiplied(b)


# --------------------------------------------------------------------------
# STEP export
# --------------------------------------------------------------------------

def export_step(root, path, description=""):
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    labels = {}

    def lab_for(node):
        if id(node) in labels:
            return labels[id(node)]
        if isinstance(node, Part):
            lab = st.AddShape(node.shape.wrapped, False)
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString(node.name))
            r, g, b = COLOURS[node.colour]
            col = Quantity_Color(r / 255, g / 255, b / 255, Quantity_TypeOfColor.Quantity_TOC_sRGB)
            ct.SetColor(lab, col, XCAFDoc_ColorType.XCAFDoc_ColorGen)
            ct.SetColor(lab, col, XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        else:
            lab = st.NewShape()
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString(node.name))
            for child, t in node.children:
                clab = lab_for(child)
                comp = st.AddComponent(lab, clab, TopLoc_Location(t))
                TDataStd_Name.Set_s(comp, TCollection_ExtendedString(child.name))
        labels[id(node)] = lab
        return lab

    lab_for(root)
    st.UpdateAssemblies()

    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    # header
    model = writer.ChangeWriter().Model()
    from OCP.APIHeaderSection import APIHeaderSection_MakeHeader
    hdr = APIHeaderSection_MakeHeader(model)
    hdr.SetName(TCollection_HAsciiString(root.name))
    hdr.SetAuthorValue(1, TCollection_HAsciiString("Fusion 360 Animation Workshop"))
    hdr.SetOrganizationValue(1, TCollection_HAsciiString("Workshop example model"))
    hdr.SetOriginatingSystem(TCollection_HAsciiString("CadQuery / OpenCascade"))
    if description:
        hdr.SetDescriptionValue(1, TCollection_HAsciiString(description))
    status = writer.Write(path)
    return status


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def _bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    return b


def volume(shape):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def check_assembly(root, tol=0.5, verbose=True):
    """Validity + pairwise interference check of all leaf instances."""
    items = []
    bad = []
    for path, part, t in root.leaves():
        s = part.shape.wrapped.Moved(TopLoc_Location(t))
        items.append(("/".join(path), s, _bbox(s)))
    for part in {id(p): p for _, p, _ in root.leaves()}.values():
        if not BRepCheck_Analyzer(part.shape.wrapped).IsValid():
            bad.append(part.name)
    clashes = []
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            if items[i][2].IsOut(items[j][2]):
                continue
            common = BRepAlgoAPI_Common(items[i][1], items[j][1])
            v = volume(common.Shape())
            if v > tol:
                clashes.append((items[i][0], items[j][0], round(v, 2)))
    if verbose:
        print(f"  instances: {n}, unique parts: {len({id(p) for _, p, _ in root.leaves()})}")
        print(f"  invalid parts: {bad or 'none'}")
        print(f"  clashes > {tol} mm^3: {len(clashes)}")
        for c in clashes:
            print("    ", c)
    return clashes, bad


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def V(x, y, z=0.0):
    return cq.Vector(x, y, z)


def polar(r, a):
    return V(r * cos(a), r * sin(a))


def cyl(r, length, base=(0, 0, 0), axis=(0, 0, 1)):
    return cq.Solid.makeCylinder(r, length, V(*base), V(*axis))


def cyl_between(r, p0, p1):
    p0, p1 = cq.Vector(*p0), cq.Vector(*p1)
    d = p1 - p0
    return cq.Solid.makeCylinder(r, d.Length, p0, d.normalized())


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def sphere(r, c=(0, 0, 0)):
    return cq.Workplane().sphere(r).val().translate(V(*c))


def tube(r_out, r_in, length, base=(0, 0, 0), axis=(0, 0, 1)):
    return cyl(r_out, length, base, axis).cut(cyl(r_in, length, base, axis))


def sector(r1, r2, a1, a2, z0, z1):
    """Annular sector between radii r1..r2 and angles a1..a2 (deg), z0..z1."""
    a1, a2 = radians(a1), radians(a2)
    am = (a1 + a2) / 2
    w = (cq.Workplane("XY")
         .moveTo(r1 * cos(a1), r1 * sin(a1))
         .lineTo(r2 * cos(a1), r2 * sin(a1))
         .threePointArc((r2 * cos(am), r2 * sin(am)), (r2 * cos(a2), r2 * sin(a2)))
         .lineTo(r1 * cos(a2), r1 * sin(a2)))
    if r1 > 0:
        w = w.threePointArc((r1 * cos(am), r1 * sin(am)), (r1 * cos(a1), r1 * sin(a1)))
    w = w.close().extrude(z1 - z0).translate((0, 0, z0))
    return w.val()


def revolve_profile(pts, angle=360):
    """Revolve a closed (r, z) polyline about the Z axis."""
    w = cq.Workplane("XZ").polyline(pts).close().revolve(angle, (0, 0, 0), (0, 1, 0))
    return w.val()


def solid_of(obj):
    """Largest solid of a Workplane / Shape / Compound."""
    if isinstance(obj, cq.Workplane):
        obj = obj.val()
    solids = obj.Solids()
    return max(solids, key=lambda x: volume(x.wrapped)) if solids else obj


def fuse_all(shapes):
    shapes = list(shapes)
    out = shapes[0]
    if len(shapes) > 1:
        out = out.fuse(*shapes[1:])
    return out.clean()


def cut_all(base, tools):
    tools = list(tools)
    if not tools:
        return base
    return base.cut(*tools).clean()


def hexagon_prism(af, h, z0=0.0, chamfer=True):
    """Hex prism, across-flats af, from z0 to z0+h, axis Z."""
    r = af / sqrt(3)  # circumradius
    w = cq.Workplane("XY").polygon(6, 2 * r).extrude(h).translate((0, 0, z0))
    s = w.val()
    if chamfer:
        # classic 30 deg chamfer: intersect with double cone
        c = (cq.Workplane("XZ")
             .polyline([(0, z0), (af / 2 * 0.95, z0), (r + 0.2, z0 + (r + 0.2 - af / 2 * 0.95) * 0.58),
                        (r + 0.2, z0 + h - (r + 0.2 - af / 2 * 0.95) * 0.58), (af / 2 * 0.95, z0 + h), (0, z0 + h)])
             .close().revolve(360, (0, 0, 0), (0, 1, 0)).val())
        s = s.intersect(c)
    return s


def socket_cap_screw(d, length):
    """ISO 4762 style. Head z=0..d (above), shank z=-length..0 (below)."""
    head = cyl(0.75 * d, d, (0, 0, 0))
    head = head.fuse(cyl(0.75 * d - 0.4, 0.3, (0, 0, d - 0.01))).clean()  # tiny top bevel step
    sock = (cq.Workplane("XY").polygon(6, (0.5 * d) / cos(pi / 6) * 1.0).extrude(0.6 * d)
            .translate((0, 0, d - 0.6 * d + 0.3)).val())
    head = head.cut(sock)
    shank = cyl(d / 2, length, (0, 0, -length))
    tip = cyl(d / 2 + 1, 0.6, (0, 0, -length - 0.0)).cut(
        cq.Solid.makeCone(d / 2 - 0.5, d / 2 + 0.1, 0.6, V(0, 0, -length)))
    s = head.fuse(shank).clean().cut(tip)
    return s


def flange_bolt(d, length, af=None, head_h=None):
    """Hex flange bolt. Head z=0..head_h, shank z=-length..0."""
    af = af or 1.5 * d
    head_h = head_h or 0.7 * d
    flange = cq.Solid.makeCone(af * 0.62, af * 0.55, 0.25 * d, V(0, 0, 0))
    hexh = hexagon_prism(af, head_h - 0.25 * d, 0.25 * d)
    shank = cyl(d / 2, length, (0, 0, -length))
    return fuse_all([flange, hexh, shank])


def hex_bolt(d, length, af=None, head_h=None):
    af = af or 1.5 * d
    head_h = head_h or 0.65 * d
    hexh = hexagon_prism(af, head_h, 0)
    shank = cyl(d / 2, length, (0, 0, -length))
    return fuse_all([hexh, shank])


def hex_nut(af, h, bore):
    n = hexagon_prism(af, h, 0)
    return n.cut(cyl(bore / 2, h + 2, (0, 0, -1)))


# ---------------------------- involute gears -------------------------------

def involute_gear_face(m, z, pa_deg=20.0, backlash=0.1):
    """Planar face (XY) of an involute spur gear, tooth 0 centred on +X."""
    pa = radians(pa_deg)
    r = m * z / 2
    rb = r * cos(pa)
    ra = r + m
    rf = r - 1.25 * m
    inv = lambda a: tan(a) - a
    half_pitch = pi / (2 * z) - (backlash / 2) / r
    theta0 = half_pitch + inv(pa)          # flank angle at base circle
    r_start = max(rb, rf)
    t0 = sqrt(max((r_start / rb) ** 2 - 1, 0))
    t1 = sqrt((ra / rb) ** 2 - 1)
    n = 10
    pts = []
    for i in range(n):
        t = t0 + (t1 - t0) * (i / (n - 1)) ** 1.3
        x = rb * (cos(t) + t * sin(t))
        y = rb * (sin(t) - t * cos(t))
        pts.append((math.hypot(x, y), math.atan2(y, x)))
    edges = []
    for i in range(z):
        c = 2 * pi * i / z
        lower = [polar(rr, c - theta0 + ph) for rr, ph in pts]
        upper = [polar(rr, c + theta0 - ph) for rr, ph in pts]
        nxt = c + 2 * pi / z
        if rf < rb:
            edges.append(cq.Edge.makeLine(polar(rf, c - theta0), lower[0]))
        edges.append(cq.Edge.makeSpline(lower))
        edges.append(cq.Edge.makeThreePointArc(lower[-1], polar(ra, c), upper[-1]))
        edges.append(cq.Edge.makeSpline(list(reversed(upper))))
        if rf < rb:
            edges.append(cq.Edge.makeLine(upper[0], polar(rf, c + theta0)))
            a_end = polar(rf, nxt - theta0)
            a_start = polar(rf, c + theta0)
        else:
            a_start = upper[0]
            a_end = polar(pts[0][0], nxt - theta0 + pts[0][1])
        edges.append(cq.Edge.makeThreePointArc(a_start, polar(rf if rf < rb else pts[0][0], c + pi / z), a_end))
    wire = cq.Wire.assembleEdges(edges)
    return cq.Face.makeFromWires(wire), dict(r=r, ra=ra, rf=rf, rb=rb)


def spur_gear(m, z, width, bore, pa_deg=20.0, backlash=0.1):
    face, info = involute_gear_face(m, z, pa_deg, backlash)
    g = cq.Solid.extrudeLinear(face, V(0, 0, width))
    if bore:
        g = g.cut(cyl(bore / 2, width + 2, (0, 0, -1)))
    return g, info


# ---------------------------- springs -------------------------------------

def helical_spring(mean_r, wire_r, length, coils):
    """Closed & ground compression spring, z = 0..length."""
    pitch = (length - 2 * wire_r) / coils
    h = length + 4 * wire_r
    helix = cq.Wire.makeHelix(pitch=pitch, height=h, radius=mean_r).translate(V(0, 0, -2 * wire_r))
    prof = cq.Workplane("XZ").center(mean_r, -2 * wire_r).circle(wire_r)
    s = prof.sweep(cq.Workplane().add(helix), isFrenet=True).val()
    # grind both ends flat so the spring sits square on its seats
    s = s.cut(box(-50, 50, -50, 50, -20, 0)).cut(box(-50, 50, -50, 50, length, length + 20))
    return s

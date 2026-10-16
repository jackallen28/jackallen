"""Read a STEP file back (as Fusion would), print its component tree and
optionally export a tessellated mesh JSON for previews.

usage: python inspect_step.py file.step [mesh.json] [deflection]
"""
import sys, json, base64, collections
import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool, XCAFDoc_ColorType, XCAFDoc_ColorTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor
from OCP.gp import gp_Trsf
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location


def name_of(lab):
    attr = TDataStd_Name()
    if lab.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return attr.Get().ToExtString()
    return "?"


def read(path):
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    app.InitDocument(doc)
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.SetNameMode(True)
    r.ReadFile(path)
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    return doc, st, ct


def walk(st, ct, lab, trsf, path, out, tree, depth=0):
    if XCAFDoc_ShapeTool.IsAssembly_s(lab):
        comps = TDF_LabelSequence()
        XCAFDoc_ShapeTool.GetComponents_s(lab, comps)
        counts = collections.Counter()
        for i in range(1, comps.Length() + 1):
            c = comps.Value(i)
            ref = TDF_Label()
            XCAFDoc_ShapeTool.GetReferredShape_s(c, ref)
            loc = XCAFDoc_ShapeTool.GetLocation_s(c)
            nm = name_of(ref)
            counts[nm] += 1
            occ = f"{nm}:{counts[nm]}"
            is_asm = XCAFDoc_ShapeTool.IsAssembly_s(ref)
            tree.append(("  " * (depth + 1)) + occ + ("  [sub-assembly]" if is_asm else ""))
            walk(st, ct, ref, trsf.Multiplied(loc.Transformation()), path + [occ], out, tree, depth + 1)
    else:
        shape = XCAFDoc_ShapeTool.GetShape_s(lab)
        col = Quantity_Color()
        ok = XCAFDoc_ColorTool.GetColor_s(lab, XCAFDoc_ColorType.XCAFDoc_ColorSurf, col) or \
            XCAFDoc_ColorTool.GetColor_s(lab, XCAFDoc_ColorType.XCAFDoc_ColorGen, col)
        rgb = col.Values(Quantity_TypeOfColor.Quantity_TOC_sRGB) if ok else (0.7, 0.7, 0.7)
        out.append(dict(path=path, name=name_of(lab), shape=shape, trsf=trsf, rgb=rgb))


def mesh_of(shape, defl):
    BRepMesh_IncrementalMesh(shape, defl, False, 0.35, True)
    verts, tris = [], []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            t = loc.Transformation()
            base = len(verts)
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(t)
                verts.append((p.X(), p.Y(), p.Z()))
            rev = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                if rev:
                    b, c = c, b
                tris.append((base + a - 1, base + b - 1, base + c - 1))
        exp.Next()
    return np.array(verts, dtype=np.float32), np.array(tris, dtype=np.uint32)


def main():
    path = sys.argv[1]
    doc, st, ct = read(path)
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    out, tree = [], []
    for i in range(1, roots.Length() + 1):
        lab = roots.Value(i)
        tree.append(name_of(lab) + "  [root]")
        walk(st, ct, lab, gp_Trsf(), [], out, tree)
    print("\n".join(tree))
    uniq = collections.Counter(o["name"] for o in out)
    print(f"\nleaf instances: {len(out)}   unique parts: {len(uniq)}")
    if len(sys.argv) > 2:
        defl = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
        cache = {}
        parts, insts = [], []
        for o in out:
            key = o["name"]
            if key not in cache:
                v, t = mesh_of(o["shape"], defl)
                cache[key] = len(parts)
                parts.append(dict(name=key, rgb=[round(c, 4) for c in o["rgb"]],
                                  v=base64.b64encode(v.tobytes()).decode(),
                                  t=base64.b64encode(t.tobytes()).decode(), ntri=len(t)))
            tr = o["trsf"]
            m = [[tr.Value(r, c) for c in range(1, 5)] for r in range(1, 4)]
            insts.append(dict(part=cache[key], path=o["path"], m=m))
        json.dump(dict(parts=parts, instances=insts), open(sys.argv[2], "w"))
        print("triangles (unique):", sum(p["ntri"] for p in parts))


if __name__ == "__main__":
    main()

"""00 STARTER - Jar with screw lid (3 components).

The simplest possible assembly: a jar, a lid and the rubber seal inside the lid.
Z up, jar standing on the XY plane, jar axis = Z axis.
Expected animation: unscrew the lid (rotate ~2 turns while it rises 10 mm),
lift it clear, then drop the seal out of the lid.
"""
import sys
from cadlib import *


def jar():
    # (r, z) half-section: body r40, shoulder, neck r33 with a lip bead
    pts = [(0, 0), (38, 0), (40, 2), (40, 78), (33, 88), (33, 92), (34.2, 93), (34.2, 95),
           (33, 96), (33, 104), (30, 104), (30, 88), (37, 78), (37, 4), (0, 4)]
    s = revolve_profile(pts)
    return s


def lid():
    # cap: top plate z 106..110, skirt r 35..38 down to z 92, knurled outside
    s = tube(38, 35, 14, (0, 0, 92)).fuse(cyl(38, 4, (0, 0, 106))).clean()
    s = cq.Workplane().add(s).faces(">Z").edges().fillet(2).val()
    knurls = [box(37, 39, -1, 1, 93, 105).rotate(V(0, 0, 0), V(0, 0, 1), k * 10) for k in range(36)]
    s = cut_all(s, knurls)
    return s.cut(tube(30, 22, 0.8, (0, 0, 109.2)))           # shallow ring on the top face


def seal():
    return tube(34.9, 29.5, 2, (0, 0, 104))                  # sits on the jar rim, under the lid top


def build():
    root = Asm("Jar with Lid")
    root.add(Part("Jar", jar(), "teal"))
    root.add(Part("Lid Seal", seal(), "rubber"))
    root.add(Part("Lid", lid(), "red"))
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "00_Starter_Jar_With_Lid.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Starter: jar with screw lid and seal"))

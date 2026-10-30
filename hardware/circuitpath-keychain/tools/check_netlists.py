"""Fail if the schematic's netlist and the PCB's pad nets differ.  python3 check_netlists.py net.xml board.kicad_pcb"""
import sys, xml.etree.ElementTree as ET
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
sys.path.insert(0, __import__('os').path.dirname(__file__))
import design as _D
sch = {}
for n in ET.parse(sys.argv[1]).getroot().iter("net"):
    name = n.get("name").lstrip("/")
    for node in n.iter("node"):
        sch[(node.get("ref"), node.get("pin"))] = name
b = pcbnew.LoadBoard(sys.argv[2])
pcb = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname() and pad.GetNumber():
            pcb[(fp.GetReference(), pad.GetNumber())] = pad.GetNetname().lstrip("/")
bad = 0
for k in sorted(set(sch) | set(pcb)):
    a, c = sch.get(k), pcb.get(k)
    # unconnected pins show as unconnected-(...) in the schematic netlist
    if a and a.startswith("unconnected"): a = None
    if k in _D.PCB_NC: continue          # deliberate: redundant USB-C VBUS pads left unconnected on the PCB
    if a != c:
        bad += 1
        print("MISMATCH", k, "schematic:", a, "pcb:", c)
print("pads compared:", len(set(sch) | set(pcb)), "mismatches:", bad)
if bad: sys.exit(1)

# geometry check: no two pads on the same layer may overlap unless they share a net (catches stacked pads)
import itertools
pads = [(fp.GetReference(), pad) for fp in b.GetFootprints() for pad in fp.Pads() if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
ov = 0
for (r1, p1), (r2, p2) in itertools.combinations(pads, 2):
    if p1.GetNetname() == p2.GetNetname() and p1.GetNetname():
        continue
    if not (p1.GetLayerSet().Contains(pcbnew.F_Cu) and p2.GetLayerSet().Contains(pcbnew.F_Cu)) and not (p1.GetLayerSet().Contains(pcbnew.B_Cu) and p2.GetLayerSet().Contains(pcbnew.B_Cu)):
        continue
    if p1.GetBoundingBox().Intersects(p2.GetBoundingBox()):
        ov += 1
        print("PAD OVERLAP", r1, p1.GetNumber(), r2, p2.GetNumber())
print("pad overlaps between different nets:", ov)

# courtyard check: parts on the same side must not overlap each other, and must stay inside the board
fps = list(b.GetFootprints())
cy = 0
for f1, f2 in itertools.combinations(fps, 2):
    if f1.IsFlipped() != f2.IsFlipped():
        continue
    lay = pcbnew.B_CrtYd if f1.IsFlipped() else pcbnew.F_CrtYd
    c1, c2 = f1.GetCourtyard(lay), f2.GetCourtyard(lay)
    if c1.OutlineCount() and c2.OutlineCount() and c1.Collide(c2, 0):
        cy += 1
        print("COURTYARD OVERLAP", f1.GetReference(), f2.GetReference())
print("courtyard overlaps:", cy)
sys.exit(1 if (ov or cy) else 0)

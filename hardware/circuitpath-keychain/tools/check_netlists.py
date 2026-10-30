"""Fail if the schematic's netlist and the PCB's pad nets differ.  python3 check_netlists.py net.xml board.kicad_pcb"""
import sys, xml.etree.ElementTree as ET
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
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
    if a != c:
        bad += 1
        print("MISMATCH", k, "schematic:", a, "pcb:", c)
print("pads compared:", len(set(sch) | set(pcb)), "mismatches:", bad)
sys.exit(1 if bad else 0)

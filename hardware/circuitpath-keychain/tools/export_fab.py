"""Write fab/BOM-JLCPCB.csv, fab/BOM-full.csv and fab/CPL-JLCPCB.csv from design.py + the board.  python3 export_fab.py board.kicad_pcb"""
import csv, os, sys, collections
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, os.path.dirname(__file__))
import pcbnew
import design as D

out = os.path.join(os.path.dirname(__file__), "..", "fab")
os.makedirs(out, exist_ok=True)
assembled = [p for p in D.PARTS if p["lcsc"]]
groups = collections.OrderedDict()
for p in assembled:
    groups.setdefault((p["value"], p["fp"].split(":")[1], p["lcsc"], p["side"]), []).append(p)

def key(r):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", r)]

with open(os.path.join(out, "BOM-JLCPCB.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, lcsc, side), ps in groups.items():
        w.writerow([val, ",".join(sorted((p["ref"] for p in ps), key=key)), fp, lcsc])

with open(os.path.join(out, "BOM-full.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "Designators", "Value", "Footprint", "Side", "Manufacturer part", "LCSC #", "LCSC number status", "What it is"])
    for (val, fp, lcsc, side), ps in groups.items():
        ps = sorted(ps, key=lambda p: key(p["ref"]))
        status = "verified on lcsc.com/jlcpcb.com" if ps[0]["ok"] else "FROM MEMORY - check in JLCPCB parts search"
        w.writerow([len(ps), ",".join(p["ref"] for p in ps) if len(ps) < 8 else ps[0]["ref"] + "..." + ps[-1]["ref"],
                    val, fp, "Top" if side == "F" else "Bottom", ps[0]["mpn"], lcsc, status, ps[0]["desc"]])
    for p in D.PARTS:
        if not p["lcsc"]:
            w.writerow([1, p["ref"], p["value"], p["fp"].split(":")[1], "Top", "", "", "NOT assembled by JLCPCB SMT", p["desc"]])

b = pcbnew.LoadBoard(sys.argv[1])
with open(os.path.join(out, "CPL-JLCPCB.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    lc = {p["ref"] for p in assembled}
    for fp in sorted(b.GetFootprints(), key=lambda q: key(q.GetReference())):
        if fp.GetReference() not in lc:
            continue
        pos = fp.GetPosition()
        w.writerow([fp.GetReference(), "%.4fmm" % pcbnew.ToMM(pos.x), "%.4fmm" % (-pcbnew.ToMM(pos.y)),
                    "Bottom" if fp.IsFlipped() else "Top", "%.0f" % (fp.GetOrientationDegrees() % 360)])
print("wrote BOM-JLCPCB.csv, BOM-full.csv, CPL-JLCPCB.csv")

#!/usr/bin/env python3
"""Export JLCPCB fabrication + assembly files for the USB LED Bar.

Produces, in ../jlcpcb/:
  usb-led-bar_gerbers.zip  - Gerbers + Excellon drills (upload on the PCB order page)
  usb-led-bar_bom.csv      - BOM in JLCPCB format (Comment, Designator, Footprint, LCSC Part #)
  usb-led-bar_cpl.csv      - pick-and-place in JLCPCB format (Designator, Mid X, Mid Y, Layer, Rotation)

Needs only the Python standard library and `kicad-cli` (KiCad 7 or newer) on PATH.
Gerber/drill options follow JLCPCB's "How to generate Gerber and drill files in KiCad" guide.
"""
import csv
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict
from pathlib import Path

PROJECT = "usb-led-bar"
ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / f"{PROJECT}.kicad_pcb"
SCH = ROOT / f"{PROJECT}.kicad_sch"
OUT = ROOT / "jlcpcb"

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# Extra rotation (degrees) added to KiCad's value for footprints whose JLCPCB part
# model is drawn differently. Empty by default - if JLCPCB's placement preview shows
# an LED backwards, add e.g. {"LED_2835_PolarityTolerant": 180} and re-run.
ROTATION_OFFSETS = {}


def run(*args):
    subprocess.run(["kicad-cli", *map(str, args)], check=True)


def export_gerbers(tmp):
    gerb = tmp / "gerbers"
    gerb.mkdir()
    run(
        "pcb", "export", "gerbers", PCB,
        "--output", f"{gerb}/",
        "--layers", LAYERS,
        "--subtract-soldermask",
        "--no-x2",
        "--no-netlist",
        "--use-drill-file-origin",
        "--precision", "6",
    )
    run(
        "pcb", "export", "drill", PCB,
        "--output", f"{gerb}/",
        "--format", "excellon",
        "--drill-origin", "plot",
        "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate",
        "--excellon-separate-th",
    )
    files = sorted(f for f in gerb.iterdir() if f.suffix != ".gbrjob")  # JLCPCB ignores job files
    zpath = OUT / f"{PROJECT}_gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    return zpath, [f.name for f in files]


def export_cpl(tmp):
    pos = tmp / "pos.csv"
    run(
        "pcb", "export", "pos", PCB,
        "--output", pos,
        "--format", "csv",
        "--units", "mm",
        "--side", "front",
        "--smd-only",
        "--use-drill-file-origin",
    )
    cpl = OUT / f"{PROJECT}_cpl.csv"
    with open(pos, newline="") as fin, open(cpl, "w", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(fin):
            rot = (float(row["Rot"]) + ROTATION_OFFSETS.get(row["Package"], 0)) % 360
            layer = "Top" if row["Side"] == "top" else "Bottom"
            w.writerow([row["Ref"], f'{float(row["PosX"]):.4f}mm', f'{float(row["PosY"]):.4f}mm', layer, f"{rot:g}"])
    return cpl


def export_bom(tmp):
    net = tmp / "netlist.xml"
    run("sch", "export", "netlist", SCH, "--output", net, "--format", "kicadxml")
    groups = OrderedDict()
    for comp in ET.parse(net).getroot().find("components"):
        fields = {f.get("name"): f.text for f in comp.iter("field")}
        lcsc = fields.get("LCSC")
        if not lcsc:  # J1 (hand-soldered cable) and mounting holes are not assembled
            continue
        footprint = comp.findtext("footprint", "").split(":")[-1]
        comment = comp.findtext("value", "")
        if fields.get("MPN"):
            comment = f"{comment} {fields['MPN']}"
        key = (comment, footprint, lcsc)
        groups.setdefault(key, []).append(comp.get("ref"))
    bom = OUT / f"{PROJECT}_bom.csv"
    with open(bom, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (comment, footprint, lcsc), refs in groups.items():
            refs.sort(key=lambda r: (r.rstrip("0123456789"), int(r[len(r.rstrip("0123456789")):] or 0)))
            w.writerow([comment, ",".join(refs), footprint, lcsc])
    return bom


def main():
    if shutil.which("kicad-cli") is None:
        raise SystemExit("kicad-cli not found - install KiCad 7+ and make sure kicad-cli is on PATH")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        zpath, names = export_gerbers(tmp)
        cpl = export_cpl(tmp)
        bom = export_bom(tmp)
    print(f"{zpath.relative_to(ROOT)}: {', '.join(names)}")
    print(cpl.relative_to(ROOT))
    print(bom.relative_to(ROOT))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export JLCPCB fabrication + assembly files for the USB LED Bar variants.

usage: python3 scripts/export_jlcpcb.py [variant-dir ...]     (default: jst usb-c)

For each variant directory (containing one <name>.kicad_pcb / .kicad_sch) this writes,
in <variant-dir>/jlcpcb/:
  <name>_gerbers.zip  - Gerbers + Excellon drills (upload on the PCB order page)
  <name>_bom.csv      - BOM in JLCPCB format (Comment, Designator, Footprint, LCSC Part #)
  <name>_cpl.csv      - pick-and-place in JLCPCB format (Designator, Mid X, Mid Y, Layer, Rotation)

Needs only the Python standard library and `kicad-cli` (KiCad 7 or newer) on PATH.
Gerber/drill options follow JLCPCB's "How to generate Gerber and drill files in KiCad" guide.
"""
import csv
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VARIANTS = ["jst", "usb-c"]
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# Extra rotation (degrees) added to KiCad's value for footprints whose JLCPCB part
# model is drawn differently. Empty by default - if JLCPCB's placement preview shows
# a part turned the wrong way, add e.g. {"LED_2835_PolarityTolerant": 180} and re-run.
ROTATION_OFFSETS = {}


def run(*args):
    subprocess.run(["kicad-cli", *map(str, args)], check=True, stdout=subprocess.DEVNULL)


def export_gerbers(pcb, out, name, tmp):
    gerb = tmp / "gerbers"
    gerb.mkdir()
    run(
        "pcb", "export", "gerbers", pcb,
        "--output", f"{gerb}/",
        "--layers", LAYERS,
        "--subtract-soldermask",
        "--no-x2",
        "--no-netlist",
        "--use-drill-file-origin",
        "--precision", "6",
    )
    run(
        "pcb", "export", "drill", pcb,
        "--output", f"{gerb}/",
        "--format", "excellon",
        "--drill-origin", "plot",
        "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate",
        "--excellon-separate-th",
    )
    files = sorted(f for f in gerb.iterdir() if f.suffix != ".gbrjob")  # JLCPCB ignores job files
    zpath = out / f"{name}_gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    return zpath


def export_cpl(pcb, out, name, tmp):
    pos = tmp / "pos.csv"
    run(
        "pcb", "export", "pos", pcb,
        "--output", pos,
        "--format", "csv",
        "--units", "mm",
        "--side", "front",
        "--smd-only",
        "--use-drill-file-origin",
    )
    cpl = out / f"{name}_cpl.csv"
    with open(pos, newline="") as fin, open(cpl, "w", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(fin):
            rot = (float(row["Rot"]) + ROTATION_OFFSETS.get(row["Package"], 0)) % 360
            layer = "Top" if row["Side"] == "top" else "Bottom"
            w.writerow([row["Ref"], f'{float(row["PosX"]):.4f}mm', f'{float(row["PosY"]):.4f}mm', layer, f"{rot:g}"])
    return cpl


def ref_key(ref):
    prefix = ref.rstrip("0123456789")
    return prefix, int(ref[len(prefix):] or 0)


def export_bom(sch, out, name, tmp):
    net = tmp / "netlist.xml"
    run("sch", "export", "netlist", sch, "--output", net, "--format", "kicadxml")
    groups = OrderedDict()
    for comp in ET.parse(net).getroot().find("components"):
        fields = {f.get("name"): f.text for f in comp.iter("field")}
        lcsc = fields.get("LCSC")
        if not lcsc:
            continue
        footprint = comp.findtext("footprint", "").split(":")[-1]
        comment = comp.findtext("value", "")
        if fields.get("MPN"):
            comment = f"{comment} {fields['MPN']}"
        groups.setdefault((comment, footprint, lcsc), []).append(comp.get("ref"))
    bom = out / f"{name}_bom.csv"
    with open(bom, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (comment, footprint, lcsc), refs in sorted(groups.items(), key=lambda kv: ref_key(min(kv[1], key=ref_key))):
            w.writerow([comment, ",".join(sorted(refs, key=ref_key)), footprint, lcsc])
    return bom


def export_variant(vdir):
    pcb = next(vdir.glob("*.kicad_pcb"))
    sch = pcb.with_suffix(".kicad_sch")
    name = pcb.stem
    out = vdir / "jlcpcb"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        files = [export_gerbers(pcb, out, name, tmp), export_bom(sch, out, name, tmp), export_cpl(pcb, out, name, tmp)]
    for f in files:
        print(f.relative_to(ROOT))


def main():
    if shutil.which("kicad-cli") is None:
        raise SystemExit("kicad-cli not found - install KiCad 7+ and make sure kicad-cli is on PATH")
    for v in sys.argv[1:] or DEFAULT_VARIANTS:
        export_variant((ROOT / v).resolve())


if __name__ == "__main__":
    main()

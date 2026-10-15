#!/usr/bin/env python3
"""Release outputs for every routed board: schematic (checked against the PCB netlist),
BOM, JLCPCB BOM/CPL, Gerber+drill zips and a whole-kit BOM.  Runs on the boards already
in hardware/kicad (no re-routing).

    python3 release.py
"""

import collections
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from vibeduino import bom, fab, modules, route, sch  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
KICAD = os.path.join(ROOT, "kicad")
OUT = os.path.join(ROOT, "fab")
SCHEMATICS = os.path.join(ROOT, "schematics")
PREVIEWS = os.path.join(ROOT, "previews")
LIB = os.path.join(KICAD, "lib")

# A classroom kit: one shield plus one of every module.
KIT = {"shield": 1, **{f.__name__: 1 for f in modules.ALL}}


def boards():
    yield "shield", os.path.join(KICAD, "shield", "vibeduino-shield.kicad_pcb")
    for f in modules.ALL:
        yield f.__name__, os.path.join(KICAD, "modules", f.__name__, f"vibeduino-{f.__name__}.kicad_pcb")


def describe(key, path):
    if key == "shield":
        return ("VIBEDUINO Shield (Arduino Uno R3)",
                "Four hex module slots (J1 power/I2C, J2 AN/PWM/IO1/IO2), BSS138 5V-3V3 I2C level "
                "shifter, Qwiic port, reset button, power LED.")
    m = json.load(open(os.path.join(os.path.dirname(path), "module.json")))
    return f"VIBEDUINO {m['name']} module - {m['title']}", m["description"]


def schematic(key, path, name, pdf_dir):
    """Generate the board's schematic next to its PCB, link the footprints to it, prove the two
    netlists match, and export a PDF (into pdf_dir) and a PNG preview."""
    sch_path = path[:-len(".kicad_pcb")] + ".kicad_sch"
    title, desc = describe(key, path)
    n, paper, uuids = sch.build(path, sch_path, name, title, desc)
    sch.link_footprints(path, os.path.basename(sch_path), uuids)
    sch.write_lib_tables(os.path.dirname(path), LIB)
    diffs = sch.compare(path, sch_path)
    assert not diffs, (name, diffs)
    pdf = os.path.join(pdf_dir, f"{name}.pdf")
    subprocess.run(["kicad-cli", "sch", "export", "pdf", "-o", pdf, sch_path], check=True,
                   capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["kicad-cli", "sch", "export", "svg", "-o", td, sch_path], check=True,
                       capture_output=True)
        import cairosvg
        cairosvg.svg2png(url=os.path.join(td, f"{name}.svg"), output_width=2400,
                         background_color="white",
                         write_to=os.path.join(PREVIEWS, f"{name}-schematic.png"))
    return pdf, dict(symbols=n, paper=paper, file=os.path.relpath(sch_path, ROOT))


def merge_pdfs(paths, out_dir):
    """One schematic PDF for the whole kit (per-board PDFs if pypdf is missing)."""
    os.makedirs(out_dir, exist_ok=True)
    try:
        from pypdf import PdfWriter
    except ImportError:
        print("pypdf not installed - writing one PDF per board")
        for p in paths:
            shutil.copy(p, out_dir)
        return
    w = PdfWriter()
    for p in paths:
        w.append(p)
    with open(os.path.join(out_dir, "vibeduino-schematics.pdf"), "wb") as f:
        w.write(f)


def main():
    kit = collections.OrderedDict()
    summary = []
    libs = sch.write_libraries(LIB, [p for _, p in boards()])
    print("kicad/lib:", ", ".join(libs), flush=True)
    pdf_dir = tempfile.mkdtemp()
    pdfs = []
    for key, path in boards():
        name = f"vibeduino-{key}"
        out = os.path.join(OUT, name)
        bom.annotate(path)
        pdf, sheet = schematic(key, path, name, pdf_dir)
        pdfs.append(pdf)
        lines = bom.write_board_bom(path, out, name)
        n_cpl = bom.write_cpl(path, out, name)
        zpath, files = fab.gerbers(path, out, name)
        e, w, u, _ = route.drc(path)          # annotate() must not have changed anything
        assert e == 0 and u == 0, (name, e, u)
        smt_sides = sorted({g["side"] for g in lines if g["part"].process == "SMT"})
        summary.append(dict(board=name, parts=sum(len(g["refs"]) for g in lines),
                            lines=len(lines), placements=n_cpl, smt_sides=smt_sides,
                            tht=sum(len(g["refs"]) for g in lines if g["part"].process == "THT"),
                            gerber_files=len(files), schematic=sheet))
        for g in lines:
            p = g["part"]
            k = kit.setdefault(p.key, dict(part=p, qty=0, boards=collections.Counter()))
            k["qty"] += len(g["refs"]) * KIT[key]
            k["boards"][key] += len(g["refs"])
        print(f"{name:22s} {summary[-1]['parts']:3d} parts / {len(lines):2d} lines, "
              f"{n_cpl:2d} SMT placements on {','.join(smt_sides) or '-'}, schematic "
              f"{sheet['symbols']} symbols (netlist == PCB), gerbers -> "
              f"{os.path.relpath(zpath, ROOT)}", flush=True)

    merge_pdfs(pdfs, SCHEMATICS)
    shutil.rmtree(pdf_dir)

    with open(os.path.join(OUT, "vibeduino-kit-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty per kit", "Description", "Manufacturer", "MPN", "Package", "Process",
                    "Used on", "Notes"])
        for k in sorted(kit.values(), key=lambda k: (k["part"].process, k["part"].key)):
            p = k["part"]
            used = ", ".join(f"{b}×{n}" if n > 1 else b for b, n in k["boards"].items())
            w.writerow([k["qty"], p.desc, p.mfr, p.mpn, p.package, p.process, used, p.note])
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(dict(kit=KIT, boards=summary), f, indent=2)
    write_markdown(kit, summary)
    return 0


def write_markdown(kit, summary):
    """hardware/BOM.md - generated, do not edit by hand."""
    proc_name = {"SMT": "SMT (machine)", "THT": "Through-hole", "HAND": "Hand assembly"}
    tot = collections.Counter()
    for k in kit.values():
        tot[k["part"].process] += k["qty"]
    L = ["# VIBEDUINO — Bill of Materials (rev A)", "",
         "_Generated by `generator/release.py` from the placed footprints — do not edit by hand._", "",
         "One **classroom kit** = 1 shield + 1 of each of the 10 modules (Arduino Uno R3 not included).",
         "", f"* **{tot['SMT']}** SMT placements, **{tot['THT']}** through-hole parts, "
         f"**{tot['HAND']}** hand-assembled part (OLED panel) per kit",
         f"* {len(kit)} unique line items", "",
         "Per-board files live in `fab/<board>/`. For production, order the modules as the "
         "ten-module panel in [`panel/`](panel/README.md).", "",
         "| File | Use |", "|---|---|",
         "| `<board>-gerbers.zip` | Gerbers (Cu, mask, silk, paste, outline) + Excellon drill (PTH/NPTH) — upload to the PCB fab |",
         "| `<board>-bom.csv` | Full BOM with MPNs, side and assembly process |",
         "| `<board>-bom-jlcpcb.csv` | JLCPCB assembly BOM with LCSC part numbers (SMT and through-hole) |",
         "| `<board>-cpl-jlcpcb.csv` | JLCPCB pick-and-place (SMT and through-hole), JLCPCB rotation offsets applied |",
         "| `vibeduino-kit-bom.csv` | Whole-kit totals |", "",
         "Schematics (generated from, and netlist-checked against, each PCB) sit next to each board "
         "in `kicad/`; all of them are in one PDF, `schematics/vibeduino-schematics.pdf`.", "",
         "## Kit BOM", "",
         "| Qty / kit | Part | Manufacturer | MPN | LCSC | Package | Process | Used on |",
         "|---:|---|---|---|---|---|---|---|"]
    for k in sorted(kit.values(), key=lambda k: (k["part"].process, k["part"].key)):
        p = k["part"]
        used = ", ".join(f"{b}×{n}" if n > 1 else b for b, n in k["boards"].items())
        L.append(f"| {k['qty']} | {p.desc} | {p.mfr} | {p.mpn} | {p.lcsc or '—'} | {p.package} | "
                 f"{proc_name.get(p.process, p.process)} | {used} |")
    L += ["", "## Per board", "",
          "| Board | Parts | SMT placements | SMT side | Through-hole |", "|---|---:|---:|---|---:|"]
    for b in summary:
        L.append(f"| `{b['board']}` | {b['parts']} | {b['placements']} | "
                 f"{', '.join(b['smt_sides']) or '—'} | {b['tht']} |")
    L += ["", "## Ordering & assembly notes", "",
          "* **PCB**: 2 layers, FR4 1.6 mm, 1 oz copper, min track/space 0.15 mm, min drill 0.3 mm, "
          "**tented vias**. Any mask colour (renders use black + white silk, ENIG).",
          "* The ten modules are small (25.4 × 29.3 mm). Order them as the ready-made **ten-module "
          "panel** in `panel/` instead of ten separate designs.",
          "* **SMT**: every board is single-sided SMT. The shield and modules use the top side; the "
          "**OLED module's SMT parts are on the bottom** (its top is the display), so the module "
          "panel needs two-sided assembly.",
          "* **LCSC numbers** were checked against the LCSC/JLCPCB listings in October 2026. Stock "
          "changes daily, so re-check at order time. Resistors and capacitors are generic; any 1 % "
          "0603 / X5R-X7R equivalent is fine. Lines without an LCSC number (5 mm red and green LEDs, "
          "passive buzzer) are commodity parts with no verified listing: choose one to the "
          "description, or hand-fit them.",
          "* **Placement rotations** in the CPL files include JLCPCB's usual offsets (SOT-23, "
          "electrolytic, WS2812B +180°). JLCPCB's library still differs for some parts, so check the "
          "placement preview before confirming.",
          "* **Through-hole**: module bus headers and the shield's Arduino headers go on the **underside**. "
          "Trim the shield socket leads to ≤ 1.5 mm, because the shield rests on the Uno's USB jack.",
          "* **OLED**: the 28-pin FPC is soldered to the pads under the glass (hand or hot-bar). Then "
          "the glass folds over and is fixed with thin double-sided tape.",
          "* **Optional kit accessories** (not in the BOM): pot knob, tactile switch caps, 2 × micro "
          "servo (SG90 class), Qwiic cable.", ""]
    with open(os.path.join(ROOT, "BOM.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())

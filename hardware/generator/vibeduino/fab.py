"""Fabrication outputs: Gerbers + Excellon drill, zipped per board (JLCPCB-ready)."""

import glob
import os
import shutil
import subprocess
import zipfile

LAYERS = ["F.Cu", "B.Cu", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask",
          "Edge.Cuts"]


def gerbers(pcb_path, out_dir, name):
    """Write <name>-gerbers.zip (all copper/mask/silk/paste/outline layers + drill files)."""
    work = os.path.join(out_dir, "gerbers")
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", ",".join(LAYERS),
                    "--subtract-soldermask", "-o", work + "/", pcb_path],
                   check=True, capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon",
                    "--excellon-separate-th", "--excellon-units", "mm", "--generate-map",
                    "--map-format", "gerberx2", "-o", work + "/", pcb_path],
                   check=True, capture_output=True)
    files = sorted(glob.glob(os.path.join(work, "*")))
    zpath = os.path.join(out_dir, f"{name}-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.basename(f))
    shutil.rmtree(work)
    return zpath, [os.path.basename(f) for f in files]

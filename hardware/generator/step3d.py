#!/usr/bin/env python3
"""3D outputs: a STEP model of every board, plus rendered 3D previews.

    python3 step3d.py [shield pot ...]

* kicad/lib/VIBEDUINO.3dshapes: STEP models for the parts KiCad's library lacks
  (RK09K pot, TS-1187A switch, JST SH Qwiic socket, 0.66" OLED glass).
* 3d/vibeduino-<board>.step: board + all parts, for enclosure / mechanical CAD.
  Modules have their origin at the hex centre; the shield at the Arduino Uno's
  lower-left corner, so it lines up with Arduino's own Uno CAD model.
* previews/3d/: top and bottom 3D renders of every board and a module contact sheet.
* 3d/vibeduino-assembly.step and previews/3d/vibeduino-assembly-3d*.png: the full stack,
  a simplified Arduino Uno (3d/arduino-uno-r3-standin.step) + shield + four modules.

Needs KiCad's 3D library (kicad-packages3d; KICAD7_3DMODEL_DIR overrides
/usr/share/kicad/3dmodels), OpenCASCADE for Python (pip install cadquery-ocp trimesh
mapbox-earcut) and, for the renders, Node with three.js + playwright-core
(npm install in this directory) and a Chromium build ($CHROMIUM_PATH).
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402
from PIL import Image  # noqa: E402

from vibeduino import models3d, modules, render, spec  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
KICAD = os.path.join(ROOT, "kicad")
MODEL_DIR = os.path.join(KICAD, "lib", "VIBEDUINO.3dshapes")
OUT = os.path.join(ROOT, "3d")
PREVIEWS = os.path.join(ROOT, "previews", "3d")

# Stack heights (mm, from the Uno's underside): Uno PCB 1.6, female headers 8.5,
# male header bodies 2.54 between each board and the sockets it plugs into.
SHIELD_Z = 1.6 + 8.5 + 2.54
MODULE_Z = SHIELD_Z + 1.6 + 8.5 + 2.54
ASSEMBLIES = {
    "vibeduino-assembly": {1: "oled", 2: "dpad", 3: "pot", 4: "servo"},
    "vibeduino-assembly-2": {1: "led", 2: "rgb", 3: "temp", 4: "buzzer"},
}

VIEWS = {
    "": {"width": 1400, "height": 1100, "dir": [0.42, -0.85, 1.0]},
    "-bottom": {"width": 1400, "height": 1100, "dir": [0.42, -0.85, 1.0], "flip": True},
}


def boards():
    yield "shield", os.path.join(KICAD, "shield", "vibeduino-shield.kicad_pcb"), \
        spec.uno_to_kicad(0, 0)
    for f in modules.ALL:
        k = f.__name__
        yield k, os.path.join(KICAD, "modules", k, f"vibeduino-{k}.kicad_pcb"), spec.MODULE_ORIGIN


def textures(key, pcb, td):
    top, bottom = os.path.join(td, f"{key}-top.png"), os.path.join(td, f"{key}-bottom.png")
    render.photo(pcb, top, side="F")
    render.photo(pcb, bottom, side="B")          # mirrored (seen from below), as uv() expects
    return top, bottom, render._crop(pcbnew.LoadBoard(pcb))


def render_glb(glb, name, views, td):
    for suffix, view in views.items():
        vf = os.path.join(td, f"view{suffix}.json")
        json.dump(view, open(vf, "w"))
        png = os.path.join(PREVIEWS, f"{name}-3d{suffix}.png")
        subprocess.run(["node", os.path.join(HERE, "vibeduino", "render3d.mjs"), glb, png, vf],
                       check=True)


def render_board(key, pcb, origin, step, td):
    top, bottom, crop = textures(key, pcb, td)
    glb = os.path.join(td, f"{key}.glb")
    models3d.write_glb(step, pcb, origin, top, bottom, crop, glb)
    views = dict(VIEWS)
    if key == "shield":                          # flatter angle: all eight sockets visible
        views = {k: dict(v, dir=[0.22, -0.6, 1.0]) for k, v in views.items()}
    render_glb(glb, f"vibeduino-{key}", views, td)


def assemblies(td):
    """Uno stand-in + shield + four modules: one STEP (first assembly) and renders."""
    uno = os.path.join(OUT, "arduino-uno-r3-standin.step")
    models3d.write_step(models3d.uno_standin(), uno, "Arduino_Uno_R3_standin")
    models3d._strip_step_timestamp(uno)
    shield = {k: (p, o) for k, p, o in boards()}
    uno_items = models3d.step_items(uno)
    sp, so = shield["shield"]
    shield_items = models3d.board_items(os.path.join(OUT, "vibeduino-shield.step"), sp, so,
                                        *textures("shield", sp, td))
    for i, (name, slots) in enumerate(ASSEMBLIES.items()):
        groups = [(uno_items, (0, 0, 0)), (shield_items, (0, 0, SHIELD_Z))]
        entries = [(uno, (0, 0, 0)), (os.path.join(OUT, "vibeduino-shield.step"), (0, 0, SHIELD_Z))]
        for slot, key in slots.items():
            mp, mo = shield[key]
            x, y = spec.SLOTS[slot]
            step = os.path.join(OUT, f"vibeduino-{key}.step")
            groups.append((models3d.board_items(step, mp, mo, *textures(key, mp, td)),
                           (x, y, MODULE_Z)))
            entries.append((step, (x, y, MODULE_Z)))
        glb = os.path.join(td, f"{name}.glb")
        models3d.write_scene_glb(groups, glb)
        render_glb(glb, name, {"": {"width": 1800, "height": 1300, "dir": [0.45, -0.95, 0.85],
                                    "fill": 0.86}}, td)
        if i == 0:
            models3d.write_assembly_step(entries, os.path.join(OUT, f"{name}.step"),
                                         "VIBEDUINO_assembly")


def contact_sheet(keys, out_png, suffix=""):
    ims = [Image.open(os.path.join(PREVIEWS, f"vibeduino-{k}-3d{suffix}.png")).convert("RGB")
           for k in keys]
    w, h = ims[0].size
    s = 0.5
    cols = 5
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (int(w * s) * cols, int(h * s) * rows), ims[0].getpixel((5, 5)))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((int(w * s), int(h * s)), Image.LANCZOS),
                    ((i % cols) * int(w * s), (i // cols) * int(h * s)))
    sheet.save(out_png)


def main(argv):
    only = set(argv)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREVIEWS, exist_ok=True)
    print("custom models:", ", ".join(models3d.write_custom_models(MODEL_DIR)))
    with tempfile.TemporaryDirectory() as td:
        for key, pcb, origin in boards():
            if only and key not in only:
                continue
            models3d.assign_models(pcb, MODEL_DIR)
            step = os.path.join(OUT, f"vibeduino-{key}.step")
            missing = models3d.export_step(pcb, step, origin)
            if missing:
                raise RuntimeError(f"{key}: missing 3D models: {missing}")
            render_board(key, pcb, origin, step, td)
            print(f"{key:7s} -> {os.path.relpath(step, ROOT)} "
                  f"({os.path.getsize(step) / 1e6:.1f} MB) + 3D previews", flush=True)
        if not only or "assembly" in only:
            assemblies(td)
    if not only:
        keys = [f.__name__ for f in modules.ALL]
        contact_sheet(keys, os.path.join(PREVIEWS, "modules-3d.png"))
        contact_sheet(keys, os.path.join(PREVIEWS, "modules-3d-bottom.png"), "-bottom")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

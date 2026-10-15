"""PNG previews: photo-style top/bottom renders and a KiCad-style layout view."""

import io
import os
import re
import subprocess
import tempfile

import cairosvg
import cv2
import numpy as np
import pcbnew
from PIL import Image

PX_PER_MM = 40

THEMES = {
    # name: (mask over bare FR4, mask over copper, exposed copper, exposed FR4, silk)
    "black": ((24, 24, 26), (44, 44, 48), (222, 182, 92), (176, 160, 118), (245, 245, 245)),
    "blue": ((18, 52, 110), (30, 78, 150), (222, 182, 92), (176, 160, 118), (245, 245, 245)),
}


def _svg_layer(pcb_path, layers, crop, bw=True, theme=None):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "l.svg")
        cmd = ["kicad-cli", "pcb", "export", "svg", "--layers", ",".join(layers),
               "--page-size-mode", "1", "--exclude-drawing-sheet", "-o", out, pcb_path]
        if bw:
            cmd.insert(4, "--black-and-white")
        subprocess.run(cmd, check=True, capture_output=True)
        svg = open(out).read()
    x0, y0, x1, y1 = crop
    w, h = x1 - x0, y1 - y0
    svg = re.sub(r'width="[^"]*mm" height="[^"]*mm" viewBox="[^"]*"',
                 f'width="{w}mm" height="{h}mm" viewBox="{x0} {y0} {w} {h}"', svg, count=1)
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=int(w * PX_PER_MM),
                           output_height=int(h * PX_PER_MM), background_color="white")
    return Image.open(io.BytesIO(png)).convert("RGB")


def _dark(img):
    a = np.array(img.convert("L"))
    return a < 128


def _crop(board, margin=1.0):
    bb = board.GetBoardEdgesBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - margin, pcbnew.ToMM(bb.GetTop()) - margin,
            pcbnew.ToMM(bb.GetRight()) + margin, pcbnew.ToMM(bb.GetBottom()) + margin)


def _holes(board, crop, shape):
    m = np.zeros(shape, np.uint8)
    x0, y0 = crop[0], crop[1]

    def dot(pos, d):
        cx = int((pcbnew.ToMM(pos.x) - x0) * PX_PER_MM)
        cy = int((pcbnew.ToMM(pos.y) - y0) * PX_PER_MM)
        cv2.circle(m, (cx, cy), max(1, int(d / 2 * PX_PER_MM)), 1, -1)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            ds = pad.GetDrillSize()
            if ds.x > 0:
                dot(pad.GetPosition(), pcbnew.ToMM(min(ds.x, ds.y)))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            dot(t.GetPosition(), pcbnew.ToMM(t.GetDrillValue()))
    return m.astype(bool)


def _board_mask(edge_dark):
    lines = edge_dark.astype(np.uint8) * 255
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8))
    h, w = lines.shape
    flood = lines.copy()
    ff = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 128)
    return flood != 128


def photo(pcb_path, out_png, side="F", theme="black"):
    board = pcbnew.LoadBoard(pcb_path)
    crop = _crop(board)
    s = side
    edge = _dark(_svg_layer(pcb_path, ["Edge.Cuts"], crop))
    cu = _dark(_svg_layer(pcb_path, [f"{s}.Cu"], crop))
    opening = _dark(_svg_layer(pcb_path, [f"{s}.Mask"], crop))
    silk = _dark(_svg_layer(pcb_path, [f"{s}.SilkS"], crop))
    inside = _board_mask(edge)
    holes = _holes(board, crop, inside.shape)
    c_fr4, c_cu, c_gold, c_bare, c_silk = THEMES[theme]
    img = np.zeros(inside.shape + (4,), np.uint8)
    img[inside] = (*c_fr4, 255)
    img[inside & cu] = (*c_cu, 255)
    img[inside & opening & ~cu] = (*c_bare, 255)
    img[inside & opening & cu] = (*c_gold, 255)
    img[inside & silk & ~opening] = (*c_silk, 255)
    img[holes] = (0, 0, 0, 0)
    out = Image.fromarray(img, "RGBA")
    if side == "B":
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    out.save(out_png)
    return out


def layout(pcb_path, out_png):
    """Layout review image: B.Cu (blue) under F.Cu (red), silk (yellow), outline (white).
    Copper pours are hidden so the routing stays readable."""
    board = pcbnew.LoadBoard(pcb_path)
    for z in list(board.Zones()):
        if not z.GetIsRuleArea():
            board.Remove(z)
    tmp = tempfile.NamedTemporaryFile(suffix=".kicad_pcb", delete=False)
    tmp.close()
    pcbnew.SaveBoard(tmp.name, board)
    try:
        _layout(tmp.name, board, out_png)
    finally:
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_prl"):
            if os.path.exists(tmp.name.replace(".kicad_pcb", ext)):
                os.remove(tmp.name.replace(".kicad_pcb", ext))


def _layout(pcb_path, board, out_png):
    crop = _crop(board)
    edge = _dark(_svg_layer(pcb_path, ["Edge.Cuts"], crop))
    fcu = _dark(_svg_layer(pcb_path, ["F.Cu"], crop))
    bcu = _dark(_svg_layer(pcb_path, ["B.Cu"], crop))
    silk = _dark(_svg_layer(pcb_path, ["F.SilkS"], crop))
    holes = _holes(board, crop, edge.shape)
    img = np.zeros(edge.shape + (3,), np.float32)
    img[:] = (18, 22, 28)
    inside = _board_mask(edge)
    img[inside] = (34, 40, 48)

    def over(mask, col, a):
        img[mask] = img[mask] * (1 - a) + np.array(col, np.float32) * a
    over(bcu, (60, 110, 200), 0.85)
    over(fcu, (205, 60, 60), 0.62)
    over(silk, (240, 220, 120), 0.95)
    over(edge, (235, 235, 235), 1.0)
    img[holes] = (10, 10, 10)
    Image.fromarray(img.astype(np.uint8)).save(out_png)

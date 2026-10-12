"""Renders a board the way it will look when made: green solder mask, gold pads, white silkscreen.

Usage: python3 tools/render_pcb.py BOARD.kicad_pcb OUT_PREFIX [px_per_mm]
Writes OUT_PREFIX-top.svg and OUT_PREFIX-copper.svg (both copper layers, for checking the
routing), plus .png versions when Chromium is available (for the README).
Needs KiCad 7 (kicad-cli and the pcbnew Python module).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

MASK = '#1e5b3c'          # green solder mask over bare board
CHROMIUM = [os.environ.get('CHROMIUM', ''), '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
            shutil.which('chromium') or '', shutil.which('google-chrome') or '']


def layer_svg(pcb, layer, mirror=False):
    """One layer from kicad-cli in black, returned as (viewBox, inner SVG)."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'layer.svg')
        cmd = ['kicad-cli', 'pcb', 'export', 'svg', '--layers', layer, '--black-and-white',
               '--page-size-mode', '2', '--exclude-drawing-sheet', '--drill-shape-opt', '0', '-o', out, pcb]
        if mirror:
            cmd.insert(-3, '--mirror')
        subprocess.run(cmd, check=True, capture_output=True)
        svg = open(out).read()
    view = re.search(r'viewBox="([^"]+)"', svg).group(1)
    inner = svg[svg.index('>', svg.index('<svg')) + 1:svg.rindex('</svg>')]
    inner = re.sub(r'<title>.*?</title>|<desc>.*?</desc>', '', inner, flags=re.S)
    return view, inner


def colour(inner, col):
    return inner.replace('#000000', col)


def edge_offset(pcb, box):
    """Where the board's top-left corner lands in the exported SVG."""
    _view, inner = layer_svg(pcb, 'Edge.Cuts')
    pts = re.findall(r'[ML]\s*(-?[\d.]+)[ ,](-?[\d.]+)', ' '.join(re.findall(r'd="([^"]+)"', inner)))
    return min(float(x) for x, _y in pts), min(float(y) for _x, y in pts)


def holes(board, ox, oy, x0, y0):
    out = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSizeX() <= 0:
                continue
            p = pad.GetPosition()
            r = pcbnew.ToMM(min(pad.GetDrillSizeX(), pad.GetDrillSizeY())) / 2
            out.append(f'<circle cx="{pcbnew.ToMM(p.x) - x0 + ox:.3f}" cy="{pcbnew.ToMM(p.y) - y0 + oy:.3f}" '
                       f'r="{r:.3f}" fill="#141414"/>')
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            r = pcbnew.ToMM(t.GetDrillValue()) / 2
            out.append(f'<circle cx="{pcbnew.ToMM(p.x) - x0 + ox:.3f}" cy="{pcbnew.ToMM(p.y) - y0 + oy:.3f}" '
                       f'r="{r:.3f}" fill="#141414"/>')
    return ''.join(out)


def areas(board, ox, oy, x0, y0, col):
    """Dashed outlines for the keep-out areas (logo, heatsink), so they show on the render."""
    out = []
    for z in board.Zones():
        if not z.GetIsRuleArea():
            continue
        bb = z.GetBoundingBox()
        x, y = pcbnew.ToMM(bb.GetX()) - x0 + ox, pcbnew.ToMM(bb.GetY()) - y0 + oy
        w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        name = z.GetZoneName().replace(' (L7805 only)', '')
        out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="{col}" '
                   f'stroke-width="0.25" stroke-dasharray="1 0.8" opacity="0.9"/>'
                   f'<text x="{x + w / 2:.2f}" y="{y + h / 2 + 0.6:.2f}" font-family="sans-serif" font-size="1.7" '
                   f'fill="{col}" text-anchor="middle" opacity="0.9">{name}</text>')
    return ''.join(out)


def board_shape(board, ox, oy, x0, y0, fill):
    bb = board.GetBoardEdgesBoundingBox()
    w = pcbnew.ToMM(bb.GetWidth())
    h = pcbnew.ToMM(bb.GetHeight())
    return (f'<rect x="{pcbnew.ToMM(bb.GetX()) - x0 + ox:.3f}" y="{pcbnew.ToMM(bb.GetY()) - y0 + oy:.3f}" '
            f'width="{w:.3f}" height="{h:.3f}" rx="1" fill="{fill}"/>')


def to_png(svg_path, png_path, px_per_mm, w_mm, h_mm):
    exe = next((c for c in CHROMIUM if c and os.path.exists(c)), None)
    if not exe:
        return False
    pw, ph = int(w_mm * px_per_mm), int(h_mm * px_per_mm)
    with tempfile.TemporaryDirectory() as d:
        html = os.path.join(d, 'p.html')
        svg = open(svg_path).read()
        svg = re.sub(r'width="[^"]+mm" height="[^"]+mm"', f'width="{pw}px" height="{ph}px"', svg, count=1)
        open(html, 'w').write(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        shot = os.path.join(d, 's.png')
        subprocess.run([exe, '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        f'--window-size={pw},{ph + 200}', f'--screenshot={shot}', 'file://' + html],
                       capture_output=True)
        if not os.path.exists(shot):
            return False
        subprocess.run(['convert', shot, '-crop', f'{pw}x{ph}+0+0', '+repage', png_path], check=True)
    return True


def without_fills(pcb, path):
    """Copy of the board without the copper pour fills, so the tracks show in the copper view."""
    t = open(pcb).read()
    out, i = [], 0
    while True:
        j = t.find('(filled_polygon', i)
        if j < 0:
            out.append(t[i:])
            break
        out.append(t[i:j])
        depth, k = 0, j
        while True:
            depth += {'(': 1, ')': -1}.get(t[k], 0)
            if depth == 0:
                break
            k += 1
        i = k + 1
    open(path, 'w').write(''.join(out))


def render(pcb, prefix, px_per_mm=12):
    board = pcbnew.LoadBoard(pcb)
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0 = pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY())
    view, _ = layer_svg(pcb, 'Edge.Cuts')
    vx, vy, vw, vh = (float(v) for v in view.split())
    ox, oy = edge_offset(pcb, bb)
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw}mm" height="{vh}mm" '
            f'viewBox="{vx} {vy} {vw} {vh}">')
    shape = board_shape(board, ox, oy, x0, y0, MASK)
    drills = holes(board, ox, oy, x0, y0)

    # Top: copper seen through the mask, exposed pads, silkscreen
    parts = [head, shape,
             f'<g opacity="0.55">{colour(layer_svg(pcb, "F.Cu")[1], "#4fa56c")}</g>',
             colour(layer_svg(pcb, 'F.Mask')[1], '#d8ae4a'),
             colour(layer_svg(pcb, 'F.SilkS')[1], '#f5f5f0'),
             drills, areas(board, ox, oy, x0, y0, '#ffe08a'), '</svg>']
    top = prefix + '-top.svg'
    open(top, 'w').write(''.join(parts))

    # Both copper layers (front red, back blue, pours left out) with the silkscreen
    with tempfile.TemporaryDirectory() as d:
        bare = os.path.join(d, os.path.basename(pcb))
        without_fills(pcb, bare)
        parts = [head, board_shape(board, ox, oy, x0, y0, '#f7f7f5'),
                 f'<g opacity="0.75">{colour(layer_svg(bare, "B.Cu")[1], "#3b6fd1")}</g>',
                 f'<g opacity="0.8">{colour(layer_svg(bare, "F.Cu")[1], "#c8402e")}</g>',
                 colour(layer_svg(bare, 'F.SilkS')[1], '#6b6b6b'),
                 drills, '</svg>']
    copper = prefix + '-copper.svg'
    open(copper, 'w').write(''.join(parts))

    for svg in (top, copper):
        to_png(svg, svg[:-4] + '.png', px_per_mm, vw, vh)
    return top, copper


if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 12)

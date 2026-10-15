"""Fit check: four modules on the shield.

``verify_fit`` proves geometrically that the four hex slots and their header
bodies never collide and stay clear of the Uno's tall parts; ``render`` pastes
the module renders onto the shield render at the slot positions.
"""

import itertools
import math

import pcbnew
from PIL import Image, ImageFilter
from shapely.geometry import Polygon, box

from . import render, spec


def _hex(cx, cy, r=spec.HEX_R):
    return Polygon([(cx + x, cy + y) for x, y in spec.hex_vertices(r)])


def _header_body(cx, cy, row_y):
    """Plastic body of a 1x5 2.54 mm header/socket row (module-local -> shield-local)."""
    x0 = cx + spec.BUS_PIN_X[0] - 1.27
    x1 = cx + spec.BUS_PIN_X[-1] + 1.27
    return box(x0, cy + row_y - 1.27, x1, cy + row_y + 1.27)


def verify_fit():
    """Return a list of human-readable results; raises AssertionError on a clash."""
    out = []
    centres = {s: (x, spec.UNO_H - y) for s, (x, y) in spec.SLOTS.items()}
    hexes = {s: _hex(*c) for s, c in centres.items()}
    bodies = {s: [_header_body(*c, -spec.BUS_ROW_Y), _header_body(*c, spec.BUS_ROW_Y)]
              for s, c in centres.items()}
    for a, b in itertools.combinations(hexes, 2):
        d = hexes[a].distance(hexes[b])
        assert d > 0.5 and not hexes[a].intersects(hexes[b]), (a, b, d)
        db = min(x.distance(y) for x in bodies[a] for y in bodies[b])
        assert db > 0.3, ("header bodies", a, b, db)
        out.append(f"slots {a}-{b}: board gap {d:.2f} mm, header-body gap {db:.2f} mm")
    outline = Polygon([(x, spec.UNO_H - y) for x, y in spec.UNO_OUTLINE])
    for s, h in hexes.items():
        assert outline.buffer(0.01).contains(h), ("slot outside shield", s)
    out.append("all four modules lie inside the Uno R3 outline")
    for label, (x0, y0, x1, y1) in spec.UNO_KEEPOUTS.items():
        k = box(x0, spec.UNO_H - y1, x1, spec.UNO_H - y0)
        for s, c in centres.items():
            for b in bodies[s]:
                assert not b.intersects(k), ("socket over", label, s)
    out.append("no socket lead lands above the USB jack, DC jack or ICSP header")
    return out


def render_assembly(shield_pcb, shield_png, module_pngs, out_png):
    """module_pngs: {slot: path to module top render}."""
    board = pcbnew.LoadBoard(shield_pcb)
    x0, y0, _, _ = render._crop(board)
    base = Image.open(shield_png).convert("RGBA")
    pad = 60
    canvas = Image.new("RGBA", (base.width + 2 * pad, base.height + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(base, (pad, pad))
    k = render.PX_PER_MM
    for s, path in module_pngs.items():
        cx, cy = spec.SLOTS[s]
        lx, ly = cx, spec.UNO_H - cy
        px = (spec.SHIELD_ORIGIN[0] + lx - x0) * k + pad
        py = (spec.SHIELD_ORIGIN[1] + ly - y0) * k + pad
        im = Image.open(path).convert("RGBA")
        # drop shadow: modules stand ~11 mm above the shield
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        alpha = im.split()[3].point(lambda a: 110 if a > 0 else 0)
        sh.putalpha(alpha)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        canvas.alpha_composite(sh, (int(px - im.width / 2 + 24), int(py - im.height / 2 + 30)))
        canvas.alpha_composite(im, (int(px - im.width / 2), int(py - im.height / 2)))
    canvas.save(out_png)
    return out_png


def contact_sheet(pngs, out_png, cols=5, bg=(245, 243, 238, 255), gap=30):
    ims = [Image.open(p).convert("RGBA") for p in pngs]
    w = max(i.width for i in ims)
    h = max(i.height for i in ims)
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGBA", (cols * (w + gap) + gap, rows * (h + gap) + gap), bg)
    for n, im in enumerate(ims):
        r, c = divmod(n, cols)
        sheet.alpha_composite(im, (gap + c * (w + gap) + (w - im.width) // 2,
                                   gap + r * (h + gap) + (h - im.height) // 2))
    sheet.save(out_png)
    return out_png

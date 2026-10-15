"""Bitmap artwork (logo, wordmarks) -> silkscreen polygons.

The Allentronics logo PNG and text rendered with a TrueType/OpenType font are
thresholded, traced with OpenCV and emitted as filled polygons (with holes)
in millimetres, centred on (0, 0).  ``min_line`` thickens hairlines so every
stroke stays above the fab's minimum silkscreen width.
"""

import functools
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "..", "assets"))
LOGO_PNG = os.path.join(ASSETS, "allentronics-logo.png")
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu"]

# Regions of the logo PNG (x0, y0, x1, y1) in source pixels.
LOGO_PARTS = {
    "full": None,
    "icon": (0, 0, 180, 181),            # circuit "A" mark with mortarboard
    "wordmark": (180, 40, 1235, 135),    # ALLENTRONICS
    "tagline": (180, 140, 1235, 181),    # EDUCATION SERVICES
    "text": (180, 40, 1235, 181),        # ALLENTRONICS + EDUCATION SERVICES
}


@functools.lru_cache(maxsize=None)
def _logo_mask():
    a = np.array(Image.open(LOGO_PNG).convert("RGBA")).astype(int)
    return ((a[..., 3] > 128) & (a[..., :3].sum(-1) < 700)).astype(np.uint8)


def logo_mask(part="full"):
    m = _logo_mask()
    box = LOGO_PARTS[part]
    if box:
        x0, y0, x1, y1 = box
        m = m[y0:y1, x0:x1]
    return _crop(m)


def _find_font(name):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def text_mask(text, font="Inter-Black.otf", px=400, tracking=0.04):
    f = ImageFont.truetype(_find_font(font), px)
    widths = [f.getlength(c) for c in text]
    total = int(sum(widths) + tracking * px * (len(text) - 1) + px)
    im = Image.new("L", (total, int(px * 1.5)), 0)
    d = ImageDraw.Draw(im)
    x = px * 0.5
    for c, w in zip(text, widths):
        d.text((x, px * 0.1), c, font=f, fill=255)
        x += w + tracking * px
    return _crop((np.array(im) > 127).astype(np.uint8))


def _crop(m):
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def mask_polys(mask, width=None, height=None, min_line=0.0, upsample=4, eps=0.35):
    """Trace a binary mask into [(outer, [holes])] polygons in mm centred at 0,0."""
    h, w = mask.shape
    scale = (width / w) if width else (height / h)            # mm per source px
    big = cv2.resize(mask * 255, (w * upsample, h * upsample), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), upsample * 0.6)
    big = (big > 127).astype(np.uint8)
    mm_per = scale / upsample
    if min_line > 0:
        # Grow strokes thinner than min_line (opening-based detection is overkill
        # for logos; a uniform half-deficit dilation keeps proportions).
        dt = cv2.distanceTransform(big, cv2.DIST_L2, 5)
        ridge = dt[(dt == cv2.dilate(dt, np.ones((3, 3)))) & (dt > 0)]
        thin = np.percentile(ridge, 10) * 2 * mm_per if ridge.size else min_line
        if thin < min_line:
            r = int(round((min_line - thin) / 2 / mm_per))
            if r > 0:
                k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
                big = cv2.dilate(big, k)
    pad = 2
    big = np.pad(big, pad)
    contours, hier = cv2.findContours(big, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    hier = hier[0]
    H, W = big.shape
    cx, cy = W / 2, H / 2

    def to_mm(c):
        c = cv2.approxPolyDP(c, eps * upsample, True)[:, 0, :]
        return [(float((x - cx) * mm_per), float((y - cy) * mm_per)) for x, y in c]

    out = []
    for i, c in enumerate(contours):
        if hier[i][3] != -1 or len(c) < 3:
            continue
        outer = to_mm(c)
        if len(outer) < 3:
            continue
        holes = []
        j = hier[i][2]
        while j != -1:
            hp = to_mm(contours[j])
            if len(hp) >= 3:
                holes.append(hp)
            j = hier[j][0]
        out.append((outer, holes))
    return out


def size_of(polys):
    xs = [x for o, _ in polys for x, _ in o]
    ys = [y for o, _ in polys for _, y in o]
    return max(xs) - min(xs), max(ys) - min(ys)


def transform(polys, dx=0, dy=0, mirror=False, rot=0):
    """Mirror about the y axis (for bottom silk), rotate (deg, CCW on screen), translate."""
    import math
    c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))

    def tf(p):
        x, y = p
        if mirror:
            x = -x
        x, y = x * c - y * s, x * s + y * c
        return x + dx, y + dy
    return [([tf(p) for p in o], [[tf(p) for p in h] for h in hs]) for o, hs in polys]


def place(pcb, polys, x, y, layer="F.SilkS", rot=0):
    mirror = layer.startswith("B.")
    pcb.polyset(layer, transform(polys, x, y, mirror=mirror, rot=rot))


def logo(part="full", width=None, height=None, min_line=0.16):
    return mask_polys(logo_mask(part), width=width, height=height, min_line=min_line)


def wordmark(text="VIBEDUINO", width=None, height=None, font="Inter-Black.otf",
             tracking=0.06, min_line=0.16):
    return mask_polys(text_mask(text, font, tracking=tracking), width=width, height=height,
                      min_line=min_line)

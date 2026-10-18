"""Make PiPath's logo images from the school's logo (data/brand/logo_original.png).

    python3 tools/make_logo_assets.py

Needs Pillow (on Raspberry Pi OS Desktop already). Writes, in data/brand/:
    logo_corner_44.png / logo_corner_66.png   wide version for the corner of every screen
    logo_full_200.png  / logo_full_300.png    the whole logo, for the welcome screen
    icon_128.png                               the squares on a white tile: the menu / desktop icon
The white background becomes transparent, so the logo sits on any colour.
To use another school's logo, replace logo_original.png (same layout) and run this again.
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent.parent / "data" / "brand"
CELL, X0, Y0 = 43, 20, 104            # the pixel squares: 43 px cells from (20, 104)


def transparent(im: Image.Image) -> Image.Image:
    """White -> transparent, keeping anti-aliased edges (alpha from how far a pixel is from white)."""
    im = im.convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            a = 255 - min(r, g, b)                    # white = 0, any colour or grey = opaque
            if a <= 6:
                px[x, y] = (0, 0, 0, 0)
                continue
            k = 255 / a                               # un-blend from white
            px[x, y] = (max(0, min(255, round(255 - (255 - r) * k))),
                        max(0, min(255, round(255 - (255 - g) * k))),
                        max(0, min(255, round(255 - (255 - b) * k))), a)
    return im


def main():
    src = Image.open(HERE / "logo_original.png").convert("RGB")
    mark = src.crop((X0, Y0, X0 + 8 * CELL, Y0 + 4 * CELL))           # 8 x 4 cells of squares
    mark = mark.crop((0, 0, 8 * CELL, 4 * CELL))
    line1 = src.crop((150, 236, 504, 270))       # BANYULE NILLUMBIK
    tech = src.crop((150, 286, 312, 334))        # TECH
    school = src.crop((150, 346, 506, 402))      # SCHOOL
    # the bottom-right of the mark's grid holds the start of the text: blank it
    blank = Image.new("RGB", (6 * CELL, 2 * CELL), "white")
    mark.paste(blank, (2 * CELL, 2 * CELL))
    gap = 22
    words_w = tech.width + gap + school.width
    text = Image.new("RGB", (max(line1.width, words_w), line1.height + 14 + school.height), "white")
    text.paste(line1, (0, 0))
    text.paste(tech, (0, line1.height + 14 + (school.height - tech.height) // 2))
    text.paste(school, (tech.width + gap, line1.height + 14))
    h = max(mark.height, text.height)
    lock = Image.new("RGB", (mark.width + 30 + text.width, h), "white")
    lock.paste(mark, (0, (h - mark.height) // 2))
    lock.paste(text, (mark.width + 30, (h - text.height) // 2))
    lock = transparent(lock)
    for height in (44, 66):
        w = round(lock.width * height / lock.height)
        lock.resize((w, height), Image.LANCZOS).save(HERE / f"logo_corner_{height}.png")
    full = transparent(src.crop((14, 98, 512, 408)))
    for width in (200, 300):
        full.resize((width, round(full.height * width / full.width)), Image.LANCZOS).save(
            HERE / f"logo_full_{width}.png")
    # the app icon: the squares on a white tile with a thin grey edge (Windows 95 style)
    icon = Image.new("RGB", (128, 128), "white")
    squares = mark.resize((112, 56), Image.LANCZOS)
    icon.paste(squares, (8, 36))
    edge = Image.new("RGB", (128, 128), "#808080")
    edge.paste(icon.crop((2, 2, 126, 126)), (2, 2))
    edge.save(HERE / "icon_128.png")
    print("written to", HERE)


if __name__ == "__main__":
    main()

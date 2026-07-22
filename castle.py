"""
Medieval castle
  Base plate:    80×80×3mm
  Curtain wall:  60×60mm footprint, 20mm high, 3mm thick, crenellations on top
  Keep:          40×40×50mm, centred, crenellations on top
  Corner towers: 4× cylinder dia=15mm, H=60mm at keep corners, crenellated
  Gatehouse:     arched opening centred on front curtain wall face
"""

from build123d import *
from math import pi, cos, sin, radians


def gen_step():
    MERLON_W   = 4.0    # merlon width
    MERLON_H   = 4.0    # merlon height
    MERLON_D   = 3.0    # merlon depth (= wall thickness for keep/curtain)

    # ── Base plate ────────────────────────────────────────────────────────────
    with BuildPart() as bp:
        Box(80, 80, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))

    base = bp.part

    # ── Curtain wall (hollow square, 60×60 OD, 3mm thick, 20mm high) ─────────
    with BuildPart() as cw:
        Box(60, 60, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
        Box(54, 54, 20, align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT)

    curtain = cw.part.moved(Location((0, 0, 3)))

    # Crenellations on curtain wall top — 4 sides
    curtain_merlons = []
    wall_len   = 60.0
    wall_t     = 3.0
    wall_top_z = 3 + 20

    for side in range(4):
        ang = side * 90
        # place merlons along the side (local x = along wall, local y = outward)
        n_merlon = 5
        spacing  = wall_len / (2 * n_merlon)
        for i in range(n_merlon):
            lx = -wall_len/2 + spacing + i * 2 * spacing
            with BuildPart() as mb:
                Box(MERLON_W, wall_t, MERLON_H,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
            m = mb.part.moved(Location((lx, wall_len/2 - wall_t/2, wall_top_z)))
            m = m.moved(Location((0, 0, 0),
                                  (0, 0, ang)))
            curtain_merlons.append(m)

    # ── Gatehouse arch on front face of curtain wall ──────────────────────────
    # Front face is at Y = -30 (south face), arch centred at X=0
    ARCH_W  = 8.0
    ARCH_H  = 12.0
    ARCH_R  = ARCH_W / 2

    with BuildPart() as ga:
        # rectangular lower part
        Box(ARCH_W, wall_t + 0.2, ARCH_H - ARCH_R,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    gate_rect = ga.part.moved(Location((0, -30 - 0.1, 3)))

    # arch cylinder half
    with BuildPart() as ac:
        Cylinder(radius=ARCH_R, height=wall_t + 0.2,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
        # keep only top half (Y>=0 in local frame → Z>=0 after rotate)
        Box(ARCH_R*2 + 0.2, wall_t + 0.2, ARCH_R,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT)
    arch_cut = ac.part.rotate(Axis.X, 90).moved(
        Location((0, -30 - 0.1, 3 + ARCH_H - ARCH_R)))

    gate_void = gate_rect + arch_cut
    curtain = curtain - gate_void

    # ── Keep (40×40×50mm, centred) ────────────────────────────────────────────
    with BuildPart() as kp:
        Box(40, 40, 50, align=(Align.CENTER, Align.CENTER, Align.MIN))
    keep = kp.part.moved(Location((0, 0, 3)))

    keep_top_z = 3 + 50
    keep_side  = 40.0

    keep_merlons = []
    for side in range(4):
        ang    = side * 90
        n_m    = 4
        spc    = keep_side / (2 * n_m)
        for i in range(n_m):
            lx = -keep_side/2 + spc + i * 2 * spc
            with BuildPart() as mb:
                Box(MERLON_W, MERLON_D, MERLON_H,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
            m = mb.part.moved(Location(
                (lx, keep_side/2 - MERLON_D/2, keep_top_z)))
            m = m.moved(Location((0, 0, 0), (0, 0, ang)))
            keep_merlons.append(m)

    # ── Corner towers (dia=15, H=60) at keep corners ─────────────────────────
    TOWER_R = 7.5
    TOWER_H = 60.0
    corners = [(-20, -20), (20, -20), (20, 20), (-20, 20)]

    towers = []
    for (cx, cy) in corners:
        with BuildPart() as tw:
            Cylinder(radius=TOWER_R, height=TOWER_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        t = tw.part.moved(Location((cx, cy, 3)))
        towers.append(t)

    # Crenellations on each tower top
    tower_merlons = []
    N_TM = 6
    tower_top_z = 3 + TOWER_H
    for (cx, cy) in corners:
        for i in range(N_TM):
            ang = i * (360 / N_TM)
            r   = TOWER_R - MERLON_D/2
            mx  = cx + r * cos(radians(ang))
            my  = cy + r * sin(radians(ang))
            with BuildPart() as mb:
                Box(MERLON_W, MERLON_D, MERLON_H,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
            m = mb.part.moved(Location((mx, my, tower_top_z),
                                        (0, 0, ang)))
            tower_merlons.append(m)

    # ── Assemble ──────────────────────────────────────────────────────────────
    result = base + curtain + keep
    for t in towers:
        result = result + t
    for m in curtain_merlons + keep_merlons + tower_merlons:
        result = result + m

    result.label = "castle"
    return result

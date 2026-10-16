"""01 SIMPLE - Spur gear reduction stage (car gearbox theme).

18T pinion drives a 36T gear (2:1 reduction), module 2, centre distance 54 mm.
Global frame: Z up, shafts run along Y. Front of the model faces -Y.
"""
import sys
from cadlib import *

M = 2.0
Z_PINION, Z_GEAR = 18, 36
CD = M * (Z_PINION + Z_GEAR) / 2          # 54 mm centre distance
XP, XG = -CD / 2, CD / 2                   # shaft x positions
ZC = 50.0                                  # shaft height
Y_BRACKET = 24.0                           # bracket mid-planes at y = +/-24
TO_Y = [("x", -90)]                        # local +Z -> global +Y
TO_NEG_Y = [("x", 90)]                     # local +Z -> global -Y


def base_plate():
    s = box(-75, 75, -40, 40, 0, 8)
    s = cq.Workplane().add(s).edges("|Z").fillet(6).val()
    holes = [cyl(4.5, 10, (x, y, -1)) for x in (-65, 65) for y in (-30, 30)]
    for x in (-45, 45):
        for y in (-Y_BRACKET, Y_BRACKET):
            holes.append(cyl(5.0, 6, (x, y, 0)))          # counterbore from below
            holes.append(cyl(2.75, 10, (x, y, -1)))       # clearance hole
    return cut_all(s, holes)


def bearing_bracket():
    """Profile in XZ, 8 thick in Y (local y = -4..4), bottom at z = 0."""
    zc = ZC - 8
    parts = [box(-55, 55, -4, 4, 0, 20), box(-27, 27, -4, 4, zc - 8, zc + 8)]
    for x in (XP, XG):
        parts.append(box(x - 11, x + 11, -4, 4, 0, zc))
        parts.append(cyl(19, 8, (x, -4, zc), (0, 1, 0)))
    s = fuse_all(parts)
    try:
        s = cq.Workplane().add(s).edges("|Y").fillet(3).val()
    except Exception:
        pass
    cuts = [cyl(13, 10, (x, -5, zc), (0, 1, 0)) for x in (XP, XG)]
    cuts += [cyl(2.5, 16, (x, 0, -0.01)) for x in (-45, 45)]   # tapped holes (M5)
    return cut_all(s, cuts)


def ball_bearing():
    """6000 deep-groove bearing 10 x 26 x 8, axis Z, z = -4..4."""
    s = tube(13, 5, 8, (0, 0, -4))
    grooves = [tube(10.5, 7.5, 0.8, (0, 0, 4 - 0.8)), tube(10.5, 7.5, 0.8, (0, 0, -4))]
    s = cut_all(s, grooves)
    ch = [tube(14, 12.6, 0.4, (0, 0, z)) for z in (-4, 3.6)]
    return cut_all(s, ch)


def shaft(length, flat_len=25):
    """Dia 10 shaft, axis Z from 0..length, D-flat on the drive end (top)."""
    s = cyl(5, length)
    s = cq.Workplane().add(s).faces(">Z or <Z").chamfer(0.6).val()
    s = s.cut(box(-6, 6, 4, 6, length - flat_len, length + 1))
    return s


def pinion():
    g, _ = spur_gear(M, Z_PINION, 14, 0)
    g = g.translate(V(0, 0, -7))
    hub = cyl(11, 7, (0, 0, 7))
    s = g.fuse(hub).clean()
    s = s.cut(cyl(5, 30, (0, 0, -10)))
    s = s.cut(cyl(2, 12, (0, 0, 10.5), (0, 1, 0)))      # set-screw hole in hub
    return s


def driven_gear():
    g, info = spur_gear(M, Z_GEAR, 12, 0)
    g = g.translate(V(0, 0, -6))
    hub = cyl(13, 8, (0, 0, -14))
    s = g.fuse(hub).clean()
    holes = [cyl(6, 20, (22 * cos(radians(30 + 60 * k)), 22 * sin(radians(30 + 60 * k)), -10)) for k in range(6)]
    holes.append(cyl(5, 40, (0, 0, -20)))
    holes.append(cyl(2, 14, (0, 0, -10), (0, 1, 0)))
    return cut_all(s, holes)


def shaft_collar():
    s = tube(10, 5, 8, (0, 0, -4))
    s = cq.Workplane().add(s).edges().chamfer(0.5).val()
    return s.cut(cyl(2, 12, (0, 0, 0), (1, 0, 0)))


def build():
    P = {
        "base": Part("Base Plate", base_plate(), "gunmetal"),
        "bracket": Part("Bearing Bracket", bearing_bracket(), "aluminium"),
        "bearing": Part("Ball Bearing 6000", ball_bearing(), "steel"),
        "in_shaft": Part("Input Shaft", shaft(98), "dark_steel"),
        "out_shaft": Part("Output Shaft", shaft(98), "dark_steel"),
        "pinion": Part("Pinion Gear 18T", pinion(), "brass"),
        "gear": Part("Driven Gear 36T", driven_gear(), "blue"),
        "collar": Part("Shaft Collar", shaft_collar(), "black_oxide"),
        "screw": Part("Cap Screw M5x16", socket_cap_screw(5, 16), "black_oxide"),
    }
    root = Asm("Spur Gear Reduction Stage")
    root.add(P["base"])
    for y in (-Y_BRACKET, Y_BRACKET):
        root.add(P["bracket"], place((0, y, 8)))
    for x in (XP, XG):
        for y in (-Y_BRACKET, Y_BRACKET):
            root.add(P["bearing"], place((x, y, ZC), TO_Y))
    # input shaft: drive end sticks out of the FRONT (-Y)
    root.add(P["in_shaft"], place((XP, 38, ZC), TO_NEG_Y))
    # output shaft: drive end sticks out of the BACK (+Y)
    root.add(P["out_shaft"], place((XG, -38, ZC), TO_Y))
    root.add(P["pinion"], place((XP, 0, ZC), TO_Y))
    root.add(P["gear"], place((XG, 0, ZC), [("z", 180 / Z_GEAR)] + TO_Y))
    root.add(P["collar"], place((XP, 32, ZC), TO_Y))
    root.add(P["collar"], place((XG, -32, ZC), TO_Y))
    for x in (-45, 45):
        for y in (-Y_BRACKET, Y_BRACKET):
            root.add(P["screw"], place((x, y, 6), [("x", 180)]))
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "01_Simple_Gear_Reduction.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Simple: 18T/36T spur gear reduction stage"))

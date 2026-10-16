"""02 MODERATE - Front wheel corner: hub, disc brake & wheel (car theme).

Everything is modelled in a 'wheel frame' (x = forward, y = up, z = outboard
along the axle, origin = hub flange face) and the whole corner is then placed
so the tyre stands on the ground plane (global Z up, wheel faces -Y / Front).

Sizes are realistic: 5 x 114.3 studs, 300 mm vented disc, fixed 4-piston
caliper, 17 x 7.5J ET45 alloy wheel, 225/45 R17 tyre.
"""
import sys
from cadlib import *

PCD_R = 114.3 / 2
STUD_ANGLES = [90 + 72 * k for k in range(5)]
WHEEL_FRAME = place((0, 0, 317), [("x", 90)])   # local z (outboard) -> global -Y


def wf(t=(0, 0, 0), rots=()):
    return place(t, rots)


def pcd(r, a_deg):
    return (r * cos(radians(a_deg)), r * sin(radians(a_deg)))


# ----------------------------------------------------------------- knuckle --
def steering_knuckle():
    z0, z1 = -100, -80                     # web plate thickness
    def prism(pts, za=z0, zb=z1):
        return cq.Workplane("XY").polyline(pts).close().extrude(zb - za).translate((0, 0, za)).val()
    parts = [tube(60, 40, 48, (0, 0, -100))]
    parts.append(prism([(-32, 40), (32, 40), (24, 152), (-24, 152)]))               # upper arm
    parts.append(box(-35, 35, 150, 178, -110, -70))                                # strut clamp
    parts.append(prism([(-28, -40), (28, -40), (20, -135), (-20, -135)]))          # lower arm
    parts.append(cyl(22, 32, (0, -160, -90), (0, 1, 0)))                           # ball-joint boss
    parts.append(prism([(-45, -15), (-45, -62), (-150, -62), (-150, -36)]))         # steering arm
    parts.append(cyl(14, 28, (-150, -63, -90), (0, 1, 0)))                         # tie-rod boss
    for sg in (1, -1):                                                             # caliper ears
        a = radians(45 * sg)
        u, n = (cos(a), sin(a)), (-sin(a), cos(a))
        pts = [(50 * u[0] + 13 * n[0], 50 * u[1] + 13 * n[1]), (125 * u[0] + 13 * n[0], 125 * u[1] + 13 * n[1]),
               (125 * u[0] - 13 * n[0], 125 * u[1] - 13 * n[1]), (50 * u[0] - 13 * n[0], 50 * u[1] - 13 * n[1])]
        parts.append(prism(pts))
        parts.append(cyl(14, 20, (125 * u[0], 125 * u[1], z0)))
    s = fuse_all(parts)
    cuts = [cyl(40, 60, (0, 0, -105))]                                             # bearing bore
    cuts.append(cyl(7, 80, (-40, 164, -90), (1, 0, 0)))                            # strut pinch bolt hole
    cuts.append(box(-3, 3, 170, 180, -112, -68))                                   # clamp slot
    cuts.append(cyl(9, 40, (0, -165, -90), (0, 1, 0)))                             # ball joint taper
    cuts.append(cyl(6, 40, (-150, -70, -90), (0, 1, 0)))                           # tie-rod taper
    for sg in (1, -1):
        a = radians(45 * sg)
        cuts.append(cyl(5.25, 30, (125 * cos(a), 125 * sin(a), -105)))
    return cut_all(s, cuts)


def wheel_bearing():
    s = tube(40, 22, 40, (0, 0, -96))
    g = [tube(33, 29, 1.0, (0, 0, -56 - 1.0)), tube(33, 29, 1.0, (0, 0, -96))]
    return cut_all(s, g)


def wheel_hub():
    parts = [cyl(70, 12, (0, 0, -12)), cyl(33, 14, (0, 0, 0)),
             cyl(26, 44, (0, 0, -56)), cyl(22, 54, (0, 0, -110))]
    s = fuse_all(parts)
    s = cq.Workplane().add(s).faces(">Z").edges().chamfer(1.5).val()
    cuts = [cyl(6, 20, (*pcd(PCD_R, a), -15)) for a in STUD_ANGLES]
    cuts += [cyl(8, 20, (*pcd(50, a + 36), -15)) for a in STUD_ANGLES]
    return cut_all(s, cuts)


def hub_nut():
    return hex_nut(60, 12, 44)


def wheel_stud():
    head = cyl(9, 6, (0, 0, -6))
    shank = cyl(6, 56, (0, 0, 0))
    s = fuse_all([head, shank])
    s = cq.Workplane().add(s).faces(">Z").edges().chamfer(1.0).val()
    return s


# -------------------------------------------------------------------- disc --
def brake_disc():
    parts = [tube(86, 33.2, 6, (0, 0, 0)),          # hat face
             tube(86, 80, 25, (0, 0, -25)),         # hat wall
             tube(150, 80, 9, (0, 0, -25)),         # outer cheek
             tube(150, 100, 9, (0, 0, -44))]        # inner cheek
    for k in range(36):
        v = box(100, 150, -2.2, 2.2, -35.01, -24.99)
        parts.append(v.rotate(V(0, 0, 0), V(0, 0, 1), k * 10))
    s = fuse_all(parts)
    cuts = [cyl(7, 20, (*pcd(PCD_R, a), -5)) for a in STUD_ANGLES]
    # cosmetic slots (1.2 deep) in both friction faces
    for k in range(6):
        for z0 in (-17.2, -44.0):
            sl = box(108, 142, -1.5, 1.5, z0, z0 + 1.2)
            cuts.append(sl.rotate(V(0, 0, 0), V(0, 0, 1), 60 * k + 12))
    return cut_all(s, cuts)


# ----------------------------------------------------------------- caliper --
PISTON_POS = [pcd(125, 12), pcd(125, -12)]
PAD_PIN_POS = (165.0, 0.0)


def caliper_body():
    s = sector(96, 178, -34, 34, -90, 22)
    lugs = [sector(108, 142, 34, 56, -80, -60), sector(108, 142, -56, -34, -80, -60)]
    s = fuse_all([s] + lugs)
    cuts = [cyl(154, 32, (0, 0, -46)),                          # disc slot
            sector(80, 200, -28, 28, -60, 0)]                    # pad pocket / window
    for (x, y) in PISTON_POS:
        cuts.append(cyl(19, 20, (x, y, -80)))                   # inboard bores
        cuts.append(cyl(19, 20, (x, y, 0)))                     # outboard bores
    cuts.append(cyl(4, 130, (*PAD_PIN_POS, -100)))
    for a in (45, -45):
        cuts.append(cyl(5, 18, (*pcd(125, a), -80.01)))         # tapped mounting holes
    (bx0, by0), (bx1, by1) = pcd(168, 20), pcd(182, 20)
    cuts.append(cyl_between(3, (bx0, by0, -75), (bx1, by1, -75)))  # bleed screw thread
    return cut_all(s, cuts)


def bleed_screw():
    hexh = hexagon_prism(8, 5, 0)
    stem = cyl(3, 8, (0, 0, -8))
    nip = cyl(2.5, 6, (0, 0, 5))
    return fuse_all([hexh, stem, nip]).cut(cyl(1, 30, (0, 0, -9)))


def caliper_piston():
    s = cyl(19, 18)
    s = s.cut(cyl(13, 12, (0, 0, -0.01)))
    s = cq.Workplane().add(s).faces(">Z").edges().chamfer(1).val()
    return s


def brake_pad():
    backing = sector(98, 152, -27, 27, 0, 6)
    friction = sector(101, 149, -25, 25, 6, 16)
    s = backing.fuse(friction).clean()
    s = s.cut(box(100, 152, -1.5, 1.5, 12, 17))                # wear slot
    return s


def pad_pin():
    shank = cyl(4, 116, (0, 0, -116))
    head = cyl(6.5, 4, (0, 0, 0))
    s = fuse_all([shank, head])
    return s.cut(cyl(1.2, 20, (-10, 0, -110), (1, 0, 0)))      # R-clip hole


def caliper_bolt():
    return flange_bolt(10, 36)


# ------------------------------------------------------------------- wheel --
TYRE_ZC = -39.0                                                 # rim / tyre centre-plane


def alloy_wheel():
    rim = [(232, 66), (238, 62), (238, 58), (234, 56), (216, 56), (216, 36), (194, 24), (194, -10),
           (216, -22), (216, -134), (234, -134), (238, -136), (238, -140), (232, -144),
           (209, -144), (209, -36), (187, -16), (187, 18), (202, 32), (209, 50), (222, 66)]
    face = [(33.1, 6), (76, 6), (90, 34), (196, 44), (214, 46), (214, 60), (200, 60),
            (100, 48), (80, 26), (33.1, 26)]
    s = revolve_profile(rim).fuse(revolve_profile(face)).clean()
    cuts = [cyl(7.5, 40, (*pcd(PCD_R, a), 0)) for a in STUD_ANGLES]
    for k in range(5):
        c = 90 + 36 + 72 * k
        a1i, a2i = radians(c - 27.5), radians(c + 27.5)
        a1o, a2o = radians(c - 30.5), radians(c + 30.5)
        rin, rout = 106, 186
        w = (cq.Workplane("XY")
             .moveTo(rin * cos(a1i), rin * sin(a1i))
             .lineTo(rout * cos(a1o), rout * sin(a1o))
             .threePointArc((rout * cos(radians(c)), rout * sin(radians(c))), (rout * cos(a2o), rout * sin(a2o)))
             .lineTo(rin * cos(a2i), rin * sin(a2i))
             .threePointArc((rin * cos(radians(c)), rin * sin(radians(c))), (rin * cos(a1i), rin * sin(a1i)))
             .close().extrude(50).translate((0, 0, 24)))
        try:
            w = w.edges("|Z").fillet(9)
        except Exception:
            pass
        cuts.append(w.val())
    cuts.append(cyl(5.5, 14, (0, 184, 7), (0, 1, 0)))             # tyre valve hole in drop well
    return cut_all(s, cuts)


def tyre():
    wp = (cq.Workplane("XZ").moveTo(216, 36).lineTo(216, 56).lineTo(234, 56).lineTo(240, 57)
          .spline([(246, 66), (256, 72), (275, 74), (292, 71), (305, 63), (313, 52), (316.5, 40), (317, 20),
                   (317, -39), (317, -98), (316.5, -118), (313, -130), (305, -141), (292, -149), (275, -152),
                   (256, -150), (246, -144), (240, -135)], includeCurrent=True)
          .lineTo(234, -134).lineTo(216, -134).lineTo(216, -114).lineTo(222, -114)
          .spline([(228, -122), (238, -130), (252, -138), (270, -139), (287, -133), (297, -120), (300, -103),
                   (300, -39), (300, 25), (297, 42), (287, 55), (270, 61), (252, 60), (238, 52), (228, 44),
                   (222, 36)], includeCurrent=True)
          .close().revolve(360, (0, 0, 0), (0, 1, 0)))
    s = wp.val()
    grooves = [tube(330, 309, 8, (0, 0, zc - 4)) for zc in (TYRE_ZC - 70, TYRE_ZC - 25, TYRE_ZC + 25, TYRE_ZC + 70)]
    return cut_all(s, grooves)


def tyre_valve():
    """Snap-in valve; local z points radially inwards, base flange sits in the tyre cavity."""
    base = cyl(9, 2, (0, 0, -20))
    stem = cyl(5.5, 18, (0, 0, -18))
    tip = cyl(4, 20, (0, 0, 0))
    cap = cyl(4.6, 10, (0, 0, 18))
    return fuse_all([base, stem, tip, cap])


def lug_nut():
    seat = cq.Solid.makeCone(11.5, 10.5, 3, V(0, 0, 0))
    hexh = hexagon_prism(19, 21, 3)
    dome = cyl(9, 6, (0, 0, 24))
    s = fuse_all([seat, hexh, dome])
    s = cq.Workplane().add(s).faces(">Z").edges().fillet(2.5).val()
    return s.cut(cyl(6, 20, (0, 0, -0.01)))


def centre_cap():
    plug = cyl(32.8, 10, (0, 0, -10))
    lid = cyl(40, 3, (0, 0, 0))
    s = fuse_all([plug, lid])
    s = cq.Workplane().add(s).faces(">Z").edges().fillet(2.0).val()
    ring = tube(30, 26, 1.0, (0, 0, 3 - 0.01))
    s = s.fuse(ring).clean()
    return s.cut(cyl(28, 8, (0, 0, -11)))


# ----------------------------------------------------------------- assembly --
def build():
    P = dict(
        knuckle=Part("Steering Knuckle", steering_knuckle(), "cast_iron"),
        bearing=Part("Wheel Bearing", wheel_bearing(), "steel"),
        hub=Part("Wheel Hub", wheel_hub(), "dark_steel"),
        hubnut=Part("Hub Nut M44", hub_nut(), "black_oxide"),
        stud=Part("Wheel Stud M12", wheel_stud(), "gold"),
        disc=Part("Brake Disc 300mm Vented", brake_disc(), "silver_paint"),
        cal=Part("Caliper Body", caliper_body(), "red"),
        piston=Part("Caliper Piston", caliper_piston(), "steel"),
        pad=Part("Brake Pad", brake_pad(), "gunmetal"),
        pin=Part("Pad Retaining Pin", pad_pin(), "steel"),
        bleed=Part("Bleed Screw", bleed_screw(), "brass"),
        calbolt=Part("Caliper Mounting Bolt M10", caliper_bolt(), "black_oxide"),
        wheel=Part("Alloy Wheel 17x7.5", alloy_wheel(), "silver_paint"),
        tyre=Part("Tyre 225-45 R17", tyre(), "rubber"),
        valve=Part("Tyre Valve", tyre_valve(), "black_oxide"),
        lugnut=Part("Lug Nut M12", lug_nut(), "steel"),
        cap=Part("Centre Cap", centre_cap(), "black_oxide"),
    )

    caliper = Asm("Brake Caliper Assembly")
    caliper.add(P["cal"])
    for (x, y) in PISTON_POS:
        caliper.add(P["piston"], wf((x, y, -60), [("x", 180)]))   # inboard pistons
        caliper.add(P["piston"], wf((x, y, 0)))                   # outboard pistons
    caliper.add(P["pad"], wf((0, 0, -60)))                         # inner pad
    caliper.add(P["pad"], wf((0, 0, 0), [("x", 180)]))             # outer pad
    caliper.add(P["pin"], wf((*PAD_PIN_POS, 22)))
    bx, by = pcd(178, 20)
    caliper.add(P["bleed"], wf((bx, by, -75), [("y", 90), ("z", 20)]))

    wheel = Asm("Wheel and Tyre Assembly")
    wheel.add(P["wheel"])
    wheel.add(P["tyre"])
    wheel.add(P["valve"], wf((0, 176, 7), [("x", 90)]))
    wheel.add(P["cap"], wf((0, 0, 26)))

    root = Asm("Front Wheel Corner Assembly")
    W = WHEEL_FRAME
    root.add(P["knuckle"], W)
    root.add(P["bearing"], W)
    root.add(P["hub"], W)
    root.add(P["hubnut"], compose(W, wf((0, 0, -108))))
    for a in STUD_ANGLES:
        root.add(P["stud"], compose(W, wf((*pcd(PCD_R, a), -12))))
    root.add(P["disc"], W)
    root.add(caliper, W)
    for a in (45, -45):
        root.add(P["calbolt"], compose(W, wf((*pcd(125, a), -100), [("x", 180)])))
    root.add(wheel, W)
    for a in STUD_ANGLES:
        root.add(P["lugnut"], compose(W, wf((*pcd(PCD_R, a), 26))))
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "02_Moderate_Wheel_Brake_Corner.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Moderate: front wheel corner - hub, 4-piston disc brake, alloy wheel and tyre"))

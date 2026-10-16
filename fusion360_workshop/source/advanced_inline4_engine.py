"""03 ADVANCED - Inline 4-cylinder SOHC 8-valve engine (car theme).

Bore 80 x stroke 80 (1.6 L), rod 140, firing order 1-3-4-2.
Global frame: Z up, crankshaft along X (origin = crank centre line, middle
main bearing). Front of engine (timing belt) = -X. Intake side = -Y.

Static pose: crank at 0 deg -> cyl 1 at TDC (firing), cyl 4 at TDC (overlap),
cyl 2 & 3 at BDC. The camshaft is phased correctly for that pose, so the
cyl 3 intake valve and cyl 2 exhaust valve are shown OPEN (lobe pressing the
bucket, spring compressed).

Product structure (nested, for Auto Explode One Level vs All Levels):
  Inline-4 Engine
    Block Assembly            (block, main caps, main cap bolts)
    Crankshaft Assembly       (crank, flywheel, pulleys, bolts)
    Piston and Rod Assembly x4  (piston, pin, rings, rod, cap, rod bolts)
    Cylinder Head Assembly    (head, camshaft, caps, plugs, cam pulley,
      Valvetrain                 valves, springs, retainers, tappets)
    head gasket, head bolts, timing belt, covers, manifolds, sump ...
"""
import sys
from cadlib import *

CRANK_R, ROD_L, COMP_H = 40.0, 140.0, 30.0
BORE_R = 40.0
DECK_Z = CRANK_R + ROD_L + COMP_H + 1.0       # 211
HEAD_Z0, HEAD_Z1 = DECK_Z + 1.0, 312.0        # gasket 1 mm
CYL_X = [-138.0, -46.0, 46.0, 138.0]
MAIN_X = [-184.0, -92.0, 0.0, 92.0, 184.0]
PIN_UP = {0: True, 1: False, 2: False, 3: True}     # cyl index -> pin at TDC?
FIRING_INDEX = {0: 0, 2: 1, 3: 2, 1: 3}             # 1-3-4-2
CAM_Z = 338.0
BASE_R, NOSE_R, NOSE_D = 18.0, 7.6, 18.0
LOBE_SEP = 57.0
CHAMBER_ROOF = HEAD_Z0 + 5.0                         # 217
VALVE_LEN = 99.0
INT_R, EXH_R = 16.0, 14.0
SPRING_SEAT, SPRING_LEN = 272.0, 38.0
PLUG_XY = lambda cx: (cx - 6.0, 30.0)
BLK_X0, BLK_X1 = -195.0, 195.0
FRONT_PULLEY_X = (-231.0, -209.0)
FILTER_X, FILTER_Z = 40.0, 20.0
ROD_BOLT_Y = 31.0


def xcyl(r, x0, x1, y=0.0, z=0.0):
    return cyl(r, x1 - x0, (x0, y, z), (1, 0, 0))


def ycyl(r, y0, y1, x=0.0, z=0.0):
    return cyl(r, y1 - y0, (x, y0, z), (0, 1, 0))


def zcyl(r, z0, z1, x=0.0, y=0.0):
    return cyl(r, z1 - z0, (x, y, z0))


def yz_extrude(wp_fn, x0, x1):
    """wp_fn(Workplane on YZ) -> closed sketch; extrude along +X from x0 to x1."""
    wp = cq.Workplane("YZ").workplane(offset=x0)
    return wp_fn(wp).extrude(x1 - x0).val()


# =========================================================== crank & rods ===
def crankshaft():
    parts = [xcyl(25, mx - 11, mx + 11) for mx in MAIN_X]
    for i, cx in enumerate(CYL_X):
        zp = CRANK_R if PIN_UP[i] else -CRANK_R
        parts.append(xcyl(22, cx - 12, cx + 12, 0, zp))
        sgn = 1 if zp > 0 else -1
        for (x0, x1) in ((cx - 35, cx - 12), (cx + 12, cx + 35)):
            def web(wp, zp=zp, sgn=sgn):
                return wp.center(0, zp / 2).slot2D(abs(zp) + 58, 58, 90)
            parts.append(yz_extrude(web, x0, x1))
            a0, a1 = radians(-90 * sgn - 55), radians(-90 * sgn + 55)
            am = radians(-90 * sgn)
            def cw(wp, a0=a0, a1=a1, am=am):
                return (wp.moveTo(0, 0).lineTo(60 * cos(a0), 60 * sin(a0))
                        .threePointArc((60 * cos(am), 60 * sin(am)), (60 * cos(a1), 60 * sin(a1))).close())
            parts.append(yz_extrude(cw, x0, x1))
    parts.append(xcyl(16, -262, BLK_X0))                    # front snout
    parts.append(xcyl(40, BLK_X1, 210))                     # rear flywheel flange
    s = fuse_all(parts)
    cuts = [xcyl(6, -262.1, -232)]                          # pulley bolt thread
    for k in range(6):
        a = radians(30 + 60 * k)
        cuts.append(xcyl(4, 198, 210.1, 28 * cos(a), 28 * sin(a)))
    return cut_all(s, cuts)


def flywheel():
    g, info = spur_gear(2.75, 100, 20, 30)
    cuts = [tube(122, 62, 2.01, (0, 0, 18))]                # clutch face recess
    for k in range(6):
        a = radians(30 + 60 * k)
        cuts.append(cyl(4.5, 30, (28 * cos(a), 28 * sin(a), -5)))
        b = radians(60 * k)
        cuts.append(cyl(4, 30, (127 * cos(b), 127 * sin(b), -5)))
    for k in range(3):
        a = radians(90 + 120 * k)
        cuts.append(cyl(14, 30, (90 * cos(a), 90 * sin(a), -5)))
    return cut_all(g, cuts)


def crank_timing_pulley():
    x0, x1 = FRONT_PULLEY_X
    s = fuse_all([xcyl(30, x0 + 2, x1 - 2), xcyl(34, x0, x0 + 2), xcyl(34, x1 - 2, x1)])
    teeth = []
    for k in range(20):
        a = 360 / 20 * k
        teeth.append(box(x0 + 2, x1 - 2, -1.6, 1.6, 28.6, 31).rotate(V(0, 0, 0), V(1, 0, 0), a))
    s = cut_all(s, teeth)
    return s.cut(xcyl(16, x0 - 1, x1 + 1))


def crank_pulley():
    x0, x1 = -262.0, -236.0
    s = fuse_all([xcyl(25, x0, x1), xcyl(64, x0 + 8, x0 + 16), tube(75, 62, x1 - x0, (x0, 0, 0), (1, 0, 0))])
    cuts = [xcyl(16, x0 - 1, x1 + 1)]
    for k in range(4):
        xg = x0 + 4 + k * 5.5
        cuts.append(tube(80, 72.5, 2.5, (xg, 0, 0), (1, 0, 0)))
    for k in range(4):
        a = radians(45 + 90 * k)
        cuts.append(xcyl(10, x0 - 1, x1 + 1, 44 * cos(a), 44 * sin(a)))
    return cut_all(s, cuts)


def connecting_rod():
    ring = tube(34, 22, 22, (-11, 0, 0), (1, 0, 0)).intersect(box(-12, 12, -40, 40, 0, 40))
    bosses = [box(-11, 11, 24, 38, 0, 16), box(-11, 11, -38, -24, 0, 16)]
    beam = cq.Workplane("YZ").workplane(offset=-9).polyline(
        [(-20, 26), (20, 26), (11, 128), (-11, 128)]).close().extrude(18).val()
    small = tube(16, 10, 20, (-10, 0, ROD_L), (1, 0, 0))
    small_fill = xcyl(16, -9, 9, 0, ROD_L)
    s = fuse_all([ring, beam, small_fill] + bosses)
    s = s.cut(xcyl(10, -12, 12, 0, ROD_L)).fuse(small).clean()
    pockets = []
    for xs in (4.5, -9.01):
        pockets.append(cq.Workplane("YZ").workplane(offset=xs).polyline(
            [(-13, 42), (13, 42), (6.5, 118), (-6.5, 118)]).close().extrude(4.51).val())
    s = cut_all(s, pockets)
    s = cut_all(s, [zcyl(4.5, -1, 14, 0, ROD_BOLT_Y), zcyl(4.5, -1, 14, 0, -ROD_BOLT_Y), xcyl(22, -12, 12)])
    return s


def rod_cap():
    ring = tube(34, 22, 22, (-11, 0, 0), (1, 0, 0)).intersect(box(-12, 12, -40, 40, -40, 0))
    bosses = [box(-11, 11, 24, 38, -26, 0), box(-11, 11, -38, -24, -26, 0)]
    s = fuse_all([ring] + bosses)
    return cut_all(s, [zcyl(4.5, -27, 1, 0, ROD_BOLT_Y), zcyl(4.5, -27, 1, 0, -ROD_BOLT_Y), xcyl(22, -12, 12)])


def piston():
    s = zcyl(39.8, -32, 30)
    s = s.cut(zcyl(34, -33, 22))
    bosses = [xcyl(14, 10.5, 34.5), xcyl(14, -34.5, -10.5)]
    s = fuse_all([s] + bosses)
    cuts = [xcyl(10, -45, 45)]
    for (z0, z1) in ((24, 25.5), (19.5, 21), (13, 16)):
        cuts.append(tube(41, 36, z1 - z0, (0, 0, z0)))
    for sx in (1, -1):                                       # slipper skirt relief
        cuts.append(box(29 * sx if sx > 0 else -45, 45 if sx > 0 else -29, -45, 45, -33, -16))
    cuts.append(zcyl(INT_R + 1, 28.5, 31, -20, 0))            # valve reliefs in crown
    cuts.append(zcyl(EXH_R + 1, 28.5, 31, 20, 0))
    return cut_all(s, cuts)


def gudgeon_pin():
    return tube(10, 6, 66, (0, 0, -33))


def piston_ring(h):
    s = tube(39.8, 36.5, h)
    return s.cut(box(38, 41, -0.25, 0.25, -1, h + 1))


def oil_ring():
    s = tube(39.8, 36.5, 3)
    s = s.cut(box(38, 41, -0.3, 0.3, -1, 4))
    slots = [box(36, 41, -1.2, 1.2, 1.0, 2.0).rotate(V(0, 0, 0), V(0, 0, 1), 15 + k * 30) for k in range(12)]
    return cut_all(s, slots)


def rod_bolt():
    return flange_bolt(9, 40, af=12, head_h=6)


# ===================================================== block & bottom end ===
def cylinder_block():
    parts = [box(BLK_X0, BLK_X1, -75, 75, 90, DECK_Z), box(BLK_X0, BLK_X1, -95, 95, -60, 90)]
    s = fuse_all(parts)
    s = s.cut(box(-173, 173, -85, 85, -60.01, 80)).cut(box(-173, 173, -73, 73, 79, 90))
    adds = [box(mx - 11, mx + 11, -85, 85, 0, 90) for mx in MAIN_X[1:4]]
    adds += [zcyl(46, 70, 90.01, cx) for cx in CYL_X]
    adds.append(ycyl(36, -103, -94.99, FILTER_X, FILTER_Z))   # oil filter boss
    for x in (-150, 150):                                       # engine mount bosses
        for y in (-95, 95):
            adds.append(box(x - 22, x + 22, y - 8 if y < 0 else y, y if y < 0 else y + 8, -10, 40))
    s = fuse_all([s] + adds)
    cuts = [zcyl(BORE_R, 60, DECK_Z + 1, cx) for cx in CYL_X]
    cuts.append(xcyl(25, BLK_X0 - 1, BLK_X1 + 1))
    cuts.append(box(BLK_X0 - 1, -173, -45, 45, -61, 0))
    cuts.append(box(173, BLK_X1 + 1, -45, 45, -61, 0))
    for mx in MAIN_X:
        for y in (-35, 35):
            cuts.append(zcyl(5, -0.01, 30, mx, y))
            cuts.append(zcyl(5.5, 150, DECK_Z + 0.01, mx, y * 55 / 35))
    cuts.append(ycyl(10, -104, -80, FILTER_X, FILTER_Z))      # oil filter thread
    for x in (-150, 150):
        for y in (-99, 99):
            cuts.append(ycyl(5, -110 if y < 0 else 90, -90 if y < 0 else 110, x, 15))
    return cut_all(s, cuts)


def main_cap():
    s = box(-11, 11, -45, 45, -30, 0)
    s = cq.Workplane().add(s).edges("|X").edges("<Z").chamfer(4).val()
    return cut_all(s, [xcyl(25, -12, 12), zcyl(5, -31, 1, 0, 35), zcyl(5, -31, 1, 0, -35)])


def oil_pan():
    w = (cq.Workplane("XY").box(BLK_X1 - BLK_X0, 190, 90).translate((0, 0, -105))
         .edges("|Z").fillet(12).edges("<Z").fillet(10).faces(">Z").shell(-3))
    s = solid_of(w)
    lip = box(BLK_X0, BLK_X1, -95, 95, -66, -60).cut(box(BLK_X0 + 6, BLK_X1 - 6, -89, 89, -67, -59))
    s = s.fuse(lip).clean()
    return s.cut(zcyl(7, -151, -146, 150, 0))


def drain_plug():
    return flange_bolt(14, 12, af=17, head_h=9)


def oil_filter():
    X, Z = FILTER_X, FILTER_Z
    can = ycyl(38, -190, -107, X, Z)
    can = cq.Workplane().add(can).faces("<Y").edges().fillet(10).val()
    base = ycyl(36, -107, -103, X, Z)
    s = fuse_all([can, base])
    flutes = []
    for k in range(16):
        a = 360 / 16 * k
        fl = box(X - 2, X + 2, -175, -150, Z + 37, Z + 40).rotate(V(X, 0, Z), V(0, 1, 0), a)
        flutes.append(fl)
    s = cut_all(s, flutes)
    return s.cut(ycyl(10, -104, -100, X, Z))


# ================================================================ head ======
def lobe_lift(theta_deg):
    """Valve lift for a lobe whose nose points theta deg from +Z (towards +Y)."""
    psi = radians(180 - (theta_deg % 360)) if True else 0
    psi = abs(math.atan2(math.sin(psi), math.cos(psi)))
    return max(0.0, NOSE_D * cos(psi) + NOSE_R - BASE_R)


def lobe_angles():
    out = {}
    for i, cx in enumerate(CYL_X):
        phi = 90.0 * FIRING_INDEX[i]
        out[(i, "int")] = LOBE_SEP + phi
        out[(i, "exh")] = -LOBE_SEP + phi
    return out


def valve_x(i, kind):
    return CYL_X[i] + (-20.0 if kind == "int" else 20.0)


def valve_profile(R):
    return [(0, 0), (R, 0), (R, 1.2), (R - 3, 4), (R - 9.5, 9), (3.5, 16), (3.5, VALVE_LEN), (0, VALVE_LEN)]


def valve(R):
    s = revolve_profile(valve_profile(R))
    s = s.cut(tube(4, 2.9, 2, (0, 0, VALVE_LEN - 9)))        # keeper groove
    return s


def cylinder_head():
    s = box(BLK_X0, BLK_X1, -75, 75, HEAD_Z0, HEAD_Z1)
    towers = [box(mx - 10, mx + 10, -28, 28, HEAD_Z1 - 0.01, CAM_Z) for mx in MAIN_X]
    s = fuse_all([s] + towers)
    cuts = []
    for i, cx in enumerate(CYL_X):
        cuts.append(zcyl(38, HEAD_Z0 - 0.1, CHAMBER_ROOF, cx))
        for kind, R, pr, ydir in (("int", INT_R, 13.0, -1), ("exh", EXH_R, 11.0, 1)):
            vx = valve_x(i, kind)
            seat = revolve_profile([(0, -0.2), (R, -0.2), (R, 1.2), (R - 3, 4), (0, 4)])
            cuts.append(seat.translate(V(vx, 0, CHAMBER_ROOF)))
            cuts.append(zcyl(pr, CHAMBER_ROOF + 3, 245, vx))
            cuts.append(sphere(pr, (vx, 0, 245)))
            cuts.append(ycyl(pr, min(0, 76 * ydir), max(0, 76 * ydir), vx, 245))
            cuts.append(zcyl(3.5, 240, SPRING_SEAT + 0.01, vx))      # guide
            cuts.append(zcyl(15, SPRING_SEAT, HEAD_Z1 + 0.01, vx))  # tappet bore
        px, py = PLUG_XY(cx)
        cuts.append(zcyl(7, CHAMBER_ROOF - 0.1, 236, px, py))
        cuts.append(zcyl(12, 236, HEAD_Z1 + 0.01, px, py))
    for mx in MAIN_X:
        for y in (-55, 55):
            cuts.append(zcyl(6, HEAD_Z0 - 0.1, HEAD_Z1 + 0.1, mx, y))
        for y in (-21, 21):
            cuts.append(zcyl(3.5, 318, CAM_Z + 0.01, mx, y))
    cuts.append(xcyl(14, BLK_X0 - 1, BLK_X1 + 1, 0, CAM_Z))
    return cut_all(s, cuts)


def lobe_sketch(theta_deg):
    """Closed lobe outline in the YZ plane (cam axis at origin)."""
    t = radians(theta_deg)
    n = (sin(t), cos(t))                                    # nose direction (y, z)
    c1 = (NOSE_D * n[0], NOSE_D * n[1])
    alpha = math.acos((BASE_R - NOSE_R) / NOSE_D)
    def rot(v, a):
        return (v[0] * cos(a) - v[1] * sin(a), v[0] * sin(a) + v[1] * cos(a))
    np_, nm = rot(n, alpha), rot(n, -alpha)
    T0p, T0m = (BASE_R * np_[0], BASE_R * np_[1]), (BASE_R * nm[0], BASE_R * nm[1])
    T1p = (c1[0] + NOSE_R * np_[0], c1[1] + NOSE_R * np_[1])
    T1m = (c1[0] + NOSE_R * nm[0], c1[1] + NOSE_R * nm[1])
    tip = (c1[0] + NOSE_R * n[0], c1[1] + NOSE_R * n[1])
    back = (-BASE_R * n[0], -BASE_R * n[1])
    def f(wp):
        return (wp.moveTo(*T0p).lineTo(*T1p).threePointArc(tip, T1m).lineTo(*T0m)
                .threePointArc(back, T0p).close())
    return f


def camshaft():
    parts = [xcyl(12, MAIN_X[0] - 10, MAIN_X[-1] + 10, 0, CAM_Z)]
    parts += [xcyl(14, mx - 10, mx + 10, 0, CAM_Z) for mx in MAIN_X]
    parts.append(xcyl(10, -235, MAIN_X[0] - 9.99, 0, CAM_Z))
    for (i, kind), th in lobe_angles().items():
        vx = valve_x(i, kind)
        lobe = yz_extrude(lobe_sketch(th), vx - 7, vx + 7).translate(V(0, 0, CAM_Z))
        parts.append(lobe)
    return fuse_all(parts)


def cam_cap():
    s = box(-10, 10, -28, 28, 0, 16)
    s = cq.Workplane().add(s).edges("|X").edges(">Z").fillet(5).val()
    return cut_all(s, [xcyl(14, -11, 11), zcyl(3.5, -1, 17, 0, 21), zcyl(3.5, -1, 17, 0, -21)])


def cam_pulley():
    x0, x1 = FRONT_PULLEY_X
    s = fuse_all([xcyl(60, x0 + 2, x1 - 2, 0, CAM_Z), xcyl(64, x0, x0 + 2, 0, CAM_Z), xcyl(64, x1 - 2, x1, 0, CAM_Z)])
    cuts = [xcyl(10, x0 - 1, x1 + 1, 0, CAM_Z)]
    for k in range(5):
        a = radians(90 + 72 * k)
        cuts.append(xcyl(12, x0 - 1, x1 + 1, 36 * cos(a), CAM_Z + 36 * sin(a)))
    teeth = []
    for k in range(40):
        teeth.append(box(x0 + 2, x1 - 2, -1.6, 1.6, 58.6, 61).rotate(V(0, 0, 0), V(1, 0, 0), 9 * k)
                     .translate(V(0, 0, CAM_Z)))
    return cut_all(s, cuts + teeth)


def bucket_tappet():
    return fuse_all([zcyl(15, 0, 4), tube(15, 13, 20, (0, 0, -20))])


def spring_retainer():
    flange = tube(11, 3.5, 3, (0, 0, 0))
    hub = cq.Solid.makeCone(5.5, 7, 7, V(0, 0, -7))
    s = fuse_all([flange, hub])
    return s.cut(zcyl(3.5, -8, 4))


def spark_plug():
    parts = [zcyl(7, -19, 0), zcyl(1, -21, -19), hexagon_prism(16, 14, 0), zcyl(9, 13.9, 16)]
    parts.append(zcyl(5.5, 16, 60))
    parts.append(zcyl(3, 59.9, 68))
    s = fuse_all(parts)
    ribs = [tube(6, 5.0, 1.5, (0, 0, 34 + 4 * k)) for k in range(5)]
    return cut_all(s, ribs)


# =========================================================== top end ========
def head_gasket():
    s = box(BLK_X0, BLK_X1, -75, 75, DECK_Z, HEAD_Z0)
    cuts = [zcyl(41, DECK_Z - 1, HEAD_Z0 + 1, cx) for cx in CYL_X]
    cuts += [zcyl(6, DECK_Z - 1, HEAD_Z0 + 1, mx, y) for mx in MAIN_X for y in (-55, 55)]
    return cut_all(s, cuts)


def valve_cover():
    w = (cq.Workplane("XY").box(400, 154, 70).translate((0, 0, HEAD_Z1 + 35))
         .edges("|Z").fillet(10).edges(">Z").fillet(14).faces("<Z").shell(-4))
    s = solid_of(w)
    ribs = [box(-150, 150, y - 2, y + 2, HEAD_Z1 + 69, HEAD_Z1 + 72) for y in (55, 65)]
    s = fuse_all([s] + ribs)
    cuts = [zcyl(12, 300, 400, *PLUG_XY(cx)) for cx in CYL_X]
    cuts.append(xcyl(13, -205, -190, 0, CAM_Z))
    cuts.append(zcyl(15, 360, 400, 100, -45))
    return cut_all(s, cuts)


def oil_filler_cap():
    s = fuse_all([zcyl(14.8, -10, 0), zcyl(20, 0, 10)])
    s = cq.Workplane().add(s).faces(">Z").edges().fillet(3).val()
    grips = [box(18, 22, -2, 2, 1, 11).rotate(V(0, 0, 0), V(0, 0, 1), 30 * k) for k in range(12)]
    return cut_all(s, grips)


def ignition_coil():
    """Pencil coil: boot goes down the plug well, head sits on the cam cover."""
    boot = fuse_all([zcyl(6.5, 305 - 382, -14), zcyl(11, -14, 0)])   # slim boot clears the cam lobes
    head = box(-20, 20, -13, 13, 0, 16)
    head = cq.Workplane().add(head).edges("|Z").fillet(5).val()
    conn = box(14, 30, -7, 7, 4, 14)
    ear = box(-34, -14, -6, 6, 0, 4).fuse(zcyl(6, 0, 4, -34, 0)).clean()
    s = fuse_all([boot, head, conn, ear])
    return cut_all(s, [box(18, 31, -5, 5, 6, 12), zcyl(3, -1, 5, -34, 0)])


def timing_belt():
    c1, c2 = (0.0, 0.0), (0.0, CAM_Z)

    def hull(r1, r2):
        d = c2[1] - c1[1]
        u = (0.0, 1.0)
        a = math.acos((r1 - r2) / d)
        def rot(v, ang):
            return (v[0] * cos(ang) - v[1] * sin(ang), v[0] * sin(ang) + v[1] * cos(ang))
        np_, nm = rot(u, a), rot(u, -a)
        T1p, T1m = (r1 * np_[0], r1 * np_[1]), (r1 * nm[0], r1 * nm[1])
        T2p = (c2[0] + r2 * np_[0], c2[1] + r2 * np_[1])
        T2m = (c2[0] + r2 * nm[0], c2[1] + r2 * nm[1])
        far2 = (c2[0] + r2 * u[0], c2[1] + r2 * u[1])
        far1 = (c1[0] - r1 * u[0], c1[1] - r1 * u[1])
        def f(wp):
            return (wp.moveTo(*T1p).lineTo(*T2p).threePointArc(far2, T2m).lineTo(*T1m)
                    .threePointArc(far1, T1p).close())
        return f
    x0, x1 = FRONT_PULLEY_X[0] + 2, FRONT_PULLEY_X[1] - 2
    outer = yz_extrude(hull(34, 64), x0, x1)
    inner = yz_extrude(hull(30, 60), x0 - 1, x1 + 1)
    return outer.cut(inner)


def intake_manifold():
    ports = [valve_x(i, "int") for i in range(4)]
    parts = [box(-180, 140, -87, -75, 223, 267)]
    parts += [ycyl(17, -152, -86.99, px, 245) for px in ports]
    plen = xcyl(32, -185, 150, -172, 245)
    plen = cq.Workplane().add(plen).faces(">X").edges().fillet(10).val()
    parts.append(plen)
    s = fuse_all(parts)
    cuts = [ycyl(13, -165, -74, px, 245) for px in ports]
    cuts.append(xcyl(28, -181, 144, -172, 245))
    cuts.append(xcyl(22, -186, -180, -172, 245))
    for px in (-170, -20, 130):
        for z in (230, 260):
            cuts.append(ycyl(4, -88, -74, px if px < 130 else 135, z))
    return cut_all(s, cuts)


def throttle_body():
    body = tube(28, 22, 30, (-215, -172, 245), (1, 0, 0))
    flange = tube(34, 22, 6, (-191, -172, 245), (1, 0, 0))
    plate = xcyl(21.6, -201, -199, -172, 245).rotate(V(-200, -172, 245), V(0, 0, 1), 20)
    spindle = ycyl(2.5, -201, -143.5, -200, 245)
    lever = box(-206, -194, -146, -142, 247, 275)
    return fuse_all([body, flange, plate, spindle, lever])


def exhaust_manifold():
    ports = [valve_x(i, "exh") for i in range(4)]
    C = (20.0, 160.0, 150.0)
    D = (20.0, 160.0, 52.0)
    outer, inner = [box(-140, 180, 75, 87, 223, 267)], []
    for px in ports:
        P0, P1 = (px, 80.0, 245.0), (px, 118.0, 245.0)
        P2 = ((px + 20) / 2, 150.0, 192.0)
        for (a, b) in ((P0, P1), (P1, P2), (P2, C)):
            outer.append(cyl_between(17, a, b))
            inner.append(cyl_between(13, a, b))
        outer += [sphere(17, P1), sphere(17, P2)]
        inner += [sphere(13, P1), sphere(13, P2)]
        inner.append(ycyl(11.5, 74, 81, px, 245))
    outer += [sphere(24, C), cyl_between(22, C, D), tube(34, 18, 8, (D[0], D[1], D[2]))]
    inner += [sphere(19, C), cyl_between(18, C, (D[0], D[1], D[2] - 2))]
    s = fuse_all(outer)
    return cut_all(s, inner)


# ================================================================ build =====
def build():
    P = dict(
        block=Part("Cylinder Block", cylinder_block(), "cast_iron"),
        maincap=Part("Main Bearing Cap", main_cap(), "cast_iron"),
        mainbolt=Part("Main Cap Bolt M10", flange_bolt(10, 60), "black_oxide"),
        crank=Part("Crankshaft", crankshaft(), "dark_steel"),
        flywheel=Part("Flywheel", flywheel(), "steel"),
        flybolt=Part("Flywheel Bolt M8", flange_bolt(8, 32), "black_oxide"),
        ctp=Part("Crank Timing Pulley", crank_timing_pulley(), "steel"),
        cpul=Part("Crank Pulley", crank_pulley(), "gunmetal"),
        cpbolt=Part("Crank Pulley Bolt M12", hex_bolt(12, 30, af=19, head_h=9), "black_oxide"),
        piston=Part("Piston", piston(), "aluminium"),
        pin=Part("Gudgeon Pin", gudgeon_pin(), "steel"),
        ring=Part("Compression Ring", piston_ring(1.5), "dark_steel"),
        oilring=Part("Oil Control Ring", oil_ring(), "dark_steel"),
        rod=Part("Connecting Rod", connecting_rod(), "steel"),
        cap=Part("Rod Cap", rod_cap(), "steel"),
        rodbolt=Part("Rod Bolt M9", rod_bolt(), "black_oxide"),
        gasket=Part("Head Gasket", head_gasket(), "copper"),
        head=Part("Cylinder Head", cylinder_head(), "aluminium"),
        headbolt=Part("Head Bolt M11", flange_bolt(11, 150, af=16, head_h=8), "black_oxide"),
        cam=Part("Camshaft", camshaft(), "dark_steel"),
        camcap=Part("Cam Bearing Cap", cam_cap(), "aluminium"),
        cambolt=Part("Cam Cap Bolt M7", flange_bolt(7, 30), "black_oxide"),
        campul=Part("Cam Timing Pulley", cam_pulley(), "steel"),
        ivalve=Part("Intake Valve", valve(INT_R), "steel"),
        evalve=Part("Exhaust Valve", valve(EXH_R), "dark_steel"),
        spring=Part("Valve Spring", helical_spring(9.5, 1.7, SPRING_LEN, 6), "green"),
        retainer=Part("Spring Retainer", spring_retainer(), "steel"),
        tappet=Part("Bucket Tappet", bucket_tappet(), "steel"),
        plug=Part("Spark Plug", spark_plug(), "ceramic"),
        coil=Part("Ignition Coil", ignition_coil(), "black_oxide"),
        belt=Part("Timing Belt", timing_belt(), "rubber"),
        cover=Part("Valve Cover", valve_cover(), "red"),
        filler=Part("Oil Filler Cap", oil_filler_cap(), "yellow"),
        pan=Part("Oil Pan", oil_pan(), "gunmetal"),
        drain=Part("Drain Plug", drain_plug(), "steel"),
        filter=Part("Oil Filter", oil_filter(), "blue"),
        intake=Part("Intake Manifold", intake_manifold(), "silver_paint"),
        throttle=Part("Throttle Body", throttle_body(), "aluminium"),
        exhaust=Part("Exhaust Manifold", exhaust_manifold(), "cast_iron"),
    )

    # --- block assembly
    blk = Asm("Block Assembly")
    blk.add(P["block"])
    for mx in MAIN_X:
        blk.add(P["maincap"], place((mx, 0, 0)))
    for mx in MAIN_X:
        for y in (-35, 35):
            blk.add(P["mainbolt"], place((mx, y, -30), [("x", 180)]))

    # --- crank assembly
    crk = Asm("Crankshaft Assembly")
    crk.add(P["crank"])
    crk.add(P["flywheel"], place((210, 0, 0), [("z", 90), ("y", 90)]))
    for k in range(6):
        a = radians(30 + 60 * k)
        crk.add(P["flybolt"], place((230, 28 * cos(a), 28 * sin(a)), [("y", 90)]))
    crk.add(P["ctp"])
    crk.add(P["cpul"])
    crk.add(P["cpbolt"], place((-262, 0, 0), [("y", -90)]))

    # --- piston & rod sub-assembly (origin = crank-pin centre, rod along +Z)
    pr = Asm("Piston and Rod Assembly")
    pr.add(P["rod"])
    pr.add(P["cap"])
    for y in (-ROD_BOLT_Y, ROD_BOLT_Y):
        pr.add(P["rodbolt"], place((0, y, -26), [("x", 180)]))
    pr.add(P["piston"], place((0, 0, ROD_L)))
    pr.add(P["pin"], place((0, 0, ROD_L), [("y", 90)]))
    pr.add(P["ring"], place((0, 0, ROD_L + 24), [("z", 0)]))
    pr.add(P["ring"], place((0, 0, ROD_L + 19.5), [("z", 120)]))
    pr.add(P["oilring"], place((0, 0, ROD_L + 13), [("z", 240)]))

    # --- valvetrain (lift computed from the cam lobe positions)
    vt = Asm("Valvetrain")
    compressed = {}
    lifts = {}
    for (i, kind), th in lobe_angles().items():
        L = round(lobe_lift(th), 2)
        lifts[(i + 1, kind)] = L
        vx = valve_x(i, kind)
        vt.add(P["ivalve" if kind == "int" else "evalve"], place((vx, 0, CHAMBER_ROOF - L)))
        if L > 0:
            if L not in compressed:
                compressed[L] = Part("Valve Spring (Compressed)" if not compressed else f"Valve Spring (Compressed {L} mm)",
                                     helical_spring(9.5, 1.7, SPRING_LEN - L, 6), "green")
            vt.add(compressed[L], place((vx, 0, SPRING_SEAT)))
        else:
            vt.add(P["spring"], place((vx, 0, SPRING_SEAT)))
        vt.add(P["retainer"], place((vx, 0, SPRING_SEAT + SPRING_LEN - L)))
        vt.add(P["tappet"], place((vx, 0, CHAMBER_ROOF + VALVE_LEN - L)))
    print("  valve lifts (cyl, valve): mm", {k: v for k, v in lifts.items() if v > 0})

    hd = Asm("Cylinder Head Assembly")
    hd.add(P["head"])
    hd.add(vt)
    hd.add(P["cam"])
    for mx in MAIN_X:
        hd.add(P["camcap"], place((mx, 0, CAM_Z)))
        for y in (-21, 21):
            hd.add(P["cambolt"], place((mx, y, CAM_Z + 16)))
    hd.add(P["campul"])
    for cx in CYL_X:
        hd.add(P["plug"], place((*PLUG_XY(cx), 236)))

    root = Asm("Inline-4 Engine")
    root.add(blk)
    root.add(crk)
    for i, cx in enumerate(CYL_X):
        root.add(pr, place((cx, 0, CRANK_R if PIN_UP[i] else -CRANK_R)))
    root.add(P["gasket"])
    root.add(hd)
    for mx in MAIN_X:
        for y in (-55, 55):
            root.add(P["headbolt"], place((mx, y, HEAD_Z1)))
    root.add(P["belt"])
    root.add(P["cover"])
    root.add(P["filler"], place((100, -45, HEAD_Z1 + 70)))
    for cx in CYL_X:
        root.add(P["coil"], place((*PLUG_XY(cx), HEAD_Z1 + 70)))
    root.add(P["pan"])
    root.add(P["drain"], place((150, 0, -150), [("x", 180)]))
    root.add(P["filter"])
    root.add(P["intake"])
    root.add(P["throttle"])
    root.add(P["exhaust"])
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "03_Advanced_Inline4_Engine.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Advanced: inline 4-cylinder SOHC 8-valve engine with nested sub-assemblies"))

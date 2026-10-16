"""02 MODERATE - Handheld game controller with PCB (22 components, 2 sub-assemblies).

Controller lies flat, buttons facing +Z (up), triggers on the back edge (+Y).
  Front Shell Assembly : front shell, D-pad, A/B/X/Y buttons
  Main Board Assembly  : PCB, 2 thumbstick modules, 2 thumbstick caps
  + back shell, battery, 2 rumble motors, 2 triggers, 5 screws
"""
import sys
from cadlib import *

H_SPLIT, TOP, BOT = 12.0, 26.0, 0.0
WALL = 2.0
PCB_Z = 7.0
DPAD = (-38.0, 10.0)
BTN_C = (38.0, 10.0)
BUTTONS = {"A": ((38, 1), "green"), "B": ((47, 10), "red"), "X": ((29, 10), "blue"), "Y": ((38, 19), "yellow")}
STICKS = [(-16.0, 1.0), (16.0, 1.0)]
SCREWS = [(-30, 24), (30, 24), (-45, -30), (45, -30), (0, -5)]
MOTORS = [(-42.0, -16.0), (42.0, -16.0)]
TRIG_X = 44.0


def footprint(offset=0.0):
    wp = cq.Workplane("XY").rect(110 - 2 * offset, 40 - 2 * offset).extrude(1).translate((0, 10, 0))
    for sx in (-1, 1):
        wp = wp.union(cq.Workplane("XY").circle(24 - offset).extrude(1).translate((45 * sx, -18, 0)))
    return wp


def body_solid(offset, z0, z1):
    f = footprint(offset).val()
    sk = cq.Workplane("XY").add(f).faces("<Z").wires().toPending().extrude(z1 - z0)
    return sk.val().translate(V(0, 0, z0))


def shells():
    outer = body_solid(0, BOT, TOP)
    try:
        outer = cq.Workplane().add(outer).edges("|Z").fillet(6).faces(">Z or <Z").edges().fillet(3).val()
    except Exception:
        pass
    inner = body_solid(WALL, BOT + WALL, TOP - WALL)
    hollow = outer.cut(inner)
    # screw bosses
    bosses = [zc(3.5, BOT + 1, TOP - 1, x, y) for x, y in SCREWS]
    hollow = fuse_all([hollow] + bosses)
    # trigger notches through the back edge
    notch = [box(TRIG_X * s - 8, TRIG_X * s + 8, 25, 40, 10, 22) for s in (-1, 1)]
    hollow = cut_all(hollow, notch)
    front = hollow.intersect(box(-100, 100, -60, 60, H_SPLIT, 50))
    back = hollow.intersect(box(-100, 100, -60, 60, -10, H_SPLIT))
    # front shell openings
    cuts = [box(DPAD[0] - 11.3, DPAD[0] + 11.3, DPAD[1] - 3.8, DPAD[1] + 3.8, 20, 30),
            box(DPAD[0] - 3.8, DPAD[0] + 3.8, DPAD[1] - 11.3, DPAD[1] + 11.3, 20, 30)]
    cuts += [zc(5, 20, 30, *p) for p, _ in BUTTONS.values()]
    cuts += [zc(11, 20, 30, *p) for p in STICKS]
    cuts += [zc(1, H_SPLIT - 1, TOP - 3, x, y) for x, y in SCREWS]          # tapped holes
    front = cut_all(front, cuts)
    bcuts = [zc(1.1, -1, H_SPLIT + 1, x, y) for x, y in SCREWS]
    bcuts += [zc(2.2, -1, 2, x, y) for x, y in SCREWS]                # counterbores
    back = cut_all(back, bcuts)
    return front, back


def zc(r, z0, z1, x=0.0, y=0.0):
    return cyl(r, z1 - z0, (x, y, z0))


def dpad():
    s = fuse_all([box(-11, 11, -3.5, 3.5, 22, 28), box(-3.5, 3.5, -11, 11, 22, 28),
                  box(-13, 13, -4.5, 4.5, 22, 23.6), box(-4.5, 4.5, -13, 13, 22, 23.6)])
    return s.translate(V(*DPAD, 0))


def face_button():
    s = fuse_all([zc(4.5, 22, 28), zc(6, 22, 23.6)])
    return cq.Workplane().add(s).faces(">Z").edges().fillet(1.2).val()


def pcb():
    s = box(-50, 50, -7, 27, PCB_Z, PCB_Z + 1.6)
    s = cut_all(s, [zc(4, PCB_Z - 1, PCB_Z + 3, x, y) for x, y in SCREWS])
    top = PCB_Z + 1.6
    parts = [s]
    parts += [box(-7, 7, 6, 20, top, top + 1.4), box(-4, 4, 0, 4, top, top + 1)]   # MCU + chip
    for p, _ in BUTTONS.values():
        parts.append(box(p[0] - 3, p[0] + 3, p[1] - 3, p[1] + 3, top, top + 2))      # tact switches
    for dx, dy in ((-8, 0), (8, 0), (0, -8), (0, 8)):
        parts.append(box(DPAD[0] + dx - 2.5, DPAD[0] + dx + 2.5, DPAD[1] + dy - 2.5, DPAD[1] + dy + 2.5, top, top + 2))
    parts.append(box(-5, 5, 22, 27, top, top + 3.5))                                  # USB-C socket
    for k in range(6):
        parts.append(box(-25 + 3 * k, -23 + 3 * k, 22, 25, top, top + 1.5))           # passives
    return fuse_all(parts)


def stick_module():
    top = PCB_Z + 1.6
    s = box(-7, 7, -7, 7, top, top + 8)
    return fuse_all([s, zc(5, top + 8, top + 9.5)])


def stick_cap():
    top = PCB_Z + 1.6 + 9.5
    shaft = zc(2.5, top, 27)
    cap = zc(9, 27, 31)
    cap = cq.Workplane().add(cap).faces(">Z").edges().fillet(2.5).val()
    s = fuse_all([shaft, cap])
    return s.cut(tube(6, 5, 1, (0, 0, 30.6)))


def battery():
    s = box(-20, 20, 2, 22, WALL, 6.5)
    return cq.Workplane().add(s).edges("|Z").fillet(2).val()


def rumble_motor():
    s = zc(5, WALL, 11)
    weight = sector(0, 4, -60, 60, 11, 13)
    return fuse_all([s, zc(0.8, 11, 11.5), weight])


def trigger():
    s = box(-7.5, 7.5, 26.5, 33, 11, 21)
    s = cq.Workplane().add(s).edges("|X").edges(">Y").fillet(3).val()
    return s.cut(cyl(1.2, 20, (-10, 28.5, 12.5), (1, 0, 0)))


def build():
    front, back = shells()
    fs = Asm("Front Shell Assembly")
    fs.add(Part("Front Shell", front, "white"))
    fs.add(Part("D-Pad", dpad(), "gunmetal"))
    for name, (p, col) in BUTTONS.items():
        fs.add(Part(f"Button {name}", face_button(), col), place((p[0], p[1], 0)))
    mb = Asm("Main Board Assembly")
    mb.add(Part("Main PCB", pcb(), "green"))
    mod, cap = Part("Thumbstick Module", stick_module(), "black_oxide"), Part("Thumbstick Cap", stick_cap(), "gunmetal")
    for x, y in STICKS:
        mb.add(mod, place((x, y, 0)))
    for x, y in STICKS:
        mb.add(cap, place((x, y, 0)))
    root = Asm("Game Controller")
    root.add(fs)
    root.add(mb)
    root.add(Part("Back Shell", back, "gunmetal"))
    root.add(Part("Battery", battery(), "blue"))
    motor = Part("Rumble Motor", rumble_motor(), "silver_paint")
    for x, y in MOTORS:
        root.add(motor, place((x, y, 0)))
    trig = Part("Trigger", trigger(), "black_oxide")
    for s in (-1, 1):
        root.add(trig, place((TRIG_X * s, 0, 0)))
    scr = Part("Screw M2x18", socket_cap_screw(2, 18), "steel")
    for x, y in SCREWS:
        root.add(scr, place((x, y, 2), [("x", 180)]))
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "02_Moderate_Game_Controller.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Moderate: handheld game controller with PCB"))

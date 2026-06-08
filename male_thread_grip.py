"""
Male 2-start thread with grip base
  Base:    OD=24mm, H=6mm, Z=0..6, with 10 grip bumps around top edge
  Shaft:   OD=13.8mm (major), H=10mm, Z=6..16, entry chamfer at tip
  Thread:  2-start RH, pitch=1.4mm, lead=2.8mm, 60 deg profile
           Major (crest)=13.8mm, minor (root)=12.3mm, depth=0.75mm
"""

from build123d import *
from math import tan, radians, sin, cos, sqrt, pi


def gen_step():
    # ── Parameters ────────────────────────────────────────────────────────
    BASE_OD       = 24.0
    BASE_H        = 6.0
    MAJOR_D       = 13.8
    MINOR_D       = 12.3
    SHAFT_H       = 10.0
    PITCH         = 1.4
    LEAD          = 2.8
    THREAD_H      = (MAJOR_D - MINOR_D) / 2    # 0.75 mm
    FLANK_DEG     = 30.0
    FLANK_RUN     = THREAD_H * tan(radians(FLANK_DEG))
    HALF_CREST    = 0.08
    major_r       = MAJOR_D / 2                 # 6.9 mm
    SHAFT_Z0      = BASE_H                      # 6.0 mm
    SHAFT_Z1      = BASE_H + SHAFT_H            # 16.0 mm
    CHAMFER_SIZE  = 1.0                         # entry chamfer at shaft tip
    N_BUMPS       = 10
    BUMP_R        = 2.0                         # bump sphere radius
    BUMP_PCD      = 10.0                        # bump centre PCD radius from axis

    # ── Base + shaft body ─────────────────────────────────────────────────
    with BuildPart() as bp:
        # Base
        Cylinder(radius=BASE_OD/2, height=BASE_H,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
        # Shaft at major (crest) diameter
        with Locations((0, 0, BASE_H)):
            Cylinder(radius=major_r, height=SHAFT_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Grip bumps: sphere domes proud of the base top face
        for i in range(N_BUMPS):
            angle = 2 * pi * i / N_BUMPS
            cx = BUMP_PCD * cos(angle)
            cy = BUMP_PCD * sin(angle)
            with Locations((cx, cy, BASE_H + BUMP_R * 0.6)):
                Sphere(radius=BUMP_R, mode=Mode.ADD)

    body = bp.part

    # Entry chamfer: subtract a cone at the shaft tip
    # 45-deg chamfer, CHAMFER_SIZE deep, apex at shaft tip centre
    chamfer_cone = Cone(
        bottom_radius = major_r + CHAMFER_SIZE,
        top_radius    = 0,
        height        = major_r + CHAMFER_SIZE,
        align         = (Align.CENTER, Align.CENTER, Align.MIN),
    ).moved(Location((0, 0, SHAFT_Z1 - (major_r + CHAMFER_SIZE))))
    body = body - chamfer_cone

    # ── Per-turn groove sweeps ────────────────────────────────────────────
    def groove_solids(start_angle_deg: float) -> list:
        solids = []
        z0 = SHAFT_Z0 + 0.05
        # Leave chamfer zone clear at tip
        z_end = SHAFT_Z1 - CHAMFER_SIZE - 0.1
        while z0 < z_end:
            z1  = min(z0 + LEAD, z_end)
            h   = z1 - z0
            if h < 0.05:
                break
            helix = Helix(
                pitch  = LEAD,
                height = h,
                radius = major_r,
            ).moved(Location((0, 0, z0), (0, 0, start_angle_deg)))

            ang = radians(start_angle_deg)
            tx  = -sin(ang);  ty = cos(ang)
            tz  = LEAD / (2 * pi * major_r)
            mag = sqrt(tx*tx + ty*ty + tz*tz)
            tx /= mag; ty /= mag; tz /= mag

            sweep_plane = Plane(
                origin=(major_r * cos(ang), major_r * sin(ang), z0),
                z_dir=(tx, ty, tz),
                x_dir=(0, 0, 1),
            )
            with BuildSketch(sweep_plane) as sk:
                Polygon(
                    [
                        ( HALF_CREST + FLANK_RUN,  0),
                        ( HALF_CREST,             -THREAD_H),
                        (-HALF_CREST,             -THREAD_H),
                        (-(HALF_CREST + FLANK_RUN), 0),
                    ],
                    align=None,
                )
            g = sweep(sk.sketch, path=helix, is_frenet=True)
            if hasattr(g, 'volume') and g.volume > 0:
                solids.append(g)
            z0 += LEAD
        return solids

    # ── Fuse grooves then single subtraction ─────────────────────────────
    all_grooves = groove_solids(0.0) + groove_solids(180.0)
    tool = all_grooves[0]
    for g in all_grooves[1:]:
        tool = tool.fuse(g)
    result = body - tool

    result.label = "male_thread_grip"
    return result

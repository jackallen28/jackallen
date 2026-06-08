"""
Male 2-start threaded shaft
  Shaft:   OD=13.8mm (major), H=10mm, Z=0..10
  Thread:  2-start RH, pitch=1.4mm, lead=2.8mm, 60 deg profile
           Major (crest)=13.8mm, minor (root)=12.3mm, depth=0.75mm
"""

from build123d import *
from math import tan, radians, sin, cos, sqrt, pi


def gen_step():
    MAJOR_D    = 13.8
    MINOR_D    = 12.3
    SHAFT_H    = 10.0
    LEAD       = 2.8
    THREAD_H   = (MAJOR_D - MINOR_D) / 2   # 0.75 mm
    FLANK_DEG  = 30.0
    FLANK_RUN  = THREAD_H * tan(radians(FLANK_DEG))
    HALF_CREST = 0.08
    major_r    = MAJOR_D / 2

    with BuildPart() as bp:
        Cylinder(radius=major_r, height=SHAFT_H,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = bp.part

    def groove_solids(start_angle_deg: float) -> list:
        solids = []
        z0 = 0.05
        while z0 < SHAFT_H - 0.05:
            z1 = min(z0 + LEAD, SHAFT_H - 0.05)
            h  = z1 - z0
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

    all_grooves = groove_solids(0.0) + groove_solids(180.0)
    tool = all_grooves[0]
    for g in all_grooves[1:]:
        tool = tool.fuse(g)
    result = body - tool

    result.label = "male_thread_simple"
    return result

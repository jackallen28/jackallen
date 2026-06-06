"""
Dual-start metric thread test piece — male cast from toleranced female
  Flange:      OD=20mm, H=3mm, Z=0..3  (grip/reference surface)
  Shaft:       OD=14.4mm (major), H=12mm, Z=3..15
  Thread:      2-start RH, pitch=1.5mm, lead=3.0mm, 60 deg profile
               Major (crest) = 14.4mm  — fills female groove exactly
               Minor (root)  = 12.8mm  — fills female bore exactly
               Depth = 0.80mm, full shaft length
  Strategy:    per-turn is_frenet=True sweeps; two starts offset 180 deg
               Groove goes INWARD from major surface (depth at -THREAD_H)
"""

from build123d import *
from math import tan, radians, sin, cos, sqrt, pi


def gen_step():
    # ── Parameters ────────────────────────────────────────────────────────
    FLANGE_OD     = 20.0
    FLANGE_H      = 3.0
    MINOR_D       = 12.8   # = female bore — root fills female bore exactly
    MAJOR_D       = 14.4   # = female groove — crest fills female groove exactly
    SHAFT_H       = 12.0
    PITCH         = 1.5
    LEAD          = 3.0
    THREAD_H      = (MAJOR_D - MINOR_D) / 2   # 0.85 mm
    FLANK_DEG     = 30.0
    FLANK_RUN     = THREAD_H * tan(radians(FLANK_DEG))
    HALF_CREST    = 0.09
    major_r       = MAJOR_D / 2   # 7.1 mm
    SHAFT_Z0      = FLANGE_H
    SHAFT_Z1      = FLANGE_H + SHAFT_H

    # ── Body: flange + shaft ──────────────────────────────────────────────
    with BuildPart() as bp:
        # Flange
        Cylinder(radius=FLANGE_OD/2, height=FLANGE_H,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
        # Shaft at major (crest) diameter
        Cylinder(radius=major_r, height=SHAFT_H,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
                     Location((0, 0, FLANGE_H)))
    body = bp.part

    # ── Per-turn groove helper ────────────────────────────────────────────
    def groove_solids(start_angle_deg: float) -> list:
        solids = []
        z0 = SHAFT_Z0 + 0.05
        while z0 < SHAFT_Z1 - 0.05:
            z1 = min(z0 + LEAD, SHAFT_Z1 - 0.05)
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

            origin_pt = (major_r * cos(ang), major_r * sin(ang), z0)

            sweep_plane = Plane(
                origin=origin_pt,
                z_dir=(tx, ty, tz),
                x_dir=(0, 0, 1),
            )
            with BuildSketch(sweep_plane) as sk:
                Polygon(
                    [
                        ( HALF_CREST + FLANK_RUN,  0),
                        ( HALF_CREST,             -THREAD_H),   # inward
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

    # ── Fuse all grooves then single subtraction ──────────────────────────
    all_grooves = groove_solids(0.0) + groove_solids(180.0)
    tool = all_grooves[0]
    for g in all_grooves[1:]:
        tool = tool.fuse(g)
    result = body - tool

    result.label = "dual_start_thread_male_cast"
    return result

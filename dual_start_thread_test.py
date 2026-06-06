"""
Dual-start metric thread test piece (female/internal)
  Body:        OD=20mm, H=12mm, Z=0..12
  Bore:        ID=12.5mm through full height (minor diameter)
  Thread:      2-start RH, pitch=1.5mm, lead=3.0mm, 60 deg profile
               Major (groove bottom) = 14.2mm, minor (bore) = 12.5mm
               Depth = 0.85mm, thread length = 7mm (Z=2.5..9.5)
  Strategy:    per-turn is_frenet=True sweeps; two starts offset 180 deg
"""

from build123d import *
from math import tan, radians


def gen_step():
    # ── Parameters ────────────────────────────────────────────────────────
    OD            = 20.0
    HEIGHT        = 12.0
    MINOR_D       = 12.8       # bore dia (+0.2mm tolerance for shrinkage)
    MAJOR_D       = 14.4       # groove bottom dia (+0.2mm tolerance)
    PITCH         = 1.5        # distance between adjacent crests (one-start pitch)
    LEAD          = 3.0        # axial advance per revolution (2 × pitch)
    THREAD_H      = (MAJOR_D - MINOR_D) / 2   # 0.85 mm radial depth
    FLANK_DEG     = 30.0       # half-angle of 60-deg included metric profile
    FLANK_RUN     = THREAD_H * tan(radians(FLANK_DEG))   # 0.491 mm
    HALF_CREST    = 0.09       # small metric crest flat half-width
    THREAD_LEN    = HEIGHT - 0.1   # full bore, stop just before end faces
    THREAD_Z0     = 0.05           # start just after bottom face
    minor_r       = MINOR_D / 2   # 6.25 mm

    # ── Body: outer cylinder with through bore ────────────────────────────
    with BuildPart() as bp:
        Cylinder(radius=OD/2, height=HEIGHT,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
        Cylinder(radius=minor_r, height=HEIGHT,
                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                 mode=Mode.SUBTRACT)
    body = bp.part

    # ── Thread groove helper ──────────────────────────────────────────────
    def groove_solids(start_angle_deg: float) -> list:
        """Return one-turn groove solids for one thread start."""
        solids = []
        z0 = THREAD_Z0
        while z0 < THREAD_Z0 + THREAD_LEN:
            z1 = min(z0 + LEAD, THREAD_Z0 + THREAD_LEN)
            h  = z1 - z0
            if h < 0.05:
                break

            # Helix for this turn at the bore (minor) radius
            helix = Helix(
                pitch  = LEAD,       # per-start advance per revolution
                height = h,
                radius = minor_r,
            ).moved(Location((0, 0, z0), (0, 0, start_angle_deg)))

            # Profile plane: normal along +Y (helix tangent at start),
            # x along +Z.  With is_frenet=True the Frenet normal is radially
            # inward; +THREAD_H in profile-y goes OUTWARD into the bore wall.
            origin_pt = (
                minor_r * __import__('math').cos(radians(start_angle_deg)),
                minor_r * __import__('math').sin(radians(start_angle_deg)),
                z0,
            )
            # tangent direction at start of helix (approx +Y rotated by start_angle)
            tx = -__import__('math').sin(radians(start_angle_deg))
            ty =  __import__('math').cos(radians(start_angle_deg))
            tz = LEAD / (2 * __import__('math').pi * minor_r)

            import math
            mag = math.sqrt(tx*tx + ty*ty + tz*tz)
            tx /= mag; ty /= mag; tz /= mag

            sweep_plane = Plane(
                origin=origin_pt,
                z_dir=(tx, ty, tz),
                x_dir=(0, 0, 1),
            )
            with BuildSketch(sweep_plane) as sk:
                Polygon(
                    [
                        ( HALF_CREST + FLANK_RUN,  0),
                        ( HALF_CREST,              +THREAD_H),
                        (-HALF_CREST,              +THREAD_H),
                        (-(HALF_CREST + FLANK_RUN), 0),
                    ],
                    align=None,
                )
            g = sweep(sk.sketch, path=helix, is_frenet=True)
            if hasattr(g, 'volume') and g.volume > 0:
                solids.append(g)
            z0 += LEAD
        return solids

    # ── Collect grooves, fuse into one tool, single subtraction ──────────
    all_grooves = groove_solids(0.0) + groove_solids(180.0)
    # Fuse all groove solids into one compound tool before subtracting
    tool = all_grooves[0]
    for g in all_grooves[1:]:
        tool = tool.fuse(g)
    result = body - tool

    result.label = "dual_start_thread_test"
    return result

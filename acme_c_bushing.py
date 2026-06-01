"""
1-3/4 - 6 ACME-C Tapered Bushing
  Origin:    Z=0 at small (bottom) end face, axis along +Z
  Bottom OD: 33.4 mm  (major/crest diameter at small end)
  Top OD:    45.0 mm  (major/crest diameter at large end)
  Height:    64.0 mm
  Thread:    1-3/4 - 6 ACME-C external taper
             6 TPI, 29-deg included angle, depth = P/2
  Strategy:  frustum at major OD, conical helix groove subtracted inward
"""

from build123d import *
from math import tan, atan, radians, degrees


def gen_step():
    # ── Thread parameters ─────────────────────────────────────────────────
    TPI        = 6
    PITCH      = 25.4 / TPI          # 4.2333 mm
    THREAD_H   = PITCH / 2           # ACME depth = P/2 = 2.1167 mm
    FLANK_DEG  = 14.5                 # half-angle of 29-deg included
    HALF_CREST = PITCH * 0.3707 / 2  # ACME-C crest/root flat half-width
    FLANK_RUN  = THREAD_H * tan(radians(FLANK_DEG))

    # ── Body geometry ─────────────────────────────────────────────────────
    BOT_OD = 33.4          # major (crest) OD at small end
    TOP_OD = 45.0          # major (crest) OD at large end
    HEIGHT = 64.0
    bot_r  = BOT_OD / 2   # 16.7 mm
    top_r  = TOP_OD / 2   # 22.5 mm

    # Cone half-angle matching body taper
    cone_deg = degrees(atan((top_r - bot_r) / HEIGHT))   # ~5.18 deg

    # ── Frustum body at major (crest) diameter ────────────────────────────
    with BuildPart() as part:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                Line((0, 0),          (bot_r, 0))
                Line((bot_r, 0),      (top_r, HEIGHT))
                Line((top_r, HEIGHT), (0, HEIGHT))
                Line((0, HEIGHT),     (0, 0))
            make_face()
        revolve(axis=Axis.Z)

        # ── ACME groove: conical helix tracks the outer taper surface ─────
        # Groove is cut INWARD from the major-diameter surface
        helix_path = Helix(
            pitch      = PITCH,
            height     = HEIGHT,
            radius     = bot_r,
            cone_angle = cone_deg,
        )

        # Profile in plane normal to helix start (z_dir radially outward, x_dir along +Z)
        # Groove vertices: z=0 at surface, z=-THREAD_H into body
        sweep_plane = Plane(
            origin=(bot_r, 0, 0),
            z_dir=(1, 0, 0),
            x_dir=(0, 0, 1),
        )
        with BuildSketch(sweep_plane):
            Polygon(
                [
                    ( HALF_CREST + FLANK_RUN,  0),
                    ( HALF_CREST,              -THREAD_H),
                    (-HALF_CREST,              -THREAD_H),
                    (-(HALF_CREST + FLANK_RUN), 0),
                ],
                align=None,
            )
        sweep(path=helix_path, mode=Mode.SUBTRACT)

    part.part.label = "acme_c_bushing"
    return part.part

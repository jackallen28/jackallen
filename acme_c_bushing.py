"""
1-3/4 - 6 ACME-C Tapered Bushing
  Origin:    Z=0 at small (bottom) end, axis along +Z
  Bottom OD: 33.4 mm  (major/crest diameter at small end)
  Top OD:    45.0 mm  (major/crest diameter at large end)
  Height:    64.0 mm
  Thread:    1-3/4 - 6 ACME-C external taper
             6 TPI, 29-deg included angle, depth = P/2 = 2.117 mm
  Strategy:  per-turn Frenet sweeps on conical helix ensure radially-correct
             groove depth throughout the full tapered length
"""

from build123d import *
from math import tan, atan, radians, degrees


def gen_step():
    # ── Parameters ────────────────────────────────────────────────────────
    TPI        = 6
    PITCH      = 25.4 / TPI          # 4.2333 mm
    THREAD_H   = PITCH / 2           # ACME depth = P/2 = 2.1167 mm
    FLANK_DEG  = 14.5
    HALF_CREST = PITCH * 0.3707 / 2
    FLANK_RUN  = THREAD_H * tan(radians(FLANK_DEG))

    BOT_OD = 33.4;  TOP_OD = 45.0;  HEIGHT = 64.0
    bot_r  = BOT_OD / 2;  top_r = TOP_OD / 2
    cone_deg = degrees(atan((top_r - bot_r) / HEIGHT))

    # ── Frustum body at major (crest) OD ─────────────────────────────────
    with BuildPart() as fp:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                Line((0, 0),          (bot_r, 0))
                Line((bot_r, 0),      (top_r, HEIGHT))
                Line((top_r, HEIGHT), (0, HEIGHT))
                Line((0, HEIGHT),     (0, 0))
            make_face()
        revolve(axis=Axis.Z)
    body = fp.part

    # ── Per-turn Frenet groove sweeps ─────────────────────────────────────
    # Sweep each full turn individually so the Frenet frame stays correct.
    # Fixed-frame (default) sweep drifts radially over multiple turns.
    grooves = []
    z0 = 0.0
    while z0 < HEIGHT:
        z1  = min(z0 + PITCH, HEIGHT)
        h   = z1 - z0
        r0  = bot_r + (top_r - bot_r) * z0 / HEIGHT

        helix_i = Helix(
            pitch      = PITCH,
            height     = h,
            radius     = r0,
            cone_angle = cone_deg,
        ).moved(Location((0, 0, z0)))

        # Profile plane: normal along +Y (helix tangent at start), x along +Z
        # With is_frenet=True: profile y-dir → Frenet normal = radially inward ✓
        with BuildSketch(
            Plane(origin=(r0, 0, z0), z_dir=(0, 1, 0), x_dir=(0, 0, 1))
        ) as sk:
            Polygon(
                [
                    ( HALF_CREST + FLANK_RUN,  0),
                    ( HALF_CREST,             -THREAD_H),
                    (-HALF_CREST,             -THREAD_H),
                    (-(HALF_CREST + FLANK_RUN), 0),
                ],
                align=None,
            )
        g = sweep(sk.sketch, path=helix_i, is_frenet=True)
        if g.volume > 0:
            grooves.append(g)
        z0 += PITCH

    # Subtract all grooves from body
    result = body
    for g in grooves:
        result = result - g

    result.label = "acme_c_bushing"
    return result

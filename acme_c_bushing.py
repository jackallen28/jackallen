"""
1-3/4 - 6 ACME-C Tapered Bushing
  Bottom OD: 33.4 mm (small end, Z=0)
  Top OD:    45.0 mm (large end, Z=64)
  Height:    64.0 mm
  Thread:    1-3/4 - 6 ACME-C external taper, conical helix tracking the body taper
"""

from build123d import *
from math import tan, atan, radians, degrees

# ── Thread parameters ─────────────────────────────────────────────────────────
TPI        = 6
PITCH      = 25.4 / TPI          # 4.2333 mm
THREAD_H   = PITCH / 2           # ACME depth = P/2
FLANK_DEG  = 14.5                 # half included angle
HALF_CREST = PITCH * 0.3707 / 2  # flat at crest/root
FLANK_RUN  = THREAD_H * tan(radians(FLANK_DEG))

# ── Body geometry ─────────────────────────────────────────────────────────────
BOT_OD = 33.4
TOP_OD = 45.0
HEIGHT = 64.0
bot_r  = BOT_OD / 2   # 16.7 mm
top_r  = TOP_OD / 2   # 22.5 mm

# Cone angle of the body taper (half-angle from Z axis)
cone_angle_deg = degrees(atan((top_r - bot_r) / HEIGHT))   # ~5.18 deg

# ── Build part ────────────────────────────────────────────────────────────────
with BuildPart() as part:

    # Frustum: revolve trapezoidal profile around Z
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Line((0, 0),          (bot_r, 0))
            Line((bot_r, 0),      (top_r, HEIGHT))
            Line((top_r, HEIGHT), (0, HEIGHT))
            Line((0, HEIGHT),     (0, 0))
        make_face()
    revolve(axis=Axis.Z)

    # Conical helix: radius starts at bot_r and expands at the same taper angle
    # so the helix path tracks the outer surface of the frustum exactly
    helix_path = Helix(
        pitch      = PITCH,
        height     = HEIGHT,
        radius     = bot_r,
        cone_angle = cone_angle_deg,
    )

    # Tooth profile in plane normal to helix axis at the small end
    # x = along part Z axis, z = radially outward from body axis
    # Groove goes from z=0 (surface) to z=-THREAD_H (into body)
    sweep_plane = Plane(
        origin=(bot_r, 0, 0),
        z_dir=(1, 0, 0),
        x_dir=(0, 0, 1),
    )
    with BuildSketch(sweep_plane):
        Polygon(
            [
                ( HALF_CREST + FLANK_RUN,  0),
                ( HALF_CREST,             -THREAD_H),
                (-HALF_CREST,             -THREAD_H),
                (-(HALF_CREST + FLANK_RUN), 0),
            ],
            align=None,
        )
    sweep(path=helix_path, mode=Mode.SUBTRACT)

# ── Export STEP ───────────────────────────────────────────────────────────────
export_step(part.part, "acme_c_bushing.step")
export_stl(part.part,  "acme_c_bushing.stl")

bb = part.part.bounding_box()
print(f"Exported STEP + STL")
print(f"BBox:   {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} mm")
print(f"Volume: {part.part.volume:.1f} mm³  |  Turns: {HEIGHT/PITCH:.1f}")

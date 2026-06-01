"""
1-3/4 - 6 ACME-C Tapered Bushing
  Nominal thread: 1-3/4" = 44.45 mm major dia, 6 TPI, ACME-C (29 deg included)
  Body top OD:    33.4 mm
  Body bottom OD: 45.0 mm
  Height:         64.0 mm
  Taper:          body taper follows top/bottom OD; thread helix radius tracks taper
"""

from build123d import *
from math import tan, radians, pi

# ── Thread parameters ─────────────────────────────────────────────────────────
TPI        = 6
PITCH      = 25.4 / TPI          # 4.2333 mm
THREAD_H   = PITCH / 2           # ACME full depth = P/2 = 2.1167 mm
FLANK_DEG  = 14.5                 # half-angle (29 deg included / 2)
HALF_CREST = PITCH * 0.3707 / 2  # ACME-C crest flat ≈ 0.3707p per side

# ── Body geometry ─────────────────────────────────────────────────────────────
TOP_OD  = 33.4
BOT_OD  = 45.0
HEIGHT  = 64.0
top_r   = TOP_OD / 2
bot_r   = BOT_OD / 2

# Taper rate: change in radius per unit Z (positive = narrowing toward top)
taper_rate = (bot_r - top_r) / HEIGHT   # mm radius per mm height

# ── Frustum body ──────────────────────────────────────────────────────────────
with BuildPart() as part:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Line((0, 0),          (bot_r, 0))
            Line((bot_r, 0),      (top_r, HEIGHT))
            Line((top_r, HEIGHT), (0, HEIGHT))
            Line((0, HEIGHT),     (0, 0))
        make_face()
    revolve(axis=Axis.Z)

    # ── ACME-C tapered thread ─────────────────────────────────────────────────
    # Use the mean radius (mid-height) for the helix; the groove subtraction
    # will intersect the tapered body correctly.
    flank_run   = THREAD_H * tan(radians(FLANK_DEG))
    mean_r      = (top_r + bot_r) / 2   # 39.1 mm — helix reference radius

    helix_path  = Helix(pitch=PITCH, height=HEIGHT, radius=mean_r)

    # Tooth profile in a plane normal to X at mean_r
    sweep_plane = Plane(
        origin=(mean_r, 0, 0),
        z_dir=(1, 0, 0),
        x_dir=(0, 0, 1),
    )
    with BuildSketch(sweep_plane):
        Polygon(
            [
                (0,         -(HALF_CREST + flank_run)),
                (THREAD_H,  -HALF_CREST),
                (THREAD_H,   HALF_CREST),
                (0,          HALF_CREST + flank_run),
            ],
            align=None,
        )
    sweep(path=helix_path, mode=Mode.SUBTRACT)

# ── Export STEP ───────────────────────────────────────────────────────────────
output = "acme_c_bushing.step"
export_step(part.part, output)

bb = part.part.bounding_box()
n_threads = HEIGHT / PITCH
print(f"Exported:  {output}")
print(f"BBox:      {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} mm")
print(f"Volume:    {part.part.volume:.1f} mm³")
print(f"Pitch:     {PITCH:.4f} mm  ({TPI} TPI)")
print(f"Thread H:  {THREAD_H:.4f} mm")
print(f"Turns:     {n_threads:.1f}")

"""
1-3/4 - 6 ACME-C Tapered Bushing
  Body top OD:    45.0 mm  (large end, Z = HEIGHT)
  Body bottom OD: 33.4 mm  (small end, Z = 0)
  Height:         64.0 mm
  Thread:         1-3/4" - 6 ACME-C (TAPER), 29-deg included, on outer taper surface
"""

from build123d import *
from math import tan, radians

# ── Thread parameters ─────────────────────────────────────────────────────────
TPI        = 6
PITCH      = 25.4 / TPI          # 4.2333 mm
THREAD_H   = PITCH / 2           # ACME depth = P/2 = 2.1167 mm
FLANK_DEG  = 14.5                 # half-angle (29 deg included)
HALF_CREST = PITCH * 0.3707 / 2  # ACME-C crest flat

# ── Body geometry ─────────────────────────────────────────────────────────────
BOT_OD  = 33.4   # small end at Z = 0
TOP_OD  = 45.0   # large end at Z = HEIGHT
HEIGHT  = 64.0
bot_r   = BOT_OD / 2
top_r   = TOP_OD / 2
mean_r  = (bot_r + top_r) / 2

# ── Frustum (small end down, large end up) ────────────────────────────────────
with BuildPart() as part:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Line((0, 0),          (bot_r, 0))         # bottom face (small)
            Line((bot_r, 0),      (top_r, HEIGHT))     # tapered side
            Line((top_r, HEIGHT), (0, HEIGHT))         # top face (large)
            Line((0, HEIGHT),     (0, 0))              # axis
        make_face()
    revolve(axis=Axis.Z)

    # ── ACME-C tapered thread on outer surface ────────────────────────────────
    flank_run   = THREAD_H * tan(radians(FLANK_DEG))

    helix_path  = Helix(pitch=PITCH, height=HEIGHT, radius=mean_r)

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

# ── Export ────────────────────────────────────────────────────────────────────
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

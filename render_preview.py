"""
Normal-shaded render of acme_c_bushing.stl — makes thread flanks visible.
Uses trimesh ray casting + face normals for Phong shading.
"""

import numpy as np
from PIL import Image
import trimesh

mesh = trimesh.load("acme_c_bushing.stl")
print(f"Mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

# ── Camera / view setup ───────────────────────────────────────────────────────
# Slight isometric: rotate around Z then tilt down — shows thread spiral well
def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c,-s,0,0],[s,c,0,0],[0,0,1,0],[0,0,0,1]], float)

def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]], float)

T = rot_z(np.radians(40)) @ rot_x(np.radians(-70))
m = mesh.copy()
m.apply_transform(T)
m.fix_normals()

bb = m.bounds
cx = (bb[0,0]+bb[1,0])/2
cy = (bb[0,1]+bb[1,1])/2
extent = max(bb[1]-bb[0])

# ── Ray grid ──────────────────────────────────────────────────────────────────
W, H = 1000, 1200
pad = 6
x = np.linspace(bb[0,0]-pad, bb[1,0]+pad, W)
y = np.linspace(bb[0,1]-pad, bb[1,1]+pad, H)
xx, yy = np.meshgrid(x, y)
N = W * H
origins = np.c_[xx.ravel(), yy.ravel(), np.full(N, bb[1,2]+100)]
dirs    = np.tile([0, 0, -1.0], (N, 1))

# ── Intersect ─────────────────────────────────────────────────────────────────
from trimesh.ray.ray_triangle import RayMeshIntersector
inter   = RayMeshIntersector(m)
locs, idx_ray, idx_tri = inter.intersects_location(origins, dirs, multiple_hits=False)

# ── Phong shading ─────────────────────────────────────────────────────────────
BG     = np.array([30, 30, 35],    float)
METAL  = np.array([185, 188, 195], float)   # steel colour
LIGHT  = np.array([1.0, 0.8, 0.5])          # key light direction (normalised)
LIGHT /= np.linalg.norm(LIGHT)
FILL   = np.array([0.3, 0.4, 0.7])          # cool fill light
FILL  /= np.linalg.norm(FILL)

img = np.full((H, W, 3), BG, dtype=float)

if len(locs):
    normals = m.face_normals[idx_tri]          # (N_hits, 3)

    # diffuse
    d_key  = np.clip( normals @ LIGHT, 0, 1)
    d_fill = np.clip( normals @ FILL,  0, 1) * 0.25

    # specular (Blinn-Phong)
    view = np.array([0., 0., 1.])
    H_vec = (LIGHT + view); H_vec /= np.linalg.norm(H_vec)
    spec  = np.clip(normals @ H_vec, 0, 1) ** 60 * 0.7

    shading = 0.15 + 0.75*d_key + d_fill + spec   # ambient + diff + spec
    colours = np.clip(METAL[None,:] * shading[:,None], 0, 255)

    rows = idx_ray // W
    cols = idx_ray %  W
    img[rows, cols] = colours

img = img.astype(np.uint8)
Image.fromarray(img, 'RGB').save("acme_c_bushing_preview.png")
print("Saved acme_c_bushing_preview.png")

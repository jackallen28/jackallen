"""Photo-style colour renders of a USB LED Bar GLB (made by make_3d.py) with Blender Cycles.

usage: blender -b -P scripts/render_blender.py -- <model.glb> <out-dir> [samples] [resolution-%]

Renders: hero-usb-c.png, hero-logo.png, leds-on.png, top.png, bottom.png, usb-c-closeup.png
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1 :]
GLB, OUT = argv[0], argv[1]
SAMPLES = int(argv[2]) if len(argv) > 2 else 128
RES_PCT = int(argv[3]) if len(argv) > 3 else 100

# colours written by make_3d.py -> render materials
MATERIALS = {
    (0.72, 0.64, 0.42): ("fr4", dict(base=(0.42, 0.36, 0.20), rough=0.7)),
    (0.05, 0.33, 0.13): ("mask", dict(base=(0.010, 0.135, 0.040), rough=0.55, coat=0.08)),
    (0.12, 0.45, 0.18): ("mask_cu", dict(base=(0.025, 0.22, 0.065), rough=0.5, coat=0.08)),
    (0.80, 0.80, 0.78): ("hasl", dict(base=(0.86, 0.86, 0.84), metal=1.0, rough=0.22)),
    (0.97, 0.97, 0.97): ("silk", dict(base=(0.88, 0.88, 0.86), rough=0.6)),
    (0.10, 0.10, 0.10): ("res_body", dict(base=(0.018, 0.018, 0.018), rough=0.55)),
    (0.86, 0.86, 0.84): ("res_term", dict(base=(0.82, 0.82, 0.80), metal=1.0, rough=0.3)),
    (0.95, 0.95, 0.92): ("led_body", dict(base=(0.86, 0.86, 0.82), rough=0.35)),
    (1.00, 0.80, 0.40): ("led_phosphor", dict(base=(0.95, 0.40, 0.035), rough=0.15, coat=0.6)),
    (0.70, 0.70, 0.73): ("usb_shell", dict(base=(0.80, 0.80, 0.82), metal=1.0, rough=0.16)),
    (0.06, 0.06, 0.06): ("plastic_black", dict(base=(0.012, 0.012, 0.012), rough=0.45)),
    (0.85, 0.65, 0.20): ("gold", dict(base=(1.0, 0.71, 0.29), metal=1.0, rough=0.2)),
}
WARM_WHITE = (1.0, 0.62, 0.32)  # ~2900 K


def make_material(name, base, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.08
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

def srgb_to_linear(c):
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


# make_3d.py colours are sRGB; the GLB stores them linear, so match in linear space
lib = {key: make_material(name, **kw) for key, (name, kw) in MATERIALS.items()}
linear = {srgb_to_linear(k): k for k in lib}
for o in meshes:
    for slot in o.material_slots:
        if slot.material is None or not slot.material.use_nodes:
            continue
        bsdf = next((n for n in slot.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        c = tuple(bsdf.inputs["Base Color"].default_value[:3]) if bsdf else (0.5, 0.5, 0.5)
        key = min(linear, key=lambda k: sum((a - b) ** 2 for a, b in zip(k, c)))
        slot.material = lib[linear[key]]

# normalise: board 1.0 units long, origin at board centre, board top at z = thickness
pts = [o.matrix_world @ Vector(v) for o in meshes for v in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
S = 1.0 / (hi.x - lo.x)
rig = bpy.data.objects.new("rig", None)
bpy.context.scene.collection.objects.link(rig)
for o in meshes:
    if o.parent is None:
        o.parent = rig
for o in [o for o in bpy.context.scene.objects if o.parent is None and o is not rig]:
    o.parent = rig
centre = (lo + hi) / 2
rig_base = Matrix.Scale(S, 4) @ Matrix.Translation(-Vector((centre.x, centre.y, 0)))
rig.matrix_world = rig_base
MM = S * 1.0  # one millimetre in scene units if the GLB is in mm
if hi.x - lo.x < 1.0:  # GLB written in metres
    MM = S * 0.001
BOARD_W = (hi.y - lo.y) * S
Z_LOW = lo.z * S  # lowest point (shell legs under the board)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.use_denoising = False  # distro Blender builds may lack OpenImageDenoise; use samples + clamping
scene.cycles.adaptive_threshold = 0.01
scene.cycles.sample_clamp_indirect = 3.0
scene.cycles.blur_glossy = 1.0
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

world = bpy.data.worlds.new("studio")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
scene.world = world

floor_mat = make_material("floor", (0.30, 0.30, 0.31), 0.85)
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, Z_LOW - 0.0005))
floor = bpy.context.active_object
floor.data.materials.append(floor_mat)


def area_light(name, loc, target, size, energy, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.size, d.energy, d.color = size, energy, color
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


lights = [
    # key light above and behind the board so its reflection in the glossy mask points away from the camera
    area_light("key", (-0.2, 0.7, 1.3), (0, 0, 0), 1.4, 60),
    area_light("fill", (0.0, -1.4, 0.45), (0, 0, 0), 2.0, 12),
    area_light("rim", (1.1, 0.9, 0.5), (0, 0, 0), 1.0, 35),
]

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(loc, target):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def orbit(target, azimuth, elevation, dist):
    a, e = math.radians(azimuth), math.radians(elevation)
    t = Vector(target)
    aim(t + dist * Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))), t)


phosphor = lib[(1.00, 0.80, 0.40)]


# a small warm point light just above each LED so the glow spills onto the board and floor
glows = []
for o in meshes:
    if any(sl.material is phosphor for sl in o.material_slots):
        bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
        c = sum(bb, Vector()) / 8
        d = bpy.data.lights.new("glow", "POINT")
        d.color, d.shadow_soft_size = WARM_WHITE, 1.2 * MM
        g = bpy.data.objects.new("glow", d)
        scene.collection.objects.link(g)
        g.location = c + Vector((0, 0, 1.5 * MM))
        glows.append(g)


def leds(on):
    p = phosphor.node_tree.nodes["Principled BSDF"]
    p.inputs["Emission Color"].default_value = (*WARM_WHITE, 1)
    p.inputs["Emission Strength"].default_value = 60.0 if on else 0.0
    for g in glows:
        g.data.energy = 0.6 if on else 0.0


def compositor_glare(on):
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    comp = nt.nodes.new("CompositorNodeComposite")
    if on:
        g = nt.nodes.new("CompositorNodeGlare")
        g.glare_type, g.quality, g.threshold, g.size = "FOG_GLOW", "HIGH", 1.0, 8
        nt.links.new(rl.outputs["Image"], g.inputs["Image"])
        nt.links.new(g.outputs["Image"], comp.inputs["Image"])
    else:
        nt.links.new(rl.outputs["Image"], comp.inputs["Image"])


def studio(bright=True):
    bg.inputs["Color"].default_value = (0.45, 0.46, 0.48, 1) if bright else (0.004, 0.004, 0.005, 1)
    bg.inputs["Strength"].default_value = 0.3 if bright else 1.0
    floor_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        (0.30, 0.30, 0.31, 1) if bright else (0.03, 0.03, 0.035, 1)
    )
    for lt, e in zip(lights, (60, 12, 35)):
        lt.data.energy = e if bright else e * 0.04


def render(name, res, persp=True, lens=50, ortho=1.0):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = RES_PCT
    cam_data.type = "PERSP" if persp else "ORTHO"
    cam_data.lens = lens
    cam_data.ortho_scale = ortho
    cam_data.clip_start, cam_data.clip_end = 0.001, 100
    scene.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)


Z_HIGH = hi.z * S


def flip(bottom_up):
    """Turn the board over end-for-end (it then rests on the USB-C shell) for the underside shot."""
    if bottom_up:
        rig.matrix_world = Matrix.Translation((0, 0, Z_HIGH + 0.0005)) @ Matrix.Rotation(math.pi, 4, "Y") @ rig_base
        floor.location.z = 0
    else:
        rig.matrix_world = rig_base
        floor.location.z = Z_LOW - 0.0005


leds(False)
compositor_glare(False)
studio(True)

orbit((0.0, 0.0, 0.0), -32, 32, 1.8)
render("hero-usb-c", (1920, 1080), lens=55)

orbit((0.04, 0.0, 0.0), 30, 30, 1.8)
render("hero-logo", (1920, 1080), lens=55)

aim((0, 0, 3.0), (0, 0, 0))
render("top", (3200, 560), persp=False, ortho=1.04)

orbit((-0.44, 0.0, 0.01), -40, 24, 0.33)
render("usb-c-closeup", (1920, 1080), lens=60)

flip(True)
orbit((0.0, 0.0, 0.0), 25, 32, 1.8)
render("bottom", (1920, 1080), lens=55)
flip(False)

studio(False)
leds(True)
compositor_glare(True)
orbit((0.0, 0.0, 0.0), -24, 34, 1.75)
render("leds-on", (1920, 1080), lens=55)

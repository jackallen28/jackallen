import bpy, sys, math, mathutils
view = sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="board.glb")
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == "MESH"]
mn = mathutils.Vector((1e9,)*3); mx = mathutils.Vector((-1e9,)*3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector(map(min, mn, w)); mx = mathutils.Vector(map(max, mx, w))
ctr = (mn+mx)/2; size = mx-mn; L = size.x

def bsdf(m): return m.node_tree.nodes.get("Principled BSDF")
def near(c, t): return all(abs(a-b) < 0.03 for a, b in zip(c[:3], t))
def setm(m, color, rough=0.4, emit=None, strength=0.0, coat=0.0, metal=None):
    b = bsdf(m); b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if metal is not None: b.inputs["Metallic"].default_value = metal
    if coat: b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength

led5 = []
for o in meshes:
    for i, s in enumerate(o.material_slots):
        m = s.material; c = tuple(bsdf(m).inputs["Base Color"].default_value)
        if near(c, (0.08, 0.20, 0.14)):                 # solder mask -> purple
            s.material = m = m.copy(); setm(m, (0.15, 0.02, 0.28), 0.38, coat=0.25)
        elif near(c, (0.09, 0.42, 0.17)):               # 0603 LED body -> glowing blue
            s.material = m = m.copy(); setm(m, (0.1, 0.3, 1.0), 0.2, (0.15, 0.5, 1.0), 6.0)
        elif near(c, (0.45, 0.01, 0.0)):                # 5 mm LED
            led5.append((o, i))
        elif near(c, (0.78, 0.77, 0.63)) and 57/118 < ((o.matrix_world @ mathutils.Vector(o.bound_box[0])).x - mn.x) / size.x < 92/118:
            s.material = m = m.copy(); setm(m, (0.15, 0.35, 1.0), 0.15, (0.2, 0.55, 1.0), 8.0)   # matrix LED lens
        elif near(c, (0.71, 0.50, 0.21)):               # exposed copper/ENIG pads -> gold
            s.material = m = m.copy(); setm(m, (0.95, 0.72, 0.25), 0.25, metal=1.0)
# colour the three 5 mm LEDs by their position along the board's short axis
led5.sort(key=lambda t: t[0].matrix_world.translation.z)
for (o, i), col in zip(led5, [(0.05, 0.8, 0.1), (1.0, 0.45, 0.02), (0.9, 0.05, 0.03)]):
    m = o.material_slots[i].material.copy(); o.material_slots[i].material = m
    setm(m, col, 0.12, col, 1.2)


# ---------- stand-ins for parts the stock KiCad library has no 3D model for, + silkscreen
def kx(x): return mn.x + x/1000.0
def kz(y): return ctr.z - y/1000.0
top_y = min((o.matrix_world @ mathutils.Vector(c)).y for o in meshes for c in o.bound_box if o.material_slots and any(near(tuple(bsdf(sl.material).inputs["Base Color"].default_value), (0.15,0.02,0.28)) or near(tuple(bsdf(sl.material).inputs["Base Color"].default_value),(0.15,0.02,0.28)) for sl in o.material_slots))
def mat(name, color, rough=0.3, metal=0.0, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = bsdf(m)
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = 0.0
    return m
def box(x, y, w, d, h, m, z0=0.0):   # kicad mm: centre x,y; size w (x) d (y) h (up)
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.scale = (w/1000, h/1000, d/1000); o.location = (kx(x), top_y - (z0 + h/2)/1000, kz(y)); o.data.materials.append(m)
    return o
def cyl(x, y, r, h, m, z0=0.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=r/1000, depth=h/1000, vertices=48)
    o = bpy.context.active_object; o.rotation_euler = (math.pi/2, 0, 0); o.location = (kx(x), top_y - (z0 + h/2)/1000, kz(y)); o.data.materials.append(m); return o
steel = mat("steel", (0.42, 0.43, 0.46), 0.45, 0.85); blk = mat("blk", (0.01, 0.01, 0.012), 0.35); gold = mat("gold2", (0.62, 0.40, 0.08), 0.3, 1.0)
white = mat("silk", (0.95, 0.93, 0.98), 0.6)
box(17, 0, 3.3, 9.0, 3.2, steel); box(17, 0, 0.9, 7.0, 3.3, blk, 0.0)       # USB-C (vertical): metal shell + dark slot
for y in (-4.4, 4.4):                                                          # buttons
    box(36, y, 5.1, 5.1, 1.4, steel); cyl(36, y, 1.7, 0.7, blk, 1.4)
for y, w in ((3.5, 2.0), (1.0, 1.0), (-1.0, 1.0), (-3.5, 2.0)):               # USB-A gold fingers
    box(4.75, y, 7.5, w, 0.06, gold)
def text(s, x, y, size, rot=0, align="CENTER"):
    bpy.ops.object.text_add(); o = bpy.context.active_object; o.data.body = s; o.data.size = size/1000; o.data.extrude = 0.00004
    o.data.align_x = align; o.data.align_y = "CENTER"
    o.rotation_euler = (math.pi/2, -math.radians(rot), 0); o.location = (kx(x), top_y - 0.00006, kz(y)); o.data.materials.append(white)

text("USB-C", 17, 7, 1.0)
sys.path.insert(0, "/home/user/jackallen/hardware/circuitpath-keychain/tools")
import design as D
squares, lines = D.logo_shapes()
for x0, y0, x1, y1, filled in squares:                      # logo squares: solid or outlined, as on the silkscreen
    if filled:
        box((x0+x1)/2, (y0+y1)/2, x1-x0, y1-y0, 0.05, white)
    else:
        t = 0.12
        box((x0+x1)/2, y0, x1-x0, t, 0.05, white); box((x0+x1)/2, y1, x1-x0, t, 0.05, white)
        box(x0, (y0+y1)/2, t, y1-y0, 0.05, white); box(x1, (y0+y1)/2, t, y1-y0, 0.05, white)
for tt, xx in D.LOGO_TEXT:
    text(tt, xx, 0, 3.0, 90)
for tx, x, y, h, w in lines:
    text(tx, x, y, h, 90, "LEFT")

# buzzer stand-in on the back face (the stock library has no model for it): 9x9x1 body + brass diaphragm
bot_y = max((o.matrix_world @ mathutils.Vector(c)).y for o in meshes for c in o.bound_box if o.material_slots and any(near(tuple(bsdf(sl.material).inputs["Base Color"].default_value), (0.15,0.02,0.28)) for sl in o.material_slots))
brass = mat("brass", (0.55, 0.38, 0.1), 0.3, 1.0); plastic = mat("plastic", (0.03, 0.03, 0.035), 0.5)
bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.active_object
o.scale = (9/1000, 0.9/1000, 9/1000); o.location = (kx(98), bot_y + 0.45/1000, kz(0)); o.data.materials.append(plastic)
bpy.ops.mesh.primitive_cylinder_add(radius=3.7/1000, depth=0.12/1000, vertices=64); o = bpy.context.active_object
o.rotation_euler = (math.pi/2, 0, 0); o.location = (kx(98), bot_y + 0.95/1000, kz(0)); o.data.materials.append(brass)

scene.render.engine = "CYCLES"; scene.cycles.samples = 128; scene.cycles.use_denoising = False
scene.render.resolution_x, scene.render.resolution_y = 2000, 800
scene.view_settings.view_transform = "Standard"; scene.view_settings.exposure = -1.3
w = bpy.data.worlds.new("w"); scene.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.04, 0.04, 0.06, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.5
UP = mathutils.Vector((0, 1, 0))
side = -1 if view in ("top", "angle") else 1          # the board's top face looks toward -Y in this model
def look(loc, target, up):
    f = (target - loc).normalized(); r = f.cross(up).normalized(); u = r.cross(f)
    return mathutils.Matrix(((r.x, u.x, -f.x), (r.y, u.y, -f.y), (r.z, u.z, -f.z))).to_euler()
def light(loc, e, sz):
    d = bpy.data.lights.new("l", "AREA"); d.energy = e; d.size = sz
    o = bpy.data.objects.new("l", d); scene.collection.objects.link(o); o.location = loc
    o.rotation_euler = look(mathutils.Vector(loc), ctr, mathutils.Vector((0, 0, 1)))
light(ctr + UP*side*L*0.9 + mathutils.Vector((-L*0.3, 0, L*0.3)), L*L*11, L*0.7)
light(ctr + UP*side*L*0.7 + mathutils.Vector((L*0.5, 0, -L*0.2)), L*L*4, L*0.7)
cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cam); scene.collection.objects.link(co); scene.camera = co
if view in ("top", "back"):
    cam.type = "ORTHO"; cam.ortho_scale = L*1.12
    co.location = ctr + UP*side*L*2
    co.rotation_euler = look(co.location, ctr, mathutils.Vector((0, 0, 1)))
else:
    cam.lens = 70
    co.location = ctr + UP*side*L*0.62 + mathutils.Vector((-L*0.25, 0, L*0.75))
    co.rotation_euler = look(co.location, ctr, UP*side)
    scene.render.resolution_y = 1100
scene.render.filepath = f"//shot_{view}.png"
bpy.ops.render.render(write_still=True)

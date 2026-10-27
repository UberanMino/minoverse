"""Raphaels Traum – surreales Blender-Video (Cycles, prozedural).

Aufruf:  blender -b -P dream.py -- <segment> [test <frames...>]
         segment = 1..9 (siehe SEGS), test rendert nur einzelne Bilder als PNG.
Jedes Segment wird als eigene Bildfolge gerendert und danach per ffmpeg mit Überblendungen verbunden.
"""
import bpy, bmesh, math, os, sys, random
from math import sin, cos, pi, radians
from mathutils import Vector, Matrix, Euler

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["1"]
SEG = int(ARGV[0])
TEST = [int(a) for a in ARGV[2:]] if len(ARGV) > 1 and ARGV[1] == "test" else None
FPS = int(os.environ.get("DREAM_FPS", 12))
RES = (int(os.environ.get("DREAM_W", 540)), int(os.environ.get("DREAM_H", 960)))
SAMPLES = int(os.environ.get("DREAM_SAMPLES", 6))
OUT = os.environ.get("DREAM_OUT", "/home/claude/dream/frames")
XF = 0.75  # Überblendung in Sekunden (wird an jedes Segment außer dem letzten angehängt)

# Segmente: (Dauer s, Nebelfarbe, Nebelstart, Nebeltiefe)
SEGS = {
    1: (8.0, "#e9d3dc", 8, 45),    # 1. Stock: Rezeption, Fleischbuffet
    2: (7.0, "#e3d0dd", 8, 40),    # Aufzug ohne Knöpfe, hin und her
    3: (6.5, "#d9c7e6", 4, 30),    # zu steile Treppe
    4: (5.0, "#e6d6cf", 3, 14),    # Tablett mit zwei kleinen Pommes
    5: (5.5, "#e0cfe0", 12, 45),    # Aufzug kaputt, zum anderen Aufzug
    6: (11.0, "#2a2233", 6, 30),   # Aufzug zieht sich zusammen, Familie
    7: (11.5, "#8f9fd6", 10, 70),  # 6. Stock: fraktale Rolltreppen, Mitarbeiter
    8: (6.5, "#d8c3a5", 8, 40),    # 5. Stock: beiges Restaurant, Speisekarte
    9: (6.0, "#f3dcb4", 6, 34),    # Weg in den 3. Stock
}

SC = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
rnd = random.Random(7)

def hexc(h, a=1.0):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (a,)

def smooth(u):
    u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)

def seg_t(a, b, t):
    return smooth((t - a) / (b - a))

# ---------------------------------------------------------------- Materialien
_MATS = {}
def mat(col, rough=0.5, metal=0.0, emit=0.0, alpha=1.0, ecol=None, key=None):
    k = key or (col, rough, metal, emit, alpha, ecol)
    if k in _MATS: return _MATS[k]
    m = bpy.data.materials.new("m%d" % len(_MATS))
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexc(col)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = hexc(ecol or col)
        b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        try: m.surface_render_method = "BLENDED"
        except Exception: pass
    _MATS[k] = m
    return m

def checker_mat(c1, c2, scale, rough=0.25):
    m = bpy.data.materials.new("checker"); nt = m.node_tree
    b = nt.nodes["Principled BSDF"]; b.inputs["Roughness"].default_value = rough
    ck = nt.nodes.new("ShaderNodeTexChecker"); ck.inputs["Scale"].default_value = scale
    ck.inputs["Color1"].default_value = hexc(c1); ck.inputs["Color2"].default_value = hexc(c2)
    tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], ck.inputs["Vector"])
    nt.links.new(ck.outputs["Color"], b.inputs["Base Color"])
    return m

def wavy_mat(c1, c2, scale=2.0, rough=0.4, emit=0.0):
    """marmorierte, langsam „atmende“ Oberfläche (Wave-Textur, Phase per Treiber über die Zeit)"""
    m = bpy.data.materials.new("wavy"); nt = m.node_tree
    b = nt.nodes["Principled BSDF"]; b.inputs["Roughness"].default_value = rough
    w = nt.nodes.new("ShaderNodeTexWave"); w.inputs["Scale"].default_value = scale
    w.inputs["Distortion"].default_value = 6.0; w.inputs["Detail"].default_value = 2.0
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = hexc(c1); cr.color_ramp.elements[1].color = hexc(c2)
    nt.links.new(w.outputs["Fac"], cr.inputs["Fac"]); nt.links.new(cr.outputs["Color"], b.inputs["Base Color"])
    if emit:
        nt.links.new(cr.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emit
    fc = w.inputs["Phase Offset"].driver_add("default_value"); fc.driver.expression = "frame/30"
    return m

# ---------------------------------------------------------------- Geometrie
def _obj(name, bm, loc, rot, m, parent, scale=(1, 1, 1)):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o)
    if m: o.data.materials.append(m)
    o.parent = parent; o.location = loc; o.rotation_euler = rot; o.scale = scale
    return o

def box(size, loc=(0, 0, 0), m=None, parent=None, rot=(0, 0, 0), bevel=0.0, name="box"):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    o = _obj(name, bm, loc, rot, m, parent)
    if bevel:
        md = o.modifiers.new("bv", "BEVEL"); md.width = bevel; md.segments = 3
    return o

def cyl(r, h, loc=(0, 0, 0), m=None, parent=None, rot=(0, 0, 0), seg=24, r2=None, name="cyl"):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    o = _obj(name, bm, loc, rot, m, parent)
    for p in o.data.polygons: p.use_smooth = True
    return o

def sph(r, loc=(0, 0, 0), m=None, parent=None, scale=(1, 1, 1), rot=(0, 0, 0), seg=24, name="sph"):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    o = _obj(name, bm, loc, rot, m, parent, scale)
    for p in o.data.polygons: p.use_smooth = True
    return o

def empty(name="e", loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); SC.collection.objects.link(o)
    o.parent = parent; o.location = loc; o.rotation_euler = rot
    return o

def text(body, loc, size, m, parent=None, rot=(pi / 2, 0, 0), align="CENTER", ext=0.0, name="txt"):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = body; cu.size = size
    cu.align_x = align; cu.align_y = "CENTER"; cu.extrude = ext
    o = bpy.data.objects.new(name, cu); SC.collection.objects.link(o)
    o.data.materials.append(m); o.parent = parent; o.location = loc; o.rotation_euler = rot
    return o

def array(o, count, offset):
    md = o.modifiers.new("arr", "ARRAY"); md.count = count
    md.use_relative_offset = False; md.use_constant_offset = True; md.constant_offset_displace = offset
    return md

# ---------------------------------------------------------------- Figur (gesichtslose Traum-Puppe)
def person(name, loc, col, h=1.75, parent=None, cap=None, badge=False, tray=False):
    s = h / 1.75
    M = {"s": s}
    root = empty(name, loc, (0, 0, 0), parent); M["root"] = root
    skin = mat(col[0], 0.45); cloth = mat(col[1], 0.6); legc = mat(col[2], 0.6)
    hips = empty(name + "_hips", (0, 0, 0.95 * s), parent=root); M["hips"] = hips
    chest = empty(name + "_chest", (0, 0, 0), parent=hips); M["chest"] = chest
    cyl(0.19 * s, 0.62 * s, (0, 0, 0.33 * s), cloth, chest, r2=0.21 * s)
    sph(0.21 * s, (0, 0, 0.64 * s), cloth, chest, scale=(1, 0.75, 0.45))
    head = empty(name + "_head", (0, 0, 0.72 * s), parent=chest); M["head"] = head
    cyl(0.055 * s, 0.14 * s, (0, 0, 0.05 * s), skin, head)
    sph(0.13 * s, (0, 0, 0.22 * s), skin, head, scale=(0.9, 1.0, 1.18))
    if cap:
        cyl(0.13 * s, 0.07 * s, (0, 0, 0.36 * s), mat(cap, 0.5), head)
        box((0.14 * s, 0.2 * s, 0.015 * s), (0.11 * s, 0, 0.33 * s), mat(cap, 0.5), head)
    if badge:
        box((0.012, 0.09 * s, 0.05 * s), (0.2 * s, 0.07 * s, 0.48 * s), mat("#f2e7c9", 0.3, emit=0.3), chest)
    for side, key in ((1, "L"), (-1, "R")):
        sh = empty(name + "_arm" + key, (0, side * 0.25 * s, 0.6 * s), parent=chest); M["arm" + key] = sh
        cyl(0.05 * s, 0.62 * s, (0, 0, -0.3 * s), cloth, sh, r2=0.04 * s)
        sph(0.05 * s, (0, 0, -0.63 * s), skin, sh)
        lg = empty(name + "_leg" + key, (0, side * 0.1 * s, 0), parent=hips); M["leg" + key] = lg
        cyl(0.075 * s, 0.9 * s, (0, 0, -0.45 * s), legc, lg, r2=0.055 * s)
        box((0.24 * s, 0.1 * s, 0.07 * s), (0.06 * s, 0, -0.92 * s), mat("#2b2730", 0.5), lg, bevel=0.02)
    if tray:
        tr = empty(name + "_tray", (0.42 * s, 0, 0.32 * s), parent=chest); M["tray"] = tr
        box((0.42, 0.56, 0.025), (0, 0, 0), mat("#c9423f", 0.35), tr, bevel=0.01)
        for dy in (-0.12, 0.12): fries(tr, (0.02, dy, 0.012), 0.55)
    return M

def fries(parent, loc, sc=1.0):
    g = empty("fries", loc, (0, 0, rnd.uniform(-0.3, 0.3)), parent)
    red = mat("#d8281f", 0.45); yel = mat("#f4c542", 0.55)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.06 * sc, radius2=0.085 * sc, depth=0.11 * sc)
    _obj("frybox", bm, (0, 0, 0.055 * sc), (0, 0, pi / 4), red, g)
    for i in range(9):
        a = rnd.uniform(0, 2 * pi); r = rnd.uniform(0, 0.04) * sc
        box((0.012 * sc, 0.012 * sc, 0.12 * sc), (cos(a) * r, sin(a) * r, 0.12 * sc), yel, g,
            rot=(rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 0))
    return g

def pose(M, walk=0.0, phase=0.0, arms=None, lean=0.0, tray=False):
    a = sin(phase) * 0.55 * walk
    M["legL"].rotation_euler = (0, a, 0); M["legR"].rotation_euler = (0, -a, 0)
    M["hips"].location.z = (0.95 + 0.03 * abs(sin(phase)) * walk) * M["s"]
    M["chest"].rotation_euler = (0, lean, 0.08 * sin(phase) * walk)
    if tray:
        M["armL"].rotation_euler = (0.25, -1.25, 0); M["armR"].rotation_euler = (-0.25, -1.25, 0)
    elif arms:
        M["armL"].rotation_euler = arms[0]; M["armR"].rotation_euler = arms[1]
    else:
        M["armL"].rotation_euler = (0.08, -a * 0.8, 0); M["armR"].rotation_euler = (-0.08, a * 0.8, 0)

def place(M, p, yaw):
    M["root"].location = p; M["root"].rotation_euler = (0, 0, yaw)

def walk_path(M, pts, t, t0, t1, speed_phase=9.0, tray=False):
    """bewegt die Figur gleichmäßig über die Punkte pts (Vektoren) zwischen t0 und t1"""
    u = max(0.0, min(1.0, (t - t0) / (t1 - t0)))
    L = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]; tot = sum(L)
    d = u * tot; i = 0
    while i < len(L) - 1 and d > L[i]: d -= L[i]; i += 1
    p = pts[i].lerp(pts[i + 1], d / L[i] if L[i] else 0)
    dv = pts[i + 1] - pts[i]
    place(M, p, math.atan2(dv.y, dv.x))
    moving = 1.0 if 0 < u < 1 else 0.0
    pose(M, moving, t * speed_phase, tray=tray)
    return p

# ---------------------------------------------------------------- Kamera
CAM = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); SC.collection.objects.link(CAM); SC.camera = CAM
CAM.data.sensor_width = 36; CAM.data.clip_start = 0.05; CAM.data.clip_end = 600
CAM.data.dof.use_dof = True; CAM.data.dof.aperture_fstop = 2.2
FOCUS = empty("focus"); CAM.data.dof.focus_object = FOCUS

def catmull(keys, t, idx):
    if t <= keys[0][0]: return keys[0][idx]
    if t >= keys[-1][0]: return keys[-1][idx]
    i = 0
    while keys[i + 1][0] < t: i += 1
    p0 = keys[max(0, i - 1)][idx]; p1 = keys[i][idx]; p2 = keys[i + 1][idx]; p3 = keys[min(len(keys) - 1, i + 2)][idx]
    u = (t - keys[i][0]) / (keys[i + 1][0] - keys[i][0]); u = u * u * (3 - 2 * u) * 0.5 + u * 0.5
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3)

def camera(keys, t, roll=0.0, sway=1.0, focus=None):
    """keys: (t, pos, target, lens). Leichtes Schweben + Rollen für den Traum-Look."""
    K = [(k[0], Vector(k[1]), Vector(k[2]), float(k[3])) for k in keys]
    p = catmull(K, t, 1); g = catmull(K, t, 2); lens = catmull(K, t, 3)
    p = p + Vector((sin(t * 0.9) * 0.06, cos(t * 0.7) * 0.06, sin(t * 1.1) * 0.05)) * sway
    d = (g - p).normalized()
    q = d.to_track_quat("-Z", "Y")
    r = roll + sin(t * 0.6) * 0.035 * sway
    CAM.location = p
    CAM.rotation_euler = (q @ Matrix.Rotation(r, 4, "Z").to_quaternion()).to_euler()
    CAM.data.lens = lens
    FOCUS.location = focus if focus is not None else g

def bubble(body, loc, width, size=0.055, col="#fffaf0"):
    """Sprechblase im Kamerabild (Kind der Kamera, steht immer gerade)"""
    g = empty("bubble", loc, (0, 0, 0), CAM)
    lines = body.split("\n")
    h = size * (1.5 * len(lines) + 0.9)
    box((width, h, 0.004), (0, 0, 0), mat(col, 0.6, emit=0.9, ecol=col), g, bevel=0.025)
    text(body, (0, 0, 0.004), size, mat("#2a2230", 0.6), g, rot=(0, 0, 0))
    return g

def show(o, on):
    o.scale = (1, 1, 1) if on else (0.0001, 0.0001, 0.0001)

# ---------------------------------------------------------------- Welt / Licht / Look
def setup_world(fog_hex, top_hex, bottom_hex, strength=1.0):
    w = bpy.data.worlds.new("w"); SC.world = w; nt = w.node_tree
    bg = nt.nodes["Background"]; bg.inputs["Strength"].default_value = strength
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.35; cr.color_ramp.elements[0].color = hexc(bottom_hex)
    cr.color_ramp.elements[1].position = 0.75; cr.color_ramp.elements[1].color = hexc(top_hex)
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1; mr.inputs["From Max"].default_value = 1
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])  # Welt: Generated = Blickrichtung
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], cr.inputs["Fac"])
    nt.links.new(cr.outputs["Color"], bg.inputs["Color"])

def setup_render(fog_hex, mist_start, mist_depth):
    r = SC.render
    r.engine = "CYCLES"; SC.cycles.device = "CPU"
    SC.cycles.samples = SAMPLES; SC.cycles.use_denoising = True
    try: SC.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    SC.cycles.max_bounces = int(os.environ.get("DREAM_BOUNCES", 3)); SC.cycles.diffuse_bounces = 1; SC.cycles.glossy_bounces = 1
    SC.cycles.transmission_bounces = 4; SC.cycles.transparent_max_bounces = 8
    SC.cycles.use_adaptive_sampling = True; SC.cycles.adaptive_threshold = 0.05
    SC.cycles.blur_glossy = 1.0; SC.cycles.sample_clamp_indirect = 4.0
    r.use_persistent_data = True
    r.resolution_x, r.resolution_y = RES; r.resolution_percentage = 100
    r.fps = FPS
    SC.view_settings.view_transform = "AgX"
    try: SC.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    r.image_settings.file_format = "PNG"
    vl = SC.view_layers[0]; vl.use_pass_mist = True
    SC.world.mist_settings.start = mist_start; SC.world.mist_settings.depth = mist_depth
    SC.world.mist_settings.falloff = "QUADRATIC"
    if os.environ.get("DREAM_NOCOMP"): return
    ng = bpy.data.node_groups.new("comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N = ng.nodes; L = ng.links
    rl = N.new("CompositorNodeRLayers"); out = N.new("NodeGroupOutput")
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MIX"
    fog = list(hexc(fog_hex)); fog_lin = fog
    mix.inputs[7].default_value = fog_lin  # B (Farbe)
    mf = N.new("ShaderNodeMath"); mf.operation = "MULTIPLY"; mf.inputs[1].default_value = 0.92
    L.new(rl.outputs["Mist"], mf.inputs[0]); L.new(mf.outputs[0], mix.inputs[0])
    L.new(rl.outputs["Image"], mix.inputs[6])
    gl = N.new("CompositorNodeGlare")
    for nm, v in (("Type", "Bloom"), ("Threshold", 0.75), ("Strength", 0.9), ("Size", 0.75), ("Quality", "Medium")):
        try: gl.inputs[nm].default_value = v
        except Exception: pass
    hs = N.new("CompositorNodeHueSat"); hs.inputs["Saturation"].default_value = 0.88
    ld = N.new("CompositorNodeLensdist")
    for nm, v in (("Distortion", 0.06), ("Dispersion", 0.07), ("Fit", True)):
        try: ld.inputs[nm].default_value = v
        except Exception: pass
    L.new(mix.outputs[2], gl.inputs["Image"]); L.new(gl.outputs["Image"], hs.inputs["Image"])
    L.new(hs.outputs["Image"], ld.inputs["Image"]); L.new(ld.outputs["Image"], out.inputs[0])
    SC.compositing_node_group = ng
    try: r.compositor_device = "CPU"
    except Exception: pass

def area(loc, energy, size, col="#ffffff", rot=(0, 0, 0), shape="RECTANGLE"):
    l = bpy.data.lights.new("area", "AREA"); l.energy = energy; l.size = size; l.color = hexc(col)[:3]; l.shape = shape
    o = bpy.data.objects.new("area", l); SC.collection.objects.link(o); o.location = loc; o.rotation_euler = rot
    return o

def point(loc, energy, col="#ffffff", r=0.2):
    l = bpy.data.lights.new("pt", "POINT"); l.energy = energy; l.color = hexc(col)[:3]; l.shadow_soft_size = r
    o = bpy.data.objects.new("pt", l); SC.collection.objects.link(o); o.location = loc
    return o

def floaters(center, n, spread, mats, size=(0.1, 0.4)):
    """schwebende Kleinteile (Staub, Würfel, Kugeln), driften langsam"""
    out = []
    for i in range(n):
        p = Vector(center) + Vector((rnd.uniform(-1, 1) * spread[0], rnd.uniform(-1, 1) * spread[1], rnd.uniform(0, 1) * spread[2]))
        s = rnd.uniform(*size)
        if rnd.random() < 0.5: o = sph(s / 2, p, rnd.choice(mats), seg=12)
        else: o = box((s, s, s), p, rnd.choice(mats))
        out.append((o, p.copy(), rnd.uniform(0, 6.28), rnd.uniform(0.2, 0.6)))
    return out

def drift(fl, t):
    for o, p, ph, sp in fl:
        o.location = p + Vector((sin(t * sp + ph) * 0.3, cos(t * sp * 0.8 + ph) * 0.3, sin(t * sp * 1.3 + ph) * 0.4))
        o.rotation_euler = (t * sp, t * sp * 0.7 + ph, ph)

# =====================================================================================================
# SET A – 1. Stock: Rezeption, Fleischbuffet, Aufzug ohne Knöpfe, steile Treppe, zweiter Aufzug
# =====================================================================================================
def build_floor1():
    A = {}
    floor = box((160, 160, 0.2), (0, 0, -0.1), checker_mat("#f3e6e9", "#c9a9b7", 0.6, 0.18))
    wallm = wavy_mat("#efe1d6", "#dcc2c9", 0.6, 0.6)
    box((46, 0.5, 7.5), (-9, 8.25, 3.75), wallm)                       # Rückwand
    box((0.5, 30, 7.5), (14.25, -6, 3.75), wallm)                       # rechte Wand
    # Säulen, die oben im Nebel verschwinden
    colm = mat("#f6eef0", 0.35)
    for x in range(-40, 41, 9):
        for y in range(-40, 6, 9):
            if abs(x) < 14 and -10 < y < 6: continue
            cyl(0.55, 60, (x + 2, y, 30), colm, seg=20)
    # riesige „1“
    text("1", (-3, 7.98, 5.8), 3.2, mat("#7b4b8f", 0.4, emit=0.6), ext=0.1)
    # --- Aufzug 1 (keine Knöpfe)
    frame = mat("#b8a7b2", 0.25, metal=0.85)
    box((2.6, 0.3, 3.2), (-3, 7.9, 1.6), frame)
    A["e1L"] = box((0.98, 0.08, 2.6), (-3.5, 7.72, 1.3), mat("#d9cdd3", 0.18, metal=0.9))
    A["e1R"] = box((0.98, 0.08, 2.6), (-2.5, 7.72, 1.3), mat("#d9cdd3", 0.18, metal=0.9))
    box((2.0, 0.06, 2.7), (-3, 7.82, 1.35), mat("#1b141f", 0.6))      # Kabine dahinter (dunkel)
    A["panel"] = box((0.32, 0.06, 0.7), (-1.25, 7.98 - 0.04, 1.35), mat("#cfc2c8", 0.2, metal=0.8), bevel=0.02)
    A["ghosts"] = [cyl(0.05, 0.02, (-1.25, 7.9, 1.6 - i * 0.17), mat("#ffffff", 0.3, emit=1.5, alpha=0.6),
                       rot=(pi / 2, 0, 0)) for i in range(4)]
    A["oob"] = text("AUSSER BETRIEB", (-3, 7.6, 3.75), 0.55, mat("#ff2a1f", 0.4, emit=12.0))
    # --- Aufzug 2 weit links, leuchtend
    box((2.6, 0.3, 3.2), (-20, 7.9, 1.6), frame)
    A["e2L"] = box((0.98, 0.08, 2.6), (-20.5, 7.72, 1.3), mat("#d9cdd3", 0.18, metal=0.9))
    A["e2R"] = box((0.98, 0.08, 2.6), (-19.5, 7.72, 1.3), mat("#d9cdd3", 0.18, metal=0.9))
    box((2.0, 0.06, 2.7), (-20, 7.86, 1.35), mat("#fff3d0", 0.5, emit=6.0))
    text("2", (-20, 7.72, 3.55), 0.5, mat("#fff3d0", 0.4, emit=3.0))
    A["arrows"] = []
    for i in range(10):
        a = text(">", (-4.5 - i * 1.5, 6.0, 0.02), 1.1, mat("#ffcf6e", 0.4, emit=4.0), rot=(0, 0, pi))
        A["arrows"].append(a)
    # --- steile Treppe (≈70°) neben Aufzug 1, führt in den Nebel
    stm = mat("#e7d7dc", 0.5)
    st = box((1.8, 0.2, 0.45), (4.0, 2.0, 0.225), stm)
    array(st, 34, (0, 0.2, 0.45))
    box((0.12, 7.2, 15.6), (5.02, 5.4, 7.6), mat("#cdb4c1", 0.5), rot=(radians(0), 0, 0))
    rail = cyl(0.03, 16.3, (3.05, 5.4, 8.1), mat("#5a3e66", 0.3, metal=0.6), rot=(-radians(66), 0, 0))
    # --- Rezeption
    desk = mat("#a77b8f", 0.3)
    box((6.5, 1.2, 1.15), (8.5, -3.5, 0.575), desk, bevel=0.08)
    box((6.7, 1.4, 0.08), (8.5, -3.5, 1.19), mat("#f5ebe6", 0.15), bevel=0.02)
    text("REZEPTION", (8.5, -4.22, 0.62), 0.42, mat("#fff2c8", 0.4, emit=2.5))
    cyl(0.12, 0.08, (7.0, -3.4, 1.27), mat("#e3c27a", 0.15, metal=1.0))
    sph(0.07, (7.0, -3.4, 1.31), mat("#e3c27a", 0.15, metal=1.0), scale=(1, 1, 0.6))
    # Uhr ohne Zeiger
    A["clock"] = empty("clock", (8.5, -2.9, 4.2), (pi / 2, 0, 0))
    cyl(0.9, 0.08, (0, 0, 0), mat("#fbf6ef", 0.3), A["clock"], seg=40)
    cyl(0.95, 0.06, (0, 0, -0.01), mat("#7b4b8f", 0.3), A["clock"], seg=40)
    # --- Fleischbuffet
    tbl = mat("#f8f1ee", 0.3)
    box((6.0, 1.4, 0.08), (-0.5, -4.5, 0.95), tbl, bevel=0.02)
    box((6.0, 1.42, 0.7), (-0.5, -4.5, 0.55), mat("#8c4f6b", 0.5))
    text("HEUTE: FLEISCH", (-0.5, -5.25, 0.6), 0.3, mat("#fff2c8", 0.4, emit=2.0))
    A["meat"] = []
    meat = mat("#8b2b1e", 0.22); meat2 = mat("#a8442a", 0.25); fat = mat("#f2e2cf", 0.3); bone = mat("#efe4d2", 0.4)
    sausage = mat("#b0503a", 0.18)
    for i in range(14):
        x = -3.2 + i * 0.42 + rnd.uniform(-0.08, 0.08); y = -4.5 + rnd.uniform(-0.4, 0.4)
        g = empty("meat", (x, y, 1.05), (0, 0, rnd.uniform(0, 6.28)))
        k = i % 4
        if k == 0:   # Keule
            sph(0.16, (0, 0, 0.1), meat2, g, scale=(1.3, 1, 0.9)); cyl(0.035, 0.3, (0.27, 0, 0.12), bone, g, rot=(0, pi / 2, 0))
            sph(0.05, (0.42, 0, 0.12), bone, g)
        elif k == 1:  # Steak
            sph(0.22, (0, 0, 0.04), meat, g, scale=(1.2, 0.9, 0.18)); sph(0.235, (0, 0, 0.035), fat, g, scale=(1.2, 0.9, 0.14))
        elif k == 2:  # Würstchen
            for j in range(3):
                cyl(0.05, 0.36, (0, (j - 1) * 0.11, 0.06), sausage, g, rot=(0, pi / 2, 0))
        else:         # Schinken / Braten
            sph(0.2, (0, 0, 0.14), meat2, g, scale=(1.1, 0.9, 0.85)); sph(0.12, (0.15, 0, 0.18), fat, g, scale=(0.5, 0.9, 0.8))
        A["meat"].append((g, g.location.copy(), rnd.uniform(0, 6.28)))
    # riesiges schwebendes Hähnchen über dem Buffet
    A["bigmeat"] = empty("bigmeat", (-0.5, -4.5, 3.8))
    sph(0.9, (0, 0, 0), meat2, A["bigmeat"], scale=(1.3, 1, 0.85))
    for s in (-1, 1):
        cyl(0.12, 1.0, (0.9, s * 0.45, 0.2), meat2, A["bigmeat"], rot=(0, pi / 2 - 0.3, 0))
        sph(0.15, (1.45, s * 0.45, 0.37), bone, A["bigmeat"])
    # Licht
    area((0, -2, 9), 2500, 18, "#fff0f4", rot=(0, 0, 0))
    area((-10, 4, 7), 900, 10, "#e7d4ff")
    point((-0.5, -4.5, 2.4), 120, "#ffb27a", 0.5)
    A["fl"] = floaters((-3, 0, 1.5), 26, (14, 9, 6), [mat("#ffffff", 0.3, emit=1.2), mat("#d8b6ff", 0.4), mat("#ffd2b0", 0.4)], (0.06, 0.3))
    return A

def anim_floor1(A, t, seg):
    if seg != 5: show(A["oob"], False)
    drift(A["fl"], t)
    for g, p, ph in A["meat"]:
        s = 1 + 0.08 * sin(t * 2.2 + ph)
        g.scale = (s, s, s); g.location = p + Vector((0, 0, 0.04 * sin(t * 1.3 + ph)))
    A["bigmeat"].rotation_euler = (0.2 * sin(t * 0.5), 0.1, t * 0.35)
    A["bigmeat"].location.z = 3.8 + 0.25 * sin(t * 0.8)
    A["clock"].rotation_euler = (pi / 2, 0, 0.15 * sin(t * 0.4))

# =====================================================================================================
# SET B – Aufzugskabine, die sich zusammenzieht (Kamera hinter der für sie unsichtbaren Rückwand)
# =====================================================================================================
BX = 200.0
def build_cabin():
    B = {}
    root = empty("cabin", (BX, 0, 0)); B["root"] = root
    wall = wavy_mat("#6d5a4a", "#9c8166", 1.4, 0.35)
    B["L"] = box((0.12, 3.0, 3.0), (-1.3, 0, 1.5), wall, root)
    B["R"] = box((0.12, 3.0, 3.0), (1.3, 0, 1.5), wall, root)
    B["C"] = box((2.8, 3.0, 0.12), (0, 0, 2.9), mat("#3a2f36", 0.5), root)
    B["lamp"] = box((1.6, 1.6, 0.03), (0, 0, -0.07), mat("#fff1d6", 0.4, emit=5.0), B["C"])
    box((6, 6, 0.1), (0, 0, -0.05), mat("#3b2b2b", 0.4), root)
    B["back"] = box((2.8, 0.12, 3.0), (0, -1.6, 1.5), wall, root)
    B["back"].visible_camera = False
    # Frontwand mit Türen
    fr = mat("#9b8f94", 0.25, metal=0.8)
    box((3.4, 0.14, 0.5), (0, 1.55, 2.75), fr, root)
    for s in (-1, 1): box((0.75, 0.14, 3.0), (s * 1.2, 1.55, 1.5), fr, root)
    B["dL"] = box((0.86, 0.06, 2.5), (-0.43, 1.5, 1.25), mat("#c8bdc3", 0.2, metal=0.9), root)
    B["dR"] = box((0.86, 0.06, 2.5), (0.43, 1.5, 1.25), mat("#c8bdc3", 0.2, metal=0.9), root)
    B["disp"] = text("1", (0, 1.47, 2.75), 0.32, mat("#ff9a3c", 0.4, emit=6.0), root, rot=(pi / 2, 0, pi))
    # Flur vor der Tür (Zwischenhalt): türkis, endlos
    hall = empty("hall", (0, 4.5, 0), parent=root); B["hall"] = hall
    box((6, 6, 0.1), (0, 0, -0.04), checker_mat("#bfe3dc", "#7fb3ab", 1.2), hall)
    box((6, 0.2, 4), (0, 3.0, 2), mat("#9fd1c8", 0.5), hall)
    area((BX, 5.0, 3.5), 400, 3, "#cff7ee")
    B["fam"] = [person("vater", (-0.45, 5.6, 0), ("#e8cfc0", "#4f6b8a", "#2f3a4a"), 1.85, root),
                person("mutter", (0.45, 5.6, 0), ("#e8cfc0", "#9a5a7a", "#3a2e3a"), 1.7, root),
                person("kind", (0.0, 5.2, 0), ("#efd6c6", "#e3b440", "#4a4a6a"), 1.1, root)]
    B["me"] = person("me", (0, 0, 0), ("#e9e2f2", "#b9b0d9", "#6a6390"), 1.75, root, tray=True)
    area((BX, 0, 2.6), 160, 1.2, "#ffe9c9", rot=(0, 0, 0))
    return B

# =====================================================================================================
# SET C – 6. Stock: fraktale, steile Rolltreppen ohne Ziel
# =====================================================================================================
CX = 400.0
def escalator(parent, start, yaw, pitch, L, steps_list, body_m, step_m, glass_m, rail_m):
    e = empty("esc", start, (0, pitch, yaw), parent)
    box((L, 1.3, 0.35), (L / 2, 0, -0.32), body_m, e)
    for s in (-1, 1):
        box((L, 0.05, 0.9), (L / 2, s * 0.62, 0.35), glass_m, e)
        box((L, 0.09, 0.08), (L / 2, s * 0.62, 0.84), rail_m, e)
    # waagerechte Stufen: Stufe gegen die Neigung gedreht, Array-Versatz im Stufen-Raum
    sl = 0.42
    st = box((sl * 0.92, 1.1, 0.18), (0, 0, -0.08), step_m, e, rot=(0, -pitch, 0))
    off = Matrix.Rotation(-pitch, 3, "Y").inverted() @ Vector((sl, 0, 0))
    array(st, max(2, int(L / sl) - 1), off)
    steps_list.append((st, Vector((0, 0, -0.08)), Vector((sl, 0, 0)), rnd.choice((1, -1))))
    return e

def build_floor6():
    C = {}
    col = bpy.data.collections.new("fractal"); SC.collection.children.link(col)
    root = empty("f6", (0, 0, 0)); C["root"] = root
    body_m = mat("#3b3f6e", 0.35, metal=0.5); step_m = mat("#c7c9d9", 0.3, metal=0.9)
    glass_m = mat("#bfe9ff", 0.1, emit=0.8, alpha=0.35); rail_m = mat("#1c1a2b", 0.3)
    land_m = mat("#e9e3f5", 0.4)
    steps = []; chain = []
    def grow(p, yaw, depth, L, main):
        down = main or depth % 2 == 0 or rnd.random() < 0.7
        pitch = rnd.uniform(0.85, 1.05) * (1 if down else -1)
        e = escalator(root, p, yaw, pitch, L, steps, body_m, step_m, glass_m, rail_m)
        d = Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "Y") @ Vector((1, 0, 0))
        end = Vector(p) + d * L
        cyl(1.1, 0.3, end + Vector((0, 0, -0.35)), land_m, root, seg=8)
        if main: chain.append(end.copy())
        if depth <= 0: return
        n = 3 if depth >= 3 else 2
        for i in range(n):
            ny = yaw + (i - (n - 1) / 2) * rnd.uniform(1.3, 1.9) + rnd.uniform(-0.2, 0.2)
            grow(end + Vector((0, 0, 0)), ny, depth - 1, L * rnd.uniform(0.68, 0.8), main and i == 0)
    start = Vector((0, 0, 0)); chain.append(start.copy())
    cyl(2.2, 0.4, (0, 0, -0.4), land_m, root, seg=8)
    rnd.seed(11)
    grow(start, 0.3, 4, 13.0, True)
    for k, yaw in enumerate((2.4, 4.2)):
        grow(start, yaw, 2, 10.0, False)
    # alles in eine Sammlung → kleinere/größere Instanzen als Selbstähnlichkeit im Nebel
    def move(o):
        for c in o.users_collection: c.objects.unlink(o)
        col.objects.link(o)
        for ch in o.children: move(ch)
    move(root)
    real = bpy.data.objects.new("f6_real", None); SC.collection.objects.link(real)
    real.instance_type = "COLLECTION"; real.instance_collection = col; real.location = (CX, 0, 0)
    # Original-Sammlung selbst nicht direkt rendern (nur über Instanzen)
    bpy.context.view_layer.layer_collection.children[col.name].exclude = True
    C["inst"] = []
    for (s, off, rz) in ((3.2, (-60, 70, -40), 1.2), (7.0, (90, 160, -160), 2.6), (0.35, (6, -6, 4), 0.7), (2.0, (40, -60, 30), 4.0), (5.0, (-150, 40, 110), 0.2)):
        ins = bpy.data.objects.new("f6_inst", None); SC.collection.objects.link(ins)
        ins.instance_type = "COLLECTION"; ins.instance_collection = col
        ins.location = Vector((CX, 0, 0)) + Vector(off); ins.scale = (s, s, s); ins.rotation_euler = (0.3 * rz % 0.6, 0, rz)
        C["inst"].append((ins, rz))
    C["real"] = real
    C["steps"] = steps; C["chain"] = [Vector((CX, 0, 0)) + c for c in chain]
    text("6", (CX - 4, 6, 6), 4.0, mat("#ffe08a", 0.4, emit=3.0), rot=(pi / 2, 0, pi * 0.85), ext=0.15)
    C["me"] = person("me6", (CX, 0, 0), ("#e9e2f2", "#b9b0d9", "#6a6390"), 1.75, tray=True)
    p1 = C["chain"][1]
    C["worker"] = person("worker", (CX, 0, 0), ("#e3c8b6", "#2f6b52", "#1f2b28"), 1.8, cap="#2f6b52", badge=True)
    area((CX, 0, 30), 6000, 40, "#e8e4ff")
    point((CX + 4, 3, 6), 600, "#ffd9a0", 1.0)
    C["fl"] = floaters((CX, 0, -20), 40, (40, 40, 40), [mat("#ffffff", 0.3, emit=2.0), mat("#ffe08a", 0.3, emit=1.0)], (0.1, 0.5))
    return C

# =====================================================================================================
# SET D – 5. Stock: beiges Restaurant mit riesiger Speisekarte, Weg in den 3. Stock
# =====================================================================================================
DX = 600.0
def build_floor5():
    D = {}
    o = Vector((DX, 0, 0))
    beige = wavy_mat("#d9c3a2", "#c4a983", 0.8, 0.6)
    brown = mat("#6b4a33", 0.45); seat = mat("#8a5d3d", 0.5); tab = mat("#e7d6b8", 0.35)
    box((120, 120, 0.2), o + Vector((0, 0, -0.1)), mat("#7a5a41", 0.35))
    box((0.4, 80, 6), o + Vector((-9, 20, 3)), beige)
    box((0.4, 80, 6), o + Vector((9, 20, 3)), beige)
    box((18, 80, 0.3), o + Vector((0, 20, 6.1)), mat("#cbb391", 0.7))
    # Sitzreihen (leer), wiederholen sich in den Nebel
    for row in range(14):
        y = 4 + row * 3.2
        for x in (-5.5, 5.5):
            box((2.2, 1.0, 0.08), o + Vector((x, y, 0.78)), tab, bevel=0.03)
            cyl(0.08, 0.74, o + Vector((x, y, 0.37)), brown)
            for dy in (-1, 1):
                box((2.4, 0.55, 0.45), o + Vector((x, y + dy * 0.95, 0.225)), seat, bevel=0.05)
                box((2.4, 0.2, 1.3), o + Vector((x, y + dy * 1.28, 0.65)), seat, bevel=0.05)
            sph(0.28, o + Vector((x, y, 2.6)), mat("#ffdca0", 0.4, emit=8.0), seg=16)
            cyl(0.01, 3.2, o + Vector((x, y, 4.3)), brown, seg=6)
    text("5", o + Vector((0, 46, 4.0)), 3.0, mat("#5b3b25", 0.4), ext=0.1)
    # riesige Speisekarte am Eingang
    D["menu"] = g = empty("menu", o + Vector((0, 1.2, 0)))
    box((6.4, 0.2, 7.6), (0, 0, 3.8), mat("#3b2a1e", 0.4), g, bevel=0.06)
    box((6.0, 0.05, 7.2), (0, -0.12, 3.8), mat("#f3e6cc", 0.7), g)
    ink = mat("#3a2716", 0.6); red = mat("#a3261c", 0.5)
    text("SPEISEKARTE", (0, -0.16, 6.85), 0.6, ink, g)
    text("5. Stock", (0, -0.16, 6.25), 0.3, ink, g)
    items = [("Beige Suppe", "46,90 €"), ("Lauwarmes Schnitzel", "89,00 €"), ("Ein Salatblatt", "31,50 €"),
             ("Brot von gestern", "22,00 €"), ("2 kleine Pommes", "54,00 €"), ("Braune Soße pur", "38,70 €"),
             ("Leitungswasser", "19,99 €"), ("Tagesgericht", "??? €")]
    for i, (n, p) in enumerate(items):
        z = 5.5 - i * 0.62
        text(n, (-2.65, -0.16, z), 0.3, ink, g, align="LEFT")
        text("·  ·  ·  ·  ·", (0.85, -0.16, z), 0.22, ink, g)
        text(p, (2.65, -0.16, z), 0.3, red, g, align="RIGHT")
    text("Bitte warten, Sie werden nicht platziert.", (0, -0.16, 0.45), 0.17, ink, g)
    point(o + Vector((0, -2.5, 6.0)), 500, "#ffe2b0", 1.0)
    # Weg zum 3. Stock: Durchgang in der linken Wand mit Treppe nach unten, warmes Licht
    D["door"] = d = empty("door3", o + Vector((-8.75, -4.0, 0)), (0, 0, -pi / 2))
    box((2.6, 0.6, 3.4), (0, 0, 1.7), mat("#fff1c9", 0.5, emit=9.0), d)
    text("3", (0, -0.4, 4.1), 0.9, mat("#ffcf6e", 0.4, emit=6.0), d)
    text("↓", (0.9, -0.4, 4.1), 0.7, mat("#ffcf6e", 0.4, emit=6.0), d)
    D["glow"] = point(o + Vector((-8.0, -4.0, 1.8)), 300, "#ffd28a", 0.8)
    area(o + Vector((0, 10, 5.8)), 1500, 12, "#ffe7c4", rot=(0, 0, 0))
    D["me"] = person("me5", o, ("#e9e2f2", "#b9b0d9", "#6a6390"), 1.75, tray=True)
    D["fl"] = floaters(o + Vector((0, 8, 1)), 22, (7, 14, 4), [mat("#fff1c9", 0.3, emit=2.0), mat("#c4a983", 0.5)], (0.05, 0.2))
    return D

# =====================================================================================================
# Segmente
# =====================================================================================================
fog = SEGS[SEG][1]
if SEG in (1, 2, 3, 4, 5):
    setup_world(fog, "#f7e3ee", "#d9c6e8", 0.9)
    A = build_floor1()
    me = person("me", (0, 0, 0), ("#e9e2f2", "#b9b0d9", "#6a6390"), 1.75, tray=True)
elif SEG == 6:
    setup_world(fog, "#3a2e44", "#1a1420", 0.3)
    B = build_cabin()
elif SEG == 7:
    setup_world(fog, "#c9d3ff", "#3b3a7a", 1.0)
    C = build_floor6()
else:
    setup_world(fog, "#f1dcb8", "#b99a76", 0.8)
    D = build_floor5()
setup_render(fog, SEGS[SEG][2], SEGS[SEG][3])

def frame_tray(M, on):
    show(M["tray"], on)

def per_frame(t):
    V = Vector
    if SEG == 1:
        anim_floor1(A, t, 1)
        frame_tray(me, False)
        p = walk_path(me, [V((7, -8, 0)), V((3.5, -6.6, 0)), V((1.0, -6.4, 0))], t, 1.5, 5.0)
        if t > 5.0:   # dreht sich angewidert weg
            u = seg_t(5.0, 6.2, t)
            place(me, p, math.atan2(-6.4 + 6.6, 1.0 - 3.5) + pi * 0.5 * u + pi * 0.0)
            pose(me, 0, 0, arms=((0.2, -0.3 - 1.6 * u, 0.4 * u), (-0.2, -0.3 - 1.6 * u, -0.4 * u)), lean=-0.25 * u)
            me["head"].rotation_euler = (0, -0.2 * u, 0.6 * u)
        camera([(0, (12, -16, 2.2), (5, -4, 1.6), 30), (3.5, (6, -12.5, 1.8), (0, -4.6, 1.4), 32),
                (6.0, (2.5, -10.5, 1.5), (0.0, -5.4, 1.4), 38), (8.8, (0.5, -9.5, 1.6), (0.5, -5.4, 1.5), 40)], t,
               focus=me["root"].location + V((0, 0, 1.4)) if t > 3.5 else None)
    elif SEG == 2:
        anim_floor1(A, t, 2)
        frame_tray(me, False)
        for o in A["ghosts"]:
            m = 0.5 + 0.5 * sin(t * 3 + o.location.z * 10); o.scale = (m, m, 1)
        E = V((-3, 6.6, 0)); S = V((4, 1.0, 0))
        legs = [E, S, E, S, E]; n = len(legs) - 1; seg_d = 6.6 / n
        k = min(n - 1, int(t / seg_d)); lt = t - k * seg_d
        a, b = legs[k], legs[k + 1]
        u = smooth(min(1, lt / (seg_d * 0.8)))
        place(me, a.lerp(b, u), math.atan2((b - a).y, (b - a).x))
        pose(me, 1.0 if u < 1 else 0.0, t * 11)
        if u >= 1: me["head"].rotation_euler = (0, 0, 0.6 * sin(t * 5))
        else: me["head"].rotation_euler = (0, 0, 0)
        # Geister-Doppelgänger: dieselbe Figur, zeitversetzt (Traum-Echo) – über Kopien
        for gi, gh in enumerate(GHOSTS):
            tt = max(0, t - 0.35 * (gi + 1)); kk = min(n - 1, int(tt / seg_d)); ll = tt - kk * seg_d
            aa, bb = legs[kk], legs[kk + 1]; uu = smooth(min(1, ll / (seg_d * 0.8)))
            place(gh, aa.lerp(bb, uu), math.atan2((bb - aa).y, (bb - aa).x)); pose(gh, 1.0 if uu < 1 else 0, tt * 11)
            show(gh["tray"], False)
        camera([(0, (0.5, -3.4, 2.7), (0.6, 5, 1.6), 16), (7.6, (0.5, -2.2, 2.4), (0.6, 5, 1.6), 17)], t,
               focus=me["root"].location + V((0, 0, 1.2)))
    elif SEG == 3:
        anim_floor1(A, t, 3)
        frame_tray(me, False)
        # klettert die Treppe hoch (Stufe 0.45 hoch, 0.2 tief), rutscht bei ~4 s fast ab
        if t < 3.6: h = smooth(t / 3.6) * 2.7
        elif t < 4.6: h = 2.7 - 2.2 * smooth((t - 3.6) / 0.5)
        else: h = 0.5 - 0.5 * smooth((t - 4.6) / 0.8)
        y = 2.0 + h / 0.45 * 0.2
        place(me, V((4.0, y - 0.15, h)), pi / 2)
        if t < 3.6:
            pose(me, 1.0, t * 7, arms=((0.1, -2.2 - 0.5 * sin(t * 7), 0), (-0.1, -2.2 + 0.5 * sin(t * 7), 0)), lean=0.45)
        elif t < 4.6:
            w = (t - 3.6) / 1.0
            pose(me, 0, 0, arms=((0.3, -2.8 + w, 0.8), (-0.3, -2.8 + w, -0.8)), lean=-0.5)
            me["root"].rotation_euler = (0, -0.35 * sin(w * pi), pi / 2)
        else:
            pose(me, 0, 0, arms=((0.2, -0.4, 0.3), (-0.2, -0.4, -0.3)), lean=-0.1)
        camera([(0, (1.5, -1.5, 0.4), (4.0, 6, 5.5), 18), (3.4, (1.2, -0.5, 0.5), (4.0, 6, 6.0), 18),
                (4.0, (1.8, -0.8, 0.9), (4.0, 3.2, 2.0), 20), (7.2, (2.0, -1.8, 1.4), (4.0, 2.0, 1.0), 24)], t,
               roll=0.25 + 0.12 * sin(t * 0.7), focus=me["root"].location + V((0, 0, 1.2)))
    elif SEG == 4:
        anim_floor1(A, t, 4)
        frame_tray(me, True)
        place(me, V((1.5, 1.0, 0)), pi / 2 + 0.3)
        pose(me, 0, 0, tray=True); me["chest"].rotation_euler = (0, 0.12, 0)
        me["head"].rotation_euler = (0, 0.45, 0)
        # das Tablett wird größer, die Pommes bleiben winzig (Traumlogik)
        s = 1.0 + 1.6 * seg_t(0.5, 4.5, t)
        me["tray"].scale = (s, s, 1)
        for ch in me["tray"].children:
            if ch.name.startswith("fries"): ch.scale = (1 / s, 1 / s, 1)
        bpy.context.view_layer.update()
        tp = me["tray"].matrix_world.translation.copy()
        yaw = pi / 2 + 0.3; f = V((cos(yaw), sin(yaw), 0)); sd = V((-sin(yaw), cos(yaw), 0))
        camera([(0, tp + f * 1.1 + sd * -0.6 + V((0, 0, 0.75)), tp + V((0, 0, 0.15)), 30),
                (2.5, tp + f * 1.2 + V((0, 0, 0.55)), tp + V((0, 0, 0.25)), 30),
                (5.8, tp + f * 1.0 + sd * 0.7 + V((0, 0, 0.9)), tp + V((0, 0, 0.1)), 34)], t, focus=tp)
    elif SEG == 5:
        anim_floor1(A, t, 5)
        frame_tray(me, True)
        blink = 1 if (t * 2.5) % 1 < 0.7 else 0
        show(A["oob"], blink and t > 0.3)
        for i, a in enumerate(A["arrows"]):
            on = ((t * 6 - i) % 10) < 3
            show(a, on)
        walk_path(me, [V((-2.5, 6.3, 0)), V((-6, 5.6, 0)), V((-19.8, 5.8, 0))], t, 1.2, 5.6, tray=True)
        if t > 3.2:
            u = seg_t(3.2, 4.5, t)
            A["e2L"].location.x = -20.5 - 0.95 * u; A["e2R"].location.x = -19.5 + 0.95 * u
        mp = me["root"].location.copy()
        camera([(0, (-1.2, 1.8, 1.9), (-3, 7.6, 2.6), 24), (1.4, (-1.2, 1.8, 1.9), (-3.5, 6.5, 2.0), 24),
                (3.0, (-5.5, 1.2, 1.7), (-12, 6.0, 1.0), 22), (6.3, (-14.5, 2.8, 1.7), (-20, 7.5, 1.5), 24)], t,
               focus=mp + V((0, 0, 1.3)))
    elif SEG == 6:
        R = B["root"]; me6 = B["me"]
        # Phasen: 0–1 Tür zu; 1–4 Fahrt, Wände ziehen sich fast bis zum Erdrücken zusammen; 4–5.2 Halt, Wände zurück,
        # Tür auf; 5.2–7 Familie steigt ein; 7–8 Tür zu; 8–10.5 Wände ziehen sich zusammen, gerade so passend
        squeeze1 = seg_t(1.0, 3.8, t) * (1 - seg_t(4.0, 4.8, t))
        squeeze2 = seg_t(7.8, 10.0, t)
        wx = 1.3 - 0.95 * squeeze1 - 0.25 * squeeze2    # halbe Breite
        cz = 2.9 - 0.8 * squeeze1 - 0.15 * squeeze2
        by = -1.6 + 0.9 * squeeze1 + 0.35 * squeeze2
        jit = 0.015 * sin(t * 37) * (squeeze1 + squeeze2)
        B["L"].location.x = -wx - jit; B["R"].location.x = wx + jit
        B["C"].location.z = cz; B["back"].location.y = by
        doors = seg_t(4.4, 5.0, t) * (1 - seg_t(7.0, 7.7, t))
        B["dL"].location.x = -0.43 - 0.85 * doors; B["dR"].location.x = 0.43 + 0.85 * doors
        floors = ["1", "1", "2", "3", "3", "?", "4", "4", "4", "4", "5", "5", "6"]
        B["disp"].data.body = floors[min(len(floors) - 1, int(t / 0.85))] if t < 4.2 or t > 8.2 else "4"
        # ich: in der Mitte, wird gequetscht (Arme an den Körper, leicht geduckt), danach nach hinten
        my = 0.0 - 0.5 * seg_t(5.0, 6.0, t)
        place(me6, V((0, my, 0)), pi / 2)
        pose(me6, 0, 0, tray=True)
        hunch = squeeze1 * 0.35
        me6["chest"].rotation_euler = (0, hunch, 0); me6["head"].rotation_euler = (0, hunch * 0.6, 0.4 * sin(t * 1.5) * squeeze1)
        me6["root"].scale = (1, 1 - 0.25 * squeeze1, 1 - 0.18 * squeeze1)
        # Familie
        for i, f in enumerate(B["fam"]):
            x0 = (-0.45, 0.45, 0.0)[i]; tgt = (V((-0.55, 0.55, 0)), V((0.55, 0.5, 0)), V((0.0, 0.85, 0)))[i]
            st = V((x0, 5.6 if i < 2 else 5.2, 0))
            u = seg_t(5.2 + i * 0.2, 6.9 + i * 0.2, t)
            p = st.lerp(tgt, u)
            yaw = -pi / 2 if u < 0.98 else (-pi / 2 + pi * seg_t(6.9, 7.6, t))
            place(f, p, yaw); pose(f, 1.0 if 0 < u < 1 else 0, t * 9)
            f["root"].scale = (1, 1 - 0.12 * squeeze2, 1 - 0.06 * squeeze2)
        show(B["hall"], doors > 0.01)
        camera([(0, (BX, -3.2, 2.2), (BX, 1.0, 1.3), 18), (3.8, (BX, -2.4, 1.6), (BX, 1.0, 1.2), 18),
                (5.0, (BX, -2.8, 1.8), (BX, 3.0, 1.3), 20), (8.0, (BX, -3.0, 1.9), (BX, 1.0, 1.3), 19),
                (11.5, (BX, -2.4, 1.7), (BX, 1.0, 1.2), 18)], t, sway=0.6 + squeeze1,
               focus=V((BX, 0.2, 1.3)))
    elif SEG == 7:
        drift(C["fl"], t)
        for st, base, sv, dr in C["steps"]:
            st.location = base + sv * ((t * 0.9 * dr) % 1.0)
        for ins, rz in C["inst"]:
            ins.rotation_euler.z = rz + t * 0.03
        me7 = C["me"]; ch = C["chain"]; wk = C["worker"]
        show(me7["tray"], True)
        top = ch[0] + V((0, 0, -0.2))
        place(wk, top + V((0.2, 1.3, 0)), -pi / 2 - 0.4)
        talk = 1.0 if 5.6 < t < 7.8 else 0.0
        pose(wk, 0, 0, arms=((0.1, 0.1, 0), (-0.3, -0.6 - 0.6 * talk - 0.25 * talk * sin(t * 7), -0.5)))
        mp0 = top + V((-0.9, -0.2, 0))
        if t < 2.2:
            u = seg_t(0, 2.2, t); place(me7, mp0 + V((-2.0 * (1 - u), -0.3 * (1 - u), 0)), 0.4)
            pose(me7, 1.0 if u < 1 else 0, t * 9, tray=True)
        elif t < 7.9:
            place(me7, mp0, 0.75); pose(me7, 0, 0, tray=True)
            me7["head"].rotation_euler = (0, -0.1, 0.12 * sin(t * 0.8))
        else:
            u = seg_t(7.9, 11.5, t)
            pts = [mp0, ch[0] + V((0.3, 0.1, 0)), ch[1], ch[2]]
            Ls = [(pts[i + 1] - pts[i]).length for i in range(3)]; d = u * sum(Ls); i = 0
            while i < 2 and d > Ls[i]: d -= Ls[i]; i += 1
            a, b = pts[i], pts[i + 1]
            place(me7, a.lerp(b, d / Ls[i]), math.atan2((b - a).y, (b - a).x))
            pose(me7, 1.0, t * 12, tray=True, lean=-0.4 if i else 0)
            me7["root"].rotation_euler.x = 0.12 * sin(t * 8)
        show(Q1, 3.0 < t < 5.4); show(Q2, 5.6 < t < 7.9)
        mp = me7["root"].location.copy()
        CO = CAMOFF7
        mid = top + V((-0.35, 0.55, 1.15))
        keys = [(0, top + CO[0], top + V((0, 0, -2)), 24), (2.4, mid + CO[1], mid, 30),
                (7.6, mid + CO[1] * 0.8, mid, 30), (9.6, ch[1] + CO[2], ch[0].lerp(ch[1], 0.7), 28),
                (12.3, ch[2] + CO[3], ch[2] + V((0, 0, -2)), 22)]
        camera(keys, t, focus=mp + V((0, 0, 1.2)), roll=0.1 * sin(t * 0.4))
    elif SEG == 8:
        drift(D["fl"], t)
        me5 = D["me"]; o = V((DX, 0, 0)); show(me5["tray"], True)
        walk_path(me5, [o + V((2.5, -9, 0)), o + V((0.4, -3.4, 0))], t, 0.0, 2.6, tray=True)
        if t > 2.6:
            u = seg_t(2.6, 3.4, t)
            place(me5, o + V((0.4, -3.4, 0)), math.atan2(5.6, -2.1) * (1 - u) + (pi / 2) * u)
            pose(me5, 0, 0, tray=True)
            me5["head"].rotation_euler = (0, -0.45 * u, 0.25 * sin(t * 0.9) * seg_t(4.5, 5.0, t))
        D["menu"].scale = (1, 1, 1 + 0.06 * seg_t(1.5, 6.5, t))
        camera([(0, o + V((4.5, -13, 1.4)), o + V((0.5, 1, 3.4)), 24), (3.0, o + V((2.0, -8.0, 0.9)), o + V((0, 1, 4.0)), 24),
                (7.2, o + V((1.2, -6.4, 0.6)), o + V((0, 1, 4.6)), 22)], t, focus=o + V((0, 1.0, 3.5)) if t > 2.5 else None)
    elif SEG == 9:
        drift(D["fl"], t)
        me5 = D["me"]; o = V((DX, 0, 0)); show(me5["tray"], True)
        walk_path(me5, [o + V((0.4, -3.4, 0)), o + V((-3, -4.0, 0)), o + V((-8.6, -4.0, 0)), o + V((-10.5, -4.0, -0.6))], t, 0.4, 5.6, tray=True)
        D["glow"].data.energy = 300 + 1600 * seg_t(2.5, 6, t)
        camera([(0, o + V((3.5, -7.5, 1.6)), o + V((-2, -3.6, 1.2)), 26), (3.0, o + V((-1.5, -6.6, 1.6)), o + V((-8, -4, 1.4)), 28),
                (6.0, o + V((-5.5, -5.2, 1.5)), o + V((-10, -4, 1.3)), 30)], t, focus=me5["root"].location + V((0, 0, 1.2)))

# Zusatzobjekte, die per_frame braucht
GHOSTS = []
if SEG == 2:
    gm = ("#ffffff", "#d7cff5", "#a79fd1")
    for i in range(2):
        g = person("ghost%d" % i, (0, 0, 0), gm, 1.75, tray=True)
        a = mat("#e4dcff", 0.5, emit=0.6, alpha=0.28 - 0.1 * i, key="ghost%d" % i)
        for ob in bpy.data.objects:
            if ob.name.startswith("ghost%d" % i) and ob.type == "MESH":
                ob.data.materials.clear(); ob.data.materials.append(a)
        GHOSTS.append(g)
Q1 = Q2 = None
_v = [float(x) for x in os.environ.get("DREAM_C7", "-16 -18 12 3.6 -2.6 0.5 -2 -4 15 -8 -12 26").split()]
CAMOFF7 = [Vector(_v[i:i + 3]) for i in range(0, 12, 3)]
if SEG == 7:
    Q1 = bubble("Warum sind die Rolltreppen\nso steil und so komisch?", (-0.06, -0.3, -1.6), 0.82, 0.042)
    Q2 = bubble("Das muss so sein.\nWegen der Konstruktion des Hauses.", (0.04, 0.32, -1.6), 0.9, 0.042, "#e6fff2")

DUR = SEGS[SEG][0] + (XF if SEG != max(SEGS) else 0.0)
NF = int(round(DUR * FPS))
SC.frame_start = 1; SC.frame_end = NF

def handler(scene, *_):
    per_frame((scene.frame_current - 1) / FPS)
bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(handler)

os.makedirs(OUT, exist_ok=True)
if TEST is not None:
    for f in TEST:
        SC.frame_set(f)
        SC.render.filepath = os.path.join(OUT, "test_s%d_f%04d.png" % (SEG, f))
        bpy.ops.render.render(write_still=True)
else:
    SC.render.filepath = os.path.join(OUT, "s%d" % SEG, "f")
    bpy.ops.render.render(animation=True)

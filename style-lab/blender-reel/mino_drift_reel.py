"""MINO DRIFT – Runde 8 der Blender-Reels für den Minoverse: zurück zu den Welten aus Büro v2/v3 und Office v2/v3, aber mit
dem Weltall-Büro als Anker und der ruhigen Dat-Swag-Kamera (Einstellung je ~4 Schläge, Bounce zum Beat). Mino Man und
Chicken Guy gleiten durch Riesen-Screens von Welt zu Welt: Hot-Dog-Fabrik, Pepsi-Meer zum Surfen, Screen-Tunnel,
Himmel mit Hot-Dog-Regen, Büro-Cameo. Mehr Swag (Polka-Anzug, Sonnenbrille, Bandana, Goldketten), viele Easter Eggs
(UFO, fliegender Toaster, Gummiente, Banner-Rakete, Pepsi-Oma-Rakete, Hot-Dog-Tänzer) und knalligere Farben.

Varianten (--variant oder "variant" in den Params):
  1 DRIFT            Weltall -> Fabrik -> Tunnel -> Pepsi-Surf -> Weltall-Party
  2 ORBIT SURF       Surfen durchs All, Fallschirmsprung in den Hot-Dog-Regen, Büro-Party, Tunnel, Weltall-Party
  3 HOT DOG HUSTLE   Weltall -> Tunnel -> Fabrik -> Ritt auf dem Riesen-Hot-Dog -> Pepsi -> Screen-Wand mit Chicken-Guy-Mosaik

  blender -b --factory-startup --python mino_drift_reel.py -- --params params_drift_v1.json --clips <abs>/clips --cghead <abs>/cghead --fast --pngdir out/drift_v1
  Optionen wie mino_office_reel.py (--still, --frames, --res, --engine, --samples, --nocomp, --exposure, --portrait)
  Farbkorrektur: --sat (1.3) --value (1.04) --bright (2) --contrast (14); weich z. B. --sat 1.15 --value 1.0 --contrast 4 --exposure 0.05
"""
import json
import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ Optionen
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None, flag=False):
    if name in argv:
        if flag:
            return True
        return argv[argv.index(name) + 1]
    return default


P = {"bpm": 150.0, "song_offset_s": 0.0, "drop_beat": 16, "beats": 48, "variant": 1}
if opt("--params") and os.path.exists(opt("--params")):
    P.update(json.load(open(opt("--params"))))
BPM = float(P["bpm"])
BEAT = 60.0 / BPM
NB = int(P["beats"])
DROP = int(P["drop_beat"])
VARIANT = int(opt("--variant", P.get("variant", 1)))
FPS = int(opt("--fps", 30))
RES = [int(v) for v in opt("--res", "540x960").split("x")]
DUR = NB * BEAT
NFRAMES = int(round(DUR * FPS))
ENGINE = opt("--engine", "EEVEE").upper()
SAMPLES = int(opt("--samples", 32 if ENGINE == "EEVEE" else 16))   # TAA 32 wie bei Dat Swag
FONT_DIR = os.path.join(HERE, "fonts")
rnd = random.Random(7)


def B(b):
    return b * BEAT


# ------------------------------------------------------------------ Hilfen
def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_inout(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def beat_of(t):
    return t / BEAT


def pulse(t, decay=0.18, every=1.0, start=0.0, end=1e9):
    """1 auf jedem Schlag (every in Schlägen), klingt mit decay (Sekunden) ab."""
    if t < B(start) or t > B(end):
        return 0.0
    ph = ((t - B(start)) % B(every))
    return math.exp(-ph / decay)


def hsh(i):
    x = math.sin(i * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return (c[0], c[1], c[2], a)


# ------------------------------------------------------------------ Szene leeren
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.fps = FPS
scn.frame_start = 1
scn.frame_end = NFRAMES
scn.render.resolution_x, scn.render.resolution_y = RES
scn.render.resolution_percentage = 100
scn.render.use_lock_interface = True

# ------------------------------------------------------------------ Materialien
MATS = {}


def node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def bsdf_input(b, *names):
    for n in names:
        if n in b.inputs:
            return b.inputs[n]
    return None


def mat(name, color, rough=0.5, metal=0.0, emit=None, estr=0.0, sss=0.0, coat=0.0, spec=0.5):
    key = name
    if key in MATS:
        return MATS[key]
    m, nt, out = node_mat(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = hexcol(color) if isinstance(color, str) else color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        bsdf_input(b, "Emission Color", "Emission").default_value = hexcol(emit) if isinstance(emit, str) else emit
        bsdf_input(b, "Emission Strength").default_value = estr
    if sss:
        i = bsdf_input(b, "Subsurface Weight", "Subsurface")
        if i:
            i.default_value = sss
        r = bsdf_input(b, "Subsurface Radius")
        if r:
            r.default_value = (0.9, 0.35, 0.2)
        s = bsdf_input(b, "Subsurface Scale")
        if s:
            s.default_value = 0.03
    if coat:
        i = bsdf_input(b, "Coat Weight", "Clearcoat")
        if i:
            i.default_value = coat
    i = bsdf_input(b, "Specular IOR Level", "Specular")
    if i:
        i.default_value = spec
    nt.links.new(b.outputs[0], out.inputs[0])
    MATS[key] = m
    return m


def emit_mat(name, color, strength=3.0):
    if name in MATS:
        return MATS[name]
    m, nt, out = node_mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = hexcol(color) if isinstance(color, str) else color
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0])
    MATS[name] = m
    return m


def noise_mat(name, c0, c1, scale=8.0, rough=0.5, bump=0.3, c2=None, detail=6.0, sss=0.0):
    """Prozedurale Oberfläche: Farbverlauf über Noise, plus Bump."""
    if name in MATS:
        return MATS[name]
    m, nt, out = node_mat(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = rough
    if sss:
        i = bsdf_input(b, "Subsurface Weight", "Subsurface")
        if i:
            i.default_value = sss
        s = bsdf_input(b, "Subsurface Scale")
        if s:
            s.default_value = 0.03
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.35, hexcol(c0)
    els[1].position, els[1].color = 0.7, hexcol(c1)
    if c2:
        e = els.new(0.85)
        e.color = hexcol(c2)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs[0], out.inputs[0])
    MATS[name] = m
    return m


# ------------------------------------------------------------------ Geometrie
COLL = scn.collection


def link(ob, parent=None):
    COLL.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    e.rotation_euler = rot
    e.empty_display_size = 0.1
    return link(e, parent)


_PRIM = {}


def _prim_mesh(kind, seg):
    """Grundform einmal per bpy.ops erzeugen und danach nur noch kopieren (bpy.ops wird mit vielen Objekten sehr langsam)."""
    key = (kind, seg)
    if key not in _PRIM:
        if kind == "cube":
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=seg, ring_count=max(8, seg // 2))
        elif kind == "ico":
            bpy.ops.mesh.primitive_ico_sphere_add(radius=0.5, subdivisions=2)
        elif kind == "cyl":
            bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, vertices=seg)
        elif kind == "cone":
            bpy.ops.mesh.primitive_cone_add(radius1=0.5, radius2=0.0, depth=1, vertices=seg)
        elif kind == "torus":
            bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.1, major_segments=seg, minor_segments=10)
        elif kind == "plane":
            bpy.ops.mesh.primitive_plane_add(size=1)
        tmp = bpy.context.active_object
        me = tmp.data
        me.use_fake_user = True
        bpy.data.objects.remove(tmp, do_unlink=True)
        _PRIM[key] = me
    return _PRIM[key].copy()


def prim(kind, name, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), m=None, parent=None, smooth_=True,
         bevel=0.0, subsurf=0, seg=24):
    me = _prim_mesh(kind, seg)
    me.use_fake_user = False
    me.materials.clear()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    # aus der Standard-Collection in unsere verschieben ist unnötig: use_empty -> Szene-Collection
    ob.location = loc
    ob.scale = scale
    ob.rotation_euler = rot
    if m is not None:
        ob.data.materials.append(m)
    if smooth_ and kind not in ("cube", "plane"):
        for p in ob.data.polygons:
            p.use_smooth = True
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 3
        md.limit_method = "ANGLE"
        for p in ob.data.polygons:
            p.use_smooth = True
        if hasattr(ob.data, "set_sharp_from_angle"):
            ob.data.set_sharp_from_angle(angle=math.radians(40))
    if subsurf:
        md = ob.modifiers.new("subsurf", "SUBSURF")
        md.levels = subsurf
        md.render_levels = subsurf
    if parent is not None:
        ob.parent = parent
    return ob


def curve_obj(name, pts, radius=0.03, m=None, parent=None, res=12, closed=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.resolution_u = res
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu)
    if m is not None:
        cu.materials.append(m)
    return link(ob, parent)


FONTS = {}


def font(key):
    files = {"anton": "anton-latin-400-normal.ttf", "vt": "vt323-latin-400-normal.ttf",
             "courier": "courier-prime-latin-700-normal.ttf", "elite": "special-elite-latin-400-normal.ttf",
             "barlow": "barlow-condensed-latin-800-normal.ttf"}
    if key not in FONTS:
        p = os.path.join(FONT_DIR, files.get(key, ""))
        FONTS[key] = bpy.data.fonts.load(p) if os.path.exists(p) else None
    return FONTS[key]


def text(name, body, size=0.1, m=None, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), fnt="anton", align="CENTER",
         valign="CENTER", extrude=0.0, spacing=1.0, width=0.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = valign
    cu.extrude = extrude
    cu.space_line = spacing
    f = font(fnt)
    if f:
        cu.font = f
    if width:
        cu.text_boxes[0].width = width
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = rot
    if m is not None:
        cu.materials.append(m)
    return link(ob, parent)


# ------------------------------------------------------------------ Kamera (früh, weil die UI-Ebene daran hängt)
cam_data = bpy.data.cameras.new("Kamera")
cam_data.lens = 30
cam_data.sensor_fit = "VERTICAL"
cam_data.sensor_height = 36.0
cam_data.clip_start = 0.02
cam_data.clip_end = 1500
cam_data.dof.use_dof = False          # flach und klar wie Dat Swag
CAM = bpy.data.objects.new("Kamera", cam_data)
link(CAM)
scn.camera = CAM


def look(cam_pos, target, roll=0.0, lens=None):
    CAM.location = cam_pos
    d = Vector(target) - Vector(cam_pos)
    rot = d.to_track_quat("-Z", "Y").to_euler()
    rot.rotate_axis("Z", roll)
    CAM.rotation_euler = rot
    if lens:
        cam_data.lens = lens


# ------------------------------------------------------------------ Viele Quader/Kugeln in einem Mesh
def parts_mesh(name, parts, mats, parent=None, loc=(0, 0, 0), link_=True, rot=(0, 0, 0)):
    """Ein Mesh aus vielen Teilen: (art, mitte, größe, material_index[, rot_z]); art 'b' = Quader, 's' = Kugel.
    Spart Objekte und Draw-Calls – so passt ein Büro bis zum Horizont in den Speicher."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for p in parts:
        kind, c, sz, mi = p[0], p[1], p[2], p[3]
        rz = p[4] if len(p) > 4 else 0.0
        M = Matrix.Translation(Vector(c)) @ Matrix.Rotation(rz, 4, "Z") @ Matrix.Diagonal((sz[0], sz[1], sz[2], 1.0))
        if kind == "s":
            ret = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5, matrix=M)
        else:
            ret = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
        faces = set()
        for v in ret["verts"]:
            faces.update(v.link_faces)
        for f in faces:
            f.material_index = mi
            f.smooth = kind == "s"
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    if link_:
        link(ob, parent)
    return ob


def proto_collection(name):
    """Collection außerhalb der Szene als Vorlage für Instanzen."""
    c = bpy.data.collections.new(name)
    return c


def move_to(ob, coll):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    for ch in ob.children:
        move_to(ch, coll)
    return ob


def instance(name, coll, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0, parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.instance_type = "COLLECTION"
    ob.instance_collection = coll
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = (scale, scale, scale) if not isinstance(scale, (tuple, list)) else scale
    return link(ob, parent)


def ease_back(t):
    t = clamp(t)
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def resolve(x):
    return x() if callable(x) else x


# ------------------------------------------------------------------ Himmel und Sonne
SUN_DIR = Vector((0.5, -0.62, 0.5)).normalized()      # Richtung zur Sonne: hinter der Kamera, die meist nach +Y schaut
world = bpy.data.worlds.new("Himmel")
scn.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
w_out = wn.nodes.new("ShaderNodeOutputWorld")
w_tc = wn.nodes.new("ShaderNodeTexCoord")
w_sep = wn.nodes.new("ShaderNodeSeparateXYZ")
wn.links.new(w_tc.outputs["Generated"], w_sep.inputs[0])
w_mr = wn.nodes.new("ShaderNodeMapRange")
w_mr.inputs["From Min"].default_value = -0.02
w_mr.inputs["From Max"].default_value = 0.65
wn.links.new(w_sep.outputs["Z"], w_mr.inputs["Value"])
SKY_RAMP = wn.nodes.new("ShaderNodeValToRGB")
SKY_RAMP.color_ramp.elements.new(0.3)
wn.links.new(w_mr.outputs[0], SKY_RAMP.inputs["Fac"])
w_dot = wn.nodes.new("ShaderNodeVectorMath")
w_dot.operation = "DOT_PRODUCT"
w_dot.inputs[1].default_value = SUN_DIR
wn.links.new(w_tc.outputs["Generated"], w_dot.inputs[0])
w_pos = wn.nodes.new("ShaderNodeMath"); w_pos.operation = "MAXIMUM"; w_pos.inputs[1].default_value = 0.0
wn.links.new(w_dot.outputs["Value"], w_pos.inputs[0])
w_halo = wn.nodes.new("ShaderNodeMath"); w_halo.operation = "POWER"; w_halo.inputs[1].default_value = 30.0
wn.links.new(w_pos.outputs[0], w_halo.inputs[0])
w_disk = wn.nodes.new("ShaderNodeMapRange")
w_disk.inputs["From Min"].default_value = 0.9986
w_disk.inputs["From Max"].default_value = 0.9992
w_disk.inputs["To Max"].default_value = 30.0
wn.links.new(w_pos.outputs[0], w_disk.inputs["Value"])
w_sum = wn.nodes.new("ShaderNodeMath"); w_sum.operation = "MULTIPLY_ADD"; w_sum.inputs[1].default_value = 0.9
wn.links.new(w_halo.outputs[0], w_sum.inputs[0])
wn.links.new(w_disk.outputs[0], w_sum.inputs[2])
SUN_AMT = wn.nodes.new("ShaderNodeValue"); SUN_AMT.outputs[0].default_value = 1.0
w_sm = wn.nodes.new("ShaderNodeMath"); w_sm.operation = "MULTIPLY"
wn.links.new(w_sum.outputs[0], w_sm.inputs[0])
wn.links.new(SUN_AMT.outputs[0], w_sm.inputs[1])
SUN_COL = wn.nodes.new("ShaderNodeRGB"); SUN_COL.outputs[0].default_value = hexcol("#fff0c8")
w_sc = wn.nodes.new("ShaderNodeVectorMath"); w_sc.operation = "SCALE"
wn.links.new(SUN_COL.outputs[0], w_sc.inputs[0])
wn.links.new(w_sm.outputs[0], w_sc.inputs["Scale"])
# Sterne (nur im Akten-Kosmos)
w_vor = wn.nodes.new("ShaderNodeTexVoronoi"); w_vor.inputs["Scale"].default_value = 260.0
wn.links.new(w_tc.outputs["Generated"], w_vor.inputs["Vector"])
w_st = wn.nodes.new("ShaderNodeMapRange")
w_st.inputs["From Min"].default_value = 0.07; w_st.inputs["From Max"].default_value = 0.0
w_st.inputs["To Max"].default_value = 4.0
wn.links.new(w_vor.outputs["Distance"], w_st.inputs["Value"])
STARS = wn.nodes.new("ShaderNodeValue"); STARS.outputs[0].default_value = 0.0
w_stm = wn.nodes.new("ShaderNodeMath"); w_stm.operation = "MULTIPLY"
wn.links.new(w_st.outputs[0], w_stm.inputs[0])
wn.links.new(STARS.outputs[0], w_stm.inputs[1])
w_add1 = wn.nodes.new("ShaderNodeVectorMath"); w_add1.operation = "ADD"
wn.links.new(SKY_RAMP.outputs["Color"], w_add1.inputs[0])
wn.links.new(w_sc.outputs[0], w_add1.inputs[1])
w_add2 = wn.nodes.new("ShaderNodeVectorMath"); w_add2.operation = "ADD"
wn.links.new(w_add1.outputs[0], w_add2.inputs[0])
wn.links.new(w_stm.outputs[0], w_add2.inputs[1])
w_bg = wn.nodes.new("ShaderNodeBackground")
wn.links.new(w_add2.outputs[0], w_bg.inputs["Color"])
# Die Kamera sieht den Himmel voll, als Umgebungslicht nur gedämpft (sonst wird alles flau)
w_lp = wn.nodes.new("ShaderNodeLightPath")
w_str = wn.nodes.new("ShaderNodeMapRange")
w_str.inputs["To Min"].default_value = 0.55
w_str.inputs["To Max"].default_value = 1.0
wn.links.new(w_lp.outputs["Is Camera Ray"], w_str.inputs["Value"])
wn.links.new(w_str.outputs[0], w_bg.inputs["Strength"])
wn.links.new(w_bg.outputs[0], w_out.inputs["Surface"])


def light(name, kind, loc, energy, color="#ffffff", size=1.0, rot=(0, 0, 0), spot=0.8):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = hexcol(color)[:3]
    if kind == "AREA":
        ld.size = size
    if kind == "SPOT":
        ld.spot_size = spot
        ld.spot_blend = 0.6
    if kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    return link(ob)


SUN = light("Sonne", "SUN", (0, 0, 60), 3.2, "#fff1d6", rot=SUN_DIR.to_track_quat("Z", "Y").to_euler())
SUN.data.angle = math.radians(1.2)

# ------------------------------------------------------------------ Dunst: alles verschwimmt zum Horizont (Node-Gruppe in jedem Material)
HAZE = bpy.data.node_groups.new("Dunst", "ShaderNodeTree")
HAZE.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
HAZE.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
_hi = HAZE.nodes.new("NodeGroupInput")
_ho = HAZE.nodes.new("NodeGroupOutput")
_hcd = HAZE.nodes.new("ShaderNodeCameraData")
_hmr = HAZE.nodes.new("ShaderNodeMapRange")
_hmr.interpolation_type = "SMOOTHSTEP"
HAZE_NEAR = HAZE.nodes.new("ShaderNodeValue"); HAZE_NEAR.outputs[0].default_value = 18.0
HAZE_FAR = HAZE.nodes.new("ShaderNodeValue"); HAZE_FAR.outputs[0].default_value = 125.0
HAZE.links.new(_hcd.outputs["View Distance"], _hmr.inputs["Value"])
HAZE.links.new(HAZE_NEAR.outputs[0], _hmr.inputs["From Min"])
HAZE.links.new(HAZE_FAR.outputs[0], _hmr.inputs["From Max"])
HAZE_COL = HAZE.nodes.new("ShaderNodeRGB")
_hem = HAZE.nodes.new("ShaderNodeEmission")
HAZE.links.new(HAZE_COL.outputs[0], _hem.inputs["Color"])
_hmx = HAZE.nodes.new("ShaderNodeMixShader")
HAZE.links.new(_hmr.outputs[0], _hmx.inputs[0])
HAZE.links.new(_hi.outputs[0], _hmx.inputs[1])
HAZE.links.new(_hem.outputs[0], _hmx.inputs[2])
HAZE.links.new(_hmx.outputs[0], _ho.inputs[0])


def apply_haze():
    """Hängt die Dunst-Gruppe hinter jedes Material (außer UI_ – die Akten-Pop-ups kleben vor der Kamera)."""
    n = 0
    for m in list(bpy.data.materials):
        if m.name.startswith("UI_") or not m.use_nodes:
            continue
        nt = m.node_tree
        out = next((x for x in nt.nodes if x.type == "OUTPUT_MATERIAL"), None)
        if out is None or not out.inputs["Surface"].links:
            continue
        src = out.inputs["Surface"].links[0].from_socket
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree = HAZE
        nt.links.new(src, g.inputs[0])
        nt.links.new(g.outputs[0], out.inputs["Surface"])
        n += 1
    print("Dunst in", n, "Materialien")


# Himmels-Paletten der Welten: Horizont, Mitte, Zenit, Sonne, Sterne, Dunst nah/fern, Sonnenlicht
SKIES = {
    "buero":  ("#d6eaff", "#7fb6ff", "#2a6cf0", 1.0, 0.0, 24, 185, 3.2, "#fff1d6"),
    "hotdog": ("#ffd77a", "#ff7ab8", "#9a3cff", 1.6, 0.0, 25, 160, 3.0, "#ffd9b0"),
    "pepsi":  ("#c8f6ff", "#3cc4ff", "#0a4fd6", 1.2, 0.0, 30, 220, 3.4, "#ffffff"),
    "kosmos": ("#2a1050", "#120630", "#020108", 0.35, 1.0, 40, 320, 2.2, "#c9b8ff"),
}
WORLD_NOW = [None]


def set_sky(name):
    if WORLD_NOW[0] == name:
        return
    WORLD_NOW[0] = name
    hz, md, zn, sun, stars, near, far, sun_e, sun_c = SKIES[name]
    els = SKY_RAMP.color_ramp.elements
    els[0].color, els[1].color, els[2].color = hexcol(hz), hexcol(md), hexcol(zn)
    # Elemente sind nach Position sortiert: 0.0 Horizont, 0.3 Mitte, 1.0 Zenit
    SUN_AMT.outputs[0].default_value = sun
    STARS.outputs[0].default_value = stars
    HAZE_NEAR.outputs[0].default_value = near
    HAZE_FAR.outputs[0].default_value = far
    HAZE_COL.outputs[0].default_value = hexcol(hz)
    SUN.data.energy = sun_e
    SUN.data.color = hexcol(sun_c)[:3]


# ------------------------------------------------------------------ Teppich bis zum Horizont
def carpet_mat():
    m, nt, out = node_mat("Teppich")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.95
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 0.35; n1.inputs["Detail"].default_value = 4
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 60.0; n2.inputs["Detail"].default_value = 2
    nt.links.new(geo.outputs["Position"], n1.inputs["Vector"])
    nt.links.new(geo.outputs["Position"], n2.inputs["Vector"])
    mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MULTIPLY_ADD"; mx.inputs[1].default_value = 0.35
    nt.links.new(n2.outputs["Fac"], mx.inputs[0])
    nt.links.new(n1.outputs["Fac"], mx.inputs[2])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.45, hexcol("#3d6470")
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.85, hexcol("#56808b")
    nt.links.new(mx.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.2
    nt.links.new(n2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


FLOOR = prim("plane", "Teppich", (0, 0, 0), (6000, 6000, 1), m=carpet_mat())




# ------------------------------------------------------------------ Bildschirme
SCREENS = []   # dicts: obj, nodes (value nodes), content objects, base color, mode


def screen_material(idx, base):
    """Emissionsmaterial mit Scanlines, Bildschnee und Ein/Aus. Handler steuert die Value-Nodes."""
    m, nt, out = node_mat("Screen%02d" % idx)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # Werte, die der Handler setzt
    v_on = nt.nodes.new("ShaderNodeValue"); v_on.name = "on"; v_on.outputs[0].default_value = 0.0
    v_st = nt.nodes.new("ShaderNodeValue"); v_st.name = "static"; v_st.outputs[0].default_value = 1.0
    v_w = nt.nodes.new("ShaderNodeValue"); v_w.name = "w"; v_w.outputs[0].default_value = 0.0
    v_fl = nt.nodes.new("ShaderNodeValue"); v_fl.name = "flash"; v_fl.outputs[0].default_value = 0.0
    col = nt.nodes.new("ShaderNodeRGB"); col.name = "col"; col.outputs[0].default_value = hexcol(base)
    # Hintergrund: vertikaler Verlauf der Senderfarbe
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    grad = nt.nodes.new("ShaderNodeMath"); grad.operation = "MULTIPLY_ADD"
    grad.inputs[1].default_value = 0.6; grad.inputs[2].default_value = 0.4
    nt.links.new(sep.outputs["Y"], grad.inputs[0])
    bgc = nt.nodes.new("ShaderNodeMixRGB"); bgc.blend_type = "MULTIPLY"; bgc.inputs[0].default_value = 1.0
    nt.links.new(col.outputs[0], bgc.inputs[1])
    nt.links.new(grad.outputs[0], bgc.inputs[2])
    # Scanlines
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"; wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["UV"], wave.inputs["Vector"])
    sl = nt.nodes.new("ShaderNodeMapRange")
    sl.inputs["To Min"].default_value = 0.72; sl.inputs["To Max"].default_value = 1.0
    nt.links.new(wave.outputs["Fac"], sl.inputs["Value"])
    # Bildschnee (4D-Noise, w wird pro Frame verschoben)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 260.0
    nz.inputs["Detail"].default_value = 0.0
    nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
    nt.links.new(v_w.outputs[0], nz.inputs["W"])
    snow = nt.nodes.new("ShaderNodeMapRange")
    snow.inputs["From Min"].default_value = 0.35; snow.inputs["From Max"].default_value = 0.65
    nt.links.new(nz.outputs["Fac"], snow.inputs["Value"])
    mix1 = nt.nodes.new("ShaderNodeMixRGB")
    nt.links.new(v_st.outputs[0], mix1.inputs[0])
    nt.links.new(bgc.outputs[0], mix1.inputs[1])
    nt.links.new(snow.outputs[0], mix1.inputs[2])
    # Blitz zu Weiß
    mix2 = nt.nodes.new("ShaderNodeMixRGB")
    nt.links.new(v_fl.outputs[0], mix2.inputs[0])
    nt.links.new(mix1.outputs[0], mix2.inputs[1])
    mix2.inputs[2].default_value = (1, 1, 1, 1)
    scan = nt.nodes.new("ShaderNodeMixRGB"); scan.blend_type = "MULTIPLY"; scan.inputs[0].default_value = 1.0
    nt.links.new(mix2.outputs[0], scan.inputs[1])
    nt.links.new(sl.outputs[0], scan.inputs[2])
    # Vignette der Bildröhre
    grad2 = nt.nodes.new("ShaderNodeTexGradient"); grad2.gradient_type = "QUADRATIC_SPHERE"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (-0.5, -0.5, 0)
    mp.inputs["Scale"].default_value = (1.35, 1.35, 1)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    # Mapping verschiebt vor dem Skalieren -> Mittelpunkt bei UV 0.5
    nt.links.new(mp.outputs[0], grad2.inputs[0])
    vig = nt.nodes.new("ShaderNodeMapRange")
    vig.inputs["To Min"].default_value = 0.25; vig.inputs["To Max"].default_value = 1.0
    nt.links.new(grad2.outputs["Fac"], vig.inputs["Value"])
    strength = nt.nodes.new("ShaderNodeMath"); strength.operation = "MULTIPLY"
    nt.links.new(vig.outputs[0], strength.inputs[0])
    nt.links.new(v_on.outputs[0], strength.inputs[1])
    s2 = nt.nodes.new("ShaderNodeMath"); s2.operation = "MULTIPLY"; s2.inputs[1].default_value = 2.5
    nt.links.new(strength.outputs[0], s2.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(scan.outputs[0], em.inputs["Color"])
    nt.links.new(s2.outputs[0], em.inputs["Strength"])
    # Glas der Röhre (dunkel, spiegelnd) über der Emission
    glass = nt.nodes.new("ShaderNodeBsdfPrincipled")
    glass.inputs["Base Color"].default_value = hexcol("#0a0c0f")
    glass.inputs["Roughness"].default_value = 0.08
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(em.outputs[0], add.inputs[0])
    nt.links.new(glass.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m, {"on": v_on, "static": v_st, "w": v_w, "flash": v_fl, "col": col}


CASINGS = ["#cfc6b4", "#3b3530", "#6b4a2e", "#2a2a2e", "#b9b2a6", "#8d7a5f"]


def tv(name, loc, size=0.6, rot_z=0.0, casing=None, base="#1d3a8a", tilt=0.0, parent=None, knobs=True):
    """Röhrenfernseher: Gehäuse, leicht gewölbte Mattscheibe, Knöpfe. size = Breite in m."""
    root = empty(name, loc, parent, rot=(tilt, 0, rot_z))
    w, h, d = size, size * 0.78, size * 0.85
    cas = casing or CASINGS[len(SCREENS) % len(CASINGS)]
    body = prim("cube", name + "_body", (0, -d * 0.5, h * 0.5), (w, d, h), m=mat("TV_" + cas, cas, 0.45, coat=0.3),
                parent=root, bevel=size * 0.05)
    back = prim("cube", name + "_back", (0, -d * 1.05, h * 0.5), (w * 0.7, d * 0.5, h * 0.7), m=mat("TV_" + cas, cas, 0.45),
                parent=root, bevel=size * 0.05)
    # Bildröhre: Ebene mit leichter Wölbung (Subdivision + Cast zur Kugel)
    sw, sh = w * 0.72, h * 0.72
    scr = prim("plane", name + "_screen", (-w * 0.08, 0.012, h * 0.52), (sw, sh, 1), rot=(math.radians(90), 0, math.pi), parent=root)
    sub = scr.modifiers.new("sub", "SUBSURF"); sub.levels = 3; sub.render_levels = 3; sub.subdivision_type = "SIMPLE"
    cast = scr.modifiers.new("bulge", "CAST"); cast.factor = 0.12; cast.cast_type = "SPHERE"
    sm, nodes = screen_material(len(SCREENS), base)
    scr.data.materials.append(sm)
    # schwarzer Rahmen um die Röhre
    # Rahmen liegt hinter der Mattscheibe, sonst verdeckt er sie
    prim("cube", name + "_bezel", (-w * 0.08, -0.009, h * 0.52), (sw * 1.1, 0.02, sh * 1.12), m=mat("Bezel", "#111014", 0.6), parent=root)
    if knobs:
        for i in range(2):
            prim("cyl", name + "_knob%d" % i, (w * 0.39, 0.02, h * (0.66 - i * 0.22)), (size * 0.07, size * 0.07, 0.04),
                 rot=(math.radians(90), 0, 0), m=mat("Knob", "#1a1a1a", 0.4), parent=root, seg=16)
    s = {"name": name, "root": root, "screen": scr, "nodes": nodes, "size": size, "w": sw, "h": sh,
         "base": base, "content": [], "phase": rnd.random(), "on_at": None}
    SCREENS.append(s)
    return s


def screen_text(s, body, size_rel=0.16, color="#ffffff", y_rel=0.0, x_rel=0.0, fnt="anton", strength=6.0, name=None):
    """Leuchtender Text knapp vor der Mattscheibe."""
    scr = s["screen"]
    m = emit_mat("Txt_" + color + str(strength), color, strength)
    ob = text(name or (s["name"] + "_txt%d" % len(s["content"])), body, size=s["h"] * size_rel, m=m, parent=s["root"],
              loc=(scr.location.x + x_rel * s["w"], 0.05, scr.location.z + y_rel * s["h"]), rot=(math.radians(90), 0, math.pi), fnt=fnt)
    s["content"].append(ob)
    return ob


def screen_bar(s, color, y_rel, h_rel, w_rel=1.0, x_rel=0.0, strength=5.0):
    scr = s["screen"]
    ob = prim("plane", s["name"] + "_bar%d" % len(s["content"]), (scr.location.x + x_rel * s["w"], 0.045, scr.location.z + y_rel * s["h"]),
              (s["w"] * w_rel, s["h"] * h_rel, 1), rot=(math.radians(90), 0, math.pi), m=emit_mat("Bar_" + color + str(strength), color, strength), parent=s["root"])
    s["content"].append(ob)
    return ob



# ------------------------------------------------------------------ Vorlagen: Hot Dog, Pepsi-Flasche, Pixel-Chicken-Guy
HOTDOG = proto_collection("HotDogVorlage")
_bun = mat("Broetchen", "#e0a35a", 0.6, sss=0.1)
_wurst = mat("Wurst", "#b4472c", 0.35, coat=0.4)
_senf = mat("Senf", "#ffd21f", 0.4, emit="#ffd21f", estr=0.3)
_hd = parts_mesh("HD", [("s", (0, -0.055, 0), (0.6, 0.12, 0.16), 0), ("s", (0, 0.055, 0), (0.6, 0.12, 0.16), 0),
                        ("s", (0, 0, 0.05), (0.72, 0.1, 0.1), 1)], [_bun, _wurst], link_=False)
HOTDOG.objects.link(_hd)
_ms = curve_obj("HD_senf", [Vector((-0.28 + i * 0.07, 0.025 * (1 if i % 2 else -1), 0.1)) for i in range(9)], radius=0.012, m=_senf)
move_to(_ms, HOTDOG)

PEPSI = proto_collection("PepsiVorlage")
_pb = mat("PepsiBlau", "#1d4fd8", 0.12, coat=1.0)
_pw = mat("PepsiWeiss", "#f2f2f2", 0.4)
_pr = mat("PepsiRot", "#e3122b", 0.4)
_bt = parts_mesh("PF", [("s", (0, 0, 0.32), (0.3, 0.3, 0.7), 0), ("b", (0, 0, 0.32), (0.31, 0.31, 0.12), 1),
                        ("b", (0, 0, 0.24), (0.305, 0.305, 0.04), 2), ("s", (0, 0, 0.72), (0.14, 0.14, 0.3), 0),
                        ("b", (0, 0, 0.88), (0.1, 0.1, 0.05), 0)], [_pb, _pw, _pr], link_=False)
PEPSI.objects.link(_bt)

# Pixel-Chicken-Guy (zwei Tanzbilder) für Bildschirme und Akten
CG_PIX = {"H": "#141010", "S": "#7a4a30", "K": "#1a0c06", "N": "#5a321e", "M": "#4a1a18", "W": "#f2e6c4",
          "P": "#ff8fa6", "O": "#d27a2a", "B": "#f4ecd8", "Y": "#ffd23c"}
CG_SPRITE = [
    ["....HHHH....", "..HHHHHHHH..", "..SSSSSSSS..", ".SSKKSSKKSS.", ".SSSSNNSSSS.", ".SSSMMMMSSS.", "..SSMWWMSS..",
     "..SSMPPMSS..", "...SSSSSS...", "O..OOOOOO..O", ".OOOOOOOOOO.", "...OOOOOO...", "...OO..OO...", "...BB..BB..."],
    ["....HHHH....", "..HHHHHHHH..", "..SSSSSSSS..", ".SSKKSSKKSS.", ".SSSSNNSSSS.", ".SSMMMMMMSS.", "..SMWW.WMS..",
     "..SMPPPPMS..", "...SMMMMS...", "...OOOOOO...", ".OOOOOOOOOO.", "O..OOOOOO..O", "...OO..OO...", "..BB....BB.."],
]


def pixel_sprite(name, rows, px, parent, loc, rot, emit=True, strength=4.0):
    keys = sorted(set("".join(rows)) - {"."})
    mats = [emit_mat("Pix_" + k + ("e" if emit else ""), CG_PIX[k], strength) if emit else mat("Pix_" + k, CG_PIX[k], 0.6) for k in keys]
    parts = []
    h = len(rows)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                parts.append(("b", ((i - len(row) / 2 + 0.5) * px, (h / 2 - j - 0.5) * px, 0), (px * 0.98, px * 0.98, px * 0.3), keys.index(ch)))
    return parts_mesh(name, parts, mats, parent=parent, loc=loc, rot=rot)


# ------------------------------------------------------------------ Röhren-PCs mit Programmen
PROG_MATS = {}
PROG_BASE = {"news": "#1b3fa8", "vermisst": "#c4002a", "spirale": "#20102a", "hotdog": "#ff5fa8", "pixel": "#0f7a3a",
             "pepsi": "#1f4fd0", "desktop": "#008080", "kosmos": "#0a0618"}
SCREEN_TIME = []     # Value-Nodes, die pro Bild die Zeit bekommen


def spiral_mat(name, c0="#0a0a0a", c1="#ffffff", c2="#ff3fa4", emitting=True):
    """Hypnose-Spirale: Winkel + Radius -> Streifen, die sich drehen."""
    m, nt, out = node_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-0.5, -0.5, 0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(mp.outputs[0], sp.inputs[0])
    at = nt.nodes.new("ShaderNodeMath"); at.operation = "ARCTAN2"
    nt.links.new(sp.outputs["Y"], at.inputs[0]); nt.links.new(sp.outputs["X"], at.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; nt.links.new(mp.outputs[0], ln.inputs[0])
    tv_ = nt.nodes.new("ShaderNodeValue"); tv_.name = "zeit"; SCREEN_TIME.append(tv_)
    a3 = nt.nodes.new("ShaderNodeMath"); a3.operation = "MULTIPLY"; a3.inputs[1].default_value = 3.0
    nt.links.new(at.outputs[0], a3.inputs[0])
    r9 = nt.nodes.new("ShaderNodeMath"); r9.operation = "MULTIPLY_ADD"; r9.inputs[1].default_value = 40.0
    nt.links.new(ln.outputs[1], r9.inputs[0]); nt.links.new(a3.outputs[0], r9.inputs[2])
    tt = nt.nodes.new("ShaderNodeMath"); tt.operation = "MULTIPLY_ADD"; tt.inputs[1].default_value = -9.0
    nt.links.new(tv_.outputs[0], tt.inputs[0]); nt.links.new(r9.outputs[0], tt.inputs[2])
    sn = nt.nodes.new("ShaderNodeMath"); sn.operation = "SINE"; nt.links.new(tt.outputs[0], sn.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.45, hexcol(c0)
    els[1].position, els[1].color = 0.55, hexcol(c1)
    e2 = els.new(0.9); e2.color = hexcol(c2)
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1.0
    nt.links.new(sn.outputs[0], mr.inputs["Value"]); nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    if emitting:
        em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 3.0
        nt.links.new(ramp.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    else:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
        nt.links.new(ramp.outputs[0], bsdf_input(b, "Emission Color", "Emission"))
        bsdf_input(b, "Emission Strength").default_value = 0.8
        nt.links.new(b.outputs[0], out.inputs[0])
    return m


SPIRAL_M = spiral_mat("Spirale")
CASE_BEIGE = mat("PCbeige", "#d9d0b8", 0.45, coat=0.2)


def monitor(name, loc, rot_z=0.0, prog="news", parent=None, size=0.42):
    """Beiger Röhrenmonitor wie in den 90ern. Programme teilen sich Material und Zustand (spart Shader)."""
    root = empty(name, loc, parent, rot=(0, 0, rot_z))
    w, h, d = size, size * 0.86, size * 0.9
    prim("cube", name + "_body", (0, -d * 0.45, h * 0.5 + 0.05), (w, d * 0.9, h), m=CASE_BEIGE, parent=root, bevel=size * 0.04)
    prim("cube", name + "_back", (0, -d * 1.0, h * 0.5 + 0.05), (w * 0.7, d * 0.4, h * 0.7), m=CASE_BEIGE, parent=root, bevel=size * 0.04)
    prim("cube", name + "_fuss", (0, -d * 0.45, 0.025), (w * 0.6, d * 0.6, 0.05), m=CASE_BEIGE, parent=root, bevel=0.01)
    sw, sh = w * 0.78, h * 0.72
    scr = prim("plane", name + "_screen", (0, 0.012, h * 0.53 + 0.05), (sw, sh, 1), rot=(math.radians(90), 0, math.pi), parent=root)
    sub = scr.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 2; sub.subdivision_type = "SIMPLE"
    cast = scr.modifiers.new("bulge", "CAST"); cast.factor = 0.1; cast.cast_type = "SPHERE"
    if prog not in PROG_MATS:
        PROG_MATS[prog] = screen_material(len(PROG_MATS), PROG_BASE[prog])
    sm, nodes = PROG_MATS[prog]
    scr.data.materials.append(sm)
    prim("cube", name + "_bezel", (0, -0.009, h * 0.53 + 0.05), (sw * 1.12, 0.02, sh * 1.15), m=mat("BezelBeige", "#bfb59c", 0.5), parent=root)
    s = {"name": name, "root": root, "screen": scr, "nodes": nodes, "size": size, "w": sw, "h": sh, "prog": prog,
         "base": PROG_BASE[prog], "content": [], "anim": [], "phase": rnd.random()}
    SCREENS.append(s)
    fill_program(s)
    return s


def screen_obj(s, ob):
    """Ein Objekt auf die Mattscheibe setzen (lokal: x quer, z hoch, vor dem Glas)."""
    ob.parent = s["root"]
    s["content"].append(ob)
    return ob


def fill_program(s):
    p = s["prog"]
    sc = s["screen"].location
    W, H = s["w"], s["h"]
    rot = (math.radians(90), 0, math.pi)
    if p == "news":
        screen_text(s, "MINO 1", 0.22, "#ffffff", y_rel=0.28)
        screen_text(s, "NEWS", 0.15, "#ffd23c", y_rel=0.05)
        bar = screen_bar(s, "#ffffff", -0.33, 0.14, strength=4.0)
        tk = screen_text(s, "+++ GOD ABSENT +++", 0.09, "#c4002a", y_rel=-0.33, fnt="barlow")
        s["anim"].append(lambda t, b, o=tk: setattr(o, "hide_render", int(b * 4) % 4 == 3))
    elif p == "vermisst":
        screen_text(s, "MISSING", 0.2, "#ffffff", y_rel=0.25)
        o = screen_text(s, "CHICKEN GUY", 0.17, "#ffe34a", y_rel=-0.02)
        screen_text(s, "LAST SEEN: DANCING", 0.075, "#ffffff", y_rel=-0.3, fnt="barlow")
        s["anim"].append(lambda t, b, o=o: setattr(o, "hide_render", int(b * 2) % 2 == 1))
    elif p == "spirale":
        pl = prim("plane", s["name"] + "_spirale", (sc.x, 0.04, sc.z), (W * 0.98, H * 0.98, 1), rot=rot, m=SPIRAL_M)
        screen_obj(s, pl)
        screen_text(s, "DO NOT LOOK", 0.11, "#ffe34a", y_rel=-0.36, strength=8)
    elif p == "hotdog":
        screen_text(s, "IT IS RAINING", 0.12, "#ffffff", y_rel=0.3)
        hs = []
        for i in range(5):
            o = instance(s["name"] + "_hd%d" % i, HOTDOG, (0, 0.05, 0), scale=W * 0.35)
            screen_obj(s, o)
            hs.append(o)

        def rain(t, b, hs=hs, x0=sc.x, z0=sc.z):
            for i, o in enumerate(hs):
                ph = (t * (0.5 + hsh(i) * 0.4) + hsh(i * 3)) % 1.0
                o.location = (x0 + (hsh(i * 7) - 0.5) * W * 0.8, 0.06, z0 + H * 0.45 - ph * H * 0.9)
                o.rotation_euler = (math.radians(90), t * 3 + i, 0)
        s["anim"].append(rain)
    elif p == "pixel":
        fr = [pixel_sprite(s["name"] + "_pix%d" % k, CG_SPRITE[k], H * 0.055, s["root"], (sc.x, 0.045, sc.z - H * 0.04), rot) for k in (0, 1)]
        for o in fr:
            s["content"].append(o)
        screen_text(s, "CHICKEN.GIF", 0.08, "#ffffff", y_rel=0.42, fnt="vt")
        s["anim"].append(lambda t, b, fr=fr: [setattr(o, "scale", (1, 1, 1) if (int(b * 2) % 2) == k else (0, 0, 0)) for k, o in enumerate(fr)])
    elif p == "pepsi":
        screen_text(s, "PEPSI GRANDMA", 0.1, "#ffffff", y_rel=0.36)
        screen_text(s, "RECOMMENDS: ONE MORE", 0.08, "#ffe34a", y_rel=-0.38, fnt="barlow")
        o = instance(s["name"] + "_flasche", PEPSI, (sc.x, 0.06, sc.z - H * 0.28), rot=(0, 0, 0), scale=H * 0.55)
        screen_obj(s, o)
        s["anim"].append(lambda t, b, o=o: setattr(o.rotation_euler, "y", math.sin(t * 6) * 0.4))
    elif p == "desktop":
        for i, lab in enumerate(("CASE.EXE", "HOTDOG.BAT", "CHICKEN.GIF")):
            x = sc.x + W * 0.3 - 0.0 * i
            z = sc.z + H * (0.3 - i * 0.26)
            screen_obj(s, prim("plane", s["name"] + "_icon%d" % i, (x, 0.042, z + H * 0.04), (W * 0.1, H * 0.1, 1), rot=rot,
                                m=emit_mat("IconGelb", "#ffd23c", 3)))
            screen_text(s, lab, 0.05, "#ffffff", y_rel=(0.3 - i * 0.26) - 0.07, x_rel=-0.3 if False else 0.3, fnt="vt")
        screen_bar(s, "#c0c0c0", -0.44, 0.1, strength=2.5)
        screen_text(s, "START", 0.06, "#000000", y_rel=-0.44, x_rel=0.38, fnt="barlow", strength=1)
        cur = prim("cone", s["name"] + "_maus", (sc.x, 0.05, sc.z), (W * 0.06, W * 0.06, W * 0.09), rot=(0, math.radians(-30), 0),
                   m=emit_mat("Mauszeiger", "#ffffff", 5), seg=3)
        screen_obj(s, cur)
        s["cursor"] = cur
    elif p == "kosmos":
        for i in range(14):
            o = prim("ico", s["name"] + "_stern%d" % i, (sc.x + (hsh(i * 3.1) - 0.5) * W * 0.9, 0.045, sc.z + (hsh(i * 5.7) - 0.5) * H * 0.9),
                     (W * 0.02,) * 3, m=emit_mat("Stern", "#ffffff", 8))
            screen_obj(s, o)
        screen_text(s, "FILE 404", 0.14, "#b48cff", y_rel=0.12)
        screen_text(s, "LOST IN SPACE", 0.08, "#ffffff", y_rel=-0.12, fnt="barlow")


# ------------------------------------------------------------------ Großraumbüro: Kabinen-Raster bis zum Horizont
FABRIC = noise_mat("Stoffwand", "#b3a283", "#c9b998", scale=60, rough=0.95, bump=0.12)
TRIM = mat("Kantenleiste", "#8a847a", 0.45)
DESK_M = mat("Tischplatte", "#ddd2ba", 0.55)
LEG_M = mat("Tischbein", "#6d6a66", 0.4, metal=0.5)
KEYS_M = mat("Tasten", "#cfc8b2", 0.6)
CHAIR_M = mat("Stuhlstoff", "#2b3a55", 0.85)
PAPER_M = mat("Papier", "#f1ece0", 0.85)
MANILA_M = mat("Akte_manila", "#d9b77a", 0.8)


def far_screen_mat():
    """Bildschirme der fernen Kabinen: jede Instanz eigene Farbe (Object Info Random), pulsiert im Takt."""
    m, nt, out = node_mat("BildschirmFern")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    bt = nt.nodes.new("ShaderNodeValue"); bt.name = "takt"
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
    nt.links.new(oi.outputs["Random"], add.inputs[0]); nt.links.new(bt.outputs[0], add.inputs[1])
    fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"; nt.links.new(add.outputs[0], fr.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cols = ["#1b3fa8", "#c4002a", "#0f7a3a", "#ff5fa8", "#008080", "#ffd23c", "#7a3cff"]
    els = ramp.color_ramp.elements
    ramp.color_ramp.interpolation = "CONSTANT"
    els[0].position, els[0].color = 0.0, hexcol(cols[0])
    els[1].position, els[1].color = 1.0, hexcol(cols[-1])
    for i, c in enumerate(cols[1:-1]):
        e = els.new((i + 1) / len(cols)); e.color = hexcol(c)
    nt.links.new(fr.outputs[0], ramp.inputs["Fac"])
    stv = nt.nodes.new("ShaderNodeValue"); stv.name = "staerke"; stv.outputs[0].default_value = 2.0
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs[0], em.inputs[0]); nt.links.new(stv.outputs[0], em.inputs[1])
    nt.links.new(em.outputs[0], out.inputs[0])
    MATS["BildschirmFern"] = m
    return m, bt, stv


FAR_SCREEN_M, FAR_TAKT, FAR_STAERKE = far_screen_mat()
CUB_MATS = [FABRIC, TRIM, DESK_M, LEG_M, CASE_BEIGE, FAR_SCREEN_M, KEYS_M, CHAIR_M, PAPER_M, MANILA_M]
CW_H, CW_T, CW_I = 1.35, 0.06, 0.04


def cubicle_parts(with_pc=True, detail=True, seed=0):
    """Eine Kabine im lokalen Raum: Eingang zeigt nach +Y, Schreibtisch an der Rückwand (-Y)."""
    H, T, I = CW_H, CW_T, CW_I
    L = 3.0 - 2 * I
    p = [("b", (0, -1.5 + I + T / 2, H / 2), (L, T, H), 0), ("b", (-1.5 + I + T / 2, 0, H / 2), (T, L, H), 0),
         ("b", (1.5 - I - T / 2, 0, H / 2), (T, L, H), 0), ("b", (-1.5 + I + 0.45, 1.5 - I - T / 2, H / 2), (0.9, T, H), 0)]
    p += [("b", (0, -1.5 + I + T / 2, H + 0.015), (L, T + 0.02, 0.03), 1), ("b", (-1.5 + I + T / 2, 0, H + 0.015), (T + 0.02, L, 0.03), 1),
          ("b", (1.5 - I - T / 2, 0, H + 0.015), (T + 0.02, L, 0.03), 1), ("b", (-1.5 + I + 0.45, 1.5 - I - T / 2, H + 0.015), (0.9, T + 0.02, 0.03), 1)]
    # L-Schreibtisch
    p += [("b", (0, -1.5 + 0.1 + 0.375, 0.74), (2.8, 0.75, 0.04), 2), ("b", (-1.5 + 0.1 + 0.375, -0.25, 0.74), (0.75, 1.5, 0.04), 2),
          ("b", (0.95, -1.05, 0.36), (0.45, 0.6, 0.72), 3)]
    if with_pc:
        p += [("b", (0, -1.0, 0.97), (0.42, 0.4, 0.37), 4), ("b", (0, -1.22, 0.95), (0.3, 0.25, 0.28), 4),
              ("b", (0, -0.792, 0.985), (0.31, 0.01, 0.24), 5), ("b", (0, -0.6, 0.77), (0.45, 0.16, 0.025), 6)]
    if detail:
        p += [("b", (-0.9, -1.15, 0.25), (0.2, 0.45, 0.45), 4),                                   # PC-Turm
              ("b", (0, -0.1, 0.48), (0.48, 0.46, 0.08), 7), ("b", (0, 0.15, 0.8), (0.46, 0.07, 0.5), 7),  # Stuhl
              ("b", (0, -0.1, 0.25), (0.05, 0.05, 0.45), 3), ("b", (0, -0.1, 0.04), (0.5, 0.5, 0.03), 3)]
        r = random.Random(seed)
        for k in range(r.randint(1, 4)):   # Papierkram und Akten
            x = -1.0 + r.random() * 0.6 if k % 2 else 0.45 + r.random() * 0.5
            n = r.randint(1, 6)
            p.append(("b", (x, -1.15 + r.random() * 0.2, 0.76 + n * 0.012), (0.32, 0.24, n * 0.024), 9 if k % 2 else 8, r.random() - 0.5))
        for k in range(r.randint(1, 3)):   # Zettel an der Stoffwand
            p.append(("b", (-0.9 + k * 0.6 + r.random() * 0.2, -1.5 + I + T + 0.004, 1.05 + r.random() * 0.15), (0.21, 0.004, 0.28), 8))
    return p


KAB_NAH = proto_collection("KabineNah")
KAB_NAH.objects.link(parts_mesh("KabineNahMesh", cubicle_parts(True, True, 1), CUB_MATS, link_=False))
KAB_NAH_LEER = proto_collection("KabineOhnePC")   # für Kabinen mit eigenem, animiertem Monitor
KAB_NAH_LEER.objects.link(parts_mesh("KabineOhnePCMesh", cubicle_parts(False, True, 2), CUB_MATS, link_=False))
KAB_FERN = proto_collection("KabineFern")
KAB_FERN.objects.link(parts_mesh("KabineFernMesh", cubicle_parts(True, False), CUB_MATS, link_=False))

SHIRT_M, _snt, _sout = node_mat("HemdFern")
_sb = _snt.nodes.new("ShaderNodeBsdfPrincipled"); _sb.inputs["Roughness"].default_value = 0.8
_soi = _snt.nodes.new("ShaderNodeObjectInfo")
_sr = _snt.nodes.new("ShaderNodeValToRGB"); _sr.color_ramp.interpolation = "CONSTANT"
_sr.color_ramp.elements[0].color = hexcol("#f2d04a")
_sr.color_ramp.elements[1].position, _sr.color_ramp.elements[1].color = 0.66, hexcol("#9ec3e6")
_se = _sr.color_ramp.elements.new(0.33); _se.color = hexcol("#f4f1ea")
_snt.links.new(_soi.outputs["Random"], _sr.inputs["Fac"]); _snt.links.new(_sr.outputs[0], _sb.inputs["Base Color"])
_snt.links.new(_sb.outputs[0], _sout.inputs[0])
SKIN_W = mat("HautBuero", "#d8a688", 0.5, sss=0.2)
HAIR_W = mat("HaarBuero", "#2a2018", 0.8)
PANTS_M = mat("HoseBuero", "#3a3d48", 0.8)
WORKER = proto_collection("MitarbeiterFern")
WORKER.objects.link(parts_mesh("MitarbeiterMesh", [
    ("b", (0, -0.12, 0.86), (0.4, 0.24, 0.56), 0), ("s", (0, -0.15, 1.3), (0.23, 0.25, 0.28), 1),
    ("s", (0, -0.12, 1.36), (0.24, 0.25, 0.2), 2), ("b", (0, -0.35, 0.56), (0.36, 0.45, 0.16), 3),
    ("b", (0, -0.55, 0.28), (0.3, 0.12, 0.5), 3), ("b", (-0.2, -0.35, 0.9), (0.09, 0.45, 0.09), 0),
    ("b", (0.2, -0.35, 0.9), (0.09, 0.45, 0.09), 0)], [SHIRT_M, SKIN_W, HAIR_W, PANTS_M], link_=False))

CELLS = []


def cell_pos(s, bx, c, by, jc):
    x = s * (1.4 + bx * 8.8 + c * 3.0 + 1.5)
    y = by * 14.8 + jc * 3.0 + 1.5
    rz = math.radians(s * (90 if c == 0 else -90))
    return x, y, rz


def cw(cell, lp):
    """Lokaler Kabinenpunkt -> Weltkoordinaten."""
    x, y, rz = cell
    v = Matrix.Rotation(rz, 3, "Z") @ Vector(lp)
    return Vector((x + v.x, y + v.y, v.z))


HERO_CELLS = {}
for s_ in (-1, 1):
    for c_ in (0, 1):
        for by_ in (-1, 0, 1, 2):
            for jc_ in range(4):
                HERO_CELLS[(s_, 0, c_, by_, jc_)] = cell_pos(s_, 0, c_, by_, jc_)



# Kabinen entlang der Hauptgänge: eigene Monitore mit Programmen, animierte Kollegen
PROG_ORDER = ["news", "vermisst", "hotdog", "pixel", "spirale", "pepsi", "kosmos", "desktop"]
HERO = {}
for i, (key, cell) in enumerate(sorted(HERO_CELLS.items())):
    s_, bx_, c_, by_, jc_ = key
    instance("KH_%d" % i, KAB_NAH_LEER, (cell[0], cell[1], 0), (0, 0, cell[2]))
    prog = PROG_ORDER[int(hsh(i * 2.3) * len(PROG_ORDER))]
    if key == (1, 0, 0, 0, 1):                      # Mino Mans Rechner
        prog = "news"
    elif prog == "desktop":
        prog = "news"
    mon = monitor("PC%02d" % i, cw(cell, (0, -1.0, 0.76)), cell[2], prog)
    HERO[key] = {"cell": cell, "mon": mon, "worker": None}


# ------------------------------------------------------------------ Akten


# ------------------------------------------------------------------ Akten
FOLDER_COLS = ["#d9b77a", "#cfa864", "#e8c98e", "#9fb4d8", "#e7a0a8"]
paper_m = mat("Papier", "#f1ece0", 0.85)
STACKS = []


def akte(name, loc, rot_z=0.0, col=None, label=None, open_=False, parent=None, scale=1.0):
    root = empty(name, loc, parent, rot=(0, 0, rot_z))
    c = col or FOLDER_COLS[int(hsh(len(STACKS) * 3.3) * len(FOLDER_COLS))]
    w, d = 0.32 * scale, 0.24 * scale
    prim("cube", name + "_deckel", (0, 0, 0.006 * scale), (w, d, 0.012 * scale), m=mat("Akte_" + c, c, 0.8), parent=root)
    prim("cube", name + "_papier", (0.004, 0.002, 0.018 * scale), (w * 0.95, d * 0.93, 0.012 * scale), m=paper_m, parent=root)
    if label:
        text(name + "_lbl", label, size=0.028 * scale, m=mat("Tinte", "#1a1a1a", 0.6), parent=root,
             loc=(0, 0.02 * scale, 0.0255 * scale), fnt="courier")
    STACKS.append(root)
    return root



# ------------------------------------------------------------------ Figuren
skin_light = mat("HautHell", "#e2b8a0", 0.5, sss=0.25)
skin_dark = mat("HautDunkel", "#5a3624", 0.45, sss=0.2)


def _gauss(p, c, r):
    d = (p - c).length / r
    return math.exp(-d * d)


def sculpt_head(name, size, deforms, mouth, m_skin, m_lip, m_inner, parent, loc=(0, 0, 0), seg=(72, 48), open_keys=True, hole=True,
                open_amt=0.5):
    """Kopf als ein durchgehendes Mesh: Ellipsoid, per Gauß-Beulen modelliert (Nase, Augenhöhlen, Wangen, Kinn),
    mit einer echten Mundöffnung samt Innenfutter und Shapekeys für Mimik (auf, breit, O, Lächeln).
    Koordinaten der Beulen im Einheitskugel-Raum, +Y = vorn. mouth = (z, halbe Breite, halbe Höhe)."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=1.0)
    for v in bm.verts:
        p = v.co.copy()
        for c, r, d in deforms:
            w = _gauss(p, Vector(c), r)
            v.co += Vector(d) * w
    mz, mw, mh = mouth
    # Mundöffnung: Flächen vorne innerhalb einer Ellipse entfernen
    kill = [f for f in bm.faces if hole and f.calc_center_median().y > 0.5 and
            (f.calc_center_median().x / mw) ** 2 + ((f.calc_center_median().z - mz) / mh) ** 2 < 1.0]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    # Lippenmaterial in einem Ring um die Öffnung
    for f in (bm.faces if hole else []):
        c = f.calc_center_median()
        if c.y > 0.4 and (c.x / (mw * 1.35)) ** 2 + ((c.z - mz) / (mh + 0.1)) ** 2 < 1.0:
            f.material_index = 1
    # Innenfutter: Rand nach innen extrudieren
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
        nv = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        for v in nv:
            v.co.y -= 0.22
            v.co.x *= 0.85
            v.co.z = mz + (v.co.z - mz) * 0.8
        for g in ret["geom"]:
            if isinstance(g, bmesh.types.BMFace):
                g.material_index = 2
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_skin)
    me.materials.append(m_lip)
    me.materials.append(m_inner)
    ob = bpy.data.objects.new(name, me)
    link(ob, parent)
    ob.location = loc
    ob.scale = size
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    if open_keys:
        ob.shape_key_add(name="Basis")
        base = [v.co.copy() for v in me.vertices]

        def key(kname, fn, vmax=1.5):
            k = ob.shape_key_add(name=kname, from_mix=False)
            k.slider_max = vmax
            for i, p in enumerate(base):
                if p.y < 0.0:
                    continue
                k.data[i].co = p + fn(p)

        mc = Vector((0, 0.9, mz))

        def k_open(p):     # Unterkiefer runter, Kinn und Unterlippe ziehen mit, Oberlippe etwas hoch
            dx, dz = p.x / 0.62, (p.z - mz)
            if dz < 0:
                w = math.exp(-dx * dx) * math.exp(-((dz + 0.25) / 0.55) ** 2)
                return Vector((0, -0.08 * w, -open_amt * w))
            w = math.exp(-(p.x / 0.36) ** 2) * math.exp(-(dz / 0.16) ** 2)
            return Vector((0, 0.0, 0.1 * w))

        def k_wide(p):     # Mundwinkel auseinander
            w = math.exp(-((abs(p.x) - mw) / 0.25) ** 2) * math.exp(-((p.z - mz) / 0.22) ** 2)
            return Vector((math.copysign(0.14, p.x) * w, -0.03 * w, 0))

        def k_round(p):    # O-Mund: Winkel zusammen, Lippen vor
            w = math.exp(-((abs(p.x) - mw) / 0.3) ** 2) * math.exp(-((p.z - mz) / 0.25) ** 2)
            return Vector((-math.copysign(0.12, p.x) * w, 0.06 * w, 0))

        def k_smile(p):    # Mundwinkel hoch, Wangen hoch
            w = math.exp(-((abs(p.x) - mw * 1.1) / 0.22) ** 2) * math.exp(-((p.z - mz) / 0.25) ** 2)
            wc = math.exp(-((abs(p.x) - 0.45) / 0.25) ** 2) * math.exp(-((p.z - (mz + 0.3)) / 0.2) ** 2)
            return Vector((0.02 * w, 0.02 * wc, 0.1 * w + 0.05 * wc))

        def k_sneer(p):    # Oberlippe hoch (Zähne zeigen), Nase kraus
            w = math.exp(-(p.x / 0.35) ** 2) * math.exp(-((p.z - (mz + 0.05)) / 0.12) ** 2) * (p.z > mz)
            return Vector((0, 0.01 * w, 0.09 * w))

        for kname, fn in (("auf", k_open), ("breit", k_wide), ("rund", k_round), ("laecheln", k_smile), ("zaehne", k_sneer)):
            key(kname, fn)
    return ob


def hair_cap(name, size, deforms, hairline, m_hair, parent, loc=(0, 0, 0), grow=1.045, extra=None):
    """Haare als Kappe, die der Schädelform folgt: Kugel minimal größer, alles unter der Haarlinie weg.
    hairline(x, y) -> z-Grenze im Einheitsraum. extra: weitere Beulen nur für die Frisur (Volumen, Scheitel)."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=grow)
    for v in bm.verts:
        p = v.co.copy() / grow
        for c, r, d in deforms + (extra or []):
            v.co += Vector(d) * _gauss(p, Vector(c), r)
    kill = [f for f in bm.faces if f.calc_center_median().z < hairline(f.calc_center_median().x, f.calc_center_median().y)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_hair)
    ob = bpy.data.objects.new(name, me)
    link(ob, parent)
    ob.location = loc
    ob.scale = size
    so = ob.modifiers.new("dicke", "SOLIDIFY")
    so.thickness = 0.03
    so.offset = 1.0
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    return ob


def unit_to_local(size, c, loc=(0, 0, 0)):
    return Vector((c[0] * size[0] + loc[0], c[1] * size[1] + loc[1], c[2] * size[2] + loc[2]))


def band_lens(name, size, z_c, half_h, x_gap, m, parent, loc=(0, 0, 0), grow=1.07, ang=1.15):
    """Wraparound-Brillenglas: Ausschnitt einer leicht größeren Kopfkugel in Augenhöhe."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=192, v_segments=128, radius=grow)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median() / grow
        a = math.atan2(c.x, c.y)
        if c.y <= 0 or abs(a) > ang or abs(c.z - z_c) > half_h * (1 - 0.35 * (abs(a) / ang) ** 2) or abs(c.x) < x_gap:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    link(ob, parent)
    ob.location = loc
    ob.scale = size
    so = ob.modifiers.new("dicke", "SOLIDIFY")
    so.thickness = 0.04
    return ob


def half_sphere(name, up, scale, m, parent):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.5)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z * up < -1e-4], context="VERTS")
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.scale = scale
    link(ob, parent)
    so = ob.modifiers.new("dicke", "SOLIDIFY")
    so.thickness = 0.01
    return ob


def build_minoman(loc):
    """Mino Man nach dem Originalbild: langes schmales Gesicht, Seitenscheitel mit hoher Stirn, große Ohren,
    schmale pinke Wraparound-Brille mit dunklen Gläsern, Schnurrbart-Schatten, Navy-Anzug, Magenta-Krawatte."""
    R = empty("MinoMan", loc)
    suit = mat("Anzug", "#1b2238", 0.55)
    shirt = mat("Hemd", "#eef0f4", 0.6)
    tie_m, nt, out = node_mat("Krawatte")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 28
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeValToRGB")
    rr.color_ramp.elements[0].position, rr.color_ramp.elements[0].color = 0.08, hexcol("#d9b8e6")
    rr.color_ramp.elements[1].position, rr.color_ramp.elements[1].color = 0.12, hexcol("#7a1450")
    nt.links.new(vor.outputs["Distance"], rr.inputs["Fac"])
    nt.links.new(rr.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs[0])
    torso = prim("cube", "MM_torso", (0, 0, 1.15), (0.56, 0.3, 0.62), m=suit, parent=R, bevel=0.08, subsurf=1)
    prim("cube", "MM_hemd", (0, 0.135, 1.32), (0.16, 0.05, 0.3), m=shirt, parent=R, bevel=0.02)
    tie = prim("cube", "MM_krawatte", (0, 0.165, 1.25), (0.075, 0.03, 0.38), m=tie_m, parent=R, bevel=0.01)
    prim("cube", "MM_knoten", (0, 0.17, 1.44), (0.07, 0.035, 0.06), m=tie_m, parent=R, bevel=0.01)
    for sx in (-1, 1):   # Revers
        prim("cube", "MM_revers%d" % sx, (sx * 0.12, 0.15, 1.3), (0.1, 0.03, 0.34), rot=(0, sx * 0.35, 0), m=suit, parent=R, bevel=0.01)
    arms = {}
    for sx in (-1, 1):
        sh = empty("MM_schulter%d" % sx, (sx * 0.3, 0, 1.38), R)
        prim("cyl", "MM_oberarm%d" % sx, (0, 0, -0.2), (0.15, 0.15, 0.42), m=suit, parent=sh, bevel=0.02)
        el = empty("MM_ellbogen%d" % sx, (0, 0, -0.4), sh)
        prim("cyl", "MM_unterarm%d" % sx, (0, 0, -0.18), (0.13, 0.13, 0.38), m=suit, parent=el)
        prim("sphere", "MM_hand%d" % sx, (0, 0, -0.4), (0.1, 0.08, 0.12), m=skin_light, parent=el)
        arms[sx] = (sh, el)
    legs = {}
    shoe = mat("Schuh", "#121212", 0.3, coat=0.6)
    for sx in (-1, 1):
        hip = empty("MM_huefte%d" % sx, (sx * 0.13, 0, 0.84), R)
        prim("cyl", "MM_oberschenkel%d" % sx, (0, 0, -0.21), (0.19, 0.21, 0.46), m=suit, parent=hip)
        knee = empty("MM_knie%d" % sx, (0, 0, -0.42), hip)
        prim("cyl", "MM_unterschenkel%d" % sx, (0, 0, -0.2), (0.17, 0.18, 0.42), m=suit, parent=knee)
        prim("cube", "MM_schuh%d" % sx, (0, 0.05, -0.4), (0.13, 0.28, 0.08), m=shoe, parent=knee, bevel=0.03)
        legs[sx] = (hip, knee)
    neck = empty("MM_hals", (0, 0.02, 1.47), R)
    prim("cyl", "MM_halszyl", (0, 0, 0.05), (0.13, 0.13, 0.14), m=skin_light, parent=neck)
    prim("cyl", "MM_kragen", (0, 0, 0.0), (0.16, 0.16, 0.06), m=shirt, parent=neck)
    head = empty("MM_kopf", (0, 0, 0.12), neck)
    # Kopf nach dem Originalbild: lang und schmal, hohe Stirn, lange gerade Nase, schmales Kinn, große Ohren
    HS = (0.135, 0.15, 0.2)
    HL = (0, 0, 0.17)
    MM_DEF = [
        ((0, 0.9, 0.45), 0.4, (0, 0.04, 0.05)),          # Stirn
        ((0.33, 0.93, 0.18), 0.2, (0, -0.1, 0)), ((-0.33, 0.93, 0.18), 0.2, (0, -0.1, 0)),   # Augenhöhlen
        ((0, 1.0, 0.12), 0.13, (0, 0.12, 0)),             # Nasenrücken
        ((0, 1.0, -0.12), 0.17, (0, 0.3, -0.02)),         # Nasenspitze, lang
        ((0.12, 0.95, -0.2), 0.1, (0.02, 0.1, 0)), ((-0.12, 0.95, -0.2), 0.1, (-0.02, 0.1, 0)),
        ((0.5, 0.75, 0.0), 0.3, (0.03, 0.05, 0)), ((-0.5, 0.75, 0.0), 0.3, (-0.03, 0.05, 0)),   # Wangenknochen
        ((0.55, 0.5, -0.6), 0.4, (-0.12, 0, 0)), ((-0.55, 0.5, -0.6), 0.4, (0.12, 0, 0)),       # schmaler Kiefer
        ((0, 0.92, -0.82), 0.25, (0, 0.06, -0.06)),       # Kinn
        ((0, 0.95, -0.45), 0.25, (0, 0.05, 0)),           # Mundpartie
    ]
    face_skin = noise_mat("HautMM", "#d9a98f", "#e8bea6", scale=30, rough=0.5, bump=0.05, sss=0.2)
    skull = sculpt_head("MM_kopfmesh", HS, MM_DEF, (-0.5, 0.2, 0.012), face_skin, mat("LippenMM", "#b07068", 0.45),
                        mat("Mundhoehle", "#2a0508", 0.6), head, loc=HL, open_keys=False, hole=False)
    curve_obj("MM_lippen", [unit_to_local(HS, c, HL) for c in ((-0.2, 0.97, -0.5), (0, 1.03, -0.49), (0.2, 0.97, -0.5))],
              radius=0.006, m=mat("LippenMM", "#b07068", 0.45), parent=head)
    for sx in (-1, 1):
        prim("sphere", "MM_ohr%d" % sx, (sx * 0.135, -0.005, 0.17), (0.04, 0.085, 0.12), rot=(0, sx * 0.25, 0), m=face_skin, parent=head)
    hair = noise_mat("HaarBraun", "#2a1c14", "#4a3424", scale=40, rough=0.7, bump=0.4)

    def mm_hairline(x, y):
        front = smooth((y + 0.2) / 0.9)
        return lerp(-0.25, 0.62 - 0.12 * smooth((x + 0.2) / 0.6), front)   # hohe Stirn, Scheitel links

    hair_cap("MM_haar", HS, MM_DEF, mm_hairline, hair, head, loc=HL, grow=1.05,
             extra=[((-0.35, 0.55, 0.8), 0.35, (0.05, 0.05, 0.12)), ((0.2, 0.3, 0.9), 0.5, (0, 0, 0.08))])
    stub = mat("Bartschatten", "#6a4a3a", 0.8)
    curve_obj("MM_schnurrbart", [unit_to_local(HS, c, HL) for c in ((-0.25, 0.96, -0.38), (0, 1.02, -0.33), (0.25, 0.96, -0.38))],
              radius=0.007, m=stub, parent=head)
    mouth = skull
    # Brille: zwei schmale dunkle Wraparound-Gläser, pinker Rahmen oben und unten, Steg
    frame_m = mat("BrilleRahmen", "#e2558c", 0.3, coat=0.8)
    lens = mat("Glaeser", "#14060c", 0.05, coat=1.0, spec=1.0)
    band_lens("MM_glaeser", HS, 0.17, 0.085, 0.06, lens, head, loc=HL, grow=1.1, ang=1.05)
    band_lens("MM_rahmen", HS, 0.17, 0.105, 0.0, frame_m, head, loc=HL, grow=1.09, ang=1.2)
    glint = prim("sphere", "MM_reflex", unit_to_local(HS, (0.32, 1.12, 0.2), HL), (0.02, 0.006, 0.01), m=emit_mat("Reflex", "#ffffff", 30), parent=head)
    return {"root": R, "head": head, "neck": neck, "arms": arms, "legs": legs, "mouth": mouth, "glint": glint, "torso": torso}


# ------------------------------------------------------------------ Realistischer Chicken-Guy-Kopf (MakeHuman hm08, CC0; Daten aus build_cg_head.py)
CG_HEAD_DIR = os.path.abspath(opt("--cghead", os.path.join(HERE, "cghead")))


def _img_node(nt, path, alpha=False, noncolor=False):
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    return tx


def cg_head_mats(d, meta):
    """Haut mit Textur + Subsurface + Poren, nasse Augen, Zähne, Zunge, Brauen/Wimpern mit Alpha."""
    T = {k: os.path.join(d, v) for k, v in meta["textures"].items()}
    mats = {}
    # Haut
    m, nt, out = node_mat("CG_Haut")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tx = _img_node(nt, T["skin"])
    # etwas dunkler und wärmer als die Vorlage, wie im Video
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Hue"].default_value = 0.49
    hsv.inputs["Saturation"].default_value = 0.95
    hsv.inputs["Value"].default_value = float(opt("--cgskin", 0.86))
    nt.links.new(tx.outputs["Color"], hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], b.inputs["Base Color"])
    bsdf_input(b, "Roughness").default_value = 0.5
    try:
        bsdf_input(b, "Subsurface Weight", "Subsurface").default_value = 0.25
        bsdf_input(b, "Subsurface Radius").default_value = (1.0, 0.4, 0.22)
        bsdf_input(b, "Subsurface Scale").default_value = 0.02
    except Exception:   # noqa: BLE001
        pass
    try:
        bsdf_input(b, "Specular IOR Level", "Specular").default_value = 0.35
        bsdf_input(b, "Coat Weight").default_value = 0.0
        bsdf_input(b, "Coat Roughness").default_value = 0.3
    except Exception:   # noqa: BLE001
        pass
    # Poren und feine Unebenheiten
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.12
    bp.inputs["Distance"].default_value = 0.0004
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs[0], out.inputs[0])
    mats["skin"] = m
    # Zähne (leicht gelblich, glänzend), Zunge/Zahnfleisch
    for key, rough, coat in (("teeth", 0.25, 0.5), ("tongue", 0.35, 0.6)):
        m, nt, out = node_mat("CG_" + key)
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tx = _img_node(nt, T[key])
        nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
        bsdf_input(b, "Roughness").default_value = rough
        try:
            bsdf_input(b, "Coat Weight").default_value = coat
        except Exception:   # noqa: BLE001
            pass
        nt.links.new(b.outputs[0], out.inputs[0])
        mats[key] = m
    # Brauen, Wimpern: Textur mit Alpha
    for key, col in (("brows", "#0a0604"), ("lashes", "#050302")):
        m, nt, out = node_mat("CG_" + key)
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = hexcol(col)
        bsdf_input(b, "Roughness").default_value = 0.6
        tx = _img_node(nt, T[key])
        nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
        nt.links.new(b.outputs[0], out.inputs[0])
        for attr, v in (("surface_render_method", "DITHERED"), ("blend_method", "HASHED")):
            if hasattr(m, attr):
                try:
                    setattr(m, attr, v)
                except Exception:   # noqa: BLE001
                    pass
        if hasattr(m, "shadow_method"):
            m.shadow_method = "HASHED"
        mats[key] = m
    # kurz geschorene Haare: fast schwarz, feine Stoppel-Struktur
    m, nt, out = node_mat("CG_Haare")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2500.0
    nz.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#040303")
    ramp.color_ramp.elements[1].color = hexcol("#120d0a")
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bsdf_input(b, "Roughness").default_value = 0.85
    bsdf_input(b, "Specular IOR Level", "Specular").default_value = 0.2
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.001
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs[0], out.inputs[0])
    mats["hair"] = m
    # Augen: Iris-Textur, nasse Hornhaut
    m, nt, out = node_mat("CG_Auge")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tx = _img_node(nt, T["eyes"])
    ehsv = nt.nodes.new("ShaderNodeHueSaturation")
    ehsv.inputs["Saturation"].default_value = 0.8      # weniger rote Äderchen
    ehsv.inputs["Value"].default_value = 1.1
    nt.links.new(tx.outputs["Color"], ehsv.inputs["Color"])
    nt.links.new(ehsv.outputs["Color"], b.inputs["Base Color"])
    bsdf_input(b, "Roughness").default_value = 0.15
    try:
        bsdf_input(b, "Coat Weight").default_value = 1.0
        bsdf_input(b, "Coat Roughness").default_value = 0.02
    except Exception:   # noqa: BLE001
        pass
    nt.links.new(b.outputs[0], out.inputs[0])
    mats["eyes"] = m
    return mats


def _mesh_from(name, verts, flen, fverts, uv, fmat=None):
    me = bpy.data.meshes.new(name)
    n = len(flen)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.reshape(-1))
    me.loops.add(len(fverts))
    me.loops.foreach_set("vertex_index", fverts)
    me.polygons.add(n)
    starts = np.zeros(n, np.int32)
    starts[1:] = np.cumsum(flen)[:-1]
    me.polygons.foreach_set("loop_start", starts)
    if hasattr(me.polygons[0] if n else None, "loop_total"):
        try:
            me.polygons.foreach_set("loop_total", flen)
        except Exception:   # noqa: BLE001
            pass
    if fmat is not None:
        me.polygons.foreach_set("material_index", fmat)
    lay = me.uv_layers.new(name="UVMap")
    lay.data.foreach_set("uv", uv.reshape(-1))
    me.polygons.foreach_set("use_smooth", np.ones(n, bool))
    me.update(calc_edges=True)
    me.validate()
    return me


def load_cg_head(parent):
    """Realistischer Kopf (MakeHuman hm08, CC0) mit Ausdrucks-Shape-Keys. None, wenn die Daten fehlen."""
    path = os.path.join(CG_HEAD_DIR, "cg_head.npz")
    if not os.path.exists(path):
        print("Chicken-Guy-Kopf: keine Daten in", CG_HEAD_DIR, "-> alter Kopf")
        return None
    D = np.load(path)
    meta = json.load(open(os.path.join(CG_HEAD_DIR, "cg_head.json")))
    mats = cg_head_mats(CG_HEAD_DIR, meta)
    me = _mesh_from("CG_kopf_real", D["verts"], D["face_len"], D["face_verts"], D["uv"], D["face_mat"])
    for p in meta["parts"]:
        me.materials.append(mats[p])
    ob = bpy.data.objects.new("CG_kopf_real", me)
    link(ob, parent)
    sub = ob.modifiers.new("glatt", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    ob.shape_key_add(name="Basis", from_mix=False)
    base = D["verts"]
    for k in meta["keys"]:
        sk = ob.shape_key_add(name=k, from_mix=False)
        co = base.copy()
        co[D["key_idx:" + k]] += D["key_d:" + k]
        sk.data.foreach_set("co", co.reshape(-1))
        sk.slider_max = 1.6
        sk.slider_min = -0.5
        sk.value = 0.0          # neue Keys stehen in Blender 5 sonst teils auf 1
    # Mundhöhle: dunkles Rot hinter Zähnen und Zunge (das Basismesh ist innen offen)
    mc = Vector(meta["mouth"])
    cav = prim("sphere", "CG_mundhoehle", (mc.x, mc.y + 0.028, mc.z - 0.012), (0.062, 0.1, 0.07), m=mat("MundhoehleCG", "#7a1c26", 0.5, emit="#5a0c14", estr=0.15),
               parent=parent)
    eyes = {}
    ev = D["eye_verts"]
    for side, sgn in (("L", 1), ("R", -1)):
        c = Vector(meta["eye_centers"][side])
        piv = empty("CG_augpiv_" + side, c, parent)
        # nur die Faces des richtigen Auges behalten
        fl_, fv_, uv_ = D["eye_face_len"], D["eye_face_verts"], D["eye_uv"]
        st_ = np.concatenate([[0], np.cumsum(fl_)[:-1]])
        keepf = [i for i in range(len(fl_)) if ev[fv_[st_[i]], 0] * sgn > 0]
        used = sorted({int(v) for i in keepf for v in fv_[st_[i]:st_[i] + fl_[i]]})
        rm = {v: n for n, v in enumerate(used)}
        nfv = np.array([rm[int(v)] for i in keepf for v in fv_[st_[i]:st_[i] + fl_[i]]], np.int32)
        nuv = np.concatenate([uv_[st_[i]:st_[i] + fl_[i]] for i in keepf])
        emesh = _mesh_from("CG_auge_" + side, ev[used] - np.array(c, np.float32), fl_[keepf], nfv, nuv)
        emesh.materials.append(mats["eyes"])
        eo = bpy.data.objects.new("CG_auge_" + side, emesh)
        link(eo, piv)
        eyes[side] = piv
    return {"obj": ob, "keys": ob.data.shape_keys.key_blocks, "eyes": eyes, "meta": meta, "cav": cav}


CG_BZ, CG_BS = 0.8, (1.25, 1.25, 1.2)
CG_HEAD_S = float(opt("--cghs", 3.1))     # Kopf deutlich zu groß fürs Hähnchen, wie im Original
CG_HEAD_Z = float(opt("--cghz", 0.16))


def build_chickenguy(loc):
    """Chicken Guy nach dem Original: riesiger ovaler Kopf auf einem knusprigen Brathähnchen,
    dürre Flügelarme, Keulenbeine. Das Gesicht hat ein eigenes Rig: Kiefer, Mundhöhle mit Zahnlücke, Zunge,
    Lider, Brauen, Wangen – für Schreien, Grimassen, Augen-zu-Ekstase."""
    R = empty("ChickenGuy", loc)
    crisp = noise_mat("Kruste", "#4a1f08", "#b5651c", scale=16, rough=0.38, bump=1.0, c2="#e8a848", detail=12)   # paniert, knusprig
    bone_m = mat("Knochen", "#efe6d2", 0.6)
    # Proportionen wie im Original: dickes Hähnchen, Kopf sitzt ohne Hals direkt obendrauf
    body = empty("CG_koerper", (0, 0, CG_BZ), R)
    body.scale = CG_BS
    torso = prim("sphere", "CG_rumpf", (0, 0, 0.0), (0.62, 0.52, 0.7), m=crisp, parent=body, seg=32)
    dsp = torso.modifiers.new("klumpig", "DISPLACE")
    tex = bpy.data.textures.new("Klumpen", "CLOUDS")
    tex.noise_scale = 0.18
    dsp.texture = tex
    dsp.strength = 0.05
    for sx in (-1, 1):
        prim("sphere", "CG_brust%d" % sx, (sx * 0.09, 0.14, 0.04), (0.32, 0.24, 0.4), m=crisp, parent=body)
    prim("sphere", "CG_buerzel", (0, -0.2, -0.28), (0.28, 0.24, 0.2), m=crisp, parent=body)
    legs = {}
    for sx in (-1, 1):
        hip = empty("CG_huefte%d" % sx, (sx * 0.2, 0.05, -0.25), body)
        prim("sphere", "CG_keule%d" % sx, (0, 0, -0.14), (0.2, 0.2, 0.34), m=crisp, parent=hip)
        prim("cyl", "CG_knochen%d" % sx, (0, 0, -0.38), (0.06, 0.06, 0.2), m=bone_m, parent=hip, seg=12)
        for k in (-1, 1):
            prim("sphere", "CG_knubbel%d%d" % (sx, k), (k * 0.025, 0, -0.49), (0.06, 0.06, 0.06), m=bone_m, parent=hip, seg=12)
        legs[sx] = hip
    wings = {}
    for sx in (-1, 1):
        sh = empty("CG_schulter%d" % sx, (sx * 0.42, 0.0, 0.28), body)
        prim("cyl", "CG_oberfluegel%d" % sx, (sx * 0.17, 0, 0), (0.07, 0.07, 0.36), rot=(0, math.radians(90), 0), m=crisp, parent=sh, seg=12)
        el = empty("CG_ellbogen%d" % sx, (sx * 0.34, 0, 0), sh)
        prim("cyl", "CG_unterfluegel%d" % sx, (sx * 0.16, 0, 0), (0.055, 0.055, 0.32), rot=(0, math.radians(90), 0), m=crisp, parent=el, seg=12)
        tip = empty("CG_hand%d" % sx, (sx * 0.31, 0, 0), el)
        prim("cone", "CG_spitze%d" % sx, (sx * 0.06, 0, 0), (0.07, 0.04, 0.14), rot=(0, math.radians(90 * sx), 0), m=crisp, parent=tip, seg=10)
        wings[sx] = (sh, el, tip)
    neck = empty("CG_hals", (0, 0.04, 0.3), body)
    head = empty("CG_kopf", (0, 0.0, 0.12), neck)
    head.scale = (0.66, 0.66, 0.69)
    REAL = None if opt("--oldcg", flag=True) else load_cg_head(head)
    if REAL:
        head.scale = (CG_HEAD_S, CG_HEAD_S, CG_HEAD_S)
        head.location = (0, 0.06, CG_HEAD_Z)
        return {"root": R, "body": body, "torso": torso, "neck": neck, "head": head, "wings": wings, "legs": legs, "real": REAL}
    # großer ovaler Kopf nach dem Original: breite Nase, volle Lippen, kurze Haare, große Mundöffnung
    HS = (0.31, 0.3, 0.39)
    HL = (0, 0, 0.36)
    # nach dem Video: Ei-Form, unten breit (volle Wangen, Hängebacken), oben schmaler; kleine Augen unter schweren
    # Lidern, kurze breite Nase mit weiten Nasenlöchern, dicke Lippen, sehr großer Schreimund
    CG_DEF = [
        ((0, 0.9, 0.5), 0.4, (0, 0.02, 0.02)),
        ((0.6, 0.35, 0.6), 0.45, (-0.07, 0, 0)), ((-0.6, 0.35, 0.6), 0.45, (0.07, 0, 0)),          # Stirn schmaler
        ((0.33, 0.93, 0.2), 0.17, (0, -0.1, 0)), ((-0.33, 0.93, 0.2), 0.17, (0, -0.1, 0)),          # tiefe Augenhöhlen
        ((0.33, 0.95, 0.31), 0.16, (0, 0.05, -0.02)), ((-0.33, 0.95, 0.31), 0.16, (0, 0.05, -0.02)),  # schwere Oberlider
        ((0, 0.97, 0.38), 0.3, (0, 0.04, 0)),             # Brauenwulst
        ((0, 1.0, 0.06), 0.11, (0, 0.06, 0)),
        ((0, 1.0, -0.1), 0.2, (0, 0.22, -0.03)),          # kurze, breite Nase
        ((0.19, 0.95, -0.15), 0.14, (0.06, 0.1, 0)), ((-0.19, 0.95, -0.15), 0.14, (-0.06, 0.1, 0)),   # Nasenflügel
        ((0.45, 0.8, -0.18), 0.3, (0.07, 0.08, 0)), ((-0.45, 0.8, -0.18), 0.3, (-0.07, 0.08, 0)),     # volle Wangen
        ((0.55, 0.65, -0.5), 0.38, (0.17, 0.05, -0.02)), ((-0.55, 0.65, -0.5), 0.38, (-0.17, 0.05, -0.02)),  # Hängebacken
        ((0.72, 0.25, -0.55), 0.45, (0.12, 0, 0)), ((-0.72, 0.25, -0.55), 0.45, (-0.12, 0, 0)),              # unten breit
        ((0, 0.95, -0.47), 0.32, (0, 0.16, 0)),           # dicke Mundpartie
        ((0, 0.9, -0.84), 0.34, (0, 0.03, -0.02)),        # rundes, breites Kinn
        ((0, 0.5, -0.98), 0.5, (0, 0, 0.07)),
        ((0.62, 0.4, -0.45), 0.45, (0.1, 0, 0)), ((-0.62, 0.4, -0.45), 0.45, (-0.1, 0, 0)),
        ((0, 0.0, 1.0), 0.5, (0, 0, -0.06)),
    ]
    skin_cg = noise_mat("HautCG", "#7d4c31", "#9a6442", scale=25, rough=0.42, bump=0.04, sss=0.2)
    skull = sculpt_head("CG_kopfmesh", HS, CG_DEF, (-0.47, 0.34, 0.04), skin_cg, mat("LippenCG", "#8e4c46", 0.45),
                        mat("InnenlippeCG", "#e08a96", 0.4, sss=0.3), head, loc=HL, open_amt=0.7, seg=(128, 96))
    hair = noise_mat("HaarSchwarz", "#060606", "#1a1512", scale=60, rough=0.8, bump=0.5)
    hair_cap("CG_haar", HS, CG_DEF, lambda x, y: lerp(-0.1, 0.56 - 0.05 * (1 - abs(x)), smooth((y + 0.3) / 0.9)), hair, head, loc=HL, grow=1.025)
    for sx in (-1, 1):
        prim("sphere", "CG_ohr%d" % sx, (sx * 0.3, -0.02, 0.36), (0.07, 0.11, 0.16), rot=(0, sx * 0.2, 0), m=skin_cg, parent=head)
    cheeks = []
    # Augen mit Lidern (in den Augenhöhlen)
    eye_w = mat("Augenweiss", "#efe9e2", 0.25, coat=0.6)
    iris = mat("Iris", "#1b0f0a", 0.2, coat=1.0)
    eyes = {}
    lid_m = skin_cg
    crease_m = mat("Falte", "#3a1e12", 0.7)
    lash_m = mat("Wimpern", "#0b0605", 0.6)
    for sx in (-1, 1):
        ec = empty("CG_auge%d" % sx, unit_to_local(HS, (sx * 0.33, 0.77, 0.21), HL), head)
        prim("sphere", "CG_augapfel%d" % sx, (0, 0, 0), (0.088, 0.068, 0.062), m=eye_w, parent=ec)
        pup = prim("sphere", "CG_pupille%d" % sx, (0, 0.025, 0), (0.05, 0.02, 0.05), m=iris, parent=ec)
        glz = prim("sphere", "CG_glanz%d" % sx, (0.01, 0.038, 0.012), (0.01, 0.005, 0.01), m=emit_mat("Glanz", "#ffffff", 8), parent=ec)
        lids = []
        for up in (1, -1):
            piv = empty("CG_lid%d%d" % (sx, up), (0, -0.004, 0), ec)
            lid = half_sphere("CG_lidhaut%d%d" % (sx, up), up, (0.104, 0.086, 0.08), lid_m, piv)   # flach: zu = Schlitz
            if up > 0:   # dunkle Wimpernlinie an der Lidkante, damit zugekniffene Augen lesbar sind
                arc = [Vector((0.054 * math.cos(a), 0.052 * math.sin(a), 0.0)) for a in
                       (math.radians(d) for d in range(15, 170, 15))]
                curve_obj("CG_wimper%d" % sx, arc, radius=0.007, m=lash_m, parent=piv)
            lids.append(piv)
        # Falten beim Zukneifen: Krähenfüße außen, Falte unterm Auge, Knick am Nasenrücken
        creases = []
        for k, (pts, rad) in enumerate((
                ([(sx * 0.06, 0.02, 0.01), (sx * 0.085, 0.0, 0.02), (sx * 0.1, -0.02, 0.035)], 0.005),
                ([(sx * 0.06, 0.02, -0.012), (sx * 0.088, 0.0, -0.02), (sx * 0.1, -0.02, -0.04)], 0.005),
                ([(-sx * 0.04, 0.045, -0.04), (0, 0.05, -0.05), (sx * 0.05, 0.04, -0.04)], 0.006),
                ([(-sx * 0.075, 0.035, 0.03), (-sx * 0.085, 0.035, 0.0)], 0.005))):
            cr = curve_obj("CG_falte%d%d" % (sx, k), [Vector(q) for q in pts], radius=rad, m=crease_m, parent=ec)
            creases.append(cr)
        brow = curve_obj("CG_braue%d" % sx, [Vector((-0.07, 0, -0.012)), Vector((0, 0, 0.012)), Vector((0.07, 0, -0.012))],
                         radius=0.009, m=mat("BraueCG", "#2a1810", 0.7), parent=empty("CG_braue_piv%d" % sx, unit_to_local(HS, (sx * 0.34, 0.97, 0.43), HL), head))
        eyes[sx] = {"c": ec, "pupil": pup, "lids": lids, "brow": brow.parent, "glanz": glz, "creases": creases}
    # Mundinneres: dunkle Höhle, obere Zähne mit Lücke, Unterkiefer mit Zähnen und Zunge
    mouth = empty("CG_mund", unit_to_local(HS, (0, 0.8, -0.46), HL), head)
    cav = prim("sphere", "CG_mundhoehle", (0, -0.05, -0.04), (0.24, 0.15, 0.22), m=mat("MundhoehleCG", "#3a0a10", 0.6), parent=mouth)
    teeth_m = mat("ZaehneCG", "#ece0bf", 0.3, coat=0.4)
    uteeth = empty("CG_zaehne_oben", (0, 0.0, 0.0), mouth)
    # zwei große Schneidezähne mit Lücke, daneben kleinere – wie im Video
    for i, (x, w_, h_) in enumerate(((-0.072, 0.024, 0.026), (-0.04, 0.03, 0.036), (0.04, 0.03, 0.036), (0.072, 0.024, 0.026))):
        prim("cube", "CG_zahn_o%d" % i, (x, 0.0, -0.004 - (h_ - 0.026) * 0.5), (w_, 0.018, h_), m=teeth_m, parent=uteeth, bevel=0.005)
    jaw = empty("CG_kiefer", (0, -0.01, 0.0), mouth)
    for i, x in enumerate((-0.06, -0.022, 0.022, 0.06)):
        prim("cube", "CG_zahn_u%d" % i, (x, 0.0, 0.0), (0.024, 0.014, 0.022), m=teeth_m, parent=jaw, bevel=0.004)
    tongue = prim("sphere", "CG_zunge", (0, -0.02, -0.01), (0.17, 0.12, 0.06), m=mat("ZungeCG", "#e07a88", 0.35, sss=0.3), parent=jaw)
    upper = lower = None
    return {"root": R, "body": body, "torso": torso, "neck": neck, "head": head, "eyes": eyes, "mouth": mouth, "cav": cav,
            "skull": skull, "upper": upper, "lower": lower, "jaw": jaw, "tongue": tongue, "wings": wings, "legs": legs, "cheeks": cheeks, "uteeth": uteeth}


def build_munch(loc):
    R = empty("Munch", loc)
    coat = noise_mat("Trenchcoat", "#7a5f3a", "#8e7046", scale=20, rough=0.8, bump=0.15)
    prim("cube", "MU_mantel", (0, 0, 0.85), (0.62, 0.4, 1.1), m=coat, parent=R, bevel=0.1, subsurf=1)
    prim("sphere", "MU_bauch", (0, 0.12, 0.85), (0.6, 0.45, 0.6), m=coat, parent=R)
    prim("cube", "MU_guertel", (0, 0.0, 0.85), (0.66, 0.46, 0.06), m=mat("Guertel", "#3a2a1a", 0.6), parent=R)
    for sx in (-1, 1):
        prim("cyl", "MU_bein%d" % sx, (sx * 0.14, 0, 0.18), (0.16, 0.16, 0.36), m=mat("Hose", "#1a1a1e", 0.7), parent=R)
    arm = empty("MU_arm", (0.33, 0.05, 1.3), R)
    prim("cyl", "MU_oberarm", (0, 0, -0.2), (0.15, 0.15, 0.42), m=coat, parent=arm)
    fore = empty("MU_unterarm", (0, 0, -0.4), arm)
    prim("cyl", "MU_ua", (0, 0, -0.17), (0.13, 0.13, 0.36), m=coat, parent=fore)
    folder = akte("MU_akte", (0, 0.0, -0.36), col="#d9b77a", label="CASE 001", parent=fore, scale=1.0)
    folder.rotation_euler = (math.radians(80), 0, 0)
    head = empty("MU_kopf", (0, 0.02, 1.55), R)
    prim("sphere", "MU_schaedel", (0, 0, 0.12), (0.4, 0.4, 0.44), m=skin_light, parent=head, seg=32)
    prim("sphere", "MU_nase", (0, 0.2, 0.1), (0.1, 0.09, 0.08), m=mat("NaseRot", "#d07a70", 0.5, sss=0.2), parent=head)
    cap = mat("Muetze", "#1d2a4a", 0.5)
    prim("cyl", "MU_muetze", (0, 0, 0.32), (0.44, 0.44, 0.12), m=cap, parent=head)
    prim("cyl", "MU_schirm", (0, 0.12, 0.27), (0.4, 0.3, 0.02), m=mat("Schirm", "#0c0c10", 0.3), parent=head)
    prim("cube", "MU_abzeichen", (0, 0.22, 0.33), (0.06, 0.01, 0.05), m=mat("Gold", "#d8a72a", 0.3, metal=1.0), parent=head)
    for sx in (-1, 1):   # müde, halb geschlossene Augen
        prim("sphere", "MU_auge%d" % sx, (sx * 0.08, 0.18, 0.15), (0.07, 0.03, 0.02), m=mat("MuedeAugen", "#2a1a1a", 0.4), parent=head)
        prim("sphere", "MU_sack%d" % sx, (sx * 0.08, 0.18, 0.12), (0.08, 0.03, 0.025), m=mat("Augenring", "#b07f78", 0.6), parent=head)
    jaw = prim("sphere", "MU_mund", (0, 0.19, 0.0), (0.1, 0.03, 0.03), m=mat("Mundhoehle", "#2a0508", 0.6), parent=head)
    crumbs = []
    for i in range(10):
        crumbs.append(prim("cube", "MU_kruemel%d" % i, (0, 0, -5), (0.018, 0.018, 0.004), m=paper_m))
    return {"root": R, "head": head, "arm": arm, "fore": fore, "folder": folder, "jaw": jaw, "crumbs": crumbs}


def build_grandma(loc):
    """Platzhalter, bis der echte Pepsi-Grandma-Clip da ist."""
    R = empty("Grandma", loc)
    prim("cube", "GM_jacke", (0, 0, 0.95), (0.5, 0.32, 0.6), m=mat("Strick", "#d58aa6", 0.9), parent=R, bevel=0.08, subsurf=1)
    prim("cone", "GM_rock", (0, 0, 0.45), (0.62, 0.45, 0.6), m=mat("Rock", "#4a2a46", 0.8), parent=R)
    head = empty("GM_kopf", (0, 0, 1.38), R)
    prim("sphere", "GM_schaedel", (0, 0, 0.1), (0.3, 0.3, 0.34), m=skin_light, parent=head)
    for i in range(16):
        a = i / 16 * math.tau
        prim("ico", "GM_locke%d" % i, (math.cos(a) * 0.13, math.sin(a) * 0.12 - 0.02, 0.22 + hsh(i) * 0.06), (0.14, 0.14, 0.12),
             m=mat("Dauerwelle", "#cfcfd6", 0.9), parent=head)
    for sx in (-1, 1):
        prim("torus", "GM_brille%d" % sx, (sx * 0.06, 0.15, 0.12), (0.12, 0.12, 0.12), rot=(math.radians(90), 0, 0),
             m=mat("Gold", "#d8a72a", 0.3, metal=1.0), parent=head)
    arm = empty("GM_arm", (0.27, 0.05, 1.18), R)
    prim("cyl", "GM_aermel", (0, 0, -0.18), (0.12, 0.12, 0.38), m=mat("Strick", "#d58aa6", 0.9), parent=arm)
    bottle = empty("GM_flasche", (0, 0.05, -0.42), arm)
    prim("cyl", "GM_flaschenkoerper", (0, 0, 0.0), (0.09, 0.09, 0.24), m=mat("Cola", "#1f4fd0", 0.15, coat=1.0), parent=bottle)
    prim("cyl", "GM_banderole", (0, 0, 0.0), (0.095, 0.095, 0.06), m=mat("Banderole", "#e8e8e8", 0.4), parent=bottle)
    prim("cyl", "GM_hals", (0, 0, 0.16), (0.04, 0.04, 0.1), m=mat("Cola", "#1f4fd0", 0.15, coat=1.0), parent=bottle)
    foam = []
    fm = mat("Schaum", "#f6f2e8", 0.6, emit="#ffffff", estr=0.2)
    for i in range(40):
        foam.append(prim("ico", "GM_schaum%d" % i, (0, 0, -5), (0.06, 0.06, 0.06), m=fm))
    return {"root": R, "head": head, "arm": arm, "bottle": bottle, "foam": foam}



AKTEN_TEXT = ["CASE 001\nCHICKEN GUY\nSTATUS: MISSING", "CASE 017\nHOT DOG RAIN\n(VEGAN)\nSTATUS: PENDING",
              "FILE 404\nNOT FOUND", "CASE 002\nPEPSI GRANDMA\nAGAIN", "MEMO 033\nWEDNESDAY\nFOLLOWED TUESDAY",
              "CASE 009\nGOD\nABSENT", "MEMO 120\nDANCING\nPERMITTED"]
HIDE = Vector((0, 0, -80))

# ------------------------------------------------------------------ Figuren aufstellen
MM = build_minoman((0, 0, 0))
CG = build_chickenguy((0, 0, 0))
MU = build_munch((0, 0, 0))
GM = build_grandma((0, 0, 0))
CG_S = 0.85
MM_DESK = HERO[(1, 0, 0, 0, 1)]          # Mino Mans Kabine am Hauptgang


def seat_pos(h, z=0.0):
    return cw(h["cell"], (0, -0.1, z))


# Kollegen in den Kabinen am Gang (animiert: tippen, später Party)
WORKERS = []
SHIRTS = ["#ffd23a", "#ff4fa8", "#2fd0ff", "#7cff4a", "#ff7a2a", "#b05cff"]


def worker(name, h, shirt):
    cell = h["cell"]
    R = empty(name, seat_pos(h), rot=(0, 0, cell[2] + math.pi))     # schaut zum Schreibtisch
    sm = mat("Hemd_" + shirt, shirt, 0.8)
    prim("cube", name + "_torso", (0, 0.02, 0.86), (0.4, 0.24, 0.56), m=sm, parent=R, bevel=0.05)
    prim("cube", name + "_schenkel", (0, 0.22, 0.56), (0.36, 0.45, 0.16), m=PANTS_M, parent=R, bevel=0.03)
    prim("cube", name + "_schienbein", (0, 0.42, 0.28), (0.3, 0.12, 0.5), m=PANTS_M, parent=R, bevel=0.03)
    head = empty(name + "_kopf", (0, 0.03, 1.16), R)
    prim("sphere", name + "_schaedel", (0, 0, 0.14), (0.23, 0.25, 0.28), m=SKIN_W, parent=head, seg=16)
    prim("sphere", name + "_haar", (0, -0.02, 0.2), (0.245, 0.255, 0.2), m=HAIR_W, parent=head, seg=16)
    arms = {}
    for sx in (-1, 1):
        sh = empty(name + "_sh%d" % sx, (sx * 0.23, 0.02, 1.08), R)
        prim("cyl", name + "_oa%d" % sx, (0, 0, -0.15), (0.09, 0.09, 0.3), m=sm, parent=sh, seg=10)
        el = empty(name + "_el%d" % sx, (0, 0, -0.3), sh)
        prim("cyl", name + "_ua%d" % sx, (0, 0, -0.14), (0.08, 0.08, 0.28), m=sm, parent=el, seg=10)
        prim("sphere", name + "_hd%d" % sx, (0, 0, -0.3), (0.07, 0.06, 0.08), m=SKIN_W, parent=el, seg=10)
        arms[sx] = (sh, el)
    w = {"root": R, "head": head, "arms": arms, "seed": len(WORKERS), "rz": cell[2] + math.pi, "pos": seat_pos(h)}
    WORKERS.append(w)
    return w


for i, (key, h) in enumerate(sorted(HERO.items())):
    if h is MM_DESK:
        continue
    if hsh(i * 4.1 + 2) < 0.62:
        h["worker"] = worker("Kollege%02d" % i, h, SHIRTS[i % len(SHIRTS)])

# Pflanzen am Gang
PLANT_M = noise_mat("Blatt", "#2f7a32", "#58a83c", scale=12, rough=0.6, bump=0.2)
POT_M = mat("Topf", "#c86a3c", 0.7)
for i, y in enumerate((-1.3, 13.4, 28.2, 43.0)):
    for sx in (-1, 1):
        root = empty("Pflanze%d%d" % (i, sx), (sx * 1.15, y, 0))
        prim("cyl", "Topf%d%d" % (i, sx), (0, 0, 0.2), (0.4, 0.4, 0.4), m=POT_M, parent=root, seg=16)
        for k in range(7):
            prim("ico", "Laub%d%d%d" % (i, sx, k), ((hsh(k + i) - .5) * 0.4, (hsh(k * 3 + i) - .5) * 0.4, 0.6 + k * 0.12), (0.4, 0.4, 0.5),
                 m=PLANT_M, parent=root)

# Akten liegen organisch auf den Tischen (keine Pop-ups mehr)
for i, (key, h) in enumerate(sorted(HERO.items())):
    if h is MM_DESK:
        continue
    if hsh(i * 1.7) < 0.5:
        for j in range(1 + int(hsh(i) * 4)):
            akte("TischAkte%d_%d" % (i, j), cw(h["cell"], (0.6, -1.05, 0.76 + j * 0.026)), h["cell"][2] + (hsh(i + j) - .5) * 0.5,
                 label=AKTEN_TEXT[(i + j) % len(AKTEN_TEXT)] if j == 0 else None)

# fliegende Blätter (Party im Büro)
FLYERS = []
for i in range(50):
    ob = prim("plane", "Blatt%02d" % i, (0, 0, -50), (0.21, 0.297, 1), m=PAPER_M)
    FLYERS.append({"ob": ob, "seed": i})

# ------------------------------------------------------------------ Echte Clips als Videotexturen
CLIP_DIR = os.path.abspath(opt("--clips", os.path.join(HERE, "clips")))
CLIP_MATS = {}
CLIP_FALLBACK = {"cg": "#c4002a", "mm": "#1b3fa8", "gm": "#1f4fd0"}


def clip_mat(key, strength=1.5, offset=0):
    """Emissionsmaterial, das einen Clip abspielt (tex_<key>.mp4 im Clip-Ordner, Endlosschleife im Bildtakt).
    Fehlt die Datei (lokaler Test), gibt es einen farbigen Platzhalter mit Rauschen."""
    k = (key, offset)
    if k in CLIP_MATS:
        return CLIP_MATS[k]
    m, nt, out = node_mat("Clip_%s_%d" % (key, offset))
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[1].default_value = strength
    path = os.path.join(CLIP_DIR, "tex_%s.mp4" % key)
    if os.path.exists(path):
        img = bpy.data.images.load(path, check_existing=True)
        img.source = "MOVIE"
        img.colorspace_settings.name = "sRGB"
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        iu = tex.image_user
        iu.frame_duration = max(30, int(getattr(img, "frame_duration", 0) or 300))
        # Versatz über frame_start: frame_offset wird erst nach der Schleife addiert und friert dann auf dem letzten Bild ein
        iu.frame_start = 1 - offset % iu.frame_duration
        iu.frame_offset = 0
        iu.use_cyclic = True
        iu.use_auto_refresh = True
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0
        nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = hexcol(CLIP_FALLBACK.get(key, "#7a3cff"))
        ramp.color_ramp.elements[1].color = hexcol("#ffe34a")
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    CLIP_MATS[k] = m
    return m


# ------------------------------------------------------------------ Riesige Bildschirme (hängen vom Himmel oder fallen herab)
BIG_BEZEL = mat("Riesenrahmen", "#d6cdb9", 0.45, coat=0.25)
BIG_DARK = mat("Riesenrahmen_dunkel", "#2a2622", 0.5)
CABLE_M = mat("Stahlseil", "#3a3a3e", 0.35, metal=0.8)
BIGS = []


def big_screen(name, key, h=9.0, cables=True, label="MINO TV", offset=0):
    """Hochformat-Bildschirm wie ein Reel, beiger 90er-Rahmen. Vorderseite zeigt nach lokal +Y."""
    w = h * 9 / 16
    root = empty(name, HIDE)
    prim("cube", name + "_rahmen", (0, -0.3, 0), (w + 0.7, 0.6, h + 1.1), m=BIG_BEZEL, parent=root, bevel=0.18)
    prim("cube", name + "_rueck", (0, -1.0, 0.2), (w * 0.75, 0.9, h * 0.65), m=BIG_BEZEL, parent=root, bevel=0.25)
    prim("cube", name + "_kante", (0, 0.0, 0), (w + 0.12, 0.04, h + 0.12), m=BIG_DARK, parent=root)
    scr = prim("plane", name + "_bild", (0, 0.03, 0), (w, h, 1), rot=(math.radians(90), 0, math.pi), m=clip_mat(key, offset=offset), parent=root)
    no_shadow_obj(scr)
    if label:
        text(name + "_marke", label, size=0.32, m=emit_mat("Marke", "#3a3530", 0.0) if False else mat("Marke", "#5a524a", 0.5),
             parent=root, loc=(0, 0.02, -h / 2 - 0.3), rot=(math.radians(90), 0, math.pi), fnt="barlow")
    if cables:
        for sx in (-1, 1):
            prim("cyl", name + "_seil%d" % sx, (sx * w * 0.38, -0.3, h / 2 + 0.55 + 100), (0.07, 0.07, 200), m=CABLE_M, parent=root, seg=8)
    s = {"root": root, "screen": scr, "w": w, "h": h, "key": key}
    BIGS.append(s)
    return s


def no_shadow_obj(ob):
    if hasattr(ob, "visible_shadow"):
        ob.visible_shadow = False


def big_front(s, d=0.0):
    M = world_matrix(s["root"])
    return M @ Vector((0, 0.03 + d, 0))


def big_place(s, pos, rz, t, sway=1.0):
    s["root"].location = pos
    s["root"].rotation_euler = (math.sin(t * 0.9 + hsh(len(s["key"]))) * 0.03 * sway, math.sin(t * 0.6) * 0.02 * sway, rz)


def big_drop(s, b, b_land, pos, rz, t, h_fall=40.0):
    """Fällt vom Himmel und landet auf dem Schlag b_land, federt nach."""
    if b < b_land - 1.0:
        s["root"].location = Vector(pos) + Vector((0, 0, h_fall + 60))
        return
    if b < b_land:
        k = (b - (b_land - 1.0))
        z = h_fall * (1 - k * k)
        s["root"].location = Vector(pos) + Vector((0, 0, z))
    else:
        k = b - b_land
        z = abs(math.sin(k * math.pi * 1.6)) * math.exp(-k * 2.6) * 2.2
        s["root"].location = Vector(pos) + Vector((0, 0, z))
    s["root"].rotation_euler = (math.sin(t * 3) * 0.02 * max(0, 1 - (b - b_land)), 0, rz)


# Fünf Riesenschirme über dem Büro (Clips: Chicken Guy, Mino Man, Pepsi Grandma, alte Edits, Reels)
OFFICE_BIGS = [
    (big_screen("Riese0", "cg2", 10.0), Vector((-8.5, 30, 14.0)), math.pi + 0.25),
    (big_screen("Riese1", "mm", 9.0), Vector((9.5, 24, 12.5)), math.pi - 0.3),
    (big_screen("Riese2", "gm2", 11.0), Vector((-2.0, 58, 21.0)), math.pi),
    (big_screen("Riese3", "e1", 10.0), Vector((17.0, 50, 17.0)), math.pi - 0.45),
    (big_screen("Riese4", "ig1", 10.0), Vector((-19.0, 46, 18.0)), math.pi + 0.5),
    (big_screen("Riese5", "e2", 12.0), Vector((6.0, 88, 30.0)), math.pi),
]
# einer, der auf den Beat herabfällt und im Gang landet (Variante 2), und einer im All
DROP_BIG = big_screen("RieseFall", "mm", 7.0, cables=False, label="BREAKING", offset=40)
SPACE_BIG = big_screen("RieseAll", "cg2", 8.0, label="MINO TV", offset=80)


# ------------------------------------------------------------------ Die Akte auf Mino Mans Tisch (Variante 1)
def case_file(name, loc, rz, title, stamp, photo_key, scale=1.5):
    root = empty(name, loc, rot=(0, 0, rz))
    root.scale = (scale, scale, scale)
    W, D = 0.32, 0.24
    prim("cube", name + "_ruecken", (0, 0, 0.004), (W, D, 0.008), m=mat("Akte_manila", "#d9b77a", 0.8), parent=root)
    prim("cube", name + "_seite", (0.004, 0, 0.011), (W * 0.94, D * 0.92, 0.004), m=PAPER_M, parent=root)
    text(name + "_text", title, size=0.017, m=mat("Tinte", "#1a1a1a", 0.6), parent=root, loc=(0.045, 0.03, 0.0135), fnt="courier",
         align="LEFT")
    photo = prim("plane", name + "_foto", (-0.075, 0.0, 0.014), (0.1, 0.1 * 16 / 9, 1), rot=(0, 0, math.radians(-3)), m=clip_mat(photo_key, 1.2, 25),
                 parent=root)
    prim("cube", name + "_klammer", (-0.075, 0.085, 0.016), (0.012, 0.03, 0.003), m=mat("Klammer", "#b8b8c0", 0.3, metal=1.0), parent=root)
    st = text(name + "_stempel", stamp, size=0.032, m=mat("Stempelrot", "#c8142a", 0.6), parent=root, loc=(0.075, -0.07, 0.0136), fnt="anton")
    st.rotation_euler.z = 0.25
    hinge = empty(name + "_scharnier", (-W / 2, 0, 0.016), root)
    prim("cube", name + "_deckel", (W / 2, 0, 0), (W, D, 0.008), m=mat("Akte_manila", "#d9b77a", 0.8), parent=hinge)
    text(name + "_deckeltext", title.split("\n")[0] + "\n" + title.split("\n")[1], size=0.026, m=mat("Tinte", "#1a1a1a", 0.6), parent=hinge,
         loc=(W / 2, 0.02, 0.0045), fnt="courier")
    return {"root": root, "hinge": hinge, "photo": photo, "stamp": st}


CASE = case_file("FallAkte", cw(MM_DESK["cell"], (-0.55, -0.82, 0.765)), MM_DESK["cell"][2] + math.radians(8),
                 "CASE 001\nCHICKEN GUY\nSTATUS: MISSING\nLAST SEEN:\nHOT DOG FACTORY", "MISSING", "cg")


def photo_center(d=0.0):
    M = world_matrix(CASE["photo"])
    return M @ Vector((0, 0, d / 1.5))


# ------------------------------------------------------------------ Mehr Leben: Kuh, Pinguin, Tauben, Wasserspender
def build_cow():
    R = empty("Kuh", HIDE)
    spots, nt, out = node_mat("KuhFell")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.inputs["Roughness"].default_value = 0.8
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexNoise"); vo.inputs["Scale"].default_value = 2.2; vo.inputs["Detail"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeValToRGB"); rr.color_ramp.interpolation = "CONSTANT"
    rr.color_ramp.elements[0].color = hexcol("#151312")
    rr.color_ramp.elements[1].position, rr.color_ramp.elements[1].color = 0.52, hexcol("#f2efe8")
    nt.links.new(vo.outputs["Fac"], rr.inputs["Fac"]); nt.links.new(rr.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs[0])
    pink = mat("KuhRosa", "#e7a3a0", 0.6, sss=0.2)
    horn = mat("Horn", "#e8dcc0", 0.5)
    body = empty("Kuh_koerper", (0, 0, 1.0), R)
    prim("sphere", "Kuh_rumpf", (0, 0, 0), (0.75, 1.75, 0.8), m=spots, parent=body, seg=32)
    prim("sphere", "Kuh_euter", (0, -0.45, -0.38), (0.32, 0.36, 0.25), m=pink, parent=body)
    head = empty("Kuh_kopf", (0, 0.95, 0.25), body)
    prim("sphere", "Kuh_schaedel", (0, 0.15, 0.05), (0.42, 0.6, 0.45), m=spots, parent=head)
    prim("sphere", "Kuh_maul", (0, 0.45, -0.07), (0.38, 0.28, 0.27), m=pink, parent=head)
    for sx in (-1, 1):
        prim("cone", "Kuh_horn%d" % sx, (sx * 0.17, 0.05, 0.3), (0.07, 0.07, 0.18), rot=(0, sx * 0.6, 0), m=horn, parent=head, seg=10)
        prim("sphere", "Kuh_ohr%d" % sx, (sx * 0.27, 0.0, 0.18), (0.2, 0.06, 0.1), m=spots, parent=head)
        prim("sphere", "Kuh_auge%d" % sx, (sx * 0.17, 0.33, 0.13), (0.06, 0.05, 0.06), m=mat("Iris", "#1b0f0a", 0.2, coat=1.0), parent=head)
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            hp = empty("Kuh_bein%d%d" % (sx, sy), (sx * 0.24, sy * 0.55, -0.35), body)
            prim("cyl", "Kuh_beinzyl%d%d" % (sx, sy), (0, 0, -0.32), (0.16, 0.16, 0.66), m=spots, parent=hp, seg=12)
            prim("cyl", "Kuh_huf%d%d" % (sx, sy), (0, 0, -0.62), (0.17, 0.17, 0.08), m=mat("Huf", "#2a2420", 0.5), parent=hp, seg=12)
            legs.append((hp, sx * sy))
    tail = empty("Kuh_schwanz", (0, -0.85, 0.2), body)
    curve_obj("Kuh_schwanzkurve", [Vector((0, 0, 0)), Vector((0, -0.1, -0.3)), Vector((0, -0.08, -0.6))], radius=0.025, m=spots, parent=tail)
    return {"root": R, "body": body, "head": head, "legs": legs, "tail": tail}


def build_penguin():
    R = empty("Pinguin", HIDE)
    blk = mat("PinguinSchwarz", "#15171c", 0.45)
    wht = mat("PinguinWeiss", "#f4f2ec", 0.5)
    orn = mat("PinguinOrange", "#f0961e", 0.4)
    body = empty("Ping_koerper", (0, 0, 0.42), R)
    prim("sphere", "Ping_rumpf", (0, 0, 0), (0.46, 0.4, 0.75), m=blk, parent=body, seg=24)
    prim("sphere", "Ping_bauch", (0, 0.09, -0.04), (0.38, 0.3, 0.62), m=wht, parent=body, seg=24)
    head = empty("Ping_kopf", (0, 0, 0.42), body)
    prim("sphere", "Ping_schaedel", (0, 0, 0.0), (0.3, 0.3, 0.3), m=blk, parent=head, seg=20)
    prim("cone", "Ping_schnabel", (0, 0.2, -0.02), (0.07, 0.07, 0.16), rot=(math.radians(-90), 0, 0), m=orn, parent=head, seg=10)
    for sx in (-1, 1):
        prim("sphere", "Ping_auge%d" % sx, (sx * 0.08, 0.12, 0.05), (0.06, 0.04, 0.06), m=wht, parent=head)
        prim("sphere", "Ping_pupille%d" % sx, (sx * 0.085, 0.15, 0.05), (0.03, 0.02, 0.03), m=mat("Iris", "#1b0f0a", 0.2, coat=1.0), parent=head)
    flips = []
    for sx in (-1, 1):
        f = empty("Ping_fluegel%d" % sx, (sx * 0.22, 0, 0.15), body)
        prim("sphere", "Ping_fl%d" % sx, (sx * 0.03, 0, -0.2), (0.08, 0.18, 0.45), m=blk, parent=f)
        flips.append((f, sx))
        prim("sphere", "Ping_fuss%d" % sx, (sx * 0.11, 0.1, 0.02), (0.14, 0.2, 0.05), m=orn, parent=R)
    return {"root": R, "body": body, "head": head, "flips": flips}


COW = build_cow()
PENG = build_penguin()

PIGEON = proto_collection("TaubeVorlage")
_tg = mat("Taubengrau", "#8a8c94", 0.6)
_tgr = mat("Taubenhals", "#4f7a6e", 0.4, coat=0.4)
PIGEON.objects.link(parts_mesh("TaubeMesh", [("s", (0, 0, 0.1), (0.14, 0.26, 0.15), 0), ("s", (0, 0.11, 0.2), (0.09, 0.09, 0.09), 1),
                                             ("b", (0, 0.17, 0.2), (0.02, 0.05, 0.015), 2), ("b", (0, -0.17, 0.12), (0.08, 0.14, 0.02), 0)],
                               [_tg, _tgr, mat("Schnabel", "#d9a24a", 0.5)], link_=False))
PIGEONS = []
for i in range(14):
    key = sorted(HERO.keys())[int(hsh(i * 5.3) * len(HERO))]
    cell = HERO[key]["cell"]
    p = cw(cell, ((hsh(i) - 0.5) * 2.4, 1.5 - CW_I - CW_T / 2 - 3.0 + 0.0, CW_H + 0.03))
    p = cw(cell, (-1.5 + CW_I + CW_T / 2, (hsh(i * 2) - 0.5) * 2.2, CW_H + 0.03)) if i % 2 else cw(cell, ((hsh(i) - 0.5) * 2.2, -1.5 + CW_I + CW_T / 2, CW_H + 0.03))
    PIGEONS.append({"ob": instance("Taube%02d" % i, PIGEON, p, (0, 0, hsh(i * 7) * math.tau)), "home": p, "seed": i})

# Wasserspender mit Pepsi Grandma
COOLER = empty("Wasserspender", (-1.0, 9.6, 0))
prim("cube", "WS_sockel", (0, 0, 0.5), (0.36, 0.36, 1.0), m=mat("WS_weiss", "#e9e6df", 0.5), parent=COOLER, bevel=0.03)
prim("cyl", "WS_flasche", (0, 0, 1.25), (0.3, 0.3, 0.5), m=mat("WS_blau", "#7fb6ff", 0.05, coat=1.0), parent=COOLER, seg=20)

# ------------------------------------------------------------------ UI-Ebene vor der Kamera (nur noch für den Blitz beim Eintauchen)
OVL_D = 0.3
OVL = empty("UI", (0, 0, -OVL_D), CAM)


def flash_mat():
    m, nt, out = node_mat("UI_Blitz")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.6
    col = nt.nodes.new("ShaderNodeRGB"); col.name = "farbe"; col.outputs[0].default_value = (1, 1, 1, 1)
    nt.links.new(col.outputs[0], em.inputs[0])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    al = nt.nodes.new("ShaderNodeValue"); al.name = "alpha"
    ms = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(al.outputs[0], ms.inputs[0]); nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(em.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs[0])
    for attr, v in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(m, attr):
            try:
                setattr(m, attr, v)
            except Exception:   # noqa: BLE001
                pass
    return m, {"alpha": al, "farbe": col}


_fm, FLASH_N = flash_mat()
FLASH = prim("plane", "UI_Blitzflaeche", (0, 0, 0.0), (1.5, 2.4, 1), m=_fm, parent=OVL)


def flash_run(b, hits, col="#ffffff"):
    """Kurzer Blitz genau auf den Übergangs-Schlägen (kein langes Ausblenden mehr)."""
    a = 0.0
    for bh in hits:
        if bh - 0.15 <= b < bh:
            a = max(a, (b - (bh - 0.15)) / 0.15)
        elif bh <= b < bh + 0.35:
            a = max(a, 1 - (b - bh) / 0.35)
    FLASH_N["alpha"].outputs[0].default_value = a * 0.9
    FLASH.scale = (1.5, 2.4, 1) if a > 0.001 else (0, 0, 0)


def ovl_update():
    k = OVL_D * 18.0 / cam_data.lens
    OVL.scale = (k, k, k)


# ------------------------------------------------------------------ Welten hinter den Bildschirmen
WX = {"fabrik": Vector((5000, 0, 0)), "pepsi": Vector((-5000, 0, 0)), "orbit": Vector((0, 5000, 0))}
SKIES.update({
    "orbit":  ("#10245e", "#040a26", "#000003", 1.5, 1.0, 140, 1100, 3.4, "#ffffff"),
    "fabrik": ("#3a1f0e", "#1c0f07", "#070403", 0.0, 0.0, 7, 62, 0.35, "#ffb070"),
})

# --- Hot-Dog-Fabrik (Variante 1): dunkle Halle, Fließbänder voller Hot Dogs, Stampfer im Takt, Natriumlicht
FW = empty("Fabrik", WX["fabrik"])
CONCRETE = noise_mat("Beton", "#4a4642", "#5e5953", scale=3.0, rough=0.85, bump=0.15)
STEEL = mat("Stahl", "#6f747a", 0.35, metal=0.9)
RUBBER = mat("Band", "#1c1c1e", 0.7)
YELLOW = mat("Warngelb", "#e8b21a", 0.5)
prim("plane", "Fabrikboden", (0, 40, 0.0), (300, 300, 1), m=CONCRETE, parent=FW)
BELTS = []
for k, bx in enumerate((-3.2, 0.0, 3.2)):
    prim("cube", "Band%d" % k, (bx, 30, 0.9), (1.2, 80, 0.1), m=RUBBER, parent=FW)
    prim("cube", "Bandrahmen%d" % k, (bx, 30, 0.8), (1.4, 80, 0.14), m=STEEL, parent=FW)
    for j in range(16):
        prim("cube", "Bandbein%d_%d" % (k, j), (bx, -8 + j * 5, 0.4), (1.3, 0.12, 0.8), m=STEEL, parent=FW)
    prim("cube", "Warnstreifen%d" % k, (bx + 0.72, 30, 0.88), (0.04, 80, 0.12), m=YELLOW, parent=FW)
    BELTS.append(bx)
BELT_DOGS = [instance("BandHotDog%03d" % i, HOTDOG, (0, 0, 0), scale=1.0, parent=FW) for i in range(90)]
PRESSES = []
for k in range(6):
    py = 6 + k * 9
    bx = BELTS[k % 3]
    prim("cube", "Pressgestell%d" % k, (bx, py, 2.6), (1.8, 1.2, 0.3), m=STEEL, parent=FW)
    for sx in (-1, 1):
        prim("cube", "Pressbein%d_%d" % (k, sx), (bx + sx * 0.85, py, 1.5), (0.14, 0.14, 2.4), m=STEEL, parent=FW)
    ram = prim("cube", "Stempel%d" % k, (bx, py, 2.0), (0.9, 0.7, 0.8), m=YELLOW, parent=FW, bevel=0.04)
    PRESSES.append(ram)
TANKS = []
for k in range(8):
    sx = -1 if k % 2 == 0 else 1
    pos = (sx * (8 + hsh(k) * 3), 4 + k * 7, 0)
    prim("cyl", "Tank%d" % k, (pos[0], pos[1], 4.0), (3.4, 3.4, 8.0), m=STEEL, parent=FW, seg=32)
    prim("sphere", "Tankdeckel%d" % k, (pos[0], pos[1], 8.0), (3.4, 3.4, 1.6), m=STEEL, parent=FW, seg=32)
    curve_obj("Rohr%d" % k, [Vector((pos[0], pos[1], 7.5)), Vector((pos[0] * 0.6, pos[1] + 1, 10)), Vector((BELTS[k % 3], pos[1] + 3, 4.0))],
              radius=0.18, m=STEEL, parent=FW)
SODIUM = emit_mat("Natriumlicht", "#ffae4a", 12.0)
for k in range(10):
    for sx in (-1, 1):
        prim("cube", "Lampe%d%d" % (k, sx), (sx * 4.8, -4 + k * 7, 7.0), (1.6, 0.4, 0.12), m=SODIUM, parent=FW)
for k in range(5):
    light("Fabriklicht%d" % k, "POINT", WX["fabrik"] + Vector((0, 2 + k * 11, 5.5)), 900, "#ffa040", size=1.5)
SIGN_M = emit_mat("Schildrot", "#ff3b2a", 5.0)
text("FabrikSchild", "MINOVERSE HOT DOG\nMANUFACTURING FACILITY", size=1.3, m=SIGN_M, parent=FW, loc=(0, 52, 7.5), rot=(math.radians(90), 0, 0))
text("FabrikSchild2", "VEGAN LINE: OUT OF ORDER", size=0.55, m=emit_mat("Schildgelb", "#ffd23c", 4.0), parent=FW, loc=(-5.5, 20, 3.4),
     rot=(math.radians(90), 0, math.radians(30)))
text("FabrikSchild3", "DAYS WITHOUT INCIDENT: 0", size=0.45, m=emit_mat("Schildweiss", "#f4f4f4", 3.0), parent=FW, loc=(5.6, 26, 3.2),
     rot=(math.radians(90), 0, math.radians(-30)))
STEAM = [prim("ico", "Dampf%02d" % i, (0, 0, -50), (1, 1, 1), m=mat("Dampf", "#d8d0c8", 0.9, emit="#ffb070", estr=0.15), parent=FW)
         for i in range(36)]
FAB_MON = monitor("FabrikPC", WX["fabrik"] + Vector((1.6, 34.0, 1.0)), math.radians(180) + 0.3, "news", size=1.2)
FAB_SHELF = prim("cube", "FabrikPCtisch", WX["fabrik"] + Vector((1.6, 34.3, 0.5)), (1.4, 1.0, 1.0), m=STEEL)

# --- Pepsi-Ozean (Variante 3)
PW = empty("PepsiOzean", WX["pepsi"])
bpy.ops.mesh.primitive_grid_add(x_subdivisions=180, y_subdivisions=180, size=260)
OCEAN = bpy.context.active_object
OCEAN.name = "Ozean"
OCEAN.parent = PW
OCEAN.location = (0, 60, -0.5)
for p in OCEAN.data.polygons:
    p.use_smooth = True
OCEAN.data.materials.append(noise_mat("Pepsimeer", "#0a3cb8", "#1f6cff", scale=0.6, rough=0.08, bump=0.4, c2="#e8f4ff"))
WAVE_TEX = bpy.data.textures.new("Wellen", "CLOUDS")
WAVE_TEX.noise_scale = 7.0
WAVE_E = empty("Wellenursprung", (0, 0, 0), PW)
_dm = OCEAN.modifiers.new("wellen", "DISPLACE")
_dm.texture = WAVE_TEX
_dm.texture_coords = "OBJECT"
_dm.texture_coords_object = WAVE_E
_dm.strength = 1.6
BOTTLES = []
for i in range(9):
    a = (i / 9) * math.tau
    o = instance("Riesenflasche%d" % i, PEPSI, (math.sin(a) * (16 + hsh(i) * 18), 30 + math.cos(a) * (16 + hsh(i) * 18), -1),
                 scale=6 + hsh(i * 3) * 6, parent=PW)
    BOTTLES.append(o)
FOAM = [prim("ico", "Schaum%03d" % i, (0, 0, -50), (1, 1, 1), m=mat("Schaum", "#f8f6f0", 0.6, emit="#ffffff", estr=0.3), parent=PW)
        for i in range(90)]
SURF = empty("Surfbrett", HIDE)
prim("sphere", "Brett", (0, 0, 0.02), (2.3, 0.62, 0.08), m=mat("Brettweiss", "#f4f0e6", 0.25, coat=0.8), parent=SURF, seg=32)
prim("sphere", "Brettstreifen", (0, 0, 0.035), (2.0, 0.12, 0.07), m=mat("Pepsiblau", "#1f4fd0", 0.25, coat=0.8), parent=SURF, seg=24)
prim("sphere", "Brettstreifen2", (0, 0, 0.034), (1.9, 0.22, 0.068), m=mat("Pepsirot", "#d8232a", 0.25, coat=0.8), parent=SURF, seg=24)
for _sx in (-1, 1):
    prim("cone", "Finne%d" % _sx, (-0.95, _sx * 0.12, -0.08), (0.12, 0.02, 0.16), rot=(math.pi, 0, 0), m=mat("Pepsiblau", "#1f4fd0", 0.25), parent=SURF, seg=8)
RAFT = parts_mesh("Floss", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                            ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
RAFT_MON = monitor("FlossPC", (0, 0, 0), 0, "pepsi", parent=RAFT)
RAFT_MON["root"].location = (0.45, -0.2, 0.77)

# --- Großraumbüro im Weltall (Variante 2): eine Büro-Insel schwebt über einem Planeten
OW = empty("OrbitBuero", WX["orbit"])
PLANET = prim("sphere", "Planet", (0, 60, -520), (900, 900, 900), m=noise_mat("Planetenhaut", "#123c8a", "#2f7a3e", scale=1.6, rough=0.7, bump=0.1,
                                                                                 c2="#f4f2ee", detail=8), parent=OW, seg=96)
def atmo_mat():
    """Dünner Leuchtrand: am Rand blau, in der Mitte durchsichtig (sonst verdeckt die Hülle den Planeten)."""
    m, nt, out = node_mat("UI_Atmo")      # UI_: kein Dunst auf der Hülle
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[1].position = 0.95
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = hexcol("#6fb4ff")
    em.inputs[1].default_value = 1.2
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    ms = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(ramp.outputs["Color"], ms.inputs[0])
    nt.links.new(tr.outputs[0], ms.inputs[1])
    nt.links.new(em.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs[0])
    for attr, v in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(m, attr):
            try:
                setattr(m, attr, v)
            except Exception:   # noqa: BLE001
                pass
    return m


ATMO = prim("sphere", "Atmosphaere", (0, 60, -520), (915, 915, 915), m=atmo_mat(), parent=OW, seg=96)
ISLAND = empty("Insel", WX["orbit"] + Vector((0, 20, 0)))
prim("cube", "Inselteppich", (0, 0, -0.05), (19, 19, 0.1), m=carpet_mat(), parent=ISLAND)
prim("cube", "Inselsockel", (0, 0, -0.9), (19.2, 19.2, 1.6), m=CONCRETE, parent=ISLAND, bevel=0.2)
prim("cone", "Inselunterseite", (0, 0, -4.5), (17, 17, 6.0), rot=(math.radians(180), 0, 0), m=CONCRETE, parent=ISLAND, seg=8)
ISLAND_CELLS = []
for ix in range(-2, 3):
    for iy in range(-2, 3):
        if (ix, iy) in ((0, -2), (0, -1)):
            continue
        rz = math.radians(90 if ix < 0 else -90 if ix > 0 else 180)
        instance("InselKabine%d%d" % (ix + 2, iy + 2), KAB_NAH, (ix * 3.4, iy * 3.4, 0), (0, 0, rz), parent=ISLAND)
        if hsh(ix * 3.1 + iy * 7.7) < 0.55:
            instance("InselKollege%d%d" % (ix + 2, iy + 2), WORKER, (ix * 3.4, iy * 3.4, 0), (0, 0, rz), parent=ISLAND)
DESK_MM = parts_mesh("SchwebeTischMM", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                                        ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
DESK_MM_MON = monitor("SchwebePC", (0, 0, 0), 0, "news", parent=DESK_MM)
DESK_MM_MON["root"].location = (0, 0.15, 0.77)
DESK_MM_MON["root"].rotation_euler.z = math.pi
DESK_CG = parts_mesh("SchwebeTischCG", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                                        ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
SPACE_PAPER = [prim("plane", "AllBlatt%02d" % i, (0, 0, 0), (0.6, 0.85, 1), m=PAPER_M, parent=OW) for i in range(40)]
SPACE_CHAIRS = [parts_mesh("AllStuhl%d" % i, [("b", (0, 0, 0.48), (0.48, 0.46, 0.08), 0), ("b", (0, 0.2, 0.8), (0.46, 0.07, 0.5), 0),
                                               ("b", (0, 0, 0.25), (0.05, 0.05, 0.45), 1)], [CHAIR_M, LEG_M]) for i in range(5)]
SPACE_COOLER = parts_mesh("AllWasserspender", [("b", (0, 0, 0.5), (0.36, 0.36, 1.0), 0), ("s", (0, 0, 1.25), (0.3, 0.3, 0.5), 1)],
                          [mat("WS_weiss", "#e9e6df", 0.5), mat("WS_blau", "#7fb6ff", 0.05, coat=1.0)])

# Riesen-Röhrenmonitor im Gang (Variante 3 springt hinein)
GATE = monitor("TorPC", (0, 9.0, 0), 0, "pepsi", size=1.7)
GATE["root"].location.z = -50
GATE_FRONT = None

MU["root"].location = HIDE


# ------------------------------------------------------------------ Ausdrücke Chicken Guy
EXPR = {
    #            open  wide  lid   brow  tilt  teeth tongue cheek
    "null":     (0.0, 1.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0),
    "neutral":  (0.25, 1.0, 0.35, 0.0, 0.05, 0.6, 0.0, 0.1),
    "deadpan":  (0.3, 1.0, 0.4, -0.1, 0.05, 0.7, 0.0, 0.1),     # halb offene Lider, Mund offen, Zähne sichtbar (wie im Video)
    "schrei":   (1.1, 0.85, 0.9, -0.7, -0.1, 1.0, 0.5, 0.9),    # Augen zugekniffen, hohes ovales Mundloch
    "ekstase":  (0.9, 0.7, 1.0, 0.8, -0.4, 0.8, 0.5, 0.5),      # Kopf zurück, Augen zu
    "grimasse": (0.5, 1.3, 0.65, -0.5, 0.15, 1.0, 0.0, 0.7),
    "boah":     (0.75, 0.75, 0.15, 0.9, 0.0, 0.6, 0.3, 0.1),    # Augen weit auf
    "starr":    (0.45, 1.0, 0.25, 0.2, 0.0, 0.8, 0.0, 0.0),     # starrt in die Kamera, Mund offen
}
EXPR_SEQ = ["starr", "schrei", "deadpan", "boah", "starr", "grimasse", "deadpan", "ekstase"]
EXPR_FORCE = None
def expr_at(t):
    if EXPR_FORCE:
        return EXPR[EXPR_FORCE]
    b = beat_of(t)
    if b < DROP - 0.5:
        if b > DROP - 2:
            return EXPR["boah"]
        return EXPR["schrei"] if (int(b) % 4 == 3 and (b % 1) < 0.6) else EXPR["deadpan"]
    i = int(b - DROP)
    cur = EXPR[EXPR_SEQ[i % len(EXPR_SEQ)]]
    nxt = EXPR[EXPR_SEQ[(i + 1) % len(EXPR_SEQ)]]
    f = (b - DROP) - i
    k = smooth((f - 0.75) / 0.25)   # kurz vor dem nächsten Schlag umblenden
    return tuple(lerp(a, c, k) for a, c in zip(cur, nxt))


def _kset(kb, name, v):
    if name in kb:
        kb[name].value = v


def apply_face(t):
    """Ausdruck -> Shape Keys des realistischen Kopfes (MakeHuman-Ausdruckseinheiten, afrikanischer Kopftyp)."""
    op, wide, lid, brow, tilt, teeth, tongue, cheek = expr_at(t)
    hit = pulse(t, 0.12, 1, DROP, NB)
    op = clamp(op + hit * 0.15 * (op > 0.3), 0, 1.2)
    R_ = CG.get("real")
    if not R_:
        return
    kb = R_["keys"]
    _kset(kb, "mouth-open", op * 1.0)
    _kset(kb, "mouth-retraction", clamp(wide - 1.0, 0, 1) * 1.2)
    _kset(kb, "mouth-corner-puller", clamp(wide - 1.0, 0, 1) * 0.6 + cheek * 0.25)
    _kset(kb, "mouth-pursing", clamp(1.0 - wide, 0, 1) * 0.9)
    _kset(kb, "mouth-upward-retraction", teeth * 0.4 + cheek * 0.3)     # Oberlippe hoch: obere Zähne mit Lücke sichtbar
    _kset(kb, "mouth-depression", 0.15 + teeth * 0.35)                   # Unterlippe runter: untere Zähne
    _kset(kb, "mouth-eversion", 0.3)
    blink = 1.0 if (t % 3.1) < 0.09 else 0.0
    l = clamp(max(lid, blink * (lid < 0.9)))
    slit = clamp((l - 0.2) / 0.35) * (1 - clamp((l - 0.7) / 0.25))
    close = clamp((l - 0.6) / 0.35)
    wideo = clamp((0.2 - l) / 0.2)
    for side in ("left", "right"):
        _kset(kb, "eye-%s-slit" % side, slit * 0.9)
        _kset(kb, "eye-%s-closure" % side, close)
        _kset(kb, "eye-%s-opened-up" % side, wideo * 0.9)
        _kset(kb, "eyebrows-%s-up" % side, clamp(brow) * 1.1)
        _kset(kb, "eyebrows-%s-inner-up" % side, clamp(brow) * 0.5)
        _kset(kb, "eyebrows-%s-down" % side, clamp(-brow) * 1.1)
    for side in ("left", "right"):
        _kset(kb, "nose-%s-elevation" % side, cheek * 0.8)
        _kset(kb, "nose-%s-dilatation" % side, cheek * 0.6 + op * 0.2)
    for sx, e in R_["eyes"].items():
        e.rotation_euler = (math.sin(t * 0.9) * 0.05, 0, math.sin(t * 2.3 + (sx == "L")) * 0.12)
    CG["head"].rotation_euler.x = tilt



# ------------------------------------------------------------------ Kamera-Werkzeuge
def world_matrix(ob):
    """Weltmatrix aus Ort/Drehung/Größe der Eltern-Kette (im Handler ist matrix_world noch vom letzten Bild)."""
    M = Matrix.Identity(4)
    while ob is not None:
        M = Matrix.LocRotScale(ob.location, ob.rotation_euler, ob.scale) @ M
        ob = ob.parent
    return M


def mon_front(s, d=0.15, dz=0.0):
    M = world_matrix(s["root"])
    sc = s["screen"].location
    return M @ Vector((sc.x, sc.y + d, sc.z + dz))


def track(b, keys):
    """Kamerafahrt aus Schlüsseln (Schlag, Position, Ziel, Brennweite[, Kurve]); gleicher Schlag zweimal = harter Schnitt."""
    for i in range(len(keys) - 1):
        b0, p0, t0, l0 = keys[i][:4]
        b1, p1, t1, l1 = keys[i + 1][:4]
        if b0 <= b < b1:
            e = keys[i + 1][4] if len(keys[i + 1]) > 4 else ease_inout
            k = e((b - b0) / (b1 - b0))
            return vlerp(resolve(p0), resolve(p1), k), vlerp(resolve(t0), resolve(t1), k), lerp(l0, l1, k)
    last = keys[-1]
    return Vector(resolve(last[1])), Vector(resolve(last[2])), last[3]


def snap(x):
    """Schnell ankommen und leicht überschwingen: die Kamera 'federt' auf den Schlag."""
    return ease_back(clamp(x * 1.25))


def stutter(b0, b1, front, steps=4, far=3.0, near=0.04, lens=30, up=None):
    """Taktgenaues Eintauchen: in Stufen auf jedem Teilschlag näher an den Bildschirm (front(d) -> Punkt vor dem Glas)."""
    keys = []
    for i in range(steps + 1):
        bb = b0 + (b1 - b0) * i / steps
        d = far * (near / far) ** (i / steps)
        keys.append((bb, (lambda d=d: front(d)), (lambda: front(0.0)), lens + i * 2, ease_out))
    return keys


def bounce_tour(b0, b1, spots, step=1.0, lens_jitter=4):
    """Nach dem Drop: die Kamera springt federnd auf jedem Schlag an eine andere Stelle der Party."""
    keys = []
    n = int(round((b1 - b0) / step))
    for i in range(n + 1):
        p, tg, ln = spots[i % len(spots)]
        keys.append((b0 + i * step, p, tg, ln + (i % 3 - 1) * lens_jitter, snap))
    return keys


CAM_FX = {"punch": 0.0, "roll": 0.0}


def cam_fx(t, b, p, tg, lens, amount=1.0):
    """Beat-Bounce: Zoom-Stoß und kurzer Ruck nach unten auf jedem Schlag, leichtes Kippen im Wechsel."""
    if b < DROP or amount <= 0:
        return p, tg, lens, 0.0
    hit = pulse(t, 0.11, 1, DROP, NB) * amount
    off = pulse(t, 0.09, 0.5, DROP, NB) * 0.35 * amount       # Achtel dazwischen etwas schwächer
    d = (tg - p)
    p2 = p + d * (0.07 * hit) + Vector((0, 0, -0.06 * hit * max(1.0, d.length * 0.1)))
    lens2 = lens * (1 + 0.1 * hit + 0.03 * off)
    roll = (0.035 if int(b) % 2 == 0 else -0.035) * hit
    return p2, tg, lens2, roll


# ------------------------------------------------------------------ Posen
def place(root, pos, rz=None, s=None):
    root.location = pos
    if rz is not None:
        root.rotation_euler = (0, 0, rz)
    if s is not None:
        root.scale = (s, s, s)


MM_MOVES = ["zeigen", "jubel", "roboter", "wackeln"]


def pose_mm(t, mode, trick=None):
    b = beat_of(t)
    ph = t / BEAT * math.pi
    hit = pulse(t, 0.14, 1, 0, NB)
    legs, arms = MM["legs"], MM["arms"]
    MM["torso"].rotation_euler = (0, 0, 0)
    MM["glint"].scale = (0.022 * (1 + 2 * pulse(t, 0.25, 4, 0, NB)), 0.006, 0.012)
    if mode == "tanzen":
        mode = MM_MOVES[int(b / 4) % len(MM_MOVES)]
    if mode in ("sitzen", "schweben"):
        for sx, (hp, kn) in legs.items():
            hp.rotation_euler = (math.radians(88), 0, sx * 0.08)
            kn.rotation_euler = (math.radians(-88), 0, 0)
        for sx, (sh, el) in arms.items():
            tip = math.sin(t * 22 + sx * 1.7) * 0.06
            sh.rotation_euler = (math.radians(30) + tip, 0, sx * 0.1)
            el.rotation_euler = (math.radians(60) - tip, 0, 0)
        MM["neck"].rotation_euler = (0.12 + hit * 0.03, 0, math.sin(t * 0.8) * 0.05)
        return
    # Beine: Wippen auf jedem Schlag
    for sx, (hp, kn) in legs.items():
        st = max(0.0, math.sin(ph + (0 if sx > 0 else math.pi)))
        hp.rotation_euler = (st * 0.5, 0, sx * 0.06)
        kn.rotation_euler = (-st * 0.85, 0, 0)
    if mode == "zeigen":       # Deadpan-Disco: abwechselnd ein Arm in den Himmel
        up = int(b) % 2
        for sx, (sh, el) in arms.items():
            a = smooth(((b % 1) / 0.2)) if ((sx > 0) == (up == 1)) else 1 - smooth(((b % 1) / 0.2))
            sh.rotation_euler = (lerp(0.35, 2.95, a), 0, -sx * lerp(0.15, 0.35, a))
            el.rotation_euler = (lerp(1.2, 0.1, a), 0, 0)
        MM["neck"].rotation_euler = (hit * 0.12, 0, math.sin(ph * 0.5) * 0.12)
    elif mode == "jubel":      # beide Fäuste pumpen auf den Schlag
        pump = hit
        for sx, (sh, el) in arms.items():
            sh.rotation_euler = (2.6 + 0.3 * pump, 0, -sx * 0.4)
            el.rotation_euler = (0.9 - 0.8 * pump, 0, 0)
        MM["neck"].rotation_euler = (-0.15 - hit * 0.15, 0, 0)
    elif mode == "roboter":    # eckig, auf Achteln einrastend
        st = int(b * 2) % 4
        for sx, (sh, el) in arms.items():
            a = [0.0, 1.57, 0.0, 1.57][(st + (0 if sx > 0 else 1)) % 4]
            sh.rotation_euler = (a, 0, -sx * 0.1)
            el.rotation_euler = (1.57 - a * 0.5, 0, 0)
        MM["neck"].rotation_euler = (0, 0, [0.0, 0.5, 0.0, -0.5][st])
        MM["torso"].rotation_euler = (0, 0, [0.0, 0.15, 0.0, -0.15][st])
    elif mode == "wackeln":    # Arme seitlich, Hüfte schwingt, Kopf nickt
        sw = math.sin(ph)
        for sx, (sh, el) in arms.items():
            sh.rotation_euler = (0.4, 0, -sx * (1.2 + 0.3 * sw * sx))
            el.rotation_euler = (0.6 + 0.4 * math.sin(ph * 2 + sx), 0, 0)
        MM["torso"].rotation_euler = (0, sw * 0.12, sw * 0.2)
        MM["neck"].rotation_euler = (hit * 0.25, 0, -sw * 0.15)
    elif mode == "surfen":
        tr = trick or "carve"
        lean = math.sin(t * 1.6) * 0.25
        for sx, (hp, kn) in legs.items():
            bend = 0.55 if tr in ("carve", "duck") else 0.35
            if tr == "duck":
                bend = 1.0
            hp.rotation_euler = (bend * 0.7 * (1 if sx > 0 else 0.6), -sx * 0.35, 0)
            kn.rotation_euler = (-bend, 0, 0)
        for sx, (sh, el) in arms.items():
            if tr == "air":
                sh.rotation_euler = (2.7, 0, -sx * 0.6)
                el.rotation_euler = (0.2, 0, 0)
            elif tr == "duck":
                sh.rotation_euler = (0.9 if sx > 0 else -0.3, -sx * 0.9, 0)
                el.rotation_euler = (0.8, 0, 0)
            else:
                sh.rotation_euler = (0.2 + math.sin(t * 2 + sx) * 0.15 + lean * sx, -sx * 1.35, 0)
                el.rotation_euler = (0.25, 0, 0)
        MM["torso"].rotation_euler = (0, lean * 0.6, 0)
        MM["neck"].rotation_euler = (0, 0, -0.7)


CG_MOVES = ["flattern", "huepfen", "drehen", "flattern", "wippen"]


def pose_cg(t, wild=1.0, move=None):
    b = beat_of(t)
    hit_drop = pulse(t, 0.16, 1, 0, NB)
    ph = t / BEAT * math.pi
    mv = move or CG_MOVES[int(b / 4) % len(CG_MOVES)]
    body = CG["body"]
    hop = abs(math.sin(ph)) * 0.14 * wild
    if mv == "huepfen":
        hop = abs(math.sin(ph)) * 0.35 * wild
    body.location.z = CG_BZ + hop
    body.scale = (CG_BS[0] * (1 + hit_drop * 0.08 * wild), CG_BS[1] * (1 + hit_drop * 0.08 * wild), CG_BS[2] * (1 - hit_drop * 0.1 * wild))
    spin = 0.0
    if mv == "drehen":
        spin = ease_inout((b % 2) / 2) * math.tau * wild
    body.rotation_euler = (0, math.sin(ph) * 0.2 * wild, math.sin(ph * 0.5) * 0.35 * wild + spin)
    for sx, (sh, el, tip) in CG["wings"].items():
        flap = math.sin(ph * 2 + (0 if sx > 0 else math.pi * 0.5))
        if mv == "wippen":
            flap = math.sin(ph) * 0.4
        sh.rotation_euler = (0, -sx * (0.4 + flap * 0.9 * wild), sx * math.sin(ph) * 0.4 * wild)
        el.rotation_euler = (0, -sx * (0.6 + math.sin(ph * 2 + 1) * 0.9 * wild), 0)
        tip.rotation_euler = (0, -sx * math.sin(ph * 4) * 0.5 * wild, 0)
    for sx, hip in CG["legs"].items():
        hip.rotation_euler = (math.sin(ph + (0 if sx > 0 else math.pi)) * 0.55 * wild, 0, 0)
    CG["neck"].rotation_euler = (math.sin(ph * 2) * 0.12 * wild + hit_drop * 0.15 * wild, math.sin(ph) * 0.25 * wild, math.sin(ph * 0.5) * 0.25 * wild)
    apply_face(t)


def cg_head():
    R_ = CG.get("real")
    if R_:      # Mitte des echten Kopfes (Weltmatrix selbst rechnen, matrix_world ist im Handler noch vom letzten Bild)
        bb = R_["meta"]["bbox"]
        c = Vector(((bb[0][0] + bb[1][0]) / 2, (bb[0][1] + bb[1][1]) / 2, (bb[0][2] + bb[1][2]) / 2))
        return world_matrix(R_["obj"]) @ c
    s = CG["root"].scale.z
    return CG["root"].location + Vector((0, 0, 1.55 * s))


def mm_head():
    s = MM["root"].scale.z
    return MM["root"].location + Vector((0, 0, 1.76 * s))


def pose_munch(t, eat=1.0):
    bite = pulse(t, 0.12, 1, 0, NB) * eat
    MU["fore"].rotation_euler = (math.radians(-95) - bite * 0.25, 0, math.radians(-25))
    MU["arm"].rotation_euler = (math.radians(-40), 0, math.radians(20))
    MU["jaw"].scale = (0.1, 0.03, 0.03 + bite * 0.05)
    MU["head"].rotation_euler = (0.15 * bite, 0, math.sin(t * 0.7) * 0.1)


def pose_grandma(t, b, erupt_from=None):
    GM["arm"].rotation_euler = (math.radians(-60) + math.sin(t * 9) * 0.25 * (erupt_from is not None), 0, 0)
    for i, f in enumerate(GM["foam"]):
        if erupt_from is None or b < erupt_from:
            f.location = HIDE
            continue
        t0 = B(erupt_from + int(b - erupt_from))
        tt = (t - t0) - (i % 8) * 0.02
        top = GM["root"].location + Vector((0.27, 0.12, 1.25))
        ang = hsh(i * 3.3) * math.tau
        v = Vector((math.cos(ang) * 0.7, math.sin(ang) * 0.7 + 0.5, 3.2 + hsh(i) * 1.5))
        f.location = top + v * tt + Vector((0, 0, -4.9 * tt * tt)) if tt > 0 else HIDE
        sc = (0.05 + hsh(i * 7) * 0.06) * max(0.0, 1 - tt)
        f.scale = (sc, sc, sc)


def cow_run(t, b, path0, path1, b0, b1, dance=False):
    k = clamp((b - b0) / max(0.01, b1 - b0))
    p = vlerp(path0, path1, k)
    d = (Vector(path1) - Vector(path0))
    place(COW["root"], p, math.atan2(-d.x, d.y), 1.0)
    ph = t * 5.0
    for hp, sgn in COW["legs"]:
        hp.rotation_euler.x = math.sin(ph) * 0.35 * sgn if not dance else math.sin(t / BEAT * math.pi) * 0.25 * sgn
    COW["body"].location.z = 1.0 + abs(math.sin(ph)) * 0.04 + (pulse(t, 0.12, 1, 0, NB) * 0.12 if dance else 0)
    COW["head"].rotation_euler = (math.sin(t * 2) * 0.1 + (pulse(t, 0.12, 1, 0, NB) * 0.35 if dance else 0), 0, math.sin(t * 0.7) * 0.3)
    COW["tail"].rotation_euler = (0, math.sin(t * 6) * 0.5, 0)


def peng_run(t, b, path0, path1, b0, b1, dance=False):
    k = clamp((b - b0) / max(0.01, b1 - b0))
    p = vlerp(path0, path1, k)
    d = (Vector(path1) - Vector(path0))
    rz = math.atan2(-d.x, d.y) if d.length > 0.01 else 0
    place(PENG["root"], p, rz, 1.0)
    wob = math.sin(t * 9)
    PENG["root"].rotation_euler = (0, wob * 0.18, rz)
    for f, sx in PENG["flips"]:
        f.rotation_euler = (0, sx * (0.25 + (0.9 * abs(math.sin(t / BEAT * math.pi)) if dance else 0.2 * abs(wob))), 0)
    PENG["head"].rotation_euler = (pulse(t, 0.12, 1, 0, NB) * 0.4 if dance else 0, 0, math.sin(t * 1.3) * 0.3)


def pigeons_run(t, b, fly_at=None):
    for pg in PIGEONS:
        i = pg["seed"]
        if fly_at is not None and b >= fly_at:
            tt = t - B(fly_at) - hsh(i) * 0.2
            if tt < 0:
                tt = 0
            v = Vector(((hsh(i * 3) - 0.5) * 4, (hsh(i * 5) - 0.2) * 5, 4.0))
            pg["ob"].location = pg["home"] + v * tt + Vector((0, 0, 0.3 * math.sin(tt * 30) * 0.1))
            pg["ob"].scale = (1, 1, 1 + 0.3 * math.sin(tt * 40))
        else:
            peck = pulse(t + hsh(i) * 0.4, 0.1, 1, 0, NB)
            pg["ob"].location = pg["home"]
            pg["ob"].rotation_euler = (peck * 0.5, 0, hsh(i * 7) * math.tau + math.sin(t + i) * 0.4)
            pg["ob"].scale = (1, 1, 1)


# ------------------------------------------------------------------ Büro-Leben
def office(t, b, party=0.0, beat_change=False):
    hit = pulse(t, 0.14, 1, 0, NB)
    FAR_TAKT.outputs[0].default_value = (int(b) if beat_change else int(b / 8)) * 0.37
    FAR_STAERKE.outputs[0].default_value = 2.0 + 4.0 * hit * party
    for n in SCREEN_TIME:
        n.outputs[0].default_value = t
    for key, (m_, nodes) in PROG_MATS.items():
        ph = hsh(len(key) * 3.1)
        st = 1.0 if (hsh(int(b * 4) + ph * 50) > 0.97) else 0.0
        nodes["on"].outputs[0].default_value = 1.0
        nodes["static"].outputs[0].default_value = st
        nodes["flash"].outputs[0].default_value = 0.7 * hit * party * (1 if (int(b) + int(ph * 7)) % 2 == 0 else 0.3)
        nodes["w"].outputs[0].default_value = t * 40 + ph * 10
    for s in SCREENS:
        vis = s["nodes"]["static"].outputs[0].default_value < 0.6
        for c in s["content"]:
            c.hide_render = not vis
        for f in s["anim"]:
            f(t, b)
    for w in WORKERS:
        k = w["seed"]
        if party > 0.5:
            # jeder feiert anders: drehen auf dem Stuhl, Arme hoch, Kopfnicken
            style = k % 3
            spin = (b * 0.5 + hsh(k)) * math.tau * (0.5 if style == 0 else 0.0) * (1 if k % 2 else -1)
            w["root"].rotation_euler.z = w["rz"] + spin
            w["root"].location = w["pos"] + Vector((0, 0, pulse(t, 0.12, 1, 0, NB) * 0.08 * (style == 2)))
            for sx, (sh, el) in w["arms"].items():
                if style == 1:
                    sh.rotation_euler = (2.6 + 0.3 * hit, 0, -sx * 0.4)
                    el.rotation_euler = (0.8 - 0.6 * hit, 0, 0)
                else:
                    sh.rotation_euler = (2.8 + math.sin(t * 9 + sx + k) * 0.25, 0, -sx * 0.3)
                    el.rotation_euler = (0.3, 0, 0)
            w["head"].rotation_euler = (hit * 0.3, 0, math.sin(t * 3 + k) * 0.3)
        else:
            w["root"].rotation_euler.z = w["rz"]
            w["root"].location = w["pos"]
            for sx, (sh, el) in w["arms"].items():
                tip = math.sin(t * 20 + sx * 1.3 + k) * 0.06
                sh.rotation_euler = (math.radians(32) + tip, 0, sx * 0.08)
                el.rotation_euler = (math.radians(55) - tip, 0, 0)
            w["head"].rotation_euler = (0.1, 0, math.sin(t * 0.6 + k) * 0.15)


def flyers(t, b, b0, center, active):
    for f in FLYERS:
        i = f["seed"]
        tt = t - B(b0) - hsh(i) * 0.4
        if not active or tt < 0:
            f["ob"].location = HIDE
            continue
        up = 4.0 + hsh(i * 2) * 3
        z_ = max(0.02, 0.8 + up * tt - 1.6 * tt * tt)
        f["ob"].location = center + Vector(((hsh(i * 1.3) - .5) * 6 + math.sin(tt * 2 + i) * 0.6, (hsh(i * 2.9) - .5) * 10 + math.cos(tt * 1.7 + i) * 0.5, z_))
        f["ob"].rotation_euler = (tt * (2 + hsh(i) * 4), tt * 3 * (hsh(i * 5) - .5), tt * 2)


def bigs_office(t, b):
    for s, pos, rz in OFFICE_BIGS:
        big_place(s, pos + Vector((0, 0, math.sin(t * 0.5 + pos.x) * 0.25)), rz, t)


def hide_bigs():
    for s, pos, rz in OFFICE_BIGS:
        s["root"].location = HIDE


# ------------------------------------------------------------------ Welten animieren
def world_fabrik(t, b):
    c = WX["fabrik"]
    speed = 1.6 + (1.2 if b >= DROP else 0.0)
    for i, o in enumerate(BELT_DOGS):
        bx = BELTS[i % 3]
        y = ((i // 3) * 2.6 + t * speed * (1 if i % 2 else 1.15)) % 78 - 9
        o.location = (bx + (hsh(i) - 0.5) * 0.5, y, 1.02)
        o.rotation_euler = (0, 0, math.pi / 2 + (hsh(i * 3) - 0.5) * 0.4)
    for k, ram in enumerate(PRESSES):
        ph = (b + k * 0.5) % 1.0
        down = math.exp(-ph * 9) if b >= DROP else 0.3 + 0.3 * math.sin(t * 2 + k)
        ram.location.z = 2.05 - down * 0.85
    for i, s in enumerate(STEAM):
        ph = (t * 0.35 + hsh(i)) % 1.0
        src = Vector(((-1 if i % 2 else 1) * (8 + hsh(i) * 3), 4 + (i % 8) * 7, 8.6))
        s.location = src + Vector((math.sin(t + i) * 0.5, 0, ph * 6))
        sc = 0.6 + ph * 2.0
        s.scale = (sc, sc, sc)


def world_pepsi(t, b):
    WAVE_E.location = (t * 1.2, t * 0.7, 0)
    for i, o in enumerate(BOTTLES):
        o.location.z = -1.2 + math.sin(t * 1.5 + i) * 0.6
        o.rotation_euler = (math.sin(t + i) * 0.12, math.cos(t * 0.8 + i) * 0.12, i)
    for i, f in enumerate(FOAM):
        bo = BOTTLES[i % len(BOTTLES)]
        t0 = B(int(b / 2) * 2 + (i % 2))
        tt = t - t0 - (i // len(BOTTLES)) * 0.03
        if tt < 0 or tt > 1.6 or b < DROP:
            f.location = HIDE
            continue
        s = bo.scale.x
        ang = hsh(i * 3.3) * math.tau
        top = Vector(bo.location) + Vector((0, 0, 0.95 * s))
        v = Vector((math.cos(ang) * 2.5, math.sin(ang) * 2.5, 9 + hsh(i) * 6))
        f.location = top + v * tt + Vector((0, 0, -9.8 * tt * tt))
        sc = (0.4 + hsh(i * 7) * 0.6) * (1 - tt / 2)
        f.scale = (sc, sc, sc)


def world_orbit(t, b):
    c = WX["orbit"]
    PLANET.rotation_euler.z = t * 0.01
    ISLAND.rotation_euler.z = math.sin(t * 0.2) * 0.04
    ISLAND.location.z = c.z + math.sin(t * 0.5) * 0.3
    for i, p in enumerate(SPACE_PAPER):
        p.location = c + Vector(((hsh(i * 2.1) - .5) * 40, 4 + hsh(i * 3.3) * 40, (hsh(i * 5.7) - .5) * 12 + 3 + math.sin(t + i) * 0.8))
        p.rotation_euler = (t * (0.5 + hsh(i)) + i, t * 0.3 + i, i)
    for i, o in enumerate(SPACE_CHAIRS):
        o.location = c + Vector(((hsh(i * 9.1) - .5) * 24, 10 + hsh(i * 4.4) * 22, 3 + (hsh(i * 2.2) - .5) * 6 + math.sin(t * 0.7 + i)))
        o.rotation_euler = (t * 0.4 + i, t * 0.25, t * 0.3 + i)
    SPACE_COOLER.location = c + Vector((-7, 14, 4 + math.sin(t * 0.6)))
    SPACE_COOLER.rotation_euler = (t * 0.3, 0.4, t * 0.2)
    big_place(SPACE_BIG, ISLAND.location + Vector((-6.5, 9.5, 9.0)), math.pi + 0.35, t)


# ------------------------------------------------------------------ Mehr Zufall (Inspiration aus den Reels): Riesen-Sneaker am Himmel, Gemüse-Band
def build_sneaker():
    R = empty("Sneaker", HIDE)
    R.scale = (3.2, 3.2, 3.2)
    white = mat("SneakerWeiss", "#f4f2ee", 0.5)
    prim("cube", "Sn_sohle", (0, 0, 0.06), (0.42, 1.2, 0.14), m=white, parent=R, bevel=0.06)
    prim("sphere", "Sn_schaft", (0, -0.05, 0.3), (0.44, 1.15, 0.5), m=mat("SneakerRot", "#d8232a", 0.55), parent=R, seg=24)
    prim("cube", "Sn_kappe", (0, 0.48, 0.18), (0.4, 0.28, 0.2), m=white, parent=R, bevel=0.08)
    prim("cyl", "Sn_kragen", (0, -0.3, 0.55), (0.34, 0.4, 0.12), m=mat("SneakerSchwarz", "#141414", 0.6), parent=R, seg=20)
    for i in range(5):
        prim("cube", "Sn_senkel%d" % i, (0, 0.25 - i * 0.1, 0.52 - i * 0.015), (0.3, 0.025, 0.02), m=white, parent=R)
    text("Sn_logo", "MINO", size=0.14, m=white, parent=R, loc=(0.222, -0.05, 0.3), rot=(math.radians(90), 0, math.radians(90)), fnt="anton")
    return R


SNEAKER = build_sneaker()


def sneaker_run(t, b, flights):
    """Fliegt in hohem Bogen über das Büro, dreht sich dabei (Liste von (Start, Ende, von, nach))."""
    for b0, b1, p0, p1 in flights:
        if b0 <= b < b1:
            k = (b - b0) / (b1 - b0)
            p = vlerp(Vector(p0), Vector(p1), k) + Vector((0, 0, math.sin(k * math.pi) * 6))
            SNEAKER.location = p
            SNEAKER.rotation_euler = (k * 5.0, k * 2.0, k * 3.5)
            return
    SNEAKER.location = HIDE


VEG = []


def build_veg(name, kind, loc):
    R = empty(name, HIDE)
    jacket = mat("Lederjacke", "#16161a", 0.35, coat=0.5)
    prim("cube", name + "_torso", (0, 0, 1.05), (0.46, 0.28, 0.62), m=jacket, parent=R, bevel=0.06)
    prim("cube", name + "_hose", (0, 0, 0.42), (0.4, 0.26, 0.7), m=mat("Leo", "#c8962a", 0.7), parent=R, bevel=0.04)
    head = empty(name + "_kopf", (0, 0, 1.45), R)
    if kind == "brokkoli":
        prim("cyl", name + "_stiel", (0, 0, 0.12), (0.16, 0.16, 0.26), m=mat("Stiel", "#8fbf5a", 0.6), parent=head, seg=12)
        for k in range(9):
            a = k / 9 * math.tau
            prim("ico", name + "_roeschen%d" % k, (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.38 + hsh(k) * 0.08), (0.3, 0.3, 0.28),
                 m=noise_mat("Brokkoli", "#2f6b1e", "#5fa83a", scale=30, rough=0.7, bump=0.6), parent=head)
        prim("ico", name + "_krone", (0, 0, 0.5), (0.34, 0.34, 0.3), m=noise_mat("Brokkoli", "#2f6b1e", "#5fa83a", scale=30, rough=0.7, bump=0.6),
             parent=head)
    elif kind == "paprika":
        prim("sphere", name + "_frucht", (0, 0, 0.28), (0.5, 0.48, 0.55), m=mat("Paprika", "#d8160e", 0.15, coat=1.0), parent=head, seg=24)
        prim("cyl", name + "_stielp", (0, 0, 0.6), (0.06, 0.06, 0.14), m=mat("Stiel", "#8fbf5a", 0.6), parent=head, seg=8)
    else:
        prim("cone", name + "_karotte", (0, 0, 0.3), (0.34, 0.34, 0.7), rot=(math.pi, 0, 0), m=mat("Karotte", "#f07818", 0.5), parent=head, seg=16)
        for k in range(3):
            prim("cone", name + "_kraut%d" % k, ((k - 1) * 0.06, 0, 0.74), (0.08, 0.04, 0.3), m=mat("Kraut", "#3f9a2a", 0.6), parent=head, seg=8)
    for sx in (-1, 1):
        prim("sphere", name + "_auge%d" % sx, (sx * 0.09, 0.22, 0.32), (0.07, 0.04, 0.07), m=mat("Augenweiss", "#efe9e2", 0.25, coat=0.6), parent=head)
        prim("sphere", name + "_pup%d" % sx, (sx * 0.09, 0.24, 0.32), (0.035, 0.02, 0.035), m=mat("Iris", "#1b0f0a", 0.2, coat=1.0), parent=head)
    arms = {}
    for sx in (-1, 1):
        sh = empty(name + "_sh%d" % sx, (sx * 0.28, 0, 1.3), R)
        prim("cyl", name + "_arm%d" % sx, (0, 0, -0.28), (0.12, 0.12, 0.56), m=jacket, parent=sh, seg=10)
        arms[sx] = sh
    v = {"root": R, "head": head, "arms": arms, "home": Vector(loc), "seed": len(VEG)}
    VEG.append(v)
    return v


build_veg("Brokkoli", "brokkoli", (-1.5, 13.6, 0))
build_veg("Paprika", "paprika", (0.0, 14.3, 0))
build_veg("Karotte", "karotte", (1.5, 13.6, 0))


def veg_run(t, b, active):
    for v in VEG:
        if not active:
            v["root"].location = HIDE
            continue
        k = v["seed"]
        hit = pulse(t + k * 0.05, 0.12, 1, 0, NB)
        v["root"].location = v["home"] + Vector((0, 0, hit * 0.12))
        v["root"].rotation_euler = (0, math.sin(t / BEAT * math.pi + k) * 0.12, math.pi + math.sin(t * 0.7 + k) * 0.3)
        v["head"].rotation_euler = (hit * 0.35, 0, math.sin(t * 2 + k) * 0.25)
        for sx, sh in v["arms"].items():
            sh.rotation_euler = (2.4 + 0.5 * (hit if (int(b) + k) % 2 else 1 - hit), 0, -sx * 0.5)


# ------------------------------------------------------------------ Drei Abläufe
def set_world(name):
    set_sky(name)


D_MM = MM_DESK
C_MM = D_MM["cell"]
MM_SEAT = seat_pos(D_MM, -0.29)
MM_SEAT_RZ = C_MM[2] + math.pi
MH_SEAT = cw(C_MM, (0, -0.12, 1.45))
DANCE = True
CAM_OVERRIDE = None
CASE_HOME = CASE["root"].location.copy()
B0 = OFFICE_BIGS[0][0]


def party_cast(t, b, b0, mm_pos=(0.55, 7.4), cg_pos=(-0.55, 8.6), arrive=None):
    """Alle feiern im Hauptgang: Mino Man, Chicken Guy, Pepsi Grandma am Wasserspender, Pinguin, Kuh, Gemüse-Band."""
    place(MM["root"], Vector((mm_pos[0] + math.sin(t * 1.1) * 0.15, mm_pos[1], 0)), math.pi + math.sin(t * 1.1) * 0.3, 1.0)
    pose_mm(t, "tanzen")
    place(CG["root"], Vector((cg_pos[0], cg_pos[1] + math.sin(t * 0.8) * 0.3, 0)), math.pi + math.sin(t * 0.9) * 0.5, CG_S)
    pose_cg(t, 1.0)
    place(GM["root"], Vector((-0.55, 10.4, 0)), math.pi + 0.5, 1.0)
    pose_grandma(t, b, erupt_from=b0 + 2)
    peng_run(t, b, (1.0, 10.9, 0), (1.0, 10.9, 0), 0, 1, dance=True)
    PENG["root"].rotation_euler.z = math.pi + math.sin(t * 2) * 0.4
    cow_run(t, b, (-0.2, 12.6, 0), (-0.2, 12.6, 0), 0, 1, dance=True)
    COW["root"].rotation_euler.z = math.pi + 0.4 * math.sin(t * 0.5)
    veg_run(t, b, True)


def party_spots():
    return [
        ((-0.4, 4.0, 1.6), (0, 9, 1.1), 26),
        (lambda: MM["root"].location + Vector((0.9, -1.6, 1.7)), lambda: mm_head(), 34),
        (lambda: CG["root"].location + Vector((-0.7, -1.7, 1.3)), lambda: cg_head(), 32),
        ((2.2, 4.5, 7.5), (0, 10, 0.5), 22),
        (lambda: GM["root"].location + Vector((0.9, -1.4, 1.5)), lambda: GM["root"].location + Vector((0, 0, 1.4)), 30),
        ((1.1, 2.5, 0.45), (0, 11, 2.4), 20),
        ((0.3, 9.6, 0.6), (-0.2, 12.6, 1.2), 26),
        ((0.0, 10.0, 2.0), (0, 14.3, 1.9), 28),
        (lambda: CG["root"].location + Vector((0.2, -1.0, 0.8)), lambda: cg_head(), 40),
    ]


def office_base(t, b, party, b_party=None):
    office(t, b, party=party, beat_change=party > 0.5)
    bigs_office(t, b)
    pigeons_run(t, b, fly_at=b_party)


def hide_extras():
    for o in (COW, PENG, GM, MU):
        o["root"].location = HIDE
    veg_run(0, 0, False)
    SNEAKER.location = HIDE
    DROP_BIG["root"].location = HIDE



# ================================================================== Runde 6: die Screens stehen im Mittelpunkt
# Raphael zu Runde 5: Screens und Welt stabil, Chicken Guy besser, aber die Kamera war übertrieben. Tanz, Kamera und
# Erzählung wie bei Dat Swag: ruhige, konsistente Einstellungen mit etwas Bounce auf dem Beat. Mehr um die vom Himmel
# hängenden Screens bauen, aus Screens eine Statue formen, die angebetet und umtanzt wird. Das Büro tritt zurück
# (Seiten-Screen, Horizont). Das Büro im Weltall mag er sehr.
SKIES["abend"] = ("#ffd2a0", "#ff9a7a", "#5b46b8", 1.4, 0.0, 26, 175, 2.6, "#ffbf86")
PZ = Vector((0, -2600, 0))          # der Platz: weit weg vom Büro-Raster, das Büro steht nur noch am Horizont
SPACE_ON = True
GATE["root"].location.z = -50


def ds_pulse(b, k=6.0):
    """Dat-Swag-Puls: 1 genau auf dem Schlag, schnell abklingend; vor dem Drop ruhig."""
    return math.exp(-k * (b % 1.0)) if b >= DROP else 0.0


def pop(b, b0, b1=1e9, grow=0.25):
    """Aufpoppen mit kleinem Überschwinger, wieder weg ab b1."""
    if b < b0 or b >= b1:
        return 0.0
    return ease_back(clamp((b - b0) / grow))


def neon(name, col, s=4.0):
    return emit_mat("UI_" + name, col, s)


def sign(name, body, loc, size, col, rz=0.0, parent=None, fnt="anton"):
    """Leuchtschrift in der Welt (diegetisch), Vorderseite zeigt nach -Y (gedreht um rz)."""
    ob = text(name, body, size=size, m=neon(name, col, 5.0), parent=parent, loc=loc, rot=(math.radians(90), 0, rz), fnt=fnt, extrude=0.03)
    no_shadow_obj(ob)
    return ob


# ------------------------------------------------------------------ Kamera wie Dat Swag
# Eine Einstellung alle 4 (selten 2) Schläge, weicher Übergang von ~8 Bildern, ganz leichtes Weiterdriften.
# Bounce: Brennweite +1,6 mm auf jedem Schlag, kleiner Ruck auf den Takt-Einsen. Kein Kippen, keine Stotterfahrten.
SHOTS = []


def shot(b, pos, target, lens=24, trans=0.67, drift=0.0, orbit=0.0, rise=0.0):
    """drift: Meter pro Schlag Richtung Ziel; orbit: Bogenmaß pro Schlag um das Ziel; rise: Meter pro Schlag nach oben."""
    SHOTS.append({"b": b, "pos": pos, "tg": target, "lens": lens, "trans": trans, "drift": drift, "orbit": orbit, "rise": rise})


def _shot_pose(s, b):
    p = Vector(resolve(s["pos"]))
    tg = Vector(resolve(s["tg"]))
    h = max(0.0, b - s["b"])
    if s["orbit"]:
        d = p - tg
        a = s["orbit"] * h
        d = Vector((d.x * math.cos(a) - d.y * math.sin(a), d.x * math.sin(a) + d.y * math.cos(a), d.z))
        p = tg + d
    if s["drift"]:
        p = p + (tg - p).normalized() * s["drift"] * h
    if s["rise"]:
        p = p + Vector((0, 0, s["rise"] * h))
    return p, tg, s["lens"]


SHAKE_AT = []


def ds_camera(b):
    SH = sorted(SHOTS, key=lambda s: s["b"])
    i = max([k for k, s in enumerate(SH) if s["b"] <= b] or [0])
    p, tg, lens = _shot_pose(SH[i], b)
    if i > 0 and SH[i]["trans"] > 0:
        u = smooth((b - SH[i]["b"]) / SH[i]["trans"])
        if u < 1.0:
            p0, t0, l0 = _shot_pose(SH[i - 1], SH[i]["b"])
            p, tg, lens = vlerp(p0, p, u), vlerp(t0, tg, u), lerp(l0, lens, u)
    # Bounce auf dem Beat
    lens = lens + 1.6 * ds_pulse(b)
    sh = 0.0
    for wb, a in SHAKE_AT:
        if 0 <= b - wb < 0.8:
            sh = max(sh, a * math.exp(-(b - wb) * 4.0))
    f = b * BEAT * FPS
    d = (tg - p)
    sh *= max(1.0, d.length * 0.12)
    p = p + Vector((math.sin(f * 2.7), 0, math.cos(f * 3.3))) * sh + Vector((0, 0, -0.025 * ds_pulse(b) * max(1.0, d.length * 0.1)))
    look(p, tg, 0.0, lens)


SHAKE_AT += [(DROP + k * 4 + wb, a) for k in range(9) for wb, a in ((0, 0.04 if k % 2 == 0 else 0.025),)]


# ------------------------------------------------------------------ Tanz wie Dat Swag: Wiegen + Hüpfen, Armmuster wechselt pro Takt
def ds_root(root, base, rz0, b, amp=1.0, s=None):
    k = amp if b >= DROP else amp * 0.4
    root.location = Vector(base) + Vector((0.16 * math.sin(math.pi * b / 2) * k, 0, 0.07 * abs(math.sin(math.pi * b)) * k))
    root.rotation_euler = (0, 0, rz0 + 0.22 * math.sin(math.pi * b / 2) * k)
    if s is not None:
        root.scale = (s, s, s)


DS_MM_BARS = ["pumpen", "zeigen", "rollen", "posen"]


def pose_mm_ds(t, b):
    """Mino Man tanzt im Dat-Swag-Muster: Takt 1 pumpen, 2 zeigen, 3 rollen, 4 Posen auf jedem Schlag."""
    mode = DS_MM_BARS[int(b // 4) % 4]
    hit = ds_pulse(b)
    ph = math.pi * b
    legs, arms = MM["legs"], MM["arms"]
    for sx, (hp, kn) in legs.items():
        st = max(0.0, math.sin(ph + (0 if sx > 0 else math.pi)))
        hp.rotation_euler = (st * 0.35, 0, sx * 0.06)
        kn.rotation_euler = (-st * 0.6, 0, 0)
    MM["torso"].rotation_euler = (0, 0, 0.12 * math.sin(ph))
    MM["neck"].rotation_euler = (0.14 * hit - 0.04, 0, -0.1 * math.sin(ph))
    MM["glint"].scale = (0.022 * (1 + 2 * hit), 0.006, 0.012)
    if mode == "pumpen":
        s_ = math.sin(ph)
        for sx, (sh, el) in arms.items():
            sh.rotation_euler = (0.5 + 0.6 * s_ * sx, 0, -sx * 0.25)
            el.rotation_euler = (1.4, 0, 0)
    elif mode == "zeigen":
        for sx, (sh, el) in arms.items():
            if sx > 0:
                sh.rotation_euler = (2.9 + 0.2 * hit, 0, -0.2)
                el.rotation_euler = (0.1, 0, 0)
            else:
                sh.rotation_euler = (0.3, -0.55, 0)
                el.rotation_euler = (1.7, 0, 0)
    elif mode == "rollen":
        w = 2 * math.pi * b
        for sx, (sh, el) in arms.items():
            sh.rotation_euler = (1.1 + 0.45 * math.sin(w + (0 if sx > 0 else math.pi)), 0, -sx * 0.3)
            el.rotation_euler = (1.4, 0, 0)
    else:
        p = int(b) % 4
        P_ = [((2.9, -0.5), (2.9, -0.5)), ((2.6, 0.1), (0.4, 1.9)), ((0.3, 1.8), (0.3, 1.8)), ((1.57, 0.0), (1.57, 0.0))][p]
        for sx, (sh, el) in arms.items():
            a, e = P_[0] if sx > 0 else P_[1]
            sh.rotation_euler = (a, 0, -sx * (0.45 if a > 2 else 0.15))
            el.rotation_euler = (max(0.0, e) if e > 0 else 0.1, 0, 0)


# ------------------------------------------------------------------ Die Menge: stehende Kolleginnen und Kollegen
SKINS = [mat("HautA", "#d8a688", 0.5, sss=0.2), mat("HautB", "#a8704a", 0.5, sss=0.2), mat("HautC", "#6a4028", 0.5, sss=0.2),
         mat("HautD", "#f0c8a8", 0.5, sss=0.2)]
HAIRS = [HAIR_W, mat("HaarBlond", "#c8a050", 0.8), mat("HaarGrau", "#9a9690", 0.8), mat("HaarRot", "#8a3a1a", 0.8)]
SHOE_M = mat("Schuh", "#1c1a18", 0.5)
TIE_COLS = ["#c4002a", "#1b3fa8", "#2f7a32", "#e2a400"]
CROWD = []


def dancer(name, i):
    shirt = SHIRTS[i % len(SHIRTS)]
    sm = mat("Hemd_" + shirt, shirt, 0.8)
    skin = SKINS[int(hsh(i * 3.1) * len(SKINS))]
    hair = HAIRS[int(hsh(i * 5.3) * len(HAIRS))]
    R = empty(name, HIDE)
    legs = {}
    for sx in (-1, 1):
        lg = empty(name + "_bein%d" % sx, (sx * 0.11, 0, 0.92), R)
        prim("cube", name + "_bn%d" % sx, (0, 0, -0.45), (0.16, 0.18, 0.9), m=PANTS_M, parent=lg, bevel=0.03)
        prim("cube", name + "_sch%d" % sx, (0, 0.05, -0.9), (0.17, 0.3, 0.08), m=SHOE_M, parent=lg)
        legs[sx] = lg
    chest = empty(name + "_brust", (0, 0, 0.92), R)
    prim("cube", name + "_torso", (0, 0, 0.3), (0.42, 0.25, 0.6), m=sm, parent=chest, bevel=0.05)
    prim("cube", name + "_krawatte", (0, 0.13, 0.33), (0.07, 0.02, 0.4), m=mat("Krawatte_" + TIE_COLS[i % 4], TIE_COLS[i % 4], 0.5), parent=chest)
    head = empty(name + "_kopf", (0, 0, 0.62), chest)
    prim("sphere", name + "_schaedel", (0, 0, 0.14), (0.23, 0.25, 0.28), m=skin, parent=head, seg=16)
    prim("sphere", name + "_haar", (0, -0.02, 0.2), (0.245, 0.255, 0.2), m=hair, parent=head, seg=16)
    for sx in (-1, 1):
        prim("sphere", name + "_auge%d" % sx, (sx * 0.07, 0.115, 0.17), (0.035, 0.02, 0.04), m=SHOE_M, parent=head, seg=8)
    arms = {}
    for sx in (-1, 1):
        sh = empty(name + "_sh%d" % sx, (sx * 0.24, 0.0, 0.54), chest)
        prim("cyl", name + "_oa%d" % sx, (0, 0, -0.15), (0.09, 0.09, 0.3), m=sm, parent=sh, seg=10)
        el = empty(name + "_el%d" % sx, (0, 0, -0.3), sh)
        prim("cyl", name + "_ua%d" % sx, (0, 0, -0.14), (0.08, 0.08, 0.28), m=sm, parent=el, seg=10)
        prim("sphere", name + "_hd%d" % sx, (0, 0, -0.3), (0.07, 0.06, 0.08), m=skin, parent=el, seg=10)
        arms[sx] = (sh, el)
    d = {"root": R, "chest": chest, "head": head, "arms": arms, "legs": legs, "seed": i}
    CROWD.append(d)
    return d


def crowd_pose(d, t, b, mode, base, rz, amp=1.0):
    """Modi: walk, stand, bow (anbeten), dance (Dat-Swag-Muster), conga, sit, float."""
    k = d["seed"]
    R, ch, hd = d["root"], d["chest"], d["head"]
    ph = math.pi * b
    hit = ds_pulse(b)
    R.scale = (1, 1, 1)
    for sx, lg in d["legs"].items():
        lg.rotation_euler = (0, 0, 0)
    ch.rotation_euler = (0, 0, 0)
    hd.rotation_euler = (0, 0, 0)
    def arm(sx, x, z=0.0, e=0.2, y=0.0):
        sh, el = d["arms"][sx]
        sh.rotation_euler = (x, y, z)
        el.rotation_euler = (e, 0, 0)
    if mode == "walk":
        st = math.sin(t * 7.5 + k)
        R.location = Vector(base) + Vector((0, 0, abs(st) * 0.04))
        R.rotation_euler = (0, 0, rz)
        for sx, lg in d["legs"].items():
            lg.rotation_euler = (st * 0.45 * sx, 0, 0)
        for sx in (-1, 1):
            arm(sx, -st * 0.4 * sx, -sx * 0.08, 0.3)
        return
    if mode == "sit":
        R.location = Vector(base) + Vector((0, 0, -0.42))
        R.rotation_euler = (0, 0, rz)
        for sx, lg in d["legs"].items():
            lg.rotation_euler = (math.radians(88), 0, 0)
        for sx in (-1, 1):
            arm(sx, 0.5, -sx * 0.05, 1.2)
        hd.rotation_euler = (0.1 * hit, 0, math.sin(t * 0.7 + k) * 0.15)
        return
    if mode == "stand":
        R.location = Vector(base)
        R.rotation_euler = (0, 0, rz + math.sin(t * 0.6 + k) * 0.05)
        for sx in (-1, 1):
            arm(sx, 0.05, -sx * 0.1, 0.25)
        hd.rotation_euler = (-0.25, 0, math.sin(t * 0.8 + k) * 0.2)      # schaut nach oben
        return
    if mode == "bow":
        # Anbeten im Zwei-Schlag-Rhythmus: auf geraden Schlägen tief verbeugen, Arme nach vorn; auf ungeraden aufrichten, Arme hoch
        down = (int(b) % 2 == 0)
        u = smooth((b % 1.0) / 0.35)
        a = u if down else 1 - u
        R.location = Vector(base)
        R.rotation_euler = (0, 0, rz)
        ch.rotation_euler = (-1.05 * a + 0.12 * (1 - a), 0, 0)
        hd.rotation_euler = (0.3 * a - 0.3 * (1 - a), 0, 0)
        for sx in (-1, 1):
            arm(sx, lerp(2.95, 2.5, a), -sx * lerp(0.45, 0.15, a), lerp(0.1, 0.25, a))
        return
    if mode == "conga":
        R.location = Vector(base) + Vector((0, 0, 0.05 * abs(math.sin(ph))))
        R.rotation_euler = (0, 0, rz + 0.12 * math.sin(ph))
        kick = (int(b) % 4 == 3)
        for sx, lg in d["legs"].items():
            if kick and ((int(b // 4) % 2 == 0) == (sx > 0)):
                lg.rotation_euler = (0, -sx * 0.7 * math.sin(clamp(b % 1.0) * math.pi), 0)
            else:
                lg.rotation_euler = (math.sin(ph * 2) * 0.25 * sx, 0, 0)
        for sx in (-1, 1):
            arm(sx, 1.45, sx * 0.25, 0.15)
        ch.rotation_euler = (-0.15, 0.1 * math.sin(ph), 0)
        return
    # dance / float: Dat-Swag-Muster, jeder leicht versetzt
    bb = b + (k % 3) * 0.0
    base2 = Vector(base) + (Vector((0, 0, 0.6 + 0.35 * math.sin(t * 0.9 + k))) if mode == "float" else Vector((0, 0, 0)))
    ds_root(R, base2, rz, bb, amp)
    if mode == "float":
        R.rotation_euler = (0.25 * math.sin(t * 0.7 + k), 0.2 * math.cos(t * 0.6 + k), R.rotation_euler.z)
    bar = (int(bb // 4) + k) % 4
    for sx, lg in d["legs"].items():
        st = max(0.0, math.sin(ph + (0 if sx > 0 else math.pi)))
        lg.rotation_euler = (st * 0.3, 0, 0)
    ch.rotation_euler = (0.06 - 0.06 * hit, 0, 0.18 * math.sin(ph))
    hd.rotation_euler = (0.14 * hit - 0.04, 0, -0.1 * math.sin(ph))
    if bar == 0:
        s_ = math.sin(ph)
        for sx in (-1, 1):
            arm(sx, 0.6 * s_ * sx + 0.3, -sx * 0.25, 1.2)
    elif bar == 1:
        arm(1, 2.9 + 0.25 * hit, -0.2, 0.15)
        arm(-1, 0.2, 0.55, 1.6)
    elif bar == 2:
        w = 2 * math.pi * bb
        for sx in (-1, 1):
            arm(sx, 1.1 + 0.45 * math.sin(w + (0 if sx > 0 else math.pi)), -sx * 0.3, 1.3)
    else:
        p = int(bb) % 4
        if p == 0:
            arm(1, 2.9, -0.5, 0.0); arm(-1, 2.9, 0.5, 0.0)
        elif p == 1:
            arm(1, 2.4, -0.3, 0.0); arm(-1, 0.4, 0.2, 2.0)
        elif p == 2:
            arm(1, 0.3, -0.6, 1.8); arm(-1, 0.3, 0.6, 1.8)
        else:
            arm(1, 1.57, -0.1, 0.0); arm(-1, 1.57, 0.1, 0.0)


N_CROWD = {1: 26, 2: 18, 3: 14, 4: 24, 5: 16}.get(VARIANT, 20)
for i_ in range(N_CROWD):
    dancer("Menge%02d" % i_, i_)


# ------------------------------------------------------------------ Hängende Screens (Pool) und der Büro-Seitenschirm
def mix_clip_mat(name, own_key, other_key, offset=0, ncol=1, nrow=1, col=0, row=0, strength=1.5):
    """Clip-Material mit Umschalter: 0 = eigener Clip, 1 = anderer Clip (optional als Kachel einer Video-Wand)."""
    m, nt, out = node_mat("Mix_" + name)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[1].default_value = strength
    mix = nt.nodes.new("ShaderNodeMixRGB")
    val = nt.nodes.new("ShaderNodeValue")
    val.outputs[0].default_value = 0.0
    nt.links.new(val.outputs[0], mix.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    for slot, key, tiled in ((1, own_key, False), (2, other_key, True)):
        path = os.path.join(CLIP_DIR, "tex_%s.mp4" % key)
        if os.path.exists(path):
            img = bpy.data.images.load(path, check_existing=True)
            img.source = "MOVIE"
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            iu = tex.image_user
            iu.frame_duration = max(30, int(getattr(img, "frame_duration", 0) or 300))
            iu.frame_start = 1 - (offset % iu.frame_duration if slot == 1 else 0)
            iu.frame_offset = 0
            iu.use_cyclic = True
            iu.use_auto_refresh = True
            src = tex.outputs["Color"]
        else:
            tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 6.0
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.elements[0].color = hexcol(CLIP_FALLBACK.get(key, "#7a3cff"))
            ramp.color_ramp.elements[1].color = hexcol("#ffe34a" if slot == 1 else "#ffffff")
            nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
            src = ramp.outputs["Color"]
        if tiled and (ncol > 1 or nrow > 1):
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (1.0 / ncol, 1.0 / nrow, 1)
            mp.inputs["Location"].default_value = (col / ncol, row / nrow, 0)
            nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        else:
            nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(src, mix.inputs[slot])
    nt.links.new(mix.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, val


def pool_screen(name, key, h=9.0, label="MINO TV", offset=0, m=None):
    s = big_screen(name, key, h, label=label, offset=offset)
    if m is not None:
        s["screen"].data.materials.clear()
        s["screen"].data.materials.append(m)
    return s


POOL_KEYS = ["cg2", "mm", "gm2", "e1", "ig1", "e2", "cg2", "ig2", "e3", "mm", "ig3", "e4", "gm2", "e5", "ig4", "e6"]
POOL = []
SWITCH = []          # Umschalter "alle zeigen Chicken Guy" (Variante 5)
for i_, k_ in enumerate(POOL_KEYS):
    if VARIANT == 5:
        m_, v_ = mix_clip_mat("Pool%02d" % i_, k_, "cg", offset=i_ * 37)
        SWITCH.append(v_)
        POOL.append(pool_screen("Schirm%02d" % i_, k_, 9.0, offset=i_ * 37, m=m_))
    else:
        POOL.append(pool_screen("Schirm%02d" % i_, k_, 9.0, offset=i_ * 37))

OFFICE_CAM = big_screen("BueroKamera", "office", 6.0, label="OFFICE CAM  LIVE", offset=0)


def hang(s, pos, rz, t, scale=1.0, sway=1.0):
    """Hängt am Seil vom Himmel, schwingt leicht."""
    s["root"].location = Vector(pos) + Vector((0, 0, math.sin(t * 0.5 + pos[0] * 0.3) * 0.25 * sway))
    s["root"].rotation_euler = (math.sin(t * 0.9 + hsh(pos[0])) * 0.03 * sway, math.sin(t * 0.6 + pos[1]) * 0.02 * sway, rz)
    s["root"].scale = (scale, scale, scale)


def pose_lerp(s, pa, ra, sa, pb, rb, sb, u, t, sway=1.0):
    p = vlerp(pa, pb, u)
    r = (lerp(ra[0], rb[0], u), lerp(ra[1], rb[1], u), lerp(ra[2], rb[2], u))
    sc = lerp(sa, sb, u)
    s["root"].location = p + Vector((0, 0, math.sin(t * 0.5 + pa[0] * 0.3) * 0.25 * sway * (1 - u)))
    s["root"].rotation_euler = r
    s["root"].scale = (sc, sc, sc)


def hide_pool():
    for s in POOL:
        s["root"].location = HIDE
    OFFICE_CAM["root"].location = HIDE


hide_pool()


# ------------------------------------------------------------------ Die Screen-Statue: hängende Screens bilden eine Figur
# Teile (lokal, Figur schaut nach -Y): Beine, Rumpf, Arme, Kopf, Krone. Werte in Metern bei Maßstab 1.
IDOL_PARTS = [
    # (name, pool-index, ort x/z, drehung um y, maßstab)
    ("bein_l", 3, (-2.2, 3.7), 0.0, 0.8),
    ("bein_r", 5, (2.2, 3.7), 0.0, 0.8),
    ("rumpf_l", 1, (-2.35, 11.6), 0.0, 0.88),
    ("rumpf_r", 9, (2.35, 11.6), 0.0, 0.88),
    ("arm_l", 4, (-7.0, 12.6), -0.75, 0.72),
    ("arm_r", 7, (7.0, 12.6), 0.75, 0.72),
    ("kopf", 0, (0.0, 19.6), 0.0, 0.8),
    ("krone_l", 10, (-3.2, 24.6), -0.45, 0.38),
    ("krone_m", 6, (0.0, 25.4), 0.0, 0.42),
    ("krone_r", 14, (3.2, 24.6), 0.45, 0.38),
]


def idol_pose(i, C, S, rz, arms_up=0.0, nod=0.0):
    """Zielpose von Teil i: Weltort, Drehung, Maßstab. arms_up hebt die Arm-Screens (die Statue erwacht)."""
    name, pi_, (x, z), ry, sc = IDOL_PARTS[i]
    if name.startswith("arm"):
        sx = -1 if name.endswith("l") else 1
        ang = lerp(ry, sx * 2.3, arms_up)
        # um die Schulter (x = ±4.4, z = 15.5) drehen
        sh = Vector((sx * 4.4, 0, 15.5))
        v = Vector((x, 0, z)) - Vector((sx * 4.4, 0, 15.5))
        a = ang - ry
        v = Vector((v.x * math.cos(a) + v.z * math.sin(a), 0, -v.x * math.sin(a) + v.z * math.cos(a)))
        x, z = (sh + v).x, (sh + v).z
        ry = ang
    if name == "kopf" or name.startswith("krone"):
        z -= nod * 0.6
    local = Vector((x, 0, z)) * S
    loc = C + Matrix.Rotation(rz, 3, "Z") @ local
    # Screen schaut lokal nach +Y; Figur schaut nach -Y -> pi um z
    return loc, (0.0, ry, rz + math.pi), sc * S


def idol_run(t, b, C, S, rz, hang_spots, b_start, step=1.0, arms_up=0.0, scatter=None):
    """Vor b_start hängen die Teile verstreut am Himmel, dann rastet pro Schlag ein Teil in der Figur ein."""
    nod = ds_pulse(b) * 0.5 if b >= b_start + len(IDOL_PARTS) * step else 0.0
    for i, (name, pi_, xz, ry, sc) in enumerate(IDOL_PARTS):
        s = POOL[pi_]
        pb, rb, sb = idol_pose(i, C, S, rz, arms_up, nod)
        hp, hrz, hs = hang_spots[i]
        bi = b_start + i * step
        if b < bi:
            if scatter:
                scatter(s, i, t, b)
            else:
                hang(s, hp, hrz, t, hs)
        else:
            u = ease_back(clamp((b - bi) / 0.6))
            ra = (0.0, 0.0, hrz)
            pose_lerp(s, Vector(hp), ra, hs, pb, rb, sb, u, t, sway=0.0)


# Sockel: Pyramide aus beigen Röhrenmonitoren
PEDESTAL = []


def build_pedestal(C, n=(4, 3, 2), size=1.6, rz=0.0):
    z = 0.0
    for lvl, cnt in enumerate(n):
        for j in range(cnt):
            x = (j - (cnt - 1) / 2) * size * 1.12
            mon = monitor("Sockel%d_%d_%d" % (VARIANT, lvl, j), C + Matrix.Rotation(rz, 3, "Z") @ Vector((x, -0.2, z)), rz + math.pi,
                          PROG_ORDER[(lvl * 3 + j) % 7], size=size)
            PEDESTAL.append(mon)
        z += size * 0.86 + 0.06
    return z


# ------------------------------------------------------------------ Kirchenbänke aus Bürostühlen
def pews(C, rows=3, per_row=7, gap=1.25, row_gap=1.6, rz=0.0, name="Bank"):
    parts = []
    for r in range(rows):
        for j in range(per_row):
            x = (j - (per_row - 1) / 2) * gap
            y = -r * row_gap
            parts += [("b", (x, y, 0.48), (0.5, 0.48, 0.08), 0), ("b", (x, y - 0.22, 0.82), (0.48, 0.07, 0.55), 0),
                      ("b", (x, y, 0.24), (0.06, 0.06, 0.45), 1), ("b", (x, y, 0.03), (0.55, 0.08, 0.04), 1), ("b", (x, y, 0.03), (0.08, 0.55, 0.04), 1)]
    ob = parts_mesh(name, parts, [CHAIR_M, LEG_M], loc=C, rot=(0, 0, rz))
    return ob


def pew_seat(C, r, j, per_row=7, gap=1.25, row_gap=1.6, rz=0.0):
    x = (j - (per_row - 1) / 2) * gap
    y = -r * row_gap
    return C + Matrix.Rotation(rz, 3, "Z") @ Vector((x, y - 0.05, 0))


# ------------------------------------------------------------------ Gemeinsame Abläufe pro Bild
def world_space(t, b):
    c = WX["orbit"]
    PLANET.rotation_euler.z = t * 0.01
    ISLAND.rotation_euler.z = 0.0
    ISLAND.location.z = c.z + math.sin(t * 0.5) * 0.15
    for i, p in enumerate(SPACE_PAPER):
        p.location = c + Vector(((hsh(i * 2.1) - .5) * 40, 4 + hsh(i * 3.3) * 40, (hsh(i * 5.7) - .5) * 12 + 3 + math.sin(t + i) * 0.8))
        p.rotation_euler = (t * (0.5 + hsh(i)) + i, t * 0.3 + i, i)
    for i, o in enumerate(SPACE_CHAIRS):
        o.location = c + Vector(((hsh(i * 9.1) - .5) * 24, 10 + hsh(i * 4.4) * 22, 3 + (hsh(i * 2.2) - .5) * 6 + math.sin(t * 0.7 + i)))
        o.rotation_euler = (t * 0.4 + i, t * 0.25, t * 0.3 + i)
    SPACE_COOLER.location = c + Vector((-7, 14, 4 + math.sin(t * 0.6)))
    SPACE_COOLER.rotation_euler = (t * 0.3, 0.4, t * 0.2)


def base_frame(t, b, party=0.0):
    hide_extras()
    SPACE_BIG["root"].location = HIDE
    office(t, b, party=party, beat_change=party > 0.5)
    MU["root"].location = HIDE
    if SPACE_ON:
        set_world("orbit")
        world_space(t, b)
    else:
        DESK_MM.location = HIDE
        DESK_CG.location = HIDE


def crowd_ring(t, b, C, r0, mode, rz_face=None, n=None, r_step=1.6, per=12, start_a=0.0, arc=math.tau, amp=1.0):
    """Menge im Kreis (oder Bogen) um C, alle schauen zur Mitte."""
    n = n or len(CROWD)
    for i, d in enumerate(CROWD[:n]):
        ring_i, j = divmod(i, per)
        r = r0 + ring_i * r_step
        a = start_a + (j + 0.5 * (ring_i % 2)) / per * arc
        p = C + Vector((math.sin(a) * r, -math.cos(a) * r, 0))
        face = math.atan2(-(C - p).x, (C - p).y) if rz_face is None else rz_face
        crowd_pose(d, t, b, mode, p, face, amp)
    for d in CROWD[n:]:
        d["root"].location = HIDE


def crowd_hide():
    for d in CROWD:
        d["root"].location = HIDE


def face_to(p, q):
    d = Vector(q) - Vector(p)
    return math.atan2(-d.x, d.y)


# ================================================================== Fünf Abläufe
def scatter_spots(n, C, seed, rx=(-16, 16), ry=(4, 32), rz_=(10, 22), sc=(0.55, 0.75)):
    out = []
    for i in range(n):
        x = lerp(rx[0], rx[1], hsh(i * 3.7 + seed))
        y = lerp(ry[0], ry[1], hsh(i * 5.1 + seed * 2))
        z = lerp(rz_[0], rz_[1], hsh(i * 7.3 + seed * 3))
        out.append((C + Vector((x, y, z)), math.pi + (hsh(i * 2.2 + seed) - 0.5) * 0.7, lerp(sc[0], sc[1], hsh(i * 9.1 + seed))))
    return out


def fall_cg(t, b, b0, b1, at, rz=math.pi):
    """Chicken Guy fällt vom Himmel und landet auf Schlag b1 (kleines Stauchen)."""
    if b < b0:
        place(CG["root"], HIDE)
        return False
    if b < b1:
        u = (b - b0) / (b1 - b0)
        place(CG["root"], Vector(at) + Vector((0, 0, 14 * (1 - u) ** 2)), rz + u * 4, CG_S)
        pose_cg(t, 1.0, "flattern")
        return False
    return True


def mm_walk(t, b, p0, p1, b0, b1):
    k = clamp((b - b0) / max(0.01, b1 - b0))
    p = vlerp(p0, p1, smooth(k) * 0.3 + 0.7 * k)
    place(MM["root"], p, face_to(p0, p1), 1.0)
    st = math.sin(t * 7.5)
    for sx, (hp, kn) in MM["legs"].items():
        hp.rotation_euler = (st * 0.45 * sx, 0, sx * 0.06)
        kn.rotation_euler = (-max(0.0, -st * sx) * 0.6, 0, 0)
    for sx, (sh, el) in MM["arms"].items():
        sh.rotation_euler = (-st * 0.35 * sx + 0.1, 0, -sx * 0.1)
        el.rotation_euler = (0.3, 0, 0)
    MM["torso"].rotation_euler = (0, 0, 0)
    MM["neck"].rotation_euler = (0, 0, 0)


def mm_stand(t, p, rz, look_up=0.0):
    place(MM["root"], p, rz, 1.0)
    for sx, (hp, kn) in MM["legs"].items():
        hp.rotation_euler = (0, 0, sx * 0.06)
        kn.rotation_euler = (0, 0, 0)
    for sx, (sh, el) in MM["arms"].items():
        sh.rotation_euler = (0.05, 0, -sx * 0.08)
        el.rotation_euler = (0.2, 0, 0)
    MM["torso"].rotation_euler = (0, 0, 0)
    MM["neck"].rotation_euler = (-0.45 * look_up, 0, math.sin(t * 0.7) * 0.05)


def mm_ds(t, b, p, rz, amp=1.0):
    ds_root(MM["root"], p, rz, b, amp, 1.0)
    pose_mm_ds(t, b)


def cg_ds(t, b, p, rz, wild=1.0):
    ds_root(CG["root"], p, rz, b, 0.8, CG_S)
    pose_cg(t, wild)






# ================================================================== Runde 8: MINO DRIFT
# Raphael zu Runde 7: zurück zu den Ideen aus Büro v2/v3 und Office v2/v3 (Hot-Dog-Fabrik, Surfen, Weltall), aber mit der
# ruhigen Dat-Swag-Kamera. Anker ist das Weltall-Büro, die Figuren gleiten durch Screens von Welt zu Welt. Mehr Swag
# (Mino Mans Anzug, Chicken Guy mit Sonnenbrille, Bandana, Goldkette), mehr zufällige Kleinigkeiten, knalligere Farben.
SPACE_ON = True
FWV = WX["fabrik"]
GATE["root"].location.z = -50
hide_pool()
CLIP_FALLBACK.update({"cg2": "#c4002a", "gm2": "#1f4fd0"})

# --- Farben: heller, gesättigter, mehr Kontrast
SKIES.update({
    "orbit":  ("#8a3cff", "#2c138f", "#070322", 1.5, 1.0, 160, 1400, 3.8, "#ffffff"),
    "fabrik": ("#ff7a2a", "#8a1fb8", "#16051f", 0.0, 0.0, 10, 80, 0.8, "#ffc080"),
    "pepsi":  ("#b8f8ff", "#20c0ff", "#0038f0", 1.3, 0.0, 30, 240, 4.0, "#ffffff"),
    "tunnel": ("#ff2fa8", "#3a0a9a", "#050012", 0.0, 1.0, 70, 420, 0.4, "#ffffff"),
    "regen":  ("#ffe84a", "#ff5fc0", "#7a2cff", 1.8, 0.0, 34, 230, 3.6, "#ffe6c8"),
    "buero":  ("#c8f2ff", "#5ab2ff", "#1458ff", 1.1, 0.0, 24, 185, 3.6, "#fff1d6"),
})
PLANET.data.materials.clear()
PLANET.data.materials.append(noise_mat("PlanetBunt", "#0a62ff", "#1fd86a", scale=1.6, rough=0.6, bump=0.1, c2="#ffffff", detail=8))
for _n, _e in (("Fabriklicht%d" % k, 1500) for k in range(5)):
    if _n in bpy.data.objects:
        bpy.data.objects[_n].data.energy = _e
for _k, (_c, _x) in enumerate((("#ff2fa8", -6.2), ("#20e6ff", 6.2))):
    prim("cube", "FabrikNeon%d" % _k, (_x, 30, 5.2), (0.12, 70, 0.12), m=emit_mat("FabNeon%d" % _k, _c, 8.0), parent=FW)
sign("FabrikSchild4", "NOW HIRING: DANCERS", FWV + Vector((-6.0, 30, 3.8)), 0.5, "#7cff4a", rz=math.radians(-60))


def kk(b, b0, b1):
    return clamp((b - b0) / max(0.001, b1 - b0))


def put(root, p, rz=0.0, s=1.0, rx=0.0, ry=0.0):
    root.location = p
    root.rotation_euler = (rx, ry, rz)
    root.scale = (s, s, s)


def descendants(ob):
    out = []
    for ch in ob.children:
        out.append(ch)
        out += descendants(ch)
    return out


# ------------------------------------------------------------------ Swag: Mino Man im verspielten Anzug, Goldkette
def dots_mat(name, base, dot1, dot2, scale=7.0, rough=0.4, coat=0.3):
    m, nt, out = node_mat(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = rough
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    tc = nt.nodes.new("ShaderNodeTexCoord")
    col = None
    for k, (c, sc, rad) in enumerate(((dot1, scale, 0.17), (dot2, scale * 1.7, 0.12))):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (0.37 * k, 0.21 * k, 0.11 * k)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        vo = nt.nodes.new("ShaderNodeTexVoronoi")
        vo.inputs["Scale"].default_value = sc
        if "Randomness" in vo.inputs:
            vo.inputs["Randomness"].default_value = 0.55
        nt.links.new(mp.outputs["Vector"], vo.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = rad
        mr.inputs["From Max"].default_value = rad - 0.02
        nt.links.new(vo.outputs["Distance"], mr.inputs["Value"])
        mx = nt.nodes.new("ShaderNodeMixRGB")
        nt.links.new(mr.outputs[0], mx.inputs[0])
        if col is None:
            mx.inputs[1].default_value = hexcol(base)
        else:
            nt.links.new(col, mx.inputs[1])
        mx.inputs[2].default_value = hexcol(c)
        col = mx.outputs[0]
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


GOLD = mat("Gold", "#ffc21a", 0.22, metal=1.0, emit="#ff9a00", estr=0.15)
SUIT_SWAG = dots_mat("AnzugSwag", "#7b2cff", "#ffe14a", "#2ff0c8", scale=6.5)
LAPEL_SWAG = mat("ReversSwag", "#ffd21a", 0.3, coat=0.8)
TIE_SWAG = mat("KrawatteSwag", "#ff2f9a", 0.3, coat=0.8)
SNEAK_W = mat("SneakerWeissMM", "#f8f6f0", 0.4)
for ob in descendants(MM["root"]):
    if ob.type != "MESH":
        continue
    n = ob.name
    if any(n.startswith(p) for p in ("MM_torso", "MM_oberarm", "MM_unterarm", "MM_oberschenkel", "MM_unterschenkel")):
        ob.data.materials.clear(); ob.data.materials.append(SUIT_SWAG)
    elif n.startswith("MM_revers"):
        ob.data.materials.clear(); ob.data.materials.append(LAPEL_SWAG)
    elif n.startswith("MM_krawatte") or n.startswith("MM_knoten"):
        ob.data.materials.clear(); ob.data.materials.append(TIE_SWAG)
    elif n.startswith("MM_schuh"):
        ob.data.materials.clear(); ob.data.materials.append(SNEAK_W)
for sx in (-1, 1):
    k_ = [o for o in descendants(MM["root"]) if o.name == "MM_schuh%d" % sx]
    if k_:
        prim("cube", "MM_sohle%d" % sx, (0, 0.05, -0.445), (0.135, 0.29, 0.03), m=mat("SohleRot", "#ff2a2a", 0.5), parent=k_[0].parent)
_mm_chain = [Vector((0.15 * math.sin(a), 0.03 + 0.17 * math.cos(a), 1.47 - 0.2 * (0.5 + 0.5 * math.cos(a)) ** 2))
             for a in (i / 16 * math.tau for i in range(16))]
curve_obj("MM_kette", _mm_chain, radius=0.012, m=GOLD, parent=MM["root"], closed=True)
prim("cyl", "MM_anhaenger", (0, 0.205, 1.25), (0.09, 0.09, 0.02), rot=(math.radians(90), 0, 0), m=GOLD, parent=MM["root"], seg=24)
text("MM_anhaenger_m", "M", size=0.07, m=mat("AnhaengerSchrift", "#6a3a00", 0.4), parent=MM["root"], loc=(0, 0.217, 1.248),
     rot=(math.radians(90), 0, 0), fnt="anton")
prim("cube", "MM_einstecktuch", (0.17, 0.155, 1.4), (0.08, 0.02, 0.05), rot=(0, 0, 0), m=mat("Tuch", "#2ff0c8", 0.5), parent=MM["root"])


# ------------------------------------------------------------------ Swag: Chicken Guy mit Sonnenbrille, Bandana, Goldkette
def bandana_mat():
    m, nt, out = node_mat("Bandana")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.7
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = 70.0
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.22
    mr.inputs["From Max"].default_value = 0.17
    nt.links.new(vo.outputs["Distance"], mr.inputs["Value"])
    mx = nt.nodes.new("ShaderNodeMixRGB")
    nt.links.new(mr.outputs[0], mx.inputs[0])
    mx.inputs[1].default_value = hexcol("#e3121c")
    mx.inputs[2].default_value = hexcol("#ffffff")
    nt.links.new(mx.outputs[0], b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


BANDANA_M = bandana_mat()
SHADES_M = mat("Sonnenglas", "#05020a", 0.08, metal=0.6, coat=1.0, emit="#ff2fa8", estr=0.15)
SHADES_TINT = mat("SonnenglasRand", "#ff2fa8", 0.05, coat=1.0, emit="#ff2fa8", estr=0.4)
CH = CG["head"]
if CG.get("real"):
    # Koordinaten im Kopfraum des MakeHuman-Kopfes (Augen bei y 0.09, z 0.041; Breite ±0.089; Scheitel z 0.158)
    for sx in (-1, 1):
        prim("sphere", "CG_sonnenglas%d" % sx, (sx * 0.033, 0.127, 0.044), (0.04, 0.016, 0.03), m=SHADES_M, parent=CH, seg=24)
        prim("torus", "CG_sonnenrand%d" % sx, (sx * 0.033, 0.128, 0.044), (0.042, 0.042, 0.03), rot=(math.radians(90), 0, 0),
             m=GOLD, parent=CH, seg=24).scale = (0.043, 0.032, 0.03)
        curve_obj("CG_buegel%d" % sx, [Vector((sx * 0.054, 0.124, 0.05)), Vector((sx * 0.08, 0.085, 0.052)), Vector((sx * 0.088, 0.02, 0.045))],
                  radius=0.0022, m=GOLD, parent=CH)
    curve_obj("CG_steg", [Vector((-0.013, 0.131, 0.05)), Vector((0, 0.134, 0.054)), Vector((0.013, 0.131, 0.05))], radius=0.002, m=GOLD, parent=CH)
    bd = half_sphere("CG_bandana", 1, (0.196, 0.24, 0.205), BANDANA_M, CH)
    bd.location = (0, 0.012, 0.072)
    bd.rotation_euler = (math.radians(-6), 0, 0)
    prim("sphere", "CG_bandknoten", (0, -0.11, 0.085), (0.04, 0.03, 0.035), m=BANDANA_M, parent=CH)
    for sx in (-1, 1):
        prim("cone", "CG_bandzipfel%d" % sx, (sx * 0.018, -0.118, 0.05), (0.045, 0.012, 0.07), rot=(math.radians(165), sx * 0.3, 0),
             m=BANDANA_M, parent=CH, seg=8)
_cg_chain = [Vector((0.25 * math.sin(a), 0.04 + 0.25 * math.cos(a), 0.31 - 0.23 * (0.5 + 0.5 * math.cos(a)) ** 2))
             for a in (i / 20 * math.tau for i in range(20))]
curve_obj("CG_kette", _cg_chain, radius=0.022, m=GOLD, parent=CG["body"], closed=True)
prim("cyl", "CG_medaillon", (0, 0.3, 0.05), (0.16, 0.16, 0.03), rot=(math.radians(90), 0, 0), m=GOLD, parent=CG["body"], seg=32)
text("CG_medaillon_s", "$", size=0.13, m=mat("MedaillonSchrift", "#6a3a00", 0.4), parent=CG["body"], loc=(0, 0.318, 0.05),
     rot=(math.radians(90), 0, 0), fnt="anton")


def pose_mm_fly(t, b, sup=1.0):
    """Superman-Flug: ein Arm nach vorn, Beine gestreckt (Körper wird über root gekippt)."""
    hit = ds_pulse(b)
    for sx, (hp, kn) in MM["legs"].items():
        hp.rotation_euler = (0.08 * math.sin(t * 6 + sx), 0, sx * 0.08)
        kn.rotation_euler = (-0.15 - 0.1 * math.sin(t * 6 + sx), 0, 0)
    for sx, (sh, el) in MM["arms"].items():
        if sx > 0:
            sh.rotation_euler = (2.95 * sup, 0, -0.15)
            el.rotation_euler = (0.05, 0, 0)
        else:
            sh.rotation_euler = (0.2 + 2.6 * (1 - sup), 0, 0.35)
            el.rotation_euler = (0.4, 0, 0)
    MM["torso"].rotation_euler = (0, 0, 0)
    MM["neck"].rotation_euler = (-0.6 * sup + 0.1 * hit, 0, 0)


# ------------------------------------------------------------------ Weltall-Insel: vorn Tanzfläche statt Kabinen
for ob in list(ISLAND.children):
    nm = ob.name
    if nm.startswith("InselKabine") or nm.startswith("InselKollege"):
        iy = int(nm[-1]) - 2
        if iy < 1:
            bpy.data.objects.remove(ob, do_unlink=True)
FLOOR_COLS = ["#ff2fa8", "#20e6ff", "#ffe14a", "#7cff4a", "#a040ff"]
FLOOR_M = [emit_mat("Tanzboden%d" % k, c, 2.2) for k, c in enumerate(FLOOR_COLS)]
FLOOR_TILES = []
for ix in range(8):
    for iy in range(5):
        tl = prim("cube", "Fliese%d%d" % (ix, iy), ((ix - 3.5) * 2.2, -8.6 + iy * 2.1, 0.02), (2.1, 2.0, 0.06), m=FLOOR_M[(ix + iy) % 5], parent=ISLAND)
        FLOOR_TILES.append((tl, ix, iy))
for k, (c, y) in enumerate((("#ff2fa8", -9.62), ("#20e6ff", 9.62))):
    prim("cube", "InselNeon%d" % k, (0, y, -0.2), (19.4, 0.12, 0.12), m=emit_mat("InselNeon%d" % k, c, 6.0), parent=ISLAND)
    prim("cube", "InselNeonS%d" % k, (y, 0, -0.2), (0.12, 19.4, 0.12), m=emit_mat("InselNeon%d" % k, c, 6.0), parent=ISLAND)
ISL_SIGN = sign("InselSchild", "MINOVERSE ORBITAL OFFICE", ISLAND.location + Vector((0, 9.0, 4.2)), 0.9, "#ffe14a")
ISL_SIGN.parent = ISLAND
ISL_SIGN.location = (0, 9.4, 4.0)
sign("InselSchild2", "FLOOR 0  -  NO GRAVITY  -  DANCING MANDATORY", ISLAND.location, 0.32, "#20e6ff", parent=ISLAND, fnt="barlow").location = (0, 9.4, 3.1)


def floor_run(b, on=True):
    for tl, ix, iy in FLOOR_TILES:
        k = (ix * 3 + iy * 7 + int(b) * (1 if on else 0)) % 5 if on else (ix + iy) % 5
        if b >= DROP:
            k = (ix + iy + int(b)) % 5 if int(b // 4) % 2 == 0 else (ix * iy + int(b) * 2) % 5
        tl.material_slots[0].material = FLOOR_M[k]


# ------------------------------------------------------------------ Kleinkram und Easter Eggs
def build_ufo():
    R = empty("UFO", HIDE)
    metal = mat("UFOmetall", "#c8ccd8", 0.2, metal=1.0)
    prim("sphere", "UFO_scheibe", (0, 0, 0), (4.4, 4.4, 0.9), m=metal, parent=R, seg=48)
    prim("sphere", "UFO_kuppel", (0, 0, 0.45), (1.9, 1.9, 1.3), m=mat("UFOglas", "#7fe9ff", 0.05, coat=1.0, emit="#3fd8ff", estr=0.6), parent=R, seg=32)
    lights = []
    for i in range(10):
        a = i / 10 * math.tau
        lights.append(prim("sphere", "UFO_licht%d" % i, (math.cos(a) * 2.05, math.sin(a) * 2.05, -0.05), (0.28, 0.28, 0.2),
                           m=emit_mat("UFOlicht%d" % (i % 3), ["#ff2fa8", "#7cff4a", "#ffe14a"][i % 3], 8.0), parent=R, seg=12))
    bm, nt, out = node_mat("UI_UFOstrahl")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = hexcol("#9dff6a"); em.inputs[1].default_value = 2.5
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    ms = nt.nodes.new("ShaderNodeMixShader"); ms.inputs[0].default_value = 0.28
    nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(em.outputs[0], ms.inputs[2]); nt.links.new(ms.outputs[0], out.inputs[0])
    for attr, v in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(bm, attr):
            try:
                setattr(bm, attr, v)
            except Exception:   # noqa: BLE001
                pass
    beam = prim("cone", "UFO_strahl", (0, 0, -6.2), (5.0, 5.0, 12.0), m=bm, parent=R, seg=32)
    no_shadow_obj(beam)
    return {"root": R, "lights": lights, "beam": beam}


UFO = build_ufo()


def ufo_run(t, b, pos, beam=True):
    UFO["root"].location = Vector(pos) + Vector((math.sin(t * 0.7) * 0.4, 0, math.sin(t * 1.3) * 0.3))
    UFO["root"].rotation_euler = (0.06 * math.sin(t), 0.05 * math.cos(t * 0.8), t * 1.2)
    UFO["beam"].scale = (5.0, 5.0, 12.0) if beam else (0, 0, 0)


def build_satellite():
    R = empty("Satellit", HIDE)
    foil = mat("Goldfolie", "#ffb21a", 0.3, metal=1.0)
    prim("cube", "Sat_koerper", (0, 0, 0), (1.6, 1.6, 2.0), m=foil, parent=R, bevel=0.05)
    panel = noise_mat("Solarzelle", "#0a1a8a", "#2a5aff", scale=12, rough=0.2, bump=0.05)
    for sx in (-1, 1):
        prim("cube", "Sat_panel%d" % sx, (sx * 3.4, 0, 0), (4.6, 0.06, 1.6), m=panel, parent=R)
        prim("cyl", "Sat_arm%d" % sx, (sx * 1.0, 0, 0), (0.08, 0.08, 1.0), rot=(0, math.radians(90), 0), m=STEEL, parent=R, seg=8)
    prim("sphere", "Sat_schuessel", (0, -0.2, 1.6), (1.8, 1.8, 0.5), m=mat("Schuessel", "#f2f2f2", 0.4), parent=R, seg=24)
    sign("Sat_schild", "VEGAN HOT DOG RAIN PROGRAM", (0, -0.85, 0.3), 0.22, "#7cff4a", parent=R, fnt="barlow")
    sign("Sat_schild2", "STATUS: STILL TESTING", (0, -0.85, -0.1), 0.18, "#ffe14a", parent=R, fnt="barlow")
    return R


SAT = build_satellite()


def build_toaster():
    R = empty("Toaster", HIDE)
    chrome = mat("Chrom", "#e8ecf4", 0.08, metal=1.0)
    prim("cube", "To_koerper", (0, 0, 0), (1.2, 0.7, 0.8), m=chrome, parent=R, bevel=0.15)
    for sx in (-1, 1):
        prim("cube", "To_schlitz%d" % sx, (sx * 0.22, 0, 0.41), (0.12, 0.5, 0.02), m=mat("Schlitz", "#111111", 0.6), parent=R)
    wings = []
    for sx in (-1, 1):
        piv = empty("To_fluegelpiv%d" % sx, (0, sx * 0.36, 0.2), R)
        prim("sphere", "To_fluegel%d" % sx, (0, sx * 0.55, 0.1), (0.9, 1.1, 0.06), m=mat("Fluegel", "#ffffff", 0.6, emit="#ffffff", estr=0.3), parent=piv, seg=16)
        wings.append((piv, sx))
    toast = [prim("cube", "Toast%d" % i, HIDE, (0.5, 0.12, 0.5), m=noise_mat("Toast", "#c07a2a", "#e8b060", scale=20, rough=0.8, bump=0.3), seg=8) for i in range(2)]
    return {"root": R, "wings": wings, "toast": toast}


TOASTER = build_toaster()


def toaster_run(t, b, p0, p1, b0, b1):
    if not (b0 <= b < b1):
        TOASTER["root"].location = HIDE
        for o in TOASTER["toast"]:
            o.location = HIDE
        return
    u = kk(b, b0, b1)
    p = vlerp(Vector(p0), Vector(p1), u) + Vector((0, 0, math.sin(u * math.pi * 3) * 0.8))
    d = Vector(p1) - Vector(p0)
    TOASTER["root"].location = p
    TOASTER["root"].rotation_euler = (0.1 * math.sin(t * 3), 0, math.atan2(d.y, d.x) - math.pi / 2)
    for piv, sx in TOASTER["wings"]:
        piv.rotation_euler = (sx * (0.6 * math.sin(t * 14)), 0, 0)
    for i, o in enumerate(TOASTER["toast"]):
        ph = ((b - b0) * 0.5 + i * 0.5) % 1.0
        o.location = p + Vector(((i - 0.5) * 0.4, 0, 0.5 + ph * 3.0))
        o.rotation_euler = (ph * 6, ph * 3, 0)


def build_duck():
    R = empty("Gummiente", HIDE)
    y = mat("Entengelb", "#ffd51a", 0.25, coat=0.9)
    prim("sphere", "En_koerper", (0, 0, 0.9), (3.6, 2.6, 2.0), m=y, parent=R, seg=32)
    prim("sphere", "En_kopf", (0, 0.9, 2.3), (1.7, 1.7, 1.7), m=y, parent=R, seg=32)
    prim("cone", "En_schnabel", (0, 1.85, 2.15), (0.9, 0.9, 0.9), rot=(math.radians(-90), 0, 0), m=mat("Schnabel", "#ff7a1a", 0.3, coat=0.8), parent=R, seg=16).scale = (0.9, 0.9, 0.55)
    for sx in (-1, 1):
        prim("sphere", "En_auge%d" % sx, (sx * 0.45, 1.55, 2.6), (0.32, 0.2, 0.36), m=mat("Entenauge", "#111111", 0.2, coat=1.0), parent=R, seg=16)
    prim("cone", "En_schwanz", (0, -1.6, 1.4), (0.9, 0.9, 1.0), rot=(math.radians(120), 0, 0), m=y, parent=R, seg=16)
    return R


DUCK = build_duck()


def build_jetski():
    R = empty("Jetski", HIDE)
    prim("sphere", "Js_rumpf", (0, 0, 0.3), (0.9, 2.4, 0.5), m=mat("JetskiRot", "#ff2a3a", 0.25, coat=0.9), parent=R, seg=24)
    prim("cube", "Js_sitz", (0, -0.3, 0.6), (0.5, 1.0, 0.2), m=mat("Sitz", "#141414", 0.6), parent=R, bevel=0.06)
    prim("cyl", "Js_lenker", (0, 0.6, 0.85), (0.9, 0.06, 0.06), rot=(0, math.radians(90), 0), m=STEEL, parent=R, seg=8)
    return R


JETSKI = build_jetski()


def build_disco():
    m, nt, out = node_mat("Discokugel")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.05
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 18.0
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    nt.links.new(vo.outputs["Color"], b.inputs["Base Color"])
    em_name = "Emission Color" if "Emission Color" in b.inputs else "Emission"
    nt.links.new(vo.outputs["Color"], b.inputs[em_name])
    v = nt.nodes.new("ShaderNodeValue"); v.outputs[0].default_value = 0.5
    if "Emission Strength" in b.inputs:
        nt.links.new(v.outputs[0], b.inputs["Emission Strength"])
    nt.links.new(b.outputs[0], out.inputs[0])
    R = empty("Discokugel", HIDE)
    prim("sphere", "Disco_kugel", (0, 0, 0), (2.4, 2.4, 2.4), m=m, parent=R, seg=24, smooth_=False)
    prim("cyl", "Disco_seil", (0, 0, 100), (0.05, 0.05, 200), m=CABLE_M, parent=R, seg=6)
    return R, v


DISCO, DISCO_E = build_disco()


def build_banner():
    R = empty("Bannerrakete", HIDE)
    prim("cyl", "Ba_rakete", (0, 0, 0), (0.6, 0.6, 2.6), rot=(0, math.radians(90), 0), m=mat("RaketeWeiss", "#f4f2ee", 0.4), parent=R, seg=16)
    prim("cone", "Ba_spitze", (1.7, 0, 0), (0.6, 0.6, 0.9), rot=(0, math.radians(90), 0), m=mat("RaketeRot", "#ff2a3a", 0.4), parent=R, seg=16)
    prim("cone", "Ba_flamme", (-1.9, 0, 0), (0.55, 0.55, 1.6), rot=(0, math.radians(-90), 0), m=emit_mat("Flamme", "#ff9a1a", 10.0), parent=R, seg=12)
    prim("cube", "Ba_tuch", (-8.5, 0, 0), (11.0, 0.05, 1.8), m=mat("Bannertuch", "#ff2fa8", 0.6, emit="#ff2fa8", estr=0.5), parent=R)
    for sy in (-1, 1):
        sign("Ba_text%d" % sy, "GUCCI MOVES  -  ARRIVING FRIDAY", (-8.5, sy * 0.06, -0.05), 0.75, "#ffe14a", rz=0 if sy < 0 else math.pi, parent=R)
    return R


BANNER = build_banner()


def banner_run(t, b, p0, p1, b0, b1):
    if not (b0 <= b < b1):
        BANNER.location = HIDE
        return
    u = kk(b, b0, b1)
    d = Vector(p1) - Vector(p0)
    BANNER.location = vlerp(Vector(p0), Vector(p1), u) + Vector((0, 0, math.sin(t * 2) * 0.3))
    BANNER.rotation_euler = (math.sin(t * 3) * 0.05, 0, math.atan2(d.y, d.x))


GM_ROCKET = empty("GrandmaRakete", HIDE)
instance("GrandmaFlasche", PEPSI, (0, 0, 0), (0, math.radians(-90), 0), 4.0, parent=GM_ROCKET)
GM_TRAIL = [prim("ico", "GMspur%02d" % i, HIDE, (1, 1, 1), m=mat("Schaum", "#f8f6f0", 0.6, emit="#ffffff", estr=0.3)) for i in range(28)]


def gm_rocket_run(t, b, p0, p1, b0, b1):
    if not (b0 <= b < b1):
        GM_ROCKET.location = HIDE
        for f in GM_TRAIL:
            f.location = HIDE
        return False
    u = kk(b, b0, b1)
    d = (Vector(p1) - Vector(p0))
    p = vlerp(Vector(p0), Vector(p1), u) + Vector((0, 0, math.sin(u * math.pi * 2) * 1.5))
    rz = math.atan2(d.y, d.x)
    GM_ROCKET.location = p
    GM_ROCKET.rotation_euler = (math.sin(t * 4) * 0.1, 0, rz + math.pi)
    fwd = d.normalized()
    put(GM["root"], p + Vector((0, 0, 1.25)) - fwd * 0.4, rz - math.pi / 2, 1.0)
    pose_grandma(t, b, None)
    GM["arm"].rotation_euler = (math.radians(-150), 0, 0)
    for i, f in enumerate(GM_TRAIL):
        a = (i / len(GM_TRAIL))
        f.location = p - fwd * (2.5 + a * 9) + Vector((math.sin(i * 2.3 + t * 5) * 0.4 * a, math.cos(i * 1.7) * 0.4 * a, math.sin(i + t * 4) * 0.4 * a))
        sc = 0.5 + a * 1.2
        f.scale = (sc, sc, sc)
    return True


HD_RIDE = empty("HotDogRakete", HIDE)
instance("HotDogRiese", HOTDOG, (0, 0, 0), (0, 0, 0), 5.0, parent=HD_RIDE)
prim("cone", "HotDogFlamme", (-2.4, 0, 0.2), (0.8, 0.8, 1.8), rot=(0, math.radians(-90), 0), m=emit_mat("Flamme2", "#ff6a1a", 12.0), parent=HD_RIDE, seg=12)


def hd_ride(p, rz, t):
    HD_RIDE.location = p
    HD_RIDE.rotation_euler = (math.sin(t * 2.2) * 0.08, math.sin(t * 1.7) * 0.06, rz)


# Hot Dogs mit Sonnenbrille tanzen auf dem Band
HD_DANCERS = []
for i_ in range(4):
    R_ = empty("TanzHotDog%d" % i_, HIDE)
    instance("TanzHotDogMesh%d" % i_, HOTDOG, (0, 0, 0.55), (0, math.radians(90), math.radians(90)), 1.6, parent=R_)
    for sx in (-1, 1):
        prim("sphere", "TanzHotDogBrille%d%d" % (i_, sx), (sx * 0.07, 0.15, 0.9), (0.11, 0.04, 0.07), m=SHADES_M, parent=R_, seg=12)
    prim("cube", "TanzHotDogBuegel%d" % i_, (0, 0.14, 0.92), (0.28, 0.02, 0.015), m=GOLD, parent=R_)
    HD_DANCERS.append(R_)


def hd_dancers_run(t, b, spots):
    for i, R_ in enumerate(HD_DANCERS):
        if i >= len(spots):
            R_.location = HIDE
            continue
        hit = ds_pulse(b)
        R_.location = Vector(spots[i]) + Vector((0, 0, abs(math.sin(math.pi * (b + i * 0.5))) * 0.25))
        R_.rotation_euler = (0, 0.3 * math.sin(math.pi * b + i), math.pi + 0.5 * math.sin(math.pi * b / 2 + i) + (math.tau * ease_inout((b % 2) / 2) if (int(b // 4) + i) % 3 == 0 and b >= DROP else 0))
        R_.scale = (1 + 0.1 * hit, 1 + 0.1 * hit, 1 - 0.08 * hit)


# Hot-Dog-Regen im All (Testlauf des Programms)
HD_SPACE = [instance("AllHotDog%02d" % i, HOTDOG, HIDE, (0, 0, 0), 1.4) for i in range(36)]


def hd_space_run(t, b, C, on):
    for i, o in enumerate(HD_SPACE):
        if not on:
            o.location = HIDE
            continue
        ph = (t * 0.45 + hsh(i * 3.1)) % 1.0
        o.location = C + Vector(((hsh(i * 1.7) - 0.5) * 26, (hsh(i * 2.3) - 0.3) * 18, 22 - ph * 26))
        o.rotation_euler = (t * (1 + hsh(i)) + i, t * 0.7 + i, i)


# ------------------------------------------------------------------ Neue Welt: Kanal-Tunnel aus Screens
WX["tunnel"] = Vector((0, -5000, 0))
TW = WX["tunnel"]
TUN_R = 4.2
TUN_KEYS = ["cg2", "mm", "gm2", "e1", "ig1", "e3", "e5", "ig2", "e2", "ig3"]
TUN_RINGS = []
for r_ in range(22):
    y = r_ * 6.0
    for j in range(8):
        a = j / 8 * math.tau + (r_ % 2) * math.tau / 16
        u = Vector((math.sin(a), 0, math.cos(a)))
        pn = prim("plane", "Tunnel%02d_%d" % (r_, j), TW + Vector((0, y, 0)) - u * TUN_R, (3.1, 5.4, 1), rot=(0, a, 0),
                  m=clip_mat(TUN_KEYS[(r_ * 3 + j) % len(TUN_KEYS)], offset=(r_ * 7 + j * 13) % 2 * 45))
        no_shadow_obj(pn)
    rm = emit_mat("TunnelRing%d" % (r_ % 3), ["#ff2fa8", "#20e6ff", "#ffe14a"][r_ % 3], 6.0)
    ring = curve_obj("TunnelRing%02d" % r_, [TW + Vector((math.sin(a) * (TUN_R - 0.1), y + 3.0, math.cos(a) * (TUN_R - 0.1)))
                                            for a in (k / 16 * math.tau for k in range(16))], radius=0.09, m=rm, closed=True)
    TUN_RINGS.append(ring)
TUN_LIGHTS = [light("TunnelLicht%d" % k, "POINT", TW + Vector((0, 10 + k * 30, 0)), 800, ["#ff2fa8", "#20e6ff", "#ffe14a", "#a040ff"][k], size=2.0)
              for k in range(4)]
TUN_EM = [bpy.data.materials.get("TunnelRing%d" % k) for k in range(3)]


def world_tunnel(t, b, y_now):
    for k, m in enumerate(TUN_EM):
        if m:
            em = next((n for n in m.node_tree.nodes if n.type == "EMISSION"), None)
            if em:
                em.inputs[1].default_value = 4.0 + 10.0 * math.exp(-6 * ((b + k / 3.0) % 1.0))
    for k, L in enumerate(TUN_LIGHTS):
        L.location = TW + Vector((math.sin(t * 3 + k) * 2.0, y_now + (k - 1.5) * 6, math.cos(t * 2 + k) * 2.0))


# ------------------------------------------------------------------ Neue Welt: Hot-Dog-Regen über den Wolken (Gott ist nicht im Büro)
WX["regen"] = Vector((5000, 5000, 0))
RW = WX["regen"]
RWE = empty("RegenWelt", RW)
PUFF = mat("Wolke", "#ffffff", 0.9, sss=0.3, emit="#ffe8f6", estr=0.25)
CLOUD = proto_collection("WolkeVorlage")
_cl = parts_mesh("WolkeMesh", [("s", (0, 0, 0), (4.0, 3.0, 2.2), 0), ("s", (1.8, 0.4, 0.5), (3.0, 2.6, 2.4), 0), ("s", (-1.9, -0.3, 0.3), (3.2, 2.4, 2.0), 0),
                                ("s", (0.4, -0.8, 1.1), (2.6, 2.2, 2.2), 0), ("s", (3.4, -0.2, -0.2), (2.0, 1.8, 1.4), 0)], [PUFF], link_=False)
CLOUD.objects.link(_cl)
prim("plane", "Wolkenboden", (0, 60, -3.0), (900, 900, 1), m=noise_mat("Wolkenmeer", "#ffd6f0", "#ffffff", scale=0.05, rough=0.9, bump=0.2, c2="#ffe8a0"), parent=RWE)
for i_ in range(60):
    a_ = hsh(i_ * 2.7) * math.tau
    r_ = 30 + hsh(i_ * 5.1) * 120
    instance("Wolke%02d" % i_, CLOUD, (math.sin(a_) * r_, 14 + math.cos(a_) * r_, -7.0 + hsh(i_ * 3.3) * 3.0), (0, 0, a_), 1.5 + hsh(i_) * 3.0, parent=RWE)
STAGE_CLOUD = instance("Buehnenwolke", CLOUD, (0, 14, -8.2), (0, 0, 0.3), 3.6, parent=RWE)
prim("cyl", "Buehnenplatte", (0, 14, 0.0), (15, 15, 0.3), m=mat("Wolkenplatte", "#ffffff", 0.8, emit="#ffe8f6", estr=0.15), parent=RWE, seg=48)
THRONE = parts_mesh("Thron", [("b", (0, 0, 0.6), (1.6, 1.4, 1.2), 0), ("b", (0, 0.6, 2.0), (1.6, 0.25, 3.0), 0), ("b", (-0.9, 0, 1.2), (0.25, 1.4, 0.6), 0),
                              ("b", (0.9, 0, 1.2), (0.25, 1.4, 0.6), 0), ("s", (0, 0.6, 3.6), (1.0, 0.3, 1.0), 1)], [GOLD, mat("ThronRot", "#d4141c", 0.5)],
                    loc=RW + Vector((0, 24, 0.15)))
sign("ThronSchild", "GOD IS OUT OF OFFICE", RW + Vector((0, 22.2, 5.6)), 0.9, "#ffffff")
sign("ThronSchild2", "BACK AFTER VEGAN HOT DOG RAIN", RW + Vector((0, 22.2, 4.8)), 0.42, "#7a2cff", fnt="barlow")
RAINBOW = []
for k_, c_ in enumerate(["#ff2a2a", "#ff8a1a", "#ffe14a", "#3cff5a", "#20b6ff", "#a040ff"]):
    rad = 46 - k_ * 1.2
    RAINBOW.append(curve_obj("Regenbogen%d" % k_, [RW + Vector((math.cos(a) * rad, 90, math.sin(a) * rad - 3)) for a in
                                                 (math.pi * i / 16 for i in range(17))], radius=0.65, m=emit_mat("Regenbogen%d" % k_, c_, 3.0)))
RAIN_DOGS = [instance("RegenHotDog%03d" % i, HOTDOG, HIDE, (0, 0, 0), 1.3 + hsh(i) * 1.2, parent=RWE) for i in range(130)]


def world_regen(t, b, C=None):
    C = C or Vector((0, 14, 0))
    for i, o in enumerate(RAIN_DOGS):
        sp = 9.0 + hsh(i * 1.3) * 5
        ph = (t * sp / 46.0 + hsh(i * 3.1)) % 1.0
        o.location = C + Vector(((hsh(i * 1.7) - 0.5) * 50, (hsh(i * 2.3) - 0.35) * 60, 42 - ph * 46))
        o.rotation_euler = (t * (1.5 + hsh(i)) + i, t * 0.8 + i * 0.3, i)


# ------------------------------------------------------------------ Portale: Screens, durch die man in die nächste Welt gleitet
PORTALS = {
    "space": SPACE_BIG,
    "fabrik": big_screen("PortalFabrik", "gm2", 6.5, cables=True, label="NEXT: ???", offset=30),
    "pepsi": big_screen("PortalPepsi", "e5", 7.0, cables=False, label="MINO TV", offset=60),
    "regen": big_screen("PortalRegen", "mm", 6.0, cables=False, label="EXIT", offset=90),
    "buero": big_screen("PortalBuero", "ig2", 7.0, cables=False, label="MINO TV", offset=20),
}
for _s in POOL + [SPACE_BIG]:
    for ch in descendants(_s["root"]):
        if "_seil" in ch.name:
            ch.hide_render = True


def portal_front(key, d=0.0):
    return big_front(PORTALS[key], d)


def hide_portals():
    for s in PORTALS.values():
        s["root"].location = HIDE


def into_portal(root, p_from, key, b, b0, b1, s0=1.0, rz=None):
    """Gleitet von p_from vor den Screen und schrumpft hinein; True solange sichtbar."""
    u = kk(b, b0, b1)
    if u >= 1.0:
        root.location = HIDE
        return False
    front = portal_front(key, -0.3)
    p = vlerp(Vector(p_from), front, ease_inout(u))
    sh = 1.0 - smooth(kk(u, 0.55, 1.0)) * 0.92
    put(root, p, rz if rz is not None else face_to(p_from, front), s0 * sh)
    return True


def out_of(root, key, p_to, b, b0, b1, s0=1.0, rz=0.0, arc=1.5):
    u = kk(b, b0, b1)
    front = portal_front(key, 0.4)
    p = vlerp(front, Vector(p_to), ease_out(u)) + Vector((0, 0, math.sin(u * math.pi) * arc))
    put(root, p, rz, s0 * (0.1 + 0.9 * smooth(kk(u, 0.0, 0.6))))
    return u >= 1.0


# ------------------------------------------------------------------ gemeinsame Bausteine pro Bild
CHAIR_MM = parts_mesh("FlugStuhl", [("b", (0, 0, 0.48), (0.56, 0.54, 0.1), 0), ("b", (0, -0.24, 0.85), (0.54, 0.08, 0.6), 0),
                                    ("b", (0, 0, 0.25), (0.06, 0.06, 0.45), 1), ("b", (0, 0, 0.04), (0.6, 0.08, 0.04), 1),
                                    ("b", (0, 0, 0.04), (0.08, 0.6, 0.04), 1)], [mat("StuhlPink", "#ff2fa8", 0.5), LEG_M], loc=HIDE)


def hide_r8():
    hide_extras()
    hide_pool()
    hide_portals()
    for o in (CG["root"], MM["root"], GM["root"], MU["root"]):
        o.location = HIDE
    for o in (UFO["root"], SAT, DISCO, HD_RIDE, DUCK, JETSKI, CHAIR_MM, SURF, RAFT, DESK_MM, DESK_CG, SPACE_COOLER, BANNER, GM_ROCKET):
        o.location = HIDE
    TOASTER["root"].location = HIDE
    for o in TOASTER["toast"] + GM_TRAIL:
        o.location = HIDE
    hd_dancers_run(0, 0, [])
    hd_space_run(0, 0, Vector((0, 0, 0)), False)
    crowd_hide()
    UFO["beam"].scale = (0, 0, 0)


def space_frame(t, b):
    set_world("orbit")
    world_space(t, b)
    floor_run(b)
    SAT.location = ISLAND.location + Vector((15.0, 26.0, 13.0))
    SAT.rotation_euler = (0.2, 0.1 * math.sin(t * 0.3), math.radians(200) + t * 0.08)
    SPACE_COOLER.location = ISLAND.location + Vector((-11, 4, 5 + math.sin(t * 0.6)))


def pool_drift(t, b, idx, C, r0=16.0, z0=6.0):
    for n, i in enumerate(idx):
        s = POOL[i]
        a = n / len(idx) * math.tau + t * 0.06 + 0.4
        r = r0 + hsh(i * 2.9) * 6
        p = C + Vector((math.cos(a) * r, 3 + (0.5 + 0.5 * math.sin(a)) * r * 0.9, z0 + (hsh(i * 6.1) - 0.5) * 9 + math.sin(t * 0.5 + i) * 0.6))
        s["root"].location = p
        s["root"].rotation_euler = (math.sin(t * 0.3 + i) * 0.25, math.cos(t * 0.27 + i) * 0.2, face_to(p, C + Vector((0, -12, 0))) + math.sin(t * 0.2 + i) * 0.3)
        sc = 0.55 + 0.15 * hsh(i)
        s["root"].scale = (sc, sc, sc)


def pool_arc(t, b, idx, C, r=19.0, z=8.5, arc=math.radians(220), sc=0.6):
    """Bogen aus Screens hinter der Insel, tickt nach dem Drop auf jedem Schlag eine Position weiter."""
    n = len(idx)
    step = arc / max(1, n - 1)
    if b >= DROP:
        shift = (int(b) + ease_back(clamp((b % 1.0) / 0.3))) * step * 0.5
    else:
        shift = t * 0.05
    for k, i in enumerate(idx):
        s = POOL[i]
        a = -arc / 2 + ((k * step + shift) % (arc + step))
        p = C + Vector((math.sin(a) * r, math.cos(a) * r, z + 0.6 * math.sin(math.pi * b / 2 + k) * (1 if b >= DROP else 0.3)))
        s["root"].location = p
        s["root"].rotation_euler = (0, 0, face_to(p, C))
        hit = ds_pulse(b)
        s["root"].scale = Vector((1, 1, 1)) * sc * (1 + 0.05 * hit)


def crowd_floor(t, b, C, mode="dance", n=None, rz=math.pi):
    n = n or len(CROWD)
    for i, d in enumerate(CROWD[:n]):
        r_, c_ = divmod(i, 7)
        p = C + Vector(((c_ - 3) * 1.75 + (0.5 if r_ % 2 else 0), -4.2 + r_ * 1.5, 0))
        crowd_pose(d, t, b, mode if not callable(mode) else mode(i), p, rz + (hsh(i) - 0.5) * 0.4)


def veg_at(t, b, C):
    for k, v in enumerate(VEG):
        v["home"] = C + Vector(((k - 1) * 1.6, 0, 0))
    veg_run(t, b, True)


def mm_mid():
    return MM["root"].location


def cg_mid():
    return CG["root"].location


def mid2():
    return (MM["root"].location + CG["root"].location) * 0.5


ISL = lambda: ISLAND.location     # noqa: E731
FL = Vector((0, -5.5, 0))          # Tanzfläche vorn auf der Insel (lokal)


def island_party(t, b, b0, mm_at=(1.0, -7.4), cg_at=(-1.0, -7.2)):
    isl = ISLAND.location
    mm_ds(t, b, isl + Vector((mm_at[0], mm_at[1], 0.06)), math.pi)
    cg_ds(t, b, isl + Vector((cg_at[0], cg_at[1], 0.06)), math.pi + math.sin(t * 0.7) * 0.4)
    crowd_floor(t, b, isl + Vector((0, -1.2, 0.06)))
    put(GM["root"], isl + Vector((-4.2, -6.4, 0.06)), math.pi + 0.5, 1.0)
    pose_grandma(t, b, erupt_from=b0 + 2)
    peng_run(t, b, isl + Vector((3.8, -6.6, 0.06)), isl + Vector((3.8, -6.6, 0.06)), 0, 1, dance=True)
    PENG["root"].rotation_euler.z = math.pi + math.sin(t * 2) * 0.4
    veg_at(t, b, isl + Vector((0, 0.4, 0.06)))
    DISCO.location = isl + Vector((0, -4.0, 9.0))
    DISCO.rotation_euler = (0, 0, t * 1.4)
    DISCO_E.outputs[0].default_value = 0.4 + 2.5 * ds_pulse(b)
    pool_arc(t, b, list(range(12)), isl + Vector((0, -1.0, 0)))


# ================================================================== Drei Abläufe
sh_ = shot
if VARIANT == 1:
    # ------------------------------------------------------------ 1: DRIFT – All -> Hot-Dog-Fabrik -> Tunnel -> Pepsi-Surf -> All-Party
    def ride_y(t):
        return 4.0 + 2.8 * max(0.0, t - B(16))

    def story(t, b):
        hide_r8()
        flash_run(b, [16, 27, 31, 40])
        isl = ISLAND.location
        if b < 16:
            space_frame(t, b)
            pool_drift(t, b, list(range(8)), isl)
            big_place(SPACE_BIG, isl + Vector((0, 27, 6.5)), math.pi, t, 0.3)
            ufo_run(t, b, isl + Vector((-7.5, 5.0, 14.0)), beam=b < 13)
            cu = kk(b, 0, 13)
            put(COW["root"], isl + Vector((-7.5, 5.0, 0.2 + cu * 12.5)), t * 0.6, 1.0 - 0.6 * cu, rx=math.sin(t) * 0.5, ry=t * 0.4)
            put(MU["root"], isl + Vector((10.5, 2.0, 6.0 + math.sin(t * 0.6) * 0.5)), math.pi + 0.6 + t * 0.15, 1.0, rx=0.2 * math.sin(t * 0.4))
            pose_munch(t, 1.0)
            toaster_run(t, b, isl + Vector((16, -2, 8)), isl + Vector((-18, 6, 10)), 2, 14)
            bob = math.sin(t * 0.9) * 0.25
            mm0 = isl + Vector((-2.4, -7.2, 3.0 + bob))
            cg0 = isl + Vector((2.6, -6.4, 2.6 - bob))
            if b < 10:
                put(CHAIR_MM, mm0, math.pi + math.sin(t * 0.4) * 0.5, 1.0, rx=math.sin(t * 0.5) * 0.08)
                put(MM["root"], mm0 + Vector((0, 0, 0.0)), math.pi + math.sin(t * 0.4) * 0.5, 1.0)
                pose_mm(t, "schweben")
                MM["neck"].rotation_euler = (0.05, 0, math.sin(t * 0.8) * 0.3)
                DESK_CG.location = cg0
                DESK_CG.rotation_euler = (0.06 * math.sin(t), 0.06 * math.cos(t * 0.8), math.pi + t * 0.1)
                cg_ds(t, b, cg0 + Vector((0, 0, 0.77)), math.pi + math.sin(t * 0.6) * 0.4, 0.9)
            else:
                put(CHAIR_MM, mm0 + Vector((-(b - 10) * 1.2, -(b - 10) * 0.4, (b - 10) * 0.6)), math.pi + (b - 10), 1.0, rx=(b - 10) * 0.7)
                DESK_CG.location = cg0 + Vector(((b - 10) * 1.0, 0, -(b - 10) * 0.5))
                DESK_CG.rotation_euler = ((b - 10) * 0.4, 0.2, math.pi + t * 0.1)
                fr = into_portal(MM["root"], mm0 + Vector((0, 0, 0.6)), "space", b, 10, 16)
                if fr:
                    MM["root"].rotation_euler = (-1.25, 0, MM["root"].rotation_euler.z)
                    pose_mm_fly(t, b)
                if into_portal(CG["root"], cg0 + Vector((0, 0, 0.9)), "space", b, 10.4, 16, CG_S):
                    CG["root"].rotation_euler = (-0.5, 0, CG["root"].rotation_euler.z)
                    pose_cg(t, 1.0, "flattern")
        elif b < 27:
            set_world("fabrik")
            world_fabrik(t, b)
            y = ride_y(t)
            land = kk(b, 16, 16.6)
            zf = 8.0 * (1 - land) ** 2
            big_place(PORTALS["fabrik"], FWV + Vector((1.6, 25.0, 4.4)), math.pi, t, 0.3)
            put(MU["root"], FWV + Vector((-5.4, 12.0, 0)), math.radians(70), 1.0)
            pose_munch(t, 1.0)
            if b < 25.5:
                mm_ds(t, b, FWV + Vector((0.0, y, 0.95 + zf)), math.pi + 0.3 * math.sin(t * 0.5))
                cg_ds(t, b, FWV + Vector((3.2, y + 1.2, 0.95 + zf * 1.2)), math.pi - 0.3, 1.0)
            else:
                into_portal(MM["root"], FWV + Vector((0.0, ride_y(B(25.5)), 1.0)), "fabrik", b, 25.5, 27)
                pose_mm_fly(t, b)
                MM["root"].rotation_euler.x = -1.1
                into_portal(CG["root"], FWV + Vector((3.2, ride_y(B(25.5)) + 1.2, 1.0)), "fabrik", b, 25.7, 27, CG_S)
                pose_cg(t, 1.0, "flattern")
            hd_dancers_run(t, b, [FWV + Vector((0.0, y + 1.6, 0.95)), FWV + Vector((0.0, y - 1.6, 0.95)), FWV + Vector((3.2, y - 0.6, 0.95)),
                                  FWV + Vector((-3.2, y + 0.6, 0.95))])
        elif b < 31:
            set_world("tunnel")
            yy = 8 + kk(b, 27, 31) * 108
            world_tunnel(t, b, yy)
            put(MM["root"], TW + Vector((-0.75, yy, -0.9 + 0.2 * math.sin(t * 3))), 0.0 + 0.2 * math.sin(t * 2), 1.0, rx=-1.2)
            pose_mm_fly(t, b)
            put(CG["root"], TW + Vector((0.9, yy - 0.6, -0.4 + 0.25 * math.sin(t * 2.6))), 0.3 * math.sin(t * 1.7), CG_S, rx=-0.6)
            pose_cg(t, 1.0, "flattern")
        elif b < 40:
            set_world("pepsi")
            world_pepsi(t, b)
            c = WX["pepsi"]
            wv = math.sin(t * 1.5) * 0.4
            trick, spin, air = "carve", 0.0, 0.0
            if 33 <= b < 34.5:
                spin = ease_inout((b - 33) / 1.5) * math.tau
            if 35 <= b < 36.5:
                trick = "air"
                air = math.sin((b - 35) / 1.5 * math.pi) * 2.2
            sy = 6 + (b - 31) * 1.5
            sp = c + Vector((math.sin(t * 0.5) * 2.5, sy, 0.1 + wv + air))
            drop_ = 6.0 * (1 - kk(b, 31, 31.6)) ** 2
            big_place(PORTALS["pepsi"], c + Vector((1.0, 25.0, 4.2)), math.pi, t, 0.5)
            dp = c + Vector((4.8, sy + 2.5, -0.4 + math.sin(t * 1.4 + 1) * 0.35))
            if b < 38.5:
                SURF.location = sp + Vector((0, 0, drop_))
                SURF.rotation_euler = (math.sin(t * 1.3) * 0.08 + (0.3 if trick == "air" else 0), math.sin(t * 1.1) * 0.1, math.radians(90) + spin)
                put(MM["root"], sp + Vector((0, 0, 0.12 + drop_)), math.radians(90) + spin, 1.0)
                pose_mm(t, "surfen", trick)
                DUCK.location = dp
                DUCK.rotation_euler = (math.sin(t * 1.2) * 0.06, math.sin(t) * 0.06, math.radians(-10))
                cg_ds(t, b, dp + Vector((0, -0.4, 3.1 + drop_ * 1.3)), math.pi - 0.2, 1.0)
            else:
                into_portal(MM["root"], sp + Vector((0, 0, 0.5)), "pepsi", b, 38.5, 40)
                pose_mm_fly(t, b)
                MM["root"].rotation_euler.x = -1.2
                DUCK.location = dp
                into_portal(CG["root"], dp + Vector((0, -0.4, 3.1)), "pepsi", b, 38.7, 40, CG_S)
                pose_cg(t, 1.0, "flattern")
            ja = t * 0.9
            jp = c + Vector((math.cos(ja) * 9, sy + 6 + math.sin(ja) * 7, 0.2 + wv * 0.6))
            JETSKI.location = jp
            JETSKI.rotation_euler = (0, math.sin(t * 2) * 0.15, ja + math.pi)
            put(PENG["root"], jp + Vector((0, -0.3, 0.6)), ja + math.pi, 1.0)
        else:
            space_frame(t, b)
            big_place(SPACE_BIG, isl + Vector((0, 27, 6.5)), math.pi, t, 0.3)
            island_party(t, b, 40)
            if b < 41.2:
                out_of(MM["root"], "space", isl + Vector((1.0, -7.4, 0.06)), b, 40, 41.2)
                pose_mm(t, "jubel")
                out_of(CG["root"], "space", isl + Vector((-1.0, -7.2, 0.06)), b, 40.2, 41.2, CG_S, math.pi)
                pose_cg(t, 1.0, "flattern")
            ufo_run(t, b, isl + Vector((7.5, 4.0, 14.0)), beam=True)
            cu = kk(b, 40, 44)
            put(COW["root"], isl + Vector((6.0, -3.0, 12.0 * (1 - cu) + 0.06)), math.pi + 0.4, 1.0)
            if b >= 44:
                cow_run(t, b, isl + Vector((6.0, -3.0, 0.06)), isl + Vector((6.0, -3.0, 0.06)), 0, 1, dance=True)
            hd_space_run(t, b, isl + Vector((0, -2, 0)), b >= 42)
            banner_run(t, b, isl + Vector((-40, 30, 18)), isl + Vector((40, 30, 18)), 42, 48)

    sh_(0, lambda: ISL() + Vector((-3.0, -17.0, 4.5)), lambda: ISL() + Vector((0, -6.5, 3.2)), 22, trans=0, drift=0.8)
    sh_(4, lambda: mm_mid() + Vector((1.7, -3.6, 1.2)), lambda: mm_head() + Vector((0, 0, -0.35)), 28)
    sh_(8, lambda: DESK_CG.location + Vector((-1.6, -3.4, 2.0)), lambda: cg_head() + Vector((0, 0, -0.1)), 30)
    sh_(11, lambda: mid2() + Vector((1.5, -6.5, 1.6)), lambda: portal_front("space"), 22)
    sh_(14.5, lambda: portal_front("space") + Vector((0, -9.5, -0.5)), lambda: portal_front("space"), 24, drift=5.5)
    sh_(16, lambda: FWV + Vector((-2.4, ride_y((scn.frame_current - 1) / FPS) - 5.6, 2.8)),
        lambda: FWV + Vector((1.6, ride_y((scn.frame_current - 1) / FPS) + 1.0, 1.7)), 22, trans=0)
    sh_(20, lambda: mm_mid() + Vector((-1.7, -3.4, 1.2)), lambda: mm_head() + Vector((0, 0, -0.3)), 28)
    sh_(23, lambda: cg_mid() + Vector((1.9, -3.3, 1.1)), lambda: cg_head() + Vector((0, 0, -0.15)), 30)
    sh_(25.3, lambda: portal_front("fabrik") + Vector((-0.6, -9.0, -1.4)), lambda: portal_front("fabrik"), 24, drift=5.0)
    sh_(27, lambda: TW + Vector((0.2, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 27, 31) * 108 + 4.6, 0.3)),
        lambda: TW + Vector((0, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 27, 31) * 108, -0.4)), 24, trans=0)
    sh_(31, lambda: SURF.location + Vector((4.4, -3.4, 1.6)), lambda: mm_mid() + Vector((0, 0, 1.2)), 26, trans=0)
    sh_(34, lambda: mm_mid() + Vector((-3.6, -4.6, 1.4)), lambda: mm_mid() + Vector((0, 0.8, 1.1)), 24)
    sh_(36, lambda: DUCK.location + Vector((-2.6, -5.0, 4.2)), lambda: cg_head() + Vector((0, 0, -0.3)), 28)
    sh_(38.3, lambda: portal_front("pepsi") + Vector((0.5, -10.0, -1.5)), lambda: portal_front("pepsi"), 24, drift=5.5)
    sh_(40, lambda: ISL() + Vector((0.5, -15.5, 3.2)), lambda: ISL() + Vector((0, -2.0, 2.4)), 22, trans=0)
    sh_(42, lambda: mm_mid() + Vector((1.5, -3.4, 1.3)), lambda: mm_head() + Vector((0, 0, -0.3)), 28)
    sh_(44, lambda: ISL() + Vector((0, -20.0, 6.5)), lambda: ISL() + Vector((0, 2.0, 4.0)), 18, drift=-0.6, rise=0.5)
    sh_(46.5, lambda: ISL() + Vector((0.6, -12.6, 2.2)), lambda: ISL() + Vector((0, -7.2, 1.3)), 24)

elif VARIANT == 2:
    # ------------------------------------------------------------ 2: ORBIT SURF – Surfen im All -> Screen-Tor -> Hot-Dog-Regen -> Büro-Party -> Tunnel -> All
    GATE_C = None

    def surf_path(b):
        """Mino Man surft in S-Kurven durchs All Richtung Screen-Tor."""
        isl = ISLAND.location
        y = -26 + b * 2.3
        k = clamp((b - 8) / 8)
        return isl + Vector((math.sin(b * 0.45) * 5.0 * (1 - 0.9 * clamp((b - 12) / 4)), y, 5.5 + math.sin(b * 0.3) * 1.5 + k * 8.0))

    def gate_c():
        return ISLAND.location + Vector((0, 12.5, 12.0))

    def story(t, b):
        hide_r8()
        flash_run(b, [16, 28, 36, 40])
        isl = ISLAND.location
        if b < 16:
            space_frame(t, b)
            # Screen-Tor: acht Screens im Kreis, Mino Man und Chicken Guy fliegen hindurch
            gc = gate_c()
            spin = t * 0.25 + (ease_back(clamp((b % 1.0) / 0.3)) * 0.0)
            for k in range(8):
                s = POOL[k]
                a = k / 8 * math.tau + spin
                p = gc + Vector((math.cos(a) * 7.0, 0, math.sin(a) * 7.0))
                s["root"].location = p
                s["root"].rotation_euler = (0, -a + math.pi / 2, math.pi)
                s["root"].scale = (0.42, 0.42, 0.42)
            pool_drift(t, b, list(range(8, 14)), isl + Vector((0, -6, 0)), r0=14.0, z0=8.0)
            p = surf_path(b)
            nxt = surf_path(b + 0.2)
            rz = face_to(p, nxt)
            lean = math.sin(b * 0.45 + 1.4) * 0.35
            trick = "air" if 9 <= b < 10.5 else "carve"
            SURF.location = p
            SURF.rotation_euler = (lean * 0.3, lean, rz + math.radians(90))
            put(MM["root"], p + Vector((0, 0, 0.12)), rz + math.radians(90), 1.0, ry=lean * 0.5)
            pose_mm(t, "surfen", trick)
            hp = p + Vector((-3.4 + math.sin(t) * 0.5, -2.5, 1.6 + math.sin(t * 1.3) * 0.6))
            hd_ride(hp, rz + math.pi / 2, t)
            cg_ds(t, b, hp + Vector((0, 0, 0.45)), rz, 1.0)
            if b >= 14.0:     # Gleiten durchs Tor: Flash auf 16
                k = kk(b, 14, 16)
                MM["root"].scale = Vector((1, 1, 1)) * (1 - 0.6 * k)
            gm_rocket_run(t, b, isl + Vector((30, 14, 10)), isl + Vector((-34, 4, 14)), 3, 11)
            banner_run(t, b, isl + Vector((-45, 34, 20)), isl + Vector((45, 34, 22)), 6, 15)
            put(MU["root"], isl + Vector((-9.0, -3.0, 9.0 + math.sin(t * 0.6) * 0.5)), 0.8 + t * 0.2, 1.0, rx=0.3 * math.sin(t * 0.5))
            pose_munch(t, 1.0)
        elif b < 28:
            set_world("regen")
            world_regen(t, b, RW + Vector((0, 14, 0)))
            stg = RW + Vector((0, 14, 0.3))
            fall = kk(b, 16, 20)
            if b < 20:
                z = 30 * (1 - fall) ** 1.4
                put(MM["root"], stg + Vector((1.0, -3.0, z)), math.pi + t * 1.5, 1.0, rx=(1 - fall) * -1.2)
                pose_mm_fly(t, b, 0.5)
                put(CG["root"], stg + Vector((-1.2, -2.6, z * 1.1 + 0.6)), math.pi - t * 1.3, CG_S, rx=(1 - fall) * -0.8)
                pose_cg(t, 1.0, "flattern")
            else:
                mm_ds(t, b, stg + Vector((1.0, -3.0, 0)), math.pi)
                cg_ds(t, b, stg + Vector((-1.2, -2.6, 0)), math.pi + math.sin(t * 0.7) * 0.4)
            crowd_floor(t, b, stg + Vector((0, 2.0, 0)), "dance" if b >= 20 else "stand")
            veg_at(t, b, stg + Vector((-5.5, -1.0, 0)))
            for v in VEG:
                v["root"].rotation_euler.z = math.pi - 0.6
            sneaker_run(t, b, [(21, 25, RW + Vector((40, 50, 20)), RW + Vector((-40, 20, 14)))])
            big_place(PORTALS["regen"], stg + Vector((4.5, -1.0, 3.6)), math.pi - 0.35, t, 0.3)
            if b >= 26:
                into_portal(MM["root"], stg + Vector((1.0, -3.0, 0)), "regen", b, 26, 28)
                pose_mm_fly(t, b)
                into_portal(CG["root"], stg + Vector((-1.2, -2.6, 0)), "regen", b, 26.3, 28, CG_S)
                pose_cg(t, 1.0, "flattern")
        elif b < 36:
            set_world("buero")
            office(t, b, party=1.0, beat_change=True)
            bigs_office(t, b)
            pigeons_run(t, b, fly_at=29)
            flyers(t, b, 28.5, Vector((0, 9, 0)), True)
            party_cast(t, b, 28)
            hd_dancers_run(t, b, [Vector((1.6, 9.8, 0)), Vector((-1.6, 11.6, 0))])
            if b < 29.2:
                out_of(MM["root"], "buero", Vector((0.55, 7.4, 0)), b, 28, 29.2, 1.0, math.pi)
                out_of(CG["root"], "buero", Vector((-0.55, 8.6, 0)), b, 28.2, 29.2, CG_S, math.pi)
            big_place(PORTALS["buero"], Vector((0.0, 15.0, 4.2)), math.pi, t, 0.3)
            if b >= 34:
                into_portal(MM["root"], Vector((0.55, 7.4, 0.5)), "buero", b, 34, 36)
                pose_mm_fly(t, b)
                into_portal(CG["root"], Vector((-0.55, 8.6, 0.5)), "buero", b, 34.2, 36, CG_S)
                pose_cg(t, 1.0, "flattern")
        elif b < 40:
            set_world("tunnel")
            yy = 8 + kk(b, 36, 40) * 108
            world_tunnel(t, b, yy)
            SURF.location = TW + Vector((-0.7, yy, -1.2))
            SURF.rotation_euler = (0, math.sin(t * 2) * 0.3, math.radians(90) + math.radians(90) * 0)
            SURF.rotation_euler = (0, 0, 0)
            put(MM["root"], TW + Vector((-0.7, yy, -1.08)), 0.0, 1.0)
            pose_mm(t, "surfen", "carve")
            hd_ride(TW + Vector((1.1, yy - 1.4, -1.0)), math.pi / 2, t)
            cg_ds(t, b, TW + Vector((1.1, yy - 1.4, -0.55)), 0.0, 1.0)
        else:
            space_frame(t, b)
            island_party(t, b, 40)
            ufo_run(t, b, isl + Vector((-8.0, 4.0, 15.0)), beam=False)
            hd_space_run(t, b, isl + Vector((0, -2, 0)), b >= 44)
            toaster_run(t, b, isl + Vector((-18, -10, 6)), isl + Vector((18, -6, 9)), 41, 47)
            if b < 41.2:
                k = kk(b, 40, 41.2)
                put(MM["root"], isl + Vector((1.0, -7.4, 0.06 + 14 * (1 - k) ** 2)), math.pi + k * 6, 1.0)
                pose_mm(t, "jubel")
                put(CG["root"], isl + Vector((-1.0, -7.2, 0.06 + 16 * (1 - k) ** 2)), math.pi - k * 5, CG_S)
                pose_cg(t, 1.0, "flattern")

    sh_(0, lambda: surf_path(beat_of((scn.frame_current - 1) / FPS)) + Vector((2.8, -3.4, 0.9)),
        lambda: surf_path(beat_of((scn.frame_current - 1) / FPS)) + Vector((0, 0.6, 1.0)), 24, trans=0)
    sh_(4, lambda: mm_mid() + Vector((2.4, -3.0, 0.9)), lambda: mm_head() + Vector((0, 0, -0.4)), 28)
    sh_(8, lambda: cg_mid() + Vector((-2.4, -3.4, 1.1)), lambda: cg_head() + Vector((0, 0, -0.1)), 28)
    sh_(11, lambda: mid2() + Vector((2.0, -6.5, 1.8)), lambda: gate_c(), 22)
    sh_(14, lambda: gate_c() + Vector((0.5, -13.0, 0.0)), lambda: gate_c(), 22, drift=5.0)
    sh_(16, lambda: mid2() + Vector((3.0, -5.5, 1.5)), lambda: mid2() + Vector((0, 0, 0.6)), 22, trans=0)
    sh_(20, lambda: RW + Vector((0.8, 5.0, 2.3)), lambda: RW + Vector((0, 12.0, 1.5)), 22)
    sh_(23, lambda: mm_mid() + Vector((1.6, -3.4, 1.3)), lambda: mm_head() + Vector((0, 0, -0.3)), 28)
    sh_(26, lambda: portal_front("regen") + Vector((-2.5, -9.0, -0.8)), lambda: portal_front("regen"), 24, drift=3.4)
    sh_(28, (-0.4, 3.6, 1.7), (0, 9, 1.2), 24, trans=0)
    sh_(30, lambda: CG["root"].location + Vector((-0.8, -1.9, 1.2)), lambda: cg_head(), 32)
    sh_(32, (2.2, 4.5, 7.5), (0, 10, 0.5), 22)
    sh_(33.6, lambda: portal_front("buero") + Vector((0.4, -9.0, -2.0)), lambda: portal_front("buero"), 24, drift=4.5)
    sh_(36, lambda: TW + Vector((0.3, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 36, 40) * 108 + 5.0, 0.4)),
        lambda: TW + Vector((0.2, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 36, 40) * 108 - 0.6, -0.5)), 24, trans=0)
    sh_(40, lambda: ISL() + Vector((0.5, -15.5, 3.2)), lambda: ISL() + Vector((0, -2.0, 2.4)), 22, trans=0)
    sh_(42, lambda: cg_mid() + Vector((-1.4, -3.0, 1.0)), lambda: cg_head(), 30)
    sh_(44, lambda: ISL() + Vector((-3.0, -21.0, 7.0)), lambda: ISL() + Vector((0, 2.0, 4.0)), 18, drift=-0.6, rise=0.5)

else:
    # ------------------------------------------------------------ 3: HOT DOG HUSTLE – All -> Tunnel -> Fabrik -> Hot-Dog-Ritt im Regen -> Pepsi -> Screen-Wand im All
    WALL3 = []
    for r_ in range(3):
        for c_ in range(3):
            i_ = r_ * 3 + c_
            k_ = TUN_KEYS[i_ % len(TUN_KEYS)]
            m_, v_ = mix_clip_mat("Wand8_%d" % i_, k_, "cg2", offset=i_ * 41, ncol=3, nrow=3, col=c_, row=r_)
            WALL3.append({"s": pool_screen("Wand8_%d" % i_, k_, 7.0, label="", offset=i_ * 41, m=m_), "c": c_, "r": r_, "v": v_})
            for ch in descendants(WALL3[-1]["s"]["root"]):
                if "_seil" in ch.name:
                    ch.hide_render = True

    def wall_run(t, b, C, b0):
        W, H = 7.0 * 9 / 16 + 0.75, 7.0 + 1.15
        for k, w in enumerate(WALL3):
            s = w["s"]
            goal = C + Vector(((w["c"] - 1) * W, 0, (w["r"]) * H))
            bi = b0 + k * 0.5
            a = k / 9 * math.tau + t * 0.1
            start = C + Vector((math.cos(a) * 22, -6 + math.sin(a) * 10, 8 + (hsh(k) - 0.5) * 14))
            if b < bi:
                s["root"].location = start
                s["root"].rotation_euler = (math.sin(t + k) * 0.6, t * 0.3 + k, k)
                s["root"].scale = (0.8, 0.8, 0.8)
            else:
                u = ease_back(clamp((b - bi) / 0.5))
                s["root"].location = vlerp(start, goal, u)
                s["root"].rotation_euler = (lerp(math.sin(B(bi) + k) * 0.6, 0, u), lerp(B(bi) * 0.3 + k, 0, u), lerp(k, math.pi, u))
                s["root"].scale = Vector((1, 1, 1)) * lerp(0.8, 1.0, u) * (1 + 0.03 * ds_pulse(b))
            w["v"].outputs[0].default_value = 1.0 if b >= b0 + 5 else 0.0

    def story(t, b):
        hide_r8()
        for w in WALL3:
            w["s"]["root"].location = HIDE
        flash_run(b, [12, 16, 24, 32, 40])
        isl = ISLAND.location
        if b < 12:
            space_frame(t, b)
            pool_drift(t, b, list(range(10)), isl, r0=15.0)
            big_place(SPACE_BIG, isl + Vector((3.0, 20.0, 6.0)), math.pi + 0.2, t, 0.3)
            bob = math.sin(t * 0.8) * 0.3
            dp = isl + Vector((-1.5 + b * 0.25, -11.0 + b * 0.5, 3.2 + bob))
            DESK_CG.location = dp
            DESK_CG.rotation_euler = (0.06 * math.sin(t), 0.06 * math.cos(t * 0.8), math.pi + 0.3 * math.sin(t * 0.3))
            if b < 9:
                cg_ds(t, b, dp + Vector((0, 0, 0.77)), math.pi + math.sin(t * 0.5) * 0.5, 0.9)
            else:
                into_portal(CG["root"], dp + Vector((0, 0, 0.9)), "space", b, 9, 12, CG_S)
                pose_cg(t, 1.0, "flattern")
            DESK_MM.location = isl + Vector((3.0, -4.2, 0))
            DESK_MM.rotation_euler = (0, 0, 0)
            if b < 9.5:
                put(MM["root"], isl + Vector((3.0, -3.45, -0.29)), math.pi, 1.0)
                pose_mm(t, "sitzen")
                if b > 6.5:
                    MM["neck"].rotation_euler = (-0.3, 0, -0.5 * smooth((b - 6.5) / 1.0))
            else:
                if into_portal(MM["root"], isl + Vector((3.0, -3.45, 0.2)), "space", b, 9.5, 12):
                    MM["root"].rotation_euler.x = -1.2
                    pose_mm_fly(t, b)
            ufo_run(t, b, isl + Vector((-6.0, 2.0, 14.0)), beam=True)
            cu = kk(b, 0, 11)
            put(COW["root"], isl + Vector((-6.0, 2.0, 0.2 + cu * 12.0)), t * 0.5, 1.0 - 0.6 * cu, rx=math.sin(t) * 0.5)
            put(MU["root"], isl + Vector((8.5, -6.0, 5.0 + math.sin(t * 0.6) * 0.5)), math.pi - 0.6 + t * 0.15, 1.0, rx=0.2 * math.sin(t * 0.4))
            pose_munch(t, 1.0)
            gm_rocket_run(t, b, isl + Vector((-30, 18, 12)), isl + Vector((30, 10, 9)), 1, 9)
        elif b < 16:
            set_world("tunnel")
            yy = 8 + kk(b, 12, 16) * 108
            world_tunnel(t, b, yy)
            put(MM["root"], TW + Vector((-0.75, yy, -0.9 + 0.2 * math.sin(t * 3))), 0.2 * math.sin(t * 2), 1.0, rx=-1.2)
            pose_mm_fly(t, b)
            put(CG["root"], TW + Vector((0.9, yy - 0.6, -0.4 + 0.25 * math.sin(t * 2.6))), 0.3 * math.sin(t * 1.7), CG_S, rx=-0.6)
            pose_cg(t, 1.0, "flattern")
        elif b < 24:
            set_world("fabrik")
            world_fabrik(t, b)
            y = 4.0 + 2.8 * max(0.0, t - B(16))
            zf = 8.0 * (1 - kk(b, 16, 16.6)) ** 2
            cg_ds(t, b, FWV + Vector((0.0, y, 0.95 + zf)), math.pi + 0.3 * math.sin(t * 0.5), 1.0)
            mm_ds(t, b, FWV + Vector((-3.2, y - 1.0, 0.95 + zf * 1.2)), math.pi - 0.3)
            hd_dancers_run(t, b, [FWV + Vector((0.0, y + 1.5, 0.95)), FWV + Vector((0.0, y - 1.5, 0.95)), FWV + Vector((3.2, y, 0.95)),
                                  FWV + Vector((3.2, y + 2.0, 0.95))])
            put(MU["root"], FWV + Vector((5.4, y + 6.0, 0)), math.radians(-110), 1.0)
            pose_munch(t, 1.0)
            for i, d in enumerate(CROWD[:10]):
                side = -1 if i % 2 else 1
                crowd_pose(d, t, b, "dance", FWV + Vector((side * (5.4 + (i // 2) % 2 * 1.2), y - 4 + (i // 2) * 2.0, 0)), math.pi + side * 0.6)
        elif b < 32:
            set_world("regen")
            world_regen(t, b, RW + Vector((0, 14, 0)))
            u = kk(b, 24, 32)
            hp = RW + Vector((-14 + u * 30, 6 + u * 14, 9 + math.sin(u * math.pi * 2) * 3))
            rz = math.atan2(14, 30)
            hd_ride(hp, rz, t)
            cg_ds(t, b, hp + Vector((0.5, 0, 0.45)), rz - math.pi / 2, 1.0)
            mm_ds(t, b, hp + Vector((-0.9, -0.2, 0.45)), rz - math.pi / 2 + 0.3)
            crowd_floor(t, b, RW + Vector((0, 16, 0.3)), "dance")
            sneaker_run(t, b, [(26, 30, RW + Vector((-40, 40, 22)), RW + Vector((40, 30, 16)))])
        elif b < 40:
            set_world("pepsi")
            world_pepsi(t, b)
            c = WX["pepsi"]
            wv = math.sin(t * 1.5) * 0.4
            trick, spin, air = "carve", 0.0, 0.0
            if 34 <= b < 35.5:
                trick = "air"
                air = math.sin((b - 34) / 1.5 * math.pi) * 2.2
            if 37 <= b < 38.5:
                spin = ease_inout((b - 37) / 1.5) * math.tau
            sy = 6 + (b - 32) * 1.5
            sp = c + Vector((math.sin(t * 0.5) * 2.5, sy, 0.1 + wv + air))
            dz = 6.0 * (1 - kk(b, 32, 32.6)) ** 2
            SURF.location = sp + Vector((0, 0, dz))
            SURF.rotation_euler = (math.sin(t * 1.3) * 0.08 + (0.3 if trick == "air" else 0), math.sin(t * 1.1) * 0.1, math.radians(90) + spin)
            put(MM["root"], sp + Vector((0, 0, 0.12 + dz)), math.radians(90) + spin, 1.0)
            pose_mm(t, "surfen", trick)
            dp = c + Vector((-4.6, sy + 2.0, -0.4 + math.sin(t * 1.4 + 1) * 0.35))
            DUCK.location = dp
            DUCK.rotation_euler = (math.sin(t * 1.2) * 0.06, math.sin(t) * 0.06, math.radians(15))
            cg_ds(t, b, dp + Vector((0, -0.4, 3.1 + dz * 1.3)), math.pi + 0.3, 1.0)
            ja = t * 0.9
            jp = c + Vector((math.cos(ja) * 10, sy + 7 + math.sin(ja) * 7, 0.2 + wv * 0.6))
            JETSKI.location = jp
            JETSKI.rotation_euler = (0, math.sin(t * 2) * 0.15, ja + math.pi)
            put(PENG["root"], jp + Vector((0, -0.3, 0.6)), ja + math.pi, 1.0)
        else:
            space_frame(t, b)
            isl_ = isl
            wall_run(t, b, isl_ + Vector((0, 15.0, 2.0)), 40)
            mm_ds(t, b, isl_ + Vector((1.0, -7.4, 0.06)), math.pi)
            cg_ds(t, b, isl_ + Vector((-1.0, -7.2, 0.06)), math.pi + math.sin(t * 0.7) * 0.4)
            if b < 41.2:
                k = kk(b, 40, 41.2)
                MM["root"].location.z += 14 * (1 - k) ** 2
                CG["root"].location.z += 16 * (1 - k) ** 2
            crowd_floor(t, b, isl_ + Vector((0, -1.2, 0.06)), "dance")
            put(GM["root"], isl_ + Vector((-4.2, -6.4, 0.06)), math.pi + 0.5, 1.0)
            pose_grandma(t, b, erupt_from=42)
            veg_at(t, b, isl_ + Vector((0, 0.4, 0.06)))
            DISCO.location = isl_ + Vector((0, -4.0, 9.0))
            DISCO.rotation_euler = (0, 0, t * 1.4)
            DISCO_E.outputs[0].default_value = 0.4 + 2.5 * ds_pulse(b)
            hd_space_run(t, b, isl_ + Vector((0, -2, 0)), b >= 46)
            banner_run(t, b, isl_ + Vector((40, 36, 24)), isl_ + Vector((-40, 36, 24)), 41, 48)

    sh_(0, lambda: ISL() + Vector((4.0, -19.0, 4.5)), lambda: ISL() + Vector((0.5, -7.0, 2.5)), 22, trans=0, drift=0.8)
    sh_(4, lambda: DESK_CG.location + Vector((-1.7, -3.6, 2.0)), lambda: cg_head() + Vector((0, 0, -0.1)), 30)
    sh_(6.5, lambda: ISL() + Vector((4.2, -6.8, 1.6)), lambda: mm_head() + Vector((0, 0, -0.2)), 28)
    sh_(9, lambda: mid2() + Vector((1.5, -6.0, 1.5)), lambda: portal_front("space"), 22)
    sh_(12, lambda: TW + Vector((0.2, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 12, 16) * 108 + 4.6, 0.3)),
        lambda: TW + Vector((0, 8 + kk(beat_of((scn.frame_current - 1) / FPS), 12, 16) * 108, -0.4)), 24, trans=0)
    sh_(16, lambda: FWV + Vector((3.0, 4.0 + 2.8 * max(0.0, (scn.frame_current - 1) / FPS - B(16)) - 5.6, 2.8)),
        lambda: FWV + Vector((-1.4, 4.0 + 2.8 * max(0.0, (scn.frame_current - 1) / FPS - B(16)) + 1.0, 1.7)), 22, trans=0)
    sh_(20, lambda: cg_mid() + Vector((1.6, -3.4, 1.2)), lambda: cg_head() + Vector((0, 0, -0.15)), 28)
    sh_(22, lambda: mm_mid() + Vector((-1.8, -3.2, 1.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 28)
    sh_(24, lambda: HD_RIDE.location + Vector((3.0, -7.0, 2.0)), lambda: HD_RIDE.location + Vector((0, 0, 1.3)), 24, trans=0)
    sh_(28, lambda: HD_RIDE.location + Vector((-2.2, 4.5, 2.4)), lambda: HD_RIDE.location + Vector((0, 0, 1.4)), 26)
    sh_(32, lambda: SURF.location + Vector((4.4, -3.4, 1.6)), lambda: mm_mid() + Vector((0, 0, 1.2)), 26, trans=0)
    sh_(36, lambda: DUCK.location + Vector((2.6, -5.0, 4.2)), lambda: cg_head() + Vector((0, 0, -0.3)), 28)
    sh_(38, lambda: mm_mid() + Vector((-4.5, -5.0, 1.6)), lambda: mm_mid() + Vector((0, 1.0, 1.0)), 22)
    sh_(40, lambda: ISL() + Vector((0.5, -16.0, 4.0)), lambda: ISL() + Vector((0, 4.0, 5.5)), 22, trans=0)
    sh_(44, lambda: ISL() + Vector((0, -26.0, 7.0)), lambda: ISL() + Vector((0, 10.0, 8.0)), 20, drift=-0.5, rise=0.4)
    sh_(46, lambda: cg_mid() + Vector((-1.3, -3.0, 1.0)), lambda: cg_head(), 30)

STORY = story



PORTRAIT = bool(opt("--portrait"))


def animate(t):
    b = beat_of(t)
    STORY(t, b)
    if CAM_OVERRIDE:
        CAM_OVERRIDE()
    else:
        ds_camera(b)
    FLASH.scale = (0, 0, 0)
    ovl_update()


def on_frame(scene, depsgraph=None):
    t = (scene.frame_current - 1) / FPS
    animate(t)


bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)
apply_haze()
set_sky("orbit" if SPACE_ON else "buero")


def no_shadow(ob):
    if hasattr(ob, "visible_shadow"):
        ob.visible_shadow = False
    for ch in ob.children:
        no_shadow(ch)


no_shadow(OVL)

# ------------------------------------------------------------------ Render-Einstellungen
r = scn.render
if ENGINE == "CYCLES":
    r.engine = "CYCLES"
    scn.cycles.samples = SAMPLES
    scn.cycles.use_denoising = True
    if opt("--cpu", flag=True):
        scn.cycles.device = "CPU"
    else:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
                try:
                    prefs.compute_device_type = kind
                    prefs.get_devices()
                    if any(d.type == kind for d in prefs.devices):
                        for d in prefs.devices:
                            d.use = d.type == kind
                        scn.cycles.device = "GPU"
                        print("Cycles-Gerät:", kind)
                        break
                except TypeError:
                    continue
        except Exception as e:   # noqa: BLE001
            print("GPU-Auswahl fehlgeschlagen:", e)
else:
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            r.engine = eng
            break
        except TypeError:
            continue
    ee = scn.eevee
    ee.taa_render_samples = SAMPLES
    # --fast: schlanker wie Dat Swag (kein Screen-Space-Raytracing, grobe Dunst-Kacheln, weniger Samples)
    FAST = opt("--fast", flag=True)
    if FAST and not opt("--samples"):
        ee.taa_render_samples = 16
    for attr, val in (("use_bloom", True), ("bloom_intensity", 0.08), ("use_gtao", True), ("use_volumetric_shadows", False),
                      ("volumetric_tile_size", "16" if FAST else "4"), ("use_raytracing", not FAST)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception:   # noqa: BLE001
                pass
# Farbmanagement wie Dat Swag: Standard ohne Look, flache Farben, Neon darf ausbrennen
scn.view_settings.view_transform = opt("--view", "Standard")
scn.view_settings.look = "None"
scn.view_settings.exposure = float(opt("--exposure", 0.25))

# Glow + leichte Linsenverzerrung im Compositor (Blender 4: scene.node_tree, Blender 5: compositing_node_group)
def setup_compositor():
    if hasattr(scn, "compositing_node_group"):
        ng = bpy.data.node_groups.new("Komposition", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        out_n = ng.nodes.new("NodeGroupOutput")
        rl = ng.nodes.new("CompositorNodeRLayers")
        scn.compositing_node_group = ng
        out_in = out_n.inputs[0]
    else:
        scn.use_nodes = True
        ng = scn.node_tree
        rl = ng.nodes.get("Render Layers") or ng.nodes.new("CompositorNodeRLayers")
        out_in = (ng.nodes.get("Composite") or ng.nodes.new("CompositorNodeComposite")).inputs["Image"]
    glare = ng.nodes.new("CompositorNodeGlare")
    # Bloom wie bei Dat Swag (threshold 1.6, strength 0.6)
    for attr, val in (("glare_type", "BLOOM"), ("quality", "MEDIUM"), ("threshold", 1.6), ("size", 7)):
        if hasattr(glare, attr):
            try:
                setattr(glare, attr, val)
            except Exception:   # noqa: BLE001
                pass
    for name, val in (("Type", "Bloom"), ("Threshold", 1.6), ("Strength", 0.6), ("Size", 0.6)):
        if name in glare.inputs:
            try:
                glare.inputs[name].default_value = val
            except Exception:   # noqa: BLE001
                pass
    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    last = glare.outputs["Image"]
    # Runde 8: knalliger – mehr Sättigung und Kontrast nach dem Bloom
    try:
        hs = ng.nodes.new("CompositorNodeHueSat")
        sat = float(opt("--sat", 1.3))
        for name, val in (("Saturation", sat), ("Value", float(opt("--value", 1.04)))):
            if name in hs.inputs:
                hs.inputs[name].default_value = val
        if hasattr(hs, "color_saturation"):
            hs.color_saturation = sat
        ng.links.new(last, hs.inputs["Image"])
        last = hs.outputs["Image"]
        bc = ng.nodes.new("CompositorNodeBrightContrast")
        for name, val in (("Bright", 2.0), ("Brightness", float(opt("--bright", 2.0))), ("Contrast", float(opt("--contrast", 14.0)))):
            if name in bc.inputs:
                bc.inputs[name].default_value = val
        ng.links.new(last, bc.inputs["Image"])
        last = bc.outputs["Image"]
    except Exception as e:   # noqa: BLE001
        print("Farbkorrektur übersprungen:", e)
    ng.links.new(last, out_in)


try:
    if not opt("--nocomp", flag=True):
        setup_compositor()
except Exception as e:   # noqa: BLE001
    print("Compositor übersprungen:", e)

# Song in den Sequencer, ab dem berechneten Offset
song = opt("--song")
if song and os.path.exists(song):
    se = scn.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    snd = strips.new_sound("MyMind", song, channel=1, frame_start=1)
    off = int(round(float(P.get("song_offset_s", 0)) * FPS))
    snd.frame_offset_start = off
    snd.frame_start = 1 - off
    print("Song-Offset: %.3f s (%d Frames)" % (P.get("song_offset_s", 0), off))

out = opt("--out", os.path.join(HERE, "out", "mino_drift_v%d.mp4" % VARIANT))
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

if opt("--save"):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(opt("--save")))

if opt("--portrait"):
    # Figurenbogen: --portrait cg:schrei,cg:ekstase,mm,mu,gm
    DANCE = False
    r.image_settings.file_format = "PNG"
    for spec in opt("--portrait").split(","):
        who, _, ex = spec.partition(":")
        EXPR_FORCE = ex or None
        CAM_OVERRIDE = None
        scn.frame_set(int(B(36) * FPS) + 1)
        bpy.context.view_layer.update()
        if who == "cg":
            hd = cg_head() - Vector((0, 0, 0.08))
            cam_args = (hd + Vector((-0.25, -2.1, 0.05)), hd, 0.0, 60)
        elif who == "cgauge":   # Detail: linkes Auge
            hd = CG["real"]["eyes"]["L"].matrix_world.translation.copy() if CG.get("real") else CG["head"].matrix_world.translation
            cam_args = (hd + Vector((-0.05, -0.6, 0.04)), hd, 0.0, 120)
        elif who == "cgk":   # ganzer Körper
            hd = CG["root"].matrix_world.translation + Vector((0, 0, 1.0))
            cam_args = (hd + Vector((-0.4, -4.0, 0.1)), hd, 0.0, 50)
        else:
            obj = {"mm": MM, "mu": MU}[who]
            hd = obj["head"].matrix_world.translation + Vector((0, 0, 0.15))
            cam_args = (hd + Vector((-0.15, -1.0, 0.0)), hd, 0.0, 60)
        CAM_OVERRIDE = (lambda a=cam_args: look(*a))
        on_frame(scn)
        r.filepath = os.path.abspath(out.replace(".mp4", "_portrait_%s_%s.png" % (who, ex or "x")))
        bpy.ops.render.render(write_still=True)
    sys.exit(0)

if opt("--still"):
    for ts in opt("--still").split(","):
        tsec = float(ts)
        scn.frame_set(int(round(tsec * FPS)) + 1)
        on_frame(scn)
        r.image_settings.file_format = "PNG"
        r.filepath = os.path.abspath(out.replace(".mp4", "_%05.2f.png" % tsec))
        bpy.ops.render.render(write_still=True)
        print("Standbild:", r.filepath)
else:
    if opt("--frames"):
        a_, b_ = opt("--frames").split("-")
        scn.frame_start, scn.frame_end = int(a_), int(b_)
    if opt("--pngdir"):
        # Dat-Swag-Weg: Einzelbilder, danach mit mux.py (ffmpeg) zu MP4 mit Song – abbrechbar und fortsetzbar
        d = os.path.abspath(opt("--pngdir"))
        os.makedirs(d, exist_ok=True)
        r.image_settings.file_format = "PNG"
        r.use_overwrite = False
        r.filepath = os.path.join(d, "f_")
        bpy.ops.render.render(animation=True)
        print("Frames fertig:", d, scn.frame_start, "-", scn.frame_end)
        sys.exit(0)
    r.image_settings.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    r.ffmpeg.constant_rate_factor = "HIGH"
    r.ffmpeg.audio_codec = "AAC" if song else "NONE"
    r.ffmpeg.audio_bitrate = 192
    r.filepath = os.path.abspath(out)
    bpy.ops.render.render(animation=True)
    print("Fertig:", r.filepath, "Frames", scn.frame_start, "-", scn.frame_end)

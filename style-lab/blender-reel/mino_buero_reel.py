"""MINO BÜRO – Blender-Test-Reels für den Minoverse (Rahmen: das endlose Büro unter freiem Himmel).

Welt: Großraumbüro-Kabinen bis zum Horizont, kein Dach, die Sonne scheint – die ganze Welt ist das Büro.
Auf den Röhren-PCs und in den Akten laufen völlig wilde Geschichten, die nicht zum Bürokratischen passen.
Akten poppen auf wie die Fehlerdialoge bei Dat Swag, man klickt sich durch die Computer, und immer wieder
taucht man durch einen Bildschirm oder eine Akte in eine verrückte neue Welt ein. Mino Man und Chicken Guy
tanzen durch die Gänge.

Alles ist aus Code gebaut (keine Fremdmodelle). Die Animation läuft als Funktion der Zeit über einen
frame_change-Handler, damit Beats exakt sitzen. Drei Varianten (--variant 1|2|3) teilen sich Welt und Figuren.

  blender -b --factory-startup --python mino_buero_reel.py -- --variant 1 --params params_v1.json --pngdir out/v1
  Optionen: --res 540x960  --fps 30  --engine EEVEE|CYCLES  --samples 16  --still 3.5,8  --save scene.blend
            --frames 1-120  --cpu  --fast  --nocomp  --portrait cg:schrei,cgk:ekstase,mm
"""
import json
import math
import os
import random
import sys

import bpy
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
        screen_text(s, "NACHRICHTEN", 0.15, "#ffd23c", y_rel=0.05)
        bar = screen_bar(s, "#ffffff", -0.33, 0.14, strength=4.0)
        tk = screen_text(s, "+++ GOTT ABWESEND +++", 0.09, "#c4002a", y_rel=-0.33, fnt="barlow")
        s["anim"].append(lambda t, b, o=tk: setattr(o, "hide_render", int(b * 4) % 4 == 3))
    elif p == "vermisst":
        screen_text(s, "VERMISST", 0.2, "#ffffff", y_rel=0.25)
        o = screen_text(s, "CHICKEN GUY", 0.17, "#ffe34a", y_rel=-0.02)
        screen_text(s, "ZULETZT GESEHEN: TANZEND", 0.075, "#ffffff", y_rel=-0.3, fnt="barlow")
        s["anim"].append(lambda t, b, o=o: setattr(o, "hide_render", int(b * 2) % 2 == 1))
    elif p == "spirale":
        pl = prim("plane", s["name"] + "_spirale", (sc.x, 0.04, sc.z), (W * 0.98, H * 0.98, 1), rot=rot, m=SPIRAL_M)
        screen_obj(s, pl)
        screen_text(s, "NICHT HINSEHEN", 0.11, "#ffe34a", y_rel=-0.36, strength=8)
    elif p == "hotdog":
        screen_text(s, "ES REGNET", 0.14, "#ffffff", y_rel=0.3)
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
        screen_text(s, "EMPFIEHLT: NOCH EINE!", 0.08, "#ffe34a", y_rel=-0.38, fnt="barlow")
        o = instance(s["name"] + "_flasche", PEPSI, (sc.x, 0.06, sc.z - H * 0.28), rot=(0, 0, 0), scale=H * 0.55)
        screen_obj(s, o)
        s["anim"].append(lambda t, b, o=o: setattr(o.rotation_euler, "y", math.sin(t * 6) * 0.4))
    elif p == "desktop":
        for i, lab in enumerate(("AKTE.EXE", "HOTDOG.BAT", "CHICKEN.GIF")):
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
        screen_text(s, "AKTE 404", 0.14, "#b48cff", y_rel=0.12)
        screen_text(s, "IM ALL VERLOREN", 0.08, "#ffffff", y_rel=-0.12, fnt="barlow")


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
        prog = {1: "hotdog", 2: "news", 3: "pixel"}[VARIANT]
    elif key == (1, 0, 0, 0, 2) and VARIANT == 2:   # unser Rechner in Variante 2
        prog = "desktop"
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


CG_BZ, CG_BS = 0.8, (1.25, 1.25, 1.2)


def build_chickenguy(loc):
    """Chicken Guy nach dem Original: riesiger ovaler Kopf auf einem knusprigen Brathähnchen,
    dürre Flügelarme, Keulenbeine. Das Gesicht hat ein eigenes Rig: Kiefer, Mundhöhle mit Zahnlücke, Zunge,
    Lider, Brauen, Wangen – für Schreien, Grimassen, Augen-zu-Ekstase."""
    R = empty("ChickenGuy", loc)
    crisp = noise_mat("Kruste", "#5a2a0c", "#b8661e", scale=6, rough=0.32, bump=0.6, c2="#e0a048", detail=8)
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
    folder = akte("MU_akte", (0, 0.0, -0.36), col="#d9b77a", label="AKTE 001", parent=fore, scale=1.0)
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



AKTEN_TEXT = ["AKTE 001\nCHICKEN GUY\nZUSTAND: GEGESSEN", "AKTE 017\nHOT-DOG-REGEN\n(VEGAN)\nSTATUS: BEANTRAGT",
              "AKTE 404\nNICHT GEFUNDEN", "AKTE 002\nPEPSI GRANDMA\nWIEDERHOLT", "AKTE 033\nMITTWOCH\nFOLGTE DIENSTAG",
              "AKTE 009\nGOTT\nABWESEND", "AKTE 120\nTANZEN\nERLAUBT"]
# ------------------------------------------------------------------ Figuren aufstellen
MM = build_minoman((0, 0, 0))
CG = build_chickenguy((0, 0, 0))
HS_CG = (0.31, 0.3, 0.39)
BROW_Z = CG["eyes"][1]["brow"].location.z
MU = build_munch((0, 0, 0))
CG_S = 0.85
MM_DESK = HERO[(1, 0, 0, 0, 1)]          # Mino Mans Kabine am Hauptgang
POV_DESK = HERO[(1, 0, 0, 0, 2)]         # die Kabine daneben (Variante 2: wir sitzen hier)


def seat_pos(h, z=0.0):
    return cw(h["cell"], (0, -0.1, z))


# Kollegen in den Kabinen am Gang (animiert: tippen, später Party)
WORKERS = []
SHIRTS = ["#f2d04a", "#f4f1ea", "#9ec3e6", "#e8b4c8", "#b8d8a8"]


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
    w = {"root": R, "head": head, "arms": arms, "seed": len(WORKERS), "rz": cell[2] + math.pi}
    WORKERS.append(w)
    return w


for i, (key, h) in enumerate(sorted(HERO.items())):
    if h is MM_DESK or (VARIANT == 2 and h is POV_DESK):
        continue
    if hsh(i * 4.1 + 2) < 0.62:
        h["worker"] = worker("Kollege%02d" % i, h, SHIRTS[i % len(SHIRTS)])

# Pflanzen und Wasserspender am Gang (Leben im Raster)
PLANT_M = noise_mat("Blatt", "#2f7a32", "#58a83c", scale=12, rough=0.6, bump=0.2)
POT_M = mat("Topf", "#c86a3c", 0.7)
for i, y in enumerate((-1.3, 13.4, 28.2, 43.0)):
    for sx in (-1, 1):
        root = empty("Pflanze%d%d" % (i, sx), (sx * 1.15, y, 0))
        prim("cyl", "Topf%d%d" % (i, sx), (0, 0, 0.2), (0.4, 0.4, 0.4), m=POT_M, parent=root, seg=16)
        for k in range(7):
            prim("ico", "Laub%d%d%d" % (i, sx, k), ((hsh(k + i) - .5) * 0.4, (hsh(k * 3 + i) - .5) * 0.4, 0.6 + k * 0.12), (0.4, 0.4, 0.5),
                 m=PLANT_M, parent=root)

# Akten auf den Tischen am Gang
for i, (key, h) in enumerate(sorted(HERO.items())):
    if hsh(i * 1.7) < 0.5:
        for j in range(1 + int(hsh(i) * 4)):
            akte("TischAkte%d_%d" % (i, j), cw(h["cell"], (0.6, -1.05, 0.76 + j * 0.026)), h["cell"][2] + (hsh(i + j) - .5) * 0.5,
                 label=AKTEN_TEXT[(i + j) % len(AKTEN_TEXT)] if j == 0 else None)

# fliegende Blätter (Party im Büro)
FLYERS = []
for i in range(50):
    ob = prim("plane", "Blatt%02d" % i, (0, 0, -50), (0.21, 0.297, 1), m=PAPER_M)
    FLYERS.append({"ob": ob, "seed": i})

# ------------------------------------------------------------------ UI-Ebene vor der Kamera (Akten-Pop-ups, Dialoge, Blitz)
OVL_D = 0.3
OVL = empty("UI", (0, 0, -OVL_D), CAM)


def ui(name, color, strength=1.0):
    return emit_mat("UI_" + name, color, strength)


UI_INK = ui("Tinte", "#1a1a1a")
UI_MANILA = ui("Manila", "#e2c286")
UI_MANILA_D = ui("ManilaDunkel", "#c9a464")
UI_PAPER = ui("Papier", "#f7f3e8")
UI_BLACK = ui("Schwarz", "#050505")
UI_RED = ui("Stempel", "#d8142a", 1.4)
UI_GREY = ui("Grau", "#c0c0c0")
UI_WHITE = ui("Weiss", "#ffffff")
UI_DARK = ui("Dunkelgrau", "#5a5a5a")
UI_BLUE = ui("Titel", "#000080")


def ui_box(name, loc, size, m, parent):
    o = prim("cube", name, loc, size, m=m, parent=parent)
    return o


def ui_text(name, body, size, m, parent, loc, align="CENTER", fnt="barlow"):
    return text(name, body, size=size, m=m, parent=parent, loc=loc, fnt=fnt, align=align)


def lit(name, color, rough=0.5, e=0.35):
    """Für die kleinen Dioramen in den Akten: beleuchtet, aber mit Eigenleuchten, damit sie wie UI lesbar bleiben."""
    return mat("UI_" + name, color, rough, emit=color, estr=e)


# --- Inhalte der Akten: kleine wilde Pop-up-Welten (Koordinaten: Seite ±0.42 x ±0.29, z zur Kamera)
def content_disco(st):
    ui_box(st.name + "_nacht", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("Disco", "#14062a"), st)
    ball = prim("ico", st.name + "_kugel", (0, 0.12, 0.12), (0.16, 0.16, 0.16), m=mat("UI_Discokugel", "#dddddd", 0.1, metal=1.0, emit="#ffffff", estr=0.6), parent=st)
    ball.modifiers.clear()
    beams = []
    for k in range(6):
        piv = empty(st.name + "_strahlpiv%d" % k, (0, 0.12, 0.12), st)
        prim("cone", st.name + "_strahl%d" % k, (0, -0.2, 0), (0.07, 0.07, 0.4), rot=(math.radians(90), 0, 0),
             m=ui("Strahl%d" % k, ["#ff3fa4", "#3fd0ff", "#ffe34a"][k % 3], 2.5), parent=piv, seg=12)
        piv.rotation_euler.z = k * math.tau / 6
        beams.append(piv)
    spr = [pixel_sprite(st.name + "_cg%d" % k, CG_SPRITE[k], 0.022, st, (0, -0.12, 0.05), (0, 0, 0), strength=1.5) for k in (0, 1)]
    ui_text(st.name + "_t", "ZULETZT GESEHEN: HIER", 0.04, ui("Gelb", "#ffe34a"), st, (0, -0.26, 0.01))

    def anim(t, lt, ok):
        ball.rotation_euler.z = t * 3
        for k, p in enumerate(beams):
            p.rotation_euler = (math.sin(t * 2 + k) * 0.4, 0, k * math.tau / 6 + t * 2.5)
        for k, o in enumerate(spr):
            o.scale = (1, 1, 1) if int(beat_of(t) * 2) % 2 == k else (0, 0, 0)
    return anim


def content_vulkan(st):
    ui_box(st.name + "_himmel", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("Abendrot", "#ff8a3c"), st)
    prim("cone", st.name + "_berg", (0, -0.18, 0.06), (0.5, 0.12, 0.3), rot=(math.radians(-90), 0, 0), m=lit("Lava", "#5a2a14"), parent=st, seg=24)
    dogs = [instance(st.name + "_hd%d" % k, HOTDOG, (0, 0, -5), scale=0.09, parent=st) for k in range(9)]
    ui_text(st.name + "_t", "HOT-DOG-VULKAN AKTIV", 0.04, UI_INK, st, (0, 0.24, 0.01))

    def anim(t, lt, ok):
        for k, o in enumerate(dogs):
            ph = ((lt * BEAT) * 1.4 + k / len(dogs)) % 1.0
            a = (hsh(k * 3) - 0.5) * 2.2
            o.location = (a * ph * 0.25, -0.03 + ph * 0.5 - ph * ph * 0.42, 0.1 + ph * 0.15)
            o.rotation_euler = (t * 4 + k, t * 3, k)
            o.scale = (0.09 * ok,) * 3
    return anim


def content_pepsi(st):
    ui_box(st.name + "_blau", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("PepsiHintergrund", "#2a6cff"), st)
    bot = instance(st.name + "_flasche", PEPSI, (0, -0.27, 0.06), rot=(math.radians(-90), 0, 0), scale=0.33, parent=st)
    bot.rotation_euler = (math.radians(-90), 0, 0)
    foam = [prim("ico", st.name + "_schaum%d" % k, (0, 0, 0), (0.04,) * 3, m=ui("Schaum", "#ffffff"), parent=st) for k in range(16)]
    ui_text(st.name + "_t", "NOCH EINE.", 0.05, UI_WHITE, st, (0.2, 0.22, 0.01))

    def anim(t, lt, ok):
        for k, f in enumerate(foam):
            ph = ((lt * BEAT) * 1.8 + k / len(foam)) % 1.0
            a = (hsh(k * 5) - 0.5) * 0.6
            f.location = (a * ph, 0.02 + ph * 0.45 - ph * ph * 0.25, 0.08 + hsh(k) * 0.06)
            s = (0.03 + hsh(k * 2) * 0.03) * ok * (1 - ph * 0.5)
            f.scale = (s, s, s)
        bot.rotation_euler.y = math.sin(t * 9) * 0.15
    return anim


def content_all(st):
    ui_box(st.name + "_nacht", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("All", "#05020f"), st)
    for k in range(30):
        prim("ico", st.name + "_st%d" % k, ((hsh(k * 2.1) - .5) * 0.8, (hsh(k * 3.7) - .5) * 0.54, 0.004), (0.006,) * 3, m=ui("Stern", "#ffffff", 3), parent=st)
    pl = prim("sphere", st.name + "_planet", (0.2, 0.06, 0.08), (0.18, 0.18, 0.18), m=lit("Planet", "#ff8a4a", 0.6, 0.5), parent=st, seg=24)
    ring = prim("torus", st.name + "_ring", (0.2, 0.06, 0.08), (0.42, 0.42, 0.1), rot=(math.radians(70), 0, 0.3), m=ui("Ring", "#ffd8a8"), parent=st)
    mm = empty(st.name + "_mm", (-0.18, -0.05, 0.1), st)
    prim("cube", st.name + "_mmanzug", (0, 0, 0), (0.07, 0.04, 0.1), m=lit("Anzug", "#1b2238"), parent=mm)
    prim("sphere", st.name + "_mmkopf", (0, 0, 0.08), (0.05, 0.05, 0.065), m=lit("MMHaut", "#d9a98f"), parent=mm, seg=12)
    prim("cube", st.name + "_mmbrille", (0, 0.022, 0.085), (0.052, 0.01, 0.014), m=ui("Pink", "#e2558c"), parent=mm)
    ui_text(st.name + "_t", "MINO MAN BERICHTET LIVE AUS DEM ALL", 0.03, UI_WHITE, st, (0, -0.25, 0.01))

    def anim(t, lt, ok):
        pl.rotation_euler.z = t
        mm.rotation_euler = (t * 0.7, 0, t * 1.3)
        mm.location = (-0.18 + math.sin(t) * 0.04, -0.05 + math.cos(t * 1.3) * 0.03, 0.1)
    return anim


def content_auge(st):
    ui_box(st.name + "_rot", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("AugeHinten", "#8a0f2a"), st)
    eye = empty(st.name + "_auge", (0, 0.02, 0.06), st)
    prim("sphere", st.name + "_weiss", (0, 0, 0), (0.36, 0.36, 0.36), m=lit("Augapfel", "#f4efe8", 0.3, 0.6), parent=eye, seg=32)
    prim("sphere", st.name + "_iris", (0, 0, 0.15), (0.17, 0.17, 0.06), m=ui("Iris", "#2bb24c"), parent=eye, seg=24)
    prim("sphere", st.name + "_pupille", (0, 0, 0.175), (0.08, 0.08, 0.03), m=UI_BLACK, parent=eye, seg=16)
    lid = prim("cube", st.name + "_lid", (0, 0.4, 0.2), (0.84, 0.4, 0.01), m=ui("Lid", "#8a0f2a"), parent=st)
    ui_text(st.name + "_t", "DAS AUGE PRÜFT IHREN ANTRAG", 0.035, UI_WHITE, st, (0, -0.25, 0.22))

    def anim(t, lt, ok):
        eye.rotation_euler = (math.sin(t * 2.7) * 0.4, math.sin(t * 1.9) * 0.5, 0)
        blink = 1.0 if (t % 1.6) < 0.12 else 0.0
        lid.location.y = lerp(0.4, 0.1, blink)
        lid.scale.y = lerp(0.2, 0.62, blink) / 0.4 * 0.4
    return anim


def content_spirale(st):
    m = spiral_mat("UI_SpiraleAkte", "#000000", "#ffffff", "#ff3fa4", emitting=True)
    pl = prim("plane", st.name + "_spirale", (0, 0, 0.003), (0.84, 0.58, 1), m=m, parent=st)
    ui_text(st.name + "_t", "BITTE NICHT HINSEHEN", 0.045, ui("Gelb", "#ffe34a"), st, (0, -0.24, 0.01))
    return lambda t, lt, ok: None


def content_munch(st):
    crumbs = []
    for k in range(5):     # Bissspuren am Rand
        prim("cyl", st.name + "_biss%d" % k, (0.42, -0.2 + k * 0.1, 0.004), (0.12, 0.12, 0.01), rot=(math.radians(90), 0, 0) if False else (0, 0, 0),
             m=ui("Biss", "#3a3a3a"), parent=st, seg=20)
    for k in range(12):
        crumbs.append(prim("cube", st.name + "_krume%d" % k, (0, 0, 0), (0.02, 0.02, 0.006), m=UI_MANILA_D, parent=st))
    ui_text(st.name + "_t", "DIESE AKTE WURDE\nVON OFFICER MUNCH\nGEGESSEN", 0.05, UI_INK, st, (-0.05, 0.05, 0.01), fnt="courier")

    def anim(t, lt, ok):
        for k, c in enumerate(crumbs):
            ph = ((lt * BEAT) * 0.9 + hsh(k)) % 1.0
            c.location = (0.35 + (hsh(k * 3) - .5) * 0.2, 0.2 - ph * 0.5, 0.03)
            c.rotation_euler = (0, 0, t * 5 + k)
    return anim


def content_hotdog(st):
    ui_box(st.name + "_pink", (0, 0, 0.001), (0.84, 0.58, 0.002), ui("Pink2", "#ff7ab8"), st)
    dogs = [instance(st.name + "_hd%d" % k, HOTDOG, (0, 0, 0), scale=0.1, parent=st) for k in range(10)]
    ui_text(st.name + "_t", "VEGANER HOT-DOG-REGEN:\nNICHT VEGAN", 0.04, UI_WHITE, st, (0, 0.2, 0.012))

    def anim(t, lt, ok):
        for k, o in enumerate(dogs):
            ph = (t * (0.6 + hsh(k) * 0.4) + hsh(k * 3)) % 1.0
            o.location = ((hsh(k * 7) - 0.5) * 0.75, 0.27 - ph * 0.54, 0.05 + hsh(k) * 0.05)
            o.rotation_euler = (0, 0, t * 3 + k)
    return anim


CONTENT = {"disco": content_disco, "vulkan": content_vulkan, "pepsi": content_pepsi, "all": content_all, "auge": content_auge,
           "spirale": content_spirale, "munch": content_munch, "hotdog": content_hotdog}
FOLDERS = []


def ui_folder(name, kind, label, stamp, parent=None, col="#e2c286"):
    root = empty(name, (0, 0, 0), parent if parent is not None else OVL)
    root.scale = (0, 0, 0)
    W, H = 0.9, 0.62
    cm = ui("Deckel_" + col, col)
    ui_box(name + "_rand", (0, 0, -0.008), (W + 0.025, H + 0.025, 0.004), UI_BLACK, root)
    ui_box(name + "_ruecken", (0, 0, 0), (W, H, 0.01), UI_MANILA_D, root)
    ui_box(name + "_reiter", (-W * 0.28, H / 2 + 0.04, 0), (W * 0.36, 0.09, 0.01), UI_MANILA_D, root)
    ui_text(name + "_reitertxt", label.split("\n")[0], 0.045, UI_INK, root, (-W * 0.28, H / 2 + 0.035, 0.007), fnt="courier")
    ui_box(name + "_seite", (0, 0, 0.007), (W * 0.94, H * 0.93, 0.004), UI_PAPER, root)
    st = empty(name + "_buehne", (0, 0, 0.01), root)
    anim = CONTENT[kind](st)
    hinge = empty(name + "_scharnier", (-W / 2, 0, 0.018), root)
    ui_box(name + "_deckel", (W / 2, 0, 0), (W, H, 0.012), cm, hinge)
    ui_box(name + "_deckelrand", (W / 2, 0, -0.002), (W + 0.02, H + 0.02, 0.008), UI_BLACK, hinge)
    ui_text(name + "_titel", label, 0.06, UI_INK, hinge, (W / 2, 0.08, 0.008), fnt="courier")
    stp = ui_text(name + "_stempel", stamp, 0.09, UI_RED, hinge, (W / 2 + 0.12, -0.16, 0.009), fnt="anton")
    stp.rotation_euler.z = 0.3
    f = {"root": root, "hinge": hinge, "stage": st, "anim": anim, "stamp": stp, "kind": kind}
    if parent is None:          # Weltakten (Variante 3) haben ihre eigene Liste
        FOLDERS.append(f)
    return f


FOLDER_DEFS = [
    ("disco", "AKTE 001\nCHICKEN GUY", "VERMISST"), ("vulkan", "AKTE 017\nHOT-DOG-REGEN", "BEANTRAGT"),
    ("auge", "AKTE 033\nANTRAG", "GEPRÜFT"), ("munch", "AKTE 002\nBEWEISE", "GEGESSEN"),
    ("pepsi", "AKTE 003\nPEPSI GRANDMA", "WIEDERHOLT"), ("spirale", "AKTE 404\nNICHT GEFUNDEN", "GEHEIM"),
    ("hotdog", "AKTE 018\nHOT-DOG-REGEN\n(VEGAN)", "ABGELEHNT"), ("all", "AKTE 009\nGOTT", "ABWESEND"),
    ("disco", "AKTE 120\nTANZVERBOT", "AUFGEHOBEN"), ("all", "AKTE 999\nDAS ALL", "ZUSTÄNDIG"),
]
for i, (k, lab, stp) in enumerate(FOLDER_DEFS):
    ui_folder("UIAkte%02d" % i, k, lab, stp, col=["#e2c286", "#f0b8c4", "#bcd0f0", "#e2c286", "#c8e6b0"][i % 5])


# --- Retro-Dialog und Mauszeiger
def ui_dialog(name, title, body, buttons):
    root = empty(name, (0, 0, 0.3), OVL)
    root.scale = (0, 0, 0)
    W, H = 1.02, 0.52
    ui_box(name + "_schatten", (0.02, -0.02, -0.01), (W, H, 0.005), ui("Schatten", "#202020"), root)
    ui_box(name + "_panel", (0, 0, 0), (W, H, 0.01), UI_GREY, root)
    ui_box(name + "_licht", (-W / 2 + 0.006, 0, 0.006), (0.008, H, 0.002), UI_WHITE, root)
    ui_box(name + "_licht2", (0, H / 2 - 0.006, 0.006), (W, 0.008, 0.002), UI_WHITE, root)
    ui_box(name + "_dunkel", (W / 2 - 0.006, 0, 0.006), (0.008, H, 0.002), UI_DARK, root)
    ui_box(name + "_dunkel2", (0, -H / 2 + 0.006, 0.006), (W, 0.008, 0.002), UI_DARK, root)
    ui_box(name + "_titel", (0, H / 2 - 0.055, 0.007), (W - 0.03, 0.075, 0.002), UI_BLUE, root)
    ui_text(name + "_titeltxt", title, 0.045, UI_WHITE, root, (-W / 2 + 0.035, H / 2 - 0.058, 0.01), align="LEFT")
    ui_box(name + "_x", (W / 2 - 0.06, H / 2 - 0.055, 0.009), (0.05, 0.05, 0.004), UI_GREY, root)
    ui_text(name + "_xt", "X", 0.04, UI_INK, root, (W / 2 - 0.06, H / 2 - 0.058, 0.012))
    ui_box(name + "_icon", (-W / 2 + 0.12, 0.04, 0.008), (0.12, 0.09, 0.004), UI_MANILA, root)
    ui_box(name + "_iconreiter", (-W / 2 + 0.09, 0.095, 0.008), (0.06, 0.03, 0.004), UI_MANILA, root)
    ui_text(name + "_body", body, 0.038, UI_INK, root, (-W / 2 + 0.22, 0.05, 0.01), align="LEFT")
    btns = []
    for j, lab in enumerate(buttons):
        x = (j - (len(buttons) - 1) / 2) * 0.32
        b = empty(name + "_btn%d" % j, (x, -H / 2 + 0.085, 0.008), root)
        ui_box(name + "_btnr%d" % j, (0, 0, -0.002), (0.27, 0.085, 0.004), UI_BLACK, b)
        ui_box(name + "_btnf%d" % j, (0, 0, 0), (0.26, 0.075, 0.006), UI_GREY, b)
        ui_text(name + "_btnt%d" % j, lab, 0.04, UI_INK, b, (0, -0.012, 0.005))
        btns.append(b)
    return {"root": root, "btns": btns}


def ui_cursor(name):
    import bmesh
    pts = [(0, 0), (0, -0.17), (0.04, -0.13), (0.07, -0.2), (0.095, -0.19), (0.065, -0.12), (0.12, -0.12)]
    root = empty(name, (0, 0, 0.36), OVL)
    for k, (m, off, sc) in enumerate(((UI_BLACK, -0.003, 1.22), (UI_WHITE, 0.0, 1.0))):
        me = bpy.data.meshes.new(name + "%d" % k)
        bm = bmesh.new()
        cx, cy = 0.035, -0.1
        vs = [bm.verts.new(((x - cx) * sc + cx, (y - cy) * sc + cy, off)) for x, y in pts]
        bm.faces.new(vs)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
        link(bpy.data.objects.new(name + "_%d" % k, me), root)
    root.scale = (0, 0, 0)
    return root


DLG_OPEN = ui_dialog("UIDialog", "AKTE.EXE", "Akte 001 (CHICKEN GUY) enthält\nunzulässig wilde Inhalte.\nTrotzdem öffnen?", ["ÖFFNEN", "ESSEN"])
DLG_END = ui_dialog("UIDialogEnde", "MINOVERSE", "Alle Akten wurden geöffnet.\nAlle Akten wurden gegessen.\nVorgang abgeschlossen.", ["OK"])
CURSOR = ui_cursor("UIMaus")


def flash_mat():
    m, nt, out = node_mat("UI_Blitz")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"; nz.inputs["Scale"].default_value = 300.0
    nz.inputs["Detail"].default_value = 0.0
    nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
    w = nt.nodes.new("ShaderNodeValue"); w.name = "w"
    nt.links.new(w.outputs[0], nz.inputs["W"])
    sn = nt.nodes.new("ShaderNodeMapRange"); sn.inputs["From Min"].default_value = 0.35; sn.inputs["From Max"].default_value = 0.65
    nt.links.new(nz.outputs["Fac"], sn.inputs["Value"])
    snow = nt.nodes.new("ShaderNodeValue"); snow.name = "schnee"
    mix = nt.nodes.new("ShaderNodeMixRGB"); mix.inputs[1].default_value = (1, 1, 1, 1)
    nt.links.new(snow.outputs[0], mix.inputs[0]); nt.links.new(sn.outputs[0], mix.inputs[2])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.6
    nt.links.new(mix.outputs[0], em.inputs[0])
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
    return m, {"w": w, "schnee": snow, "alpha": al}


_fm, FLASH_N = flash_mat()
FLASH = prim("plane", "UI_Blitzflaeche", (0, 0, 0.45), (1.5, 2.4, 1), m=_fm, parent=OVL)

# ------------------------------------------------------------------ Verrückte Welten hinter den Bildschirmen
WX = {"hotdog": Vector((5000, 0, 0)), "pepsi": Vector((-5000, 0, 0)), "kosmos": Vector((0, 5000, 0))}

# Hot-Dog-Himmel: rosa Wolkenmeer, es regnet Hot Dogs, Chicken Guy tanzt riesig
HW = empty("HotDogHimmel", WX["hotdog"])
cloud_m = mat("Wolke", "#ffe3f0", 0.9, emit="#ffc8e2", estr=0.35)
for i in range(70):
    a, r_ = hsh(i * 1.7) * math.tau, 4 + hsh(i * 2.3) * 70
    prim("ico", "Wolke%02d" % i, (math.cos(a) * r_, 15 + math.sin(a) * r_, -3.5 - hsh(i) * 2), (8 + hsh(i * 5) * 10, 8 + hsh(i * 7) * 10, 3 + hsh(i * 9) * 2),
         m=cloud_m, parent=HW, subsurf=1)
HD_RAIN = [instance("Regen%03d" % i, HOTDOG, (0, 0, -50), scale=1.3, parent=HW) for i in range(150)]
HOT_SIGN = text("HotDogSchild", "HOT-DOG-REGEN-PROGRAMM\nSTATUS: NICHT VEGAN", size=2.2, m=emit_mat("Neon", "#ff3fa4", 6), parent=HW,
                loc=(0, 48, 14), rot=(math.radians(90), 0, 0), fnt="anton")
SKY_TV = monitor("HimmelsTV", WX["hotdog"] + Vector((-6, 34, 6)), math.radians(-10), "news", size=7.0)

# Pepsi-Ozean
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
SURF = akte("Surfakte", (0, 0, 0), 0, col="#e7a0a8", label="AKTE 003\nPEPSI GRANDMA", scale=5.5)
RAFT = parts_mesh("Floss", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                            ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
RAFT_MON = monitor("FlossPC", (0, 0, 0), 0, "pepsi", parent=RAFT)
RAFT_MON["root"].location = (0.45, -0.2, 0.77)

# Akten-Kosmos
KW = empty("AktenKosmos", WX["kosmos"])
PLANET = prim("sphere", "Planet", (40, 110, -6), (60, 60, 60), m=noise_mat("Planetenhaut", "#ff7a3c", "#ffd166", scale=2.5, rough=0.7, bump=0.2, c2="#ff3fa4"),
              parent=KW, seg=64)
prim("torus", "Planetenring", (40, 110, -6), (130, 130, 30), rot=(math.radians(75), 0, 0.4), m=mat("Ring", "#ffe0b0", 0.6, emit="#ffd8a8", estr=0.4), parent=KW, seg=96)
ORBIT = []
for i in range(14):
    f = akte("KosmosAkte%02d" % i, (0, 0, 0), 0, label=AKTEN_TEXT[i % len(AKTEN_TEXT)], parent=KW, scale=7 + hsh(i) * 8)
    ORBIT.append(f)
SPACE_TVS = [monitor("AllTV%d" % i, WX["kosmos"] + Vector(((i - 1.5) * 9, 28 + hsh(i) * 10, (hsh(i * 3) - 0.5) * 8)), hsh(i) * 2,
                     ["spirale", "kosmos", "pixel", "vermisst"][i], size=3.0) for i in range(4)]
DESK_MM = parts_mesh("SchwebeTischMM", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                                        ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
DESK_MM_MON = monitor("SchwebePC", (0, 0, 0), 0, "news", parent=DESK_MM)
DESK_MM_MON["root"].location = (0, 0.15, 0.77)
DESK_MM_MON["root"].rotation_euler.z = math.pi        # zeigt zu Mino Man
DESK_CG = parts_mesh("SchwebeTischCG", [("b", (0, 0, 0.74), (1.6, 0.8, 0.05), 0), ("b", (-0.7, 0, 0.37), (0.06, 0.7, 0.74), 1),
                                        ("b", (0.7, 0, 0.37), (0.06, 0.7, 0.74), 1)], [DESK_M, LEG_M])
SPACE_PAPER = [prim("plane", "AllBlatt%02d" % i, (0, 0, 0), (0.6, 0.85, 1), m=PAPER_M, parent=KW) for i in range(40)]

# Riesen-Röhrenmonitor im Gang (Variante 3 springt hinein)
GATE = monitor("TorPC", (0, 9.0, 0), 0, "pepsi", size=1.7)
if VARIANT != 3:
    GATE["root"].location.z = -50

# Officer Munch steht im Gang und isst eine Akte (Variante 2)
MU["root"].location = (-0.6, 22.0, 0) if VARIANT == 2 else (0, 0, -50)
MU["root"].rotation_euler.z = math.radians(-160)


# ------------------------------------------------------------------ Ausdrücke Chicken Guy
EXPR = {
    #            open  wide  lid   brow  tilt  teeth tongue cheek
    "neutral":  (0.12, 1.0, 0.5, -0.1, 0.05, 0.4, 0.0, 0.2),
    "deadpan":  (0.12, 1.0, 0.5, -0.1, 0.05, 0.4, 0.0, 0.2),    # halb offene Lider, Lippen leicht auf, untere Zähne
    "schrei":   (1.15, 0.8, 0.97, -0.7, -0.1, 1.0, 0.6, 0.9),   # Augen zu Falten zugekniffen, hohes ovales Mundloch
    "ekstase":  (0.9, 0.65, 1.0, 0.8, -0.4, 0.7, 0.5, 0.5),     # Kopf zurück, Augen zu
    "grimasse": (0.45, 1.3, 0.75, -0.5, 0.15, 1.0, 0.0, 0.7),
    "boah":     (0.7, 0.75, 0.35, 0.8, 0.0, 0.5, 0.3, 0.2),
    "zwinker":  (0.25, 1.2, 0.5, 0.3, 0.2, 0.8, 0.0, 0.4),
}
# Ausdruck pro Schlag im Drop-Teil (zyklisch)
EXPR_SEQ = ["schrei", "schrei", "grimasse", "ekstase", "boah", "schrei", "deadpan", "ekstase"]


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


def apply_face(t):
    op, wide, lid, brow, tilt, teeth, tongue, cheek = expr_at(t)
    hit = pulse(t, 0.12, 1, DROP, NB)
    op = clamp(op + hit * 0.15 * (op > 0.3), 0, 1.15)
    m = CG
    kb = m["skull"].data.shape_keys.key_blocks
    kb["auf"].value = op
    kb["breit"].value = clamp(wide - 1.0, 0, 1.5)
    kb["rund"].value = clamp(1.0 - wide, 0, 1.0) * 1.5
    kb["zaehne"].value = teeth * 0.8
    kb["laecheln"].value = cheek * 0.5
    rz = HS_CG[2]
    m["jaw"].location.z = -op * 0.5 * rz * 0.85
    m["jaw"].location.y = -op * 0.08 * HS_CG[1]
    m["uteeth"].location.z = op * 0.1 * rz * 0.6 + teeth * 0.012
    m["uteeth"].scale = (1.0, 1.0, 0.6 + teeth * 0.6)
    m["cav"].scale = (0.24, 0.15, 0.06 + op * 0.22)
    m["cav"].location.z = -0.02 - op * 0.08
    m["tongue"].location = (0, -0.03 + tongue * 0.03, -0.01 + tongue * 0.015)
    blink = 1.0 if (t % 3.1) < 0.09 else 0.0
    for sx, e in m["eyes"].items():
        l = clamp(max(lid, blink * (lid < 0.9)))
        # Halbkugel-Lider: Achse nach hinten = offen, nach vorn = zu
        e["lids"][0].rotation_euler.x = lerp(1.4, -0.95, l)
        e["lids"][1].rotation_euler.x = lerp(-1.4, -0.35, l * 0.8)
        e["glanz"].scale = (0.01, 0.005, 0.01) if l < 0.7 else (0, 0, 0)
        cz = smooth((l - 0.75) / 0.2)      # Falten nur beim Zukneifen
        for cr in e["creases"]:
            cr.scale = (cz, cz, cz)
        b_ = brow + (0.25 if (sx > 0 and EXPR_SEQ[int(max(0, beat_of(t) - DROP)) % len(EXPR_SEQ)] == "zwinker") else 0)
        e["brow"].location.z = BROW_Z + b_ * 0.05
        e["brow"].rotation_euler.y = -sx * b_ * 0.2
        e["pupil"].location.x = math.sin(t * 2.3 + sx) * 0.01
    m["head"].rotation_euler.x = tilt



# ------------------------------------------------------------------ Animation pro Frame
def set_screen(s, on, static, flash=0.0, t=0.0):
    n = s["nodes"]
    n["on"].outputs[0].default_value = on
    n["static"].outputs[0].default_value = static
    n["flash"].outputs[0].default_value = flash
    n["w"].outputs[0].default_value = t * 40 + s["phase"] * 10
    vis = on > 0.2 and static < 0.6
    for c in s["content"]:
        c.hide_render = not vis
        c.hide_viewport = not vis



HIDE = Vector((0, 0, -80))
DANCE = True
CAM_OVERRIDE = None

# Weltordner für Variante 3: Akten ploppen über den Kabinenwänden auf
WF = []
if VARIANT == 3:
    WF_ROOT = empty("WeltAkten")
    for i, (k, lab, stp) in enumerate([("vulkan", "AKTE 017\nHOT-DOG-REGEN", "BEANTRAGT"), ("disco", "AKTE 001\nCHICKEN GUY", "TANZT"),
                                       ("auge", "AKTE 033\nANTRAG", "GEPRÜFT"), ("pepsi", "AKTE 003\nPEPSI GRANDMA", "WIEDERHOLT"),
                                       ("munch", "AKTE 002\nBEWEISE", "GEGESSEN"), ("all", "AKTE 009\nGOTT", "ABWESEND")]):
        WF.append(ui_folder("WeltAkte%d" % i, k, lab, stp, parent=WF_ROOT, col=["#e2c286", "#f0b8c4", "#bcd0f0"][i % 3]))


def world_matrix(ob):
    """Weltmatrix aus Ort/Drehung/Größe der Eltern-Kette (im Handler ist matrix_world noch vom letzten Bild)."""
    M = Matrix.Identity(4)
    while ob is not None:
        M = Matrix.LocRotScale(ob.location, ob.rotation_euler, ob.scale) @ M
        ob = ob.parent
    return M


def mon_front(s, d=0.15, dz=0.0):
    """Punkt vor der Mattscheibe eines Monitors (Weltkoordinaten), d = Abstand vor dem Glas."""
    M = world_matrix(s["root"])
    sc = s["screen"].location
    return M @ Vector((sc.x, sc.y + d, sc.z + dz))


def track(b, keys):
    """Kamerafahrt aus Schlüsseln (Schlag, Position, Ziel, Brennweite); gleicher Schlag zweimal = harter Schnitt."""
    for i in range(len(keys) - 1):
        b0, p0, t0, l0 = keys[i][:4]
        b1, p1, t1, l1 = keys[i + 1][:4]
        if b0 <= b < b1:
            e = keys[i + 1][4] if len(keys[i + 1]) > 4 else ease_inout
            k = e((b - b0) / (b1 - b0))
            return vlerp(resolve(p0), resolve(p1), k), vlerp(resolve(t0), resolve(t1), k), lerp(l0, l1, k)
    last = keys[-1]
    return Vector(resolve(last[1])), Vector(resolve(last[2])), last[3]


def lin(x):
    return clamp(x)


# ------------------------------------------------------------------ Posen
def place(root, pos, rz=None, s=None):
    root.location = pos
    if rz is not None:
        root.rotation_euler = (0, 0, rz)
    if s is not None:
        root.scale = (s, s, s)


def pose_mm(t, mode):
    b = beat_of(t)
    ph = t / BEAT * math.pi
    hit = pulse(t, 0.14, 1, 0, NB)
    legs, arms = MM["legs"], MM["arms"]
    MM["neck"].rotation_euler = (hit * 0.04, 0, 0)
    MM["glint"].scale = (0.022 * (1 + 2 * pulse(t, 0.25, 4, 0, NB)), 0.006, 0.012)
    if mode in ("sitzen", "schweben"):
        for sx, (hp, kn) in legs.items():
            hp.rotation_euler = (math.radians(88), 0, sx * 0.08)
            kn.rotation_euler = (math.radians(-88), 0, 0)
        for sx, (sh, el) in arms.items():
            tip = math.sin(t * 22 + sx * 1.7) * 0.06
            sh.rotation_euler = (math.radians(30) + tip, 0, sx * 0.1)
            el.rotation_euler = (math.radians(60) - tip, 0, 0)
        MM["neck"].rotation_euler = (0.12 + hit * 0.03, 0, math.sin(t * 0.8) * 0.05)
    elif mode == "tanzen":
        # Deadpan-Disco: abwechselnd ein Arm zeigt in den Himmel, Hüfte schwingt, Gesicht bleibt ernst
        up = int(b) % 2
        for sx, (sh, el) in arms.items():
            a = smooth(((b % 1) / 0.2)) if ((sx > 0) == (up == 1)) else 1 - smooth(((b % 1) / 0.2))
            sh.rotation_euler = (lerp(0.35, 2.95, a), 0, -sx * lerp(0.15, 0.35, a))
            el.rotation_euler = (lerp(1.2, 0.1, a), 0, 0)
        for sx, (hp, kn) in legs.items():
            st = max(0.0, math.sin(ph + (0 if sx > 0 else math.pi)))
            hp.rotation_euler = (st * 0.55, 0, sx * 0.06)
            kn.rotation_euler = (-st * 0.9, 0, 0)
        MM["neck"].rotation_euler = (hit * 0.12, 0, math.sin(ph * 0.5) * 0.12)
    elif mode == "surfen":
        for sx, (hp, kn) in legs.items():
            hp.rotation_euler = (0.35 * sx, sx * -0.35, 0)
            kn.rotation_euler = (-0.5, 0, 0)
        for sx, (sh, el) in arms.items():
            sh.rotation_euler = (0.2 + math.sin(t * 2 + sx) * 0.15, -sx * 1.35, 0)
            el.rotation_euler = (0.2, 0, 0)
        MM["neck"].rotation_euler = (0, 0, -0.6)        # schaut stoisch nach vorn, Körper seitlich
    if mode == "sitzen":
        MM["torso"].rotation_euler = (0, 0, 0)


def pose_cg(t, wild=1.0):
    b = beat_of(t)
    hit_drop = pulse(t, 0.16, 1, 0, NB)
    if not DANCE:
        wild = 0.0
    ph = t / BEAT * math.pi
    body = CG["body"]
    body.location.z = CG_BZ + abs(math.sin(ph)) * 0.14 * wild
    body.scale = (CG_BS[0] * (1 + hit_drop * 0.08 * wild), CG_BS[1] * (1 + hit_drop * 0.08 * wild), CG_BS[2] * (1 - hit_drop * 0.1 * wild))
    body.rotation_euler = (0, math.sin(ph) * 0.2 * wild, math.sin(ph * 0.5) * 0.35 * wild)
    for sx, (sh, el, tip) in CG["wings"].items():
        flap = math.sin(ph * 2 + (0 if sx > 0 else math.pi * 0.5))
        sh.rotation_euler = (0, -sx * (0.4 + flap * 0.9 * wild), sx * math.sin(ph) * 0.4 * wild)
        el.rotation_euler = (0, -sx * (0.6 + math.sin(ph * 2 + 1) * 0.9 * wild), 0)
        tip.rotation_euler = (0, -sx * math.sin(ph * 4) * 0.5 * wild, 0)
    for sx, hip in CG["legs"].items():
        hip.rotation_euler = (math.sin(ph + (0 if sx > 0 else math.pi)) * 0.55 * wild, 0, 0)
    CG["neck"].rotation_euler = (math.sin(ph * 2) * 0.12 * wild + hit_drop * 0.15 * wild, math.sin(ph) * 0.25 * wild, math.sin(ph * 0.5) * 0.25 * wild)
    apply_face(t)


def cg_head():
    s = CG["root"].scale.z
    return CG["root"].location + Vector((0, 0, 1.5 * s))


def mm_head(seated=False):
    s = MM["root"].scale.z
    return MM["root"].location + Vector((0, 0, (1.76 if not seated else 1.76) * s))


def pose_munch(t):
    bite = pulse(t, 0.12, 2, 0, NB)
    MU["fore"].rotation_euler = (math.radians(-95) - bite * 0.25, 0, math.radians(-25))
    MU["arm"].rotation_euler = (math.radians(-40), 0, math.radians(20))
    MU["jaw"].scale = (0.1, 0.03, 0.03 + bite * 0.05)
    MU["head"].rotation_euler = (0.15 * bite, 0, math.sin(t * 0.7) * 0.1)


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
            spin = (b * 0.5 + hsh(k)) * math.tau * 0.25 * (1 if k % 2 else -1)
            w["root"].rotation_euler.z = w["rz"] + spin
            for sx, (sh, el) in w["arms"].items():
                sh.rotation_euler = (2.8 + math.sin(t * 9 + sx + k) * 0.25, 0, -sx * 0.3)
                el.rotation_euler = (0.3, 0, 0)
            w["head"].rotation_euler = (hit * 0.2, 0, math.sin(t * 3 + k) * 0.3)
        else:
            w["root"].rotation_euler.z = w["rz"]
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


# ------------------------------------------------------------------ Welten
def world_hotdog(t, b, cam):
    c = WX["hotdog"]
    for i, o in enumerate(HD_RAIN):
        ph = (t * (0.18 + hsh(i) * 0.1) + hsh(i * 3)) % 1.0
        o.location = (cam.x - c.x + (hsh(i * 7) - 0.5) * 50, cam.y - c.y + 5 + hsh(i * 11) * 45, 32 - ph * 38)
        if (Vector(o.location) + c - cam).length < 4.0:
            o.location = HIDE
        o.rotation_euler = (t * (1 + hsh(i)) + i, t * 0.7 + i * 2, i)
    HOT_SIGN.location.z = 14 + math.sin(t * 2) * 0.5


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


def world_kosmos(t, b):
    PLANET.rotation_euler.z = t * 0.05
    ctr = Vector((0, 22, 2))
    for i, f in enumerate(ORBIT):
        a = t * (0.15 + hsh(i) * 0.15) + i * math.tau / len(ORBIT)
        r_ = 12 + hsh(i * 3) * 14
        f.location = ctr + Vector((math.cos(a) * r_, math.sin(a) * r_ * 0.6 + 8, math.sin(a * 2 + i) * 5))
        f.rotation_euler = (t * 0.3 + i, t * 0.2, a)
    for i, p in enumerate(SPACE_PAPER):
        p.location = Vector(((hsh(i * 2.1) - .5) * 30, 8 + hsh(i * 3.3) * 30, (hsh(i * 5.7) - .5) * 14 + math.sin(t + i) * 0.8))
        p.rotation_euler = (t * (0.5 + hsh(i)) + i, t * 0.3 + i, i)
    for i, s in enumerate(SPACE_TVS):
        s["root"].rotation_euler.x = math.sin(t * 0.7 + i) * 0.15


# ------------------------------------------------------------------ UI-Ablauf
def ui_run(t, b, events, folders):
    used = set()
    for ev in events:
        F = folders[ev["f"]]
        b0, bo, b1 = ev["b0"], ev.get("bo", ev["b0"] + 0.5), ev["b1"]
        if not (b0 <= b < b1 + 0.45):
            continue
        used.add(ev["f"])
        k = ease_back((b - b0) / 0.45)
        out = smooth((b - b1) / 0.4)
        s = ev.get("s", 0.55) * k * (1 - out)
        if "grow" in ev:      # Akte wächst über das Bild (Eintauchen)
            g = ease_inout((b - ev["grow"][0]) / (ev["grow"][1] - ev["grow"][0]))
            s = lerp(s, ev["grow"][2], g)
        pos = Vector(ev["pos"])
        if "grow" in ev:
            pos = pos * (1 - g)
        if ev.get("world"):
            F["root"].location = pos + Vector((0, 0, -out * 1.0))
            F["root"].rotation_euler = (math.radians(90), 0, ev.get("r", 0.0) + (1 - k) * 0.3)
        else:
            F["root"].location = (pos.x, pos.y - out * 0.4, ev.get("z", 0.0))
            F["root"].rotation_euler = (0, 0, ev.get("r", 0.0) + (1 - k) * 0.25)
        F["root"].scale = (s, s, s)
        ok = ease_out((b - bo) / 0.6) if b >= bo else 0.0
        F["hinge"].rotation_euler.y = -math.radians(168) * ok
        F["anim"](t, b - bo, ok)
    for i, F in enumerate(folders):
        if i not in used:
            F["root"].scale = (0, 0, 0)


def dialog_run(b, D, b0, b1, click=None, s=0.8):
    if not (b0 <= b < b1 + 0.3):
        D["root"].scale = (0, 0, 0)
        return
    k = ease_back((b - b0) / 0.35) * (1 - smooth((b - b1) / 0.3))
    D["root"].scale = (s * k, s * k, s * k)
    for j, btn in enumerate(D["btns"]):
        pressed = click is not None and click[0] == j and click[1] <= b < click[1] + 0.25
        btn.location.z = 0.002 if pressed else 0.008
        btn.scale = (0.94, 0.94, 1) if pressed else (1, 1, 1)


def cursor_run(b, keys, b0, b1):
    if not (b0 <= b < b1):
        CURSOR.scale = (0, 0, 0)
        return
    CURSOR.scale = (0.8, 0.8, 0.8)
    for i in range(len(keys) - 1):
        if keys[i][0] <= b < keys[i + 1][0]:
            k = ease_inout((b - keys[i][0]) / (keys[i + 1][0] - keys[i][0]))
            p = Vector(keys[i][1]).lerp(Vector(keys[i + 1][1]), k)
            CURSOR.location = (p.x, p.y, 0.36)
            return
    p = keys[-1][1]
    CURSOR.location = (p[0], p[1], 0.36)


def flash_run(t, b, dives, end_snow=None):
    a, snow = 0.0, 0.0
    for bd, kind in dives:
        if bd - 0.5 <= b < bd:
            a = max(a, smooth((b - (bd - 0.5)) / 0.5))
            snow = 1.0 if kind == "schnee" else 0.0
        elif bd <= b < bd + 0.7:
            a = max(a, 1 - smooth((b - bd) / 0.7))
            snow = 0.0
    if end_snow is not None and b >= end_snow:
        a = max(a, smooth((b - end_snow) / 0.6))
        snow = 1.0
    FLASH_N["alpha"].outputs[0].default_value = a
    FLASH_N["schnee"].outputs[0].default_value = snow
    FLASH_N["w"].outputs[0].default_value = t * 40
    FLASH.scale = (1.5, 2.4, 1) if a > 0.001 else (0, 0, 0)


def set_world(name):
    set_sky(name)


def ovl_update():
    k = OVL_D * 18.0 / cam_data.lens
    OVL.scale = (k, k, k)


# ------------------------------------------------------------------ Drei Abläufe
D_MM = MM_DESK
C_MM = D_MM["cell"]
MM_SEAT = seat_pos(D_MM, -0.29)
MM_SEAT_RZ = C_MM[2] + math.pi


def v1(t, b):
    """Großraum: Luftbild -> Mino Man tippt -> AKTE.EXE -> Akten-Kaskade -> in seinen Bildschirm -> Hot-Dog-Himmel -> Party -> Luftbild."""
    hot = 16 <= b < 30
    set_world("hotdog" if hot else "buero")
    office(t, b, party=1.0 if b >= 30 else 0.0, beat_change=b >= 30)
    mon = D_MM["mon"]
    # Figuren
    if b < 16:
        place(MM["root"], MM_SEAT, MM_SEAT_RZ, 1.0)
        pose_mm(t, "sitzen")
        place(CG["root"], Vector((math.sin(t * 1.3) * 0.4 - 0.2, 3.0 + math.sin(t * 0.7) * 1.2, 0)), math.pi * 0.5 + math.sin(t) * 0.6, CG_S)
        pose_cg(t, 0.5 if b < 12 else 1.0)
    elif hot:
        place(MM["root"], HIDE)
        place(CG["root"], WX["hotdog"] + Vector((0, 20, -1.2)), math.pi + 0.3 * math.sin(t * 0.5), 4.2)
        pose_cg(t, 1.0)
    else:
        place(MM["root"], Vector((0.55, 5.4, 0)), math.pi + math.sin(t * 1.1) * 0.3, 1.0)
        pose_mm(t, "tanzen")
        place(CG["root"], Vector((-0.55, 6.6, 0)), math.pi + math.sin(t * 0.9) * 0.5, CG_S)
        pose_cg(t, 1.0)
    if hot:
        cam_now = CAM.location.copy()
        world_hotdog(t, b, cam_now)
    flyers(t, b, 30, Vector((0, 8, 0)), b >= 30)
    # UI
    DLG_OPEN["root"].location.y = 0.5
    dialog_run(b, DLG_OPEN, 8.0, 9.5, click=(0, 9.15))
    cursor_run(b, [(8.3, (0.42, -0.3)), (9.0, (-0.11, 0.34)), (9.6, (-0.11, 0.34))], 8.3, 9.6)
    ev = [dict(f=0, b0=10.0, b1=13.8, pos=(-0.16, 0.66), s=0.5), dict(f=1, b0=10.5, b1=13.85, pos=(0.14, 0.55), z=0.02, s=0.5),
          dict(f=2, b0=11.0, b1=13.9, pos=(-0.12, 0.38), z=0.04, s=0.5), dict(f=3, b0=11.5, b1=13.95, pos=(0.15, 0.25), z=0.06, s=0.5),
          dict(f=6, b0=12.0, b1=14.0, pos=(-0.05, 0.08), z=0.08, s=0.5)]
    ev += [dict(f=f, b0=36 + 0.5 * i, b1=40.6, pos=(-0.15 + 0.06 * i, 0.5 - 0.19 * i), z=0.02 * i) for i, f in enumerate((4, 5, 7, 8, 1, 6))]
    ui_run(t, b, ev, FOLDERS)
    dialog_run(b, DLG_END, 45.0, 49, click=(0, 46.8))
    cursor_run(b, [(45.3, (0.3, -0.6)), (46.5, (0.0, -0.16)), (48, (0.0, -0.16))], 45.3, 48.0)
    flash_run(t, b, [(16, "schnee"), (30, "schnee")], end_snow=47.4)
    # Kamera
    mh = cw(C_MM, (0, -0.12, 1.45))
    keys = [
        (0, (14, -30, 34), (1, 16, 0), 24),
        (6, (5, -6, 9), (2.5, 5, 1.2), 26),
        (6, cw(C_MM, (1.05, -1.3, 1.5)), mh + Vector((0, 0, 0.32)), 28),
        (14, cw(C_MM, (0.8, -1.2, 1.45)), mh + Vector((0, 0, 0.3)), 32),
        (14, cw(C_MM, (0.5, 0.9, 1.6)), mon_front(mon, 0.0), 30),
        (16, mon_front(mon, 0.15), mon_front(mon, 0.0), 30, lambda x: x * x),
        (16, WX["hotdog"] + Vector((-10, 8, 2)), WX["hotdog"] + Vector((0, 20, 5)), 26),
        (20, WX["hotdog"] + Vector((8, 7, 3)), WX["hotdog"] + Vector((0, 20, 6)), 28, smooth),
        (24, WX["hotdog"] + Vector((4, 12, 6)), WX["hotdog"] + Vector((0, 20, 6.5)), 32, smooth),
        (28, WX["hotdog"] + Vector((-3, 16, 7.5)), mon_front(SKY_TV, 0.0), 30),
        (30, mon_front(SKY_TV, 2.2), mon_front(SKY_TV, 0.0), 30, lambda x: x * x),
        (30, mon_front(mon, 0.12), mon_front(mon, 0.0), 30),
        (34, (-0.7, -1.5, 2.3), (0.6, 6.5, 1.1), 26, ease_out),
        (40, (-0.4, -5.0, 2.7), (0.4, 6.5, 1.0), 28),
        (47, (12, -36, 30), (0, 22, 0), 24),
        (48, (12.5, -37, 31), (0, 22, 0), 24),
    ]
    return keys


V2_ICON = None


def v2(t, b):
    """Aktenflut: wir sitzen am PC -> Doppelklick AKTE.EXE -> zehn Akten ploppen auf -> in die letzte hinein -> Akten-Kosmos -> zurück -> Officer Munch isst."""
    kos = 16 <= b < 32
    set_world("kosmos" if kos else "buero")
    office(t, b, party=1.0 if b >= 32 else 0.0, beat_change=b >= 32)
    pm = POV_DESK["mon"]
    # Maus auf dem Bildschirm (vor dem Doppelklick)
    cur = pm.get("cursor")
    if cur is not None:
        sc = pm["screen"].location
        W, H = pm["w"], pm["h"]
        k = ease_inout(b / 2.2)
        cur.location = (sc.x + lerp(-0.25, 0.3, k) * W, 0.05, sc.z + lerp(-0.25, 0.3, k) * H)
        cur.scale = (W * 0.06, W * 0.06, W * 0.09) if b < 3.5 else (0, 0, 0)
    if kos:
        c = WX["kosmos"]
        bob = math.sin(t * 0.8) * 0.3
        DESK_MM.location = c + Vector((0, 18, 2 + bob))
        DESK_MM.rotation_euler = (0, 0, math.sin(t * 0.3) * 0.2)
        place(MM["root"], c + Vector((0, 17.25, 2 + bob - 0.32)), math.sin(t * 0.3) * 0.2, 1.0)
        pose_mm(t, "schweben")
        DESK_CG.location = c + Vector((6, 24, 4 + math.cos(t * 0.7) * 0.4))
        DESK_CG.rotation_euler = (0, 0, t * 0.15)
        place(CG["root"], DESK_CG.location + Vector((0, 0, 0.77)), math.pi + math.sin(t * 0.8) * 0.4, CG_S)
        pose_cg(t, 1.0)
        world_kosmos(t, b)
    else:
        if b < 16:
            place(MM["root"], MM_SEAT, MM_SEAT_RZ, 1.0)
            pose_mm(t, "sitzen")
            place(CG["root"], HIDE)
        else:
            place(MM["root"], Vector((0.5, 28.0, 0)), math.pi + math.sin(t) * 0.3, 1.0)
            pose_mm(t, "tanzen")
            place(CG["root"], Vector((-0.4, 25.5 + math.sin(t * 0.8) * 0.8, 0)), math.pi + math.sin(t * 0.9) * 0.6, CG_S)
            pose_cg(t, 1.0)
        pose_munch(t)
    flyers(t, b, 32, Vector((0, 22, 0)), b >= 32)
    # UI: Dialog, Maus, Akten-Kaskade, in Akte 9 hinein
    dialog_run(b, DLG_OPEN, 3.0, 5.3, click=(0, 4.9))
    cursor_run(b, [(3.2, (0.4, -0.75)), (4.7, (-0.11, -0.16)), (5.4, (-0.11, -0.16))], 3.2, 5.4)
    times = [5.5, 6.25, 7.0, 7.75, 8.25, 8.75, 9.25, 9.75, 10.0, 10.25]
    order = [0, 1, 2, 3, 4, 5, 6, 8, 7, 9]
    ev = []
    for i, (bt, f) in enumerate(zip(times, order)):
        x = (-0.18 + 0.07 * (i % 6)) * (1 if i % 2 == 0 else -1) * 0.8
        y = 0.55 - 0.12 * i
        e = dict(f=f, b0=bt, b1=14.4 if f != 9 else 16.2, pos=(x, y), z=0.02 * i)
        if f == 9:
            e.update(pos=(0.0, -0.1), grow=(14.0, 16.0, 3.4), z=0.25)
        ev.append(e)
    ev += [dict(f=3, b0=38.0, b1=42.0, pos=(-0.08, 0.3), s=0.6), dict(f=5, b0=38.75, b1=42.0, pos=(0.08, -0.05), z=0.03, s=0.6)]
    ui_run(t, b, ev, FOLDERS)
    dialog_run(b, DLG_END, 44.5, 49, click=(0, 46.5))
    cursor_run(b, [(44.8, (0.35, -0.65)), (46.3, (0.0, -0.16)), (48, (0.0, -0.16))], 44.8, 48)
    flash_run(t, b, [(16, "weiss"), (32, "schnee")], end_snow=47.4)
    # Kamera
    P = POV_DESK["cell"]
    L = HERO[(-1, 0, 0, 1, 1)]["mon"]
    kc = WX["kosmos"]
    keys = [
        (0, cw(P, (0, 0.1, 1.3)), mon_front(pm, 0.0), 34),
        (5.5, cw(P, (0, -0.28, 1.18)), mon_front(pm, 0.0), 34),
        (14.5, cw(P, (1.6, 0.9, 2.6)), cw(P, (-0.5, -1.0, 0.9)), 30),
        (16, cw(P, (1.65, 0.95, 2.65)), cw(P, (-0.5, -1.0, 0.9)), 30),
        (16, kc + Vector((-6, 7, 5)), kc + Vector((2, 20, 2.8)), 24),
        (20, kc + Vector((-2.5, 12, 4)), kc + Vector((1.5, 19.5, 3)), 26),
        (20, kc + Vector((0.7, 19.8, 3.75)), kc + Vector((0, 17.25, 3.25)), 34),
        (24, kc + Vector((-0.6, 19.6, 3.6)), kc + Vector((0, 17.25, 3.25)), 38),
        (24, lambda: DESK_CG.location + Vector((1.4, -2.6, 2.2)), lambda: cg_head(), 34),
        (28, lambda: DESK_CG.location + Vector((-1.6, -2.4, 1.6)), lambda: cg_head(), 38),
        (29, kc + Vector((-6, 10, 4)), mon_front(SPACE_TVS[1], 0.0), 28),
        (32, mon_front(SPACE_TVS[1], 2.0), mon_front(SPACE_TVS[1], 0.0), 30, lambda x: x * x),
        (32, mon_front(L, 0.12), mon_front(L, 0.0), 30),
        (34, (0.4, 16.5, 1.75), (0.2, 24, 1.3), 28, ease_out),
        (43, (0.3, 22.0, 1.9), (0.0, 30, 1.2), 28),
        (47.5, (-6, 6, 22), (0, 40, 0), 24),
        (48, (-6.2, 5.6, 22.5), (0, 40, 0), 24),
    ]
    return keys


GATE_FRONT = mon_front(GATE, 0.0)


def v3(t, b):
    """Wandertag: Chicken Guy tanzt durch die Gänge, Akten ploppen über den Kabinen auf, er springt in einen Riesen-PC -> Pepsi-Ozean -> zurück -> Luftbild in die Sonne."""
    sea = 16 <= b < 32
    set_world("pepsi" if sea else "buero")
    office(t, b, party=1.0 if b >= 32 else 0.0, beat_change=b >= 32)
    if b < 16:
        y = lerp(30.0, 11.5, smooth(b / 14.0) * 0.4 + 0.6 * clamp(b / 14.0))
        cgp = Vector((math.sin(t * 2.2) * 0.35, y, 0))
        s = CG_S
        if b >= 14.0:      # Sprung in den Bildschirm
            k = smooth((b - 14.0) / 1.2)
            cgp = vlerp(cgp, GATE_FRONT + Vector((0, -0.3, -0.5)), k) + Vector((0, 0, math.sin(k * math.pi) * 1.0))
            s = CG_S * (1 - 0.85 * k)
        place(CG["root"], cgp, math.pi + math.sin(t * 1.5) * 0.4, s)
        pose_cg(t, 0.7 if b < 8 else 1.0)
        place(MM["root"], Vector((0.6 + math.sin(t * 1.7) * 0.2, y + 1.9, 0)), math.pi + math.sin(t) * 0.25, 1.0)
        pose_mm(t, "tanzen")
    elif sea:
        c = WX["pepsi"]
        wv = math.sin(t * 1.5) * 0.4
        sp = c + Vector((math.sin(t * 0.5) * 3, 6 + (b - 16) * 1.3, 0.1 + wv))
        SURF.location = sp
        SURF.rotation_euler = (math.sin(t * 1.3) * 0.08, math.sin(t * 1.1) * 0.1, math.radians(90))
        place(MM["root"], sp + Vector((0, 0, 0.12)), math.radians(90) + 0.0, 1.0)
        pose_mm(t, "surfen")
        RAFT.location = c + Vector((6, 30, 0.2 + math.sin(t * 1.4 + 1) * 0.4))
        RAFT.rotation_euler = (math.sin(t * 1.2) * 0.06, math.sin(t) * 0.06, math.radians(180))
        place(CG["root"], RAFT.location + Vector((0.3, 0, 0.77)), math.pi, CG_S)
        pose_cg(t, 1.0)
        world_pepsi(t, b)
    else:
        k = ease_out((b - 32) / 1.0)
        place(CG["root"], vlerp(GATE_FRONT + Vector((0, 0.2, -0.4)), Vector((-0.55, 6.6, 0)), k) + Vector((0, 0, math.sin(k * math.pi) * 0.8)),
              math.pi + math.sin(t * 0.9) * 0.5, CG_S * (0.2 + 0.8 * k))
        pose_cg(t, 1.0)
        k2 = ease_out((b - 32.5) / 1.0)
        place(MM["root"], vlerp(GATE_FRONT + Vector((0, 0.2, -0.4)), Vector((0.6, 6.2, 0)), k2) + Vector((0, 0, math.sin(k2 * math.pi) * 0.6)),
              math.pi + math.sin(t * 1.1) * 0.3, 0.2 + 0.8 * k2)
        pose_mm(t, "tanzen")
    flyers(t, b, 33, Vector((0, 6, 0)), b >= 33)
    # Akten ploppen über den Kabinenwänden auf
    wev = []
    for i in range(len(WF)):
        sx = -1 if i % 2 == 0 else 1
        yy = 24.0 - i * 2.4
        wev.append(dict(f=i, b0=7.5 + i * 0.75, b1=14.5, pos=(sx * 2.3, yy, 2.25), world=True, r=-sx * 0.35, s=1.7))
    ui_run(t, b, wev, WF)
    ev = [dict(f=4, b0=24.0, b1=28.0, pos=(-0.1, 0.35)), dict(f=6, b0=24.5, b1=28.0, pos=(0.1, 0.1), z=0.03)]
    ui_run(t, b, ev, FOLDERS)
    dialog_run(b, DLG_END, 45.0, 49, click=(0, 46.8))
    cursor_run(b, [(45.3, (0.3, -0.6)), (46.5, (0.0, -0.16)), (48, (0.0, -0.16))], 45.3, 48)
    flash_run(t, b, [(16, "schnee"), (32, "weiss")], end_snow=47.4)
    c = WX["pepsi"]
    rm = RAFT_MON
    keys = [
        (0, lambda: CG["root"].location + Vector((0.4, -3.0, 1.0)), lambda: CG["root"].location + Vector((0, 0, 1.0)), 28),
        (8, lambda: CG["root"].location + Vector((0.6, -3.6, 1.4)), lambda: CG["root"].location + Vector((0, 1.0, 1.2)), 26),
        (12, lambda: CG["root"].location + Vector((0.2, -5.5, 2.8)), lambda: CG["root"].location + Vector((0, 2.5, 1.4)), 24),
        (13.5, (0.5, 14.5, 1.6), GATE_FRONT, 28),
        (16, GATE_FRONT + Vector((0, 0.15, 0)), GATE_FRONT, 30, lambda x: x * x),
        (16, lambda: MM["root"].location + Vector((4.5, -3.0, 1.6)), lambda: MM["root"].location + Vector((0, 0, 1.2)), 28),
        (22, lambda: MM["root"].location + Vector((3.5, 2.5, 1.8)), lambda: MM["root"].location + Vector((0, 0, 1.3)), 30),
        (22, lambda: RAFT.location + Vector((1.5, -3.2, 2.3)), lambda: cg_head(), 32),
        (26, lambda: RAFT.location + Vector((-1.8, -2.8, 1.7)), lambda: cg_head(), 36),
        (26, c + Vector((-20, 6, 9)), c + Vector((0, 30, 2)), 24),
        (29.5, c + Vector((-10, 16, 5)), c + Vector((4, 30, 1.5)), 26),
        (30, lambda: mon_front(rm, 3.0), lambda: mon_front(rm, 0.0), 30),
        (32, lambda: mon_front(rm, 0.15), lambda: mon_front(rm, 0.0), 30, lambda x: x * x),
        (32, GATE_FRONT + Vector((0, 0.2, 0)), GATE_FRONT, 30),
        (35, (0.6, 2.8, 1.5), (0, 8.5, 1.1), 28, ease_out),
        (43, (1.6, -5.5, 4.0), (0, 7.5, 1.0), 26),
        (43, (2.0, 30.0, 4.0), (2.0 + 0.45 * 20, 30.0 - 0.62 * 20, 4.0 + 0.2 * 20), 22),
        (48, (3.0, 36.0, 16.0), (3.0 + 0.45 * 20, 36.0 - 0.62 * 20, 16.0 + 0.1 * 20), 22),
    ]
    return keys


STORY = {1: v1, 2: v2, 3: v3}[VARIANT]
PORTRAIT = bool(opt("--portrait"))


def animate(t):
    b = beat_of(t)
    keys = STORY(t, b)
    if PORTRAIT:      # Figurenbogen: beide frei auf den Teppich stellen, Blick nach +Y
        place(CG["root"], Vector((0, -3, 0)), math.pi, 1.0)
        place(MM["root"], Vector((2.5, -3, 0)), math.pi, 1.0)
        pose_mm(t, "tanzen")
        MU["root"].location = (-2.5, -3, 0)
        MU["root"].rotation_euler.z = math.pi
        GATE["root"].location.z = -50
        FLASH.scale = (0, 0, 0)
        for f in FOLDERS:
            f["root"].scale = (0, 0, 0)
    if CAM_OVERRIDE:
        CAM_OVERRIDE()
    else:
        p, tg, lens = track(b, keys)
        shake = 0.015 * pulse(t, 0.12, 1, DROP, NB) * (1 if b >= DROP else 0)
        look(p + Vector((math.sin(t * 61) * shake, 0, math.cos(t * 47) * shake)), tg, 0.0, lens)
    ovl_update()


def on_frame(scene, depsgraph=None):
    t = (scene.frame_current - 1) / FPS
    animate(t)



bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)


def build_far_grid():
    """Erst ganz am Ende anlegen: bpy.ops-Aufrufe werden mit Tausenden Objekten in der Szene sehr langsam."""
    GRID_C = Vector((0, 18, 0))
    n_far = 0
    for s_ in (-1, 1):
        for bx_ in range(14):
            for c_ in (0, 1):
                for by_ in range(-8, 10):
                    for jc_ in range(4):
                        key = (s_, bx_, c_, by_, jc_)
                        if key in HERO_CELLS:
                            continue
                        x, y, rz = cell_pos(*key)
                        if (Vector((x, y, 0)) - GRID_C).length > 118:
                            continue
                        instance("K%d_%d_%d_%d_%d" % (s_ + 1, bx_, c_, by_ + 8, jc_), KAB_FERN, (x, y, 0), (0, 0, rz))
                        if hsh(x * 0.37 + y * 1.3) < 0.5:
                            instance("M%d_%d_%d_%d_%d" % (s_ + 1, bx_, c_, by_ + 8, jc_), WORKER, (x, y, 0), (0, 0, rz))
                        n_far += 1
    print("Kabinen in der Ferne:", n_far)


build_far_grid()
apply_haze()
set_sky("buero")


def no_shadow(ob):
    if hasattr(ob, "visible_shadow"):
        ob.visible_shadow = False
    for ch in ob.children:
        no_shadow(ch)


no_shadow(OVL)
for f in WF:
    no_shadow(f["root"])

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
scn.view_settings.exposure = float(opt("--exposure", 0.0))

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
    ng.links.new(glare.outputs["Image"], out_in)


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

out = opt("--out", os.path.join(HERE, "out", "mino_buero_v%d.mp4" % VARIANT))
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
            hd = CG["head"].matrix_world.translation + Vector((0, 0, 0.3))
            cam_args = (hd + Vector((-0.2, -1.5, 0.05)), hd, 0.0, 60)
        elif who == "cgauge":   # Detail: rechtes Auge
            hd = CG["eyes"][1]["c"].matrix_world.translation.copy()
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

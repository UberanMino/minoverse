"""MINO HEAVEN – Runde 7 der Blender-Reels für den Minoverse: Blöcke aus je sechs Screens hängen am Himmel, zeigen auf
allen Seiten denselben Clip, drehen sich im Takt und ordnen sich zu Formationen (Reihe, Bogen, Kreuz, Ring, Turm, Mosaik).
Mino Man legt an einem Altar-DJ-Pult auf, die Gemeinde tanzt und betet ekstatisch an. Kein Büro mehr: Kirche und Himmel.

Varianten (--variant oder "variant" in den Params):
  1 KATHEDRALE    Säulenhalle auf Wolken, Orgel aus Gold, die Blöcke werden ein Kreuz und am Ende ein Chicken-Guy-Mosaik
  2 SPIEGELHIMMEL Spiegelboden im Goldlicht, schwebendes Pult, Ring aus Blöcken, Helix, Mosaik, Heiligenschein
  3 ROSENFENSTER  Dämmerung, leuchtendes Rosenfenster, die Blöcke sind seine Blütenblätter und fliegen auf dem Drop los
  4 HIMMELSTREPPE Treppe zum goldenen Tor, oben legt Mino Man auf, die Blöcke säumen die Treppe
  5 LICHTMESSE    Nacht und Kerzen, die Blöcke setzen sich zu einem Block-Gott zusammen, der die Arme hebt

  blender -b --factory-startup --python mino_heaven_reel.py -- --params params_heaven_v1.json --clips <abs>/clips --cghead <abs>/cghead --fast --pngdir out/heaven_v1
  Optionen wie mino_office_reel.py (--still, --frames, --res, --engine, --samples, --nocomp)
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

PAPER_M = mat("Papier", "#f1ece0", 0.85)
MANILA_M = mat("Akte_manila", "#d9b77a", 0.8)
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

WX = {"fabrik": Vector((5000, 0, 0)), "pepsi": Vector((-5000, 0, 0)), "orbit": Vector((0, 5000, 0))}
SKIES.update({
    "orbit":  ("#10245e", "#040a26", "#000003", 1.5, 1.0, 140, 1100, 3.4, "#ffffff"),
    "fabrik": ("#3a1f0e", "#1c0f07", "#070403", 0.0, 0.0, 7, 62, 0.35, "#ffb070"),
})
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




def set_world(name):
    set_sky(name)


DANCE = True
CAM_OVERRIDE = None
# Kutten statt Hemden, goldene Stolen statt Krawatten
SHIRTS = ["#f6f2ea", "#fff8e6", "#f2e2b0", "#e6eef8", "#f4dce4"]
PANTS_M = mat("KutteUnten", "#ece6da", 0.85)
HAIR_W = mat("HaarDunkel", "#2a2018", 0.8)


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
TIE_COLS = ["#d4a017", "#c4002a", "#d4a017", "#7a1fa2"]


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




# ================================================================== Runde 7: HEAVEN – Blöcke aus Screens, Mino Man legt auf
# Raphael zu Runde 6: hängende Screens, die sich im Beat neu ordnen, sind der Stil. Jetzt Blöcke aus je 6 Screens, die alle
# denselben Clip synchron zeigen; die Blöcke drehen sich in der Luft, reagieren auf die Musik und ordnen sich im Takt um.
# Mino Man legt auf, alle anderen tanzen und beten ekstatisch an. Kein Büro mehr, sondern Kult: Kirche, Himmel.
SKIES.update({
    "himmel":  ("#fff3df", "#cfe6ff", "#5b9ae6", 1.2, 0.0, 45, 330, 3.0, "#fff2d6"),
    "gold":    ("#ffe0a6", "#ffb88a", "#8a6ad0", 1.6, 0.0, 45, 320, 2.8, "#ffcf8a"),
    "daemmer": ("#ffb8d8", "#7a6ad8", "#141048", 0.7, 0.6, 35, 280, 1.3, "#ffc8e8"),
    "nacht":   ("#3a2a6a", "#140e38", "#020110", 0.0, 1.0, 30, 240, 0.3, "#b8a8ff"),
})
SKY_OF = {1: "himmel", 2: "gold", 3: "daemmer", 4: "himmel", 5: "nacht"}
O = Vector((0, 0, 0))

# ------------------------------------------------------------------ Materialien des Himmels
MARBLE = noise_mat("Marmor", "#f6f3ec", "#dcd5ca", scale=1.6, rough=0.3, bump=0.04)
GOLD = mat("Gold", "#e8b84a", 0.28, metal=1.0)
CLOUD_FLOOR = noise_mat("Wolkenboden", "#ffffff", "#e3e9f4", scale=0.06, rough=0.95, bump=0.6, sss=0.3)
MIRROR = mat("Spiegelboden", "#f2f4ff", 0.03, metal=1.0)
PUFF = mat("Wolke", "#ffffff", 0.9, sss=0.4, emit="#ffffff", estr=0.12 if VARIANT != 5 else 0.02)
BLOCK_BEZEL = mat("Blockrahmen", "#f4f0e8", 0.3, coat=0.5)
DECK_M = mat("DeckSchwarz", "#141418", 0.35)

FLOOR = prim("plane", "Boden", (0, 0, 0), (5000, 5000, 1), m=MIRROR if VARIANT == 2 else CLOUD_FLOOR)

# ------------------------------------------------------------------ Wolken bis zum Horizont
CLOUD_PROTOS = []
for c_ in range(4):
    pc = proto_collection("WolkeVorlage%d" % c_)
    parts = []
    for j in range(9):
        s_ = 0.8 + hsh(c_ * 13 + j * 2.7) * 1.1
        parts.append(("s", ((hsh(c_ * 7 + j * 1.3) - 0.5) * 3.4, (hsh(c_ * 3 + j * 4.1) - 0.5) * 1.4, hsh(c_ * 5 + j * 2.2) * 0.7),
                      (s_, s_ * 0.85, s_ * 0.7), 0))
    pc.objects.link(parts_mesh("WolkeMesh%d" % c_, parts, [PUFF], link_=False))
    CLOUD_PROTOS.append(pc)
for i_ in range(70):
    a_ = hsh(i_ * 2.3) * math.tau
    r_ = 45 + hsh(i_ * 5.9) ** 0.7 * 170
    instance("Wolke%02d" % i_, CLOUD_PROTOS[i_ % 4], (math.cos(a_) * r_, math.sin(a_) * r_, -1.0 + hsh(i_ * 1.7) * 2.0),
             (0, 0, a_), 3.0 + hsh(i_ * 3.1) * 7.0)
SKY_CLOUDS = []
for i_ in range(10):       # ein paar große Wolken hoch am Himmel
    SKY_CLOUDS.append(instance("HimmelWolke%d" % i_, CLOUD_PROTOS[i_ % 4],
                               ((hsh(i_ * 9.1) - 0.5) * 160, 60 + hsh(i_ * 4.4) * 140, 30 + hsh(i_ * 2.6) * 40),
                               (0, 0, hsh(i_) * 3), 8 + hsh(i_ * 7.2) * 8))

# ------------------------------------------------------------------ Tauben (weiß, kreisen über allem)
DOVE = proto_collection("TaubeWeiss")
_dw = mat("TaubeWeiss", "#fbfaf6", 0.6, emit="#ffffff", estr=0.1)
DOVE.objects.link(parts_mesh("TaubeWeissMesh", [("s", (0, 0, 0), (0.18, 0.4, 0.18), 0), ("s", (0, 0.22, 0.08), (0.12, 0.13, 0.12), 0),
                                               ("b", (-0.36, 0, 0.03), (0.6, 0.22, 0.02), 0), ("b", (0.36, 0, 0.03), (0.6, 0.22, 0.02), 0),
                                               ("b", (0, -0.3, 0), (0.16, 0.24, 0.02), 0)], [_dw], link_=False))
DOVES = [instance("Taube%02d" % i_, DOVE, HIDE, (0, 0, 0), 1.0) for i_ in range(16)]


def doves_run(t, b, C, r0=14.0, z0=16.0):
    for i, o in enumerate(DOVES):
        a = t * (0.35 + 0.1 * hsh(i)) * (1 if i % 2 else -1) + i * 0.7
        r = r0 + hsh(i * 3.3) * 8
        o.location = C + Vector((math.cos(a) * r, math.sin(a) * r, z0 + hsh(i * 5.1) * 8 + math.sin(t * 2 + i) * 0.6))
        flap = math.sin(t * 14 + i) * 0.4
        o.rotation_euler = (0, flap * 0.3, a + (math.pi if i % 2 else 0.0))


# ------------------------------------------------------------------ Bauten: Säulen, Orgel, Rosenfenster, Treppe, Tor, Kerzen
COLUMN = proto_collection("Saeule")
COLUMN.objects.link(parts_mesh("SaeuleSockel", [("b", (0, 0, 0.2), (1.5, 1.5, 0.4), 0), ("b", (0, 0, 0.55), (1.25, 1.25, 0.3), 0),
                                              ("b", (0, 0, 13.6), (1.5, 1.5, 0.4), 1), ("b", (0, 0, 13.2), (1.25, 1.25, 0.4), 0)],
                               [MARBLE, GOLD], link_=False))
_shaft = prim("cyl", "SaeuleSchaft", (0, 0, 6.9), (0.95, 0.95, 12.6), m=MARBLE, seg=20)
move_to(_shaft, COLUMN)
for _r in (0.75, 12.95):
    move_to(prim("torus", "SaeuleRing", (0, 0, _r), (2.0, 2.0, 1.2), m=GOLD, seg=24), COLUMN)


def columns(C, rows, xs, dy, rz=0.0):
    for j in range(rows):
        for x in xs:
            p = C + Matrix.Rotation(rz, 3, "Z") @ Vector((x, j * dy, 0))
            instance("Saeule_%d_%d" % (j, int(x * 10)), COLUMN, p, (0, 0, rz))


def organ(C, n=17, w=7.0, rz=0.0, gap=0.0):
    """Orgelpfeifen aus Gold hinter dem DJ-Pult (mit Lücke in der Mitte für die Blöcke)."""
    for j in range(n):
        x = (j - (n - 1) / 2) * w / n
        if abs(x) < gap:
            continue
        h = 3.0 + 4.5 * (1 - abs(x) / (w / 2)) ** 0.8 + (0.6 if j % 2 else 0.0)
        p = C + Matrix.Rotation(rz, 3, "Z") @ Vector((x, 0, h / 2))
        prim("cyl", "Pfeife%02d" % j, p, (0.34, 0.34, h), m=GOLD, seg=14)
        prim("cone", "PfeifeMund%02d" % j, p + Vector((0, 0, -h / 2 + 0.9)), (0.36, 0.36, 0.3), rot=(math.pi, 0, 0), m=DECK_M, seg=14)


def steps(C, n, rise, depth, width, m=MARBLE, name="Stufe"):
    parts = [("b", (0, (k + 0.5) * depth, (k + 0.5) * rise), (width, depth, rise * (k + 1) * 0 + rise), 0) for k in range(n)]
    parts += [("b", (0, (k + 0.5) * depth, k * rise / 2), (width, depth, k * rise), 0) for k in range(1, n)]
    return parts_mesh(name, parts, [m], loc=C)


ROSE_EM = []


def rose_window(C, R=7.5):
    """Rosenfenster aus leuchtenden Glasquadraten in einem goldenen Ring, Vorderseite nach -Y."""
    cols = ["#1f3fd8", "#d81f3f", "#f2c12e", "#1fa860", "#7a2fd8", "#ff7a1f"]
    ms = []
    for i, c in enumerate(cols):
        m = emit_mat("Glas%d" % i, c, 3.0)
        ms.append(m)
        ROSE_EM.append(m.node_tree.nodes.get("Emission"))
    parts = []
    g = 0.62
    n = int(R / g)
    for ix in range(-n, n + 1):
        for iz in range(-n, n + 1):
            x, z = ix * g, iz * g
            r = math.hypot(x, z)
            if r > R - 0.2:
                continue
            a = (math.atan2(z, x) + math.pi) / math.tau
            ring = int(r / (R / 4))
            ci = (int(a * 12) + ring * 2) % len(cols) if ring > 0 else 2
            parts.append(("b", (x, 0, z), (g * 0.86, 0.12, g * 0.86), ci))
    win = parts_mesh("Rosenfenster", parts, ms, loc=C)
    for k in range(3):
        prim("torus", "RoseRing%d" % k, C + Vector((0, -0.1, 0)), (2 * R * (1 - k * 0.33) + 0.4,) * 2 + (2.2,), rot=(math.pi / 2, 0, 0),
             m=GOLD, seg=64)
    for k in range(12):      # goldene Speichen
        a = k * math.tau / 12
        prim("cube", "RoseSpeiche%d" % k, C + Vector((math.cos(a) * R / 2, -0.12, math.sin(a) * R / 2)), (R, 0.16, 0.16),
             rot=(0, -a, 0), m=GOLD)
    return win


def gate(C):
    """Goldenes Himmelstor: zwei Säulen, Bogen, Gitter."""
    for sx in (-1, 1):
        prim("cyl", "TorSaeule%d" % sx, C + Vector((sx * 4.2, 0, 4.5)), (1.0, 1.0, 9.0), m=GOLD, seg=20)
        prim("sphere", "TorKugel%d" % sx, C + Vector((sx * 4.2, 0, 9.4)), (1.2, 1.2, 1.2), m=GOLD)
    prim("torus", "TorBogen", C + Vector((0, 0, 9.0)), (8.4, 8.4, 4.0), rot=(math.pi / 2, 0, 0), m=GOLD, seg=48)
    for k in range(11):
        x = (k - 5) * 0.72
        prim("cyl", "TorStab%d" % k, C + Vector((x, 0.3, 4.0)), (0.12, 0.12, 8.0), m=GOLD, seg=8)


CANDLE = proto_collection("Kerze")
CANDLE.objects.link(parts_mesh("KerzeMesh", [("b", (0, 0, 0.25), (0.14, 0.14, 0.5), 0)], [mat("Wachs", "#f4ead2", 0.6, sss=0.3)], link_=False))
CANDLE.objects.link(parts_mesh("FlammeMesh", [("s", (0, 0, 0.6), (0.08, 0.08, 0.16), 0)], [emit_mat("Flamme", "#ffb048", 18.0)], link_=False))


def candles(C, n, r0, r1, seed=1.0):
    for i in range(n):
        a = hsh(i * 3.7 + seed) * math.tau
        r = r0 + (r1 - r0) * hsh(i * 1.9 + seed) ** 0.6
        instance("Kerze%03d" % i, CANDLE, C + Vector((math.cos(a) * r, math.sin(a) * r, 0)), (0, 0, 0), 0.8 + hsh(i * 7.7) * 1.4)


# ------------------------------------------------------------------ DJ-Pult als Altar
DJ = {}


def build_dj(C, rz=math.pi * 0):
    """Altar aus Marmor mit zwei Plattenspielern und Mischpult; Vorderseite nach -Y. Mino Man steht bei +Y."""
    R = empty("DJPult", C, rot=(0, 0, rz))
    parts_mesh("DJAltar", [("b", (0, 0, 0.5), (2.7, 1.0, 1.0), 0), ("b", (0, 0, 1.02), (2.85, 1.12, 0.06), 1),
                           ("b", (0, -0.52, 0.5), (2.5, 0.04, 0.8), 1), ("b", (0, 0, 0.04), (2.95, 1.2, 0.08), 1)],
               [MARBLE, GOLD], parent=R)
    plats = []
    for sx in (-1, 1):
        prim("cube", "Deck%d" % sx, (sx * 0.78, 0.05, 1.1), (0.78, 0.6, 0.1), m=DECK_M, parent=R, bevel=0.02)
        p = prim("cyl", "Teller%d" % sx, (sx * 0.78, 0.05, 1.17), (0.52, 0.52, 0.03), m=mat("Vinyl", "#0a0a0c", 0.25), parent=R, seg=32)
        prim("cyl", "Label%d" % sx, (0, 0, 0.6), (0.36, 0.36, 0.5), m=emit_mat("LabelGold", "#ffcc33", 2.0), parent=p, seg=24)
        prim("cube", "Strich%d" % sx, (0.16, 0, 0.7), (0.3, 0.04, 0.4), m=mat("LabelStrich", "#2a2a2a", 0.4), parent=p)
        prim("cube", "Arm%d" % sx, (sx * 0.78 + 0.28, 0.2, 1.22), (0.03, 0.42, 0.03), rot=(0, 0, 0.35), m=GOLD, parent=R)
        plats.append(p)
    prim("cube", "Mixer", (0, 0.05, 1.12), (0.5, 0.5, 0.14), m=DECK_M, parent=R, bevel=0.02)
    knobs = []
    for k in range(9):
        kx, ky = (k % 3 - 1) * 0.13, (k // 3 - 1) * 0.12
        knobs.append(prim("sphere", "Knopf%d" % k, (kx, 0.05 + ky, 1.21), (0.06, 0.06, 0.05),
                          m=emit_mat("Knopf%d" % (k % 3), ["#ff3fa4", "#3fd8ff", "#ffd23a"][k % 3], 4.0), parent=R, seg=10))
    s = sign("DJSchild", "MINO", (0, -0.56, 0.5), 0.42, "#ffd23a", parent=R)
    DJ.update({"root": R, "plats": plats, "knobs": knobs, "sign": s})
    return R


def dj_run(t, b):
    for i, p in enumerate(DJ["plats"]):
        p.rotation_euler.z = t * 3.5 * (1 if i else 0.97)
    hit = ds_pulse(b)
    for k, kb in enumerate(DJ["knobs"]):
        s_ = 1 + (0.6 * hit if (int(b) + k) % 3 == 0 else 0.0)
        kb.scale = (0.06 * s_, 0.06 * s_, 0.05 * s_)
    DJ["sign"].scale = Vector((1, 1, 1)) * (1 + 0.1 * hit)


# Kopfhörer für Mino Man
HP_M = mat("Kopfhoerer", "#18181c", 0.3)
for _sx in (-1, 1):
    prim("cyl", "MM_kh%d" % _sx, (_sx * 0.15, -0.005, 0.17), (0.11, 0.11, 0.06), rot=(0, math.pi / 2, 0), m=HP_M, parent=MM["head"], seg=20)
    prim("cyl", "MM_khgold%d" % _sx, (_sx * 0.183, -0.005, 0.17), (0.07, 0.07, 0.01), rot=(0, math.pi / 2, 0), m=GOLD, parent=MM["head"], seg=16)
curve_obj("MM_khbuegel", [Vector((-0.16, -0.005, 0.2)), Vector((-0.13, -0.005, 0.34)), Vector((0, -0.005, 0.4)),
                          Vector((0.13, -0.005, 0.34)), Vector((0.16, -0.005, 0.2))], radius=0.016, m=HP_M, parent=MM["head"])


def pose_mm_dj(t, b, mode="mix"):
    """Mino Man am Pult: Hände auf den Decks, Kopf nickt hart auf den Beat; scratchen, Faust hoch, beide Arme hoch."""
    ph = math.pi * b
    hit = ds_pulse(b)
    for sx, (hp, kn) in MM["legs"].items():
        st = max(0.0, math.sin(ph + (0 if sx > 0 else math.pi)))
        hp.rotation_euler = (st * 0.3, 0, sx * 0.06)
        kn.rotation_euler = (-st * 0.5, 0, 0)
    MM["torso"].rotation_euler = (0, 0, 0.1 * math.sin(ph * 0.5))
    MM["neck"].rotation_euler = (0.3 * hit - 0.02, 0, 0.08 * math.sin(ph * 0.5))
    MM["glint"].scale = (0.022 * (1 + 2 * hit), 0.006, 0.012)

    def arm(sx, x, z, e):
        sh, el = MM["arms"][sx]
        sh.rotation_euler = (x, 0, z)
        el.rotation_euler = (e, 0, 0)
    scr = math.sin(t * 26) * 0.07
    arm(1, 0.36 + scr, 0.12 + 0.1 * math.sin(t * 13), 1.12)
    arm(-1, 0.38, -0.1, 1.1)
    if mode == "cue":
        arm(-1, 2.15, 0.55, 2.3)              # Hand am Kopfhörer
        MM["neck"].rotation_euler = (0.12 * hit, 0, -0.25)
    elif mode == "fist":
        arm(1, 2.85 + 0.2 * hit, -0.25, 0.12)
    elif mode == "hands":
        for sx in (-1, 1):
            arm(sx, 2.75 + 0.15 * hit, -sx * 0.45, 0.12)
        MM["neck"].rotation_euler = (-0.25 - 0.1 * hit, 0, 0)


def mm_dj(t, b, at, rz=math.pi):
    place(MM["root"], at, rz, 1.0)
    MM["root"].location = Vector(at) + Vector((0, 0, 0.03 * ds_pulse(b)))
    if b < 15.5:
        mode = "cue" if int(b // 2) % 2 == 0 else "mix"
    elif b >= 40:
        mode = "hands" if int(b // 2) % 2 == 0 else "fist"
    else:
        mode = "fist" if (int(b) % 4 == 0 and b - int(b) < 0.75) else "mix"
    pose_mm_dj(t, b, mode)


# ------------------------------------------------------------------ Die Blöcke: je 6 Screens, alle mit demselben Clip
BLOCK_W = 2.4
BLOCK_H = BLOCK_W * 16 / 9
BLOCK_AP = BLOCK_W / 2 / math.tan(math.pi / 6)
BLOCKS = []
BLOCK_KEYS = ["cg2", "mm", "gm2", "e1", "ig1", "e3", "e5", "ig2", "e2", "ig3"]
CLIP_FALLBACK.update({"cg2": "#c4002a", "gm2": "#1f4fd0"})
N_BLOCKS = 9
MOS_C, MOS_R = 3, 3        # Mosaik: 3 x 3 Blöcke ergeben zusammen ein Hochformat-Bild von Chicken Guy


def hex_screen_mesh(name, m):
    verts, faces, uvs = [], [], []
    w, h, r = BLOCK_W, BLOCK_H, BLOCK_AP + 0.11
    for k in range(6):
        a = k * math.pi / 3
        n = Vector((-math.sin(a), math.cos(a), 0))
        rt = Vector((-math.cos(a), -math.sin(a), 0))
        c = n * r
        z = Vector((0, 0, 1))
        q = [c - rt * w / 2 - z * h / 2, c + rt * w / 2 - z * h / 2, c + rt * w / 2 + z * h / 2, c - rt * w / 2 + z * h / 2]
        base = len(verts)
        verts += [tuple(v) for v in q]
        faces.append((base, base + 1, base + 2, base + 3))
        uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        uv.data[li].uv = uvs[lp.vertex_index]
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    return link(ob)


def build_block(i, key):
    name = "Block%d" % i
    root = empty(name, HIDE)
    r_, c_ = divmod(i, MOS_C)
    m, v = mix_clip_mat(name, key, "cg2", offset=i * 53, ncol=MOS_C, nrow=MOS_R, col=c_, row=r_)
    parts = []
    for k in range(6):
        a = k * math.pi / 3
        parts.append(("b", (-math.sin(a) * BLOCK_AP, math.cos(a) * BLOCK_AP, 0), (BLOCK_W + 0.16, 0.2, BLOCK_H + 0.22), 0, a))
    parts_mesh(name + "_rahmen", parts, [BLOCK_BEZEL], parent=root)
    scr = hex_screen_mesh(name + "_bilder", m)
    scr.parent = root
    no_shadow_obj(scr)
    for sz in (1, -1):
        prim("cyl", name + "_deckel%d" % sz, (0, 0, sz * (BLOCK_H / 2 + 0.2)), (BLOCK_W * 2.2, BLOCK_W * 2.2, 0.28), m=GOLD, parent=root, seg=6)
        prim("cone", name + "_spitze%d" % sz, (0, 0, sz * (BLOCK_H / 2 + 0.62)), (0.7, 0.7, 0.56), rot=(0 if sz > 0 else math.pi, 0, 0), m=GOLD,
             parent=root, seg=6)
    cab = prim("cyl", name + "_kette", (0, 0, BLOCK_H / 2 + 100.8), (0.06, 0.06, 200), m=GOLD, parent=root, seg=6)
    blk = {"root": root, "val": v, "i": i, "key": key, "cable": cab}
    BLOCKS.append(blk)
    return blk


BLOCK_SPAN = 2 * BLOCK_AP + 0.4       # Breite über die Flächen plus Luft
BLOCK_TALL = BLOCK_H + 1.25           # Höhe mit Deckeln und Spitzen


def block_spin(blk, b, t, fast_from=32, fast_to=40):
    """Vor dem Drop langsames Drehen; ab dem Drop rastet jeder Block auf jedem Schlag eine Fläche weiter (60°),
    in der Steigerung auf jedem halben Schlag. Das Raster liegt auf 0°, damit Mosaike aufgehen."""
    d = 1 if blk["i"] % 2 == 0 else -1
    pre = blk["i"] * 0.4 + d * min(b, DROP) * BEAT * 0.35
    if b < DROP:
        return pre
    wrap = (pre + math.pi / 6) % (math.pi / 3) - math.pi / 6
    settle = wrap * (1 - smooth((b - DROP) / 0.5))

    def ticks(x):
        if x < fast_from:
            n = int(x - DROP); f = (x - DROP) % 1.0; k = 0.35
        elif x < fast_to:
            n = int(fast_from - DROP) + int((x - fast_from) / 0.5); f = ((x - fast_from) % 0.5) / 0.5; k = 0.5
        else:
            n = int(fast_from - DROP) + int((fast_to - fast_from) / 0.5) + int(x - fast_to); f = (x - fast_to) % 1.0; k = 0.35
        return n + ease_back(clamp(f / k))
    return settle + d * ticks(b) * math.pi / 3


def block_set(blk, pos, rz, s, t, b, sway=1.0):
    hit = ds_pulse(b) if b >= DROP else 0.35 * ds_pulse(b)
    i = blk["i"]
    sc = s * (1 + 0.06 * hit)
    blk["root"].location = Vector(pos) + Vector((0, 0, 0.18 * hit * s + math.sin(t * 0.6 + i) * 0.12 * sway))
    blk["root"].rotation_euler = (math.sin(t * 0.8 + i) * 0.025 * sway, math.cos(t * 0.7 + i) * 0.025 * sway, rz)
    blk["root"].scale = (sc, sc, sc)


def block_top(blk):
    s = blk["root"].scale.z
    return blk["root"].location + Vector((0, 0, (BLOCK_H / 2 + 0.34) * s))


# ------------------------------------------------------------------ Formationen (Positionen + Größe für n Blöcke)
def formation(name, C, n, s, t, b, kw):
    bw, bh = BLOCK_SPAN * s, BLOCK_TALL * s
    z0 = kw.get("z0", 6.0)
    out = []
    if name == "streu":
        for i in range(n):
            out.append(C + Vector(((hsh(i * 3.3 + 1) - 0.5) * kw.get("wx", 30), (hsh(i * 5.1 + 2) - 0.3) * kw.get("wy", 26),
                                   z0 + 8 + hsh(i * 7.7) * 10)))
    elif name == "reihe":
        for i in range(n):
            out.append(C + Vector(((i - (n - 1) / 2) * bw * 1.2, 0, z0)))
    elif name == "bogen":
        R = kw.get("r", 9.0)
        for i in range(n):
            a = math.radians(-70 + 140 * i / max(1, n - 1))
            out.append(C + Vector((math.sin(a) * R, math.cos(a) * R * 0.55, z0 + (1 - abs(a) / 1.3) * 2.0)))
    elif name == "kreuz":
        cells = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (-1, 3), (1, 3), (-2, 3), (2, 3)]
        for gx, gy in cells[:n]:
            out.append(C + Vector((gx * bw, 0, z0 + gy * bh)))
    elif name == "turm":
        for i in range(n):
            out.append(C + Vector((0, 0, z0 + i * bh * 0.98)))
    elif name == "helix":
        for i in range(n):
            a = i * 1.0 + t * 0.6
            out.append(C + Vector((math.cos(a) * kw.get("r", 3.2), math.sin(a) * kw.get("r", 3.2), z0 + i * bh * 0.8)))
    elif name in ("ring", "halo"):
        R = kw.get("r", 8.0)
        rot = kw.get("spin", 0.0) * (b - DROP if b > DROP else 0) + kw.get("a0", 0.0)
        for i in range(n):
            a = i / n * math.tau + rot
            out.append(C + Vector((math.cos(a) * R, math.sin(a) * R, z0 + (math.sin(a * 2 + t) * 0.4 if name == "ring" else 0))))
    elif name == "raster":
        cols = int(math.ceil(n / 2))
        for i in range(n):
            r_, c_ = divmod(i, cols)
            out.append(C + Vector(((c_ - (cols - 1) / 2) * bw * 1.12 + (0.5 * bw if r_ and n % 2 else 0), 0, z0 + r_ * bh * 1.05)))
    elif name == "pyramide":
        rows = [4, 3, 2]
        k = 0
        for r_, cnt in enumerate(rows):
            for c_ in range(cnt):
                if k < n:
                    out.append(C + Vector(((c_ - (cnt - 1) / 2) * bw * 1.05, 0, z0 + r_ * bh)))
                    k += 1
    elif name == "v":
        for i in range(n):
            out.append(C + Vector(((i - (n - 1) / 2) * bw * 1.1, 0, z0 + abs(i - (n - 1) / 2) * bh * 0.55)))
    elif name == "treppe":
        for i in range(n):
            out.append(C + Vector(((-1 if i % 2 else 1) * kw.get("dx", 5.5), i * kw.get("dy", 3.4), i * kw.get("dz", 1.4) + z0)))
    elif name == "figur":
        up = kw.get("up", 0.0)
        cells = [(-0.55, 0), (0.55, 0), (0, 1), (0, 2), (0, 3), (-1, 2 + up * 0.5), (1, 2 + up * 0.5), (-2, 2 + up), (2, 2 + up)]
        for gx, gy in cells[:n]:
            out.append(C + Vector((gx * bw, 0, z0 + gy * bh)))
    elif name == "mosaik":
        mw, mh = 2 * BLOCK_AP * s * 1.03, BLOCK_TALL * s * 0.93
        for i in range(n):
            r_, c_ = divmod(i, MOS_C)
            out.append(C + Vector(((c_ - (MOS_C - 1) / 2) * mw, 0, z0 + r_ * mh)))
    while len(out) < n:
        out.append(out[-1] + Vector((0, 0, bh)))
    return out


def blocks_run(t, b, seq, C, s_default=1.0, dur=0.9, stagger=0.07, spin=True, fast=(32, 40)):
    """seq: [(beat, name, s, kw)] – ab beat gilt die Formation; Wechsel als kurze Fahrt, Block für Block versetzt."""
    n = len(BLOCKS)
    idx = max([k for k, e in enumerate(seq) if e[0] <= b] or [0])
    b0, nm, s, kw = seq[idx]
    cur = formation(nm, kw.get("C", C), n, s, t, b, kw)
    if idx > 0:
        pb, pn, ps, pkw = seq[idx - 1]
        prev = formation(pn, pkw.get("C", C), n, ps, t, b, pkw)
    else:
        prev, ps = cur, s
    for j, blk in enumerate(BLOCKS):
        u = ease_back(clamp((b - b0 - j * stagger) / dur)) if idx > 0 else 1.0
        p = vlerp(prev[j], cur[j], u)
        sc = lerp(ps, s, clamp(u))
        rz = block_spin(blk, b, t, fast[0], fast[1]) if spin else 0.0
        block_set(blk, p, rz, sc, t, b, sway=1.0 if nm in ("streu", "reihe", "bogen", "ring") else 0.25)


def one_channel(b, b_on=40):
    on = 1.0 if b >= b_on else 0.0
    for blk in BLOCKS:
        blk["val"].outputs[0].default_value = on


# ------------------------------------------------------------------ Menge: ekstatisch
def crowd_pose2(d, t, b, mode, base, rz, amp=1.0):
    if mode not in ("praise", "jump"):
        return crowd_pose(d, t, b, mode, base, rz, amp)
    k = d["seed"]
    R, ch, hd = d["root"], d["chest"], d["head"]
    ph = math.pi * b
    hit = ds_pulse(b)
    R.scale = (1, 1, 1)

    def arm(sx, x, z=0.0, e=0.2):
        sh, el = d["arms"][sx]
        sh.rotation_euler = (x, 0, z)
        el.rotation_euler = (e, 0, 0)
    if mode == "praise":       # Arme hoch, wiegen, Kopf in den Nacken
        sw = math.sin(t * 2.2 + k)
        R.location = Vector(base) + Vector((0, 0, 0.03 * hit))
        R.rotation_euler = (0, 0, rz + 0.08 * sw)
        for sx, lg in d["legs"].items():
            lg.rotation_euler = (0, 0, 0)
        ch.rotation_euler = (0.14, 0.1 * sw, 0)
        hd.rotation_euler = (-0.4, 0, 0.15 * sw)
        for sx in (-1, 1):
            arm(sx, 2.8 + 0.12 * math.sin(t * 3 + k + sx), -sx * (0.5 + 0.2 * math.sin(t * 2.6 + k * 1.3 + sx)), 0.15)
        return
    # jump: springen auf jedem Schlag, Arme fliegen hoch
    j = abs(math.sin(ph + k * 0.3)) * amp
    R.location = Vector(base) + Vector((0, 0, 0.38 * j))
    R.rotation_euler = (0, 0, rz + 0.15 * math.sin(ph * 0.5 + k))
    for sx, lg in d["legs"].items():
        lg.rotation_euler = (0.5 * (1 - j), 0, sx * 0.08)
    ch.rotation_euler = (0.1 - 0.15 * hit, 0, 0)
    hd.rotation_euler = (-0.3 * j + 0.2 * hit, 0, 0.2 * math.sin(t * 5 + k))
    up = (int(b) + k) % 2 == 0
    for sx in (-1, 1):
        if up:
            arm(sx, 2.9, -sx * 0.4, 0.1)
        else:
            arm(sx, 2.2 + 0.5 * j, -sx * 0.7, 0.6)


def crowd_mode(b, i, plan=None):
    """Standardablauf: schauen, Arme heben, Drop = Ekstase, Anbetung, Ekstase."""
    plan = plan or [(0, "stand"), (8, "praise"), (16, "jump"), (24, "dance"), (32, "bow"), (40, "jump"), (44, "praise")]
    m = plan[0][1]
    for b0, mm in plan:
        if b >= b0 - (0.0 if mm != "praise" else hsh(i) * 0.5):
            m = mm
    return m


N_CROWD = {1: 28, 2: 22, 3: 24, 4: 22, 5: 24}[VARIANT]
for i_ in range(N_CROWD):
    dancer("Gemeinde%02d" % i_, i_)


def crowd_grid(t, b, C, rz, cols, dx, dy, plan=None, z_of=None):
    for i, d in enumerate(CROWD):
        r_, c_ = divmod(i, cols)
        p = C + Vector(((c_ - (cols - 1) / 2) * dx + (0.4 * dx if r_ % 2 else 0) + (hsh(i) - 0.5) * 0.3, -r_ * dy + (hsh(i * 2) - 0.5) * 0.3, 0))
        if z_of:
            p.z = z_of(p)
        crowd_pose2(d, t, b, crowd_mode(b, i, plan), p, rz)


def crowd_circle(t, b, C, r0, plan=None, per=11, r_step=1.7, face=None):
    for i, d in enumerate(CROWD):
        ring_i, j = divmod(i, per)
        r = r0 + ring_i * r_step
        a = (j + 0.5 * (ring_i % 2)) / per * math.tau + 0.15
        p = C + Vector((math.cos(a) * r, math.sin(a) * r, 0))
        crowd_pose2(d, t, b, crowd_mode(b, i, plan), p, face_to(p, face or C))


def side_cast(t, b, cow_p, peng_p, gm_p, face_c):
    cow_run(t, b, cow_p, cow_p, 0, 1, dance=b >= DROP)
    COW["root"].rotation_euler.z = face_to(cow_p, face_c)
    peng_run(t, b, peng_p, peng_p, 0, 1, dance=b >= DROP)
    PENG["root"].rotation_euler.z = face_to(peng_p, face_c)
    place(GM["root"], gm_p, face_to(gm_p, face_c), 1.0)
    pose_grandma(t, b, erupt_from=32 if b >= 32 else None)


def face_to(p, q):
    d = Vector(q) - Vector(p)
    return math.atan2(-d.x, d.y)


def cg_on_block(t, b, blk, rz=math.pi):
    top = block_top(blk)
    cg_ds(t, b, top, rz, 1.0)


def cg_ds(t, b, p, rz, wild=1.0):
    ds_root(CG["root"], p, rz, b, 0.8, CG_S)
    pose_cg(t, wild)


def fall_to(obj_root, b, b0, b1, at, rz, s):
    """Fällt vom Himmel und landet auf Schlag b1."""
    if b < b0:
        place(obj_root, HIDE)
        return False
    if b < b1:
        u = (b - b0) / (b1 - b0)
        place(obj_root, Vector(at) + Vector((0, 0, 16 * (1 - u) ** 2)), rz + u * 6, s)
        return False
    return True


# ================================================================== Fünf Abläufe
for i_ in range(N_BLOCKS):
    build_block(i_, BLOCK_KEYS[i_])
MU["root"].location = HIDE
sh_ = shot

# ---------------------------------------------------------------- 1: KATHEDRALE – Säulenhalle auf Wolken, Kreuz aus Blöcken
if VARIANT == 1:
    ALT = Vector((0, 16.0, 0))
    PLAT_H = 0.9
    parts_mesh("Altarstufen", [("b", (0, 16.0 + 1.2, 0.15), (12, 7.6, 0.3), 0), ("b", (0, 16.0 + 1.5, 0.45), (10, 6.6, 0.3), 0),
                               ("b", (0, 16.0 + 1.8, 0.75), (8, 5.8, 0.3), 0), ("b", (0, 16.0 - 2.15, 0.33), (12, 0.12, 0.66), 1)],
               [MARBLE, GOLD])
    columns(Vector((0, -10, 0)), 7, (-7.0, 7.0), 4.6)
    organ(ALT + Vector((0, 4.2, PLAT_H)), 25, 12.0, gap=2.4)
    build_dj(ALT + Vector((0, 0, PLAT_H)))
    MM_AT = ALT + Vector((0, 0.5, PLAT_H))
    KREUZ_C = ALT + Vector((0, 7.5, 0))
    SEQ = [(0, "streu", 0.9, {"C": Vector((0, 6, 0)), "z0": 9}),
           (8, "reihe", 0.85, {"C": Vector((0, 8, 0)), "z0": 9.5}),
           (12, "bogen", 0.9, {"C": ALT + Vector((0, 2, 0)), "z0": 7.5, "r": 10}),
           (16, "kreuz", 0.95, {"C": KREUZ_C, "z0": 3.2}),
           (24, "ring", 0.85, {"C": Vector((0, 6, 0)), "z0": 9.5, "r": 9, "spin": math.pi / 16}),
           (28, "v", 0.9, {"C": KREUZ_C, "z0": 5}),
           (32, "pyramide", 0.95, {"C": KREUZ_C, "z0": 3.2}),
           (34, "raster", 0.95, {"C": KREUZ_C, "z0": 4}),
           (36, "turm", 0.8, {"C": KREUZ_C, "z0": 2.5}),
           (38, "kreuz", 0.9, {"C": KREUZ_C, "z0": 3.2}),
           (40, "mosaik", 1.0, {"C": KREUZ_C, "z0": 3.2})]

    def story(t, b):
        set_world("himmel")
        blocks_run(t, b, SEQ, O)
        one_channel(b, 40)
        dj_run(t, b)
        mm_dj(t, b, MM_AT)
        # Chicken Guy fällt auf den mittleren Block des Kreuzes und tanzt dort
        if fall_to(CG["root"], b, 18, 20, block_top(BLOCKS[4]) if b < 24 else block_top(BLOCKS[4]), math.pi, CG_S):
            if b < 24 or b >= 40:
                cg_on_block(t, b, BLOCKS[4])
            else:
                cg_ds(t, b, ALT + Vector((2.6, -1.4, PLAT_H)), math.pi)
        crowd_grid(t, b, Vector((0, 9.5, 0)), math.pi * 0 + 0.0, 5, 1.9, 1.85)
        for d in CROWD:      # alle schauen zum Altar (+Y)
            d["root"].rotation_euler.z = d["root"].rotation_euler.z
        side_cast(t, b, Vector((4.8, 6.0, 0)), Vector((-4.6, 7.6, 0)), Vector((-4.4, 11.6, 0)), ALT)
        doves_run(t, b, Vector((0, 8, 0)), 12, 15)

    sh_(0, Vector((0, -16, 2.0)), Vector((0, 8, 9)), 18, trans=0, drift=0.15)
    sh_(4, lambda: MM_AT + Vector((1.5, -3.4, 2.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 30)
    sh_(8, Vector((-5, -12, 3.2)), Vector((0, 9, 8.5)), 20, drift=0.1)
    sh_(12, Vector((5.0, 3.0, 2.2)), ALT + Vector((0, 2, 7.5)), 20, drift=0.08)
    sh_(16, Vector((0, -6, 2.4)), KREUZ_C + Vector((0, 0, 10)), 18, drift=0.15)
    sh_(20, lambda: block_top(BLOCKS[4]) + Vector((2.5, -8.0, 1.5)), lambda: block_top(BLOCKS[4]) + Vector((0, 0, 0.3)), 22)
    sh_(24, Vector((0, -14, 6.0)), Vector((0, 6, 9)), 18, orbit=0.02)
    sh_(28, lambda: MM_AT + Vector((-1.6, -3.4, 1.2)), lambda: mm_head() + Vector((0, 0, 0.4)), 26)
    sh_(32, Vector((6.5, 2.0, 3.2)), KREUZ_C + Vector((0, 0, 8)), 20, orbit=-0.02)
    sh_(36, Vector((-2.0, 3.0, 4.2)), KREUZ_C + Vector((0, 0, 4.5)), 20)
    sh_(40, Vector((0, -2, 2.0)), KREUZ_C + Vector((0, 0, 11)), 18, drift=0.15)
    sh_(44, Vector((0, -18, 4.0)), KREUZ_C + Vector((0, 0, 9)), 18, drift=-0.3, rise=0.4)

# ---------------------------------------------------------------- 2: SPIEGELHIMMEL – Spiegelboden, schwebendes Pult, Ring aus Blöcken
elif VARIANT == 2:
    PC = Vector((0, 10, 0))
    PLAT = parts_mesh("Plattform", [("b", (0, 0, 0), (1, 1, 1), 0)], [GOLD])
    bpy.data.objects.remove(PLAT, do_unlink=True)
    PLAT = prim("cyl", "Schwebeplattform", PC + Vector((0, 0, 1.1)), (6.0, 6.0, 0.35), m=GOLD, seg=48)
    PLAT_TOP = prim("cyl", "PlattformMarmor", PC + Vector((0, 0, 1.3)), (5.6, 5.6, 0.08), m=MARBLE, seg=48)
    build_dj(PC + Vector((0, 0, 1.34)))
    MM_AT = PC + Vector((0, 0.5, 1.34))
    SEQ = [(0, "ring", 1.0, {"C": PC, "z0": 11, "r": 13, "spin": 0.0, "a0": 0.3}),
           (8, "ring", 0.9, {"C": PC, "z0": 7, "r": 10, "spin": 0.0, "a0": 0.3 + math.pi / 8}),
           (16, "ring", 0.9, {"C": PC, "z0": 6.5, "r": 9.5, "spin": math.pi / 24, "a0": 0.3 + math.pi / 8}),
           (24, "helix", 0.8, {"C": PC + Vector((0, 6, 0)), "z0": 2.0, "r": 3.4}),
           (28, "raster", 0.95, {"C": PC + Vector((0, 7.5, 0)), "z0": 3.0}),
           (32, "mosaik", 0.85, {"C": PC + Vector((0, 7.5, 0)), "z0": 2.6}),
           (40, "halo", 0.42, {"C": PC + Vector((0, 0.5, 0)), "z0": 5.4, "r": 2.4, "spin": math.pi / 8})]

    def story(t, b):
        set_world("gold")
        PLAT.location.z = 1.1 + math.sin(t * 0.8) * 0.05
        blocks_run(t, b, SEQ, PC)
        one_channel(b, 32)
        dj_run(t, b)
        mm_dj(t, b, MM_AT)
        cg_ds(t, b, PC + Vector((2.6, -1.6, 1.34)), math.pi - 0.3, 1.0 if b >= DROP else 0.6)
        crowd_circle(t, b, PC, 8.0, per=11, r_step=1.9)
        side_cast(t, b, PC + Vector((-7.0, -6.0, 0)), PC + Vector((7.4, -5.4, 0)), PC + Vector((-9.5, -2.5, 0)), PC)
        doves_run(t, b, PC, 15, 14)

    sh_(0, PC + Vector((-6, -26, 5.0)), PC + Vector((0, 0, 6)), 18, trans=0, drift=0.15, orbit=0.01)
    sh_(4, lambda: MM_AT + Vector((1.5, -3.4, 2.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 30)
    sh_(8, PC + Vector((0, -23, 2.6)), PC + Vector((0, 0, 5.5)), 18, drift=0.12)
    sh_(12, PC + Vector((10, -14, 5.5)), PC + Vector((0, 0, 4)), 20, orbit=0.02)
    sh_(16, PC + Vector((0, -21, 6.0)), PC + Vector((0, 0, 4.5)), 18, drift=0.15)
    sh_(20, lambda: CG["root"].location + Vector((1.2, -3.2, 0.9)), lambda: cg_head(), 28)
    sh_(24, PC + Vector((-8, -10, 1.2)), PC + Vector((0, 6, 7)), 18, orbit=0.03)
    sh_(28, PC + Vector((0, -6, 3.2)), PC + Vector((0, 7.5, 6)), 18)
    sh_(32, PC + Vector((2.5, -13, 3.2)), PC + Vector((0, 7.5, 5.5)), 18, drift=0.1)
    sh_(36, lambda: MM_AT + Vector((-1.5, -3.2, 1.0)), lambda: mm_head() + Vector((0, 0, 0.6)), 24)
    sh_(40, PC + Vector((3.0, -11, 4.6)), PC + Vector((0, 0, 4.2)), 20)
    sh_(44, PC + Vector((0, -26, 3.0)), PC + Vector((0, 0, 5)), 18, drift=-0.3, rise=0.3)

# ---------------------------------------------------------------- 3: ROSENFENSTER – Blöcke sind die Blütenblätter eines Glasfensters
elif VARIANT == 3:
    ALT = Vector((0, 14.0, 0))
    ROSE_C = ALT + Vector((0, 6.0, 11.0))
    rose_window(ROSE_C, 6.5)
    columns(Vector((0, -4, 0)), 5, (-6.5, 6.5), 4.4)
    build_dj(ALT + Vector((0, 0, 0)))
    parts_mesh("Podest", [("b", (0, 14.6, 0.0), (6, 3.4, 0.1), 0)], [GOLD])
    MM_AT = ALT + Vector((0, 0.5, 0))
    PETAL = {"C": ROSE_C + Vector((0, -1.5, 0)), "z0": 0.0}

    def petals(C, n, s, t, b, kw):
        return [C + Vector((math.cos(i / n * math.tau + math.pi / 2) * 9.6, -1.5, math.sin(i / n * math.tau + math.pi / 2) * 9.6)) for i in range(n)]

    _form = formation

    def formation(name, C, n, s, t, b, kw):     # noqa: F811 – Blütenblätter als eigene Formation
        if name == "rose":
            return petals(kw["C"], n, s, t, b, kw)
        return _form(name, C, n, s, t, b, kw)
    SEQ = [(0, "rose", 0.8, {"C": ROSE_C}),
           (16, "reihe", 0.8, {"C": Vector((0, 5, 0)), "z0": 8.5}),
           (20, "ring", 0.8, {"C": Vector((0, 4, 0)), "z0": 8.5, "r": 8.5, "spin": math.pi / 16}),
           (24, "bogen", 0.85, {"C": ALT, "z0": 7.0, "r": 10}),
           (28, "raster", 0.8, {"C": ALT + Vector((0, 3.5, 0)), "z0": 3.5}),
           (32, "v", 0.8, {"C": ALT + Vector((0, 3, 0)), "z0": 4.5}),
           (34, "mosaik", 0.8, {"C": ALT + Vector((0, 3.5, 0)), "z0": 2.6}),
           (40, "rose", 0.8, {"C": ROSE_C})]
    globals()["formation"] = formation

    def story(t, b):
        set_world("daemmer")
        blocks_run(t, b, SEQ, O, stagger=0.05)
        one_channel(b, 34)
        hit = ds_pulse(b)
        for e in ROSE_EM:
            e.inputs[1].default_value = 2.0 + (4.0 * hit if b >= DROP else 1.0 * hit)
        dj_run(t, b)
        mm_dj(t, b, MM_AT)
        # Chicken Guy steht in der Mitte der Rose (vor dem Glas) und tanzt
        cg_ds(t, b, ROSE_C + Vector((0, -2.2, -1.2)) if (b < 16 or b >= 40) else ALT + Vector((2.7, -1.0, 0)), math.pi, 1.0)
        crowd_grid(t, b, Vector((0, 7.0, 0)), 0.0, 6, 1.8, 1.8)
        side_cast(t, b, Vector((5.2, 3.0, 0)), Vector((-5.0, 4.5, 0)), Vector((4.6, 9.0, 0)), ALT)
        doves_run(t, b, Vector((0, 8, 0)), 12, 16)

    sh_(0, Vector((0, -14, 2.0)), ROSE_C + Vector((0, 0, -1)), 18, trans=0, drift=0.15)
    sh_(4, lambda: MM_AT + Vector((1.5, -3.4, 2.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 30)
    sh_(8, Vector((0, 1.5, 1.4)), ROSE_C, 20, drift=0.1)
    sh_(12, Vector((-6, 4, 2.0)), ROSE_C + Vector((0, 0, -2)), 22, orbit=0.02)
    sh_(16, Vector((0, -6, 2.4)), Vector((0, 6, 8.5)), 18, drift=0.12)
    sh_(20, Vector((0, -12, 5.5)), Vector((0, 4, 8.5)), 18, orbit=0.02)
    sh_(24, lambda: CG["root"].location + Vector((1.0, -3.0, 0.9)), lambda: cg_head(), 28)
    sh_(28, Vector((6.0, 2.0, 2.6)), ALT + Vector((0, 3.5, 6)), 20, orbit=-0.02)
    sh_(32, lambda: MM_AT + Vector((-1.5, -3.0, 1.1)), lambda: mm_head() + Vector((0, 0, 0.5)), 24)
    sh_(36, Vector((0, -9, 3.0)), ALT + Vector((0, 3.5, 5)), 18)
    sh_(40, Vector((0, -2, 2.2)), ROSE_C, 18, drift=0.15)
    sh_(44, Vector((0, -18, 3.5)), ROSE_C + Vector((0, 0, -3)), 18, drift=-0.3, rise=0.3)

# ---------------------------------------------------------------- 4: HIMMELSTREPPE – Treppe zum goldenen Tor, oben legt Mino Man auf
elif VARIANT == 4:
    N_ST, RISE, DEP = 14, 0.32, 1.25
    ST0 = Vector((0, 0, 0))
    steps(ST0, N_ST, RISE, DEP, 13.0, MARBLE, "Himmelstreppe")
    TOP = ST0 + Vector((0, N_ST * DEP, N_ST * RISE))
    parts_mesh("Oben", [("b", (0, 3.5, -0.5 * N_ST * RISE), (13.0, 7.0, N_ST * RISE), 0)], [MARBLE], loc=TOP)
    gate(TOP + Vector((0, 4.5, 0)))
    build_dj(TOP + Vector((0, 1.6, 0)))
    MM_AT = TOP + Vector((0, 2.1, 0))
    G_C = TOP + Vector((0, 4.5, 0))

    def stair_z(p):
        k = clamp((p.y - ST0.y) / DEP, 0, N_ST)
        return int(k) * RISE + (RISE if k >= 1 else 0) * 0 + (RISE if int(k) < N_ST and p.y > ST0.y else 0)
    SEQ = [(0, "treppe", 0.8, {"C": Vector((0, 1.5, 0)), "z0": 7, "dx": 5.5, "dy": 2.6, "dz": 0.9}),
           (8, "reihe", 0.8, {"C": G_C + Vector((0, 1.0, 0)), "z0": 12}),
           (16, "kreuz", 0.75, {"C": G_C + Vector((0, 2.5, 0)), "z0": 2.5}),
           (24, "treppe", 0.8, {"C": Vector((0, 1.5, 0)), "z0": 6, "dx": 5.0, "dy": 2.6, "dz": 0.9}),
           (28, "pyramide", 0.8, {"C": G_C + Vector((0, 2.5, 0)), "z0": 2.5}),
           (32, "v", 0.8, {"C": G_C + Vector((0, 2.5, 0)), "z0": 5}),
           (34, "ring", 0.8, {"C": G_C + Vector((0, -2, 0)), "z0": 9, "r": 8, "spin": math.pi / 8}),
           (36, "turm", 0.7, {"C": G_C + Vector((0, 2.5, 0)), "z0": 2.0}),
           (38, "kreuz", 0.75, {"C": G_C + Vector((0, 2.5, 0)), "z0": 2.5}),
           (40, "mosaik", 0.85, {"C": G_C + Vector((0, 2.5, 0)), "z0": 2.2})]

    def story(t, b):
        set_world("himmel")
        blocks_run(t, b, SEQ, O)
        one_channel(b, 40)
        dj_run(t, b)
        mm_dj(t, b, MM_AT)
        if b < 16:      # Chicken Guy steigt die Treppe hoch
            k = clamp(b / 16)
            p = Vector((0.0, 1.0 + k * (N_ST - 2) * DEP, 0))
            p.z = (int((p.y - ST0.y) / DEP) + 1) * RISE
            place(CG["root"], p, 0.0, CG_S)
            pose_cg(t, 0.6, "huepfen")
        else:
            cg_ds(t, b, TOP + Vector((2.7, 0.6, 0)), math.pi, 1.0)
        for i, d in enumerate(CROWD):
            cols = 6
            r_, c_ = divmod(i, cols)
            y = (N_ST - 2 - r_ * 2.0) * DEP + 0.6
            xx = (c_ - (cols - 1) / 2) * 1.9
            p = Vector((xx + math.copysign(0.9, xx), y, 0))
            p.z = (int((p.y - ST0.y) / DEP) + 1) * RISE
            crowd_pose2(d, t, b, crowd_mode(b, i), p, 0.0)
        side_cast(t, b, Vector((-5.2, 3.0, 2 * RISE + RISE)), Vector((5.0, 2.0, 2 * RISE)), Vector((5.4, 8.0, 7 * RISE)), MM_AT)
        doves_run(t, b, G_C, 13, 14)

    sh_(0, Vector((0, -12, 1.4)), G_C + Vector((0, 0, 6)), 18, trans=0, drift=0.15)
    sh_(4, lambda: MM_AT + Vector((1.5, -3.4, 2.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 30)
    sh_(8, lambda: CG["root"].location + Vector((0.6, 5.0, 3.0)), lambda: cg_head(), 26)
    sh_(12, Vector((-7, 2, 3.0)), G_C + Vector((0, 1, 12)), 20, drift=0.1)
    sh_(16, Vector((0, -6, 3.0)), G_C + Vector((0, 2.5, 9)), 18, drift=0.15)
    sh_(20, Vector((7.5, 6, 7.0)), G_C + Vector((0, 2.5, 7)), 20, orbit=-0.02)
    sh_(24, Vector((0, -3, 1.0)), Vector((0, 10, 7)), 16, drift=0.1)
    sh_(28, lambda: MM_AT + Vector((-1.6, -3.2, 1.0)), lambda: mm_head() + Vector((0, 0, 0.5)), 24)
    sh_(32, Vector((8, 4, 4.0)), G_C + Vector((0, 2.5, 7)), 20, orbit=0.02)
    sh_(36, lambda: CG["root"].location + Vector((3.4, -1.8, 1.2)), lambda: cg_head(), 28)
    sh_(40, Vector((0, 2, 6.5)), G_C + Vector((0, 2.5, 8)), 18, drift=0.12)
    sh_(44, Vector((0, -16, 3.0)), G_C + Vector((0, 0, 8)), 18, drift=-0.3, rise=0.4)

# ---------------------------------------------------------------- 5: LICHTMESSE – Nacht, Kerzen, die Blöcke werden ein Block-Gott
else:
    ALT = Vector((0, 12.0, 0))
    parts_mesh("Altarstufen", [("b", (0, 13.0, 0.2), (9, 6, 0.4), 0), ("b", (0, 13.3, 0.6), (7, 5, 0.4), 0)], [MARBLE])
    build_dj(ALT + Vector((0, 0, 0.8)))
    MM_AT = ALT + Vector((0, 0.5, 0.8))
    candles(Vector((0, 6, 0)), 260, 4.0, 40.0)
    candles(ALT + Vector((0, 0.6, 0.8)), 24, 1.8, 3.2, seed=9.0)
    for k_, (lx, ly) in enumerate(((-6, 4), (6, 4), (0, 18))):
        light("Kerzenlicht%d" % k_, "POINT", (lx, ly, 3.0), 600, "#ffb060", 2.0)
    GOD_C = ALT + Vector((0, 7.0, 0))
    SEQ = [(0, "streu", 0.8, {"C": Vector((0, 8, 0)), "z0": 9, "wx": 26, "wy": 22}),
           (8, "ring", 0.8, {"C": Vector((0, 6, 0)), "z0": 9, "r": 8.5}),
           (16, "ring", 0.8, {"C": Vector((0, 6, 0)), "z0": 8, "r": 8.5, "spin": math.pi / 16}),
           (20, "reihe", 0.8, {"C": Vector((0, 8, 0)), "z0": 8}),
           (24, "kreuz", 0.8, {"C": GOD_C, "z0": 2.5}),
           (28, "mosaik", 0.8, {"C": GOD_C, "z0": 2.4}),
           (32, "figur", 0.95, {"C": GOD_C, "z0": 2.4, "up": 0.0}),
           (40, "figur", 0.95, {"C": GOD_C, "z0": 2.4, "up": 1.0})]

    def story(t, b):
        set_world("nacht")
        blocks_run(t, b, SEQ, O, dur=1.2 if b >= 32 else 0.9)
        one_channel(b, 28)
        dj_run(t, b)
        mm_dj(t, b, MM_AT)
        if fall_to(CG["root"], b, 34, 36, block_top(BLOCKS[4]), math.pi, CG_S):
            cg_on_block(t, b, BLOCKS[4])
        elif b < 34:
            cg_ds(t, b, ALT + Vector((2.6, -1.0, 0.8)), math.pi, 1.0 if b >= DROP else 0.6)
        crowd_grid(t, b, Vector((0, 7.5, 0)), 0.0, 6, 1.9, 1.85,
                   plan=[(0, "stand"), (8, "praise"), (16, "jump"), (24, "dance"), (32, "bow"), (40, "praise"), (44, "jump")])
        side_cast(t, b, Vector((5.4, 4.0, 0)), Vector((-5.2, 5.0, 0)), Vector((-4.8, 10.0, 0)), ALT)
        doves_run(t, b, Vector((0, 8, 0)), 14, 18)

    sh_(0, Vector((0, -14, 1.6)), Vector((0, 8, 8)), 18, trans=0, drift=0.15)
    sh_(4, lambda: MM_AT + Vector((1.5, -3.4, 2.1)), lambda: mm_head() + Vector((0, 0, -0.3)), 30)
    sh_(8, Vector((-6, -10, 3.0)), Vector((0, 6, 8)), 18, drift=0.1)
    sh_(12, Vector((9, -6, 4.5)), Vector((0, 6, 7.5)), 18, orbit=0.02)
    sh_(16, Vector((0, -13, 3.0)), Vector((0, 6, 7.5)), 18, drift=0.12)
    sh_(20, lambda: CG["root"].location + Vector((1.2, -3.0, 0.9)), lambda: cg_head(), 28)
    sh_(24, Vector((6, 0, 3.0)), GOD_C + Vector((0, 0, 9)), 20, orbit=-0.02)
    sh_(28, lambda: MM_AT + Vector((-1.5, -3.0, 1.1)), lambda: mm_head() + Vector((0, 0, 0.5)), 24)
    sh_(32, Vector((0, -5, 1.6)), GOD_C + Vector((0, 0, 8)), 18, drift=0.1)
    sh_(36, lambda: block_top(BLOCKS[4]) + Vector((2.5, -8.0, 1.5)), lambda: block_top(BLOCKS[4]) + Vector((0, 0, 0.3)), 22)
    sh_(40, Vector((0, -2, 1.2)), GOD_C + Vector((0, 0, 10)), 16, drift=0.12)
    sh_(44, Vector((0, -18, 3.0)), GOD_C + Vector((0, 0, 8)), 18, drift=-0.3, rise=0.4)


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
set_sky(SKY_OF[VARIANT])
if VARIANT == 2:
    MIRROR_RT = True



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
                      ("volumetric_tile_size", "16" if FAST else "4"), ("use_raytracing", (not FAST) or VARIANT == 2)):
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

out = opt("--out", os.path.join(HERE, "out", "mino_heaven_v%d.mp4" % VARIANT))
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

"""MINO KABEL – Blender-Test-Reel für den Minoverse.

Welt: ein endloser dunkler Raum aus Röhrenfernsehern, Kabelsalat und herumliegenden Akten. Auf den
Fernsehern laufen Nachrichten, absurde Werbespots und Behördenmeldungen. Mitten drin: Mino Man am Pult
aus Fernsehern, Chicken Guy tanzt auf einem TV-Turm, Officer Munch isst Akten, Pepsi Grandma macht Werbung.

Alles ist aus Code gebaut (keine Fremdmodelle). Die Animation läuft als Funktion der Zeit über einen
frame_change-Handler (wie die HyperFrames-Runtime), damit Beats exakt sitzen.

  blender -b --factory-startup --python mino_kabel_reel.py -- --params params.json --song song.wav --out out/reel.mp4
  Optionen: --res 540x960  --fps 30  --engine EEVEE|CYCLES  --samples 16  --still 18.5  --save scene.blend
            --frames 1-120 (Ausschnitt)  --cpu (Cycles auf CPU)
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


P = {"bpm": 140.0, "song_offset_s": 0.0, "drop_beat": 16, "beats": 48}
if opt("--params") and os.path.exists(opt("--params")):
    P.update(json.load(open(opt("--params"))))
BPM = float(P["bpm"])
BEAT = 60.0 / BPM
NB = int(P["beats"])
DROP = int(P["drop_beat"])
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


def prim(kind, name, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), m=None, parent=None, smooth_=True,
         bevel=0.0, subsurf=0, seg=24):
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
    ob = bpy.context.active_object
    ob.name = name
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


# ------------------------------------------------------------------ Welt / Licht
world = bpy.data.worlds.new("Welt")
scn.world = world
world.use_nodes = True
wn = world.node_tree
bg = wn.nodes.get("Background")
bg.inputs[0].default_value = hexcol("#07060d")
bg.inputs[1].default_value = 1.0
# leichter Dunst, damit die Bildschirme im Raum stehen
vol = wn.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.012
vol.inputs["Color"].default_value = hexcol("#9a8cc0")
wout = wn.nodes.get("World Output")
wn.links.new(vol.outputs[0], wout.inputs["Volume"])


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


KEY = light("Key", "AREA", (2.5, 3.0, 4.5), 260, "#ffe6cc", size=2.5, rot=(math.radians(-40), math.radians(25), 0))
RIM = light("Rim", "AREA", (-3, -4, 3.5), 220, "#7f6bff", size=3, rot=(math.radians(55), math.radians(-30), 0))
FILL = light("Fill", "POINT", (0, 2.5, 1.2), 60, "#ff4fa3", size=1.5)

# ------------------------------------------------------------------ Boden und Rückwand
floor = prim("plane", "Boden", (0, -6, 0), (40, 60, 1), m=noise_mat("Linoleum", "#14121a", "#221d2b", scale=3, rough=0.35, bump=0.05))
wall = prim("plane", "Rueckwand", (0, -18, 6), (40, 12, 1), rot=(math.radians(90), 0, 0), m=mat("Wand", "#0b0a12", 0.9))

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
    s2 = nt.nodes.new("ShaderNodeMath"); s2.operation = "MULTIPLY"; s2.inputs[1].default_value = 4.0
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
    prim("cube", name + "_bezel", (-w * 0.08, 0.004, h * 0.52), (sw * 1.1, 0.02, sh * 1.12), m=mat("Bezel", "#111014", 0.6), parent=root)
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


# ------------------------------------------------------------------ Welt bauen: TV-Berg und Korridor
CHANNELS = [
    # (Senderfarbe, Zeilen)  – Werbung und Behördenmeldungen, alles diegetisch
    ("#1b3fa8", [("MINO 1", 0.30, "#ffffff"), ("NACHRICHTEN", -0.05, "#ffd23c")]),
    ("#c4002a", [("VERMISST", 0.22, "#ffffff"), ("CHICKEN GUY", -0.12, "#ffe34a")]),
    ("#0d7a3e", [("VEGANE", 0.25, "#ffffff"), ("HOT DOGS", 0.0, "#ffe34a"), ("JETZT REGNET'S", -0.27, "#ffffff")]),
    ("#1f4fd0", [("MENTOS+COLA", 0.2, "#ffffff"), ("19,99", -0.12, "#ffe34a")]),
    ("#6a1b9a", [("FREQUENZ", 0.2, "#ffffff"), ("STÄRKE 9", -0.12, "#ff9de2")]),
    ("#202020", [("AKTE 001", 0.2, "#ffffff"), ("GEGESSEN", -0.12, "#ff4d4d")]),
    ("#e0a000", [("GOTT", 0.22, "#111111"), ("ABWESEND", -0.1, "#111111")]),
    ("#0b6e8a", [("MINO FIT", 0.15, "#ffffff")]),
    ("#8a1b4f", [("KANAL", 0.22, "#ffffff"), ("404", -0.12, "#ffe34a")]),
    ("#2b2b70", [("BITTE NICHT", 0.22, "#ffffff"), ("UMSCHALTEN", -0.1, "#ffffff")]),
]


def fill_channel(s, ci):
    base, lines = CHANNELS[ci % len(CHANNELS)]
    s["nodes"]["col"].outputs[0].default_value = hexcol(base)
    s["base"] = base
    for body, y, c in lines:
        screen_text(s, body, 0.2 if len(body) < 9 else 0.15, c, y_rel=y)
    # grünes OSD oben links: Programmnummer
    screen_text(s, "P%d" % (ci + 1), 0.12, "#59ff8a", y_rel=0.38, x_rel=-0.38, fnt="vt", strength=5)


random.seed(3)
# TV-Berg hinter dem Pult (Zentrum der Welt)
MOUNTAIN = []
rows = [(7, 0.62), (6, 0.66), (5, 0.62), (4, 0.7), (3, 0.6)]
z = 0.0
ci = 0
for r, (n, sz) in enumerate(rows):
    x0 = -(n - 1) * sz * 0.55
    for i in range(n):
        s = tv("BergTV_%d_%d" % (r, i), (x0 + i * sz * 1.1 + (hsh(r * 9 + i) - 0.5) * 0.06, -3.2 - hsh(i + r) * 0.15, z),
               size=sz * (0.95 + hsh(r * 3 + i * 7) * 0.12), rot_z=(hsh(r + i * 5) - 0.5) * 0.25)
        fill_channel(s, ci)
        ci += 1
        MOUNTAIN.append(s)
    z += sz * 0.8

# Korridor: TV-Stapel links und rechts entlang -Y bis zur Kamera
CORRIDOR = []
for side in (-1, 1):
    for k in range(6):
        if side > 0 and k == 1:   # Platz für Pepsi Grandma
            continue
        y = 2.0 + k * 1.6
        h = 0
        for lvl in range(3 + (k + (side > 0)) % 2):
            sz = 0.55 + hsh(k * 13 + lvl * 3 + side) * 0.3
            s = tv("GangTV_%d_%d_%d" % (side, k, lvl), (side * (2.2 + hsh(k + lvl) * 0.25), y + (hsh(lvl * 5 + k) - 0.5) * 0.3, h),
                   size=sz, rot_z=-side * math.radians(70) + (hsh(k * 7 + lvl) - 0.5) * 0.3)
            fill_channel(s, ci)
            ci += 1
            CORRIDOR.append(s)
            h += sz * 0.78
# großer Haupt-Fernseher für den Kaltstart
HERO = tv("HeroTV", (0, 6.0, 0.0), size=1.1, casing="#6b4a2e", base="#1b3fa8")
screen_text(HERO, "MINO KABEL", 0.2, "#ffffff", y_rel=0.05, fnt="anton", strength=7)
screen_text(HERO, "P1", 0.14, "#59ff8a", y_rel=0.37, x_rel=-0.38, fnt="vt", strength=6)
screen_text(HERO, "KANAL 1 · BITTE NICHT UMSCHALTEN", 0.06, "#ffd23c", y_rel=-0.28, fnt="vt", strength=6)

# Neon-Senderlogo über dem Berg
LOGO = text("Logo", "MINO KABEL", size=0.75, m=emit_mat("Neon", "#ff3fa4", 12), loc=(0, -3.68, z + 0.8),
            rot=(math.radians(90), 0, math.pi), fnt="anton", extrude=0.03)
LOGO_FRAME = prim("cube", "LogoFrame", (0, -3.75, z + 0.8), (4.2, 0.08, 1.15), m=mat("LogoBack", "#120d18", 0.6), bevel=0.04)

# Laufschrift-Band (Ticker) quer über dem Korridoreingang
TICK_BAR = prim("cube", "TickerBand", (0, 0.4, 3.35), (8.0, 0.1, 0.32), m=mat("TickerBack", "#0a0a0a", 0.7))
TICKER_TXT = ("+++ PEPSI GRANDMA WURDE ERNEUT IM DRITTEN BEZIRK GESEHEN – KEINE WEITEREN DETAILS "
              "+++ MINISTERIUM FÜR KABEL BESTÄTIGT: ALLE KABEL SIND MIT ETWAS VERBUNDEN "
              "+++ AKTE 001 WEITERHIN UNGEKLÄRT +++ GOTT ABWESEND +++ ")
tick_m, tnt, tout = node_mat("TickerTxt")
# Text nur innerhalb des Bandes sichtbar: Emission nach Weltposition X ausblenden
geo = tnt.nodes.new("ShaderNodeNewGeometry")
sxyz = tnt.nodes.new("ShaderNodeSeparateXYZ")
tnt.links.new(geo.outputs["Position"], sxyz.inputs[0])
absx = tnt.nodes.new("ShaderNodeMath"); absx.operation = "ABSOLUTE"
tnt.links.new(sxyz.outputs["X"], absx.inputs[0])
mask = tnt.nodes.new("ShaderNodeMapRange")
mask.inputs["From Min"].default_value = 3.8; mask.inputs["From Max"].default_value = 3.6
tnt.links.new(absx.outputs[0], mask.inputs["Value"])
mstr = tnt.nodes.new("ShaderNodeMath"); mstr.operation = "MULTIPLY"; mstr.inputs[1].default_value = 7.0
tnt.links.new(mask.outputs[0], mstr.inputs[0])
tem = tnt.nodes.new("ShaderNodeEmission"); tem.inputs[0].default_value = hexcol("#ffe34a")
tnt.links.new(mstr.outputs[0], tem.inputs[1])
tnt.links.new(tem.outputs[0], tout.inputs[0])
TICKER = text("Ticker", TICKER_TXT, size=0.2, m=tick_m, loc=(4.0, 0.34, 3.35), rot=(math.radians(90), 0, math.pi), fnt="barlow", align="LEFT")

# ------------------------------------------------------------------ Kabel
CABLES = []
cable_m, cnt, cout = node_mat("Kabel")
cb = cnt.nodes.new("ShaderNodeBsdfPrincipled")
cb.inputs["Base Color"].default_value = hexcol("#0c0c0e")
cb.inputs["Roughness"].default_value = 0.35
# Leuchtpuls: Ringe, die vom Pult aus nach außen laufen (Phase vom Handler)
cgeo = cnt.nodes.new("ShaderNodeNewGeometry")
ring_d = cnt.nodes.new("ShaderNodeVectorMath"); ring_d.operation = "LENGTH"
cnt.links.new(cgeo.outputs["Position"], ring_d.inputs[0])
phase_v = cnt.nodes.new("ShaderNodeValue"); phase_v.name = "phase"
sub_ = cnt.nodes.new("ShaderNodeMath"); sub_.operation = "SUBTRACT"
cnt.links.new(ring_d.outputs["Value"], sub_.inputs[0])
cnt.links.new(phase_v.outputs[0], sub_.inputs[1])
frac = cnt.nodes.new("ShaderNodeMath"); frac.operation = "FLOORED_MODULO"; frac.inputs[1].default_value = 3.0
cnt.links.new(sub_.outputs[0], frac.inputs[0])
band = cnt.nodes.new("ShaderNodeMapRange")
band.interpolation_type = "SMOOTHSTEP"
band.inputs["From Min"].default_value = 0.0; band.inputs["From Max"].default_value = 0.35
band.inputs["To Min"].default_value = 1.0; band.inputs["To Max"].default_value = 0.0
cnt.links.new(frac.outputs[0], band.inputs["Value"])
glow_v = cnt.nodes.new("ShaderNodeValue"); glow_v.name = "glow"
gmul = cnt.nodes.new("ShaderNodeMath"); gmul.operation = "MULTIPLY"
cnt.links.new(band.outputs[0], gmul.inputs[0])
cnt.links.new(glow_v.outputs[0], gmul.inputs[1])
bsdf_input(cb, "Emission Color", "Emission").default_value = hexcol("#3fd4ff")
cnt.links.new(gmul.outputs[0], bsdf_input(cb, "Emission Strength"))
cnt.links.new(cb.outputs[0], cout.inputs[0])
CABLE_NODES = {"phase": phase_v, "glow": glow_v}

# Kabel als durchhängende Bögen zwischen Fernsehern, über den Boden und von der Decke
anchors = [s["root"].matrix_world.translation.copy() if False else Vector(s["root"].location) for s in MOUNTAIN + CORRIDOR]
for i in range(70):
    a = anchors[int(hsh(i * 3.1) * len(anchors))] + Vector((0, -0.4, 0.3))
    if i % 3 == 0:     # von der Decke herab
        b_ = Vector(((hsh(i) - 0.5) * 8, a.y + (hsh(i * 7) - 0.5) * 4, 7.5))
    elif i % 3 == 1:   # über den Boden zum Pult
        b_ = Vector(((hsh(i * 5) - 0.5) * 1.5, -1.8 + hsh(i) * 0.6, 0.6))
    else:              # zu einem anderen Fernseher
        b_ = anchors[int(hsh(i * 9.7) * len(anchors))] + Vector((0, -0.4, 0.3))
    mid = (a + b_) / 2
    sag = 0.6 + (a - b_).length * 0.25
    pts = [a, a.lerp(mid, 0.5) + Vector((0, 0, -sag * 0.6)), Vector((mid.x, mid.y, max(0.03, mid.z - sag))),
           b_.lerp(mid, 0.5) + Vector((0, 0, -sag * 0.6)), b_]
    for p in pts:
        p.z = max(0.03, p.z)
    CABLES.append(curve_obj("Kabel%02d" % i, pts, radius=0.018 + hsh(i * 2) * 0.03, m=cable_m))
# dicke Kabelbündel auf dem Boden im Korridor
for i in range(14):
    x = (hsh(i * 4) - 0.5) * 3.2
    pts = [Vector((x, 12, 0.04)), Vector((x + (hsh(i) - .5) * 1.2, 7, 0.05)), Vector((x * 0.5, 2, 0.06)),
           Vector(((hsh(i * 9) - .5) * 1.2, -1.5, 0.05)), Vector(((hsh(i * 2) - .5) * 2, -3.0, 0.4))]
    CABLES.append(curve_obj("BodenKabel%02d" % i, pts, radius=0.03 + hsh(i) * 0.03, m=cable_m))

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


AKTEN_TEXT = ["AKTE 001\nCHICKEN GUY\nZUSTAND: GEGESSEN", "AKTE 017\nHOT-DOG-REGEN\n(VEGAN)\nSTATUS: BEANTRAGT",
              "AKTE 404\nNICHT GEFUNDEN", "AKTE 002\nPEPSI GRANDMA\nWIEDERHOLT", "AKTE 033\nMITTWOCH\nFOLGTE DIENSTAG",
              "AKTE 009\nGOTT\nABWESEND", "AKTE 120\nKABEL\nMIT ETWAS\nVERBUNDEN"]
# Stapel auf dem Boden des Korridors
for i in range(16):
    x = (hsh(i * 2.7) - 0.5) * 3.0
    y = 1.0 + hsh(i * 5.1) * 10
    hgt = 1 + int(hsh(i * 8) * 6)
    for j in range(hgt):
        akte("Akte_%d_%d" % (i, j), (x + (hsh(i + j) - .5) * 0.05, y + (hsh(i * j + 1) - .5) * 0.05, j * 0.026),
             rot_z=(hsh(i * 3 + j) - 0.5) * 0.6, label=AKTEN_TEXT[(i + j) % len(AKTEN_TEXT)] if j == hgt - 1 else None)
# fliegende Blätter (für den Drop)
FLYERS = []
for i in range(60):
    ob = prim("plane", "Blatt%02d" % i, (0, 0, -5), (0.21, 0.297, 1), m=paper_m)
    FLYERS.append({"ob": ob, "seed": i, "x": (hsh(i * 1.3) - 0.5) * 5, "y": -2.0 + hsh(i * 2.9) * 5})
# Aktenschrank links vom Pult
CAB = empty("Aktenschrank", (-2.6, -1.8, 0), rot=(0, 0, math.radians(25)))
prim("cube", "Schrank", (0, 0, 0.7), (0.55, 0.6, 1.4), m=mat("Schrank", "#5d6b62", 0.4, metal=0.6), parent=CAB, bevel=0.01)
DRAWER = prim("cube", "Schublade", (0, 0.05, 1.05), (0.5, 0.6, 0.3), m=mat("Schublade", "#6f7e74", 0.4, metal=0.6), parent=CAB, bevel=0.01)
text("SchildSchrank", "AKTEN A–Z\n(GEGESSEN)", size=0.04, m=mat("Tinte", "#1a1a1a", 0.6), parent=DRAWER, loc=(0, 0.31, 0.02),
     rot=(math.radians(90), 0, math.pi), fnt="courier")

# ------------------------------------------------------------------ Pult aus Fernsehern
DESK = empty("Pult", (0, -1.6, 0))
DESK_TVS = []
for i, x in enumerate((-0.75, 0.0, 0.75)):
    s = tv("PultTV%d" % i, (x, 0.55, 0.0), size=0.72, casing="#2a2a2e", base="#1b3fa8", parent=DESK, knobs=False)
    DESK_TVS.append(s)
screen_text(DESK_TVS[0], "MINO", 0.32, "#ffffff")
screen_text(DESK_TVS[1], "1", 0.5, "#ffd23c")
screen_text(DESK_TVS[2], "LIVE", 0.32, "#ffffff")
prim("cube", "Pultplatte", (0, 0.2, 0.6), (2.4, 0.9, 0.06), m=mat("Pultplatte", "#1a1a22", 0.25, coat=0.6), parent=DESK, bevel=0.01)
akte("PultAkte", (0.55, 0.15, 0.635), rot_z=0.2, label="AKTE 001\nCHICKEN GUY", parent=DESK)
akte("PultAkte2", (0.6, 0.1, 0.66), rot_z=-0.15, col="#e7a0a8", parent=DESK)

# ------------------------------------------------------------------ Figuren
skin_light = mat("HautHell", "#e2b8a0", 0.5, sss=0.25)
skin_dark = mat("HautDunkel", "#5a3624", 0.45, sss=0.2)


def _gauss(p, c, r):
    d = (p - c).length / r
    return math.exp(-d * d)


def sculpt_head(name, size, deforms, mouth, m_skin, m_lip, m_inner, parent, loc=(0, 0, 0), seg=(72, 48), open_keys=True, hole=True):
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
                return Vector((0, -0.08 * w, -0.5 * w))
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
    for sx in (-1, 1):
        prim("cyl", "MM_bein%d" % sx, (sx * 0.13, 0, 0.42), (0.18, 0.2, 0.84), m=suit, parent=R)
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
    return {"root": R, "head": head, "neck": neck, "arms": arms, "mouth": mouth, "glint": glint, "torso": torso}


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
    CG_DEF = [
        ((0, 0.9, 0.5), 0.4, (0, 0.03, 0.03)),
        ((0.34, 0.93, 0.22), 0.2, (0, -0.09, 0)), ((-0.34, 0.93, 0.22), 0.2, (0, -0.09, 0)),
        ((0, 0.97, 0.38), 0.32, (0, 0.04, 0)),            # Brauenwulst
        ((0, 1.0, 0.05), 0.12, (0, 0.07, 0)),
        ((0, 1.0, -0.1), 0.2, (0, 0.26, -0.02)),          # breite Nase
        ((0.17, 0.95, -0.14), 0.13, (0.04, 0.1, 0)), ((-0.17, 0.95, -0.14), 0.13, (-0.04, 0.1, 0)),
        ((0.5, 0.78, -0.12), 0.32, (0.04, 0.06, 0)), ((-0.5, 0.78, -0.12), 0.32, (-0.04, 0.06, 0)),
        ((0, 0.95, -0.42), 0.32, (0, 0.13, 0)),           # volle Mundpartie
        ((0, 0.9, -0.8), 0.28, (0, 0.05, -0.05)),
        ((0.62, 0.4, -0.45), 0.45, (0.1, 0, 0)), ((-0.62, 0.4, -0.45), 0.45, (-0.1, 0, 0)),
        ((0, 0.0, 1.0), 0.5, (0, 0, -0.06)),
    ]
    skull = sculpt_head("CG_kopfmesh", HS, CG_DEF, (-0.42, 0.26, 0.03), skin_dark, mat("LippenDunkel", "#4a2420", 0.5),
                        mat("Mundhoehle", "#2a0508", 0.6), head, loc=HL)
    hair = noise_mat("HaarSchwarz", "#060606", "#1a1512", scale=60, rough=0.8, bump=0.5)
    hair_cap("CG_haar", HS, CG_DEF, lambda x, y: lerp(-0.1, 0.58, smooth((y + 0.3) / 0.9)), hair, head, loc=HL, grow=1.03)
    for sx in (-1, 1):
        prim("sphere", "CG_ohr%d" % sx, (sx * 0.3, -0.02, 0.36), (0.07, 0.11, 0.16), rot=(0, sx * 0.2, 0), m=skin_dark, parent=head)
    cheeks = []
    # Augen mit Lidern (in den Augenhöhlen)
    eye_w = mat("Augenweiss", "#efe9e2", 0.25, coat=0.6)
    iris = mat("Iris", "#1b0f0a", 0.2, coat=1.0)
    eyes = {}
    lid_m = skin_dark
    lash_m = mat("Wimpern", "#0b0605", 0.6)
    for sx in (-1, 1):
        ec = empty("CG_auge%d" % sx, unit_to_local(HS, (sx * 0.33, 0.8, 0.22), HL), head)
        prim("sphere", "CG_augapfel%d" % sx, (0, 0, 0), (0.1, 0.08, 0.075), m=eye_w, parent=ec)
        pup = prim("sphere", "CG_pupille%d" % sx, (0, 0.031, 0), (0.055, 0.022, 0.055), m=iris, parent=ec)
        glz = prim("sphere", "CG_glanz%d" % sx, (0.012, 0.045, 0.014), (0.012, 0.006, 0.012), m=emit_mat("Glanz", "#ffffff", 8), parent=ec)
        lids = []
        for up in (1, -1):
            piv = empty("CG_lid%d%d" % (sx, up), (0, -0.005, 0), ec)
            lid = half_sphere("CG_lidhaut%d%d" % (sx, up), up, (0.118, 0.114, 0.092), lid_m, piv)
            if up > 0:   # dunkle Wimpernlinie an der Lidkante, damit zugekniffene Augen lesbar sind
                arc = [Vector((0.061 * math.cos(a), 0.059 * math.sin(a), 0.0)) for a in
                       (math.radians(d) for d in range(15, 170, 15))]
                curve_obj("CG_wimper%d" % sx, arc, radius=0.008, m=lash_m, parent=piv)
            lids.append(piv)
        brow = curve_obj("CG_braue%d" % sx, [Vector((-0.07, 0, -0.012)), Vector((0, 0, 0.012)), Vector((0.07, 0, -0.012))],
                         radius=0.016, m=hair, parent=empty("CG_braue_piv%d" % sx, unit_to_local(HS, (sx * 0.34, 0.97, 0.44), HL), head))
        eyes[sx] = {"c": ec, "pupil": pup, "lids": lids, "brow": brow.parent, "glanz": glz}
    # Mundinneres: dunkle Höhle, obere Zähne mit Lücke, Unterkiefer mit Zähnen und Zunge
    mouth = empty("CG_mund", unit_to_local(HS, (0, 0.78, -0.42), HL), head)
    cav = prim("sphere", "CG_mundhoehle", (0, -0.05, -0.04), (0.22, 0.14, 0.2), m=mat("Mundhoehle", "#2a0508", 0.6), parent=mouth)
    teeth_m = mat("Zaehne", "#f4efe2", 0.25, coat=0.5)
    uteeth = empty("CG_zaehne_oben", (0, 0.0, 0.0), mouth)
    for i, x in enumerate((-0.07, -0.045, -0.02, 0.02, 0.045, 0.07)):   # Lücke in der Mitte
        prim("cube", "CG_zahn_o%d" % i, (x, 0.0, -0.005), (0.022, 0.018, 0.03), m=teeth_m, parent=uteeth, bevel=0.004)
    jaw = empty("CG_kiefer", (0, -0.01, 0.0), mouth)
    for i, x in enumerate((-0.05, -0.017, 0.017, 0.05)):
        prim("cube", "CG_zahn_u%d" % i, (x, 0.0, 0.0), (0.02, 0.014, 0.024), m=teeth_m, parent=jaw, bevel=0.004)
    tongue = prim("sphere", "CG_zunge", (0, -0.03, -0.01), (0.15, 0.1, 0.05), m=mat("Zunge", "#c2525a", 0.35, sss=0.3), parent=jaw)
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


MM = build_minoman((0, -1.95, 0.0))
CG = build_chickenguy((0, -3.3, 0.0))
HS_CG = (0.31, 0.3, 0.39)
BROW_Z = CG["eyes"][1]["brow"].location.z      # steht später oben auf dem TV-Berg
MU = build_munch((-2.15, -1.3, 0.0))
MU["root"].rotation_euler.z = math.radians(30)
GM = build_grandma((1.05, 3.0, 0.0))
GM["root"].rotation_euler.z = math.radians(40)
GM_TV = tv("GrandmaTV", (1.75, 3.55, 0.0), size=0.8, casing="#cfc6b4", base="#1f4fd0", rot_z=math.radians(20))
screen_text(GM_TV, "PEPSI GRANDMA", 0.12, "#ffffff", y_rel=0.25)
screen_text(GM_TV, "EMPFIEHLT:", 0.1, "#ffffff", y_rel=0.05)
screen_text(GM_TV, "NOCH EINE!", 0.18, "#ffe34a", y_rel=-0.2)

# Chicken Guy steht auf einem Podest aus Fernsehern vor dem Berg
PODEST = []
for i, (x, zz, sz) in enumerate([(-0.35, 0.0, 0.7), (0.35, 0.0, 0.7), (0.0, 0.55, 0.75)]):
    s = tv("PodestTV%d" % i, (x, -2.55, zz), size=sz, casing="#2a2a2e", base="#c4002a")
    screen_text(s, "VERMISST", 0.2, "#ffffff")
    PODEST.append(s)
CG["root"].location = (0, -2.75, 1.13)
CG["root"].scale = (0.75, 0.75, 0.75)

# ------------------------------------------------------------------ Kamera
cam_data = bpy.data.cameras.new("Kamera")
cam_data.lens = 28
cam_data.clip_start = 0.02
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 2.8
CAM = bpy.data.objects.new("Kamera", cam_data)
link(CAM)
scn.camera = CAM
FOCUS = empty("Fokus", (0, 0, 1))
cam_data.dof.focus_object = FOCUS


def look(cam_pos, target, roll=0.0, lens=None):
    CAM.location = cam_pos
    d = Vector(target) - Vector(cam_pos)
    rot = d.to_track_quat("-Z", "Y").to_euler()
    rot.rotate_axis("Z", roll)
    CAM.rotation_euler = rot
    FOCUS.location = target
    if lens:
        cam_data.lens = lens


# ------------------------------------------------------------------ Ausdrücke Chicken Guy
EXPR = {
    #            open  wide  lid   brow  tilt  teeth tongue cheek
    "neutral":  (0.05, 1.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0),
    "schrei":   (1.0, 0.85, 0.92, -0.6, -0.12, 1.0, 1.0, 0.8),   # wie im Original: Augen zugekniffen, Brauen runter
    "ekstase":  (0.75, 0.6, 1.0, 0.7, -0.35, 0.6, 0.6, 0.4),
    "grimasse": (0.35, 1.35, 0.55, -0.6, 0.15, 1.0, 0.0, 0.6),
    "boah":     (0.6, 0.7, 0.0, 1.0, 0.0, 0.3, 0.3, 0.2),
    "zwinker":  (0.2, 1.2, 0.4, 0.4, 0.2, 0.8, 0.0, 0.3),
}
# Ausdruck pro Schlag im Drop-Teil (zyklisch)
EXPR_SEQ = ["schrei", "schrei", "grimasse", "ekstase", "boah", "schrei", "zwinker", "ekstase"]


EXPR_FORCE = None


def expr_at(t):
    if EXPR_FORCE:
        return EXPR[EXPR_FORCE]
    b = beat_of(t)
    if b < DROP - 0.5:
        return EXPR["boah"] if b > DROP - 2 else EXPR["neutral"]
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
    kb["laecheln"].value = cheek * 0.6 if wide > 1.1 else 0.0
    rz = HS_CG[2]
    m["jaw"].location.z = -op * 0.5 * rz * 0.85
    m["jaw"].location.y = -op * 0.08 * HS_CG[1]
    m["uteeth"].location.z = op * 0.1 * rz * 0.6 + teeth * 0.012
    m["uteeth"].scale = (1.0, 1.0, 0.6 + teeth * 0.6)
    m["cav"].scale = (0.22, 0.14, 0.06 + op * 0.2)
    m["cav"].location.z = -0.02 - op * 0.08
    m["tongue"].location = (0, -0.03 + tongue * 0.03, -0.01 + tongue * 0.015)
    blink = 1.0 if (t % 3.1) < 0.09 else 0.0
    for sx, e in m["eyes"].items():
        l = clamp(max(lid, blink * (lid < 0.9)))
        # Halbkugel-Lider: Achse nach hinten = offen, nach vorn = zu
        e["lids"][0].rotation_euler.x = lerp(1.4, -0.95, l)
        e["lids"][1].rotation_euler.x = lerp(-1.4, -0.35, l * 0.8)
        e["glanz"].scale = (0.012, 0.006, 0.012) if l < 0.7 else (0, 0, 0)
        b_ = brow + (0.25 if (sx > 0 and EXPR_SEQ[int(max(0, beat_of(t) - DROP)) % len(EXPR_SEQ)] == "zwinker") else 0)
        e["brow"].location.z = BROW_Z + b_ * 0.05
        e["brow"].rotation_euler.y = -sx * b_ * 0.2
        e["pupil"].location.x = math.sin(t * 2.3 + sx) * 0.01
    m["head"].rotation_euler.x = tilt


# ------------------------------------------------------------------ Animation pro Frame
STAMPS = []


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


def animate(t):
    b = beat_of(t)
    hit = pulse(t, 0.14, 1, 0, NB)
    hit_drop = pulse(t, 0.16, 1, DROP, NB)
    build = smooth((b - 8) / (DROP - 8))
    end_off = b >= NB - 2

    # --- Bildschirme
    for i, s in enumerate(SCREENS):
        if s is HERO:
            if b < 1:
                set_screen(s, 0.0, 1.0, t=t)
            elif b < 2.5:
                set_screen(s, 1.0, 1.0 - smooth(b - 1.5), t=t)
            else:
                set_screen(s, 1.0, 0.0, flash=0.6 * pulse(t, 0.1, 4, 0, NB), t=t)
            continue
        on_beat = 3 + (i * 0.37) % 6           # gehen nacheinander an
        on = 1.0 if b >= on_beat else 0.0
        st = 1.0 if (b >= on_beat and b < on_beat + 0.5) else 0.0
        # vor dem Drop flackern sie immer schneller ins Rauschen
        if DROP - 4 <= b < DROP:
            rate = 2 ** int((b - (DROP - 4)) + 1)
            st = 1.0 if (hsh(i + int(b * rate) * 13) > 0.6) else st
        fl = 0.0
        if b >= DROP:
            fl = 0.85 * hit_drop * (1 if (i + int(b)) % 3 == 0 else 0.35)
            if (b - DROP) < 0.5:
                fl = 1.0
        if DROP - 0.5 <= b < DROP:
            fl = smooth((b - (DROP - 0.5)) / 0.5)
        if end_off:
            k = (b - (NB - 2)) / 2
            on = 0.0 if hsh(i * 3.7) < k * 1.4 else on
        set_screen(s, on, st, fl, t)

    # --- Kabel-Puls
    CABLE_NODES["phase"].outputs[0].default_value = (t / BEAT) * 3.0 * (2 if b >= DROP else 1)
    CABLE_NODES["glow"].outputs[0].default_value = (0.0 if b < 4 else 2.0 + 10 * build) * (1 + 2 * hit_drop) * (0 if end_off else 1)

    # --- Ticker
    TICKER.location.x = -4.0 + t * 0.9

    # --- Neonlogo flackert beim Einschalten, pulsiert im Drop
    logo_on = 0 if b < 6 else (1 if b >= 7 or int(b * 8) % 2 else 0)
    MATS["Neon"].node_tree.nodes["Emission"].inputs[1].default_value = (4 + 14 * hit_drop) * logo_on * (0 if end_off else 1)

    # --- Licht
    FILL.data.energy = 60 + 400 * hit_drop
    KEY.data.energy = 260 * (0.3 if b < 4 else 1.0)

    # --- Chicken Guy: tanzt immer, ab dem Drop völlig entfesselt
    wild = 0.25 + 0.75 * smooth((b - (DROP - 0.25)) / 0.25)
    if not DANCE:
        wild = 0.0
    ph = t / BEAT * math.pi
    body = CG["body"]
    body.location.z = CG_BZ + abs(math.sin(ph)) * 0.12 * wild
    body.scale = (CG_BS[0] * (1 + hit_drop * 0.08), CG_BS[1] * (1 + hit_drop * 0.08), CG_BS[2] * (1 - hit_drop * 0.1))
    body.rotation_euler = (0, math.sin(ph) * 0.18 * wild, math.sin(ph * 0.5) * 0.35 * wild)
    for sx, (sh, el, tip) in CG["wings"].items():
        flap = math.sin(ph * 2 + (0 if sx > 0 else math.pi * 0.5))
        sh.rotation_euler = (0, -sx * (0.4 + flap * 0.9 * wild), sx * math.sin(ph) * 0.4 * wild)
        el.rotation_euler = (0, -sx * (0.6 + math.sin(ph * 2 + 1) * 0.9 * wild), 0)
        tip.rotation_euler = (0, -sx * math.sin(ph * 4) * 0.5 * wild, 0)
    for sx, hip in CG["legs"].items():
        hip.rotation_euler = (math.sin(ph + (0 if sx > 0 else math.pi)) * 0.5 * wild, 0, 0)
    CG["neck"].rotation_euler = (math.sin(ph * 2) * 0.12 * wild + hit_drop * 0.15, math.sin(ph) * 0.2 * wild, math.sin(ph * 0.5) * 0.25 * wild)
    apply_face(t)
    # Chicken Guy ist vermisst: in den letzten Schlägen flackert er weg
    vis = 1.0 if b < NB - 4 else (0.0 if b >= NB - 3.5 else float(int(b * 16) % 2))
    CG["root"].scale = (0.75 * vis,) * 3

    # --- Mino Man: deadpan, minimaler Nicken auf die Zählzeit, dreht am Ende den Kopf zur Kamera
    MM["neck"].rotation_euler = (hit * 0.03, 0, lerp(0.0, -0.25, smooth((b - 40) / 1)) if b < 44 else -0.25)
    for sx, (sh, el) in MM["arms"].items():   # Hände auf dem Pult
        sh.rotation_euler = (math.radians(-38), sx * 0.05, 0)
        el.rotation_euler = (math.radians(-55), 0, 0)
    MM["glint"].scale = (0.022 * (1 + 2 * pulse(t, 0.25, 8, 4, NB)), 0.006, 0.012)
    if end_off:
        MM["glint"].scale = (0.03, 0.006, 0.02)

    # --- Officer Munch kaut die Akte, Bissen auf jedem zweiten Schlag
    bite = pulse(t, 0.12, 2, 0, NB)
    MU["fore"].rotation_euler = (math.radians(-95) - bite * 0.25, 0, math.radians(-25))
    MU["arm"].rotation_euler = (math.radians(-40), 0, math.radians(20))
    MU["jaw"].scale = (0.1, 0.03, 0.03 + bite * 0.05)
    eaten = clamp((b - 9) / 28)
    MU["folder"].scale = (1 - eaten * 0.85, 1 - eaten * 0.4, 1)
    MU["head"].rotation_euler = (0.15 * bite, 0, math.sin(t * 0.7) * 0.1)
    for i, c in enumerate(MU["crumbs"]):
        tb = (t - B(int(b / 2) * 2)) + i * 0.02
        if b > 9 and tb < 0.6:
            c.location = (MU["root"].location.x + 0.3 + (hsh(i) - .5) * 0.2, MU["root"].location.y + 0.25 + tb * 0.3, 1.4 - tb * tb * 4)
            c.rotation_euler = (t * 9 + i, t * 7, 0)
        else:
            c.location = (0, 0, -5)

    # --- Pepsi Grandma: Fontäne auf dem Drop und auf Schlag 28
    GM["arm"].rotation_euler = (math.radians(-60) + math.sin(t * 9) * 0.25 * (b > DROP - 2), 0, 0)
    for i, f in enumerate(GM["foam"]):
        best = None
        for t0 in (B(DROP), B(28)):
            if t0 <= t < t0 + 1.4:
                best = t0
        if best is None:
            f.location = (0, 0, -5)
            continue
        tt = t - best - (i % 10) * 0.02
        if tt < 0:
            f.location = (0, 0, -5)
            continue
        bw = GM["bottle"].matrix_world.translation
        ang = hsh(i * 3.3) * math.tau
        v = Vector((math.cos(ang) * 0.35, math.sin(ang) * 0.35 + 0.6, 2.6 + hsh(i) * 1.2))
        f.location = bw + v * tt + Vector((0, 0, -4.9 * tt * tt))
        s_ = 0.05 + hsh(i * 7) * 0.06
        f.scale = (s_, s_, s_)

    # --- Blätter fliegen im Drop hoch und regnen herab
    for fl_ in FLYERS:
        i = fl_["seed"]
        tt = t - B(DROP) - hsh(i) * 0.3
        if tt < 0 or b > NB - 1:
            fl_["ob"].location = (0, 0, -5)
            continue
        up = 5.5 + hsh(i * 2) * 3
        z_ = 0.3 + up * tt - 2.2 * tt * tt
        if z_ < 0.01:
            z_ = 0.01 + 0.0 * tt
        fl_["ob"].location = (fl_["x"] + math.sin(tt * 2 + i) * 0.6, fl_["y"] + math.cos(tt * 1.7 + i) * 0.5, z_)
        fl_["ob"].rotation_euler = (tt * (2 + hsh(i) * 4), tt * 3 * (hsh(i * 5) - .5), tt * 2)

    # --- Schublade des Aktenschranks springt auf jedem Takt im Drop auf
    DRAWER.location.y = 0.05 + 0.3 * pulse(t, 0.2, 4, DROP, NB)

    # --- Kamera
    camera(t, b)


CAM_OVERRIDE = None
DANCE = True


def camera(t, b):
    if CAM_OVERRIDE:
        return CAM_OVERRIDE()
    shake = 0.02 * pulse(t, 0.12, 1, DROP, NB)
    sx, sy = math.sin(t * 61) * shake, math.cos(t * 47) * shake
    hero = Vector(HERO["root"].location) + Vector((-0.09, 0.0, 0.47))
    if b < 4:                                    # Kaltstart: ganz nah an der Röhre, dann Rückzug
        k = ease_inout(b / 4)
        look(vlerp(hero + Vector((0, 0.5, 0)), hero + Vector((0.3, 3.4, 0.5)), k), hero, roll=0.04 * (1 - k), lens=lerp(40, 26, k))
    elif b < 8:                                  # über den Fernseher hinweg in den Korridor
        k = ease_inout((b - 4) / 4)
        p = vlerp(hero + Vector((0.3, 3.4, 0.5)), Vector((0.6, 9.0, 2.6)), k)
        look(p, vlerp(hero, Vector((0, 0, 1.2)), k), lens=26)
    elif b < 12:                                 # Fahrt durch den Gang, vorbei an Grandma
        k = (b - 8) / 4
        e = ease_inout(k)
        p = vlerp((0.6, 9.0, 2.7), (-0.55, 4.4, 1.5), e)
        p.z += math.sin(e * math.pi) * 0.5          # über den Hero-Fernseher hinweg
        gm = Vector(GM["root"].location)
        look(p, vlerp(gm + Vector((0.2, 0.0, 0.9)), gm + Vector((0.2, 0.3, 1.25)), k), lens=24)
    elif b < 14:                                 # Munch isst die Akte
        k = (b - 12) / 2
        mu = Vector(MU["root"].location) + Vector((0.1, 0.2, 1.45))
        p = vlerp(mu + Vector((1.4, 2.2, 0.0)), mu + Vector((0.9, 1.4, 0.1)), ease_out(k))
        look(p, mu, lens=32)
    elif b < DROP:                               # Steigerung: schneller Zug auf Chicken Guy, der sich noch versteckt
        k = ease_inout((b - 14) / (DROP - 14))
        cg = Vector(CG["root"].location) + Vector((0, 0, 1.25))
        look(vlerp((0.0, 3.0, 1.0), cg + Vector((0.0, 2.2, 0.15)), k), cg, roll=0.15 * k, lens=lerp(22, 30, k))
    elif b < 28:                                 # DROP: Orbit um den schreienden Chicken Guy
        k = (b - DROP) / (28 - DROP)
        cg = Vector(CG["root"].location) + Vector((0, 0, 1.3))
        ang = lerp(-0.3, 0.85, ease_inout(k)) if b < 24 else lerp(0.85, -0.7, ease_inout((b - 24) / 4))   # nur vorne, Gesicht bleibt sichtbar
        r = 1.9 if (int(b - DROP) // 2) % 2 == 0 else 1.35   # Zoom-Stöße alle 2 Schläge
        p = cg + Vector((math.sin(ang) * r, math.cos(ang) * r, -0.15 + 0.2 * math.sin(k * 6)))
        look(p + Vector((sx, 0, sy)), cg + Vector((0, 0, 0.1)), roll=math.sin(b * math.pi / 2) * 0.12, lens=30)
    elif b < 32:                                 # Grandma-Fontäne
        k = (b - 28) / 4
        gm = Vector(GM["root"].location) + Vector((0, 0, 1.3))
        look(gm + Vector((-1.3 + k * 0.3, 1.5, 0.3 + k * 0.6)) + Vector((sx, 0, sy)), gm + Vector((0.2, 0, 0.5 + k * 0.8)), lens=26)
    elif b < NB - 4:                             # Totale der Welt, dann langsam auf Mino Man
        k = ease_inout((b - 32) / (NB - 4 - 32))
        mm = Vector(MM["root"].location) + Vector((0, 0, 1.75))
        look(vlerp((0.0, 7.5, 3.8), mm + Vector((0.15, 1.6, 0.05)), k), vlerp((0, -3, 2.2), mm, k), lens=lerp(22, 38, k))
    else:                                        # Schluss: ganz nah, Fernseher gehen aus, nur der Brillenreflex bleibt
        k = ease_out((b - (NB - 4)) / 4)
        mm = Vector(MM["root"].location) + Vector((0, 0, 1.78))
        look(vlerp(mm + Vector((0.15, 1.6, 0.05)), mm + Vector((0.05, 0.85, 0.02)), k), mm, lens=lerp(38, 45, k))


def on_frame(scene, depsgraph=None):
    t = (scene.frame_current - 1) / FPS
    animate(t)


bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(on_frame)

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
    for attr, val in (("use_bloom", True), ("bloom_intensity", 0.08), ("use_gtao", True), ("use_volumetric_shadows", False),
                      ("volumetric_tile_size", "4"), ("use_raytracing", True)):
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

out = opt("--out", os.path.join(HERE, "out", "mino_kabel_reel.mp4"))
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
        scn.frame_set(int(B(DROP + 0.5 if who == "cg" else 36) * FPS) + 1)
        bpy.context.view_layer.update()
        if who == "cg":
            hd = CG["head"].matrix_world.translation + Vector((0, 0, 0.3 * 0.75))
            cam_args = (hd + Vector((0.2, 1.3, 0.05)), hd, 0.0, 60)
        elif who == "cgauge":   # Detail: rechtes Auge
            hd = CG["eyes"][1]["c"].matrix_world.translation.copy()
            cam_args = (hd + Vector((0.05, 0.5, 0.04)), hd, 0.0, 120)
        elif who == "cgk":   # ganzer Körper
            hd = CG["root"].matrix_world.translation + Vector((0, 0, 0.75))
            cam_args = (hd + Vector((0.3, 3.2, 0.1)), hd, 0.0, 50)
        else:
            obj = {"mm": MM, "mu": MU, "gm": GM}[who]
            hd = obj["head"].matrix_world.translation + Vector((0, 0, 0.15))
            cam_args = (hd + Vector((0.15, 1.0, 0.0)), hd, 0.0, 60)
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

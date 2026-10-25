#!/usr/bin/env python3
"""Baut den realistischen Chicken-Guy-Kopf aus dem MakeHuman-Basismesh (hm08, CC0) als kompakte Datei für das Reel.

  python build_cg_head.py --mh <Ordner mit ext/ und assets/ aus MPFB + MakeHuman system assets> --out <Zielordner>

Ablauf (reines numpy, kein Blender nötig):
  1. base.obj lesen, Makro-Targets (Mann, jung, afrikanisch, etwas fülliger) und Gesichtsform-Targets anwenden
  2. Augen, Zähne, Zunge, Brauen, Wimpern über die .mhclo-Dateien auf den geformten Kopf setzen
  3. die afrikanischen Ausdrucks-Targets (Augen zu/Schlitz/weit, Mund auf, Mundwinkel ...) als Shape Keys backen,
     dabei Zähne, Zunge und Wimpern jedes Mal neu anpassen (Mund auf bewegt den Unterkiefer mit den Zähnen)
  4. nur den Kopf behalten (Schnitt am Hals), nach Blender-Achsen (Z oben, Meter) drehen
Ergebnis: cg_head.npz (Geometrie, UVs, Teile, Shape Keys) + cg_head.json (Texturen, Augenmittelpunkte) + Texturen.
Die MakeHuman-Assets sind CC0; sie bleiben trotzdem außerhalb des Repos (nur dieses Skript liegt hier).
"""
import argparse
import gzip
import json
import os
import shutil

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--mh", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()
EXT = os.path.join(args.mh, "ext", "data")
AS = os.path.join(args.mh, "assets")
os.makedirs(args.out, exist_ok=True)


# ------------------------------------------------------------------ Lesen
def read_obj(path):
    V, VT, F, FT, G = [], [], [], [], []
    grp = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g "):
            grp = line.split(None, 1)[1].strip()
        elif line.startswith("f "):
            vs, ts = [], []
            for tok in line.split()[1:]:
                p = tok.split("/")
                vs.append(int(p[0]) - 1)
                ts.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
            F.append(vs)
            FT.append(ts)
            G.append(grp)
    return np.array(V, float), np.array(VT, float), F, FT, G


def read_target(path):
    idx, d = [], []
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, int), np.array(d, float).reshape(-1, 3)


def tpath(rel):
    return os.path.join(EXT, "targets", rel + ".target.gz")


def read_mhclo(path):
    head, rows = {}, []
    in_verts = False
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        if in_verts:
            try:
                nums = [float(x) for x in p]
            except ValueError:
                in_verts = False
            else:
                if len(nums) == 1:
                    rows.append((int(nums[0]), int(nums[0]), int(nums[0]), 1.0, 0.0, 0.0, 0.0, 0.0, 0.0))
                elif len(nums) >= 9:
                    rows.append((int(nums[0]), int(nums[1]), int(nums[2])) + tuple(nums[3:9]))
                continue
        if p[0] == "verts":
            in_verts = True
        elif p[0] in ("x_scale", "y_scale", "z_scale"):
            head[p[0]] = (int(p[1]), int(p[2]), float(p[3]))
        elif p[0] in ("obj_file", "material"):
            head[p[0]] = p[1]
    R = np.array(rows, float)
    return head, R[:, :3].astype(int), R[:, 3:6], R[:, 6:9]


class Proxy:
    def __init__(self, folder, name):
        self.dir = os.path.join(AS, folder)
        self.head, self.ref, self.w, self.off = read_mhclo(os.path.join(self.dir, name + ".mhclo"))
        self.V, self.VT, self.F, self.FT, _ = read_obj(os.path.join(self.dir, self.head.get("obj_file", name + ".obj")))
        self.name = name

    def fit(self, B):
        sc = np.ones(3)
        for k, ax in (("x_scale", 0), ("y_scale", 1), ("z_scale", 2)):
            if k in self.head:
                a, b, den = self.head[k]
                sc[ax] = abs(B[a, ax] - B[b, ax]) / den
        P = (B[self.ref[:, 0]] * self.w[:, :1] + B[self.ref[:, 1]] * self.w[:, 1:2] + B[self.ref[:, 2]] * self.w[:, 2:3])
        return P + self.off * sc


BV, BVT, BF, BFT, BG = read_obj(os.path.join(EXT, "3dobjs", "base.obj"))
vg = json.load(open(os.path.join(EXT, "mesh_metadata", "basemesh_vertex_groups.json")))


def group(k):
    s = set()
    for a, b in vg[k]:
        s.update(range(a, b + 1))
    return s


def joint(k, P=None):
    return (BV if P is None else P)[sorted(group(k))].mean(0)


# ------------------------------------------------------------------ Form: Makro + Gesicht
SHAPE = {
    # Makro: Mann, jung (≈25), afrikanisch, durchschnittliche Muskeln, etwas mehr Gewicht
    "macrodetails/universal-male-young-averagemuscle-averageweight": 0.45,
    "macrodetails/universal-male-young-averagemuscle-maxweight": 0.55,
    "macrodetails/african-male-young": 1.0,
    # Ei-Kopf: unten breit, oben schmaler, volle Wangen
    "head/head-oval": 0.55, "head/head-fat-incr": 0.65, "head/head-age-decr": 0.4, "head/head-scale-vert-incr": 0.15,
    "cheek/l-cheek-volume-incr": 0.3, "cheek/r-cheek-volume-incr": 0.3,
    "cheek/l-cheek-bones-decr": 0.3, "cheek/r-cheek-bones-decr": 0.3,
    "chin/chin-width-incr": 0.45, "chin/chin-height-decr": 0.15, "chin/chin-prominent-decr": 0.2,
    "forehead/forehead-scale-vert-decr": 0.2, "forehead/forehead-temple-decr": 0.35,
    # kurze, breite Nase mit weiten Nasenflügeln
    "nose/nose-flaring-incr": 0.75, "nose/nose-scale-horiz-incr": 0.45, "nose/nose-volume-incr": 0.35,
    "nose/nose-nostrils-width-incr": 0.6, "nose/nose-point-width-incr": 0.5, "nose/nose-scale-vert-decr": 0.3,
    "nose/nose-hump-decr": 0.4,
    # volle Lippen, breiter Mund
    "mouth/mouth-lowerlip-volume-incr": 0.75, "mouth/mouth-upperlip-volume-incr": 0.35, "mouth/mouth-scale-horiz-incr": 0.35,
    "mouth/mouth-lowerlip-height-incr": 0.35, "mouth/mouth-upperlip-height-incr": 0.2, "mouth/mouth-cupidsbow-decr": 0.3,
    # Augen: normal groß und offen, aber schwere Oberlider (müder Blick wie im Video)
    "eyes/l-eye-scale-incr": 0.5, "eyes/r-eye-scale-incr": 0.5,
    "eyes/l-eye-eyefold-down": 0.3, "eyes/r-eye-eyefold-down": 0.3,
    "eyes/l-eye-height2-incr": 0.25, "eyes/r-eye-height2-incr": 0.25,
    "eyes/l-eye-bag-incr": 0.35, "eyes/r-eye-bag-incr": 0.35,
    "eyebrows/eyebrows-trans-down": 0.25,
    "neck/neck-double-incr": 0.6, "neck/neck-scale-horiz-incr": 0.4,
}
SHAPE.update(json.load(open(os.environ["CG_SHAPE"])) if os.environ.get("CG_SHAPE") else {})

M = BV.copy()
for rel, w in SHAPE.items():
    if not w or not os.path.exists(tpath(rel)):
        if w:
            print("fehlt:", rel)
        continue
    i, d = read_target(tpath(rel))
    M[i] += d * w

# ------------------------------------------------------------------ Proxies
PROX = {
    "teeth": Proxy("teeth/teeth_base", "teeth_base"),
    "tongue": Proxy("tongue/tongue01", "tongue01"),
    "brows": Proxy("eyebrows/eyebrow001", "eyebrow001"),
    "lashes": Proxy("eyelashes/eyelashes01", "eyelashes01"),
    "eyes": Proxy("eyes/high-poly", "high-poly"),
}

# ------------------------------------------------------------------ Kopf ausschneiden
J_NECK, J_HEAD, J_JAW = joint("joint-neck", M), joint("joint-head", M), joint("joint-jaw", M)
body_faces = [k for k, g in enumerate(BG) if g == "body"]
cut_y = J_JAW[1] - float(os.environ.get("CG_CUT", "0.15"))          # knapp unter dem Kinn: Kopf sitzt ohne Hals auf dem Hähnchen
keep_f = [k for k in body_faces if min(M[v, 1] for v in BF[k]) > cut_y and abs(np.mean([M[v, 0] for v in BF[k]])) < 1.35]
keep_v = sorted({v for k in keep_f for v in BF[k]})
remap = {v: n for n, v in enumerate(keep_v)}
print("Kopf: %d Flächen, %d Punkte, Schnitt bei y=%.3f" % (len(keep_f), len(keep_v), cut_y))

# Mirror-Tabelle (für die rechten Wimpern, die das Augen-zu-Target rechts nicht mitbewegt)
MIRROR = {}
for line in open(os.path.join(EXT, "mesh_metadata", "hm08.mirror")):
    p = line.split()
    if len(p) >= 2:
        MIRROR[int(p[0])] = int(p[1])


# ------------------------------------------------------------------ Kurze Haare: Schale über der Kopfhaut
def vnormals(P, flist):
    N = np.zeros_like(P)
    for f in flist:
        a, b, c = P[f[0]], P[f[1]], P[f[2]]
        n = np.cross(b - a, c - a)
        for v in f:
            N[v] += n
    return N / np.maximum(1e-9, np.linalg.norm(N, axis=1))[:, None]


NRM = vnormals(M, [BF[k] for k in keep_f])
EYE_Y = joint("joint-l-eye", M)[1]            # Augenhöhe (MH: y oben, z vorne)
FRONT_Z = M[keep_v, 2].max()
BACK_Z = M[keep_v, 2].min()


def is_scalp(p):
    x, y, z = p
    k = np.clip((FRONT_Z - 0.25 - z) / max(0.1, (FRONT_Z - BACK_Z) * 0.75), 0, 1)
    k = k * k * (3 - 2 * k)
    line = EYE_Y + float(os.environ.get("CG_HAIRLINE", "0.78")) * (1 - k) - 0.95 * k   # vorne hoch, hinten tief (Nacken)
    if abs(x) > 0.62 and z > (FRONT_Z + BACK_Z) / 2 - 0.15 and y < EYE_Y + 0.42:   # Schläfen/Koteletten: nicht über die Ohren
        line = max(line, EYE_Y + 0.42)
    if abs(x) > 0.74 and y < EYE_Y + 0.35:      # Ohren freilassen
        return False
    return y > line


scalp_f = [k for k in keep_f if all(is_scalp(M[v]) for v in BF[k])]
scalp_v = sorted({v for k in scalp_f for v in BF[k]})
scalp_map = {v: n for n, v in enumerate(scalp_v)}
HAIR_OFF = float(os.environ.get("CG_HAIR_OFF", "0.018"))
# am Haaransatz auslaufen lassen (Randpunkte liegen fast auf der Haut), damit keine Helmkante entsteht
_edge_count = {}
for k in scalp_f:
    f = BF[k]
    for a_, b_ in zip(f, f[1:] + f[:1]):
        e = (min(a_, b_), max(a_, b_))
        _edge_count[e] = _edge_count.get(e, 0) + 1
_rim = {v for e, n in _edge_count.items() if n == 1 for v in e}
HAIR_W = np.array([0.15 if v in _rim else 1.0 for v in scalp_v])[:, None]
print("Haare: %d Flächen" % len(scalp_f))


# ------------------------------------------------------------------ Geometrie zusammensetzen
def assemble(Bm):
    """Alle Punkte des Kopfes + Proxies in fester Reihenfolge."""
    parts = [Bm[keep_v]]
    for k in ("teeth", "tongue", "brows", "lashes"):
        parts.append(PROX[k].fit(Bm))
    parts.append(Bm[scalp_v] + NRM[scalp_v] * HAIR_OFF * HAIR_W)
    return np.concatenate(parts)


NEUTRAL = assemble(M)
EYES = PROX["eyes"].fit(M)

# Flächen, UVs, Material pro Fläche
faces, fuv, fmat = [], [], []
uvs = []
PART_NAMES = ["skin", "teeth", "tongue", "brows", "lashes", "hair"]
offs = [0]
for k, n in zip(PART_NAMES, [len(keep_v)] + [len(PROX[k].V) for k in PART_NAMES[1:5]] + [len(scalp_v)]):
    offs.append(offs[-1] + n)
for k in keep_f:
    faces.append([remap[v] for v in BF[k]])
    fuv.append([BVT[t] for t in BFT[k]])
    fmat.append(0)
for pi, k in enumerate(PART_NAMES[1:5], start=1):
    pr = PROX[k]
    for vs, ts in zip(pr.F, pr.FT):
        faces.append([offs[pi] + v for v in vs])
        fuv.append([pr.VT[t] if t >= 0 else (0.0, 0.0) for t in ts])
        fmat.append(pi)

for k in scalp_f:
    faces.append([offs[5] + scalp_map[v] for v in BF[k]])
    fuv.append([BVT[t] for t in BFT[k]])
    fmat.append(5)

# Zahnlücken wie im Video: einzelne Zähne (lose Teile) aus dem Gebiss entfernen
teeth_faces = [n for n, m in enumerate(fmat) if m == 1]


def islands(face_ids):
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for n in face_ids:
        vs = faces[n]
        for v in vs[1:]:
            ra, rb = find(vs[0]), find(v)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for n in face_ids:
        groups.setdefault(find(faces[n][0]), []).append(n)
    return list(groups.values())


isl = islands(teeth_faces)
info = []
for g in isl:
    vs = sorted({v for n in g for v in faces[n]})
    c = NEUTRAL[vs].mean(0)
    info.append((g, c, len(vs)))
print("Gebiss: %d lose Teile" % len(isl))
drop = set()
# Teile nach Lage sortieren: oben/unten über y, vorne über z; Kandidaten = kleine Teile (Zähne, nicht das Zahnfleisch)
teeth_parts = [(g, c, n) for g, c, n in info if n < 400]
upper = sorted([t for t in teeth_parts if t[1][1] > np.median([t[1][1] for t in teeth_parts])], key=lambda t: t[1][0])
lower = sorted([t for t in teeth_parts if t[1][1] <= np.median([t[1][1] for t in teeth_parts])], key=lambda t: t[1][0])


def front_sorted(lst):
    return sorted(lst, key=lambda t: -t[1][2])


GAPS = json.loads(os.environ.get("CG_GAPS", '{"upper": [1], "lower": [2, 5]}'))
uf = sorted(front_sorted(upper)[:6], key=lambda t: t[1][0])      # sechs vordere oben, von rechts nach links
lf = sorted(front_sorted(lower)[:6], key=lambda t: t[1][0])
for i in GAPS.get("upper", []):
    if i < len(uf):
        drop.update(uf[i][0])
for i in GAPS.get("lower", []):
    if i < len(lf):
        drop.update(lf[i][0])
print("Zähne oben vorn:", len(uf), "unten vorn:", len(lf), "entfernt:", GAPS)
keep_faces = [n for n in range(len(faces)) if n not in drop]
faces = [faces[n] for n in keep_faces]
fuv = [fuv[n] for n in keep_faces]
fmat = [fmat[n] for n in keep_faces]

# ------------------------------------------------------------------ Ausdrücke als Shape Keys
UNITS = "expression/units/african/"
EXPR_KEYS = ["eye-left-closure", "eye-right-closure", "eye-left-slit", "eye-right-slit", "eye-left-opened-up", "eye-right-opened-up",
             "eyebrows-left-down", "eyebrows-right-down", "eyebrows-left-up", "eyebrows-right-up", "eyebrows-left-inner-up",
             "eyebrows-right-inner-up", "eyebrows-left-extern-up", "eyebrows-right-extern-up",
             "mouth-open", "mouth-corner-puller", "mouth-retraction", "mouth-upward-retraction", "mouth-depression",
             "mouth-depression-retraction", "mouth-elevation", "mouth-eversion", "mouth-protusion", "mouth-pursing",
             "mouth-compression", "mouth-parling", "mouth-part-later", "neck-platysma",
             "nose-compression", "nose-depression", "nose-left-dilatation", "nose-right-dilatation",
             "nose-left-elevation", "nose-right-elevation"]
LASH_IDX = sorted(group("helper-l-eyelashes-1") | group("helper-l-eyelashes-2"))
keys = {}
for name in EXPR_KEYS:
    i, d = read_target(tpath(UNITS + name))
    X = M.copy()
    X[i] += d
    if name.startswith("eye-right"):     # rechte Wimpern spiegeln aus dem linken Target
        il, dl = read_target(tpath(UNITS + name.replace("right", "left")))
        lash = {a: b for a, b in zip(il, dl) if a in set(LASH_IDX)}
        for a, dd in lash.items():
            m = MIRROR.get(a)
            if m is not None:
                X[m] = M[m] + np.array([-dd[0], dd[1], dd[2]])
    D = assemble(X) - NEUTRAL
    nz = np.where(np.abs(D).max(1) > 1e-6)[0]
    keys[name] = (nz, D[nz])
    print("%-28s %5d Punkte" % (name, len(nz)))

# ------------------------------------------------------------------ nach Blender: Z oben, Meter, Ursprung = Kopfgelenk, Gesicht nach +Y
origin = J_HEAD.copy()


def to_bl(P, delta=False):
    Q = P if delta else P - origin
    return np.stack([-Q[:, 0], Q[:, 2], Q[:, 1]], 1) * 0.1      # Gesicht schaut nach +Y wie alle Figuren im Reel


fl = np.array([len(f) for f in faces], np.int32)
fv = np.array([v for f in faces for v in f], np.int32)
uv = np.array([u for f in fuv for u in f], np.float32)
out = {
    "verts": to_bl(NEUTRAL).astype(np.float32), "face_len": fl, "face_verts": fv, "uv": uv, "face_mat": np.array(fmat, np.int32),
    "eye_verts": to_bl(EYES).astype(np.float32),
}
eye = PROX["eyes"]
# Hornhaut-Schicht (UV in der Ecke unten rechts, in MakeHuman transparent) weglassen: nur der Augapfel bleibt
eyeF = [(f, t) for f, t in zip(eye.F, eye.FT) if not (np.mean([eye.VT[i][0] for i in t]) > 0.8 and np.mean([eye.VT[i][1] for i in t]) < 0.2)]
print("Augen: %d von %d Flächen (ohne Hornhaut)" % (len(eyeF), len(eye.F)))
out["eye_face_len"] = np.array([len(f) for f, t in eyeF], np.int32)
out["eye_face_verts"] = np.array([v for f, t in eyeF for v in f], np.int32)
out["eye_uv"] = np.array([eye.VT[i] for f, t in eyeF for i in t], np.float32)
for name, (nz, D) in keys.items():
    out["key_idx:" + name] = nz.astype(np.int32)
    out["key_d:" + name] = to_bl(D, delta=True).astype(np.float32)
np.savez_compressed(os.path.join(args.out, "cg_head.npz"), **out)

ev = to_bl(EYES)
meta = {
    "parts": PART_NAMES,
    "keys": EXPR_KEYS,
    "eye_centers": {"L": ev[ev[:, 0] > 0].mean(0).tolist(), "R": ev[ev[:, 0] < 0].mean(0).tolist()},
    "jaw": to_bl(J_JAW[None])[0].tolist(), "neck": to_bl(J_NECK[None])[0].tolist(), "mouth": to_bl(joint("joint-mouth", M)[None])[0].tolist(),
    "bbox": [to_bl(NEUTRAL).min(0).tolist(), to_bl(NEUTRAL).max(0).tolist()],
    "textures": {},
}
for part, (folder, files) in {"skin": ("skins/young_african_male", ["young_darkskinned_male_diffuse.png"]),
                              "teeth": ("teeth/teeth_base", ["teeth.png"]), "tongue": ("tongue/tongue01", ["tongue01_diffuse.png"]),
                              "brows": ("eyebrows/eyebrow001", ["eyebrow001.png"]), "lashes": ("eyelashes/eyelashes01", ["eyelashes01.png"]),
                              "eyes": ("eyes/materials", ["brown_eye.png"])}.items():
    meta["textures"][part] = files[0]
    shutil.copy(os.path.join(AS, folder, files[0]), os.path.join(args.out, files[0]))
json.dump(meta, open(os.path.join(args.out, "cg_head.json"), "w"), indent=1)
print("fertig:", args.out, "Punkte", len(out["verts"]), "Flächen", len(fl), "bbox", meta["bbox"])

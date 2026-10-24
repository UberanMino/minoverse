/* MINO CAST 3D – die Minoverse-Figuren als code-generierte Low-Poly-Puppen (three.js).
 * Prinzip wie der Dat-Swag-Cast: keine Modelldateien, keine Fotos. Jede Figur wird beim Laden aus
 * Grundkörpern gebaut, hat ein Gelenk-Rig (Hüfte, Wirbelsäule, Arme, Beine, Kopf) und ein Gesichts-Rig
 * (Lider, Blick, Brauen, Mund). Alles ist eine reine Funktion der Zeit t.
 * Merkmale aus den Vorlagen abgeleitet:
 *   Mino Man   – news_mino_man.png / Kletter-Clip: braunes Seitenscheitel-Haar mit hoher Stirn, langes
 *                schmales Gesicht, schmale rot-pinke Wraparound-Sonnenbrille, dünner Bart, Navy-Anzug,
 *                weißes Hemd, magenta Krawatte mit kleinen weißen Kreuzen. Deadpan.
 *   Chicken Guy – Chicken-Clip: runder Kopf, kurze schwarze Haare, großer offener Mund, Körper = ganzes
 *                Brathähnchen, Flügel als Arme, Keulen als Beine.
 *   Pepsi Grandma – PLATZHALTER (echter Clip fehlt): graue Dauerwelle, runde Brille, rosa Strickjacke,
 *                blaue Cola-Flasche ohne Logo, Mentos-Rolle.
 *   Officer Munch – nach Lore: Trenchcoat + Polizeimütze, halb geschlossene rote Augen, kaut immer,
 *                hält eine Fallakte. */
(function () {
  const MC = (window.MC = {});
  let T = null;
  MC.style = 'lambert'; // 'lambert' | 'flat' | 'toon' | 'clay'
  MC.HEAD = 1.32; // Köpfe etwas zu groß (Karikatur)
  const cache = {};
  let toonGrad = null;

  function mat(color, opts) {
    const key = MC.style + '|' + color + '|' + JSON.stringify(opts || {});
    if (cache[key]) return cache[key];
    const o = Object.assign({ color }, opts || {});
    let m;
    if (MC.style === 'toon') {
      if (!toonGrad) {
        toonGrad = new T.DataTexture(new Uint8Array([70, 70, 70, 255, 170, 170, 170, 255, 255, 255, 255, 255]), 3, 1, T.RGBAFormat);
        toonGrad.magFilter = toonGrad.minFilter = T.NearestFilter;
        toonGrad.needsUpdate = true;
      }
      delete o.flatShading;
      m = new T.MeshToonMaterial(Object.assign(o, { gradientMap: toonGrad }));
    } else if (MC.style === 'clay') {
      delete o.flatShading;
      m = new T.MeshPhongMaterial(Object.assign({ shininess: 6, specular: '#2a2420' }, o));
    } else {
      if (MC.style === 'flat') o.flatShading = true;
      m = new T.MeshLambertMaterial(o);
    }
    return (cache[key] = m);
  }
  MC.mat = (c, o) => mat(c, o);
  const flat = (c) => mat(c, { flatShading: true });
  const basic = (c) => new T.MeshBasicMaterial({ color: c });
  function add(parent, geo, m, p, r, s) {
    const mesh = new T.Mesh(geo, typeof m === 'string' ? mat(m) : m);
    if (p) mesh.position.set(p[0], p[1], p[2]);
    if (r) mesh.rotation.set(r[0], r[1], r[2]);
    if (s) mesh.scale.set(s[0], s[1], s[2]);
    parent.add(mesh);
    return mesh;
  }
  const node = (parent, p) => {
    const o = new T.Object3D();
    if (p) o.position.set(p[0], p[1], p[2]);
    parent.add(o);
    return o;
  };
  const box = (w, h, d) => new T.BoxGeometry(w, h, d);
  const cyl = (rt, rb, h, s) => new T.CylinderGeometry(rt, rb, h, s || 8);
  const ball = (r, w, h) => new T.SphereGeometry(r, w || 10, h || 8);
  const ico = (r, d) => new T.IcosahedronGeometry(r, d || 0);
  MC.geo = { box, cyl, ball, ico };
  MC.add = (...a) => add(...a);
  MC.node = (...a) => node(...a);

  function pixTex(rows, colors) {
    const h = rows.length, w = rows[0].length;
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    const g = cv.getContext('2d');
    rows.forEach((row, y) => row.split('').forEach((c, x) => { if (colors[c]) { g.fillStyle = colors[c]; g.fillRect(x, y, 1, 1); } }));
    const tx = new T.CanvasTexture(cv);
    tx.magFilter = tx.minFilter = T.NearestFilter;
    tx.generateMipmaps = false;
    tx.colorSpace = T.SRGBColorSpace;
    return tx;
  }
  // Fleckentextur (knusprige Haut, Holz, Teppich …)
  function blotchTex(w, h, cols, seed, n) {
    const R = rng(seed);
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    const g = cv.getContext('2d');
    g.fillStyle = cols[0];
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < (n || w * h * 0.35); i++) {
      g.fillStyle = cols[1 + Math.floor(R() * (cols.length - 1))];
      const s = 1 + Math.floor(R() * 2);
      g.fillRect(Math.floor(R() * w), Math.floor(R() * h), s, s);
    }
    const tx = new T.CanvasTexture(cv);
    tx.magFilter = tx.minFilter = T.NearestFilter;
    tx.generateMipmaps = false;
    tx.colorSpace = T.SRGBColorSpace;
    tx.wrapS = tx.wrapT = T.RepeatWrapping;
    return tx;
  }
  MC.pixTex = (...a) => pixTex(...a);
  MC.blotchTex = (...a) => blotchTex(...a);
  function rng(seed) {
    let s = seed | 0;
    return function () {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const shade = (hex, k) => '#' + new T.Color(hex).multiplyScalar(k).getHexString();

  // ---------- Gesichts-Rig ----------
  let RIG = null;
  const rig = () => RIG || (RIG = { lids: [], looks: [], brows: [], mouths: [], jaw: null });
  function eyes(head, o) {
    const rg = rig();
    return [-1, 1].map((sx) => {
      const g = node(head, [sx * o.dx, o.y, o.z]);
      g.rotation.y = sx * 0.2;
      add(g, ball(o.r, 10, 8), o.white || '#f4f1ea', [0, 0, 0], null, [1.2, 1, 0.55]);
      const look = node(g, [0, 0, 0]);
      add(look, ball(o.r * 0.6, 8, 6), o.iris || '#3b2414', [0, 0, o.r * 0.32], null, [1, 1, 0.5]);
      add(look, ball(o.r * 0.32, 6, 5), '#0b0806', [0, 0, o.r * 0.44], null, [1, 1, 0.4]);
      add(look, ball(o.r * 0.12, 4, 3), basic('#ffffff'), [o.r * 0.18, o.r * 0.2, o.r * 0.52]);
      rg.looks.push({ n: look, x: 0, y: 0, r: o.r });
      const lid = add(g, new T.SphereGeometry(o.r * 1.12, 10, 5, 0, Math.PI * 2, 0, Math.PI / 2), o.lid, [0, 0, 0], [o.lidDrop || 0.3, 0, 0], [1.2, 1, 0.65]);
      rg.lids.push({ n: lid, x: o.lidDrop || 0.3 });
      if (o.bag) add(g, ball(o.r * 0.9, 8, 5), o.bag, [0, -o.r * 0.95, o.r * 0.05], null, [1.3, 0.45, 0.6]);
      if (o.brow) {
        const b = add(head, box(o.r * 2.5, o.r * (o.browH || 0.45), o.r * 0.6), flat(o.brow), [sx * o.dx, o.y + o.r * 1.5, o.z + o.r * 0.15], [0, sx * 0.18, sx * (o.browTilt || -0.12)]);
        rg.brows.push({ n: b, y: b.position.y, z: b.rotation.z, sx });
      }
      return g;
    });
  }
  function mouth(head, p, w, lip, o) {
    o = o || {};
    const m = node(head, p);
    const inner = add(m, box(w * 0.86, 0.022, 0.012), '#3a0d12', [0, -0.004, -0.004]);
    const teeth = o.teeth !== false ? add(inner, box(w * 0.66, 0.007, 0.004), '#f4efe6', [0, 0.007, 0.006]) : null;
    if (o.tongue) add(inner, box(w * 0.5, 0.006, 0.004), '#d0606e', [0, -0.008, 0.005]);
    const up = add(m, box(w, o.lipH || 0.011, 0.018), lip, [0, 0.007, 0]);
    const lo = add(m, box(w * 0.9, (o.lipH || 0.011) * 1.15, 0.018), lip, [0, -0.008, 0]);
    rig().mouths.push({ inner, up, lo, teeth, open: o.open || 1 });
    return m;
  }

  // ---------- Menschen-Rig ----------
  function humanoid(sp) {
    const root = new T.Group();
    const j = { root };
    const leg = sp.leg || 0.84, th = leg * 0.5, sh = leg * 0.5;
    j.hips = node(root, [0, leg + 0.04, 0]);
    add(j.hips, cyl(sp.waist * 1.02, sp.hipW, 0.16, 8), sp.bottom, [0, -0.02, 0], null, [1, 1, 0.7]);
    ['L', 'R'].forEach((s, k) => {
      const sx = k ? -1 : 1;
      const hip = (j['hip' + s] = node(j.hips, [sx * sp.hipW * 0.55, -0.06, 0]));
      add(hip, cyl(sp.thigh, sp.thigh * 0.85, th, 8), sp.bottom, [0, -th / 2, 0]);
      const knee = (j['knee' + s] = node(hip, [0, -th, 0]));
      add(knee, cyl(sp.thigh * 0.85, sp.shin, sh, 8), sp.shinColor || sp.bottom, [0, -sh / 2, 0]);
      const ankle = (j['ankle' + s] = node(knee, [0, -sh, 0]));
      const fw = sp.footW || 0.12, fl = sp.footL || 0.27, fh = sp.footH || 0.08;
      add(ankle, box(fw, fh, fl), flat(sp.shoe), [0, -fh / 2 + 0.01, fl * 0.28]);
    });
    j.spine = node(j.hips, [0, 0.04, 0]);
    const torso = sp.torso || 0.52;
    add(j.spine, cyl(sp.shoulderW, sp.waist, torso, 8), sp.top, [0, torso / 2, 0], null, [1, 1, sp.depth || 0.62]);
    if (sp.belly) add(j.spine, ball(sp.belly, 10, 8), sp.top, [0, torso * 0.32, sp.waist * 0.3], null, [1.15, 1.0, 0.8]);
    j.chest = node(j.spine, [0, torso, 0]);
    add(j.chest, ball(sp.shoulderW * 0.8, 10, 6), sp.top, [0, -0.01, 0], null, [1, 0.32, (sp.depth || 0.62) * 1.05]);
    j.neck = node(j.chest, [0, 0, 0]);
    add(j.neck, cyl(sp.neckR || 0.055, (sp.neckR || 0.055) * 1.1, 0.12, 8), sp.neckColor || sp.skin, [0, 0.04, 0]);
    j.head = node(j.neck, [0, 0.075, 0]);
    ['L', 'R'].forEach((s, k) => {
      const sx = k ? -1 : 1;
      const so = (j['shoulder' + s] = node(j.chest, [sx * (sp.shoulderW * 0.92 + 0.03), -0.05, 0]));
      const ua = sp.upperArm || 0.29, fa = sp.foreArm || 0.27;
      add(so, ball(sp.arm * 1.25, 8, 6), sp.sleeve || sp.top);
      add(so, cyl(sp.arm * 1.1, sp.arm, ua, 8), sp.sleeve || sp.top, [0, -ua / 2, 0]);
      const el = (j['elbow' + s] = node(so, [0, -ua, 0]));
      add(el, cyl(sp.arm, sp.arm * 0.85, fa, 8), sp.sleeve || sp.top, [0, -fa / 2, 0]);
      if (sp.cuff) add(el, cyl(sp.arm * 0.8, sp.arm * 0.8, 0.03, 8), sp.cuff, [0, -fa + 0.01, 0]);
      const hand = (j['hand' + s] = node(el, [0, -fa - 0.03, 0]));
      const hs = sp.handSize || 0.055;
      add(hand, ico(hs, 1), sp.hand || sp.skin, [0, -0.02, 0], null, [0.9, 1.15, 0.75]);
      add(hand, ico(hs * 0.42, 0), sp.hand || sp.skin, [sx * -hs * 0.75, 0, hs * 0.45]);
      so.rotation.z = sx * 0.1;
    });
    return { root, j, sp };
  }

  const BUILD = {};

  BUILD.minoman = function () {
    const c = { skin: '#e8b597', suit: '#1c2340', shirt: '#f3f1ee', tie: '#8e1f5f', hair: '#3e2b20', beard: '#8b5e3c', frame: '#e0507a', lens: '#170a11', shoe: '#121214', lip: '#bf7d72' };
    const h = humanoid({ leg: 0.86, hipW: 0.16, waist: 0.15, thigh: 0.075, shin: 0.062, torso: 0.53, shoulderW: 0.22, depth: 0.6, arm: 0.052,
      top: c.suit, bottom: c.suit, shoe: c.shoe, skin: c.skin, cuff: c.shirt, footL: 0.28, neckColor: c.shirt });
    const { j } = h;
    // Hemd-V, Kragen, Krawatte mit kleinen Kreuzen, Revers
    add(j.spine, box(0.11, 0.2, 0.02), c.shirt, [0, 0.43, 0.125], [-0.12, 0, 0]);
    const tieTex = pixTex(['000000', '010000', '111000', '010001', '000011', '000001'], { 0: c.tie, 1: '#e8d8ec' });
    tieTex.wrapS = tieTex.wrapT = T.RepeatWrapping; tieTex.repeat.set(2, 6);
    const tie = node(j.chest, [0, -0.02, 0.135]);
    add(tie, box(0.034, 0.03, 0.02), c.tie, [0, 0, 0]);
    add(tie, box(0.05, 0.3, 0.012), new T.MeshLambertMaterial({ map: tieTex }), [0, -0.17, -0.004], [-0.1, 0, 0]);
    h.tie = tie;
    [-1, 1].forEach((sx) => add(j.chest, box(0.05, 0.22, 0.015), flat(shade(c.suit, 0.75)), [sx * 0.07, -0.12, 0.128], [-0.12, 0, sx * 0.32]));
    [-1, 1].forEach((sx) => add(j.neck, box(0.05, 0.03, 0.05), c.shirt, [sx * 0.04, 0.02, 0.04], [0, 0, sx * 0.4]));
    // Kopf: lang und schmal, hohe Stirn
    const hd = node(j.head, [0, 0.13, 0]);
    add(hd, ball(0.12, 12, 10), c.skin, [0, 0, 0], null, [0.86, 1.3, 0.95]);
    add(hd, ball(0.07, 10, 8), c.skin, [0, -0.09, 0.025], null, [1.05, 0.8, 1]); // Kinn/Kiefer
    add(hd, ball(0.062, 8, 6), shade(c.skin, 0.8), [0, -0.1, 0.035], null, [1.05, 0.6, 0.95]); // Bartschatten
    [-1, 1].forEach((sx) => add(hd, ball(0.022, 8, 6), '#e3a08e', [sx * 0.07, -0.035, 0.078], null, [1, 0.7, 0.35])); // rosige Wangen
    [-1, 1].forEach((sx) => add(hd, ball(0.026, 6, 5), c.skin, [sx * 0.104, -0.005, -0.005], null, [0.5, 1.1, 0.8])); // Ohren
    // Haare: Kappe hinten/oben + Seitenscheitel-Welle vorn
    const hairM = mat(c.hair);
    add(hd, new T.SphereGeometry(0.128, 12, 8, 0, Math.PI * 2, 0, 1.25), hairM, [0, 0.012, -0.012], [-0.35, 0, 0], [0.9, 1.3, 1.0]);
    add(hd, ball(0.07, 10, 7), hairM, [0.03, 0.135, 0.045], [0, 0, -0.35], [1.35, 0.45, 0.85]);
    add(hd, ball(0.05, 8, 6), hairM, [-0.06, 0.115, 0.04], [0, 0, 0.5], [1.2, 0.5, 0.8]);
    [-1, 1].forEach((sx) => add(hd, ball(0.035, 8, 6), hairM, [sx * 0.095, 0.06, -0.01], null, [0.5, 1.4, 1]));
    // Brauen (meist reglos, deadpan)
    const rg = rig();
    [-1, 1].forEach((sx) => {
      const b = add(hd, box(0.045, 0.007, 0.01), flat(c.hair), [sx * 0.047, 0.07, 0.106], [0, sx * 0.2, sx * -0.05]);
      rg.brows.push({ n: b, y: b.position.y, z: b.rotation.z, sx });
    });
    // schmale Wraparound-Sonnenbrille, rot-pink
    const gl = node(hd, [0, 0.025, 0]);
    add(gl, new T.CylinderGeometry(0.112, 0.11, 0.036, 18, 1, true, -1.15, 2.3), new T.MeshPhongMaterial({ color: c.lens, shininess: 90, specular: '#ff9ab8', side: T.DoubleSide }), [0, 0, 0.0], null, [0.92, 1, 1.02]);
    add(gl, new T.CylinderGeometry(0.114, 0.114, 0.008, 18, 1, true, -1.2, 2.4), new T.MeshLambertMaterial({ color: c.frame, side: T.DoubleSide }), [0, 0.02, 0], null, [0.92, 1, 1.02]);
    add(gl, new T.CylinderGeometry(0.114, 0.114, 0.006, 18, 1, true, -1.2, 2.4), new T.MeshLambertMaterial({ color: c.frame, side: T.DoubleSide }), [0, -0.019, 0], null, [0.92, 1, 1.02]);
    add(gl, box(0.03, 0.01, 0.004), basic('#ffffff'), [0.035, 0.008, 0.112], [0, 0.3, 0]);
    j.glasses = gl;
    // lange Nase, dünner Schnurrbart
    add(hd, ball(0.02, 8, 6), shade(c.skin, 0.96), [0, -0.018, 0.112], [0.5, 0, 0], [0.85, 1.9, 1.0]); // lange Nase
    add(hd, ball(0.017, 6, 5), shade(c.skin, 0.93), [0, -0.043, 0.122]);
    add(hd, box(0.058, 0.008, 0.01), flat(c.beard), [0, -0.066, 0.113]);
    add(hd, box(0.02, 0.016, 0.01), flat(c.beard), [0, -0.118, 0.098], [0.3, 0, 0]);
    mouth(hd, [0, -0.085, 0.108], 0.05, c.lip, { lipH: 0.008, open: 0.8 });
    h.face = { node: hd, y: 0.02, z: 0.12 };
    h.colors = c;
    return h;
  };

  BUILD.chickenguy = function () {
    const c = { skin: '#5b3a28', hair: '#141010', crisp: '#c47a2c', crisp2: '#9a5518', crisp3: '#e0a24a', bone: '#f1e6cc', lip: '#6e3a2c' };
    const root = new T.Group();
    const j = { root };
    // goldbraune Haut: weicher Verlauf mit wenigen dunklen Flecken
    const cv = document.createElement('canvas'); cv.width = 64; cv.height = 64;
    const g = cv.getContext('2d');
    const grd = g.createLinearGradient(0, 0, 0, 64);
    grd.addColorStop(0, '#e6a650'); grd.addColorStop(0.55, '#c47a2c'); grd.addColorStop(1, '#8e4f16');
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
    const Rb = rng(7);
    for (let i = 0; i < 70; i++) { g.fillStyle = ['rgba(120,60,15,.55)', 'rgba(250,200,120,.45)', 'rgba(90,40,10,.4)'][i % 3]; g.beginPath(); g.ellipse(Rb() * 64, Rb() * 64, 1 + Rb() * 3, 1 + Rb() * 2, Rb() * 3, 0, 7); g.fill(); }
    const crispTex = new T.CanvasTexture(cv); crispTex.colorSpace = T.SRGBColorSpace;
    const crispM = MC.style === 'toon' ? mat(c.crisp) : new T.MeshPhongMaterial(Object.assign({ map: crispTex, shininess: MC.style === 'clay' ? 8 : 40, specular: '#7a4a1a' }, MC.style === 'flat' ? { flatShading: true } : {}));
    j.hips = node(root, [0, 0.42, 0]);
    // Keulen als Beine
    ['L', 'R'].forEach((s, k) => {
      const sx = k ? -1 : 1;
      const hip = (j['hip' + s] = node(j.hips, [sx * 0.15, 0.04, 0.02]));
      add(hip, ball(0.1, 10, 8), crispM, [0, -0.1, 0], null, [1, 1.45, 1]);
      const knee = (j['knee' + s] = node(hip, [0, -0.25, 0]));
      add(knee, cyl(0.032, 0.028, 0.1, 6), c.bone, [0, -0.04, 0]);
      const ankle = (j['ankle' + s] = node(knee, [0, -0.1, 0]));
      add(ankle, ball(0.034, 6, 5), c.bone, [-0.02, -0.01, 0.02]);
      add(ankle, ball(0.034, 6, 5), c.bone, [0.02, -0.01, 0.02]);
    });
    j.spine = node(j.hips, [0, 0, 0]);
    // der Körper: ein ganzes Brathähnchen (birnenförmig, Brust vorn)
    add(j.spine, ball(0.27, 16, 12), crispM, [0, 0.2, 0], null, [1.05, 1.0, 0.92]);
    add(j.spine, ball(0.2, 14, 10), crispM, [0, 0.42, 0.02], null, [1.05, 0.9, 0.9]);
    add(j.spine, ball(0.13, 12, 8), crispM, [0, 0.3, 0.16], null, [1.5, 1.1, 0.7]);
    add(j.spine, ball(0.06, 8, 6), crispM, [0, 0.03, -0.2], null, [1.3, 0.9, 1]); // Bürzel
    j.chest = node(j.spine, [0, 0.55, 0]);
    j.neck = node(j.chest, [0, -0.03, 0]);
    j.head = node(j.neck, [0, 0.0, 0]);
    // Flügel als Arme
    ['L', 'R'].forEach((s, k) => {
      const sx = k ? -1 : 1;
      const so = (j['shoulder' + s] = node(j.chest, [sx * 0.24, -0.14, 0]));
      add(so, ball(0.09, 8, 6), crispM, [0, -0.1, 0], null, [0.7, 1.4, 0.55]);
      const el = (j['elbow' + s] = node(so, [0, -0.22, 0]));
      add(el, ball(0.07, 8, 6), crispM, [0, -0.1, 0], null, [0.6, 1.5, 0.45]);
      const hand = (j['hand' + s] = node(el, [0, -0.22, 0]));
      add(hand, new T.ConeGeometry(0.05, 0.12, 5), flat(c.crisp2), [0, -0.03, 0], [Math.PI, 0, 0]);
      so.rotation.z = sx * 0.35;
    });
    // Kopf sitzt direkt auf dem Hähnchen
    const hd = node(j.head, [0, 0.13, 0]);
    add(hd, ball(0.15, 12, 10), c.skin, [0, 0, 0], null, [0.95, 1.08, 0.95]);
    add(hd, ball(0.09, 10, 8), c.skin, [0, -0.09, 0.03], null, [1.15, 0.8, 1]);
    add(hd, new T.SphereGeometry(0.154, 12, 8, 0, Math.PI * 2, 0, 1.05), mat(c.hair), [0, 0.01, -0.01], [-0.2, 0, 0], [0.97, 1.1, 0.98]);
    [-1, 1].forEach((sx) => add(hd, ball(0.03, 6, 5), c.skin, [sx * 0.142, -0.01, 0], null, [0.5, 1.1, 0.8]));
    eyes(hd, { dx: 0.055, y: 0.03, z: 0.12, r: 0.026, lid: c.skin, lidDrop: 0.55, iris: '#1d120c', brow: c.hair, browTilt: 0.18 });
    add(hd, ball(0.032, 8, 6), shade(c.skin, 0.9), [0, -0.025, 0.14], null, [1.3, 0.85, 0.9]);
    mouth(hd, [0, -0.085, 0.13], 0.085, c.lip, { tongue: true, open: 1.7, lipH: 0.014 });
    const h = { root, j };
    h.face = { node: hd, y: 0.03, z: 0.15 };
    return h;
  };

  BUILD.grandma = function () {
    const c = { skin: '#efc3a4', hair: '#cfd0d6', cardigan: '#e48fb5', blouse: '#f6f0e6', skirt: '#5a3d5c', shoe: '#d9c3a0', frame: '#b8902f', lip: '#b8556a', bottle: '#1f4fd0' };
    const h = humanoid({ leg: 0.74, hipW: 0.17, waist: 0.15, thigh: 0.072, shin: 0.052, torso: 0.47, shoulderW: 0.19, depth: 0.68, arm: 0.046,
      top: c.cardigan, bottom: c.skirt, shinColor: c.skin, shoe: c.shoe, footL: 0.22, skin: c.skin, neckR: 0.045, handSize: 0.05 });
    const { j } = h;
    add(j.hips, cyl(0.16, 0.24, 0.5, 9), flat(c.skirt), [0, -0.24, 0], null, [1, 1, 0.8]);
    add(j.spine, box(0.14, 0.34, 0.02), c.blouse, [0, 0.28, 0.1]);
    for (let i = 0; i < 5; i++) add(j.spine, ball(0.012, 5, 4), '#f4efe6', [0.0, 0.42 - i * 0.07, 0.115]);
    const hd = node(j.head, [0, 0.12, 0]);
    add(hd, ball(0.115, 12, 10), c.skin, [0, 0, 0], null, [0.95, 1.1, 1]);
    const R = rng(21);
    for (let i = 0; i < 26; i++) {
      const a = R() * Math.PI * 2, el = R() * 1.15;
      add(hd, ico(0.045 + R() * 0.02, 0), flat(i % 3 ? c.hair : '#e4e4ea'), [Math.cos(a) * Math.sin(el) * 0.12, 0.03 + Math.cos(el) * 0.12, Math.sin(a) * Math.sin(el) * 0.11 - 0.02]);
    }
    eyes(hd, { dx: 0.042, y: 0.02, z: 0.1, r: 0.02, lid: c.skin, lidDrop: 0.15, iris: '#4a6a8a', brow: '#a7a7ae', browTilt: 0.15 });
    [-1, 1].forEach((sx) => {
      add(hd, new T.TorusGeometry(0.03, 0.005, 5, 14), c.frame, [sx * 0.044, 0.02, 0.118]);
      add(hd, new T.CircleGeometry(0.029, 12), new T.MeshBasicMaterial({ color: '#dff0ff', transparent: true, opacity: 0.25 }), [sx * 0.044, 0.02, 0.119]);
    });
    add(hd, box(0.03, 0.005, 0.005), c.frame, [0, 0.025, 0.12]);
    add(hd, ball(0.022, 6, 5), shade(c.skin, 0.93), [0, -0.012, 0.115]);
    mouth(hd, [0, -0.06, 0.1], 0.045, c.lip, { open: 1.4 });
    // Flasche rechts, Mentos-Rolle links
    const bottle = node(j.handR, [0, -0.05, 0.04]);
    add(bottle, cyl(0.035, 0.035, 0.16, 10), new T.MeshPhongMaterial({ color: c.bottle, shininess: 70, transparent: true, opacity: 0.92 }), [0, -0.02, 0]);
    add(bottle, cyl(0.036, 0.036, 0.05, 10), '#f4f4f4', [0, -0.02, 0]);
    add(bottle, cyl(0.036, 0.036, 0.012, 10), '#d22a3a', [0, -0.03, 0]);
    add(bottle, cyl(0.014, 0.03, 0.05, 8), new T.MeshPhongMaterial({ color: c.bottle, shininess: 70 }), [0, 0.08, 0]);
    const cap = add(bottle, cyl(0.016, 0.016, 0.018, 8), '#f4f4f4', [0, 0.112, 0]);
    j.bottle = bottle; h.cap = cap;
    const mentos = node(j.handL, [0, -0.04, 0.04]);
    add(mentos, cyl(0.018, 0.018, 0.09, 8), '#eef3f8', [0, 0, 0], [0, 0, Math.PI / 2]);
    j.mentos = mentos;
    h.face = { node: hd, y: 0.02, z: 0.12 };
    h.colors = c;
    return h;
  };

  BUILD.munch = function () {
    const c = { skin: '#d8a585', coat: '#a88a5c', shirt: '#cfe0ee', pants: '#2c2c34', cap: '#1d2a4a', badge: '#e2b33a', stub: '#8a6a55', lip: '#a8655a', folder: '#e3c27a' };
    const h = humanoid({ leg: 0.8, hipW: 0.2, waist: 0.21, thigh: 0.09, shin: 0.07, torso: 0.5, shoulderW: 0.25, depth: 0.75, arm: 0.06, belly: 0.17,
      top: c.coat, bottom: c.pants, shoe: '#1a1410', skin: c.skin, footL: 0.28, neckR: 0.065 });
    const { j } = h;
    // Trenchcoat bis zum Knie, Kragen, Gürtel
    add(j.hips, new T.CylinderGeometry(0.24, 0.3, 0.5, 10, 1, true, 0.35, Math.PI * 2 - 0.7), new T.MeshLambertMaterial({ color: c.coat, side: T.DoubleSide }), [0, -0.2, 0], null, [1, 1, 0.8]);
    add(j.spine, cyl(0.235, 0.235, 0.05, 10), flat(shade(c.coat, 0.7)), [0, 0.08, 0], null, [1, 1, 0.76]);
    add(j.spine, box(0.1, 0.25, 0.02), c.shirt, [0, 0.38, 0.175], [-0.15, 0, 0]);
    [-1, 1].forEach((sx) => add(j.chest, box(0.09, 0.2, 0.02), flat(shade(c.coat, 0.85)), [sx * 0.09, -0.08, 0.16], [-0.2, 0, sx * 0.35]));
    const hd = node(j.head, [0, 0.13, 0]);
    add(hd, ball(0.13, 12, 10), c.skin, [0, 0, 0], null, [1.02, 1.05, 1]);
    add(hd, ball(0.1, 10, 8), c.skin, [0, -0.07, 0.03], null, [1.25, 0.85, 1]); // Hängebacken
    add(hd, ball(0.085, 8, 6), shade(c.skin, 0.84), [0, -0.1, 0.05], null, [1.3, 0.6, 0.95]); // Stoppeln
    eyes(hd, { dx: 0.048, y: 0.025, z: 0.112, r: 0.024, lid: c.skin, lidDrop: 1.0, iris: '#5a4030', white: '#f3c9c2', bag: '#b98f86', brow: '#4a3628', browTilt: -0.25 });
    add(hd, ball(0.03, 8, 6), '#c9806c', [0, -0.02, 0.13], null, [1.1, 0.9, 1]);
    mouth(hd, [0, -0.075, 0.122], 0.06, c.lip, { open: 1.3 });
    [-1, 1].forEach((sx) => add(hd, ball(0.03, 6, 5), c.skin, [sx * 0.13, -0.005, 0], null, [0.5, 1.1, 0.8]));
    // Polizeimütze
    const capN = node(hd, [0, 0.095, -0.005]);
    capN.rotation.x = -0.12;
    add(capN, cyl(0.15, 0.135, 0.075, 12), flat(c.cap), [0, 0.03, 0]);
    add(capN, cyl(0.135, 0.135, 0.02, 12), '#101010', [0, -0.005, 0]);
    add(capN, box(0.2, 0.012, 0.09), flat('#0c0c0c'), [0, -0.01, 0.13], [0.25, 0, 0]);
    add(capN, box(0.04, 0.04, 0.01), flat(c.badge), [0, 0.03, 0.142]);
    // Fallakte in der rechten Hand
    const folder = node(j.handR, [0.0, -0.06, 0.06]);
    add(folder, box(0.2, 0.26, 0.012), flat(c.folder), [0, 0, 0]);
    add(folder, box(0.18, 0.24, 0.006), '#f6f3ea', [0.008, 0.004, 0.008]);
    add(folder, box(0.06, 0.02, 0.012), flat(shade(c.folder, 0.85)), [-0.06, 0.135, 0]);
    j.folder = folder;
    // Krümel
    const R = rng(9);
    for (let i = 0; i < 9; i++) add(j.chest, ico(0.01, 0), flat('#e8d2a0'), [(R() - 0.5) * 0.2, -0.05 - R() * 0.25, 0.19 + R() * 0.02]);
    h.face = { node: hd, y: 0.025, z: 0.12 };
    h.colors = c;
    return h;
  };

  // schwarze Outline (inverted hull) für den Toon-Look
  function outline(root, d) {
    const ink = new T.MeshBasicMaterial({ color: '#0a0a0c', side: T.BackSide });
    const list = [];
    root.traverse((o) => { if (o.isMesh && !(o.material && o.material.transparent) && !o.userData.ink) list.push(o); });
    list.forEach((m) => {
      const g = m.geometry.clone();
      const pos = g.attributes.position, nor = g.attributes.normal;
      if (!nor) return;
      const sc = m.scale;
      for (let i = 0; i < pos.count; i++) pos.setXYZ(i, pos.getX(i) + (nor.getX(i) * d) / sc.x, pos.getY(i) + (nor.getY(i) * d) / sc.y, pos.getZ(i) + (nor.getZ(i) * d) / sc.z);
      const hull = new T.Mesh(g, ink);
      hull.userData.ink = true;
      m.add(hull);
    });
  }

  MC.make = function (name, o) {
    T = window.THREE;
    o = o || {};
    RIG = null;
    const h = BUILD[name](o);
    h.rig = rig();
    RIG = null;
    h.j.head.scale.setScalar(o.head || (name === 'chickenguy' ? 1.55 : MC.HEAD));
    h.name = name;
    h.seed = name.split('').reduce((a, ch) => a + ch.charCodeAt(0), 0);
    if (MC.style === 'toon' || o.outline) outline(h.root, o.outline || 0.012);
    h.rest = {};
    Object.keys(h.j).forEach((k) => { h.rest[k] = h.j[k].rotation.clone(); h.rest[k + '_p'] = h.j[k].position.clone(); });
    if (o.scale) h.root.scale.setScalar(o.scale);
    return h;
  };
  MC.NAMES = Object.keys(BUILD);

  MC.apply = function (h, off, lift) {
    Object.keys(h.j).forEach((k) => { if (k !== 'root') { h.j[k].rotation.copy(h.rest[k]); h.j[k].position.copy(h.rest[k + '_p']); } });
    Object.keys(off || {}).forEach((k) => {
      if (!h.j[k]) return;
      const r = h.j[k].rotation, v = off[k];
      r.x += v[0] || 0; r.y += v[1] || 0; r.z += v[2] || 0;
    });
    if (lift) h.j.hips.position.y += lift;
  };

  // Gesicht: blinzeln, umherschauen, Mund nach Sprach-Hüllkurve (talk 0..1), Brauen (raise 0..1)
  MC.face = function (h, t, talk, raise, o) {
    o = o || {};
    const rg = h.rig;
    const per = 2.6 + (h.seed % 9) * 0.19, bp = (t + h.seed * 0.37) % per;
    const blink = o.noBlink ? 0 : bp < 0.13 ? Math.sin((bp / 0.13) * Math.PI) : 0;
    rg.lids.forEach((l) => { l.n.rotation.x = l.x + blink * (1.3 - l.x * 0.6) + (o.sleepy || 0); });
    rg.looks.forEach((l) => {
      l.n.position.x = l.x + l.r * 0.28 * (o.lookX != null ? o.lookX : Math.sin(t * 0.6 + h.seed));
      l.n.position.y = l.y + l.r * 0.14 * (o.lookY != null ? o.lookY : Math.sin(t * 0.43 + h.seed * 2));
    });
    rg.brows.forEach((b) => {
      b.n.position.y = b.y + 0.012 * (raise || 0);
      b.n.rotation.z = b.z - b.sx * 0.14 * (raise || 0);
    });
    const k = talk || 0;
    rg.mouths.forEach((m) => {
      const a = k * m.open;
      m.up.position.y = 0.007 + 0.005 * a;
      m.lo.position.y = -0.008 - 0.02 * a;
      m.inner.scale.y = 0.35 + 2.3 * a;
      m.inner.position.y = -0.004 - 0.008 * a;
      m.inner.visible = a > 0.04;
    });
  };

  // Bewegungen als Funktion der Schlagphase. ph = Schläge (float). k = Intensität 0..1
  const POSES = [
    { shoulderL: [0, 0, 2.5], shoulderR: [0, 0, -2.5], elbowL: [0, 0, 0.3], elbowR: [0, 0, -0.3] },
    { shoulderL: [-1.3, 0.3, 0.9], elbowL: [-1.5, 0, 0], shoulderR: [-1.4, -0.2, -1.0], elbowR: [-0.3, 0, 0], neck: [0.45, 0.4, 0.2] },
    { shoulderR: [-2.9, 0, -0.1], elbowR: [-0.1, 0, 0], shoulderL: [0, 0, 0.5], elbowL: [-1.2, 0, 0] },
    { shoulderL: [-0.2, 0, 0.75], elbowL: [0, 0, 1.9], shoulderR: [-0.2, 0, -0.75], elbowR: [0, 0, -1.9] },
  ];
  MC.move = function (h, ph, move, o) {
    o = o || {};
    const k = o.k != null ? o.k : 1;
    const f = ph - Math.floor(ph), s = Math.sin(ph * Math.PI), c = Math.cos(ph * Math.PI);
    const bounce = Math.abs(s) * k;
    const off = {
      hips: [0, 0.1 * s * k, 0.03 * c * k],
      spine: [0.05 * bounce, 0, -0.03 * c * k],
      neck: [0.16 * bounce - 0.03, 0.06 * s * k, 0],
      kneeL: [0.22 * bounce + 0.05, 0, 0], kneeR: [0.22 * bounce + 0.05, 0, 0],
      hipL: [-0.16 * bounce - 0.03, 0, 0], hipR: [-0.16 * bounce - 0.03, 0, 0],
      ankleL: [-0.06 * bounce, 0, 0], ankleR: [-0.06 * bounce, 0, 0],
    };
    let shiftX = 0, turn = 0, lift = -0.03 * bounce;
    if (move === 'idle' || move === 'stand') {
      const b = 0.15 * Math.sin(ph * 0.8);
      Object.assign(off, { hips: [0, 0.03 * b, 0], spine: [0.01 * b, 0, 0], neck: [0.02 * b, 0.05 * Math.sin(ph * 0.3), 0], kneeL: [0.03, 0, 0], kneeR: [0.03, 0, 0], hipL: [-0.02, 0, 0], hipR: [-0.02, 0, 0], ankleL: [0, 0, 0], ankleR: [0, 0, 0] });
      off.shoulderL = [0.03 * b, 0, 0]; off.shoulderR = [-0.03 * b, 0, 0];
      lift = 0;
    } else if (move === 'anchor') { // sitzt am Pult, Hände auf dem Tisch
      Object.assign(off, { hips: [0, 0, 0], spine: [0.04, 0.03 * Math.sin(ph * 0.5), 0], neck: [0.02 + 0.03 * (o.nod || 0), 0.04 * Math.sin(ph * 0.37), 0] });
      off.hipL = [-1.5, 0, 0.05]; off.hipR = [-1.5, 0, -0.05]; off.kneeL = [1.5, 0, 0]; off.kneeR = [1.5, 0, 0]; off.ankleL = [0, 0, 0]; off.ankleR = [0, 0, 0];
      off.shoulderL = [-0.35, 0.1, -0.02]; off.elbowL = [-1.25 - 0.08 * (o.gesture || 0), 0, 0.15];
      off.shoulderR = [-0.35 - 0.3 * (o.gesture || 0), -0.1, 0.02]; off.elbowR = [-1.25 - 0.35 * (o.gesture || 0), 0, -0.15];
      lift = 0;
    } else if (move === 'nod') {
      off.shoulderL = [-0.25 * k, 0, 0.1 + 0.12 * s * k]; off.elbowL = [-0.8 * k - 0.2, 0, 0];
      off.shoulderR = [-0.25 * k, 0, -0.1 + 0.12 * s * k]; off.elbowR = [-0.8 * k - 0.2, 0, 0];
    } else if (move === 'mic') { // Reporter: Mikro vor dem Mund, steif
      Object.assign(off, { hips: [0, 0, 0], spine: [0, 0, 0], neck: [0.03 * Math.sin(ph * 0.5), 0, 0], kneeL: [0.03, 0, 0], kneeR: [0.03, 0, 0], hipL: [0, 0, 0], hipR: [0, 0, 0] });
      off.shoulderR = [-1.15, 0.35, -0.15]; off.elbowR = [-1.75, 0, 0];
      off.shoulderL = [0.02, 0, 0.05];
      lift = 0;
    } else if (move === 'twostep') {
      shiftX = 0.07 * s * k;
      off.hips = [0, 0.18 * s * k, -0.07 * s * k];
      off.spine[1] = -0.2 * s * k;
      off.hipL = [-0.45 * Math.max(0, -s) * k - 0.04, 0, 0.1 * Math.max(0, -s)]; off.kneeL = [0.8 * Math.max(0, -s) * k + 0.08, 0, 0];
      off.hipR = [-0.45 * Math.max(0, s) * k - 0.04, 0, -0.1 * Math.max(0, s)]; off.kneeR = [0.8 * Math.max(0, s) * k + 0.08, 0, 0];
      off.shoulderL = [-0.5 * s * k, 0, 0.25]; off.elbowL = [-1.3, 0, 0];
      off.shoulderR = [0.5 * s * k, 0, -0.25]; off.elbowR = [-1.3, 0, 0];
    } else if (move === 'runningman') {
      const lead = Math.floor(ph) % 2 === 0 ? 'L' : 'R', back = lead === 'L' ? 'R' : 'L';
      const up = Math.sin(f * Math.PI);
      off['hip' + lead] = [-1.1 * up * k, 0, 0]; off['knee' + lead] = [1.4 * up * k, 0, 0];
      off['hip' + back] = [0.35 * f * k, 0, 0]; off['knee' + back] = [0.25 * up * k, 0, 0];
      off.shoulderL = [(lead === 'L' ? 0.6 : -0.7) * up * k, 0, 0.15]; off.elbowL = [-1.5, 0, 0];
      off.shoulderR = [(lead === 'R' ? 0.6 : -0.7) * up * k, 0, -0.15]; off.elbowR = [-1.5, 0, 0];
      off.spine[0] = 0.12 * k;
    } else if (move === 'wave') {
      const w = (q) => Math.sin(ph * Math.PI - q);
      off.shoulderL = [-0.1, 0, 1.35 + 0.3 * w(0) * k]; off.elbowL = [0, 0, 0.7 * w(0.7) * k]; off.handL = [0, 0, 0.6 * w(1.4) * k];
      off.chest = [0, 0, 0.12 * w(2.1) * k]; off.neck[2] = -0.15 * w(2.1) * k;
      off.shoulderR = [-0.1, 0, -1.35 + 0.3 * w(2.8) * k]; off.elbowR = [0, 0, 0.7 * w(3.5) * k]; off.handR = [0, 0, 0.6 * w(4.2) * k];
    } else if (move === 'flap') { // Hühnertanz: Flügel schlagen, Knie wippen, Kopf pickt
      const fl = Math.sin(ph * Math.PI * 2);
      off.shoulderL = [0, 0, 0.3 + 0.9 * Math.max(0, fl) * k]; off.elbowL = [0, 0, -0.4 * fl * k];
      off.shoulderR = [0, 0, -0.3 - 0.9 * Math.max(0, fl) * k]; off.elbowR = [0, 0, 0.4 * fl * k];
      off.neck = [0.35 * Math.max(0, Math.sin(ph * Math.PI * 2 + 1)) * k, 0, 0];
      off.hips[1] = 0.25 * s * k;
      lift = -0.06 * bounce;
    } else if (move === 'twerk') {
      const q = Math.abs(Math.sin(ph * Math.PI * 2));
      off.spine = [0.5 * k, 0, 0]; off.hips = [-0.5 * k + 0.25 * q * k, 0, 0];
      off.hipL = [-0.6 * k, 0, 0.2]; off.hipR = [-0.6 * k, 0, -0.2]; off.kneeL = [0.9 * k, 0, 0]; off.kneeR = [0.9 * k, 0, 0];
      off.shoulderL = [-0.9, 0, 0.3]; off.shoulderR = [-0.9, 0, -0.3]; off.neck = [-0.4, 0, 0];
      lift = -0.12 * k;
    } else if (move === 'hit') {
      const i = Math.max(0, Math.floor(ph)), P = POSES[i % 4], Q = POSES[(i + 3) % 4];
      const e = 1 - Math.exp(-f * 14);
      Object.keys(Object.assign({}, P, Q)).forEach((jn) => { const p = P[jn] || [0, 0, 0], q = Q[jn] || [0, 0, 0]; off[jn] = [0, 1, 2].map((a) => q[a] + (p[a] - q[a]) * e); });
      off.spine[0] = 0.1 * Math.exp(-f * 8) * k;
    } else if (move === 'spin') {
      turn = Math.PI * 2 * ((((Math.floor(ph) % 4) + 4) % 4 + f) / 4);
      off.shoulderL = [-0.6, 0, -0.1]; off.elbowL = [0, 0.3, -1.9];
      off.shoulderR = [-0.5, 0, 0.1]; off.elbowR = [0, -0.3, 1.9];
      off.hipR = [-0.3, 0, 0]; off.kneeR = [0.6, 0, 0];
    } else if (move === 'eat') { // Akte zum Mund, kauen
      const ch = Math.max(0, Math.sin(ph * Math.PI * 2));
      Object.assign(off, { hips: [0, 0, 0], spine: [0.05, 0, 0], neck: [0.12 + 0.06 * ch, 0, 0], kneeL: [0.05, 0, 0], kneeR: [0.05, 0, 0], hipL: [0, 0, 0], hipR: [0, 0, 0] });
      off.shoulderR = [-1.2 - 0.1 * ch, -0.2, -0.25]; off.elbowR = [-1.65 - 0.1 * ch, 0, 0];
      off.shoulderL = [-0.4, 0, 0.2]; off.elbowL = [-1.3, 0, 0];
      lift = 0;
    } else if (move === 'shake') { // Flasche schütteln
      const q = Math.sin(ph * Math.PI * 4);
      off.shoulderR = [-1.1 + 0.25 * q * k, 0, -0.2]; off.elbowR = [-1.2 + 0.4 * q * k, 0, 0];
      off.shoulderL = [-0.8, 0.2, 0.25]; off.elbowL = [-1.4, 0, 0];
      off.neck = [0.1, 0.1 * q * k, 0];
    } else if (move === 'drop') { // Mentos rein: Arm über die Flasche
      off.shoulderR = [-1.0, 0, -0.1]; off.elbowR = [-0.9, 0, 0];
      off.shoulderL = [-1.5, -0.3, 0.1]; off.elbowL = [-0.9, 0, 0];
      off.neck = [0.3, 0, 0];
    } else if (move === 'blast') { // Fontäne ins Gesicht: zurückgeworfen
      const e = Math.exp(-f * 3);
      off.spine = [-0.35 * k, 0, 0.05 * Math.sin(ph * 9)]; off.neck = [-0.4 * k, 0, 0];
      off.shoulderL = [-0.4, 0, 1.1 * k]; off.elbowL = [-0.6, 0, 0]; off.shoulderR = [-1.3 * k, 0, -0.5]; off.elbowR = [-0.5, 0, 0];
      lift = 0.02 * e;
    } else if (move === 'walk') {
      const w = Math.sin(ph * Math.PI);
      off.hipL = [-0.5 * w * k, 0, 0]; off.hipR = [0.5 * w * k, 0, 0];
      off.kneeL = [0.6 * Math.max(0, -w) * k + 0.05, 0, 0]; off.kneeR = [0.6 * Math.max(0, w) * k + 0.05, 0, 0];
      off.shoulderL = [0.4 * w * k, 0, 0.08]; off.shoulderR = [-0.4 * w * k, 0, -0.08];
      off.elbowL = [-0.3, 0, 0]; off.elbowR = [-0.3, 0, 0];
      off.hips = [0, 0.08 * w * k, 0]; off.spine = [0.04, -0.06 * w * k, 0]; off.neck = [0, 0.04 * w * k, 0];
      lift = -0.02 * Math.abs(Math.cos(ph * Math.PI)) * k;
    } else if (move === 'point') {
      off.shoulderR = [-1.45 * k - 0.1, 0.25, -0.05]; off.elbowR = [-0.1, 0, 0];
      off.shoulderL = [-0.2, 0, 0.1]; off.elbowL = [-1.6 * k, 0.4, 0];
    } else if (move === 'shrug') {
      const q = Math.sin(f * Math.PI);
      off.shoulderL = [-0.3, 0, 0.5 + 0.3 * q]; off.elbowL = [-1.4, 0.5, 0];
      off.shoulderR = [-0.3, 0, -0.5 - 0.3 * q]; off.elbowR = [-1.4, -0.5, 0];
      off.neck = [0, 0, 0.2 * q];
      lift = 0;
    } else if (move === 'typing') { // sitzt, tippt
      Object.assign(off, { hips: [0, 0, 0], spine: [0.15, 0, 0], neck: [0.1, 0, 0] });
      off.hipL = [-1.5, 0, 0.05]; off.hipR = [-1.5, 0, -0.05]; off.kneeL = [1.5, 0, 0]; off.kneeR = [1.5, 0, 0];
      const a = Math.max(0, Math.sin(ph * Math.PI * 4)), b = Math.max(0, Math.sin(ph * Math.PI * 4 + 2));
      off.shoulderL = [-0.9, 0, 0.1]; off.elbowL = [-0.7 - 0.25 * a, 0, 0];
      off.shoulderR = [-0.9, 0, -0.1]; off.elbowR = [-0.7 - 0.25 * b, 0, 0];
      lift = 0;
    }
    if (o.extra) Object.keys(o.extra).forEach((jn) => { off[jn] = (off[jn] || [0, 0, 0]).map((v, a) => v + (o.extra[jn][a] || 0)); });
    MC.apply(h, off, lift);
    if (shiftX) h.j.hips.position.x += shiftX;
    h.root.rotation.y = (o.yaw || 0) + turn;
  };

  // ---------- Bühne: Renderer in niedriger Auflösung, hart hochskaliert ----------
  MC.stage = function (parent, o) {
    T = window.THREE;
    o = o || {};
    const W = o.w || 1080, H = o.h || 1920, pix = o.pix || 3;
    const cw = Math.round(W / pix), ch = Math.round(H / pix);
    const renderer = new T.WebGLRenderer({ antialias: !!o.aa, alpha: o.bg == null, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.setSize(cw, ch, false);
    renderer.outputColorSpace = T.SRGBColorSpace;
    if (o.bg == null) renderer.setClearColor(0x000000, 0);
    const cv = renderer.domElement;
    Object.assign(cv.style, { position: 'absolute', left: (o.x || 0) + 'px', top: (o.y || 0) + 'px', width: W + 'px', height: H + 'px', imageRendering: pix > 1 ? 'pixelated' : 'auto' });
    parent.appendChild(cv);
    const mk = () => {
      const scene = new T.Scene();
      if (o.bg != null) scene.background = new T.Color(o.bg);
      if (o.fog) scene.fog = new T.Fog(o.fog[0], o.fog[1], o.fog[2]);
      const hemi = new T.HemisphereLight(o.sky || '#ffffff', o.ground || '#5a5060', o.hemi != null ? o.hemi : 1.0);
      const key = new T.DirectionalLight(o.key || '#fff2e0', o.keyI != null ? o.keyI : 1.6);
      key.position.set(1.5, 3, 3.5);
      const rim = new T.DirectionalLight(o.rim || '#9fc8ff', o.rimI != null ? o.rimI : 0.8);
      rim.position.set(-2.5, 2.5, -3);
      scene.add(hemi, key, rim);
      scene.userData = { hemi, key, rim };
      return scene;
    };
    const scene = mk();
    const camera = o.ortho
      ? new T.OrthographicCamera((-o.ortho * cw) / ch, (o.ortho * cw) / ch, o.ortho, -o.ortho, 0.1, 200)
      : new T.PerspectiveCamera(o.fov || 35, cw / ch, 0.05, 200);
    camera.position.set(0, 1.4, 4.5);
    camera.lookAt(0, 1.2, 0);
    return { renderer, scene, camera, canvas: cv, newScene: mk, render: (s, c) => renderer.render(s || scene, c || camera) };
  };
})();

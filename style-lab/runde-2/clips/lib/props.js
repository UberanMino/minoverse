/* Gemeinsame Requisiten und Effekte für die Welt-Rahmen (Stilrunde 2). Alles deterministisch. */
(function () {
  const P = (window.MP = {});
  const T = () => window.THREE;
  const { add, node, geo } = MC;

  // Segment-Plan: [{id, b0, b1}] → aktives Segment zur Zeit t
  P.plan = (segs) => (t) => {
    const b = t / MV.BEAT;
    for (let i = segs.length - 1; i >= 0; i--) if (b >= segs[i].b0 - 1e-6) return Object.assign({ i, a: t - MV.b(segs[i].b0) }, segs[i]);
    return Object.assign({ i: 0, a: t }, segs[0]);
  };

  // Rauschen (TV-Schnee) auf ein kleines Canvas, Muster wechselt pro Frame-Index
  P.snow = function (cv, w, h) {
    cv.width = w; cv.height = h;
    const g = cv.getContext('2d');
    const img = g.createImageData(w, h);
    return (frame, tint) => {
      let s = (frame * 9301 + 49297) % 233280;
      for (let i = 0; i < w * h; i++) {
        s = (s * 9301 + 49297) % 233280;
        const v = (s / 233280) * 255;
        img.data[i * 4] = tint ? v * tint[0] : v;
        img.data[i * 4 + 1] = tint ? v * tint[1] : v;
        img.data[i * 4 + 2] = tint ? v * tint[2] : v;
        img.data[i * 4 + 3] = 255;
      }
      g.putImageData(img, 0, 0);
    };
  };

  // Schaum-Fontäne (Mentos-Cola): n Partikel ab einem Ursprung; update(t, t0, origin, strength)
  P.foam = function (scene, n, seed) {
    const THREE = T();
    const R = MV.rng(seed || 4);
    const mats = [MC.mat('#f6f1e4'), MC.mat('#e8d7b0'), MC.mat('#c79a5a')];
    const list = [];
    for (let i = 0; i < n; i++) {
      const m = new THREE.Mesh(geo.ico(0.03 + R() * 0.04, 1), mats[i % 3]);
      m.userData = { d: R(), vx: (R() - 0.5) * 0.9, vz: (R() - 0.5) * 0.5, vy: 2.6 + R() * 1.8, life: 0.7 + R() * 0.5 };
      m.visible = false;
      scene.add(m);
      list.push(m);
    }
    return (t, t0, o, k, dur) => {
      dur = dur || 1.4;
      list.forEach((m) => {
        const u = m.userData;
        const a = ((t - t0) - u.d * dur * 0.6);
        const ok = t >= t0 && a > 0 && a < u.life;
        m.visible = ok;
        if (!ok) return;
        const kk = k == null ? 1 : k;
        m.position.set(o.x + u.vx * a * kk, o.y + u.vy * a * kk - 4.5 * a * a, o.z + u.vz * a * kk + 0.3 * a);
        m.scale.setScalar(1 + a * 1.5);
      });
    };
  };

  // Nachrichtenpult
  P.desk = function (scene, o) {
    const THREE = T();
    o = o || {};
    const g = new THREE.Group();
    add(g, geo.box(2.4, 0.08, 0.8), MC.mat(o.top || '#d9dde6'), [0, 0.78, 0]);
    add(g, geo.box(2.3, 0.74, 0.08), MC.mat(o.front || '#1b2b5a'), [0, 0.38, 0.36]);
    add(g, geo.box(2.3, 0.07, 0.09), new THREE.MeshBasicMaterial({ color: o.strip || '#ffcc00' }), [0, 0.62, 0.37]);
    if (o.logo) {
      const tx = P.textTex(o.logo, { w: 512, h: 96, bg: o.front || '#1b2b5a', fg: '#ffffff', font: '700 64px Oswald' });
      add(g, new THREE.PlaneGeometry(1.4, 0.26), new THREE.MeshBasicMaterial({ map: tx }), [0, 0.38, 0.405]);
    }
    scene.add(g);
    return g;
  };
  P.podium = function (scene, o) {
    const THREE = T();
    o = o || {};
    const g = new THREE.Group();
    add(g, geo.box(0.7, 1.1, 0.45), MC.mat(o.color || '#3a2a1a'), [0, 0.55, 0]);
    add(g, geo.box(0.78, 0.06, 0.5), MC.mat(o.top || '#5a4026'), [0, 1.12, -0.02], [-0.25, 0, 0]);
    if (o.logo) {
      const tx = P.textTex(o.logo, { w: 256, h: 256, bg: o.color || '#3a2a1a', fg: o.ink || '#e2b33a', font: '700 60px Oswald' });
      add(g, new THREE.PlaneGeometry(0.5, 0.5), new THREE.MeshBasicMaterial({ map: tx }), [0, 0.7, 0.23]);
    }
    for (let i = 0; i < (o.mics || 3); i++) {
      const mx = (i - 1) * 0.12;
      add(g, geo.cyl(0.008, 0.008, 0.35, 5), MC.mat('#222'), [mx, 1.3, 0.05], [0.5, 0, (i - 1) * 0.3]);
      add(g, geo.ball(0.03, 6, 5), MC.mat(['#c0392b', '#2c3e50', '#27ae60'][i % 3]), [mx + (i - 1) * 0.05, 1.45, 0.14]);
    }
    scene.add(g);
    return g;
  };
  // Text als Textur (für Pult-Logos, Schilder, Akten)
  P.textTex = function (text, o) {
    const THREE = T();
    o = o || {};
    const cv = document.createElement('canvas');
    cv.width = o.w || 256; cv.height = o.h || 64;
    const g = cv.getContext('2d');
    const tx = new THREE.CanvasTexture(cv);
    tx.colorSpace = THREE.SRGBColorSpace;
    const draw = () => {
      g.fillStyle = o.bg || '#000';
      g.fillRect(0, 0, cv.width, cv.height);
      g.fillStyle = o.fg || '#fff';
      g.font = o.font || '700 40px Oswald';
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      String(text).split('\n').forEach((line, i, arr) => g.fillText(line, cv.width / 2, cv.height / 2 + (i - (arr.length - 1) / 2) * (o.lh || 48)));
      if (o.after) o.after(g, cv);
      tx.needsUpdate = true;
    };
    draw();
    if (document.fonts) document.fonts.ready.then(draw);
    if (document.fonts && document.fonts.load) document.fonts.load(o.font || '700 40px Oswald').then(draw, () => {});
    return tx;
  };
  // Boden mit Kachel-/Rautenmuster
  P.floor = function (scene, c0, c1, rep, size) {
    const THREE = T();
    const tx = MC.pixTex(['01', '10'], { 0: c0, 1: c1 });
    tx.wrapS = tx.wrapT = THREE.RepeatWrapping;
    tx.repeat.set(rep || 20, rep || 20);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(size || 30, size || 30), new THREE.MeshLambertMaterial({ map: tx }));
    m.rotation.x = -Math.PI / 2;
    scene.add(m);
    return m;
  };
})();

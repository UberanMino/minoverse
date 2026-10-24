/* Minoverse Clip-Runtime, Stilrunde 2 (HyperFrames-kompatibel).
   - Zeitbasis: 150 BPM, 32 Schläge = 8 Takte = 12,8 s, Drop auf Schlag 8 (3,2 s)
   - Alles deterministisch aus der Zeit t (kein Math.random, keine Uhr)
   - Zeichnen über MV.onFrame(fn): läuft bei hf-seek, bei GSAP-Updates und bei MV.seek
   - Lippen: MV.VO[id] = {t0, hz, env:[0..1]} aus den Stimmdateien, MV.talk(id, t)
   - Live-Vorschau: Elternseite schickt postMessage {mv:'seek', t} */
(function () {
  const MV = (window.MV = {});
  MV.BPM = 150;
  MV.BEAT = 60 / MV.BPM;
  MV.BAR = MV.BEAT * 4;
  MV.BEATS = 32;
  MV.DUR = MV.BEAT * MV.BEATS;
  MV.DROP = MV.BEAT * 8;
  MV.b = (n) => n * MV.BEAT;
  MV.clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  MV.lerp = (a, b, k) => a + (b - a) * k;
  MV.k = (t, t0, d) => MV.clamp((t - t0) / d, 0, 1); // 0..1 Fortschritt
  MV.ease = {
    out: (k) => 1 - Math.pow(1 - k, 3),
    inout: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    back: (k, s = 1.7) => 1 + (s + 1) * Math.pow(k - 1, 3) + s * Math.pow(k - 1, 2),
    elastic: (k) => (k === 0 ? 0 : k === 1 ? 1 : Math.pow(2, -10 * k) * Math.sin((k * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1),
  };
  MV.rng = function (seed) {
    let s = seed | 0;
    return function () {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  MV.hash = (n) => {
    const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  MV.noise = (x, s) => Math.sin(x * 1.7 + s * 3.1) * 0.6 + Math.sin(x * 3.3 + s * 1.3) * 0.4;
  // Impuls auf jedem Schlag (nach "from"), klingt exponentiell ab
  MV.pulse = (t, decay = 8, every = 1, from = 0) => {
    if (t < from) return 0;
    const p = ((t - from) % (MV.BEAT * every)) / MV.BEAT;
    return Math.exp(-p * decay);
  };
  MV.imp = (t, t0, tau = 0.15) => (t < t0 ? 0 : Math.exp(-(t - t0) / tau));
  MV.beat = (t) => Math.floor(t / MV.BEAT + 1e-6);
  MV.after = (t) => t >= MV.DROP - 0.005;

  MV.VO = {};
  MV.talk = function (id, t) {
    const v = MV.VO[id];
    if (!v) return 0;
    const i = Math.floor((t - v.t0) * v.hz);
    return i < 0 || i >= v.env.length ? 0 : v.env[i];
  };
  MV.talkAny = (ids, t) => ids.reduce((m, id) => Math.max(m, MV.talk(id, t)), 0);

  const hooks = [];
  MV.onFrame = (fn) => hooks.push(fn);
  let lastT = -1;
  MV.render = (t) => {
    lastT = t;
    for (const fn of hooks) fn(t);
  };
  window.addEventListener('hf-seek', (e) => MV.render(e.detail.time));

  MV.register = function (id, tl) {
    const proxy = { t: 0 };
    tl.to(proxy, { t: MV.DUR, duration: MV.DUR, ease: 'none', onUpdate: () => { if (Math.abs(proxy.t - lastT) > 1e-4) MV.render(proxy.t); } }, 0);
    window.__timelines = window.__timelines || {};
    window.__timelines[id] = tl;
    MV.tl = tl;
    tl.seek(0);
    MV.render(0);
  };
  MV.seek = function (t) {
    t = Math.max(0, Math.min(MV.DUR - 0.001, t));
    if (MV.tl) MV.tl.seek(t, false);
    MV.render(t);
  };
  // Text in Zeichen-Spans zerlegen (für Fallblatt, Tippen)
  MV.type = (el, txt, k) => { const n = Math.floor(txt.length * MV.clamp(k, 0, 1)); el.textContent = txt.slice(0, n); };

  window.addEventListener('message', (e) => {
    if (e.data && e.data.mv === 'seek') MV.seek(e.data.t);
  });
  // Eigenständige Vorschau: ?play=1 spielt in Echtzeit
  if (/[?&]play=1/.test(location.search)) {
    const t0 = performance.now();
    const loop = () => { MV.seek(((performance.now() - t0) / 1000) % MV.DUR); requestAnimationFrame(loop); };
    window.addEventListener('load', () => requestAnimationFrame(loop));
  }
})();

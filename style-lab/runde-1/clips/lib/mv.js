/* Minoverse Clip-Runtime (HyperFrames-kompatibel).
   - Zeitbasis: 132 BPM, 16 Schläge = 4 Takte ≈ 7,27 s
   - Alles deterministisch aus der Zeit t abgeleitet (kein Math.random, keine Uhr)
   - Canvas/Sprites zeichnen über MV.onFrame(fn) → läuft bei hf-seek und bei MV.seek
   - Live-Vorschau: Elternseite schickt postMessage {mv:'seek', t} */
(function () {
  const MV = (window.MV = {});
  MV.BPM = 132;
  MV.BEAT = 60 / MV.BPM;
  MV.BAR = MV.BEAT * 4;
  MV.DUR = MV.BAR * 4;
  MV.b = (n) => n * MV.BEAT; // Schlag → Sekunden

  MV.rng = function (seed) {
    let s = seed | 0;
    return function () {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  // Hash-Rauschen für "zufällige" Werte pro Schlag/Frame
  MV.hash = (n) => {
    const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  // Impuls auf jedem Schlag, klingt exponentiell ab (0..1)
  MV.pulse = (t, decay = 8, every = 1) => {
    const p = (t % (MV.BEAT * every)) / MV.BEAT;
    return Math.exp(-p * decay);
  };
  MV.beatIndex = (t) => Math.floor(t / MV.BEAT + 1e-6);

  const hooks = [];
  MV.onFrame = (fn) => hooks.push(fn);
  MV.render = (t) => {
    for (const fn of hooks) fn(t);
  };
  window.addEventListener('hf-seek', (e) => MV.render(e.detail.time));

  MV.register = function (id, tl) {
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

  // Sprite-Sheet auf ein Element legen; liefert Funktion(frameIndex)
  MV.sprite = function (el, o) {
    el.style.backgroundImage = 'url(' + o.src + ')';
    el.style.backgroundSize = o.cols * 100 + '% ' + Math.ceil(o.frames / o.cols) * 100 + '%';
    el.style.backgroundRepeat = 'no-repeat';
    const rows = Math.ceil(o.frames / o.cols);
    return function (i) {
      i = ((Math.floor(i) % o.frames) + o.frames) % o.frames;
      const c = i % o.cols,
        r = Math.floor(i / o.cols);
      el.style.backgroundPosition =
        (o.cols > 1 ? (c / (o.cols - 1)) * 100 : 0) + '% ' + (rows > 1 ? (r / (rows - 1)) * 100 : 0) + '%';
    };
  };
  MV.CG = { src: 'assets/cg_dance.webp', cols: 8, frames: 40, w: 236, h: 420, fps: 10 };
  MV.CLIMB = { src: 'assets/mm_climb.webp', cols: 6, frames: 30, w: 282, h: 480, fps: 10 };

  // Text in einzelne Zeichen-Spans zerlegen
  MV.split = function (el) {
    const txt = el.textContent;
    el.textContent = '';
    return [...txt].map((ch) => {
      const s = document.createElement('span');
      s.textContent = ch === ' ' ? ' ' : ch;
      s.style.display = 'inline-block';
      el.appendChild(s);
      return s;
    });
  };

  // Film-Korn: vorberechnete Rauschkacheln, Auswahl nach Frame
  MV.grain = function (canvas, opts = {}) {
    const W = (canvas.width = opts.w || 270),
      H = (canvas.height = opts.h || 480);
    const ctx = canvas.getContext('2d');
    const frames = [];
    const r = MV.rng(opts.seed || 7);
    for (let f = 0; f < 8; f++) {
      const img = ctx.createImageData(W, H);
      for (let i = 0; i < img.data.length; i += 4) {
        const v = r() * 255;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = opts.alpha || 40;
      }
      frames.push(img);
    }
    MV.onFrame((t) => ctx.putImageData(frames[Math.floor(t * 24) % 8], 0, 0));
  };


  // Plasma (2D, niedrige Auflösung, hochskaliert) – psychedelischer Hintergrund
  MV.plasma = function (canvas, o = {}) {
    const W = (canvas.width = o.w || 108), H = (canvas.height = o.h || 192);
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(W, H);
    return function (t, k = 1, hue = 0) {
      const d = img.data;
      for (let y = 0; y < H; y++)
        for (let x = 0; x < W; x++) {
          const u = x / W - 0.5, v = y / H - 0.5;
          const r = Math.sqrt(u * u + v * v);
          const s = Math.sin(u * 10 * k + t * 1.7) + Math.sin(v * 13 * k - t * 1.3) + Math.sin((u + v) * 9 + t) + Math.sin(r * 30 * k - t * 3.1);
          const a = s * 0.25 + hue;
          const i = (y * W + x) * 4;
          d[i] = 128 + 127 * Math.sin(Math.PI * a);
          d[i + 1] = 128 + 127 * Math.sin(Math.PI * a + 2.1);
          d[i + 2] = 128 + 127 * Math.sin(Math.PI * a + 4.2);
          d[i + 3] = 255;
        }
      ctx.putImageData(img, 0, 0);
    };
  };

  // Mandelbrot-Zoom (WebGL) – liefert draw(t, {zoom, rot, hue, cx, cy, kaleido})
  MV.fractal = function (canvas, o = {}) {
    canvas.width = o.w || 540; canvas.height = o.h || 960;
    const gl = canvas.getContext('webgl', { preserveDrawingBuffer: true });
    if (!gl) return () => {};
    const vs = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
    const fs = `precision highp float;uniform vec2 R;uniform float Z,A,H,K;uniform vec2 C;
      vec3 pal(float t){return .5+.5*cos(6.2831*(vec3(1.,1.,1.)*t+vec3(0.,.33,.67)+H));}
      void main(){vec2 uv=(gl_FragCoord.xy-.5*R)/R.y;
        if(K>0.){float a=atan(uv.y,uv.x),r=length(uv);float n=6.;a=mod(a,6.2831/n);a=abs(a-3.1415/n);uv=r*vec2(cos(a),sin(a));}
        float ca=cos(A),sa=sin(A);uv=mat2(ca,-sa,sa,ca)*uv;
        vec2 c=C+uv*Z,z=vec2(0.);float i=0.;
        for(int k=0;k<220;k++){z=vec2(z.x*z.x-z.y*z.y,2.*z.x*z.y)+c;if(dot(z,z)>256.)break;i+=1.;}
        float sm=i-log2(log2(dot(z,z)))+4.;
        vec3 col=i>=219.?vec3(0.):pal(sm*.035);
        gl_FragColor=vec4(col,1.);}`;
    const sh = (t, src) => { const s = gl.createShader(t); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr); gl.useProgram(pr);
    const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const U = (n) => gl.getUniformLocation(pr, n);
    return function (p) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(U('R'), canvas.width, canvas.height);
      gl.uniform1f(U('Z'), p.zoom); gl.uniform1f(U('A'), p.rot || 0); gl.uniform1f(U('H'), p.hue || 0); gl.uniform1f(U('K'), p.kaleido ? 1 : 0);
      gl.uniform2f(U('C'), p.cx ?? -0.743643887, p.cy ?? 0.131825904);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
  };

  // Live-Vorschau aus der Bewertungsseite
  window.addEventListener('message', (e) => {
    const d = e.data;
    if (d && d.mv === 'seek') MV.seek(d.t);
  });
  // Direkt geöffnet mit #play → ohne Ton selbst abspielen (nur zur Kontrolle)
  if (location.hash === '#play') {
    const t0 = performance.now();
    const loop = () => {
      MV.seek(((performance.now() - t0) / 1000) % MV.DUR);
      requestAnimationFrame(loop);
    };
    window.addEventListener('load', () => requestAnimationFrame(loop));
  }
})();

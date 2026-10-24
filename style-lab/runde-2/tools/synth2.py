"""Stilrunde 2: prozedurale Hard-House-Platzhalter (150 BPM, 32 Schlaege) + Piper-Stimmen + Lippen-Huellkurven."""
import numpy as np, subprocess, os, sys
from scipy import signal

SR = 44100
BPM = 150
BEAT = 60 / BPM
BAR = BEAT * 4
DUR = BEAT * 32
N = int(round(DUR * SR))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'build2/clips/audio')
VO = os.path.join(HERE, 'vo2')
rng = np.random.default_rng(150)


def buf():
    return np.zeros(N + SR * 2)


def at(b, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(b):
        return
    n = min(len(x), len(b) - i)
    b[i:i + n] += x[:n] * g


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    e = np.exp(-t / max(d, 1e-4))
    na = int(a * SR)
    if na > 0:
        e[:na] *= np.linspace(0, 1, na)
    return e


def lp(x, f, o=2):
    b, a = signal.butter(o, min(f / (SR / 2), 0.99), 'low')
    return signal.lfilter(b, a, x)


def hp(x, f, o=2):
    b, a = signal.butter(o, min(f / (SR / 2), 0.99), 'high')
    return signal.lfilter(b, a, x)


def bp(x, lo, hi, o=2):
    b, a = signal.butter(o, [lo / (SR / 2), min(hi / (SR / 2), 0.99)], 'band')
    return signal.lfilter(b, a, x)


def saw(f, n, ph=0):
    t = np.arange(n) / SR
    return 2 * ((t * f + ph) % 1) - 1


def sq(f, n):
    return np.sign(np.sin(2 * np.pi * f * np.arange(n) / SR))


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


# ---------- instruments ----------
def kick(dist=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.22)
    x += 0.3 * hp(rng.standard_normal(n), 3000) * env(n, 0.0005, 0.004)
    return np.tanh(x * dist) / np.tanh(dist)


def clap():
    n = int(0.3 * SR)
    x = bp(rng.standard_normal(n), 900, 5000) * env(n, 0.001, 0.09)
    for d in (0.008, 0.017):
        x[int(d * SR):] += 0.6 * bp(rng.standard_normal(n - int(d * SR)), 900, 5000) * env(n - int(d * SR), 0.0005, 0.01)
    return x * 0.7


def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    return hp(rng.standard_normal(n), 7000) * env(n, 0.0005, 0.08 if open_ else 0.018) * 0.35


def garage_drums(b, kick_g=1.0, hat_g=1.0, clap_g=1.0, dist=1.0, bars=range(4), skip_kick_bar=None):
    k = kick(dist)
    for bar in bars:
        for beat in range(4):
            t = (bar * 4 + beat) * BEAT
            if bar != skip_kick_bar:
                at(b, k, t, kick_g)
            if beat in (1, 3):
                at(b, clap(), t, clap_g * 0.8)
            # 2-step shuffle hats
            at(b, hat(), t + BEAT * 0.5 + BEAT * 0.08, hat_g)
            at(b, hat(), t + BEAT * 0.75 + BEAT * 0.04, hat_g * 0.5)
        at(b, hat(True), (bar * 4 + 3.5) * BEAT, hat_g * 0.7)


def garage_bass(b, roots, g=0.5, cutoff=900, wob=True):
    """Speed-Garage-Orgelbass: Saege+Square, Filter mit Achtel-LFO."""
    for bar, r in enumerate(roots):
        for step in range(8):
            if step in (1, 4) and bar % 2 == 0:
                continue
            t = bar * BAR + step * BEAT / 2 + (BEAT * 0.08 if step % 2 else 0)
            n = int(BEAT * 0.45 * SR)
            f = note(r + (12 if step == 6 else 0))
            x = 0.6 * saw(f, n) + 0.4 * sq(f * 1.003, n)
            c = cutoff * (1.6 if (wob and step % 2) else 1.0)
            x = lp(x, c, 2) * env(n, 0.003, 0.12)
            x += 0.6 * np.sin(2 * np.pi * f / 2 * np.arange(n) / SR) * env(n, 0.003, 0.15)
            at(b, np.tanh(x * 1.5), t, g)


def pad(b, chords, g=0.15, cutoff=2400, bar_len=1):
    for i, ch in enumerate(chords):
        n = int(BAR * bar_len * SR)
        x = np.zeros(n)
        for m in ch:
            for det in (-0.12, 0, 0.12):
                x += saw(note(m + det), n, rng.random())
        x = lp(x / (len(ch) * 3), cutoff)
        e = np.minimum(1, np.arange(n) / (0.2 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.2 * SR))
        at(b, x * e, i * BAR * bar_len, g)


def bell(m, d=0.8):
    n = int(d * 1.5 * SR)
    t = np.arange(n) / SR
    f = note(m)
    x = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) + 0.25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 10)
    return x * env(n, 0.001, d) * 0.4


def pluck(m, d=0.25, bright=3000):
    n = int(d * 2 * SR)
    x = saw(note(m), n) + 0.5 * saw(note(m) * 1.007, n)
    return lp(x, bright) * env(n, 0.001, d) * 0.3


def choir(ch, n):
    x = np.zeros(n)
    for m in ch:
        for det in (-0.15, 0, 0.15):
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * np.arange(n) / SR + rng.random() * 6)
            ph = np.cumsum(note(m + det) * vib) / SR
            x += 2 * (ph % 1) - 1
    y = bp(x, 650, 950) + 0.7 * bp(x, 1000, 1300) + 0.3 * bp(x, 2600, 3200)
    e = np.minimum(1, np.arange(n) / (0.15 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.3 * SR))
    return y * e / len(ch) * 0.8


def noise_riser(n, f0=300, f1=8000):
    x = rng.standard_normal(n)
    out = np.zeros(n)
    seg = n // 16
    for i in range(16):
        f = f0 * (f1 / f0) ** (i / 15)
        s = slice(i * seg, (i + 1) * seg if i < 15 else n)
        out[s] = bp(x[s], f * 0.7, min(f * 1.4, 20000))
    return out * np.linspace(0, 1, n) ** 2 * 0.35


def impact():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-t * 12)) / SR) * env(n, 0.001, 0.5)
    x += lp(rng.standard_normal(n), 2500) * env(n, 0.001, 0.3) * 0.6
    return np.tanh(x * 2) * 0.8


def click():
    n = int(0.03 * SR)
    return bp(rng.standard_normal(n), 2000, 9000) * env(n, 0.0002, 0.006) * 0.8


def stamp():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * np.cumsum(60 + 140 * np.exp(-t * 40)) / SR) * env(n, 0.0005, 0.08)
    x += lp(rng.standard_normal(n), 1800) * env(n, 0.0005, 0.03)
    return np.tanh(x * 2)


def ding():
    return bell(96, 0.6) * 0.6


def kaching():
    n = int(0.9 * SR)
    x = np.zeros(n)
    x[:int(0.08 * SR)] += hp(rng.standard_normal(int(0.08 * SR)), 4000) * 0.5
    at(x, bell(100, 0.5), 0.07)
    at(x, bell(105, 0.5), 0.12)
    return x


def sizzle(n):
    x = hp(rng.standard_normal(n), 3000) * 0.08
    pops = rng.random(n) < 0.0009
    x += hp(pops * rng.standard_normal(n) * 3, 2000) * 0.4
    return x


def thunder():
    n = int(2.5 * SR)
    x = lp(rng.standard_normal(n), 300) * env(n, 0.05, 0.9) * 2
    x += lp(rng.standard_normal(n), 1200) * env(n, 0.001, 0.08) * 0.8
    return np.tanh(x)


def heartbeat():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 50 * t) * env(n, 0.002, 0.08)
    at(x, np.sin(2 * np.pi * 45 * t[:int(0.3 * SR)]) * env(int(0.3 * SR), 0.002, 0.07) * 0.7, 0.18)
    return x


def shepard(n, up=True):
    t = np.arange(n) / SR
    x = np.zeros(n)
    for k in range(6):
        pos = (k / 6 + (t / DUR if up else -t / DUR)) % 1
        f = 55 * 2 ** (pos * 6)
        amp = np.sin(np.pi * pos) ** 2
        x += amp * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return x * 0.12


# ---------- voice + Lippen-Huellkurve ----------
import json
ENVS = {}


def voice(name, rate_mult=1.0, fx='', tempo=1.0):
    src = os.path.join(VO, name + '.wav')
    af = ('atempo=%.3f,' % tempo if tempo != 1.0 else '') + 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse'
    af += f',asetrate={int(16000 * rate_mult)},aresample={SR}'
    if fx:
        af += ',' + fx
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-af', af, '-ac', '1', '-f', 'f32le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).astype(float)
    return x / (np.abs(x).max() + 1e-9) * 0.9


def place_voice(clip, vid, mus, vox, v, t, g=1.0, duck=0.5):
    at(vox, v, t, g)
    i0, i1 = int(t * SR), int((t + len(v) / SR) * SR)
    e = np.ones(len(mus))
    e[i0:i1] = duck
    e = np.convolve(e, np.ones(2000) / 2000, mode='same')
    mus *= e
    hz = 30
    hop = SR // hz
    n = len(v) // hop
    rms = np.array([np.sqrt(np.mean(v[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    rms = rms / (rms.max() + 1e-9)
    env_ = np.clip((rms - 0.08) / 0.6, 0, 1) ** 0.8
    ENVS.setdefault(clip, {})[vid] = {'t0': round(t, 3), 'hz': hz, 'dur': round(len(v) / SR, 3), 'env': [round(float(a), 2) for a in env_]}
    print(f'  voice {vid}: {t:.2f}s – {t + len(v) / SR:.2f}s')


def finish(name, mus, vox, mgain=0.8):
    mix = mus[:N] * mgain + vox[:N]
    tail = (mus[N:N + SR] * mgain + vox[N:N + SR])
    mix[:len(tail)] += tail * np.linspace(1, 0, len(tail)) * 0.6
    mix = np.tanh(mix * 1.1)
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.95
    fn = os.path.join(OUT, name + '.mp3')
    p = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', 'loudnorm=I=-14:TP=-1.0', '-ar', '44100', '-b:a', '160k', fn],
                       input=mix.astype(np.float32).tobytes())
    with open(os.path.join(OUT, f'vo_{name}.js'), 'w') as fh:
        fh.write('/* Lippen-Huellkurven aus synth2.py (generiert) */\n')
        for vid, d in ENVS.get(name, {}).items():
            fh.write(f'MV.VO[{json.dumps(vid)}] = {json.dumps(d)};\n')
    print(name, 'ok', p.returncode)


# ---------- Hard-House-Bausteine ----------
DROPB = 8  # Drop auf Schlag 8


def tb(beat):
    return beat * BEAT


def hh_drums(b, from_beat=DROPB, to_beat=32, kick_g=1.0, dist=2.2, hat_g=1.0, clap_g=0.9, roll_at=None):
    k = kick(dist)
    for i in range(from_beat, to_beat):
        t = tb(i)
        at(b, k, t, kick_g)
        at(b, hat(True), t + BEAT * 0.5, 0.55 * hat_g)  # Offbeat-Open-Hat
        at(b, hat(), t + BEAT * 0.25, 0.35 * hat_g)
        at(b, hat(), t + BEAT * 0.75, 0.35 * hat_g)
        if i % 2 == 1:
            at(b, clap(), t, clap_g)
    if roll_at is not None:  # Snare-Roll in den letzten Takt vor einem Wechsel
        for s in range(16):
            at(b, clap(), tb(roll_at) + s * BEAT / 4, 0.25 + 0.04 * s)


def donk(m, n=None):
    """Hard-House-'Donk'/Offbeat-Bass: kurzer, perkussiver Orgel-Bass."""
    n = n or int(BEAT * 0.4 * SR)
    t = np.arange(n) / SR
    f = note(m)
    x = np.sin(2 * np.pi * f * t + 2.5 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 30))
    x += 0.4 * saw(f, n)
    return np.tanh(lp(x, 1800) * env(n, 0.002, 0.09) * 2) * 0.8


def offbass(b, roots, from_beat=DROPB, to_beat=32, g=0.6):
    for i in range(from_beat, to_beat):
        r = roots[((i - from_beat) // 4) % len(roots)]
        at(b, donk(r), tb(i) + BEAT * 0.5, g)


def hoover(m, n):
    """Hoover-artiger Lead: verstimmte Saegen mit Pitch-Bend nach unten."""
    t = np.arange(n) / SR
    bend = 1 + 0.06 * np.exp(-t * 8)
    x = np.zeros(n)
    for d in (-0.25, -0.1, 0, 0.1, 0.25):
        ph = np.cumsum(note(m + d) * bend) / SR
        x += 2 * (ph % 1) - 1
    x = lp(x / 5, 2600)
    e = np.minimum(1, t / 0.01) * np.minimum(1, (n - np.arange(n)) / (0.05 * SR))
    return x * e * 0.5


def stabs(b, seq, from_beat=DROPB, g=0.45, length=0.45):
    """seq: Liste (beat_offset, midi) innerhalb eines 4-Takt-Musters (16 Schlaege)."""
    for rep in range(from_beat, 32, 16):
        for off, m in seq:
            tt = rep + off
            if tt < 32:
                at(b, hoover(m, int(BEAT * length * SR)), tb(tt), g)


def supersaw(ch, n, cutoff=4000):
    x = np.zeros(n)
    for m in ch:
        for d in (-0.2, -0.08, 0, 0.08, 0.2):
            x += saw(note(m + d), n, rng.random())
    x = lp(x / (len(ch) * 5), cutoff)
    return x


def gate_pad(b, chords, from_beat=DROPB, g=0.22, cutoff=4500):
    """Trance-Gate: 16tel-gegatete Supersaw-Akkorde, ein Akkord pro Takt."""
    for i in range(from_beat, 32, 4):
        ch = chords[((i - from_beat) // 4) % len(chords)]
        n = int(BAR * SR)
        x = supersaw(ch, n, cutoff)
        gate = ((np.arange(n) / SR) % (BEAT / 4)) < (BEAT / 4) * 0.6
        x *= np.convolve(gate.astype(float), np.ones(200) / 200, mode='same')
        at(b, x, tb(i), g)


def zap():
    n = int(0.12 * SR)
    x = hp(rng.standard_normal(n), 1200) * env(n, 0.0005, 0.05)
    x += 0.4 * sq(1800, n) * env(n, 0.0005, 0.02)
    return x * 0.5


def tv_off():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 6000 * np.exp(-t * 9) + 80
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.25) * 0.5


def chip(m, n, duty=0.25):
    t = np.arange(n) / SR
    x = (((t * note(m)) % 1) < duty).astype(float) * 2 - 1
    return x * env(n, 0.002, 0.12) * 0.22


def gong_db():
    """Bahnhofsgong: drei Glockentöne (eigene Tonfolge)."""
    x = np.zeros(int(2.2 * SR))
    for i, m in enumerate([76, 72, 79]):
        at(x, bell(m, 1.1) * 1.2, i * 0.42)
    return x


def train_pass(n):
    x = lp(rng.standard_normal(n), 900) * 0.6
    t = np.arange(n) / SR
    clack = np.zeros(n)
    for k in range(int(n / SR / 0.11)):
        i = int(k * 0.11 * SR)
        if i < n:
            clack[i:i + 300] += np.hanning(300)[:len(clack[i:i + 300])] * 1.2
    x += lp(clack * rng.standard_normal(n), 2500) * 0.5
    swell = np.sin(np.pi * np.clip(t / (n / SR), 0, 1)) ** 0.7
    return x * swell


def horn(n):
    t = np.arange(n) / SR
    x = 0.5 * saw(note(57), n) + 0.5 * saw(note(61), n)
    return lp(x, 1400) * np.minimum(1, t / 0.05) * np.minimum(1, (n - np.arange(n)) / (0.2 * SR)) * 0.5


def typewriter():
    n = int(0.05 * SR)
    return bp(rng.standard_normal(n), 1500, 7000) * env(n, 0.0003, 0.012) * 1.1


def fax(n):
    t = np.arange(n) / SR
    f = np.where((t * 6) % 1 < 0.5, 1650, 2100)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.12


def rain_hotdogs(n):
    x = hp(rng.standard_normal(n), 2500) * 0.06
    plops = rng.random(n) < 0.0012
    x += lp(plops * rng.standard_normal(n) * 5, 900) * 0.5
    return x


ROOTS = [45, 45, 48, 43]  # A A C G


def s01():  # MINO-KABEL: News-Jingle, Zapping, Hard House, TV aus
    m, v = buf(), buf()
    for i, mm in enumerate([81, 76, 79, 84, 88]):
        at(m, bell(mm, 0.5), i * BEAT * 0.5, 0.7)
    pad(m, [[57, 61, 64], [57, 61, 64]], g=0.1)
    at(m, noise_riser(int(BAR * SR)), tb(4), 0.8)
    at(m, impact(), tb(8), 0.9)
    hh_drums(m, 8, 30, roll_at=None)
    offbass(m, ROOTS, 8, 30)
    stabs(m, [(0, 69), (1.5, 69), (3, 72), (4, 67), (6, 69), (8, 69), (9.5, 69), (11, 76), (12, 74), (14, 72)], 8, g=0.32)
    for i in range(8, 28):
        at(m, zap(), tb(i), 0.5)
    for i in range(28, 30):
        for s in range(4):
            at(m, zap(), tb(i) + s * BEAT / 4, 0.4)
    at(m, tv_off(), tb(30), 0.9)
    place_voice('01', '1a', m, v, voice('1a', 1.0, 'highpass=f=120', tempo=1.2), 0.15, duck=0.6)
    place_voice('01', '1c', m, v, voice('1c', 0.95, 'highpass=f=150,aecho=0.6:0.4:40:0.25'), tb(20) + 0.05, g=0.85, duck=0.65)
    place_voice('01', '1b', m, v, voice('1b', 1.0, 'highpass=f=120'), tb(28) + 0.05, duck=0.4)
    finish('01', m, v)


def s02():  # SIM MINO: Chiptune-Aufbau, Katastrophe = Drop, Regen
    m, v = buf(), buf()
    arp = [69, 72, 76, 72, 69, 72, 76, 79]
    for i in range(16):
        at(m, chip(arp[i % 8] + (0 if i < 8 else 2), int(BEAT * 0.5 * SR)), i * BEAT / 2, 1.0)
    for i in range(8):
        at(m, chip(45 if i < 4 else 43, int(BEAT * SR), 0.5), tb(i), 0.7)
    at(m, click(), tb(7), 1.0)
    at(m, noise_riser(int(BEAT * 3 * SR)), tb(5), 0.6)
    at(m, impact(), tb(8), 0.9)
    hh_drums(m, 8, 32)
    offbass(m, ROOTS, 8, 32)
    for rep in range(8, 32, 2):
        for k, mm in enumerate([81, 84, 88, 84]):
            at(m, chip(mm, int(BEAT * 0.25 * SR)), tb(rep) + k * BEAT / 4 + (BEAT if (rep // 2) % 2 else 0) * 0, 0.8)
    at(m, rain_hotdogs(int((DUR - tb(8)) * SR)), tb(8), 1.0)
    for i in (12, 16, 20, 24):
        at(m, ding(), tb(i), 0.6)
    place_voice('02', '2a', m, v, voice('2a', 1.0, 'highpass=f=120'), 0.25, duck=0.55)
    place_voice('02', '2b', m, v, voice('2b', 1.0, 'highpass=f=200', tempo=1.3), tb(25.8), g=0.8, duck=0.5)
    finish('02', m, v)


def s03():  # AKTE MINO: Schreibmaschine, Fax, Stempel-Drop
    m, v = buf(), buf()
    for i in range(32):
        at(m, typewriter(), i * BEAT / 4 + (BEAT * 0.05 if i % 3 == 0 else 0), 0.8)
    at(m, fax(int(BEAT * 2.5 * SR)), tb(5), 0.9)
    at(m, ding(), tb(4), 0.5)
    at(m, stamp(), tb(8), 1.2)
    at(m, impact(), tb(8), 0.7)
    hh_drums(m, 8, 32, hat_g=0.6)
    for i in range(8, 32):
        for s in (0.25, 0.75):
            at(m, typewriter(), tb(i) + BEAT * s, 0.6)
    offbass(m, [45, 45, 41, 43], 8, 32)
    stabs(m, [(0, 69), (2, 72), (4, 69), (6, 76), (8, 69), (10, 72), (12, 74), (14, 71)], 8, g=0.28)
    for i in (12, 16, 20, 24, 28):
        at(m, stamp(), tb(i), 0.7)
    place_voice('03', '3a', m, v, voice('3a', 1.0, 'highpass=f=120'), 0.2, duck=0.6)
    place_voice('03', '3b', m, v, voice('3b', 0.92, 'highpass=f=150,aecho=0.5:0.4:30:0.2'), tb(28) + 0.1, duck=0.45)
    finish('03', m, v)


def s04():  # MINO QUEST: MIDI-Adventure-Thema -> Hard House mit Chip-Lead
    m, v = buf(), buf()
    mel = [69, 72, 74, 76, 74, 72, 69, 67]
    for i, mm in enumerate(mel):
        at(m, pluck(mm, 0.35, 2500), tb(i), 0.55)
        at(m, bell(mm + 12, 0.3), tb(i), 0.15)
    pad(m, [[57, 60, 64], [55, 59, 62]], g=0.1, cutoff=1500)
    for i in range(0, 8):
        at(m, click(), tb(i) + BEAT * 0.9, 0.3)
    at(m, impact(), tb(8), 0.9)
    hh_drums(m, 8, 32)
    offbass(m, [45, 43, 41, 43], 8, 32)
    lead = [81, 84, 86, 88, 86, 84, 81, 79]
    for i in range(8, 32):
        at(m, chip(lead[i % 8], int(BEAT * 0.45 * SR), 0.5), tb(i) + BEAT * 0.5, 0.9)
    place_voice('04', '4a', m, v, voice('4a', 1.0, 'highpass=f=120'), 0.3, duck=0.6)
    place_voice('04', '4b', m, v, voice('4b', 0.9, 'highpass=f=150'), tb(4.5), duck=0.6)
    place_voice('04', '4d', m, v, voice('4d', 1.05, 'highpass=f=200'), tb(17), g=0.8, duck=0.7)
    place_voice('04', '4c', m, v, voice('4c', 1.0, 'highpass=f=120'), tb(28), duck=0.45)
    finish('04', m, v)


def s05():  # HAUPTBAHNHOF: Gong + Durchsage, Zug = Drop, Trance-Gate
    m, v = buf(), buf()
    amb = lp(rng.standard_normal(int(tb(9) * SR)), 600) * 0.05
    at(m, amb, 0, 1.0)
    at(m, gong_db(), 0.0, 0.75)
    at(m, noise_riser(int(BEAT * 3 * SR)), tb(5), 0.6)
    at(m, horn(int(0.9 * SR)), tb(7.2), 0.8)
    at(m, impact(), tb(8), 0.9)
    at(m, train_pass(int(tb(16) * SR)), tb(8), 0.9)
    hh_drums(m, 8, 30)
    offbass(m, ROOTS, 8, 30)
    gate_pad(m, [[57, 60, 64, 69], [57, 60, 64, 69], [60, 64, 67, 72], [55, 59, 62, 67]], 8, g=0.22)
    at(m, gong_db(), tb(27.2), 0.5)
    DS = 'highpass=f=300,lowpass=f=3400,aecho=0.7:0.6:60|120:0.35|0.2'
    place_voice('05', '5b', m, v, voice('5b', 1.0, DS, tempo=1.2), 1.15, duck=0.6)
    place_voice('05', '5a', m, v, voice('5a', 1.0, 'highpass=f=120', tempo=1.05), tb(23.2), duck=0.55)
    place_voice('05', '5c', m, v, voice('5c', 1.0, DS, tempo=1.2), tb(27.9), duck=0.4)
    finish('05', m, v)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or [f'{i:02d}' for i in range(1, 6)]
    for w in which:
        globals()['s' + w]()

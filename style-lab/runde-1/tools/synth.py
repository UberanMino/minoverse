"""Prozedurale 4-Takt-Loops (132 BPM) + Piper-Stimmen fuer die 10 Stil-Clips."""
import numpy as np, subprocess, os, sys
from scipy import signal

SR = 44100
BPM = 132
BEAT = 60 / BPM
BAR = BEAT * 4
DUR = BAR * 4
N = int(round(DUR * SR))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'build/clips/audio')
VO = os.path.join(HERE, 'vo')
rng = np.random.default_rng(132)


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


# ---------- voice ----------
def voice(name, rate_mult=1.0, fx=''):
    src = os.path.join(VO, name + '.wav')
    af = f'asetrate={int(16000 * rate_mult)},aresample={SR}'
    if fx:
        af += ',' + fx
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-af', af, '-ac', '1', '-f', 'f32le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).astype(float)
    return x / (np.abs(x).max() + 1e-9) * 0.9


def place_voice(mus, vox, v, t, g=1.0, duck=0.45):
    at(vox, v, t, g)
    i0, i1 = int(t * SR), int((t + len(v) / SR) * SR)
    e = np.ones(len(mus))
    e[i0:i1] = duck
    e = np.convolve(e, np.ones(2000) / 2000, mode='same')
    mus *= e


def finish(name, mus, vox, mgain=0.8):
    mix = mus[:N] * mgain + vox[:N]
    # Tail wrap so loop is seamless
    tail = (mus[N:N + SR] * mgain + vox[N:N + SR])
    mix[:len(tail)] += tail * np.linspace(1, 0, len(tail))
    mix = np.tanh(mix * 1.1)
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.95
    fn = os.path.join(OUT, name + '.mp3')
    p = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-b:a', '128k', fn],
                       input=mix.astype(np.float32).tobytes())
    print(name, 'ok', p.returncode)


ROOTS = [33, 33, 36, 31]  # A A C G (MIDI, tief)


def s01():  # Mino-Schau: News-Jingle -> Garage-Drop
    m, v = buf(), buf()
    for i, mm in enumerate([81, 76, 79, 84]):
        at(m, bell(mm, 0.6), i * BEAT * 0.5, 0.8)
    pad(m, [[57, 61, 64], [57, 61, 64]], g=0.12)
    at(m, noise_riser(int(BAR * SR)), BAR, 0.9)
    at(m, impact(), 2 * BAR, 0.9)
    garage_drums(m, bars=[2, 3])
    garage_bass(m, [0, 0, 33, 31], g=0.55)
    m[:int(2 * BAR * SR)] *= 0.9
    for t in np.arange(0, 2 * BAR, BEAT):
        at(m, click() * 0.3, t)
    place_voice(m, v, voice('01a', 0.97, 'highpass=f=120,lowpass=f=7000'), 0.15)
    place_voice(m, v, voice('01b', 0.97, 'highpass=f=120,lowpass=f=7000'), 1.45)
    place_voice(m, v, voice('01c', 0.9, 'highpass=f=120,lowpass=f=7000,aecho=0.8:0.7:120:0.35'), 5.3)
    finish('01', m, v)


def s02():  # Museum: Cembalo-Arp + Chor -> Garage
    m, v = buf(), buf()
    seq = [69, 72, 76, 81, 76, 72] * 8
    for i, mm in enumerate(seq[:32]):
        at(m, pluck(mm, 0.12, 5000), i * BEAT / 2, 0.5)
    n = int(BAR * 2 * SR)
    at(m, choir([57, 60, 64], n), 0, 0.5)
    at(m, choir([55, 59, 62, 67], n), 2 * BAR, 0.7)
    at(m, impact(), 2 * BAR, 0.7)
    garage_drums(m, bars=[2, 3], kick_g=0.9)
    garage_bass(m, [0, 0, 36, 31], g=0.45, cutoff=700)
    place_voice(m, v, voice('02a', 1.0, 'highpass=f=150,aecho=0.7:0.6:60|140:0.3|0.2'), 0.2, duck=0.55)
    finish('02', m, v)


def s03():  # Fraktal-Kosmos: Trance-Arp, Supersaw
    m, v = buf(), buf()
    arp = [69, 72, 76, 79, 81, 79, 76, 72]
    for i in range(64):
        mm = arp[i % 8] + (0 if i < 32 else 5 if i < 48 else 3)
        at(m, pluck(mm, 0.09, 2000 + 60 * i), i * BEAT / 4, 0.35)
    pad(m, [[57, 60, 64, 69], [57, 60, 64, 69], [62, 65, 69, 74], [55, 59, 62, 67]], g=0.2, cutoff=3500)
    garage_drums(m, bars=[1, 2, 3], hat_g=0.8)
    garage_bass(m, [0, 33, 38, 31], g=0.45, cutoff=1100)
    at(m, noise_riser(int(BAR * SR)), BAR, 0.6)
    at(m, impact(), 2 * BAR, 0.6)
    vv = voice('03a', 0.72, 'aecho=0.8:0.8:300|600:0.5|0.3,highpass=f=80')
    place_voice(m, v, vv, 0.3, 1.0, 0.6)
    place_voice(m, v, vv * 0.6, 4.0, 1.0, 0.7)
    finish('03', m, v)


def s04():  # Amtsdeutsch: Schreibmaschine + Stempel als Percussion
    m, v = buf(), buf()
    r = np.random.default_rng(4)
    for t in np.arange(0, 2 * BAR, BEAT / 4):
        if r.random() < 0.8:
            at(m, click(), t + r.random() * 0.02, 0.9)
    at(m, ding(), 2 * BAR - 0.25, 1)
    for i, t in enumerate(np.arange(2 * BAR, DUR, BEAT)):
        at(m, stamp(), t, 0.9)
    garage_drums(m, bars=[2, 3], kick_g=0.6, clap_g=0.7)
    garage_bass(m, [0, 0, 33, 33], g=0.5, cutoff=600, wob=False)
    pad(m, [[45, 48, 52]] * 4, g=0.08, cutoff=900)
    place_voice(m, v, voice('04a', 0.9, 'highpass=f=200,lowpass=f=4000'), 0.3, duck=0.6)
    place_voice(m, v, voice('04b', 0.85, 'highpass=f=200,lowpass=f=4000'), 6.0, duck=0.6)
    finish('04', m, v)


def s05():  # Nachtsicht: Drone, Herzschlag, dunkler Garage
    m, v = buf(), buf()
    n = int(DUR * SR) + SR
    t = np.arange(n) / SR
    drone = lp(saw(55, n) + saw(55.4, n), 300) * 0.25 + hp(rng.standard_normal(n), 6000) * 0.02
    at(m, drone, 0, 1)
    for tt in np.arange(0, 2 * BAR, BEAT * 2):
        at(m, heartbeat(), tt, 0.8)
    garage_drums(m, bars=[2, 3], kick_g=1.0, dist=2.5, hat_g=0.6)
    garage_bass(m, [0, 0, 33, 32], g=0.5, cutoff=500)
    at(m, impact(), 2 * BAR, 0.8)
    vv = voice('05a', 0.8, 'lowpass=f=3000,aecho=0.6:0.5:40:0.4')
    place_voice(m, v, vv, 1.0, 0.9, 0.7)
    place_voice(m, v, vv[::-1] * 0.5, 5.6, 0.8, 0.8)  # rueckwaerts
    finish('05', m, v)


def s06():  # Bastelstunde: Glockenspiel, Kinder-TV, dann Garage
    m, v = buf(), buf()
    mel = [72, 76, 79, 76, 77, 74, 71, 74, 72, 76, 79, 84, 83, 79, 76, 72]
    for i, mm in enumerate(mel * 2):
        at(m, bell(mm + 12, 0.35), i * BEAT / 2, 0.55)
    garage_drums(m, bars=[1, 2, 3], kick_g=0.8, hat_g=0.8)
    garage_bass(m, [0, 36, 41, 43], g=0.4, cutoff=1200)
    place_voice(m, v, voice('06a', 1.08, 'highpass=f=150'), 0.2, duck=0.6)
    place_voice(m, v, voice('06a', 1.35, 'highpass=f=150') * 0.7, 4.6, duck=0.7)
    finish('06', m, v)


def s07():  # Grosswetterlage: Regen, Donner, Pads
    m, v = buf(), buf()
    n = int(DUR * SR) + SR
    rain = hp(rng.standard_normal(n), 2500) * 0.06 + lp(rng.standard_normal(n), 800) * 0.04
    at(m, rain, 0)
    pad(m, [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]], g=0.18, cutoff=1800)
    at(m, thunder(), 2 * BAR - 0.2, 0.9)
    garage_drums(m, bars=[2, 3])
    garage_bass(m, [0, 0, 29, 31], g=0.5)
    place_voice(m, v, voice('07a', 1.0, 'highpass=f=120,lowpass=f=6500'), 0.3, duck=0.5)
    finish('07', m, v)


def s08():  # Frittiert: verzerrter Bass, Brutzeln, Bass-Boost
    m, v = buf(), buf()
    n = int(DUR * SR) + SR
    at(m, sizzle(n), 0, 1.0)
    garage_drums(m, kick_g=1.3, dist=6, hat_g=0.9)
    garage_bass(m, [33, 33, 36, 31], g=0.8, cutoff=1500)
    for k in range(4):
        at(m, impact(), k * BAR, 0.6)
    vv = voice('08a', 0.78, 'volume=4,alimiter=limit=0.6,highpass=f=60')
    vv = np.tanh(vv * 4)
    place_voice(m, v, vv, 0.25, 0.9, 0.6)
    place_voice(m, v, vv[:int(0.5 * SR)], 4.6, 0.9, 0.6)
    place_voice(m, v, vv[:int(0.5 * SR)], 5.5, 0.9, 0.6)
    m = np.tanh(m * 2.2) * 0.8
    finish('08', m, v, mgain=0.9)


def s09():  # Endlos-Schleife: Shepard-Ton + Garage
    m, v = buf(), buf()
    n = int(DUR * SR) + SR
    at(m, shepard(n), 0, 1.0)
    garage_drums(m, kick_g=0.9, hat_g=0.9)
    garage_bass(m, [33, 33, 33, 33], g=0.45, cutoff=800)
    for i in range(16):
        at(m, bell(81 + (i % 4) * 2, 0.3) * 0.5, i * BEAT)
    vv = voice('09a', 0.95, 'highpass=f=120')
    place_voice(m, v, vv, 0.4, 1.0, 0.55)
    place_voice(m, v, voice('09a', 1.25, 'highpass=f=200') * 0.45, 3.9, 1.0, 0.7)
    finish('09', m, v)


def s10():  # Teleshopping: kitschiger Jingle, Kasse
    m, v = buf(), buf()
    pad(m, [[60, 64, 67, 71], [65, 69, 72, 76], [62, 65, 69, 72], [67, 71, 74, 77]], g=0.16, cutoff=3000)
    mel = [84, 83, 81, 79, 77, 79, 81, 84]
    for i, mm in enumerate(mel):
        at(m, pluck(mm, 0.3, 6000), i * BEAT, 0.5)
    garage_drums(m, bars=[1, 2, 3], kick_g=0.85)
    garage_bass(m, [36, 41, 38, 43], g=0.45, cutoff=1300)
    for t in (2 * BAR, 3 * BAR, 3 * BAR + 2 * BEAT):
        at(m, kaching(), t, 0.8)
    place_voice(m, v, voice('10a', 1.05, 'highpass=f=150'), 0.2, duck=0.5)
    place_voice(m, v, voice('10b', 0.92, 'highpass=f=150,aecho=0.6:0.5:50:0.3'), 4.7, duck=0.5)
    finish('10', m, v)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or [f'{i:02d}' for i in range(1, 11)]
    for w in which:
        globals()['s' + w]()

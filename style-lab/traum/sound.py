"""Traum-Klangteppich: schwebende, leicht verstimmte Akkorde, langsames Atmen, Hall; Aufzug-Gong und Brummen."""
import numpy as np, wave, sys
SR = 44100
segs = [8.0, 7.0, 6.5, 5.0, 5.5, 11.0, 11.5, 6.5, 6.0]; XF = 0.75
T = sum(segs) - XF * 0  # Gesamtlänge nach Überblendung = Summe der Segmentdauern
n = int(SR * T); t = np.arange(n) / SR
starts = np.cumsum([0] + segs[:-1])
def note(m): return 440 * 2 ** ((m - 69) / 12)
chords = [[50, 57, 62, 65, 69], [48, 55, 60, 64, 71], [46, 53, 58, 62, 69], [45, 52, 57, 60, 64],
          [43, 50, 55, 59, 62], [41, 48, 53, 57, 64], [44, 51, 56, 60, 63], [48, 55, 59, 64, 67], [50, 57, 62, 66, 69]]
out = np.zeros(n)
rng = np.random.default_rng(3)
for i, ch in enumerate(chords):
    a = starts[i] - 1.0; b = starts[i] + segs[i] + 1.5
    env = np.clip((t - a) / 2.0, 0, 1) * np.clip((b - t) / 2.0, 0, 1)
    env = env * env * (3 - 2 * env)
    for m in ch:
        for det in (-0.12, 0.0, 0.11):
            f = note(m) * 2 ** (det / 12)
            ph = rng.uniform(0, 6.28)
            out += env * 0.03 * np.sin(2 * np.pi * f * t + ph + 0.4 * np.sin(2 * np.pi * 0.13 * t))
# Grundton-Brummen + Atmen
out *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
out += 0.05 * np.sin(2 * np.pi * 36.7 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t))
# Rauschen (Wind) gefiltert
noise = rng.normal(0, 1, n); k = 400; noise = np.convolve(noise, np.ones(k) / k, mode="same")
out += 0.6 * noise
# Aufzug: Gong bei Halt (Segment 6, t≈4.3 s) und Ankunft (≈ 10.6 s), Druckbrummen beim Zusammenziehen
s6 = starts[5]
for tg in (s6 + 4.3, s6 + 10.6):
    for f, d in ((880, 1.0), (698.5, 1.0)):
        tt = t - tg - (0 if f == 880 else 0.45)
        out += 0.12 * np.where(tt > 0, np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.2), 0)
for a, b in ((s6 + 1.0, s6 + 4.0), (s6 + 7.8, s6 + 10.2)):
    e = np.clip((t - a) / (b - a), 0, 1) * (t < b + 0.3)
    out += 0.1 * e * np.sin(2 * np.pi * (55 + 40 * e) * t)
# einfacher Hall: mehrere verzögerte Kopien
rev = out.copy()
for d, g in ((0.031, 0.5), (0.047, 0.45), (0.071, 0.4), (0.113, 0.35), (0.173, 0.3), (0.29, 0.25), (0.43, 0.2)):
    k = int(d * SR); rev[k:] += g * out[:-k]
out = rev
# Ende ausblenden
out *= np.clip((T - t) / 3.0, 0, 1) * np.clip(t / 1.5, 0, 1)
out = out / np.max(np.abs(out)) * 0.8
st = np.stack([out, np.roll(out, int(0.012 * SR))], 1)
w = wave.open(sys.argv[1], "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()
print("dauer", T)

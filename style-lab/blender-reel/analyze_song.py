#!/usr/bin/env python3
"""Findet Tempo, Beat-Raster und den Drop eines Songs und schreibt params.json für das Reel.

  python analyze_song.py song.wav [--bpm 140] [--drop-beat 16] [--beats 48] [-o params.json]

Nur numpy + wave (PCM 16/24/32 Bit oder 32-Bit-Float). Der Drop ist der Takt, an dem die Energie
im Bassbereich am stärksten springt (nach mindestens 16 Sekunden). Das Reel-Fenster wird so gelegt,
dass dieser Drop auf Schlag --drop-beat des Reels fällt.
"""
import argparse
import json
import struct
import wave

import numpy as np


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        x = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        x = np.where(x & 0x800000, x - 0x1000000, x).astype(np.float32) / 8388608
    elif sw == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
    else:
        raise SystemExit("unbekannte Sample-Breite %d" % sw)
    return x.reshape(-1, ch).mean(axis=1), sr


def read_any(path):
    try:
        return read_wav(path)
    except wave.Error:
        # WAVE_FORMAT_IEEE_FLOAT: wave kann das nicht, also den data-Chunk selbst suchen
        data = open(path, "rb").read()
        fmt = data.find(b"fmt ")
        _, ch, sr = struct.unpack("<HHI", data[fmt + 8:fmt + 16])
        bits = struct.unpack("<H", data[fmt + 22:fmt + 24])[0]
        d = data.find(b"data")
        size = struct.unpack("<I", data[d + 4:d + 8])[0]
        x = np.frombuffer(data[d + 8:d + 8 + size], "<f4" if bits == 32 else "<f8").astype(np.float32)
        return x.reshape(-1, ch).mean(axis=1), sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, default=0, help="bekanntes Tempo (sonst geschätzt 120-150)")
    ap.add_argument("--drop-beat", type=int, default=16)
    ap.add_argument("--beats", type=int, default=48)
    ap.add_argument("-o", default="params.json")
    a = ap.parse_args()

    x, sr = read_any(a.wav)
    hop = 512
    # Bassband (grob unter ~150 Hz) per gleitendem Mittel, plus Breitband-Onsets
    k = max(1, int(sr / 150))
    bass = np.convolve(x, np.ones(k) / k, mode="same")
    nfr = len(x) // hop
    e_all = np.sqrt(np.mean(x[: nfr * hop].reshape(nfr, hop) ** 2, axis=1))
    e_bass = np.sqrt(np.mean(bass[: nfr * hop].reshape(nfr, hop) ** 2, axis=1))
    fps = sr / hop
    onset = np.maximum(0, np.diff(e_all, prepend=e_all[0]))

    if a.bpm:
        bpm = a.bpm
    else:
        best, bpm = -1, 140.0
        for cand in np.arange(118, 152, 0.25):
            lag = fps * 60 / cand
            i = np.arange(len(onset) - int(lag * 8))
            s = sum(np.dot(onset[i], onset[(i + lag * m).astype(int)]) for m in (1, 2, 4))
            if s > best:
                best, bpm = s, cand
    beat = 60 / bpm
    # Phase: Verschiebung, bei der die Onsets am besten auf dem Raster liegen
    t = np.arange(len(onset)) / fps
    phases = np.linspace(0, beat, 64, endpoint=False)
    score = [onset[np.clip(((np.arange(int(t[-1] / beat)) * beat + p) * fps).astype(int), 0, len(onset) - 1)].sum() for p in phases]
    phase = float(phases[int(np.argmax(score))])

    # Energie pro Takt (4 Schläge) im Bass, größter Sprung = Drop
    bar = 4 * beat
    nb = int((t[-1] - phase) / bar)
    bars = np.array([e_bass[int((phase + i * bar) * fps): int((phase + (i + 1) * bar) * fps)].mean() for i in range(nb)])
    jump = np.zeros(nb)
    jump[1:] = bars[1:] / (bars[:-1] + 1e-6)
    first = int(16 / bar)
    di = first + int(np.argmax(jump[first:]))
    drop_t = phase + di * bar
    offset = drop_t - a.drop_beat * beat
    while offset < 0:
        offset += bar
    p = {
        "bpm": round(bpm, 3), "beat_phase_s": round(phase, 4), "drop_s": round(drop_t, 3),
        "song_offset_s": round(offset, 4), "drop_beat": a.drop_beat, "beats": a.beats,
        "song_length_s": round(len(x) / sr, 2), "bar_energy_jump": round(float(jump[di]), 2),
    }
    json.dump(p, open(a.o, "w"), indent=1)
    print(json.dumps(p, indent=1))
    print("weitere Drop-Kandidaten (s):", [round(phase + i * bar, 1) for i in np.argsort(-jump)[:5]])


if __name__ == "__main__":
    main()

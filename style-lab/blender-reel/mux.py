#!/usr/bin/env python3
"""Setzt die PNG-Frames und den Song zu einem MP4 zusammen (wie bei den Dat-Swag-Reels).

  python mux.py --frames out/frames --song song.wav --params params.json --out out/reel.mp4 [--ffmpeg ffmpeg] [--fps 30]

Der Song wird ab song_offset_s geschnitten, Länge = Anzahl Frames / fps, mit kurzem Ein- und Ausblenden.
"""
import argparse
import glob
import json
import os
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--frames", required=True)
ap.add_argument("--song", required=True)
ap.add_argument("--params", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--ffmpeg", default="ffmpeg")
ap.add_argument("--fps", type=int, default=30)
a = ap.parse_args()

P = json.load(open(a.params))
files = sorted(glob.glob(os.path.join(a.frames, "f_*.png")))
if not files:
    raise SystemExit("keine Frames in " + a.frames)
first = int(os.path.basename(files[0])[2:-4])
dur = len(files) / a.fps
off = float(P.get("song_offset_s", 0)) + (first - 1) / a.fps
fade_out = max(0.0, dur - 0.6)
digits = len(os.path.basename(files[0])) - 6
cmd = [
    a.ffmpeg, "-y",
    "-framerate", str(a.fps), "-start_number", str(first), "-i", os.path.join(a.frames, "f_%0" + str(digits) + "d.png"),
    "-ss", "%.4f" % off, "-t", "%.4f" % dur, "-i", a.song,
    "-map", "0:v", "-map", "1:a",
    "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
    "-vf", "fade=t=in:st=0:d=0.15,fade=t=out:st=%.3f:d=0.6" % fade_out,
    "-c:a", "aac", "-b:a", "320k",
    "-af", "afade=t=in:st=0:d=0.05,afade=t=out:st=%.3f:d=0.6" % fade_out,
    "-shortest", a.out,
]
print(" ".join(cmd))
subprocess.run(cmd, check=True)
print("fertig:", a.out, "%.2f s" % dur)

import subprocess, sys
segs = [8.0, 7.0, 6.5, 5.0, 5.5, 11.0, 11.5, 6.5, 6.0]; XF = 0.75
args = ["ffmpeg", "-loglevel", "error", "-y"]
for i in range(9): args += ["-framerate", "12", "-i", f"frames/s{i+1}/f%04d.png"]
args += ["-i", "dream.wav"]
fc = []
for i in range(9): fc.append(f"[{i}:v]framerate=fps=24:interp_start=0:interp_end=255:scene=100,format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
prev = "v0"; off = 0.0
for i in range(1, 9):
    off += segs[i - 1]
    fc.append(f"[{prev}][v{i}]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]"); prev = f"x{i}"
T = sum(segs)
fc.append(f"[{prev}]fade=t=out:st={T-2.2:.2f}:d=2.2:color=0xfff4e0,fade=t=in:st=0:d=1.0[vout]")
args += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "9:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sys.argv[1]]
subprocess.run(args, check=True)

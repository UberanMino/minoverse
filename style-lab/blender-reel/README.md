# Mino Kabel – Blender-Test-Reel

Prozedurale Blender-Szene (kein Fremdmodell, keine Medien im Repo): eine Welt aus Röhrenfernsehern,
Kabelsalat und herumliegenden Akten. Aufbau wie bei den Dat-Swag-Blender-Reels: alles aus Code,
EEVEE, Standard-View-Transform, Bloom, 1080x1920 bei 50 % (540x960), 30 fps, PNG-Frames, danach ffmpeg.

Der Song wird nicht mitgeliefert (lokal ablegen).

```
# 1) Tempo und Drop bestimmen (BPM am besten vorgeben)
python analyze_song.py song/my_mind.wav --bpm <BPM> -o params.json

# 2) Test-Standbilder (Sekunden)
blender -b --factory-startup --python mino_kabel_reel.py -- --params params.json --still 2,7.5,12,19 --out out/test.mp4

# 3) Frames rendern (abbrechbar, setzt fort) und mit Song zusammensetzen
blender -b --factory-startup --python mino_kabel_reel.py -- --params params.json --pngdir out/frames
python mux.py --frames out/frames --song song/my_mind.wav --params params.json --out out/mino_kabel_reel.mp4 --ffmpeg ffmpeg
```

Weitere Optionen: `--engine CYCLES` (GPU wird automatisch gesucht), `--samples`, `--res 540x960`,
`--exposure 0.0`, `--view Standard`, `--frames a-b`, `--portrait cg:schrei,cg:ekstase,cgk:grimasse,mm,mu,gm`
(Figurenbögen), `--save szene.blend`.

Schriften: `fonts/` ist per .gitignore ausgeschlossen. Dort als TTF ablegen (alle SIL Open Font License):
anton-latin-400-normal.ttf, vt323-latin-400-normal.ttf, courier-prime-latin-700-normal.ttf,
special-elite-latin-400-normal.ttf, barlow-condensed-latin-800-normal.ttf (z. B. aus dem google/fonts-Repo).

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

## Mino Büro (Rahmen: das endlose Büro unter freiem Himmel)

`mino_buero_reel.py` baut Großraumbüro-Kabinen bis zum Horizont unter Sonne und blauem Himmel, Röhren-PCs mit wilden
Programmen, Akten, die wie Fehlerdialoge aufploppen (mit kleinen Pop-up-Welten darin), einen AKTE.EXE-Dialog mit Mauszeiger
und Sprünge durch Bildschirme und Akten in drei Welten (Hot-Dog-Himmel, Akten-Kosmos, Pepsi-Ozean). Drei Abläufe:

| Variante | Ablauf | Song-Ausschnitt |
|---|---|---|
| 1 Großraum | Luftbild, Mino Man tippt, Akten-Kaskade, in seinen Bildschirm, Hot-Dog-Himmel, Büro-Party | `params_buero_v1.json` (Drop 89,8 s) |
| 2 Aktenflut | Wir sitzen am PC, Doppelklick, zehn Akten, in die letzte hinein, Akten-Kosmos, Officer Munch | `params_buero_v2.json` (Drop 141,0 s) |
| 3 Wandertag | Chicken Guy tanzt durch die Gänge, Akten über den Kabinen, Sprung in einen Riesen-PC, Pepsi-Ozean | `params_buero_v3.json` (Drop 51,4 s) |

    blender -b --factory-startup --python mino_buero_reel.py -- --params params_buero_v1.json --fast --pngdir out/v1
    python mux.py --frames out/v1 --song song/my_mind.wav --params params_buero_v1.json --out out/mino_buero_v1.mp4 --ffmpeg ffmpeg

## Mino Office (Runde 5)

`mino_office_reel.py` setzt Raphaels Feedback zu Runde 4 um: alles Sichtbare auf Englisch, Akten nur noch organisch
(eine liegt auf Mino Mans Tisch, die Kamera fährt hin), riesige Hochformat-Bildschirme hängen vom Himmel oder fallen herab
und spielen echte Clips (`--clips <ordner>` mit `tex_<key>.mp4`, 360x640; die Clips liegen nur lokal, nie im Repo).
Kamera federt nach dem Drop auf jeden Schlag (Zoom-Stoß, Ruck, Kippen), taucht in Stufen im Takt durch Bildschirme.
Mehr Leben im Büro: Kuh, Pinguin, Tauben, Pepsi Grandma am Wasserspender, Gemüse-Band, Riesen-Sneaker am Himmel.

| Variante | Ablauf | Song-Ausschnitt |
|---|---|---|
| 1 Case 001 | Mino Man tippt, Akte auf dem Tisch, Stotter-Zoom ins Foto, Hot-Dog-Fabrik (Chicken Guy auf dem Fließband), raus aus einem Riesenschirm, Party, Officer Munch isst die Akte | `params_office_v1.json` |
| 2 Orbit | Riesenschirm fällt in den Gang, Kamera schießt im Takt ins All, Großraumbüro im Weltall, Sturz zurück, Party | `params_office_v2.json` |
| 3 Surf | Chicken Guy und Mino Man tanzen durch die Gänge, Sprung in einen Riesen-PC, Pepsi-Ozean mit Surf-Tricks, Party, Luftbild | `params_office_v3.json` |

Chicken Guy hat jetzt einen realistischen Kopf aus dem MakeHuman-Basismesh (hm08, CC0) mit den afrikanischen
Ausdrucks-Targets als Shape Keys, angepassten Augen, Zähnen (mit Lücken), Zunge, Brauen, Wimpern und Hauttextur.
`build_cg_head.py` erzeugt daraus `cg_head.npz` + Texturen (Eingabe: entpackte MPFB-Erweiterung `ext/` und
MakeHuman-System-Assets `assets/`); das Reel liest den Ordner über `--cghead`. Ohne Daten fällt es auf den alten Kopf zurück.

    python build_cg_head.py --mh <mpfb-ordner> --out cghead
    blender -b --factory-startup --python mino_office_reel.py -- --params params_office_v1.json --clips clips --cghead cghead --fast --pngdir out/o1
    python mux.py --frames out/o1 --song song/my_mind.wav --params params_office_v1.json --out out/mino_office_v1.mp4 --ffmpeg ffmpeg

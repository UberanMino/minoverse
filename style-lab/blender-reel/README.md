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

## Mino Screens (Runde 6)

`mino_screens_reel.py` baut auf `mino_office_reel.py` auf (Welt, Figuren, Chicken-Guy-Kopf, Clips) und setzt das Feedback zu
Runde 5 um: Kamera wieder wie bei Dat Swag (feste Einstellung etwa alle 4 Schläge, weicher Übergang, leichtes Driften,
Zoom-Stoß auf jedem Schlag und kleiner Ruck auf jeder Takt-Eins, kein Kippen), Tanz im Dat-Swag-Muster (Wiegen, Hüpfen,
Armmuster wechselt pro Takt), Erzählung als Cold Open → Aufbau → Drop → Steigerung → Payoff. Die vom Himmel hängenden
Screens stehen im Mittelpunkt und setzen sich zu etwas zusammen, das angebetet wird. Das Büro ist nur noch Horizont und
ein Side-Screen („OFFICE CAM LIVE“, Clip `tex_office.mp4`).

Der Drop liegt jetzt exakt auf Schlag 16: Das Beat-Raster des Songs beginnt bei 0,0062 s (150 BPM), die Offsets sind
deshalb k · 0,4 s + 0,0062 s. In den Runden 4 und 5 lag der Drop einen halben Schlag zu spät.

| Variante | Ablauf | Song-Ausschnitt |
|---|---|---|
| 1 Idol | Zehn Screens bauen auf dem Platz eine Statue, Chicken Guy fällt auf den Altar aus Monitoren, die Menge bildet einen Ring, verbeugt sich, feiert | `params_screens_v1.json` |
| 2 Orbit-Idol | Im Weltall-Büro treiben Screens im Orbit, rasten zur Statue ein, Chicken Guy tanzt auf einem schwebenden Schreibtisch | `params_screens_v2.json` |
| 3 Totem | Ein Turm aus Screens wächst, die Etagen drehen sich wie Walzen eines Spielautomaten, die Polonaise zieht drumherum | `params_screens_v3.json` |
| 4 Wand | Zwölf Screens landen als Wand und ergeben zusammen ein Riesenbild von Chicken Guy, Schiebepuzzle, die Wand platzt | `params_screens_v4.json` |
| 5 Karussell | Ein Ring aus Screens kreist um das Weltall-Büro, alle schalten auf denselben Kanal, der Ring wird Mino Mans Heiligenschein | `params_screens_v5.json` |

    blender -b --factory-startup --python mino_screens_reel.py -- --params params_screens_v1.json --clips <abs>/clips --cghead <abs>/cghead --fast --pngdir out/screens_v1
    python mux.py --frames out/screens_v1 --song song/my_mind.wav --params params_screens_v1.json --out out/mino_screens_v1.mp4 --ffmpeg ffmpeg

## Mino Heaven (Runde 7)

`mino_heaven_reel.py` übernimmt aus `mino_screens_reel.py` Figuren, Dat-Swag-Kamera, Tanz und Clip-Texturen und setzt das
Feedback zu Runde 6 um: Statt einzelner Screens hängen Blöcke vom Himmel. Ein Block besteht aus sechs Screens im Sechseck,
die alle denselben Clip synchron zeigen. Die Blöcke drehen sich um die Hochachse (vor dem Drop langsam, danach rasten sie
auf jedem Schlag um 60° weiter, in Schlag 32–40 auf jedem halben) und ordnen sich auf dem Beat zu Formationen (Reihe, Bogen,
Kreuz, Ring, Pyramide, Turm, Helix, Figur …). In der Mosaik-Formation schalten alle Blöcke auf einen Kanal und setzen ein
Riesenbild von Chicken Guy zusammen. Mino Man legt an einem Marmor-Altar mit zwei Plattenspielern auf (Kopfhörer, Cue-Griff,
Faust auf der Takt-Eins), die Gemeinde in weißen Gewändern mit Goldstola betet an, hüpft, verbeugt sich. Das Büro ist
verschwunden: Wolkenboden, Säulen, Orgelpfeifen, Rosenfenster, Himmelstreppe, Kerzen, Tauben.

Clips: `tex_cg2.mp4` und `tex_gm2.mp4` (neue Chicken-Guy- und Pepsi-Grandma-Clips, 360x640, 30 fps) liegen wie alle Medien
nur lokal im `clips`-Ordner.

| Variante | Ablauf | Song-Ausschnitt |
|---|---|---|
| 1 Kathedrale | Säulenhalle auf Wolken, Orgel, Altar; Blöcke bilden Kreuz, Ring, Pyramide, Turm, am Ende das Mosaik | `params_heaven_v1.json` |
| 2 Spiegelhimmel | Goldener Himmel über einem Spiegelboden, schwebendes DJ-Pult, Ringe aus Blöcken, Helix, Mosaik, Heiligenschein | `params_heaven_v2.json` |
| 3 Rosenfenster | Die Blöcke sind die Blütenblätter eines leuchtenden Rosenfensters, lösen sich auf dem Drop und kehren zurück | `params_heaven_v3.json` |
| 4 Himmelstreppe | Chicken Guy steigt die Treppe zum goldenen Tor hoch, oben legt Mino Man auf, Blöcke als Kreuz, Treppe, Mosaik | `params_heaven_v4.json` |
| 5 Lichtmesse | Nacht, hunderte Kerzen; die Blöcke werden zu einem Block-Götzen, der am Ende die Arme hebt | `params_heaven_v5.json` |

    blender -b --factory-startup --python mino_heaven_reel.py -- --params params_heaven_v1.json --clips <abs>/clips --cghead <abs>/cghead --fast --pngdir out/heaven_v1
    python mux.py --frames out/heaven_v1 --song song/my_mind.wav --params params_heaven_v1.json --out out/mino_heaven_v1.mp4 --ffmpeg ffmpeg

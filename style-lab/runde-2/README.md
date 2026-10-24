# Stilrunde 2: fünf Welt-Rahmen

Lehre aus Runde 1: Figuren werden nach den Bildern **neu gebaut und animiert** (3D aus Code, wie der Dat-Swag-Cast),
und jeder Stil ist ein **Rahmen für eine ganze Welt** (wie SWAG OS), kein einzelner Shot.

| Nr | Welt | Rahmen |
|----|------|--------|
| 01 | Mino Kabel | Kabelfernsehen: CRT, OSD, Zappen auf den Beat, jeder Sender ein Format |
| 02 | Sim Mino | Gottspiel: isometrische Insel, Katastrophen-Menü, „GOTT: ABWESEND“, Berater Mino Man |
| 03 | Akte Mino | Behörden-Schreibtisch: Akten, Stempel auf den Beat, Fax, Rohrpost, Munch isst Beweise |
| 04 | Mino Quest | Point-and-Click-Adventure: Verben (inkl. ISS), Inventar, Satzzeile |
| 05 | Minoverse Hauptbahnhof | Bahnhof: Fallblatt-Anzeiger, Gleis 3, jedes Zugfenster eine Szene |

- `clips/lib/cast.js`: Mino-Cast in three.js (Humanoid-Rig, Gesichts-Rig mit Lippensync, Moves, Bühne mit Pixel-Upscaling)
- `clips/lib/mv.js`: Zeitachse (150 BPM, 32 Schläge = 12,8 s), deterministisches Seeking für HyperFrames
- `clips/lib/props.js`: Requisiten (Pult, Schreibtisch, Textur-Text, Schaum, Bildschnee)
- `tools/`: Musik/Stimmen (`synth2.py`), Render (`render2.sh`), Kontaktbögen (`shot2.js`, `sheet.js`)
- `bewertung/index.html`: Bewertungsseite

Nicht im Repo (öffentlich): Audio, Stimmen, Schriften, three.js/GSAP, Renders. Die liegen in den Projektdateien unter `stilrunde-2/`.
Zum Rendern `three.min.js` (r158) und `gsap.min.js` nach `clips/lib/` legen, Schriften nach `clips/fonts/`.

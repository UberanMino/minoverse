# Traum (Blender)

Raphaels Traum als surreales Video: 1. Stock (Rezeption, Fleischbuffet), Aufzug ohne Knöpfe, zu steile Treppe,
Tablett mit zwei kleinen Pommes, Aufzug außer Betrieb, sich zusammenziehender Aufzug mit Familie,
fraktale Rolltreppen im 6. Stock mit Mitarbeiter, beiges Restaurant im 5. Stock, Weg in den 3. Stock.

- `dream.py <segment 1..9> [test <frames>]` – baut die Szene prozedural, rendert ein Segment (Cycles CPU).
  Umgebung: `DREAM_W/H` (540x960), `DREAM_SAMPLES` (6), `DREAM_FPS` (12), `DREAM_OUT`, `DREAM_NOCOMP`.
- `sound.py out.wav` – erzeugt den Klangteppich (numpy).
- Segmente werden danach mit ffmpeg überblendet (0,75 s) und auf 24 fps weich überblendet.

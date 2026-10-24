# Minoverse Stilrunde 1

Zehn Stilproben (je 4 Takte bei 132 BPM ≈ 7,27 s, 1080 × 1920) als HyperFrames-Kompositionen.
Bewertet werden sie in der Bewertungsseite (`bewertung.html`, veröffentlicht als Claude-Artefakt
„Minoverse Stilrunde 1“). Noten und Feedback liegen in deren Datenbank (Collection `bewertungen`).

| Nr | Stil | Signatur |
|----|------|----------|
| 01 | Mino-Schau | Nachrichtenstudio, das beim Drop schmilzt; Ticker mit Pepsi Grandma |
| 02 | Museum-Fieber | Gemälde wird lebendig, Goldrahmen, absurdes Museumsschild |
| 03 | Fraktal-Kosmos | Mandelbrot-Zoom, Kaleidoskop, goldene Glyphen |
| 04 | Amtsdeutsch | Formular, Schreibmaschine, Stempel als Percussion, Officer Munch frisst die Akte |
| 05 | Nachtsicht | Überwachungskamera 8 fps, Wärmebild beim Drop |
| 06 | Bastelstunde | Papp-Stop-Motion mit Wackelaugen |
| 07 | Großwetterlage | Musik ist Wetter: BPM-Temperaturen, Hotdog-Regen |
| 08 | Frittiert | Deep-Fried-Meme, Frittierstufe steigt pro Takt |
| 09 | Endlos-Schleife | Droste-Zoom, nahtloser Loop |
| 10 | Teleshopping | 3-Uhr-nachts-Verkaufssender, Preis fällt auf den Beat |

## Aufbau

- `clips/NN-*.html` – je eine HyperFrames-Komposition (GSAP-Timeline in `window.__timelines['main']`,
  Canvas/Sprites über das `hf-seek`-Event, alles deterministisch).
- `clips/lib/mv.js` – gemeinsame Runtime: Beat-Raster, Sprites, Plasma, Mandelbrot (WebGL), Korn.
- `tools/synth.py` – prozedurale Speed-Garage-Loops + Piper-Stimmen (deutsch, offline) → `clips/audio/NN.mp3`.
- `tools/assets.py`, `tools/cut.py` – Freisteller (rembg) und Sprite-Sheets aus den Upload-Clips.
- `tools/shot.js` – Kontaktbögen per Playwright.

Nicht im Repo (öffentlich): Freisteller, Stimmen, Audio, Fonts, gsap.min.js, Renders.
Die vollständige Fassung inkl. Medien liegt in den Projektdateien unter `stilrunde-1/`.

Rendern einer Probe: Ordner mit `lib/`, `assets/`, `audio/`, `fonts/` anlegen, Clip als `index.html`
hineinkopieren, dann `npx hyperframes render -o out.mp4`.

Platzhalter: Pepsi Grandma ist gezeichnet (`assets/pg.svg`), bis der echte Clip vorliegt.

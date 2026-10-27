# Werkzeuge

- Lippensynchron: `lipsync <bild_oder_video> <audio> <ausgabe.mp4>` (Wav2Lip, CPU, langsam ~ 0,5 Min pro 30 s bei Standbild, ~2,5 Min pro 30 s bei Video). Nur Dateiname als Ausgabe -> landet in ~/forschung/. Gewichte nur nicht-kommerziell nutzbar.
- Schaerferer Mund: `lipsync --scharf <bild_oder_video> <audio> <ausgabe.mp4>` (oder `LIPSYNC_SCHARF=1 lipsync ...`). Nach Wav2Lip wird jedes Frame mit GFPGAN v1.4 nachgeschaerft (nur Gesicht, CPU). Gemessen: 11,7 s Audio + Standbild -> normal 8 s, `--scharf` 185 s (~0,6 s pro Frame, also ca. 8 Min pro 30 s Video). Staerke: `LIPSYNC_SCHARF_WEIGHT=0.5` (Standard, 0..1; hoeher = glatter, schliesst den Mund etwas). GFPGAN: Apache-2.0, liegt in ~/tools/gfpgan.

## Blender (3D-Animationen, headless)

- Programm: Blender 5.2.3 LTS (offizielles Linux-Paket) in ~/tools/blender, Aufruf `blender` (Wrapper in ~/bin).
- Headless rendern: `blender -b -P skript.py` (`-b` = ohne Fenster). Die Szene komplett im Python-Skript (bpy) bauen, Ausgabe als MP4 über `scene.render.image_settings.file_format = "FFMPEG"` (Blender 5: vorher `media_type = "VIDEO"`), `ffmpeg.format = "MPEG4"`, `ffmpeg.codec = "H264"`. Alternativ PNG-Einzelbilder rendern und mit `ffmpeg` zusammensetzen.
- Render-Engine auf diesem Rechner (keine GPU, 8 CPU-Kerne): **Cycles auf CPU** empfohlen (`scene.render.engine = "CYCLES"`, `scene.cycles.device = "CPU"`, wenige Samples z. B. 16 + Denoising). Eevee läuft auch (Software-OpenGL), ist hier aber gut doppelt so langsam.
- Gemessen (rotierender Würfel mit Kamera und Licht, 640x360, 25 fps, 75 Frames = 3 s Video): Cycles CPU 16 Samples ca. 75 s (~1 s pro Frame), Eevee ca. 168 s (~2,2 s pro Frame). Höhere Auflösung/mehr Samples/komplexe Szenen dauern entsprechend länger.
- Beispielskript: ~/forschung/blender_test/wuerfel_test.py (Engine per `ENGINE=CYCLES` oder `ENGINE=BLENDER_EEVEE`, Ziel per `OUT=...`).
- Lange Renders: terminal mit großem `timeout` starten (z. B. 1800 s oder mehr, Standard bricht nach 180 s ab) oder im Hintergrund laufen lassen (`nohup blender -b -P skript.py > render.log 2>&1 &`) und das Log prüfen. Nicht doppelt starten.
- Börsendaten (Yahoo Finance, gratis, ohne Key): Python mit /home/hermes/tools/yfinance/venv/bin/python und `import yfinance as yf`, z. B. `yf.Ticker("AAPL").history(period="1y")`. Inoffiziell, kann bei vielen Abfragen gebremst werden – sparsam abfragen.

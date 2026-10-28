"""
Iso-Firmen-Video 🏢 — die 6 Etagen in isometrischem Stil als animiertes MP4 (9:16).

Baut Frames (jede Etage erscheint nacheinander mit Fade + Zoom), dann ffmpeg.
Kein Browser/GPU nötig — cairosvg + PIL + ffmpeg.

Ausgabe: orchestra/visualizer/iso_company.mp4
"""
import io
import sys
import time
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cairosvg
from PIL import Image

VIS_DIR = Path(__file__).resolve().parent
OUT_MP4 = VIS_DIR / "iso_company.mp4"
FRAMES_DIR = Path("/tmp/iso_company_frames")

FLOORS = ["iso_scanner", "iso_research", "iso_strategy", "iso_testing", "iso_risk", "iso_control"]
FLOOR_LABELS = ["01 SCANNER", "02 RESEARCH", "03 STRATEGY", "04 TESTING", "05 RISK", "06 CONTROL"]

# Timing: pro Etage 2.0s (Fade-in 0.5s, halten 1.2s, fade-out 0.3s), Übergang 0.4s
SEC_PER_FLOOR = 2.2
FPS = 24
WIDTH = 720
HEIGHT = 1280


def load_pngs():
    """Lädt alle Etagen-PNGs als PIL-Images."""
    imgs = {}
    for name in FLOORS:
        p = VIS_DIR / f"{name}.png"
        if p.exists():
            imgs[name] = Image.open(p).convert("RGBA")
    return imgs


def lerp(a, b, t):
    return a + (b - a) * t


def main():
    FRAMES_DIR.mkdir(exist_ok=True)
    for f in FRAMES_DIR.glob("*.png"):
        f.unlink()
    imgs = load_pngs()
    if len(imgs) != len(FLOORS):
        print(f"Nur {len(imgs)}/{len(FLOORS)} PNGs gefunden")
        return 1

    total_seconds = SEC_PER_FLOOR * len(FLOORS)
    n_frames = int(total_seconds * FPS)
    print(f"Baue Video: {n_frames} Frames @ {FPS}fps (~{total_seconds:.1f}s)")

    # Hintergrund (dunkel)
    bg = Image.new("RGB", (WIDTH, HEIGHT), (10, 15, 34))

    t0 = time.time()
    for i in range(n_frames):
        t = i / FPS
        floor_idx = min(len(FLOORS) - 1, int(t / SEC_PER_FLOOR))
        local_t = t - floor_idx * SEC_PER_FLOOR

        # Fade-Kurve: 0..0.5s einblenden, 0.5..1.7s halten, 1.7..2.2s ausblenden
        if local_t < 0.5:
            alpha = local_t / 0.5
        elif local_t < 1.7:
            alpha = 1.0
        else:
            alpha = 1.0 - (local_t - 1.7) / 0.5

        alpha = max(0.0, min(1.0, alpha))

        # Etagen-PNG auf Hintergrund blenden
        img = imgs[FLOORS[floor_idx]]
        # Skalieren auf 9:16 (Bild ist 1000x800 -> auf Breite 720, dann zentrieren)
        scale = WIDTH / img.width
        new_h = int(img.height * scale)
        resized = img.resize((WIDTH, new_h), Image.LANCZOS)
        # Vertikal zentrieren (leicht höher, Label unten sichtbar)
        y_offset = (HEIGHT - new_h) // 2 - 40

        # Alpha-Blend mit Fade
        frame = bg.copy()
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        resized_rgba = resized.copy()
        # Alpha anwenden
        resized_rgba.putalpha(int(alpha * 255))
        overlay.paste(resized_rgba, (0, y_offset), resized_rgba)
        frame = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")

        # Etagen-Label unten einblenden
        label = FLOOR_LABELS[floor_idx]
        # Wir zeichnen das Label als einfaches Banner (PIL-Font fallback)
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(frame)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        except Exception:
            font = ImageFont.load_default()
        tw = draw.textlength(label, font=font)
        bx = (WIDTH - tw) / 2 - 14
        by = HEIGHT - 110
        draw.rounded_rectangle([bx, by, bx + tw + 28, by + 50], radius=14, fill=(15, 23, 42), outline=(124, 92, 255), width=2)
        draw.text((bx + 14, by + 7), label, fill=(226, 232, 240), font=font)

        frame.save(FRAMES_DIR / f"frame_{i:03d}.png")
        if i % 30 == 0:
            print(f"  Frame {i+1}/{n_frames} ({time.time()-t0:.1f}s)")

    cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
           "-i", str(FRAMES_DIR / "frame_%03d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
           str(OUT_MP4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg Fehler:", r.stderr[-500:])
        return 1
    size_kb = OUT_MP4.stat().st_size // 1024
    print(f"MP4 geschrieben: {OUT_MP4} ({size_kb} KB, ~{total_seconds:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

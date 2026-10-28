"""
Firmen-Video-Renderer 🏢 — kombiniert Logo + 6 Etagen zu einem animierten MP4 (9:16 vertikal).

Baut Frames (aktive Etage leuchtet, wandert hoch), dann ffmpeg zu MP4.
Kein Browser/GPU nötig — cairosvg + PIL + ffmpeg.

Ausgabe: orchestra/visualizer/vibe_company.mp4
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
OUT_MP4 = VIS_DIR / "vibe_company.mp4"
FRAMES_DIR = Path("/tmp/vibe_company_frames")

N_FRAMES = 60       # ~15s bei 4 fps
FPS = 4
WIDTH = 720         # 9:16 vertikal
HEIGHT = 1280


def load_svg_parts():
    parts = {}
    for name in ["company_logo", "company_floor1_3", "company_floor4_6"]:
        p = VIS_DIR / f"{name}.svg"
        if p.exists():
            parts[name] = p.read_text()
        else:
            parts[name] = None
    return parts


def inner(svg):
    """Extrahiert den Inhalt einer SVG (ohne <svg>...</svg>-Wrapper)."""
    s = svg.strip()
    start = s.find(">") + 1
    end = s.rfind("</svg>")
    return s[start:end] if start > 0 and end > start else s


def render_frame(parts, progress):
    """
    Baut einen Frame: Logo oben + 6 Etagen vertikal.
    progress (0..1): aktive Etage = int(progress * 6), leuchtet heller.
    """
    logo = parts.get("company_logo")
    f13 = parts.get("company_floor1_3")
    f46 = parts.get("company_floor4_6")
    if not logo or not f13 or not f46:
        return None

    n_floors = 6
    active = min(n_floors - 1, int(progress * n_floors))

    body = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{HEIGHT}' viewBox='0 0 {WIDTH} {HEIGHT}'>"]
    body.append("<defs><linearGradient id='bg' x1='0' y1='0' x2='0' y2='1'>"
                "<stop offset='0' stop-color='#0b1026'/><stop offset='1' stop-color='#141a3a'/></linearGradient></defs>")
    body.append(f"<rect width='{WIDTH}' height='{HEIGHT}' fill='url(#bg)'/>")

    # Logo (oben, skaliert auf 92% Breite)
    logo_w, logo_h = 820, 200
    scale_logo = WIDTH * 0.95 / logo_w
    body.append(f"<g transform='translate({(WIDTH - logo_w*scale_logo)/2:.0f},20) scale({scale_logo:.3f})'>{inner(logo)}</g>")

    # Die 6 Etagen: Floor1-3 (oben) und Floor4-6 (unten), gestapelt
    # floor1_3 SVG ist 900x560 (3 Etagen), floor4_6 ebenso
    margin_top = 200
    gap = 12
    avail_h = HEIGHT - margin_top - 30
    # Beide Etagen-SVGs haben 3 Floors à ~175px in 560px Höhe
    scale_f = min(WIDTH * 0.95 / 900, avail_h / (2 * 560 + gap) * 1.0)
    f_w = 900 * scale_f
    f_h = 560 * scale_f

    y1 = margin_top
    y2 = y1 + f_h + gap

    # Floor1-3 (oben): aktive Etage 0,1,2 -> im oberen SVG
    opacity13 = 1.0 if active < 3 else 0.35
    body.append(f"<g transform='translate({(WIDTH - f_w)/2:.0f},{y1:.0f}) scale({scale_f:.3f})' opacity='{opacity13}'>{inner(f13)}</g>")

    # Floor4-6 (unten): aktive Etage 3,4,5 -> im unteren SVG
    opacity46 = 1.0 if active >= 3 else 0.35
    body.append(f"<g transform='translate({(WIDTH - f_w)/2:.0f},{y2:.0f}) scale({scale_f:.3f})' opacity='{opacity46}'>{inner(f46)}</g>")

    # "Aktive Etage"-Badge
    floor_names = ["SCANNER", "RESEARCH", "STRATEGY", "TESTING", "RISK", "CONTROL"]
    body.append(f"<rect x='{(WIDTH-300)/2:.0f}' y='{HEIGHT-52}' width='300' height='32' rx='8' fill='#0f172a' stroke='#7c5cff'/>")
    body.append(f"<text x='{WIDTH/2}' y='{HEIGHT-31}' text-anchor='middle' fill='#e2e8f0' font-size='14' font-weight='bold'>FLOOR {active+1:02d} · {floor_names[active]} ▸</text>")

    body.append("</svg>")
    return "\n".join(body)


def main():
    FRAMES_DIR.mkdir(exist_ok=True)
    for f in FRAMES_DIR.glob("*.png"):
        f.unlink()
    parts = load_svg_parts()
    missing = [k for k, v in parts.items() if v is None]
    if missing:
        print(f"FEHLENDE SVGs: {missing}")
        return 1
    print(f"Baue Video: {N_FRAMES} Frames @ {FPS}fps (~{N_FRAMES/FPS:.0f}s)")
    t0 = time.time()
    for i in range(N_FRAMES):
        progress = i / (N_FRAMES - 1)
        svg = render_frame(parts, progress)
        if svg is None:
            continue
        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=WIDTH, output_height=HEIGHT)
        Image.open(io.BytesIO(png)).convert("RGB").save(FRAMES_DIR / f"frame_{i:03d}.png")
        if i % 10 == 0:
            print(f"  Frame {i+1}/{N_FRAMES} ({time.time()-t0:.1f}s)")

    cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
           "-i", str(FRAMES_DIR / "frame_%03d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
           str(OUT_MP4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg Fehler:", r.stderr[-500:])
        return 1
    size_kb = OUT_MP4.stat().st_size // 1024
    print(f"MP4 geschrieben: {OUT_MP4} ({size_kb} KB, ~{N_FRAMES/FPS:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

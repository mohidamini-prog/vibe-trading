"""
Animiertes GIF des Orchestra Trading Desks (~15s Loop) — robust.

Rendert N Frames als PNGs, dann mit ffmpeg (oder PIL ohne optimize) zu GIF.
Kein Browser/GPU nötig.
Ausgabe: orchestra/visualizer/trading_desk.gif
"""
import io
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.visualizer import terminal_dashboard as td
import cairosvg
from PIL import Image

OUT_GIF = Path(__file__).resolve().parent / "trading_desk.gif"
FRAMES_DIR = Path("/tmp/orchestra_gif_frames")

N_FRAMES = 40
DURATION_MS = 375  # ~15s
WIDTH = 1000


def render_frame(progress):
    """SVG mit gegebenem Kurven-Fortschritt rendern -> PIL-Image."""
    td._PROGRESS = progress
    svg = td.build_svg()
    png_bytes = cairosvg.svg2png(bytestring=svg.encode(), output_width=WIDTH)
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def main():
    FRAMES_DIR.mkdir(exist_ok=True)
    # Alte Frames löschen
    for f in FRAMES_DIR.glob("*.png"):
        f.unlink()
    print(f"Baue GIF: {N_FRAMES} Frames à {DURATION_MS}ms (~{N_FRAMES*DURATION_MS/1000:.0f}s)")
    t0 = time.time()
    for i in range(N_FRAMES):
        phase = i / N_FRAMES
        progress = min(1.0, phase / 0.6)
        img = render_frame(progress)
        img.save(FRAMES_DIR / f"frame_{i:03d}.png")
        if i % 8 == 0:
            print(f"  Frame {i+1}/{N_FRAMES} ({time.time()-t0:.1f}s)")
    td._PROGRESS = 1.0

    # ffmpeg: PNG-Sequenz -> GIF (zuverlässig, keine Frame-Deduplizierung)
    # fps = 1000/DURATION_MS
    fps = 1000 / DURATION_MS
    cmd = ["ffmpeg", "-y", "-framerate", str(round(fps, 3)),
           "-i", str(FRAMES_DIR / "frame_%03d.png"),
           "-vf", "fps=10,scale=1000:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
           "-loop", "0", str(OUT_GIF)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # Fallback: PIL ohne optimize
        frames = [Image.open(FRAMES_DIR / f"frame_{i:03d}.png") for i in range(N_FRAMES)]
        frames[0].save(OUT_GIF, save_all=True, append_images=frames[1:],
                       duration=DURATION_MS, loop=0, optimize=False)
    size_kb = OUT_GIF.stat().st_size // 1024
    print(f"GIF geschrieben: {OUT_GIF} ({size_kb} KB, ~{N_FRAMES*DURATION_MS/1000:.0f}s)")


if __name__ == "__main__":
    main()

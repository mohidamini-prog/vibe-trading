"""
Echtes Dashboard-Rendering als SVG/PNG — OHNE Browser/GPU/Qt.

Da der Android-Container-Kernel kein Chromium/EGL/Qt rendern kann, zeichnet dieses
Skript das Trading Desk MIT DEN ECHTEN DATEN aus der State-DB als Vektor-SVG
(und optional PNG via cairosvg, falls installiert). Keine Simulation — die Votes,
Gewichte und Entscheidung kommen 1:1 aus dem Dirigenten.

Ausgabe: orchestra/visualizer/trading_desk.svg (+ .png wenn möglich)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.data import cache

OUT_SVG = Path(__file__).resolve().parent / "trading_desk.svg"
OUT_PNG = Path(__file__).resolve().parent / "trading_desk.png"

AGENT_META = {
    "momentum": {"label": "Momentum", "role": "Trend-Folger"},
    "meanrev": {"label": "MeanRev", "role": "Dip-Beifang"},
    "vola": {"label": "Vola/Risk", "role": "Bremser · VETO"},
    "quant": {"label": "Quant", "role": "Quant-Meinung"},
    "news": {"label": "News/EDGAR", "role": "Event-Filter · VETO"},
}
VOTE_COLOR = {1: "#22c55e", 0: "#94a3b8", -1: "#ef4444"}
VOTE_LABEL = {1: "BUY", 0: "HOLD", -1: "SELL"}
DEC_COLOR = {"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#94a3b8"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_svg():
    last = cache.get_state("last_decision", {})
    hist = cache.get_state("conductor_history", [])
    if not last:
        return "<svg width='800' height='400'><text>Keine Entscheidung</text></svg>"

    W, H = 1280, 940
    votes = last.get("votes", [])
    dec = last.get("decision", "HOLD")
    s = last.get("S", 0)
    dec_c = DEC_COLOR.get(dec, "#94a3b8")

    # --- Kopf / Dirigent ---
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
        f"viewBox='0 0 {W} {H}' font-family='Segoe UI, sans-serif'>",
        f"<defs><linearGradient id='bg' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0' stop-color='#1a1440'/><stop offset='1' stop-color='#0a0e1a'/>"
        f"</linearGradient></defs>",
        f"<rect width='{W}' height='{H}' fill='url(#bg)'/>",
        # Titel
        f"<text x='40' y='50' fill='#d7e0f2' font-size='26' font-weight='bold'>"
        f"Orchestra — Trading Desk</text>",
        f"<text x='40' y='76' fill='#6b7a99' font-size='14'>Echtzeit · 5 isolierte Subagenten · numpy-only</text>",
        # Dirigent-Karte
        f"<rect x='40' y='100' width='1200' height='120' rx='14' fill='#121a2e' "
        f"stroke='#1f2a45'/>",
        f"<text x='70' y='140' fill='#6b7a99' font-size='13'>DIRIGENT</text>",
        f"<text x='70' y='170' fill='#d7e0f2' font-size='22' font-weight='bold'>"
        f"{esc(last.get('symbol', '—'))}</text>",
        f"<text x='70' y='200' fill='#6b7a99' font-size='13'>S = {s:+.3f} · "
        f"Stärke {last.get('strength', 0):.3f} · Conf {last.get('avg_confidence', 0)*100:.0f}%</text>",
        # Entscheidung (rechts)
        f"<text x='1180' y='170' text-anchor='end' fill='{dec_c}' font-size='48' "
        f"font-weight='bold'>{dec}</text>",
        f"<text x='1180' y='200' text-anchor='end' fill='#6b7a99' font-size='12'>"
        f"{esc(last.get('timestamp', '')[:19])}</text>",
    ]

    # --- S-Verlauf Chart ---
    if hist:
        series = [h.get("S", 0) for h in hist[-30:]]
        cx0, cy0, cw, ch = 70, 280, 1140, 120
        parts.append(f"<rect x='{cx0-30}' y='{cy0-30}' width='{cw+60}' height='{ch+60}' "
                     f"rx='14' fill='#121a2e' stroke='#1f2a45'/>")
        parts.append(f"<text x='{cx0-10}' y='{cy0-10}' fill='#6b7a99' font-size='12'>"
                     f"S-Verlauf (letzte {len(series)} Zyklen)</text>")
        maxv = max(0.5, *map(abs, series))
        mid = cy0 + ch / 2
        parts.append(f"<line x1='{cx0}' y1='{mid}' x2='{cx0+cw}' y2='{mid}' "
                     f"stroke='rgba(255,255,255,.15)'/>")
        # Füllung + Linie
        pts = []
        for i, v in enumerate(series):
            x = cx0 + (i / max(1, len(series) - 1)) * cw
            y = mid - (v / maxv) * (ch / 2 - 8)
            pts.append(f"{x:.1f},{y:.1f}")
        poly = " ".join(pts)
        parts.append(f"<polygon points='{cx0},{mid} {poly} {cx0+cw},{mid}' "
                     f"fill='rgba(124,92,255,.15)'/>")
        parts.append(f"<polyline points='{poly}' fill='none' stroke='#7c5cff' "
                     f"stroke-width='2.5'/>")

    # --- 5 Roboter ---
    n = len(votes)
    card_w, gap = 232, 20
    x0 = (W - (n * card_w + (n - 1) * gap)) / 2
    y_rob = 430
    for i, v in enumerate(votes):
        meta = AGENT_META.get(v["agent"], {"label": v["agent"], "icon": "🤖", "role": ""})
        a = v["a"]
        col = VOTE_COLOR.get(a, "#94a3b8")
        x = x0 + i * (card_w + gap)
        # Karte
        parts.append(f"<rect x='{x}' y='{y_rob}' width='{card_w}' height='330' rx='14' "
                     f"fill='#121a2e' stroke='{col}' stroke-width='2'/>")
        # Roboter-Kopf (SVG-Form, kein Emoji — robust für cairosvg)
        cx = x + card_w / 2
        head_y = y_rob + 45
        parts.append(f"<rect x='{cx-42}' y='{head_y}' width='84' height='62' rx='12' "
                     f"fill='#1c2640' stroke='{col}' stroke-width='2'/>")
        # Augen
        eye_off = 18
        if a == 1:
            eyes_svg = (f"<circle cx='{cx-eye_off}' cy='{head_y+28}' r='7' fill='#22c55e'/>"
                        f"<circle cx='{cx+eye_off}' cy='{head_y+28}' r='7' fill='#22c55e'/>")
        elif a == -1:
            eyes_svg = (f"<circle cx='{cx-eye_off}' cy='{head_y+28}' r='7' fill='#ef4444'/>"
                        f"<circle cx='{cx+eye_off}' cy='{head_y+28}' r='7' fill='#ef4444'/>")
        else:
            eyes_svg = (f"<circle cx='{cx-eye_off}' cy='{head_y+28}' r='7' fill='#94a3b8'/>"
                        f"<circle cx='{cx+eye_off}' cy='{head_y+28}' r='7' fill='#94a3b8'/>")
        parts.append(eyes_svg)
        # Antenne
        parts.append(f"<line x1='{cx}' y1='{head_y}' x2='{cx}' y2='{head_y-14}' "
                     f"stroke='{col}' stroke-width='2'/>")
        parts.append(f"<circle cx='{cx}' cy='{head_y-18}' r='5' fill='{col}'/>")
        # Name + Rolle
        parts.append(f"<text x='{x+card_w/2}' y='{y_rob+140}' text-anchor='middle' "
                     f"fill='#d7e0f2' font-size='16' font-weight='bold'>{meta['label']}</text>")
        parts.append(f"<text x='{x+card_w/2}' y='{y_rob+160}' text-anchor='middle' "
                     f"fill='#6b7a99' font-size='11'>{meta['role']}</text>")
        # Vote
        parts.append(f"<text x='{x+card_w/2}' y='{y_rob+205}' text-anchor='middle' "
                     f"fill='{col}' font-size='28' font-weight='bold'>{VOTE_LABEL.get(a, 'HOLD')}</text>")
        # Confidence + Gewicht
        parts.append(f"<text x='{x+card_w/2}' y='{y_rob+235}' text-anchor='middle' "
                     f"fill='#6b7a99' font-size='12'>conf {v['conf']*100:.0f}% · "
                     f"w {last.get('weights', {}).get(v['agent'], 0)*100:.0f}%</text>")
        # Begründung
        reason = v.get("reason", "")[:60]
        parts.append(f"<text x='{x+card_w/2}' y='{y_rob+260}' text-anchor='middle' "
                     f"fill='#8b9bb8' font-size='10'>{esc(reason)}</text>")

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    svg = build_svg()
    OUT_SVG.write_text(svg)
    print(f"SVG geschrieben: {OUT_SVG}")
    # PNG via cairosvg (falls da), sonst nur SVG
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT_PNG),
                         output_width=1280)
        print(f"PNG geschrieben: {OUT_PNG}")
    except ImportError:
        print("cairosvg nicht installiert — nur SVG. (uv pip install cairosvg für PNG)")

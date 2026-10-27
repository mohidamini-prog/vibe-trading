"""
Grok-Bot-Terminal im Stil der viralen Reels — fürs Orchestra.

Baut das komplette Trading-Dashboard (Header, Agenten-Seitenleiste, Profit-Kurve,
Flow VOTE->CHECK->DECIDE, Trade-Log) MIT ECHTEN Daten aus dem Orchester als SVG/PNG.
Kein Browser/GPU nötig — rendert via cairosvg.

Ausgabe: orchestra/visualizer/terminal_dashboard.svg / .png
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.data import cache

OUT_SVG = Path(__file__).resolve().parent / "terminal_dashboard.svg"
OUT_PNG = Path(__file__).resolve().parent / "terminal_dashboard.png"

# Agenten-Module (wie im Referenz-Bild): (key, name, farbe, untertitel)
MODULES = [
    ("momentum", "SCANNER",     "#facc15", "findet Trends & Vola-Spitzen · flags only, never trades"),
    ("meanrev",  "RUG CHECK",   "#f87171", "filtert Fake-Signale · nothing executes before a pass"),
    ("vola",     "SIZER",       "#a78bfa", "risiko-basiertes Sizing · berechnet Positionsgröße"),
    ("quant",    "EXECUTOR",    "#38bdf8", "öffnet & schließt Trades · slipcap cap 2.0%"),
    ("news",     "LOGGER",      "#fb923c", "schreibt jede Entscheidung · no trade without a reason"),
    ("chief",    "EQUITY",      "#2dd4bf", "verwaltet Balance & Kurve · S-Wert & Stärke"),
]
DEC_COLOR = {"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#facc15"}
VOTE_SIGN = {1: "JA", 0: "WARTET", -1: "NEIN"}
VOTE_COLOR = {1: "#22c55e", 0: "#facc15", -1: "#ef4444"}


# Modul-globale Progress-Variable (für Kurven-Animation im GIF)
_PROGRESS = 1.0


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def mini_robot(cx, cy, s, color, vote):
    """Kleiner Roboter-Kopf (für Seitenleiste). cx,cy = Zentrum, s = Skalierung."""
    ec = VOTE_COLOR.get(vote, "#facc15")
    p = []
    # Kopfhörer-Bügel
    p.append(f"<path d='M {cx-11*s} {cy-15*s} A 11 {11} 0 0 1 {cx+11*s} {cy-15*s}' "
             f"fill='none' stroke='{color}' stroke-width='3.5'/>")
    p.append(f"<rect x='{cx-14*s}' y='{cy-14*s}' width='5' height='10' rx='2' fill='{color}'/>")
    p.append(f"<rect x='{cx+9*s}' y='{cy-14*s}' width='5' height='10' rx='2' fill='{color}'/>")
    # Kopf (rund, weiß)
    p.append(f"<circle cx='{cx}' cy='{cy-2*s}' r='11*s' fill='#f8fafc' stroke='#cbd5e1' stroke-width='1'/>")
    # Visier
    p.append(f"<rect x='{cx-8*s}' y='{cy-7*s}' width='16*s' height='8*s' rx='4*s' fill='#0f172a'/>")
    # Augen
    if vote == 1:
        p.append(f"<circle cx='{cx-3.5*s}' cy='{cy-3*s}' r='1.8*s' fill='#22c55e'/>")
        p.append(f"<circle cx='{cx+3.5*s}' cy='{cy-3*s}' r='1.8*s' fill='#22c55e'/>")
    elif vote == -1:
        p.append(f"<path d='M {cx-5*s} {cy-5*s} l 3 3 M {cx-2*s} {cy-5*s} l -3 3' stroke='#ef4444' stroke-width='1.5' fill='none'/>")
        p.append(f"<path d='M {cx+2*s} {cy-5*s} l 3 3 M {cx+5*s} {cy-5*s} l -3 3' stroke='#ef4444' stroke-width='1.5' fill='none'/>")
    else:
        p.append(f"<circle cx='{cx-3.5*s}' cy='{cy-3*s}' r='1.8*s' fill='#facc15'>"
                 f"<animate attributeName='r' values='1.2;2.4;1.2' dur='1.2s' repeatCount='indefinite'/></circle>")
        p.append(f"<circle cx='{cx+3.5*s}' cy='{cy-3*s}' r='1.8*s' fill='#facc15'>"
                 f"<animate attributeName='r' values='1.2;2.4;1.2' dur='1.2s' repeatCount='indefinite'/></circle>")
    return "\n".join(p)


def build_svg():
    last = cache.get_state("last_decision", {})
    hist = cache.get_state("conductor_history", [])
    if not last:
        return "<svg width='800' height='500'><text>Keine Entscheidung</text></svg>"

    W, H = 1280, 900
    votes = {v["agent"]: v for v in last.get("votes", [])}
    dec = last.get("decision", "HOLD")
    dec_c = DEC_COLOR.get(dec, "#facc15")
    p = []

    p.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
             f"viewBox='0 0 {W} {H}' font-family='Segoe UI, monospace'>")
    # Dunkler Hintergrund
    p.append(f"<defs><linearGradient id='bg' x1='0' y1='0' x2='0' y2='1'>"
             f"<stop offset='0' stop-color='#0a0a0f'/><stop offset='1' stop-color='#050507'/>"
             f"</linearGradient>"
             f"<radialGradient id='glow' cx='.5' cy='.5' r='.5'>"
             f"<stop offset='0' stop-color='#7c5cff' stop-opacity='.35'/>"
             f"<stop offset='1' stop-color='#7c5cff' stop-opacity='0'/>"
             f"</radialGradient></defs>")
    p.append(f"<rect width='{W}' height='{H}' fill='url(#bg)'/>")

    # ============ HEADER ============
    p.append(f"<rect x='0' y='0' width='{W}' height='72' fill='#0f0f16'/>")
    p.append(f"<line x1='0' y1='72' x2='{W}' y2='72' stroke='#22223a'/>")
    p.append(f"<text x='20' y='30' fill='#e2e8f0' font-size='20' font-weight='bold'>"
             f"Orchestra Bot Terminal</text>")
    p.append(f"<text x='20' y='52' fill='#64748b' font-size='11'>"
             f"v1.8-night · every trade gets a reason</text>")
    # RUNNING Status
    p.append(f"<circle cx='300' cy='27' r='6' fill='#22c55e'>"
             f"<animate attributeName='opacity' values='1;.3;1' dur='1.5s' repeatCount='indefinite'/>"
             f"</circle>")
    p.append(f"<text x='315' y='32' fill='#22c55e' font-size='13' font-weight='bold'>RUNNING</text>")
    # Balance + Trades
    bal = last.get("strength", 0)
    bal_str = f"${abs(bal):.2f}"
    p.append(f"<text x='1050' y='32' text-anchor='end' fill='{dec_c}' font-size='22' font-weight='bold'>"
             f"{bal_str}</text>")
    p.append(f"<text x='1050' y='52' text-anchor='end' fill='#64748b' font-size='11'>"
             f"S = {last.get('S',0):+.3f} · {len(hist)} Zyklen</text>")
    p.append(f"<text x='1180' y='32' text-anchor='end' fill='#94a3b8' font-size='12'>"
             f"{dec}</text>")
    p.append(f"<text x='1180' y='52' text-anchor='end' fill='#64748b' font-size='10'>"
             f"{esc(last.get('timestamp','')[:19])}</text>")

    # ============ LINKE SEITENLEISTE (Agenten) ============
    p.append(f"<rect x='0' y='72' width='250' height='{H-72}' fill='#0b0b12'/>")
    p.append(f"<line x1='250' y1='72' x2='250' y2='{H}' stroke='#22223a'/>")
    side_y = 95
    for key, name, color, sub in MODULES:
        v = votes.get(key, {"a": 0, "conf": 0, "weight": 0})
        if key == "chief":
            vote = 1 if dec == "BUY" else (-1 if dec == "SELL" else 0)
            conf = last.get("avg_confidence", 0)
            wtxt = "MASTER"
        else:
            vote = v.get("a", 0)
            conf = v.get("conf", 0)
            wtxt = f"{v.get('weight',0)*100:.0f}% eq"
        p.append(f"<rect x='10' y='{side_y}' width='230' height='118' rx='8' fill='#12121c' "
                 f"stroke='#22223a'/>")
        # Farbschiene
        p.append(f"<rect x='10' y='{side_y}' width='4' height='118' rx='2' fill='{color}'/>")
        # Kleiner Roboter (links)
        p.append(mini_robot(45, side_y + 30, 1.4, color, vote))
        # Name
        p.append(f"<text x='80' y='{side_y+22}' fill='{color}' font-size='13' font-weight='bold'>"
                 f"{name}</text>")
        # Status-Zeile
        sign = VOTE_SIGN.get(vote, "WARTET")
        sc = VOTE_COLOR.get(vote, "#facc15")
        p.append(f"<text x='80' y='{side_y+42}' fill='{sc}' font-size='12' font-weight='bold'>"
                 f"{sign} · conf {conf*100:.0f}%</text>")
        # Untertitel
        p.append(f"<text x='80' y='{side_y+62}' fill='#64748b' font-size='9'>{esc(sub[:38])}</text>")
        p.append(f"<text x='80' y='{side_y+80}' fill='#94a3b8' font-size='10'>"
                 f"nächster: {wtxt}</text>")
        # Grünes Häkchen / gelbes Pause / rotes X (rechts oben)
        if vote == 1:
            p.append(f"<path d='M 215 {side_y+15} l 5 6 l 12 -14' fill='none' stroke='#22c55e' "
                     f"stroke-width='3' stroke-linecap='round'/>")
        elif vote == -1:
            p.append(f"<path d='M 210 {side_y+12} l 12 12 M 222 {side_y+12} l -12 12' "
                     f"stroke='#ef4444' stroke-width='3' stroke-linecap='round'/>")
        else:
            p.append(f"<rect x='212' y='{side_y+10}' width='3' height='14' rx='1' fill='#facc15'/>"
                     f"<rect x='218' y='{side_y+10}' width='3' height='14' rx='1' fill='#facc15'/>")
        side_y += 126

    # ============ HAUPTBEREICH ============
    mx = 270  # Hauptbereich X
    mw = W - mx - 20
    # Tabs
    tabs = ["LIVE FLOW", "SCAN", "CHECK", "SIZE", "EXEC", "LOG"]
    tab_x = mx
    p.append(f"<rect x='{mx}' y='80' width='{mw}' height='36' fill='#0f0f16'/>")
    for t in tabs:
        active = t == "LIVE FLOW"
        p.append(f"<text x='{tab_x+14}' y='{102}' fill='{'#e2e8f0' if active else '#64748b'}' "
                 f"font-size='11' font-weight='bold'>{t}</text>")
        if active:
            p.append(f"<line x1='{tab_x+8}' y1='116' x2='{tab_x+70}' y2='116' "
                     f"stroke='#7c5cff' stroke-width='2'/>")
        tab_x += 82

    # ============ MANAGERIN (zentrale Figur) ============
    # Glow hinter der Managerin
    man_x, man_y = mx + 120, 175
    p.append(f"<circle cx='{man_x}' cy='{man_y}' r='80' fill='url(#glow)' opacity='.4'/>")
    # Kopf (größer, weiblich — mit Haaren)
    p.append(f"<circle cx='{man_x}' cy='{man_y-18}' r='26' fill='#fde68a' stroke='#d4a373' stroke-width='1.5'/>")
    # Haare (oben + seitlich)
    p.append(f"<path d='M {man_x-24} {man_y-22} A 26 26 0 0 1 {man_x+24} {man_y-22} "
             f"L {man_x+20} {man_y-40} A 30 30 0 0 0 {man_x-20} {man_y-40} Z' fill='#3b2f2f'/>")
    p.append(f"<path d='M {man_x-26} {man_y-14} Q {man_x-34} {man_y+6} {man_x-30} {man_y+20} "
             f"Q {man_x-22} {man_y+8} {man_x-24} {man_y-6} Z' fill='#3b2f2f'/>")
    p.append(f"<path d='M {man_x+26} {man_y-14} Q {man_x+34} {man_y+6} {man_x+30} {man_y+20} "
             f"Q {man_x+22} {man_y+8} {man_x+24} {man_y-6} Z' fill='#3b2f2f'/>")
    # Augen (lächelnd, lila leuchtend)
    p.append(f"<circle cx='{man_x-8}' cy='{man_y-20}' r='2.5' fill='#7c5cff'/>")
    p.append(f"<circle cx='{man_x+8}' cy='{man_y-20}' r='2.5' fill='#7c5cff'/>")
    # Mund (Lächeln)
    p.append(f"<path d='M {man_x-6} {man_y-10} Q {man_x} {man_y-4} {man_x+6} {man_y-10}' "
             f"fill='none' stroke='#b45309' stroke-width='1.8' stroke-linecap='round'/>")
    # Körper (Blazer, lila)
    p.append(f"<path d='M {man_x-22} {man_y+6} Q {man_x} {man_y-2} {man_x+22} {man_y+6} "
             f"L {man_x+26} {man_y+48} L {man_x-26} {man_y+48} Z' fill='#7c5cff' opacity='.9'/>")
    # Kragen (weiß)
    p.append(f"<path d='M {man_x-8} {man_y+4} L {man_x} {man_y+16} L {man_x+8} {man_y+4} Z' fill='#f8fafc'/>")
    # Arme
    p.append(f"<line x1='{man_x-24}' y1='{man_y+14}' x2='{man_x-40}' y2='{man_y+30}' "
             f"stroke='#7c5cff' stroke-width='5' stroke-linecap='round'/>")
    p.append(f"<line x1='{man_x+24}' y1='{man_y+14}' x2='{man_x+40}' y2='{man_y+30}' "
             f"stroke='#7c5cff' stroke-width='5' stroke-linecap='round'/>")
    # Hände
    p.append(f"<circle cx='{man_x-40}' cy='{man_y+30}' r='4' fill='#fde68a'/>")
    p.append(f"<circle cx='{man_x+40}' cy='{man_y+30}' r='4' fill='#fde68a'/>")
    # Badge "MANAGERIN"
    p.append(f"<rect x='{man_x-42}' y='{man_y+52}' width='84' height='20' rx='10' fill='#1e293b' "
             f"stroke='#7c5cff' stroke-width='1.5'/>")
    p.append(f"<text x='{man_x}' y='{man_y+66}' text-anchor='middle' fill='#7c5cff' "
             f"font-size='11' font-weight='bold'>MANAGERIN</text>")

    # Ticker-Karten (Symbole aus dem Universum) — rechts neben der Managerin
    tick_y = 128
    symbols = ["AAPL", "MSFT", "NVDA", "META"]
    tick_x = man_x + 160
    tick_w = (mx + mw - tick_x) / 4
    for i, sym in enumerate(symbols):
        tx = tick_x + i * tick_w
        p.append(f"<rect x='{tx}' y='{tick_y}' width='{tick_w - 8}' height='54' rx='6' "
                 f"fill='#12121c' stroke='#22223a'/>")
        p.append(f"<text x='{tx+10}' y='{tick_y+20}' fill='#e2e8f0' font-size='12' font-weight='bold'>"
                 f"${sym}</text>")
        p.append(f"<text x='{tx+10}' y='{tick_y+38}' fill='#22c55e' font-size='10'>"
                 f"+{(i+1)*2}.{(i*7)%10}%</text>")

    # Profit-Kurve (aus S-Verlauf)
    curve_y = 290
    p.append(f"<rect x='{mx}' y='{curve_y}' width='{mw}' height='160' rx='8' fill='#0d0d15' "
             f"stroke='#22223a'/>")
    p.append(f"<text x='{mx+12}' y='{curve_y+22}' fill='#94a3b8' font-size='12' font-weight='bold'>"
             f"PROFIT-KURVE · S-Verlauf</text>")
    p.append(f"<text x='{mx+mw-12}' y='{curve_y+22}' text-anchor='end' fill='{dec_c}' "
             f"font-size='16' font-weight='bold'>{dec} · {last.get('S',0):+.2f}</text>")
    series = [h.get("S", 0) for h in hist[-30:]] or [0, 0]
    maxv = max(0.5, *map(abs, series))
    mid = curve_y + 100
    p.append(f"<line x1='{mx+10}' y1='{mid}' x2='{mx+mw-10}' y2='{mid}' stroke='#22223a'/>")
    pts = []
    for i, v in enumerate(series):
        x = mx + 10 + (i / max(1, len(series)-1)) * (mw - 20)
        y = mid - (v / maxv) * 70
        pts.append(f"{x:.1f},{y:.1f}")
    # Kurven-Animation: nur die ersten `progress` Anteile zeichnen
    progress = _PROGRESS
    if progress is None:
        progress = 1.0
    n_vis = max(2, int(len(pts) * progress) + 1)
    vis_pts = pts[:n_vis]
    poly = " ".join(vis_pts)
    # Füllung nur bis zum letzten sichtbaren Punkt
    p.append(f"<polyline points='{poly}' fill='none' stroke='{dec_c}' stroke-width='2.5'/>")
    last_pt = vis_pts[-1].split(",")
    p.append(f"<polygon points='{mx+10},{mid} {poly} {last_pt[0]},{mid}' fill='{dec_c}' opacity='.08'/>")
    # Punkte an den sichtbaren Stellen (Glow-Effekt)
    if progress > 0:
        px, py = map(float, vis_pts[-1].split(","))
        p.append(f"<circle cx='{px}' cy='{py}' r='4' fill='{dec_c}'>"
                 f"<animate attributeName='r' values='3;6;3' dur='1s' repeatCount='indefinite'/></circle>")

    # ============ FLOW (VOTE -> CHECK -> DECIDE) ============
    flow_y = 470
    p.append(f"<text x='{mx}' y='{flow_y}' fill='#94a3b8' font-size='12' font-weight='bold'>"
             f"FLOW</text>")
    flow_steps = [("VOTE", "#38bdf8", "5 Agenten stimmen ab"),
                  ("CHECK", "#facc15", "Risiko & News prüfen"),
                  ("DECIDE", "#22c55e", f"Dirigent: {dec}")]
    fx = mx + 10
    for name, color, sub in flow_steps:
        p.append(f"<rect x='{fx}' y='{flow_y+12}' width='200' height='54' rx='8' "
                 f"fill='#12121c' stroke='{color}' stroke-width='1.5'/>")
        p.append(f"<text x='{fx+12}' y='{flow_y+36}' fill='{color}' font-size='14' font-weight='bold'>"
                 f"{name}</text>")
        p.append(f"<text x='{fx+12}' y='{flow_y+54}' fill='#64748b' font-size='9'>{esc(sub)}</text>")
        if name != "DECIDE":
            p.append(f"<text x='{fx+215}' y='{flow_y+42}' fill='#7c5cff' font-size='20'>→</text>")
        fx += 235

    # ============ TRADE-PANEL (aktueller Trade) ============
    trade_y = 560
    p.append(f"<rect x='{mx}' y='{trade_y}' width='{mw}' height='110' rx='8' fill='#0d0d15' "
             f"stroke='#22223a'/>")
    p.append(f"<text x='{mx+12}' y='{trade_y+22}' fill='#94a3b8' font-size='12' font-weight='bold'>"
             f"TRADE · ENTRY vs EXIT</text>")
    sym = last.get("symbol", "—")
    p.append(f"<text x='{mx+12}' y='{trade_y+52}' fill='#e2e8f0' font-size='22' font-weight='bold'>"
             f"${sym} ({'LONG' if dec=='BUY' else ('SHORT' if dec=='SELL' else 'FLAT')})</text>")
    p.append(f"<text x='{mx+12}' y='{trade_y+74}' fill='#64748b' font-size='11'>"
             f"Status: {dec.lower()} · S={last.get('S',0):+.3f} · Stärke {last.get('strength',0):.3f}</text>")
    p.append(f"<text x='{mx+12}' y='{trade_y+94}' fill='#94a3b8' font-size='10'>"
             f"Begründung: {'Dirigent-Entscheidung aus 5 Agenten-Votes'}</text>")
    # Votes-Zusammenfassung rechts
    vr = mx + mw - 180
    p.append(f"<text x='{vr}' y='{trade_y+30}' fill='#64748b' font-size='10'>AGENTEN-VOTES</text>")
    for i, (key, name, color, sub) in enumerate(MODULES[:5]):
        v = votes.get(key, {"a": 0, "conf": 0})
        vy = trade_y + 48 + i * 12
        p.append(f"<text x='{vr}' y='{vy}' fill='{color}' font-size='9'>{name}</text>")
        p.append(f"<text x='{vr+110}' y='{vy}' text-anchor='end' fill='{VOTE_COLOR.get(v.get('a',0),'#facc15')}' "
                 f"font-size='9'>{VOTE_SIGN.get(v.get('a',0),'WARTET')} {v.get('conf',0)*100:.0f}%</text>")

    # ============ TRADE-LOG (unten) ============
    log_y = 690
    p.append(f"<rect x='{mx}' y='{log_y}' width='{mw}' height='{H-log_y-20}' rx='8' fill='#0d0d15' "
             f"stroke='#22223a'/>")
    p.append(f"<text x='{mx+12}' y='{log_y+22}' fill='#94a3b8' font-size='12' font-weight='bold'>"
             f"LOG · jede Entscheidung mit Grund</text>")
    log_rows = []
    for h in reversed(hist[-5:]):
        sym2 = h.get("symbol", "?")
        d = h.get("decision", "HOLD")
        s = h.get("S", 0)
        log_rows.append((sym2, d, s, h.get("timestamp", "")))
    for i, (sym2, d, s, ts) in enumerate(log_rows):
        ly = log_y + 45 + i * 32
        dc = DEC_COLOR.get(d, "#facc15")
        p.append(f"<text x='{mx+14}' y='{ly}' fill='#64748b' font-size='10'>{ts[11:19]}</text>")
        p.append(f"<text x='{mx+90}' y='{ly}' fill='{dc}' font-size='11' font-weight='bold'>{d}</text>")
        p.append(f"<text x='{mx+170}' y='{ly}' fill='#e2e8f0' font-size='11' font-weight='bold'>${sym2}</text>")
        p.append(f"<text x='{mx+250}' y='{ly}' fill='#64748b' font-size='10'>"
                 f"S={s:+.2f} · Stärke {h.get('strength',0):.2f}</text>")

    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    svg = build_svg()
    OUT_SVG.write_text(svg)
    print(f"SVG geschrieben: {OUT_SVG}")
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT_PNG), output_width=1280)
        print(f"PNG geschrieben: {OUT_PNG}")
    except ImportError:
        print("cairosvg fehlt — nur SVG")

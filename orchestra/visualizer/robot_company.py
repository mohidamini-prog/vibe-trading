"""
Roboter-Firma — die 5 Subagenten + Dirigent als animierte SVG-Szene am runden Tisch.

Zeichnet 6 Roboter (weiße Kapsel-Körper, Visier mit leuchtenden Augen, farbige
Kopfhörer) an einem runden Tisch, mit Voting-Panel (VOTE -> CHECK -> DECIDE) und
Final-Call-Banner. Die Votes kommen ECHT aus dem Orchester (State-DB).
Kein Browser/GPU nötig — rendert via cairosvg zu PNG.

Ausgabe: orchestra/visualizer/robot_company.svg / .png
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.data import cache

OUT_SVG = Path(__file__).resolve().parent / "robot_company.svg"
OUT_PNG = Path(__file__).resolve().parent / "robot_company.png"

# Agent -> (Name, Kopfhörer-Farbe)
CREW = [
    ("momentum", "Momentum",   "#38bdf8"),  # Blau
    ("meanrev",  "MeanRev",    "#4ade80"),  # Grün
    ("vola",     "Vola/Risk",  "#a78bfa"),  # Lila
    ("quant",    "Quant",      "#f87171"),  # Rot
    ("news",     "News/EDGAR", "#facc15"),  # Gelb
]
VOTE_COLOR = {1: "#22c55e", 0: "#facc15", -1: "#ef4444"}
VOTE_LABEL = {1: "JA", 0: "WARTET", -1: "NEIN"}
DEC_COLOR = {"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#facc15"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def robot(cx, cy, s, color, eyes, name, vote, conf, weight, is_chief=False):
    """Ein Roboter (Draufsicht-vorne). cx,cy = Tischrand-Position, s = Skalierung."""
    p = []
    # Kopfhörer-Bügel (hinter Kopf)
    p.append(f"<path d='M {cx-22*s} {cy-38*s} A 22 {22} 0 0 1 {cx+22*s} {cy-38*s}' "
             f"fill='none' stroke='{color}' stroke-width='6'/>")
    # Kopfhörer-Muscheln
    p.append(f"<rect x='{cx-27*s}' y='{cy-36*s}' width='9' height='18' rx='3' fill='{color}'/>")
    p.append(f"<rect x='{cx+18*s}' y='{cy-36*s}' width='9' height='18' rx='3' fill='{color}'/>")
    # Körper (Kapsel)
    p.append(f"<rect x='{cx-26*s}' y='{cy-26*s}' width='52*s' height='{52*s}' rx='22*s' "
             f"fill='#f8fafc' stroke='#cbd5e1' stroke-width='1.5'/>")
    # Kopf (rund, weiß)
    p.append(f"<circle cx='{cx}' cy='{cy-14*s}' r='20*s' fill='#ffffff' stroke='#cbd5e1' stroke-width='1.5'/>")
    # Visier (dunkel)
    p.append(f"<rect x='{cx-16*s}' y='{cy-24*s}' width='32*s' height='15*s' rx='7*s' "
             f"fill='#0f172a'/>")
    # Augen (leuchten je nach Vote)
    ec = VOTE_COLOR.get(vote, "#facc15")
    if vote == 1:
        eye1 = f"<circle cx='{cx-7*s}' cy='{cy-17*s}' r='3.2*s' fill='{ec}'/>"
        eye2 = f"<circle cx='{cx+7*s}' cy='{cy-17*s}' r='3.2*s' fill='{ec}'/>"
    elif vote == -1:
        eye1 = f"<path d='M {cx-10*s} {cy-20*s} l 6 6 M {cx-4*s} {cy-20*s} l -6 6' stroke='{ec}' stroke-width='2' fill='none'/>"
        eye2 = f"<path d='M {cx+4*s} {cy-20*s} l 6 6 M {cx+10*s} {cy-20*s} l -6 6' stroke='{ec}' stroke-width='2' fill='none'/>"
    else:
        eye1 = f"<circle cx='{cx-7*s}' cy='{cy-17*s}' r='3.2*s' fill='{ec}'/>"
        eye2 = f"<circle cx='{cx+7*s}' cy='{cy-17*s}' r='3.2*s' fill='{ec}'/>"
        # Pulsierender Puls
        eye1 += f"<animate attributeName='r' values='2.5;4;2.5' dur='1.5s' repeatCount='indefinite'/>"
        eye2 += f"<animate attributeName='r' values='2.5;4;2.5' dur='1.5s' repeatCount='indefinite'/>"
    p.append(eye1)
    p.append(eye2)
    # Arme (segmentiert, metallisch)
    p.append(f"<line x1='{cx-26*s}' y1='{cy+2*s}' x2='{cx-40*s}' y2='{cy+16*s}' stroke='#94a3b8' stroke-width='4' stroke-linecap='round'/>")
    p.append(f"<line x1='{cx+26*s}' y1='{cy+2*s}' x2='{cx+40*s}' y2='{cy+16*s}' stroke='#94a3b8' stroke-width='4' stroke-linecap='round'/>")
    # Schild mit Name + Status
    if is_chief:
        p.append(f"<rect x='{cx-30*s}' y='{cy+34*s}' width='60*s' height='20*s' rx='6' fill='#1e293b' stroke='{color}' stroke-width='1.5'/>")
        p.append(f"<text x='{cx}' y='{cy+48*s}' text-anchor='middle' fill='{color}' font-size='9*s' font-weight='bold'>CHIEF</text>")
    else:
        p.append(f"<text x='{cx}' y='{cy+34*s}' text-anchor='middle' fill='#94a3b8' font-size='9*s'>{esc(name)}</text>")
        p.append(f"<text x='{cx}' y='{cy+46*s}' text-anchor='middle' fill='{VOTE_COLOR.get(vote,'#facc15')}' font-size='11*s' font-weight='bold'>{esc(VOTE_LABEL.get(vote,'WARTET'))}</text>")
        p.append(f"<text x='{cx}' y='{cy+58*s}' text-anchor='middle' fill='#64748b' font-size='8*s'>conf {conf*100:.0f}% · w {weight*100:.0f}%</text>")
    return "\n".join(p)


def build_svg():
    last = cache.get_state("last_decision", {})
    if not last:
        return "<svg width='900' height='600'><text>Keine Entscheidung</text></svg>"

    W, H = 1000, 760
    votes = {v["agent"]: v for v in last.get("votes", [])}
    dec = last.get("decision", "HOLD")
    dec_c = DEC_COLOR.get(dec, "#facc15")
    agree = sum(1 for v in votes.values() if v["a"] == 1)
    n = len(votes)
    need = max(3, (n + 1) // 2 + 1)  # "4 of 6" wenn 6 Stimmen
    p = []

    p.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' font-family='Segoe UI, sans-serif'>")
    # Hintergrund (Cyberpunk-Nacht)
    p.append(f"<defs>"
             f"<linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'>"
             f"<stop offset='0' stop-color='#0b1026'/><stop offset='.6' stop-color='#141a3a'/><stop offset='1' stop-color='#0a0e1a'/></linearGradient>"
             f"<radialGradient id='glow' cx='.5' cy='.5' r='.5'>"
             f"<stop offset='0' stop-color='{dec_c}' stop-opacity='.25'/><stop offset='1' stop-color='{dec_c}' stop-opacity='0'/></radialGradient>"
             f"</defs>")
    p.append(f"<rect width='{W}' height='{H}' fill='url(#sky)'/>")
    # Stadt-Silhouette (Skyline)
    for i, (bx, bw, bh) in enumerate([(40,70,180),(130,50,120),(210,80,220),(320,55,150),(400,70,190),(500,60,140),(580,80,230),(690,50,160),(760,70,200),(850,55,130)]):
        p.append(f"<rect x='{bx}' y='{H-340-bh}' width='{bw}' height='{bh}' fill='#0f1730'/>")
        # Fenster
        for wy in range(H-340-bh+10, H-340, 22):
            for wx in range(bx+8, bx+bw-8, 18):
                if (wx+wy) % 3 == 0:
                    p.append(f"<rect x='{wx}' y='{wy}' width='4' height='6' fill='#facc15' opacity='.25'/>")
    # Neon-Horizont
    p.append(f"<line x1='0' y1='{H-340}' x2='{W}' y2='{H-340}' stroke='#7c5cff' stroke-width='2' opacity='.4'/>")

    # Tisch (rund, grüner Filz) — Ellipse in Perspektive
    tx, ty, rx, ry = W/2, 480, 300, 150
    p.append(f"<ellipse cx='{tx}' cy='{ty}' rx='{rx}' ry='{ry}' fill='#0f3d2e' stroke='#5b3a1e' stroke-width='14'/>")
    p.append(f"<ellipse cx='{tx}' cy='{ty}' rx='{rx}' ry='{ry}' fill='none' stroke='#16a34a' stroke-width='2' opacity='.5'/>")
    # Tisch-Details: Laptop, Kaffee, Pflanze
    p.append(f"<rect x='{tx-120}' y='{ty-20}' width='60' height='38' rx='3' fill='#1e293b'/>")
    p.append(f"<rect x='{tx-115}' y='{ty-14}' width='50' height='26' fill='#0ea5e9' opacity='.8'/>")
    p.append(f"<circle cx='{tx+90}' cy='{ty+5}' r='12' fill='#78350f'/>")
    p.append(f"<circle cx='{tx+90}' cy='{ty+3}' r='9' fill='#451a03'/>")
    p.append(f"<path d='M {tx+150} {ty-10} q 10 -40 0 -55 q 15 20 0 55' fill='#22c55e'/>")

    # Roboter platzieren (5 Agenten + Chief am runden Tisch)
    import math
    positions = []
    for i in range(5):
        ang = math.radians(-150 + i * 75)  # 5 Positionen, Lücke unten für Chief
        positions.append((tx + (rx+58) * math.cos(ang), ty + (ry+38) * math.sin(ang) * 0.9))
    # Chief unten (Vorsitzender)
    chief_pos = (tx, ty + ry + 60)

    # Roboter zeichnen
    for i, (agent, name, color) in enumerate(CREW):
        v = votes.get(agent, {"a": 0, "conf": 0, "weight": 0})
        cx, cy = positions[i]
        s = 1.0
        p.append(robot(cx, cy, s, color, v["a"], name, v["a"], v.get("conf", 0), v.get("weight", 0)))
    # Chief (Dirigent)
    p.append(robot(chief_pos[0], chief_pos[1], 1.25, "#7c5cff", 1 if dec == "BUY" else (-1 if dec == "SELL" else 0),
                   "Dirigent", 1 if dec == "BUY" else (-1 if dec == "SELL" else 0), last.get("avg_confidence", 0), 1.0, is_chief=True))

    # Bildschirm oben mit Voting-Panel
    p.append(f"<rect x='{W/2-190}' y='70' width='380' height='150' rx='12' fill='#0f172a' stroke='#7c5cff' stroke-width='2'/>")
    p.append(f"<rect x='{W/2-180}' y='80' width='360' height='130' rx='8' fill='#1e293b'/>")
    # Titel
    p.append(f"<text x='{W/2}' y='108' text-anchor='middle' fill='#e2e8f0' font-size='20' font-weight='bold'>VOTE → CHECK → DECIDE</text>")
    # Abstimmungs-Zeile: Häkchen / Pause für jeden Agent
    xs = W/2 - 140
    for i, (agent, name, color) in enumerate(CREW):
        v = votes.get(agent, {"a": 0})
        x = xs + i * 70
        p.append(f"<circle cx='{x}' cy='' fill='none'/>" if False else "")
        if v["a"] == 1:
            p.append(f"<path d='M {x-10} 150 l 6 7 l 14 -16' fill='none' stroke='#22c55e' stroke-width='3' stroke-linecap='round'/>")
        elif v["a"] == -1:
            p.append(f"<path d='M {x-8} 142 l 16 16 M {x+8} 142 l -16 16' stroke='#ef4444' stroke-width='3' stroke-linecap='round'/>")
        else:
            p.append(f"<rect x='{x-5}' y='142' width='4' height='16' rx='1' fill='#facc15'/>"
                     f"<rect x='{x+3}' y='142' width='4' height='16' rx='1' fill='#facc15'/>")
        p.append(f"<text x='{x}' y='178' text-anchor='middle' fill='#94a3b8' font-size='9'>{esc(name.split('/')[0].strip())}</text>")
    # "X OF 6 MUST AGREE"
    p.append(f"<text x='{W/2}' y='200' text-anchor='middle' fill='{dec_c}' font-size='14' font-weight='bold'>{agree} OF {n} STIMMEN JA</text>")

    # Final Call Banner unten
    p.append(f"<rect x='{W/2-220}' y='{H-90}' width='440' height='60' rx='12' fill='#0f172a' stroke='{dec_c}' stroke-width='3'/>")
    p.append(f"<rect x='{W/2-210}' y='{H-82}' width='420' height='44' rx='8' fill='{dec_c}' opacity='.15'/>")
    p.append(f"<text x='{W/2}' y='{H-56}' text-anchor='middle' fill='{dec_c}' font-size='26' font-weight='bold'>FINAL CALL: {esc(last.get('symbol',''))} · {esc(dec)} · S={last.get('S',0):+.2f}</text>")
    p.append(f"<text x='{W/2}' y='{H-38}' text-anchor='middle' fill='#64748b' font-size='11'>{esc(last.get('timestamp','')[:19])} · Stärke {last.get('strength',0):.2f}</text>")

    # Glow
    p.append(f"<circle cx='{W/2}' cy='{H/2}' r='380' fill='url(#glow)' opacity='.5'/>")

    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    svg = build_svg()
    OUT_SVG.write_text(svg)
    print(f"SVG geschrieben: {OUT_SVG}")
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT_PNG), output_width=1000)
        print(f"PNG geschrieben: {OUT_PNG}")
    except ImportError:
        print("cairosvg fehlt — nur SVG")

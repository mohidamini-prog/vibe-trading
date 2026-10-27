"""
Terminal-Live-View — zeigt den Orchestra-Zustand als ASCII-Übersicht im Terminal.
Nur stdlib (kein curses nötig), ARM-tauglich. Fürs Phone-Terminal.

Aufruf: .venv/bin/python -m orchestra.visualizer.terminal    (einmal)
        .venv/bin/python -m orchestra.visualizer.terminal --watch   (live, alle 5s)
"""
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.data import cache

AGENT_META = {
    "momentum": {"label": "Momentum"},
    "meanrev": {"label": "MeanRev"},
    "vola": {"label": "Vola/Risk"},
    "quant": {"label": "Quant"},
    "news": {"label": "News/EDGAR"},
}
VOTE_CHAR = {1: "▲", 0: "·", -1: "▼"}


def render():
    last = cache.get_state("last_decision", {})
    hist = cache.get_state("conductor_history", [])
    print("=" * 56)
    print("  🎼 ORCHESTRA — TRADING DESK  (ASCII-View)")
    print("=" * 56)
    if not last:
        print("  Noch keine Entscheidung — warte auf nächsten Scan.")
        return
    dec = last.get("decision", "HOLD")
    s = last.get("S", 0)
    color = "\033[92m" if dec == "BUY" else ("\033[91m" if dec == "SELL" else "\033[0m")
    print(f"  Symbol: {last.get('symbol', '—')}   "
          f"Dirigent: {color}{dec}\033[0m   S={s:+.3f}  "
          f"Stärke={last.get('strength', 0):.2f}")
    if last.get("vetoed"):
        print("  \033[93m⚠️  VETO aktiv (Risiko/News)\033[0m")
    print("-" * 56)
    for v in last.get("votes", []):
        meta = AGENT_META.get(v["agent"], {"label": v["agent"]})
        vote = VOTE_CHAR.get(v["a"], "·")
        # Vote-Farbe
        vc = "\033[92m" if v["a"] == 1 else ("\033[91m" if v["a"] == -1 else "\033[0m")
        w = last.get("weights", {}).get(v["agent"], 0)
        print(f"  {meta['label']:<11} "
              f"{vc}{vote}\033[0m  conf={v['conf']*100:3.0f}%  "
              f"w={w*100:3.0f}%  {v.get('reason', '')[:38]}")
    print("-" * 56)
    if hist:
        s_series = [h.get("S", 0) for h in hist[-30:]]
        print("  S-Verlauf: " + " ".join(
            "▲" if x > 0.5 else ("▼" if x < -0.5 else "·") for x in s_series))
    print(f"  Letzter Scan: {last.get('timestamp', '—')[:19]}  "
          f"({len(hist)} Zyklen gesamt)")
    print()


def watch(interval=5):
    while True:
        try:
            render()
        except Exception as e:
            print(f"  Fehler: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        render()

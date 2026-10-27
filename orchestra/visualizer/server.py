"""
Visualizer-Server — lightweight Echtzeit-Dashboard für den Trading Desk.

Nur stdlib (http.server), kein Flask/npm/React. ARM-tauglich.
Endpunkte:
    /            -> Dashboard (index.html)
    /api/state   -> aktueller Dirigenten-Zustand (votes, weights, decision, S)
    /api/history -> letzte N Entscheidungen (Trend der S-Werte)
    /static/...  -> app.js, style.css
"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Repo-Wurzel in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.data import cache

STATIC_DIR = Path(__file__).resolve().parent / "static"
AGENT_META = {
    "momentum": {"label": "Momentum", "icon": "⚡", "role": "Trend-Folger"},
    "meanrev": {"label": "MeanRev", "icon": "🔄", "role": "Dip-Beifang"},
    "vola": {"label": "Vola/Risk", "icon": "🛡️", "role": "Bremser · VETO"},
    "quant": {"label": "Quant", "icon": "⚛️", "role": "Quant-Meinung"},
    "news": {"label": "News/EDGAR", "icon": "📰", "role": "Event-Filter · VETO"},
}
DECISION_COLOR = {"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#94a3b8"}


def build_state():
    """Aktuellen Dirigenten-Zustand für die API aufbereiten."""
    last = cache.get_state("last_decision", {})
    if not last:
        return {"empty": True, "message": "Noch keine Entscheidung — warte auf nächsten Scan."}
    votes = []
    for v in last.get("votes", []):
        meta = AGENT_META.get(v["agent"], {"label": v["agent"], "icon": "🤖", "role": ""})
        votes.append({
            "agent": v["agent"],
            "label": meta["label"],
            "icon": meta["icon"],
            "role": meta["role"],
            "a": v["a"],
            "conf": v["conf"],
            "reason": v.get("reason", ""),
            "weight": last.get("weights", {}).get(v["agent"], 0),
        })
    history = cache.get_state("conductor_history", [])
    s_series = [h.get("S", 0) for h in history[-30:]]
    return {
        "empty": False,
        "symbol": last.get("symbol"),
        "decision": last.get("decision"),
        "S": last.get("S"),
        "strength": last.get("strength"),
        "avg_confidence": last.get("avg_confidence"),
        "vetoed": last.get("vetoed", False),
        "timestamp": last.get("timestamp"),
        "votes": votes,
        "history": s_series,
        "color": DECISION_COLOR.get(last.get("decision"), "#94a3b8"),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # still
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._send(200, build_state())
        if path == "/api/history":
            hist = cache.get_state("conductor_history", [])
            return self._send(200, hist[-50:])
        # Statische Dateien
        name = "index.html" if path == "/" else path.lstrip("/")
        if name.startswith("static/"):
            name = name[len("static/"):]
        f = (STATIC_DIR / name).resolve()
        if (STATIC_DIR in f.parents or f.parent == STATIC_DIR) and f.exists() and f.is_file():
            ctype = "text/html" if f.suffix == ".html" else (
                "application/javascript" if f.suffix == ".js" else "text/css")
            return self._send(200, f.read_bytes(), ctype)
        return self._send(404, {"error": "not found"})


def run(host="127.0.0.1", port=8643):
    srv = HTTPServer((host, port), Handler)
    print(f"🎼 Orchestra Visualizer: http://{host}:{port}")
    print("   5 Roboter zeigen live ihre Votes; Dirigent zeigt S / Entscheidung.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8643
    run(port=port)
